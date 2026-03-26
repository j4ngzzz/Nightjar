"""Stage 4 — Dafny Formal Verification.

Runs `dafny verify` on generated Dafny code and parses structured errors.
Only invariants with tier: formal reach this stage [REF-C01].

References:
- [REF-T01] Dafny CLI: `dafny verify module.dfy --verification-time-limit 15
  --isolate-assertions`
- [REF-P02] Vericoding benchmark — 82-96% Dafny success rate with LLMs
- [REF-P06] DafnyPro — structured error format with assertion batch IDs and
  resource units consumed for targeted LLM repair
- [REF-T02] dafny-annotator — reference for LLM→Dafny feedback pattern

Design per ARCHITECTURE.md Section 3:
  Stage 4 runs dafny verify with --verification-time-limit 15,
  --isolate-assertions, --boogie /vcsCores:4.
  Only invariants with tier: formal reach this stage.
  On failure: error context includes file, line, message, assertion batch,
  resource units [REF-P06].
"""

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from contractd.types import (
    CardSpec, Invariant, InvariantTier, StageResult, VerifyStatus,
)

# Dafny CLI flags per ARCHITECTURE.md Section 3 and [REF-T01]
DAFNY_VERIFY_TIMEOUT = 15  # seconds per verification task
DAFNY_CMD = os.environ.get("DAFNY_PATH", "dafny")


def _filter_formal_invariants(invariants: list[Invariant]) -> list[Invariant]:
    """Filter to only formal tier invariants [REF-C01].

    Only formal-tier invariants require mathematical proof via Dafny.
    Property-tier invariants are handled by Stage 3 PBT.
    Example-tier invariants are unit tests.
    """
    return [inv for inv in invariants if inv.tier == InvariantTier.FORMAL]


def _run_dafny_verify(dfy_path: str) -> tuple[int, str, str]:
    """Execute `dafny verify` on a .dfy file.

    CLI flags per [REF-T01] and ARCHITECTURE.md:
    - --verification-time-limit 15: cap per-assertion verification
    - --isolate-assertions: verify each assertion independently
      (helps pinpoint which assertion fails)

    Returns:
        Tuple of (return_code, stdout, stderr).

    Raises:
        FileNotFoundError: If dafny binary is not installed.
        TimeoutError: If verification exceeds overall timeout.
    """
    cmd = [
        DAFNY_CMD,
        "verify",
        str(dfy_path),
        f"--verification-time-limit:{DAFNY_VERIFY_TIMEOUT}",
        "--isolate-assertions",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=DAFNY_VERIFY_TIMEOUT * 4,  # Overall timeout = 4x per-assertion
    )

    return result.returncode, result.stdout, result.stderr


def parse_dafny_output(output: str) -> list[dict]:
    """Parse Dafny verification output into structured error dicts.

    Dafny error format per [REF-T01] and [REF-P06] DafnyPro:
      file.dfy(line,col): Error: message

    Returns list of error dicts with keys:
    - file: source filename
    - line: 1-based line number
    - column: 0-based column
    - message: error description
    - type: error classification (postcondition_failure, assertion_failure, etc.)

    Per [REF-P06], structured errors enable targeted LLM repair:
    include file, line, error message, assertion batch, resource units.
    """
    errors: list[dict] = []

    # Pattern matches: filename(line,col): Error: message
    error_pattern = re.compile(
        r"^(.+?)\((\d+),(\d+)\):\s*Error:\s*(.+)$",
        re.MULTILINE,
    )

    for match in error_pattern.finditer(output):
        file_name = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        message = match.group(4).strip()

        # Classify error type per [REF-P06] DafnyPro structured format
        error_type = _classify_dafny_error(message)

        errors.append({
            "file": file_name,
            "line": line,
            "column": column,
            "message": message,
            "type": error_type,
        })

    return errors


def _classify_dafny_error(message: str) -> str:
    """Classify a Dafny error message into a category.

    Categories per [REF-P06] DafnyPro structured error format:
    - postcondition_failure: ensures clause not satisfied
    - precondition_failure: requires clause not met at call site
    - assertion_failure: explicit assert statement failed
    - loop_invariant_failure: loop invariant not maintained
    - decreases_failure: termination measure not decreasing
    - other: unclassified
    """
    lower = message.lower()
    if "postcondition" in lower:
        return "postcondition_failure"
    if "precondition" in lower:
        return "precondition_failure"
    if "assertion" in lower or "assert" in lower:
        return "assertion_failure"
    if "invariant" in lower and "loop" in lower:
        return "loop_invariant_failure"
    if "decreases" in lower:
        return "decreases_failure"
    return "other"


def run_formal(spec: CardSpec, dfy_code: str) -> StageResult:
    """Run Stage 4 — Dafny Formal Verification on generated code.

    Per [REF-T01], [REF-P02], and [REF-P06]:
    1. Filter invariants to formal tier only [REF-C01]
    2. Write Dafny code to temp file
    3. Run `dafny verify` with --isolate-assertions [REF-T01]
    4. Parse output into structured errors [REF-P06]
    5. Return pass/fail with error context for retry loop

    Args:
        spec: Parsed .card.md specification with invariants.
        dfy_code: Generated Dafny source code string.

    Returns:
        StageResult with stage=4, status=PASS/FAIL/SKIP/TIMEOUT.
    """
    start = time.monotonic()

    # Step 1: Filter to formal-tier invariants [REF-C01]
    formal_invariants = _filter_formal_invariants(spec.invariants)

    if not formal_invariants:
        return StageResult(
            stage=4,
            name="formal",
            status=VerifyStatus.SKIP,
            duration_ms=0,
        )

    # Step 2: Write Dafny code to temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dfy", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(dfy_code)
            tmp_path = tmp.name

        # Step 3: Run dafny verify [REF-T01]
        returncode, stdout, stderr = _run_dafny_verify(tmp_path)

        duration = int((time.monotonic() - start) * 1000)

        # Step 4: Parse output [REF-P06]
        combined_output = stdout + "\n" + stderr
        errors = parse_dafny_output(combined_output)

        # Step 5: Determine status
        if returncode == 0 and not errors:
            return StageResult(
                stage=4,
                name="formal",
                status=VerifyStatus.PASS,
                duration_ms=duration,
            )
        else:
            return StageResult(
                stage=4,
                name="formal",
                status=VerifyStatus.FAIL,
                duration_ms=duration,
                errors=errors if errors else [{
                    "type": "verification_failure",
                    "message": combined_output.strip(),
                }],
            )

    except TimeoutError:
        duration = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=4,
            name="formal",
            status=VerifyStatus.TIMEOUT,
            duration_ms=duration,
            errors=[{
                "type": "timeout",
                "error": f"Dafny verification timed out after {DAFNY_VERIFY_TIMEOUT}s",
            }],
        )

    except FileNotFoundError as e:
        duration = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=4,
            name="formal",
            status=VerifyStatus.FAIL,
            duration_ms=duration,
            errors=[{
                "type": "dafny_not_found",
                "error": f"Dafny binary not found: {e}. Install from https://github.com/dafny-lang/dafny",
            }],
        )

    finally:
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except (NameError, OSError):
            pass
