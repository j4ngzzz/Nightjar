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
- Scout 3 S4: Dafny optimization flags — 10x+ repeat verification speedup
- Scout 5 F1: /verifySnapshots:3 fine-grained Boogie caching (LPAR 2015,
  MS Research: https://link.springer.com/chapter/10.1007/978-3-319-21690-4_22)

Design per ARCHITECTURE.md Section 3 + Scout 3 S4 + Scout 5 F1:
  Stage 4 runs dafny verify with:
  - --verification-time-limit N: cap per-assertion verification
  - --isolate-assertions: verify each assertion independently
  - /verifySnapshots:3: fine-grained Boogie caching (10x+ repeat speedup)
  - --vcsCores N: parallel verification (auto max(1, cpu_count//2))
  - --progress: stream per-symbol status (parse for live feedback)
  - --filter-position: 90%+ wall time reduction for single-function (optional)
  Only invariants with tier: formal reach this stage.
"""

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import litellm

from nightjar.generator import get_model
from nightjar.types import (
    CardSpec, Invariant, InvariantTier, StageResult, VerifyStatus,
)

# Dafny CLI flags per ARCHITECTURE.md Section 3 and [REF-T01]
DAFNY_VERIFY_TIMEOUT = 15  # seconds per verification task
DAFNY_CMD = os.environ.get("DAFNY_PATH", "dafny")

# Annotation repair constants (dafny-annotator greedy pattern [REF-T02])
ANNOTATION_MAX_TOKENS = 256
ANNOTATION_TEMPERATURE = 0.2
# Valid Dafny annotation keywords — the only things the repair model may insert
ANNOTATION_KEYWORDS = ("assert", "invariant", "decreases")


def _get_vcs_cores() -> int:
    """Compute parallel verification cores: max(1, cpu_count // 2).

    Per Scout 3 S4.2: near-linear speedup across independent procedures.
    Uses half of available cores to avoid starving other processes.
    Scout 5 caveat: output becomes interleaved when vcsCores > 1 — handled
    by deinterleave_progress().
    """
    cpu_count = os.cpu_count() or 4
    return max(1, cpu_count // 2)


def parse_progress_events(output: str) -> list[dict]:
    """Parse Dafny --progress output into structured progress events.

    Per Scout 5 F8 + Dafny PR #5218: --progress streams lines like:
      'Verifying Process (0/2)...'
      'Verified: Process (2/2)'

    Args:
        output: Raw stdout from dafny verify --progress.

    Returns:
        List of dicts with keys: 'symbol', 'status'.
    """
    events: list[dict] = []
    # Match "Verifying <symbol> (<n>/<total>)..." or "Verified: <symbol> ..."
    verify_pattern = re.compile(
        r"^(?:(Verifying)\s+(.+?)\s+\(\d+/\d+\)|(Verified):\s+(.+?))(?:\s*\.{3})?$",
        re.MULTILINE,
    )
    for match in verify_pattern.finditer(output):
        if match.group(1):  # "Verifying <symbol>"
            symbol = match.group(2).strip()
            status = "verifying"
        else:  # "Verified: <symbol>"
            symbol = match.group(4).strip()
            status = "verified"
        if symbol:
            events.append({"symbol": symbol, "status": status})
    return events


def deinterleave_progress(lines: list[str]) -> list[str]:
    """Sort interleaved Dafny --progress output for clean display.

    Per Scout 5 caveat: 'With --vcsCores:4, output becomes interleaved.
    Need to parse and deinterleave for clean display.'

    Strategy: stable sort — Verifying lines before Verified lines for
    each symbol, preserving order within each group.

    Args:
        lines: List of progress output lines (potentially interleaved).

    Returns:
        Sorted list where each symbol's 'Verifying' precedes 'Verified'.
    """
    # Separate into verifying (in-progress) and verified (complete) groups
    verifying = [l for l in lines if l.strip().startswith("Verifying")]
    verified = [l for l in lines if l.strip().startswith("Verified:")]
    other = [
        l for l in lines
        if not l.strip().startswith(("Verifying", "Verified:"))
    ]
    # Return in logical order: in-progress first, then completed, then other
    return verifying + verified + other


def _filter_formal_invariants(invariants: list[Invariant]) -> list[Invariant]:
    """Filter to only formal tier invariants [REF-C01].

    Only formal-tier invariants require mathematical proof via Dafny.
    Property-tier invariants are handled by Stage 3 PBT.
    Example-tier invariants are unit tests.
    """
    return [inv for inv in invariants if inv.tier == InvariantTier.FORMAL]


def _run_dafny_verify(
    dfy_path: str,
    filter_position: Optional[str] = None,
    filter_symbol: Optional[str] = None,
) -> tuple[int, str, str]:
    """Execute `dafny verify` on a .dfy file.

    CLI flags per [REF-T01], ARCHITECTURE.md, Scout 3 S4, Scout 5 F1:
    - --verification-time-limit N: cap per-assertion verification
    - --isolate-assertions: verify each assertion independently
    - /verifySnapshots:3: fine-grained Boogie caching (LPAR 2015, 10x+ repeat)
    - --vcsCores N: parallel verification (max(1, cpu_count//2))
    - --progress: stream per-symbol status for live feedback
    - --filter-position: 90%+ wall time reduction for single function (optional)
    - --filter-symbol: skip unchanged procedures by name (optional)

    Args:
        dfy_path: Path to the .dfy file to verify.
        filter_position: Optional '<file>:<line>' to verify single function.
            Per Scout 3 S4.2: provides 90%+ wall time reduction.
        filter_symbol: Optional procedure name to verify by name.
            Per Scout 3 S4.2: skips all other procedures.

    Returns:
        Tuple of (return_code, stdout, stderr).

    Raises:
        FileNotFoundError: If dafny binary is not installed.
        TimeoutError: If verification exceeds overall timeout.
    """
    vcs_cores = _get_vcs_cores()

    cmd = [
        DAFNY_CMD,
        "verify",
        str(dfy_path),
        f"--verification-time-limit:{DAFNY_VERIFY_TIMEOUT}",
        "--isolate-assertions",
        "/verifySnapshots:3",         # Fine-grained Boogie caching [Scout 5 F1, LPAR 2015]
        f"--vcsCores:{vcs_cores}",    # Parallel verification [Scout 3 S4.2]
        "--progress",                 # Stream per-symbol status [Scout 5 F8]
    ]

    # Optional: target single function (90%+ wall time reduction) [Scout 3 S4.2]
    if filter_position:
        cmd.append(f"--filter-position:{filter_position}")

    # Optional: target single procedure by name [Scout 3 S4.2]
    if filter_symbol:
        cmd.append(f"--filter-symbol:{filter_symbol}")

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

    Per [REF-T01], [REF-P02], [REF-P06], Scout 3 S4, Scout 5 F1:
    1. Filter invariants to formal tier only [REF-C01]
    2. Write Dafny code to temp file
    3. Run `dafny verify` with optimization flags [Scout 3 S4, Scout 5 F1]
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

        # Step 3: Run dafny verify with optimization flags
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


# ─── Dafny Annotation Repair (dafny-annotator greedy pattern [REF-T02]) ──────
# Per metareflection/dafny-annotator: greedy search inserts ONE annotation at a
# time and re-verifies after each, rather than bulk-inserting. This is surgical —
# most Dafny failures need just 1-2 missing invariants.
#
# Algorithm from dafny-annotator annotate():
#   1. Identify error location from Dafny output
#   2. Prompt LLM for ONE annotation (invariant/assert/decreases)
#   3. Insert annotation just before error location
#   4. Return patched code (caller re-verifies)
#
# Three-valued feedback (FAIL / partial progress / SUCCESS) is handled by the
# caller (retry.py) via re-verification.


def _build_annotation_prompt(dafny_code: str, error: dict, spec: CardSpec) -> str:
    """Build a prompt asking the LLM for ONE annotation to fix a Dafny error.

    Per dafny-annotator: show the code context around the error and ask for
    exactly one annotation (invariant/assert/decreases). The model sees the
    nearby lines so it can choose an appropriate annotation type and value.

    Args:
        dafny_code: Full Dafny source code that failed verification.
        error: Structured error dict from parse_dafny_output() with keys
               "line", "type", "message".
        spec: Original CardSpec — provides invariant context.

    Returns:
        Formatted prompt string for the annotation LLM call.
    """
    lines = dafny_code.splitlines()
    error_line = error.get("line", 1)
    error_type = error.get("type", "other")
    error_msg = error.get("message", "")

    # Show up to 8 lines of context centred on the error
    context_start = max(0, error_line - 6)
    context_end = min(len(lines), error_line + 3)
    numbered = "\n".join(
        f"{context_start + i + 1:4d} | {line}"
        for i, line in enumerate(lines[context_start:context_end])
    )

    spec_invariants = "\n".join(
        f"  - {inv.id}: {inv.statement}"
        for inv in spec.invariants
    )

    return (
        f"The following Dafny code fails to verify at line {error_line}.\n"
        f"Error type: {error_type}\n"
        f"Error: {error_msg}\n\n"
        f"Code context (around error line):\n"
        f"```\n{numbered}\n```\n\n"
        f"Spec invariants that must hold:\n{spec_invariants}\n\n"
        f"Suggest ONE Dafny annotation (invariant, assert, or decreases clause) "
        f"to help Dafny prove this. It will be inserted just before line {error_line}.\n"
        f"Return ONLY the single annotation line. Examples:\n"
        f"  invariant 0 <= i <= |s|\n"
        f"  assert x >= 0;\n"
        f"  decreases n - i\n"
    )


def _insert_annotation_at_line(dafny_code: str, line_number: int, annotation: str) -> str:
    """Insert an annotation just before the specified 1-based line number.

    Per dafny-annotator: annotations are inserted at valid positions relative
    to the error location. The indentation is matched to the target line so
    the inserted line is syntactically clean.

    Args:
        dafny_code: Full Dafny source code.
        line_number: 1-based line number — annotation is inserted before this line.
        annotation: The annotation text (may or may not be indented).

    Returns:
        New Dafny code string with annotation inserted.
    """
    lines = dafny_code.splitlines()
    # Clamp to valid range
    insert_idx = max(0, min(line_number - 1, len(lines)))

    # Infer indentation from the target line
    if insert_idx < len(lines):
        target = lines[insert_idx]
        indent = len(target) - len(target.lstrip())
        indent_str = target[:indent]
    else:
        indent_str = "    "

    indented = f"{indent_str}{annotation.strip()}"
    new_lines = lines[:insert_idx] + [indented] + lines[insert_idx:]
    return "\n".join(new_lines)


def attempt_annotation_repair(
    dafny_code: str,
    errors: list[dict],
    spec: CardSpec,
) -> Optional[str]:
    """Try to repair Dafny verification failures by adding ONE surgical annotation.

    Implements the dafny-annotator greedy search pattern [REF-T02]:
    1. Find the first error that has a known line location
    2. Ask the LLM (via litellm) for ONE annotation to fix it
    3. Validate the annotation contains a known Dafny keyword
    4. Insert the annotation just before the error line
    5. Return the patched code — the caller (retry.py) re-verifies

    Key insight: one annotation at a time is surgical. dafny-annotator's
    benchmark shows most Dafny failures need just 1-2 missing invariants.
    Bulk insertion risks introducing new errors; greedy repair does not.

    All LLM calls go through litellm [REF-T16]. Model selected from
    NIGHTJAR_MODEL env var.

    Args:
        dafny_code: Generated Dafny code that failed formal verification.
        errors: Structured error list from parse_dafny_output() — each dict
                has "line", "column", "type", "message".
        spec: Original CardSpec — provides invariant context for the prompt.

    Returns:
        Patched Dafny code string with one annotation inserted, or None if:
        - No errors have line numbers (can't locate insertion point)
        - LLM returns empty or non-annotation content
    """
    # Only handle errors with known line locations (dafny-annotator requirement)
    located = [e for e in errors if e.get("line") is not None]
    if not located:
        return None

    # Take the first located error — greedy: fix one at a time
    error = located[0]

    model = get_model()  # NIGHTJAR_MODEL env var → default; centralised in get_model()
    prompt = _build_annotation_prompt(dafny_code, error, spec)

    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Dafny annotation expert. "
                    "When given a verification failure, suggest ONE loop invariant, "
                    "assertion, or decreases clause that helps Dafny prove the code. "
                    "Return ONLY the single annotation line — no explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=ANNOTATION_TEMPERATURE,
        max_tokens=ANNOTATION_MAX_TOKENS,
    )

    annotation = response.choices[0].message.content
    if not annotation or not annotation.strip():
        return None

    annotation = annotation.strip()

    # Validate: must contain a recognised Dafny annotation keyword
    if not any(kw in annotation.lower() for kw in ANNOTATION_KEYWORDS):
        return None

    return _insert_annotation_at_line(dafny_code, error["line"], annotation)
