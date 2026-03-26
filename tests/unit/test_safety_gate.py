"""Tests for W1.6 — Behavioral Safety Gate.

Compares new verification results against previous verify.json.
Blocks if previously-passing stages now fail (regression detection).

References:
- Scout 7 S12.S1: Safety gate — block if invariants regress
- ARCHITECTURE.md: verify.json stores previous verification state
"""

import json
import os
import tempfile
import pytest
from nightjar.types import (
    StageResult, VerifyResult, VerifyStatus,
)


def _pass_stage(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.PASS)


def _fail_stage(stage: int, name: str) -> StageResult:
    return StageResult(
        stage=stage, name=name, status=VerifyStatus.FAIL,
        errors=[{"type": "test_failure", "message": "stage failed"}],
    )


def _skip_stage(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.SKIP)


class TestSafetyGateImports:
    """Safety gate module is importable with expected API."""

    def test_module_importable(self):
        """safety_gate module is importable from nightjar."""
        from nightjar import safety_gate
        assert safety_gate is not None

    def test_run_safety_gate_callable(self):
        """run_safety_gate function is importable and callable."""
        from nightjar.safety_gate import run_safety_gate
        assert callable(run_safety_gate)

    def test_check_regression_callable(self):
        """check_regression function is importable and callable."""
        from nightjar.safety_gate import check_regression
        assert callable(check_regression)

    def test_safety_gate_result_importable(self):
        """SafetyGateResult dataclass is importable."""
        from nightjar.safety_gate import SafetyGateResult
        assert SafetyGateResult is not None


class TestCheckRegression:
    """Tests for check_regression() — core regression detection logic.

    Per Scout 7 S12.S1: a regression is when a previously PASS stage
    now FAILS or TIMEOUTs in the new verification run.
    """

    def test_no_regression_when_same_stages_pass(self):
        """No regression when same stages pass in new run.

        Per Scout 7 S12.S1: if all previously-passing stages still pass,
        the safety gate should not block.
        """
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        new_result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )

        gate = check_regression(new_result, previous)
        assert gate.passed is True, (
            "Same stages passing → no regression → gate should pass"
        )

    def test_regression_detected_when_passing_stage_now_fails(self):
        """Regression detected when previously PASS stage now FAILs.

        Per Scout 7 S12.S1: this is the core safety gate invariant.
        If formal proof previously passed but now fails, block the build.
        """
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(4, "formal"),
            ],
        )
        new_result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _fail_stage(4, "formal"),  # regression!
            ],
        )

        gate = check_regression(new_result, previous)
        assert gate.passed is False, (
            "Previously PASS stage now FAIL → regression → gate should block"
        )
        assert len(gate.regressions) >= 1, "Should report at least one regression"
        regressed_names = [r["stage_name"] for r in gate.regressions]
        assert "formal" in regressed_names, "formal stage regression should be reported"

    def test_no_regression_for_new_failing_stage(self):
        """No regression when a stage that wasn't in previous result now fails.

        A stage that didn't exist before can't regress — it's a new failure,
        not a regression from a known-good state.
        """
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                # pbt and formal not in previous (e.g., skipped)
            ],
        )
        new_result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _fail_stage(3, "pbt"),  # new failure, not in previous
            ],
        )

        gate = check_regression(new_result, previous)
        # pbt wasn't passing before → not a regression
        assert gate.passed is True, (
            "Stage that wasn't passing before → not a regression"
        )

    def test_regression_in_pbt_stage_blocks(self):
        """PBT stage regression is also blocked.

        Safety gate covers all stages, not just formal verification.
        """
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
            ],
        )
        new_result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _fail_stage(3, "pbt"),  # regression
            ],
        )

        gate = check_regression(new_result, previous)
        assert gate.passed is False

    def test_skip_in_previous_is_not_a_pass(self):
        """A previously SKIPPED stage becoming FAIL is not a regression.

        SKIP means not applicable. Only PASS → FAIL is a regression.
        """
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _skip_stage(4, "formal"),  # was skipped
            ],
        )
        new_result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _fail_stage(4, "formal"),  # now failing (but wasn't passing before)
            ],
        )

        gate = check_regression(new_result, previous)
        assert gate.passed is True, (
            "SKIP → FAIL is not a regression (stage wasn't proven before)"
        )

    def test_regression_result_has_details(self):
        """Regression result includes stage name and status details."""
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(
            verified=True,
            stages=[_pass_stage(4, "formal")],
        )
        new_result = VerifyResult(
            verified=False,
            stages=[_fail_stage(4, "formal")],
        )

        gate = check_regression(new_result, previous)
        assert gate.passed is False
        assert gate.regressions, "regressions list should be non-empty"
        regression = gate.regressions[0]
        assert "stage_name" in regression
        assert "previous_status" in regression
        assert "new_status" in regression


class TestSafetyGateWithFile:
    """Tests for run_safety_gate() with verify.json file I/O.

    Per Scout 7 S12.S1: the gate loads previous state from verify.json.
    """

    def test_first_run_passes_when_no_previous_json(self):
        """First run (no verify.json) should not block.

        Per Scout 7 S12.S1: no previous state → no regression possible.
        """
        from nightjar.safety_gate import run_safety_gate

        new_result = VerifyResult(
            verified=True,
            stages=[_pass_stage(4, "formal")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            verify_path = os.path.join(tmpdir, "verify.json")
            # File does not exist
            gate = run_safety_gate(new_result, verify_json_path=verify_path)

        assert gate.passed is True, (
            "First run (no verify.json) should pass — no regression possible"
        )

    def test_saves_result_after_gate_pass(self):
        """run_safety_gate saves new result to verify.json when no regression."""
        from nightjar.safety_gate import run_safety_gate

        new_result = VerifyResult(
            verified=True,
            stages=[_pass_stage(4, "formal")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            verify_path = os.path.join(tmpdir, "verify.json")
            gate = run_safety_gate(new_result, verify_json_path=verify_path)

            # File should exist now
            assert os.path.exists(verify_path), (
                "verify.json should be written after safety gate passes"
            )

    def test_regression_blocked_using_file(self):
        """Regression is blocked when previous verify.json shows PASS that now FAILs."""
        from nightjar.safety_gate import run_safety_gate, save_verify_result

        # Build a previous verify.json with formal=PASS
        previous = VerifyResult(
            verified=True,
            stages=[_pass_stage(4, "formal")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            verify_path = os.path.join(tmpdir, "verify.json")
            # Save previous result
            save_verify_result(previous, verify_path)

            # New result has formal failing (regression)
            new_result = VerifyResult(
                verified=False,
                stages=[_fail_stage(4, "formal")],
            )
            gate = run_safety_gate(new_result, verify_json_path=verify_path)

        assert gate.passed is False, (
            "Regression from previous PASS → new FAIL should be blocked"
        )
