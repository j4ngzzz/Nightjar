"""CrossHair symbolic verification of invariant candidates.

Takes a candidate invariant (Python assert expression) and a function under test,
then uses CrossHair's symbolic execution engine (Z3-backed) to explore all
execution paths and determine if the invariant holds universally.

Returns VERIFIED if CrossHair finds no counterexample, COUNTEREXAMPLE if it does,
ERROR for setup issues, or TIMEOUT if analysis exceeds the time budget.

Uses PEP316 docstring contracts (pre:/post:) which CrossHair's default analysis
mode recognizes. The invariant uses ``__return__`` to reference the return value.

References:
- [REF-T09] CrossHair — Python symbolic execution via Z3
- [REF-C06] LLM-Driven Invariant Enrichment (upstream in pipeline)
- [REF-P14] NL2Contract — CrossHair used for contract verification
"""

import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SymbolicVerdict(str, Enum):
    """Outcome of symbolic verification. [REF-T09]"""
    VERIFIED = "verified"
    COUNTEREXAMPLE = "counterexample"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class SymbolicResult:
    """Result of CrossHair symbolic verification. [REF-T09]

    Attributes:
        verdict: The outcome of verification.
        counterexample: If verdict is COUNTEREXAMPLE, the inputs that violate
            the invariant, as a dict of param_name -> value.
        error: If verdict is ERROR, a description of what went wrong.
    """
    verdict: SymbolicVerdict
    counterexample: Optional[dict] = None
    error: Optional[str] = None


def _normalize_invariant(invariant: str) -> str:
    """Convert an invariant expression to CrossHair PEP316 format.

    Replaces 'result' with '__return__' since CrossHair uses PEP316 convention
    where the return value is referenced as ``__return__`` in post-conditions.
    """
    # Replace standalone 'result' with '__return__' for PEP316 compatibility
    # Use word boundary to avoid replacing 'results', 'result_list', etc.
    return re.sub(r'\bresult\b', '__return__', invariant)


def _build_verification_source(
    func_source: str,
    func_name: str,
    invariant: str,
    preconditions: Optional[list[str]] = None,
) -> str:
    """Build a Python source file with PEP316 docstring contracts for CrossHair.

    Injects pre:/post: conditions into the function's docstring so CrossHair's
    default PEP316 analysis mode can verify them. [REF-T09]

    CrossHair PEP316 contract format:
        pre: <precondition expression>
        post: <postcondition expression using __return__>
    """
    preconditions = preconditions or []
    normalized_invariant = _normalize_invariant(invariant)

    # Build the contract docstring lines
    contract_lines = []
    for pre in preconditions:
        contract_lines.append(f"    pre: {pre}")
    contract_lines.append(f"    post: {normalized_invariant}")
    contract_docstring = "\n".join(contract_lines)

    # Parse the function source to inject the docstring
    source = textwrap.dedent(func_source).strip()
    lines = source.split("\n")

    # Find the def line and its indentation
    def_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("def "):
            def_idx = i
            break

    if def_idx == -1:
        raise ValueError(f"No function definition found in source for '{func_name}'")

    # Find the end of the def line (could be multi-line)
    colon_idx = def_idx
    while colon_idx < len(lines) and ":" not in lines[colon_idx].split("#")[0].rsplit("->", 1)[-1]:
        colon_idx += 1

    # Determine body indentation
    body_start = colon_idx + 1
    body_indent = "    "  # default
    if body_start < len(lines):
        body_line = lines[body_start]
        stripped = body_line.lstrip()
        if stripped:
            body_indent = body_line[:len(body_line) - len(stripped)]

    # Check if there's already a docstring and skip it
    has_docstring = False
    docstring_end = body_start
    if body_start < len(lines):
        first_body = lines[body_start].strip()
        if first_body.startswith(('"""', "'''")):
            has_docstring = True
            quote = first_body[:3]
            if first_body.count(quote) >= 2 and len(first_body) > 3:
                # Single-line docstring
                docstring_end = body_start + 1
            else:
                # Multi-line docstring
                for j in range(body_start + 1, len(lines)):
                    if quote in lines[j]:
                        docstring_end = j + 1
                        break

    # Build the new source with injected contract docstring
    new_lines = lines[:body_start]
    new_lines.append(f'{body_indent}"""')
    new_lines.append(contract_docstring)
    new_lines.append(f'{body_indent}"""')
    if has_docstring:
        # Skip the old docstring
        new_lines.extend(lines[docstring_end:])
    else:
        new_lines.extend(lines[body_start:])

    return "\n".join(new_lines) + "\n"


