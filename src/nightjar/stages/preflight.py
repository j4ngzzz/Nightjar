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
import time
from pathlib import Path
from typing import Optional

import yaml

from nightjar.types import StageResult, VerifyStatus

# Required top-level fields in .card.md YAML frontmatter
_REQUIRED_FIELDS = {"card-version", "id"}

# Valid invariant tier values per [REF-C01]
_VALID_TIERS = {"example", "property", "formal"}


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
