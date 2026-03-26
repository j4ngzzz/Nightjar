"""Tests for nightjar LLM-enhanced violation explainer.

TDD: Tests written FIRST before implementation.

Reference: Scout 7 N2 — Transform Dafny SMT errors → human-readable explanations
Via litellm LLM call. All LLM calls use NIGHTJAR_MODEL env var.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from nightjar.explain import ExplainOutput


class TestLLMExplainer:
    """Tests for explain_with_llm() — LLM-enhanced explanations."""

    def test_explainer_produces_human_readable_output(self):
        """LLM explainer returns human-readable text, not raw SMT output.

        Scout 7 N2: 'Current Dafny errors are cryptic SMT output.
        Assertion at line 42 may not hold helps no one.'
        """
        from nightjar.explain import explain_with_llm

        raw_error = (
            "Dafny: postcondition might not hold\n"
            "Related location: (42,4): This is the postcondition that might not hold.\n"
            "Assertion violation\n"
            "  Call: method Withdraw(balance: int, amount: int) returns (newBalance: int)\n"
            "  ensures newBalance >= 0\n"
        )
        explanation = ExplainOutput(
            failed_stage=4,
            stage_name="formal",
            invariant_violated="newBalance >= 0",
            error_messages=[raw_error],
            counterexamples=[{"balance": 10, "amount": 50}],
            suggested_fix="",
            all_stages_summary=[],
        )

        with patch("nightjar.explain.litellm") as mock_litellm:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = (
                "The Withdraw function can produce a negative balance. "
                "When balance=10 and amount=50, newBalance=-40 which violates the invariant "
                "'newBalance >= 0'. Fix: add a precondition 'requires amount <= balance'."
            )
            mock_litellm.completion.return_value = mock_response

            result = explain_with_llm(explanation)

        assert isinstance(result, str)
        assert len(result) > 20
        # Should NOT contain raw SMT output markers
        assert "might not hold" not in result or "balance" in result

    def test_explainer_includes_counterexample(self):
        """LLM explainer includes the counterexample in its explanation."""
        from nightjar.explain import explain_with_llm

        explanation = ExplainOutput(
            failed_stage=3,
            stage_name="pbt",
            invariant_violated="output >= 0",
            error_messages=["Property violated: output >= 0"],
            counterexamples=[{"input": -5, "output": -5}],
            suggested_fix="",
            all_stages_summary=[],
        )

        with patch("nightjar.explain.litellm") as mock_litellm:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = (
                "When input is -5, the output is -5 which violates 'output >= 0'. "
                "Add input validation: if input < 0, raise ValueError."
            )
            mock_litellm.completion.return_value = mock_response

            result = explain_with_llm(explanation)

        assert isinstance(result, str)
        # LLM was called with the counterexample info
        call_kwargs = mock_litellm.completion.call_args
        prompt_text = str(call_kwargs)
        assert "-5" in prompt_text or "counterexample" in prompt_text.lower()

    def test_explainer_uses_litellm_not_direct_api(self):
        """LLM explainer uses litellm.completion, not direct provider API.

        Anti-pattern: DO NOT call provider APIs directly.
        All LLM calls MUST go through litellm [REF-T16].
        """
        from nightjar.explain import explain_with_llm

        explanation = ExplainOutput(
            failed_stage=4,
            stage_name="formal",
            invariant_violated="x > 0",
            error_messages=["Assertion violation"],
            counterexamples=[],
            suggested_fix="",
            all_stages_summary=[],
        )

        with patch("nightjar.explain.litellm") as mock_litellm:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Fix the invariant."
            mock_litellm.completion.return_value = mock_response

            explain_with_llm(explanation)

        # Must use litellm.completion
        assert mock_litellm.completion.called

    def test_explainer_uses_nightjar_model_env_var(self):
        """LLM explainer uses NIGHTJAR_MODEL env var for model selection.

        Anti-pattern: DO NOT hardcode model names.
        """
        import os
        from nightjar.explain import explain_with_llm

        explanation = ExplainOutput(
            failed_stage=4,
            stage_name="formal",
            invariant_violated="x > 0",
            error_messages=["Assertion violation"],
            counterexamples=[],
            suggested_fix="",
            all_stages_summary=[],
        )

        with patch.dict(os.environ, {"NIGHTJAR_MODEL": "claude-sonnet-4-6"}):
            with patch("nightjar.explain.litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices[0].message.content = "Fix the invariant."
                mock_litellm.completion.return_value = mock_response

                explain_with_llm(explanation)

        call_kwargs = mock_litellm.completion.call_args
        assert "claude-sonnet-4-6" in str(call_kwargs)

    def test_explainer_graceful_fallback_on_llm_error(self):
        """LLM explainer returns heuristic explanation if LLM call fails."""
        from nightjar.explain import explain_with_llm

        explanation = ExplainOutput(
            failed_stage=3,
            stage_name="pbt",
            invariant_violated="output >= 0",
            error_messages=["Property violated: output >= 0"],
            counterexamples=[{"input": -5}],
            suggested_fix="Add input validation",
            all_stages_summary=[],
        )

        with patch("nightjar.explain.litellm") as mock_litellm:
            mock_litellm.completion.side_effect = Exception("API error")

            # Must NOT raise — fall back to heuristic suggestion
            result = explain_with_llm(explanation)

        assert isinstance(result, str)
        assert len(result) > 0  # Returns fallback

    def test_load_report_handles_json_error(self, tmp_path):
        """load_report handles invalid JSON without raising (Reviewer 9 fix).

        Reviewer 9 flagged: 'existing explain.py lacks try/except around json.load()'
        This must be fixed — invalid JSON should return None, not raise.
        """
        from nightjar.explain import load_report

        bad_json = tmp_path / ".card" / "verify.json"
        bad_json.parent.mkdir()
        bad_json.write_text("not valid json {{{{", encoding="utf-8")

        contract_path = str(bad_json.parent / "test.card.md")
        result = load_report(contract_path)
        # Must return None, NOT raise json.JSONDecodeError
        assert result is None

    def test_load_report_handles_permission_error(self, tmp_path):
        """load_report returns None on permission/IO errors."""
        from nightjar.explain import load_report

        # Pass a path to a file that doesn't exist in a dir that doesn't exist
        result = load_report("/nonexistent/path/test.card.md")
        assert result is None
