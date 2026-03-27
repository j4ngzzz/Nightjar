"""Scrapling-inspired function fingerprinting for invariant rehydration.

When Nightjar regenerates code from scratch, previously discovered invariants
are lost because function names/signatures may change. This module fingerprints
Python functions by their structural shape and uses similarity matching to
carry invariants over to regenerated code — mirroring Scrapling's approach of
re-finding HTML elements after DOM changes by multi-field structural fingerprint
rather than brittle CSS selectors.

Scrapling's ``_StorageTools.element_to_dict`` (D4Vinci/Scrapling) captures:
    tag + attributes + text + DOM path + parent info + siblings + children

We capture the analogous structural fields for Python functions:
    signature + docstring + return type + called functions + complexity

Similarity is computed as a weighted sum across all dimensions, matching
Scrapling's multi-field scoring approach.

References:
    - D4Vinci/Scrapling scrapling/core/utils/_utils.py — element_to_dict,
      structural fingerprint pattern (tag + attrs + text + path + context)
    - D4Vinci/Scrapling scrapling/core/storage.py — save/retrieve fingerprints,
      similarity-based re-matching after DOM changes
    - [REF-T10] icontract — runtime contract enforcement
    - [REF-C09] Immune System — runtime enforcement stage
"""

from __future__ import annotations

import ast
import hashlib


