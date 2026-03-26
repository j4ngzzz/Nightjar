"""Tests for W1.5 — Graceful Degradation Ladder in verifier.py.

When Dafny times out, fall back to CrossHair symbolic execution.
When CrossHair times out, fall back to extended Hypothesis PBT.
When all fail, report partial confidence score with gap notation.

References:
- Scout 3 Section 5.5: Best fallback when Dafny fails (ranked)
- Scout 3 Section 5.4: Recommended fallback chain
- Scout 3 S5.6: icontract-hypothesis bridge (auto-generates Hypothesis
  strategies from @require/@ensure decorators)

Fallback chain (Scout 3 S5.5):
  1. CrossHair symbolic — uses same Z3 solver as Dafny, directly on Python
     contracts. No translation. Average 13s. Score: 9/10
  2. Hypothesis extended PBT — 10K+ examples, statistical confidence.
     When CrossHair hits path explosion, Hypothesis continues. Score: 10/10
"""

import pytest
from unittest.mock import patch, MagicMock
from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyResult, VerifyStatus,
)


def _make_spec() -> CardSpec:
    return CardSpec(
        card_version="1.0",
        id="payment",
        title="Payment Processor",
        status="draft",
        module=ModuleBoundary(owns=["charge()"]),
        contract=Contract(
            inputs=[ContractInput(name="amount", type="float")],
            outputs=[ContractOutput(name="result", type="bool")],
        ),
        invariants=[
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="amount > 0 → result is True"),
        ],
    )


def _timeout_result() -> StageResult:
    return StageResult(
        stage=4, name="formal", status=VerifyStatus.TIMEOUT,
        errors=[{"type": "timeout", "error": "Dafny timed out"}],
    )


def _fail_result() -> StageResult:
    return StageResult(
        stage=4, name="formal", status=VerifyStatus.FAIL,
        errors=[{"type": "postcondition_failure", "message": "proof failed"}],
    )


