"""Scan Python source files and extract invariant candidates from code structure.

Uses stdlib `ast` only — no LLM required for base operation.
Optional LLM enhancement via enhance_with_llm uses litellm.

References:
- [REF-T03] Hypothesis for PBT invariant patterns
- [REF-NEW-06] Oracle lifter for test-to-invariant conversion
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class ScanCandidate:
    """An invariant candidate extracted from Python source."""

    statement: str          # The invariant text (natural language)
    tier: str               # "schema" or "property"
    source: str             # "type_hint", "guard_clause", "docstring", "assertion"
    source_line: int        # Line number in source file
    confidence: float       # 0.0-1.0 based on extraction certainty
    function_name: str      # Which function this came from ("" for module-level)


@dataclass
class ScanResult:
    """Result from scanning a Python source file."""

    module_id: str                      # Derived from filename (e.g. "payment" from "payment.py")
    title: str                          # Title-cased module name
    functions: list[str]                # Discovered function names
    candidates: list[ScanCandidate]     # All extracted candidates
    test_file: Optional[Path]           # Discovered test file, None if not found
    signal_strength: str                # "high" (>=5) | "medium" (2-4) | "low" (<2)


# ── Public API ─────────────────────────────────────────────────────────────────


def scan_file(path: str) -> ScanResult:
    """Deterministic AST scan of a Python file. No LLM. No network.

    Parses the given Python file and extracts invariant candidates from:
    - Type hints (parameter and return annotations)
    - Guard clauses (if X: raise, if not x: return None)
    - Docstrings (Returns: and Raises: sections)
    - Assertion statements

    Args:
        path: Path to a Python source file.

    Returns:
        ScanResult with all extracted candidates and metadata.

    Raises:
        FileNotFoundError: if path does not exist.
    """
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    source = source_path.read_text(encoding="utf-8")
    candidates = scan_file_from_string(source)

    # Derive module_id and title from filename
    stem = source_path.stem  # e.g. "payment_processor"
    module_id = stem
    title = stem.replace("_", " ").replace("-", " ").title()

    # Extract all function names
    functions = _extract_function_names(source)

    # Compute signal strength
    n = len(candidates)
    if n >= 5:
        signal_strength = "high"
    elif n >= 2:
        signal_strength = "medium"
    else:
        signal_strength = "low"

    return ScanResult(
        module_id=module_id,
        title=title,
        functions=functions,
        candidates=candidates,
        test_file=None,
        signal_strength=signal_strength,
    )


def scan_file_from_string(source: str) -> list[ScanCandidate]:
    """Parse a Python source string and extract invariant candidates.

    Pure function — no I/O. Accepts source code directly.

    Args:
        source: Python source code as a string.

    Returns:
        List of ScanCandidate. Empty list if source is empty or unparseable.
    """
    if not source.strip():
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    candidates: list[ScanCandidate] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            fn_name = node.name
            fn_lineno = node.lineno

            # 1. Extract from type hints
            candidates.extend(_extract_type_hints(node))

            # 2. Extract from guard clauses (body statements)
            candidates.extend(_extract_guard_clauses(node))

            # 3. Extract from docstrings
            candidates.extend(_extract_docstring(node))

            # 4. Extract from assertions
            candidates.extend(_extract_assertions(node))

    return candidates


def write_scan_card_md(
    path: str,
    candidates: list[ScanCandidate],
    module_id: str,
) -> str:
    """Write a .card.md file with the extracted invariants.

    Args:
        path: Output path for the .card.md file.
        candidates: Extracted scan candidates to include.
        module_id: Module identifier for the card metadata.

    Returns:
        Path string to the written file.
    """
    content = write_scan_card_md_string(candidates, module_id)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def write_scan_card_md_string(
    candidates: list[ScanCandidate],
    module_id: str,
) -> str:
    """Generate the .card.md content string (no file I/O).

    Args:
        candidates: Extracted scan candidates.
        module_id: Module identifier for the card metadata.

    Returns:
        The .card.md file content as a string.
    """
    title = module_id.replace("_", " ").replace("-", " ").title()

    # Build YAML invariants block
    yaml_entries: list[str] = []
    for i, candidate in enumerate(candidates, 1):
        inv_id = f"INV-{i:03d}"
        statement = candidate.statement.replace('"', '\\"')
        entry = (
            f"  - id: {inv_id}\n"
            f"    tier: {candidate.tier}\n"
            f"    statement: \"{statement}\"\n"
            f"    rationale: \"Extracted from {candidate.source} (line {candidate.source_line})\"\n"
            f"    confidence: {candidate.confidence:.2f}\n"
            f"    function: \"{candidate.function_name}\""
        )
        yaml_entries.append(entry)

    invariants_yaml = "\n".join(yaml_entries) if yaml_entries else "  []"

    # Build Markdown body
    md_lines: list[str] = []
    for i, candidate in enumerate(candidates, 1):
        md_lines.append(f"### INV-{i:03d} [{candidate.tier.upper()}]")
        md_lines.append(f"**{candidate.statement}**")
        md_lines.append(f"- Source: `{candidate.source}` (line {candidate.source_line})")
        md_lines.append(f"- Function: `{candidate.function_name}`")
        md_lines.append(f"- Confidence: {candidate.confidence:.0%}")
        md_lines.append("")

    invariant_list = "\n".join(md_lines) if md_lines else "_No invariants extracted._"

    content = f"""\
