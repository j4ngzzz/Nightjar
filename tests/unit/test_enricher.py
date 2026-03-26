"""Tests for LLM-driven invariant enrichment.

References:
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-P15] Agentic PBT — LLM proposes properties
- [REF-P14] NL2Contract — LLM generates formal contracts
- [REF-T16] litellm — model-agnostic LLM interface
"""

import pytest
from unittest.mock import patch, MagicMock

from immune.enricher import (
    enrich_invariants,
    CandidateInvariant,
    EnrichmentResult,
    build_enrichment_prompt,
)


class TestCandidateInvariant:
    """Test the CandidateInvariant dataclass."""

    def test_basic_creation(self):
        inv = CandidateInvariant(
            expression="result >= 0",
            explanation="Return value is always non-negative",
            confidence=0.9,
        )
        assert inv.expression == "result >= 0"
        assert inv.explanation == "Return value is always non-negative"
        assert inv.confidence == 0.9

    def test_default_confidence(self):
        inv = CandidateInvariant(
            expression="result > 0",
            explanation="Positive return",
        )
        assert inv.confidence == 0.5


class TestBuildEnrichmentPrompt:
    """Test prompt construction for the LLM."""

    def test_basic_prompt_includes_function_sig(self):
        prompt = build_enrichment_prompt(
            function_signature="def abs_value(x: int) -> int",
            observed_invariants=["result >= 0"],
        )
        assert "abs_value" in prompt
        assert "result >= 0" in prompt

    def test_prompt_includes_error_trace(self):
        prompt = build_enrichment_prompt(
            function_signature="def divide(a: int, b: int) -> float",
            observed_invariants=[],
            error_trace="ZeroDivisionError: division by zero",
        )
        assert "ZeroDivisionError" in prompt

    def test_prompt_includes_all_observed_invariants(self):
        invariants = ["x > 0", "result >= 0", "result <= x"]
        prompt = build_enrichment_prompt(
            function_signature="def sqrt(x: float) -> float",
            observed_invariants=invariants,
        )
        for inv in invariants:
            assert inv in prompt

    def test_prompt_requests_assert_format(self):
        prompt = build_enrichment_prompt(
            function_signature="def f(x: int) -> int",
            observed_invariants=[],
        )
        assert "assert" in prompt.lower()


class TestEnrichInvariants:
    """Test the main enrichment function (with mocked LLM)."""

    @patch("immune.enricher._call_llm")
    def test_returns_candidate_invariants(self, mock_llm):
        mock_llm.return_value = (
            'assert result >= 0, "Return value is always non-negative"\n'
            'assert result <= x, "Return never exceeds input"'
        )
        result = enrich_invariants(
            function_signature="def abs_value(x: int) -> int",
            observed_invariants=["result >= 0"],
        )
        assert isinstance(result, EnrichmentResult)
        assert len(result.candidates) >= 1
        assert any("result >= 0" in c.expression for c in result.candidates)

    @patch("immune.enricher._call_llm")
    def test_handles_empty_llm_response(self, mock_llm):
        mock_llm.return_value = ""
        result = enrich_invariants(
            function_signature="def f(x: int) -> int",
            observed_invariants=[],
        )
        assert isinstance(result, EnrichmentResult)
        assert len(result.candidates) == 0

    @patch("immune.enricher._call_llm")
    def test_handles_malformed_llm_response(self, mock_llm):
        mock_llm.return_value = "This is not valid Python assertions at all."
        result = enrich_invariants(
            function_signature="def f(x: int) -> int",
            observed_invariants=[],
        )
        assert isinstance(result, EnrichmentResult)
        # Should gracefully handle — may return 0 candidates or partial parse

    @patch("immune.enricher._call_llm")
    def test_passes_error_trace_to_prompt(self, mock_llm):
        mock_llm.return_value = 'assert b != 0, "Divisor must not be zero"'
        result = enrich_invariants(
            function_signature="def divide(a: int, b: int) -> float",
            observed_invariants=[],
            error_trace="ZeroDivisionError: division by zero",
        )
        # Verify the LLM was called with a prompt containing the error trace
        call_args = mock_llm.call_args
        assert "ZeroDivisionError" in call_args[0][0]

    @patch("immune.enricher._call_llm")
    def test_llm_exception_returns_error(self, mock_llm):
        mock_llm.side_effect = Exception("API rate limit exceeded")
        result = enrich_invariants(
            function_signature="def f(x: int) -> int",
            observed_invariants=[],
        )
        assert isinstance(result, EnrichmentResult)
        assert result.error is not None
        assert "rate limit" in result.error.lower() or "API" in result.error

    @patch("immune.enricher._call_llm")
    def test_parses_multiple_assert_statements(self, mock_llm):
        mock_llm.return_value = (
            'assert result >= 0, "non-negative"\n'
            'assert isinstance(result, int), "returns int"\n'
            'assert result <= abs(x), "bounded by input"'
        )
        result = enrich_invariants(
            function_signature="def abs_value(x: int) -> int",
            observed_invariants=[],
        )
        assert len(result.candidates) == 3

    @patch("immune.enricher._call_llm")
    def test_confidence_assigned_to_candidates(self, mock_llm):
        mock_llm.return_value = 'assert result > 0, "positive result"'
        result = enrich_invariants(
            function_signature="def f(x: int) -> int",
            observed_invariants=["result > 0"],
        )
        # Candidates corroborated by observed invariants should have higher confidence
        for c in result.candidates:
            assert 0.0 <= c.confidence <= 1.0
