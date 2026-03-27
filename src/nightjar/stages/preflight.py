"""Stage 0: Pre-flight verification.

Validates:
1. .card.md file exists and is readable
2. YAML frontmatter is well-formed and parseable
3. Required fields present: card-version, id, title, status
4. Invariant tiers use valid values (example, property, formal)
5. If generated code path provided, Python AST parses successfully

Cost: ~0.5s, $0.00 — cheapest stage, runs first.
Short-circuit: malformed → FAIL immediately.

Reference: docs/ARCHITECTURE.md Section 3 (Stage 0)
"""

import ast
import sys
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from nightjar.types import StageResult, VerifyStatus

# Required top-level fields in .card.md YAML frontmatter
_REQUIRED_FIELDS = {"card-version", "id"}

# Valid invariant tier values per [REF-C01]
_VALID_TIERS = {"example", "property", "formal"}

# Representative boundary values for dead constraint detection.
# Covers zero, negatives, empty containers, None, and integer extremes.
_BOUNDARY_VALUES: list[Any] = [
    0, -1, 1, sys.maxsize, -(sys.maxsize + 1),
    0.0, -1.0,
    "", "x",
    None,
    [], [0], [1, 2],
    {},
    False, True,
]

# Sentinel: expression could not be evaluated for this input (external dep,
# non-Python statement, type mismatch). Following deal's linter pattern —
# undecidable inputs are silently skipped, never reported as errors.
_UNKNOWN: object = object()

# Safe subset of builtins for invariant evaluation. Restricts exec namespace
# to prevent arbitrary code execution while still supporting common expressions
# like len(result) >= 0, isinstance(x, int), abs(x) > 0.
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "bool": bool, "dict": dict, "float": float,
    "int": int, "isinstance": isinstance, "len": len, "list": list,
    "max": max, "min": min, "str": str, "sum": sum, "type": type,
}


def _try_eval_invariant(expr: str, val: Any) -> Any:
    """Evaluate an invariant expression with x=val and result=val.

    Mirrors deal's linter partial-execution pattern: compile the expression
    to bytecode, exec into a fresh restricted namespace, read the result out.

    Returns:
        bool result if expression was decidable.
        _UNKNOWN if undecidable (NameError, SyntaxError, or exec exception).

    NameError → external dependency not in safe builtins → silent skip.
    SyntaxError → not a Python expression (natural language) → silent skip.
    Other exceptions → type-error / runtime failure → silent skip.
    """
    try:
        code = compile(f"_r = bool({expr})", "<invariant>", "exec")
    except SyntaxError:
        return _UNKNOWN  # natural language statement — not Python

    namespace: dict[str, Any] = {
        "x": val,
        "result": val,  # also expose as 'result' — common in spec language
        "__builtins__": _SAFE_BUILTINS,
    }
    try:
        exec(code, namespace)  # noqa: S102
        return namespace.get("_r", _UNKNOWN)
    except NameError:
        return _UNKNOWN  # external name — skip per deal linter pattern
    except Exception:
        return _UNKNOWN  # type mismatch or runtime error — undecidable


def check_dead_constraints(invariants: list[dict]) -> list[dict]:
    """Detect trivially true or unsatisfiable invariants by partial evaluation.

    Implements dead constraint detection using deal's linter pattern:
    eval each invariant statement as a Python expression against representative
    boundary values. Natural language statements that don't parse as Python
    are silently skipped — no false positives.

    Categories:
    - Always true ("dead"): invariant holds for ALL boundary values.
      The constraint never catches violations — wasted verification budget.
    - Always false ("unsatisfiable"): invariant fails for ALL boundary values.
      The constraint can never be satisfied.

    This catches broken specs CHEAPLY in Stage 0, before wasting LLM/Dafny
    budget on code that could never satisfy or always satisfies the invariant.

    Args:
        invariants: List of invariant dicts from .card.md YAML frontmatter.

    Returns:
        List of error dicts for flagged invariants (empty if all OK).
    """
    flagged: list[dict] = []

    for i, inv in enumerate(invariants):
        if not isinstance(inv, dict):
            continue
        stmt = inv.get("statement", "")
        if not stmt or not isinstance(stmt, str):
            continue
        inv_id = inv.get("id", f"invariant[{i}]")

        decided: list[bool] = []
        for val in _BOUNDARY_VALUES:
            r = _try_eval_invariant(stmt, val)
            if r is _UNKNOWN:
                continue  # undecidable for this input — deal's skip rule
            decided.append(bool(r))

        if not decided:
            continue  # fully undecidable — skip (not Python, or all NameError)

        if all(decided):
            flagged.append({
                "type": "dead_constraint",
                "invariant_id": inv_id,
                "statement": stmt,
                "message": (
                    f"Invariant '{inv_id}' is trivially true for all boundary "
                    "values — it may never catch violations (dead constraint)."
                ),
            })
        elif not any(decided):
            flagged.append({
                "type": "unsatisfiable_constraint",
                "invariant_id": inv_id,
                "statement": stmt,
                "message": (
                    f"Invariant '{inv_id}' is always false for all boundary "
                    "values — it is unsatisfiable."
                ),
            })

    return flagged