---
card-version: "1.0"
id: {module_id}
title: {title}
status: draft
generated-by: nightjar-scan
module:
  owns: []
  depends-on: {{}}
contract:
  inputs: []
  outputs: []
invariants:
{invariants_yaml}
---

## Intent

<!-- Auto-generated by nightjar scan. Review and refine. -->

## Extracted Invariants

The following invariants were extracted from the source code by `nightjar scan`.
All invariants are in `draft` status — review before relying on them in CI.

{invariant_list}

## Acceptance Criteria

<!-- TODO: Add specific acceptance criteria -->

### Story 1 — {title} (P1)

**As a** developer, **I want** {module_id} to satisfy its invariants, **so that** my code is verified.

1. **Given** valid inputs, **When** operations are called, **Then** all invariants hold.

## Functional Requirements

- **FR-001**: System MUST satisfy all invariants listed above.
"""
    return content


def enhance_with_llm(
    candidates: list[ScanCandidate],
    source: str,
) -> list[ScanCandidate]:
    """Optionally enhance extracted candidates with LLM suggestions.

    If an LLM is available (via litellm + environment key), asks the LLM
    to suggest additional invariants beyond what AST extraction finds.
    On any error (no key, network issue, etc.), returns original candidates
    unchanged — never crashes.

    Args:
        candidates: Already-extracted candidates from AST scanning.
        source: The original Python source code (for LLM context).

    Returns:
        Original candidates plus any new LLM-suggested candidates.
        Returns original candidates on any error.
    """
    try:
        import litellm
        import os

        model = os.environ.get("NIGHTJAR_MODEL", "claude-sonnet-4-6")

        existing_statements = "\n".join(
            f"- {c.statement}" for c in candidates
        )

        system_prompt = """\
You are a software specification expert analyzing Python code.
Given the source code and existing extracted invariants, suggest additional
invariants that the AST extractor may have missed.

Focus on:
- Semantic invariants (business rules, ordering, relationships)
- Invariants implied by the code logic, not just types
- Edge cases the existing invariants don't cover

Return a JSON array of invariant statement strings only.
Example: ["result is always non-negative", "items must not be empty on success"]

