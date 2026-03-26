"""Tests for the verification pipeline orchestrator.

Validates that the verifier runs stages 0→1→(2∥3)→4 with short-circuit
on failure, per ARCHITECTURE.md Section 3.

References:
- [REF-C02] Closed-loop verification (Clover pattern)
- [REF-P06] DafnyPro — structured errors for repair
- ARCHITECTURE.md Section 3 — stage parallelization design
"""

from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyResult, VerifyStatus,
)
from nightjar.verifier import run_pipeline


def _make_spec(invariants: list[Invariant] | None = None) -> CardSpec:
    """Helper to build a CardSpec for testing."""
    if invariants is None:
        invariants = [
            Invariant(id="INV-001", tier=InvariantTier.PROPERTY,
                      statement="For any x, result > 0"),
        ]
    return CardSpec(
        card_version="1.0",
        id="test-module",
        title="Test Module",
        status="draft",
        module=ModuleBoundary(owns=["func_a()"]),
        contract=Contract(
            inputs=[ContractInput(name="x", type="integer")],
            outputs=[ContractOutput(name="Result", type="integer")],
        ),
        invariants=invariants,
    )


def _pass_result(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.PASS, duration_ms=10)


def _fail_result(stage: int, name: str) -> StageResult:
    return StageResult(
        stage=stage, name=name, status=VerifyStatus.FAIL, duration_ms=10,
        errors=[{"type": "test_error", "message": f"Stage {stage} failed"}],
    )


def _skip_result(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.SKIP, duration_ms=0)


class TestRunPipeline:
    """Tests for run_pipeline function."""

    def test_returns_verify_result(self):
        """run_pipeline returns a VerifyResult."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _pass_result(2, "schema")
            s3.return_value = _pass_result(3, "pbt")
            s4.return_value = _skip_result(4, "formal")

            result = run_pipeline(spec, "code_string")

        assert isinstance(result, VerifyResult)

    def test_all_stages_pass(self):
        """All stages passing → verified=True."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _pass_result(2, "schema")
            s3.return_value = _pass_result(3, "pbt")
            s4.return_value = _pass_result(4, "formal")

            result = run_pipeline(spec, "code_string")

        assert result.verified is True
        assert len(result.stages) == 5

    def test_short_circuit_on_stage_0_fail(self):
        """Stage 0 fail → pipeline stops, later stages not run."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _fail_result(0, "preflight")

            result = run_pipeline(spec, "code_string")

        assert result.verified is False
        # Stage 0 ran, but later stages should NOT have been called
        s1.assert_not_called()
        s2.assert_not_called()
        s3.assert_not_called()
        s4.assert_not_called()

    def test_short_circuit_on_stage_1_fail(self):
        """Stage 1 fail → stages 2-4 not run."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _fail_result(1, "deps")

            result = run_pipeline(spec, "code_string")

        assert result.verified is False
        s2.assert_not_called()
        s3.assert_not_called()
        s4.assert_not_called()

    def test_stage_2_and_3_both_run_after_stage_1_pass(self):
        """After stages 0-1 pass, both stages 2 and 3 execute."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _pass_result(2, "schema")
            s3.return_value = _pass_result(3, "pbt")
            s4.return_value = _skip_result(4, "formal")

            result = run_pipeline(spec, "code_string")

        s2.assert_called_once()
        s3.assert_called_once()

    def test_stage_2_fail_still_runs_stage_3(self):
        """Stages 2 and 3 are parallel — both run even if one fails."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _fail_result(2, "schema")
            s3.return_value = _pass_result(3, "pbt")

            result = run_pipeline(spec, "code_string")

        assert result.verified is False
        s3.assert_called_once()
        s4.assert_not_called()  # Stage 4 skipped because 2 failed

    def test_stage_4_not_run_if_2_or_3_fail(self):
        """Stage 4 only runs if both 2 and 3 pass."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _pass_result(2, "schema")
            s3.return_value = _fail_result(3, "pbt")

            result = run_pipeline(spec, "code_string")

        assert result.verified is False
        s4.assert_not_called()

    def test_skip_counts_as_pass(self):
        """SKIP status does not block the pipeline."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _pass_result(1, "deps")
            s2.return_value = _skip_result(2, "schema")
            s3.return_value = _skip_result(3, "pbt")
            s4.return_value = _skip_result(4, "formal")

            result = run_pipeline(spec, "code_string")

        assert result.verified is True

    def test_total_duration_is_sum_of_stages(self):
        """VerifyResult.total_duration_ms accumulates stage durations."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=100)
            s1.return_value = StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=200)
            s2.return_value = StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=50)
            s3.return_value = StageResult(stage=3, name="pbt", status=VerifyStatus.PASS, duration_ms=300)
            s4.return_value = StageResult(stage=4, name="formal", status=VerifyStatus.PASS, duration_ms=500)

            result = run_pipeline(spec, "code_string")

        assert result.total_duration_ms >= 1150  # At least sum of stages

    def test_collects_all_stage_results(self):
        """VerifyResult.stages contains results from all executed stages."""
        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            s0.return_value = _pass_result(0, "preflight")
            s1.return_value = _fail_result(1, "deps")

            result = run_pipeline(spec, "code_string")

        # Should have results for stage 0 and 1 (short-circuited after 1)
        assert len(result.stages) == 2
        assert result.stages[0].stage == 0
        assert result.stages[1].stage == 1