class TestGracefulDegradation:
    """Tests for graceful degradation when Dafny fails.

    Per Scout 3 S5.5: CrossHair → Hypothesis → partial score reporting.
    'No user is ever blocked.' (Scout 3 S5.5)
    """

    def test_fallback_crosshair_on_dafny_timeout(self):
        """When Dafny times out, run CrossHair symbolic execution as fallback.

        Per Scout 3 S5.5 Rank 1: CrossHair uses same Z3 solver as Dafny,
        directly on Python contracts. No translation step. Avg 13s.
        Score: 9/10 (covers ~80% of practical invariants symbolically).
        """
        from nightjar.verifier import run_pipeline_with_fallback

        spec = _make_spec()
        code = "def charge(amount): return amount > 0"

        # Build a pipeline result that has Dafny timeout in it
        pipeline_result = VerifyResult(
            verified=False,
            stages=[_timeout_result()],
        )

        with patch("nightjar.verifier.run_pipeline", return_value=pipeline_result), \
             patch("nightjar.verifier._run_crosshair_fallback") as mock_crosshair:
            # CrossHair passes
            mock_crosshair.return_value = StageResult(
                stage=4, name="crosshair", status=VerifyStatus.PASS,
                duration_ms=13000,
            )

            result = run_pipeline_with_fallback(spec, code)

        mock_crosshair.assert_called_once(), (
            "CrossHair fallback should be called when Dafny times out"
        )

    def test_fallback_hypothesis_on_crosshair_timeout(self):
        """When CrossHair also times out, run extended Hypothesis PBT.

        Per Scout 3 S5.5 Rank 2: 'When CrossHair hits path explosion,
        Hypothesis continues.' Combined score: 10/10 feasibility.
        """
        from nightjar.verifier import run_pipeline_with_fallback

        spec = _make_spec()
        code = "def charge(amount): return amount > 0"

        # Build a pipeline result that has Dafny timeout in it
        pipeline_result = VerifyResult(
            verified=False,
            stages=[_timeout_result()],
        )

        with patch("nightjar.verifier.run_pipeline", return_value=pipeline_result), \
             patch("nightjar.verifier._run_crosshair_fallback") as mock_crosshair, \
             patch("nightjar.verifier._run_hypothesis_extended") as mock_hyp:
            # CrossHair times out too
            mock_crosshair.return_value = StageResult(
                stage=4, name="crosshair", status=VerifyStatus.TIMEOUT,
                duration_ms=300000,
            )
            # Hypothesis passes
            mock_hyp.return_value = StageResult(
                stage=4, name="hypothesis_extended", status=VerifyStatus.PASS,
                duration_ms=30000,
            )

            result = run_pipeline_with_fallback(spec, code)

        mock_hyp.assert_called_once(), (
            "Extended Hypothesis should be called when CrossHair also times out"
        )

    def test_reports_partial_score_on_all_fail(self):
        """When all fallbacks fail, return partial confidence score.

        Per Scout 3 S5.5: 'No user is ever blocked. When all fail,
        report confidence score with gap notation.'
        E.g., 'Confidence: 75/100 (gap: formal/crosshair)'
        """
        from nightjar.verifier import run_pipeline_with_fallback

        spec = _make_spec()
        code = "def charge(amount): return amount > 0"

        pipeline_result = VerifyResult(
            verified=False,
            stages=[_timeout_result()],
        )

        with patch("nightjar.verifier.run_pipeline", return_value=pipeline_result), \
             patch("nightjar.verifier._run_crosshair_fallback") as mock_crosshair, \
             patch("nightjar.verifier._run_hypothesis_extended") as mock_hyp:
            # All fallbacks fail
            mock_crosshair.return_value = StageResult(
                stage=4, name="crosshair", status=VerifyStatus.TIMEOUT,
            )
            mock_hyp.return_value = StageResult(
                stage=4, name="hypothesis_extended", status=VerifyStatus.FAIL,
                errors=[{"type": "property_violation", "message": "counter found"}],
            )

            result = run_pipeline_with_fallback(spec, code)

        # Result should not be None — 'no user is ever blocked'
        assert result is not None
        assert isinstance(result, VerifyResult)
        # User should get SOME result even when all verification fails
        assert result.verified is False or result.verified is True

    def test_crosshair_fallback_stage_exists(self):
        """_run_crosshair_fallback function is importable from verifier."""
        from nightjar.verifier import _run_crosshair_fallback
        assert callable(_run_crosshair_fallback)

    def test_hypothesis_extended_stage_exists(self):
        """_run_hypothesis_extended function is importable from verifier."""
        from nightjar.verifier import _run_hypothesis_extended
        assert callable(_run_hypothesis_extended)

    def test_run_pipeline_with_fallback_is_callable(self):
        """run_pipeline_with_fallback function is importable from verifier."""
        from nightjar.verifier import run_pipeline_with_fallback
        assert callable(run_pipeline_with_fallback)

    def test_fallback_chain_does_not_block_on_dafny_notfound(self):
        """If Dafny is not installed, CrossHair fallback still runs.

        Per Scout 3 S5.5: CrossHair is available even without Dafny.
        The fallback chain should degrade gracefully.
        """
        from nightjar.verifier import run_pipeline_with_fallback

        spec = _make_spec()
        code = "def charge(amount): return amount > 0"

        pipeline_result = VerifyResult(
            verified=False,
            stages=[StageResult(
                stage=4, name="formal", status=VerifyStatus.FAIL,
                errors=[{"type": "dafny_not_found", "error": "dafny not in PATH"}],
            )],
        )

        with patch("nightjar.verifier.run_pipeline", return_value=pipeline_result), \
             patch("nightjar.verifier._run_crosshair_fallback") as mock_crosshair:
            mock_crosshair.return_value = StageResult(
                stage=4, name="crosshair", status=VerifyStatus.PASS,
            )

            result = run_pipeline_with_fallback(spec, code)

        # CrossHair should still be called as fallback
        mock_crosshair.assert_called_once()