Return ONLY the JSON array, no other text.
"""

        user_prompt = (
            f"Source code:\n```python\n{source}\n```\n\n"
            f"Existing invariants already extracted:\n{existing_statements}\n\n"
            "Suggest additional invariants as JSON array of strings."
        )

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        raw = (response.choices[0].message.content or "").strip()
        new_statements = _parse_llm_suggestions(raw)

        # Convert LLM suggestions into ScanCandidate objects
        new_candidates = [
            ScanCandidate(
                statement=stmt,
                tier="property",
                source="llm_enhancement",
                source_line=0,
                confidence=0.6,
                function_name="",
            )
            for stmt in new_statements
            if stmt.strip()
        ]
        return candidates + new_candidates

    except Exception:
        # Graceful fallback — never block the pipeline
        return candidates


# ── Private helpers ────────────────────────────────────────────────────────────


def _extract_function_names(source: str) -> list[str]:
    """Extract all function names from source."""
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return names


def _extract_type_hints(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ScanCandidate]:
    """Extract invariants from function type annotations.

    - Return type annotation → schema invariant about result type
    - Parameter annotations → schema invariants about input types
    """
    candidates: list[ScanCandidate] = []
    fn_name = node.name

    # Return type annotation
    if node.returns is not None:
        annotation = node.returns
        type_str = _annotation_to_str(annotation)
        if type_str:
            statement = _return_type_to_statement(type_str, annotation)
            candidates.append(
                ScanCandidate(
                    statement=statement,
                    tier="schema",
                    source="type_hint",
                    source_line=node.lineno,
                    confidence=0.95,
                    function_name=fn_name,
                )
            )

    # Parameter annotations (skip 'self' and 'cls')
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        if arg.annotation is not None:
            type_str = _annotation_to_str(arg.annotation)
            if type_str:
                statement = _param_type_to_statement(arg.arg, type_str, arg.annotation)
                candidates.append(
                    ScanCandidate(
                        statement=statement,
                        tier="schema",
                        source="type_hint",
                        source_line=getattr(arg, "lineno", node.lineno),
                        confidence=0.9,
                        function_name=fn_name,
                    )
                )

    return candidates


def _annotation_to_str(annotation: ast.expr) -> str:
    """Convert an AST annotation node to a readable string."""
    try:
        return ast.unparse(annotation)
    except Exception:
        return ""


def _return_type_to_statement(type_str: str, annotation: ast.expr) -> str:
    """Convert return type annotation to natural language invariant."""
    # Detect Optional[X] — ast.unparse gives "Optional[X]" or "X | None"
    if "Optional" in type_str or "| None" in type_str:
        inner = _extract_optional_inner(type_str)
        return f"result may be None or a {inner}" if inner else "result may be None"

    if type_str.startswith("list") or type_str.startswith("List"):
        return f"result must be a list"

    if type_str.startswith("dict") or type_str.startswith("Dict"):
        return f"result must be a dict"

    if type_str == "None":
        return "function returns None"

    return f"result must be of type {type_str}"


def _param_type_to_statement(param: str, type_str: str, annotation: ast.expr) -> str:
    """Convert parameter type annotation to natural language invariant."""
    if "Optional" in type_str or "| None" in type_str:
        inner = _extract_optional_inner(type_str)
        return f"{param} may be None or a {inner}" if inner else f"{param} may be None"

    if type_str.startswith("list") or type_str.startswith("List"):
        return f"{param} must be a list"

    if type_str.startswith("dict") or type_str.startswith("Dict"):
        return f"{param} must be a dict"

    return f"{param} must be of type {type_str}"


def _extract_optional_inner(type_str: str) -> str:
    """Extract inner type from Optional[X] or X | None."""
    # "Optional[str]" → "str"
    m = re.match(r"Optional\[(.+)\]", type_str)
    if m:
        return m.group(1)
    # "str | None" → "str"
    m = re.match(r"(.+)\s*\|\s*None", type_str)
    if m:
        return m.group(1).strip()
    return ""


def _extract_guard_clauses(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ScanCandidate]:
    """Extract invariants from guard clauses in function body.

    Patterns detected:
    - if X: raise Y → precondition from raise
    - if not x: return None → returns None for falsy input
    - if x is None: raise → must not accept None
    """
    candidates: list[ScanCandidate] = []
    fn_name = node.name

    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.If):
            continue

        # Skip: only handle direct raises or return None inside the if body
        body = stmt.body
        if not body:
            continue

        first_body = body[0]
        test = stmt.test
        lineno = stmt.lineno

        # Pattern: if X: raise Y
        if isinstance(first_body, ast.Raise):
            statement = _guard_raise_to_statement(test, first_body)
            candidates.append(
                ScanCandidate(
                    statement=statement,
                    tier="property",
                    source="guard_clause",
                    source_line=lineno,
                    confidence=0.85,
                    function_name=fn_name,
                )
            )
            continue

        # Pattern: if not x: return None  (first stmt is a Return(None))
        if isinstance(first_body, ast.Return):
            val = first_body.value
            is_none_return = val is None or (
                isinstance(val, ast.Constant) and val.value is None
            )
            if is_none_return:
                cond_str = ast.unparse(test)
                statement = f"returns None when condition holds: {cond_str}"
                candidates.append(
                    ScanCandidate(
                        statement=statement,
                        tier="property",
                        source="guard_clause",
                        source_line=lineno,
                        confidence=0.75,
                        function_name=fn_name,
                    )
                )

    return candidates


def _guard_raise_to_statement(test: ast.expr, raise_node: ast.Raise) -> str:
    """Convert a guard clause (if X: raise Y) to a natural language invariant."""
    test_str = ast.unparse(test)
    exc_str = ""
    if raise_node.exc is not None:
        exc_str = ast.unparse(raise_node.exc)

    # Detect common patterns
    # "x is None" → "must not accept None"
    if re.search(r"\bis None\b", test_str):
        param = test_str.replace("is None", "").strip()
        return f"must reject None for {param}"

    # "not x" → "must reject falsy input"
    if re.match(r"^not\s+\w+$", test_str):
        param = test_str[4:].strip()
        return f"must reject falsy input for {param}"

    # "x < 0" → "must reject negative input"
    if re.search(r"<\s*0", test_str):
        return f"must reject negative input: {test_str}"

    # "x <= 0" → "must reject non-positive input"
    if re.search(r"<=\s*0", test_str):
        return f"must reject non-positive input: {test_str}"

    # "x > max" or "x >= max"
    if re.search(r">", test_str):
        return f"must enforce upper bound: {test_str}"

    # Include error message from ValueError/TypeError if present
    if exc_str and "(" in exc_str:
        # Extract string arg from exception if present
        m = re.search(r"['\"]([^'\"]+)['\"]", exc_str)
        if m:
            return f"must reject when: {m.group(1).lower()}"

    # Generic fallback
    return f"must reject when condition is true: {test_str}"


def _extract_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ScanCandidate]:
    """Extract invariants from function docstrings.

    Handles Google-style docstrings:
    - "Returns:" section → postcondition invariant
    - "Raises:" section → precondition invariant
    """
    candidates: list[ScanCandidate] = []
    fn_name = node.name

    docstring = ast.get_docstring(node)
    if not docstring:
        return candidates

    lineno = node.lineno

    # Parse Google-style sections
    returns_content = _extract_docstring_section(docstring, "Returns")
    raises_content = _extract_docstring_section(docstring, "Raises")

    for line in returns_content:
        line = line.strip()
        if line:
            statement = f"result: {line}"
            candidates.append(
                ScanCandidate(
                    statement=statement,
                    tier="property",
                    source="docstring",
                    source_line=lineno,
                    confidence=0.7,
                    function_name=fn_name,
                )
            )

    for line in raises_content:
        line = line.strip()
        if line:
            statement = f"may raise: {line}"
            candidates.append(
                ScanCandidate(
                    statement=statement,
                    tier="property",
                    source="docstring",
                    source_line=lineno,
                    confidence=0.7,
                    function_name=fn_name,
                )
            )

    return candidates


def _extract_docstring_section(docstring: str, section_name: str) -> list[str]:
    """Extract content lines from a named docstring section.

    Supports Google-style (section followed by indented content).
    """
    lines = docstring.split("\n")
    in_section = False
    content: list[str] = []
    section_header = f"{section_name}:"

    for line in lines:
        stripped = line.strip()
        if stripped == section_header or stripped.startswith(section_header):
            in_section = True
            # Check if content is on the same line after the colon
            remainder = stripped[len(section_header):].strip()
            if remainder:
                content.append(remainder)
            continue

        if in_section:
            # End of section: a non-indented non-empty line that looks like another section
            if stripped and not line.startswith(" ") and not line.startswith("\t"):
                # Could be another section header
                if re.match(r"^\w[\w\s]*:$", stripped):
                    in_section = False
                    continue
            # Collect indented content lines
            if stripped:
                content.append(stripped)
            elif content:
                # Blank line ends the section
                break

    return content


def _extract_assertions(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ScanCandidate]:
    """Extract invariants from assert statements within functions."""
    candidates: list[ScanCandidate] = []
    fn_name = node.name

    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.Assert):
            continue

        test_str = ast.unparse(stmt.test)
        statement = _assert_to_statement(test_str, stmt)
        candidates.append(
            ScanCandidate(
                statement=statement,
                tier="property",
                source="assertion",
                source_line=stmt.lineno,
                confidence=0.8,
                function_name=fn_name,
            )
        )

    return candidates


def _assert_to_statement(test_str: str, node: ast.Assert) -> str:
    """Convert an assert test expression to a natural language invariant."""
    # assert len(result) > 0 → "result must be non-empty"
    m = re.match(r"len\((\w+)\)\s*>\s*0", test_str)
    if m:
        var = m.group(1)
        return f"{var} must be non-empty"

    # assert result >= 0 → "result must be non-negative"
    m = re.match(r"(\w+)\s*>=\s*0", test_str)
    if m:
        var = m.group(1)
        return f"{var} must be non-negative"

    # assert result > 0 → "result must be positive"
    m = re.match(r"(\w+)\s*>\s*0", test_str)
    if m:
        var = m.group(1)
        return f"{var} must be positive"

    # assert X is not None → "X must not be None"
    m = re.match(r"(\w[\w.]*)\s+is\s+not\s+None", test_str)
    if m:
        var = m.group(1)
        return f"{var} must not be None"

    # Use the assert message if present
    if node.msg is not None:
        msg_str = ast.unparse(node.msg)
        # Strip surrounding quotes for string literals
        if msg_str.startswith(("'", '"')):
            msg_str = msg_str.strip("'\"")
        return f"assertion holds: {msg_str}"

    # Generic fallback
    return f"assertion holds: {test_str}"


def _parse_llm_suggestions(raw: str) -> list[str]:
    """Parse LLM JSON output (list of strings) into a list of suggestion strings."""
    import json

    # Unwrap markdown code block if present
    code_block = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if code_block:
        raw = code_block.group(1).strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [s for s in parsed if isinstance(s, str) and s.strip()]
        return []
    except (json.JSONDecodeError, ValueError):
        return []