def _parse_crosshair_output(stdout: str, stderr: str) -> SymbolicResult:
    """Parse CrossHair CLI output into a SymbolicResult.

    CrossHair PEP316 output format for counterexamples:
        file.py:3: error: false when calling func(0) (which returns 0)
    No output = invariant verified. [REF-T09]
    """
    combined = (stdout + "\n" + stderr).strip()

    if not combined:
        return SymbolicResult(verdict=SymbolicVerdict.VERIFIED)

    for line in combined.split("\n"):
        line = line.strip()
        if not line:
            continue

        # CrossHair PEP316 error format: "file.py:N: error: <message>"
        if ": error:" in line.lower() or ("false when calling" in line.lower()):
            counterexample = _parse_counterexample(line)
            return SymbolicResult(
                verdict=SymbolicVerdict.COUNTEREXAMPLE,
                counterexample=counterexample,
            )

    # Got output but not a counterexample — could be warnings
    # Check for "no checkable functions" pattern
    if "no checkable functions" in combined.lower():
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="CrossHair found no checkable contracts in the generated source",
        )

    # Unknown output — might be informational, treat as verified if no error
    return SymbolicResult(
        verdict=SymbolicVerdict.ERROR,
        error=combined[:500],
    )


def _parse_counterexample(line: str) -> Optional[dict]:
    """Parse a counterexample from CrossHair PEP316 output.

    Example inputs:
        'file.py:3: error: false when calling identity(0) (which returns 0)'
        'file.py:3: error: false when calling divide(1, 0)'
    Returns:
        {'arg_0': '0'} or {'arg_0': '1', 'arg_1': '0'}
    """
    # PEP316 format: "when calling func(args...)"
    match = re.search(r'when calling \w+\(([^)]*)\)', line)
    if not match:
        return None

    args_str = match.group(1).strip()
    if not args_str:
        return None

    counterexample = {}
    # PEP316 uses positional args like: func(0, -1)
    # or keyword-like: func(x = 0, y = -1)
    for i, arg in enumerate(args_str.split(",")):
        arg = arg.strip()
        if "=" in arg:
            key, val = arg.split("=", 1)
            counterexample[key.strip()] = val.strip()
        else:
            counterexample[f"arg_{i}"] = arg.strip()

    return counterexample if counterexample else None


def verify_invariant_symbolic(
    func_source: str,
    func_name: str,
    invariant: str,
    preconditions: Optional[list[str]] = None,
    timeout_sec: int = 30,
) -> SymbolicResult:
    """Verify an invariant candidate using CrossHair symbolic execution.

    Injects PEP316 docstring contracts into the function and runs CrossHair
    to determine if the invariant holds for all valid inputs. The invariant
    expression should use 'result' to reference the return value (automatically
    converted to '__return__' for PEP316).

    Args:
        func_source: Python source code of the function under test.
        func_name: Name of the function to verify.
        invariant: Python expression that should hold. Use 'result' for return value.
        preconditions: Optional list of Python expressions that restrict inputs.
        timeout_sec: Maximum seconds for CrossHair analysis. [REF-T09]

    Returns:
        SymbolicResult with verdict and optional counterexample or error.

    References:
        [REF-T09] CrossHair — symbolic execution via Z3
        [REF-P14] NL2Contract — contract verification pattern
    """
    if not invariant or not invariant.strip():
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="Invariant expression is empty",
        )

    if not func_source or not func_source.strip():
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="Function source is empty",
        )

    # Check CrossHair is available
    if not _crosshair_available():
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="CrossHair not installed. Install with: pip install crosshair-tool",
        )

    # Build the verification source with PEP316 contracts
    try:
        source = _build_verification_source(
            func_source, func_name, invariant, preconditions
        )
    except (ValueError, IndexError) as e:
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error=f"Failed to build verification source: {e}",
        )

    # Write to temp file and run CrossHair
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="card_symbolic_")
        tmp_file = Path(tmp_dir) / "verify_target.py"
        tmp_file.write_text(source, encoding="utf-8")

        # CrossHair PEP316 mode (default) — no --analysis_kind needed [REF-T09]
        cmd = [
            "python", "-m", "crosshair", "check",
            f"--per_condition_timeout={timeout_sec}",
            str(tmp_file),
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 10,
            cwd=tmp_dir,
        )

        return _parse_crosshair_output(proc.stdout, proc.stderr)

    except subprocess.TimeoutExpired:
        return SymbolicResult(verdict=SymbolicVerdict.TIMEOUT)
    except FileNotFoundError:
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="CrossHair not installed. Install with: pip install crosshair-tool",
        )
    except Exception as e:
        return SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )
    finally:
        if tmp_dir:
            import shutil as _shutil
            _shutil.rmtree(tmp_dir, ignore_errors=True)


def _crosshair_available() -> bool:
    """Check if CrossHair is available (on PATH or as Python module)."""
    if shutil.which("crosshair"):
        return True
    try:
        proc = subprocess.run(
            ["python", "-m", "crosshair", "check", "--help"],
            capture_output=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