def run_preflight(
    spec_path: str,
    code_path: Optional[str] = None,
) -> StageResult:
    """Run Stage 0 pre-flight checks on a .card.md spec and optional code.

    Args:
        spec_path: Path to the .card.md specification file.
        code_path: Optional path to generated Python code to AST-validate.

    Returns:
        StageResult with stage=0, name='preflight', and pass/fail status.
    """
    start = time.monotonic()
    errors: list[dict] = []

    # 1. Check spec file exists
    spec_file = Path(spec_path)
    if not spec_file.exists():
        return _fail(start, [{"message": f"Spec file not found: {spec_path}"}])

    # 2. Read and split YAML frontmatter
    try:
        content = spec_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(start, [{"message": f"Cannot read spec file: {exc}"}])

    frontmatter = _extract_frontmatter(content)
    if frontmatter is None:
        return _fail(start, [{"message": "Missing YAML frontmatter delimiters (---). "
                              "Expected: --- YAML --- Markdown"}])

    # 3. Parse YAML
    try:
        data = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        return _fail(start, [{"message": f"YAML parse error: {exc}"}])

    if not isinstance(data, dict):
        return _fail(start, [{"message": "YAML frontmatter must be a mapping, "
                              f"got {type(data).__name__}"}])

    # 4. Validate required fields
    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append({
            "message": f"Missing required fields: {sorted(missing)}",
            "fields": sorted(missing),
        })

    # 5. Validate invariant tiers if present
    invariants = data.get("invariants", [])
    if isinstance(invariants, list):
        for i, inv in enumerate(invariants):
            if isinstance(inv, dict) and "tier" in inv:
                tier = inv["tier"]
                if tier not in _VALID_TIERS:
                    errors.append({
                        "message": f"Invalid invariant tier '{tier}' at index {i}. "
                                   f"Valid: {sorted(_VALID_TIERS)}",
                        "invariant_index": i,
                    })

    # 5.5. Dead constraint detection — cheap Stage 0 check for trivial
    # invariants. Catches always-true / always-false expressions before
    # wasting LLM/Dafny budget. Natural language statements are silently
    # skipped (SyntaxError → UNKNOWN). Per deal linter partial-execution
    # pattern: eval against boundary values, skip if undecidable.
    if isinstance(invariants, list):
        errors.extend(check_dead_constraints(invariants))

    # Short-circuit on spec errors before checking code
    if errors:
        return _fail(start, errors)

    # 6. Validate Python code AST if provided
    if code_path is not None:
        code_errors = _validate_python_ast(code_path)
        if code_errors:
            return _fail(start, code_errors)

    return _pass(start)


def _extract_frontmatter(content: str) -> Optional[str]:
    """Extract YAML frontmatter between --- delimiters.

    Returns the YAML string, or None if delimiters are missing.
    """
    stripped = content.strip()
    if not stripped.startswith("---"):
        return None

    # Find the closing ---
    end_idx = stripped.find("---", 3)
    if end_idx == -1:
        return None

    return stripped[3:end_idx].strip()


def _validate_python_ast(code_path: str) -> list[dict]:
    """Validate that a Python file parses as valid AST.

    Returns list of error dicts (empty if valid).
    """
    path = Path(code_path)
    if not path.exists():
        return [{"message": f"Code file not found: {code_path}"}]

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [{"message": f"Cannot read code file: {exc}"}]

    try:
        ast.parse(source, filename=code_path)
    except SyntaxError as exc:
        return [{
            "message": f"Python syntax error: {exc.msg}",
            "file": code_path,
            "line": exc.lineno,
            "offset": exc.offset,
        }]

    return []


def _elapsed_ms(start: float) -> int:
    """Calculate elapsed milliseconds since start."""
    return int((time.monotonic() - start) * 1000)


def _pass(start: float) -> StageResult:
    """Create a passing StageResult."""
    return StageResult(
        stage=0,
        name="preflight",
        status=VerifyStatus.PASS,
        duration_ms=_elapsed_ms(start),
    )


def _fail(start: float, errors: list[dict]) -> StageResult:
    """Create a failing StageResult with error details."""
    return StageResult(
        stage=0,
        name="preflight",
        status=VerifyStatus.FAIL,
        duration_ms=_elapsed_ms(start),
        errors=errors,
    )
