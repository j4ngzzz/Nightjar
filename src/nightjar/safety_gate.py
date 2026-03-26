"""Behavioral Safety Gate — W1.6.

Compares new verification results against the previous verify.json.
Blocks (returns SafetyGateResult.passed=False) if any previously-passing
stage now fails or times out (regression).

Per Scout 7 S12.S1: 'Block if invariants regress.'
A regression is defined as: a stage that was PASS in the previous run
is now FAIL or TIMEOUT in the new run.

SKIP → FAIL is NOT a regression (stage wasn't proven before).
A stage missing from previous run cannot regress.

References:
- Scout 7 S12.S1: Safety gate — behavioral regression detection
- ARCHITECTURE.md: verify.json stores previous verification state
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from nightjar.types import StageResult, VerifyResult, VerifyStatus


@dataclass
class SafetyGateResult:
    """Result from the behavioral safety gate check.

    Per Scout 7 S12.S1: passed=True means no regressions detected.
    passed=False means at least one previously-passing stage now fails.

    Attributes:
        passed: True if no regression, False if regression detected.
        regressions: List of regression details (stage_name, statuses).
        previous_path: Path to the previous verify.json used for comparison.
    """
    passed: bool
    regressions: list[dict] = field(default_factory=list)
    previous_path: str = ""


def check_regression(
    new_result: VerifyResult,
    previous_result: VerifyResult,
) -> SafetyGateResult:
    """Compare new verification result against previous, detect regressions.

    Per Scout 7 S12.S1: a regression occurs when a stage that was PASS
    in the previous run is now FAIL or TIMEOUT.

    SKIP in previous → FAIL in new is NOT a regression.
    Stage absent from previous → FAIL in new is NOT a regression.

    Args:
        new_result: VerifyResult from the current verification run.
        previous_result: VerifyResult from the previous verification run.

    Returns:
        SafetyGateResult with passed=True if no regressions.
    """
    # Build lookup: stage_name → VerifyStatus for previous PASS stages
    previous_passes: dict[str, VerifyStatus] = {}
    for stage in previous_result.stages:
        if stage.status == VerifyStatus.PASS:
            previous_passes[stage.name] = stage.status

    # Build lookup: stage_name → StageResult for new run
    new_by_name: dict[str, StageResult] = {}
    for stage in new_result.stages:
        new_by_name[stage.name] = stage

    regressions: list[dict] = []
    for stage_name, prev_status in previous_passes.items():
        new_stage = new_by_name.get(stage_name)
        if new_stage is None:
            continue  # Stage missing from new run — not a regression

        if new_stage.status in (VerifyStatus.FAIL, VerifyStatus.TIMEOUT):
            regressions.append({
                "stage_name": stage_name,
                "previous_status": prev_status.value,
                "new_status": new_stage.status.value,
                "errors": new_stage.errors,
            })

    return SafetyGateResult(
        passed=len(regressions) == 0,
        regressions=regressions,
    )


def load_previous_result(verify_json_path: str) -> Optional[VerifyResult]:
    """Load previous VerifyResult from verify.json.

    Args:
        verify_json_path: Path to the verify.json file.

    Returns:
        VerifyResult if file exists and is valid JSON, None otherwise.
    """
    if not os.path.exists(verify_json_path):
        return None

    try:
        with open(verify_json_path, encoding="utf-8") as f:
            data = json.load(f)

        stages = [
            StageResult(
                stage=s["stage"],
                name=s["name"],
                status=VerifyStatus(s["status"]),
                duration_ms=s.get("duration_ms", 0),
                errors=s.get("errors", []),
                counterexample=s.get("counterexample"),
            )
            for s in data.get("stages", [])
        ]

        return VerifyResult(
            verified=data.get("verified", False),
            stages=stages,
            total_duration_ms=data.get("total_duration_ms", 0),
            retry_count=data.get("retry_count", 0),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Malformed verify.json — treat as no previous result
        return None


def save_verify_result(result: VerifyResult, verify_json_path: str) -> None:
    """Save VerifyResult to verify.json.

    Creates parent directories if needed.

    Args:
        result: VerifyResult to serialize.
        verify_json_path: Path to write verify.json.
    """
    os.makedirs(os.path.dirname(verify_json_path) or ".", exist_ok=True)

    data = {
        "verified": result.verified,
        "total_duration_ms": result.total_duration_ms,
        "retry_count": result.retry_count,
        "stages": [
            {
                "stage": s.stage,
                "name": s.name,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "errors": s.errors,
                "counterexample": s.counterexample,
            }
            for s in result.stages
        ],
    }

    with open(verify_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_safety_gate(
    new_result: VerifyResult,
    verify_json_path: str = ".card/verify.json",
) -> SafetyGateResult:
    """Load previous verify.json and check new result for regressions.

    Per Scout 7 S12.S1: blocks the build if any previously-passing stage
    now fails. On first run (no verify.json), always passes.

    After a successful gate check (no regressions), saves the new result
    to verify.json so future runs can compare against it.

    Args:
        new_result: VerifyResult from the current verification run.
        verify_json_path: Path to verify.json (default: .card/verify.json).

    Returns:
        SafetyGateResult with passed=True if no regression detected.
    """
    previous = load_previous_result(verify_json_path)

    if previous is None:
        # First run — no previous state to regress from
        # Save result so next run can compare
        save_verify_result(new_result, verify_json_path)
        return SafetyGateResult(
            passed=True,
            regressions=[],
            previous_path=verify_json_path,
        )

    gate = check_regression(new_result, previous)
    gate.previous_path = verify_json_path

    if gate.passed:
        # No regression — update verify.json to new result
        save_verify_result(new_result, verify_json_path)

    return gate
