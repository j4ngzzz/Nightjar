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


class TestConfidenceDropWarning:
    """Tests for W1.6 confidence score drop warning (non-blocking).

    Per Scout 7 S12.S1: warn when new confidence < previous, but don't block.
    """

    def test_confidence_drop_warning_when_score_decreases(self):
        """Warning emitted when new confidence score < previous.

        This is a non-blocking warning — gate.passed should still be True
        if no stage regressions occurred.
        """
        from nightjar.safety_gate import check_regression
        from nightjar.confidence import ConfidenceScore

        # Previous had high confidence (all stages pass)
        previous = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        previous.confidence = ConfidenceScore(total=55, breakdown={"preflight": 15, "pbt": 20, "formal": 20})

        # New result has lower confidence (formal now skipped)
        new_result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
                _skip_stage(4, "formal"),
            ],
        )
        new_result.confidence = ConfidenceScore(total=35, breakdown={"preflight": 15, "pbt": 20})

        gate = check_regression(new_result, previous)

        # No stage regressions (formal SKIPPED, not FAILED)
        assert gate.passed is True, "SKIP is not a regression"
        assert gate.confidence_drop == 20, (
            "Should report 20-point confidence drop (55 → 35)"
        )
        assert gate.confidence_warning, "Should have non-empty confidence warning"
        assert "55" in gate.confidence_warning
        assert "35" in gate.confidence_warning

    def test_no_confidence_warning_when_score_same_or_higher(self):
        """No confidence warning when score is maintained or improved."""
        from nightjar.safety_gate import check_regression
        from nightjar.confidence import ConfidenceScore

        previous = VerifyResult(verified=True, stages=[_pass_stage(4, "formal")])
        previous.confidence = ConfidenceScore(total=20)

        new_result = VerifyResult(verified=True, stages=[_pass_stage(4, "formal")])
        new_result.confidence = ConfidenceScore(total=20)

        gate = check_regression(new_result, previous)
        assert gate.confidence_drop == 0
        assert gate.confidence_warning == ""

    def test_no_confidence_warning_when_previous_has_no_score(self):
        """No warning when previous result has no confidence score (first-time)."""
        from nightjar.safety_gate import check_regression

        previous = VerifyResult(verified=True, stages=[_pass_stage(4, "formal")])
        # previous.confidence is None (not computed)

        new_result = VerifyResult(verified=False, stages=[_skip_stage(4, "formal")])

        gate = check_regression(new_result, previous)
        assert gate.confidence_drop == 0
        assert gate.confidence_warning == ""

    def test_safety_gate_result_has_confidence_fields(self):
        """SafetyGateResult dataclass has confidence_drop and confidence_warning fields."""
        from nightjar.safety_gate import SafetyGateResult

        gate = SafetyGateResult(passed=True, confidence_drop=5, confidence_warning="dropped")
        assert gate.confidence_drop == 5
        assert gate.confidence_warning == "dropped"


class TestPBTExtended:
    """Tests for run_pbt_extended — verifies 10K example mode is wired."""

    def test_run_pbt_extended_importable(self):
        """run_pbt_extended is importable from stages.pbt."""
        from nightjar.stages.pbt import run_pbt_extended
        assert callable(run_pbt_extended)

    def test_extended_settings_has_10k_examples(self):
        """NIGHTJAR_PBT_EXTENDED_SETTINGS uses 10K examples."""
        from nightjar.stages.pbt import NIGHTJAR_PBT_EXTENDED_SETTINGS
        assert NIGHTJAR_PBT_EXTENDED_SETTINGS.max_examples == 10000

    def test_run_pbt_extended_returns_stage_result(self):
        """run_pbt_extended returns a StageResult."""
        from nightjar.stages.pbt import run_pbt_extended
        from nightjar.types import (
            CardSpec, Contract, ModuleBoundary,
            Invariant, InvariantTier, StageResult,
        )

        spec = CardSpec(
            card_version="1.0", id="test", title="Test", status="draft",
            module=ModuleBoundary(owns=["f()"]),
            contract=Contract(),
            invariants=[
                Invariant(id="INV-1", tier=InvariantTier.PROPERTY,
                          statement="returns a positive integer"),
            ],
        )
        code = "def f(x): return x + 1"
        result = run_pbt_extended(spec, code)
        assert isinstance(result, StageResult)

    def test_hypothesis_extended_uses_run_pbt_extended(self):
        """_run_hypothesis_extended calls run_pbt_extended (not run_pbt)."""
        from unittest.mock import patch
        from nightjar.verifier import _run_hypothesis_extended
        from nightjar.types import (
            CardSpec, Contract, ModuleBoundary, StageResult, VerifyStatus,
        )

        spec = CardSpec(
            card_version="1.0", id="test", title="Test", status="draft",
            module=ModuleBoundary(owns=["f()"]),
            contract=Contract(),
            invariants=[],
        )

        with patch("nightjar.stages.pbt.run_pbt_extended") as mock_ext:
            mock_ext.return_value = StageResult(
                stage=3, name="pbt", status=VerifyStatus.PASS,
            )
            result = _run_hypothesis_extended(spec, "def f(): pass")

        mock_ext.assert_called_once()
        assert result.name == "hypothesis_extended"