def fingerprint_function(source: str, func_name: str) -> dict:
    """Extract a structural fingerprint of a named function from source code.

    Mirrors Scrapling's ``element_to_dict``: instead of tag + attributes +
    text + path, we capture the analogous structural properties of a Python
    function:

        - ``params``: parameter names, type annotations, and default presence
        - ``param_names``: frozenset of names (for fast set operations)
        - ``docstring_hash``: SHA-256 prefix of the docstring (None if absent)
        - ``return_type``: unparsed return annotation string (None if absent)
        - ``called_functions``: frozenset of called function/method names
        - ``complexity``: 1 + count of branches/loops/exception-handlers

    Args:
        source: Full Python source code (may contain multiple functions).
        func_name: Name of the function to fingerprint.

    Returns:
        Dict with the fields above, keyed by name.
        Returns an empty dict if the function is not found or source is invalid.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    func_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                func_node = node
                break

    if func_node is None:
        return {}

    # --- Parameters (mirroring Scrapling's "attributes" field) ---
    params: list[dict] = []
    args_obj = func_node.args

    # positional-only, regular, keyword-only (vararg/kwarg excluded from param_names)
    positional = args_obj.posonlyargs + args_obj.args
    defaults_offset = len(positional) - len(args_obj.defaults)

    for i, arg in enumerate(positional):
        annotation = ast.unparse(arg.annotation) if arg.annotation else None
        params.append({
            "name": arg.arg,
            "annotation": annotation,
            "has_default": i >= defaults_offset,
        })

    kw_defaults = args_obj.kw_defaults  # parallel to kwonlyargs; None = no default
    for i, arg in enumerate(args_obj.kwonlyargs):
        annotation = ast.unparse(arg.annotation) if arg.annotation else None
        params.append({
            "name": arg.arg,
            "annotation": annotation,
            "has_default": kw_defaults[i] is not None,
        })

    param_names = frozenset(p["name"] for p in params)

    # --- Docstring (mirroring Scrapling's "text" field) ---
    docstring_hash: str | None = None
    body = func_node.body
    if (body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        docstring_hash = hashlib.sha256(
            body[0].value.value.encode()
        ).hexdigest()[:16]

    # --- Return type (mirroring Scrapling's "tag" — most distinctive field) ---
    return_type: str | None = None
    if func_node.returns:
        return_type = ast.unparse(func_node.returns)

    # --- Called functions (mirroring Scrapling's "children" field) ---
    called_functions: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_functions.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_functions.add(node.func.attr)

    # --- Complexity (mirroring Scrapling's "siblings" count — structural shape) ---
    # McCabe-like: start at 1, add 1 per branch/loop/handler/comprehension
    complexity = 1
    for node in ast.walk(func_node):
        if isinstance(node, (
            ast.If, ast.For, ast.While, ast.Try,
            ast.With, ast.ExceptHandler, ast.comprehension,
            ast.TryStar,  # Python 3.11+ except*
        )):
            complexity += 1

    return {
        "name": func_name,
        "params": params,
        "param_names": param_names,
        "docstring_hash": docstring_hash,
        "return_type": return_type,
        "called_functions": frozenset(called_functions),
        "complexity": complexity,
    }


def similarity_score(fp1: dict, fp2: dict) -> float:
    """Compute 0.0–1.0 structural similarity between two function fingerprints.

    Mirrors Scrapling's multi-field element matching: each structural dimension
    contributes a weighted score, and the total is their weighted sum.

    Weights (sum to 1.0):
        signature match:         0.50  — most stable identity indicator
        called_functions match:  0.30  — captures "what the function does"
        complexity match:        0.15  — rough shape
        return_type match:       0.05  — often omitted, so lowest weight

    Signature and called_functions use Jaccard similarity (|A∩B| / |A∪B|).
    Complexity uses a normalised absolute-difference score.
    Return type uses exact string equality.

    Args:
        fp1: Fingerprint dict from fingerprint_function.
        fp2: Fingerprint dict from fingerprint_function.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 if either fingerprint is empty.
    """
    if not fp1 or not fp2:
        return 0.0

    # Signature similarity — Jaccard on param name sets
    p1: frozenset = fp1.get("param_names", frozenset())
    p2: frozenset = fp2.get("param_names", frozenset())
    if not p1 and not p2:
        sig_score = 1.0  # Both have no params — identical shape
    elif not p1 or not p2:
        sig_score = 0.0  # One has params, other doesn't
    else:
        union = len(p1 | p2)
        sig_score = len(p1 & p2) / union if union else 0.0

    # Called-functions similarity — Jaccard
    c1: frozenset = fp1.get("called_functions", frozenset())
    c2: frozenset = fp2.get("called_functions", frozenset())
    if not c1 and not c2:
        call_score = 1.0
    elif not c1 or not c2:
        call_score = 0.0
    else:
        union = len(c1 | c2)
        call_score = len(c1 & c2) / union if union else 0.0

    # Complexity similarity — normalised absolute difference
    comp1: int = fp1.get("complexity", 1)
    comp2: int = fp2.get("complexity", 1)
    max_comp = max(comp1, comp2, 1)
    comp_score = 1.0 - abs(comp1 - comp2) / max_comp

    # Return type similarity — exact match
    r1 = fp1.get("return_type")
    r2 = fp2.get("return_type")
    ret_score = 1.0 if r1 == r2 else 0.0

    return (
        0.50 * sig_score
        + 0.30 * call_score
        + 0.15 * comp_score
        + 0.05 * ret_score
    )


def match_functions(
    old_fingerprints: dict[str, dict],
    new_source: str,
    threshold: float = 0.7,
) -> dict[str, str]:
    """Map old function names to best-matching functions in regenerated source.

    After Nightjar regenerates code from scratch, this mirrors Scrapling's
    element re-finding strategy: given stored fingerprints (old DOM state) and
    new source (new DOM), find the best structural match for each element above
    a similarity threshold.

    Uses greedy assignment (highest similarity first) so each old and new
    function is matched at most once — analogous to how Scrapling picks the
    highest-scoring element candidate for each stored selector.

    Args:
        old_fingerprints: Mapping of {old_func_name: fingerprint_dict}.
        new_source: Full Python source code after regeneration.
        threshold: Minimum similarity score to accept a match (default 0.7).

    Returns:
        Mapping of {old_name: new_name} for functions matched above threshold.
        Functions with no match are excluded.
    """
    try:
        tree = ast.parse(new_source)
    except SyntaxError:
        return {}

    new_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    new_fingerprints: dict[str, dict] = {
        name: fingerprint_function(new_source, name) for name in new_names
    }

    # Score all (old, new) pairs that meet the threshold
    scored: list[tuple[float, str, str]] = []
    for old_name, old_fp in old_fingerprints.items():
        if not old_fp:
            continue
        for new_name, new_fp in new_fingerprints.items():
            score = similarity_score(old_fp, new_fp)
            if score >= threshold:
                scored.append((score, old_name, new_name))

    # Greedy assignment: best scores first, each function matched at most once
    scored.sort(key=lambda x: x[0], reverse=True)
    matches: dict[str, str] = {}
    used_old: set[str] = set()
    used_new: set[str] = set()

    for score, old_name, new_name in scored:
        if old_name not in used_old and new_name not in used_new:
            matches[old_name] = new_name
            # Store confidence on the result via a separate dict if callers need it
            used_old.add(old_name)
            used_new.add(new_name)

    return matches


def match_functions_with_confidence(
    old_fingerprints: dict[str, dict],
    new_source: str,
    threshold: float = 0.7,
) -> dict[str, dict]:
    """Like match_functions but returns confidence scores alongside matches.

    Args:
        old_fingerprints: Mapping of {old_func_name: fingerprint_dict}.
        new_source: Full Python source code after regeneration.
        threshold: Minimum similarity score to accept a match (default 0.7).

    Returns:
        Mapping of {old_name: {"new_name": str, "confidence": float}}.
    """
    try:
        tree = ast.parse(new_source)
    except SyntaxError:
        return {}

    new_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    new_fingerprints: dict[str, dict] = {
        name: fingerprint_function(new_source, name) for name in new_names
    }

    scored: list[tuple[float, str, str]] = []
    for old_name, old_fp in old_fingerprints.items():
        if not old_fp:
            continue
        for new_name, new_fp in new_fingerprints.items():
            score = similarity_score(old_fp, new_fp)
            if score >= threshold:
                scored.append((score, old_name, new_name))

    scored.sort(key=lambda x: x[0], reverse=True)
    result: dict[str, dict] = {}
    used_old: set[str] = set()
    used_new: set[str] = set()

    for score, old_name, new_name in scored:
        if old_name not in used_old and new_name not in used_new:
            result[old_name] = {"new_name": new_name, "confidence": round(score, 4)}
            used_old.add(old_name)
            used_new.add(new_name)

    return result


def rehydrate_invariants(
    old_invariants: dict[str, list],
    matches: dict[str, str],
) -> dict[str, list]:
    """Transfer invariants from old function names to matched new function names.

    The final step of the Scrapling-inspired rehydration pipeline:
    once match_functions has identified which old function corresponds to
    which regenerated function, transfer the verified invariants so they
    apply to the new code.

    Invariants for functions without a match are silently excluded — they
    were lost in regeneration and must be rediscovered by the mining pipeline.

    Args:
        old_invariants: Mapping of {old_func_name: [invariant, ...]} where
            each invariant can be any object (InvariantSpec, dict, str, etc.).
        matches: Mapping of {old_func_name: new_func_name} from match_functions,
            OR {old_func_name: {"new_name": str, "confidence": float}} from
            match_functions_with_confidence. Both forms are accepted.

    Returns:
        Mapping of {new_func_name: [invariant, ...]} for matched functions only.
    """
    rehydrated: dict[str, list] = {}
    for old_name, match_value in matches.items():
        # Accept both plain str (from match_functions) and
        # {"new_name": ..., "confidence": ...} (from match_functions_with_confidence)
        if isinstance(match_value, dict):
            new_name = match_value["new_name"]
        else:
            new_name = match_value
        if old_name in old_invariants:
            rehydrated[new_name] = list(old_invariants[old_name])
    return rehydrated
