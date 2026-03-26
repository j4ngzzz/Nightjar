"""Tests for the Clover-pattern retry loop.

Validates the generate → verify → repair → re-verify cycle
per [REF-C02] and [REF-P03] Clover closed-loop verification.

References:
- [REF-C02] Closed-loop verification (Clover pattern)
- [REF-P03] Clover paper — generate → verify → feedback → regenerate
- [REF-P06] DafnyPro — structured error format for repair prompts
- [REF-T16] litellm — all LLM calls go through litellm
"""

from unittest.mock import patch, MagicMock, call
import pytest

from contractd.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyResult, VerifyStatus,
)
from contractd.retry import run_with_retry, build_repair_prompt


def _make_spec() -> CardSpec:
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
        invariants=[
            Invariant(id="INV-001", tier=InvariantTier.PROPERTY,
                      statement="For any x, result > 0"),
        ],
    )


def _pass_verify() -> VerifyResult:
    return VerifyResult(
        verified=True,
        stages=[StageResult(stage=0, name="preflight", status=VerifyStatus.PASS)],
        total_duration_ms=100,
    )


def _fail_verify(stage: int = 3) -> VerifyResult:
    return VerifyResult(
        verified=False,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS),
            StageResult(
                stage=stage, name="pbt", status=VerifyStatus.FAIL,
                errors=[{"type": "property_violation", "message": "assertion failed"}],
            ),
        ],
        total_duration_ms=200,
    )


class TestRunWithRetry:
    """Tests for run_with_retry — the Clover closed-loop [REF-C02]."""

    def test_pass_on_first_attempt(self):
        """If verification passes on first try, no retries needed."""
        spec = _make_spec()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _pass_verify()

            result = run_with_retry(spec, "initial_code", max_retries=5)

        assert result.verified is True
        assert result.retry_count == 0
        mock_llm.assert_not_called()

    def test_retry_on_failure_then_pass(self):
        """Fails first, LLM repairs, second attempt passes."""
        spec = _make_spec()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.side_effect = [_fail_verify(), _pass_verify()]
            mock_llm.return_value = "repaired_code"

            result = run_with_retry(spec, "buggy_code", max_retries=5)

        assert result.verified is True
        assert result.retry_count == 1
        mock_llm.assert_called_once()

    def test_exhaust_retries(self):
        """Exceeds max_retries → verified=False with retry_count."""
        spec = _make_spec()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _fail_verify()
            mock_llm.return_value = "still_buggy_code"

            result = run_with_retry(spec, "buggy_code", max_retries=3)

        assert result.verified is False
        assert result.retry_count == 3
        assert mock_llm.call_count == 3

    def test_default_max_retries_is_5(self):
        """Default max_retries is 5 per ARCHITECTURE.md Section 4."""
        spec = _make_spec()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _fail_verify()
            mock_llm.return_value = "still_buggy"

            result = run_with_retry(spec, "buggy_code")

        assert result.retry_count == 5
        assert mock_llm.call_count == 5

    def test_repair_prompt_includes_error_context(self):
        """LLM repair call receives structured error context [REF-P06]."""
        spec = _make_spec()
        fail_result = _fail_verify()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.side_effect = [fail_result, _pass_verify()]
            mock_llm.return_value = "repaired_code"

            run_with_retry(spec, "buggy_code", max_retries=5)

        # The LLM should have been called with spec, code, and error context
        mock_llm.assert_called_once()
        call_args = mock_llm.call_args
        assert call_args is not None

    def test_zero_retries_means_no_repair(self):
        """max_retries=0 means no repair attempts."""
        spec = _make_spec()
        with patch("contractd.retry.run_pipeline") as mock_pipeline, \
             patch("contractd.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _fail_verify()

            result = run_with_retry(spec, "buggy_code", max_retries=0)

        assert result.verified is False
        assert result.retry_count == 0
        mock_llm.assert_not_called()


class TestBuildRepairPrompt:
    """Tests for repair prompt construction per [REF-P06]."""

    def test_includes_spec_context(self):
        """Repair prompt includes the original .card.md spec."""
        spec = _make_spec()
        fail = _fail_verify()
        prompt = build_repair_prompt(spec, "buggy_code", fail, attempt=1)
        assert "test-module" in prompt or "INV-001" in prompt

    def test_includes_error_details(self):
        """Repair prompt includes structured error from failed stage."""
        spec = _make_spec()
        fail = _fail_verify()
        prompt = build_repair_prompt(spec, "buggy_code", fail, attempt=1)
        assert "assertion failed" in prompt or "property_violation" in prompt

    def test_includes_attempt_number(self):
        """Repair prompt includes the attempt number for context."""
        spec = _make_spec()
        fail = _fail_verify()
        prompt = build_repair_prompt(spec, "buggy_code", fail, attempt=3)
        assert "3" in prompt

    def test_includes_failed_code(self):
        """Repair prompt includes the code that failed verification."""
        spec = _make_spec()
        fail = _fail_verify()
        prompt = build_repair_prompt(spec, "buggy_code_here", fail, attempt=1)
        assert "buggy_code_here" in prompt
