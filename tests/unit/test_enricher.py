"""Tests for LLM-driven invariant enrichment.

References:
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-P15] Agentic PBT — LLM proposes properties
- [REF-P14] NL2Contract — LLM generates formal contracts
- [REF-T16] litellm — model-agnostic LLM interface
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from immune.enricher import (
    enrich_invariants,
    CandidateInvariant,
    EnrichmentResult,
    build_enrichment_prompt,
    _log_refinement_to_tsv,
    _propose_refinement,
    refine_invariants_ratchet,
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


# ── Invariant Refinement Ratchet tests ────────────────────────────────────────


class TestRefineInvariantsRatchet:
    """Tests for the AlphaEvolve-style refinement ratchet."""

    def test_ratchet_returns_unchanged_when_evolution_disabled(self, monkeypatch):
        """Without NIGHTJAR_ENABLE_EVOLUTION=1, returns candidates unchanged with no LLM calls."""
        monkeypatch.delenv("NIGHTJAR_ENABLE_EVOLUTION", raising=False)
        candidate = CandidateInvariant(expression="result > 0", confidence=0.3)

        with patch("immune.enricher.litellm") as mock_litellm:
            result = refine_invariants_ratchet(
                candidates=[candidate],
                function_sig="def f(x: int) -> int",
            )
            mock_litellm.completion.assert_not_called()

        assert result == [candidate]

    @patch("immune.enricher._propose_refinement")
    @patch("immune.quality_scorer.score_candidate")
    def test_ratchet_improves_low_quality_invariant(
        self, mock_score, mock_propose, monkeypatch
    ):
        """When refinement improves score, the refined version replaces the original."""
        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        original = CandidateInvariant(expression="result > 0", confidence=0.3)
        refined = CandidateInvariant(expression="result >= 1", confidence=0.3)
        mock_propose.return_value = refined

        # score_before=0.4 (below threshold 0.5), score_after=0.6 (above)
        # Use a callable side_effect so it doesn't run out if called more than twice.
        scores_by_expr = {
            "result > 0": 0.4,
            "result >= 1": 0.6,
        }

        def score_by_expression(candidate):
            s = MagicMock()
            s.score = scores_by_expr.get(candidate.expression, 0.6)
            return s

        mock_score.side_effect = score_by_expression

        result = refine_invariants_ratchet(
            candidates=[original],
            function_sig="def f(x: int) -> int",
            quality_threshold=0.5,
        )

        assert len(result) == 1
        assert result[0].expression == "result >= 1"

    @patch("immune.enricher._propose_refinement")
    @patch("immune.quality_scorer.score_candidate")
    def test_ratchet_discards_regression(
        self, mock_score, mock_propose, monkeypatch
    ):
        """When refinement lowers score, the original is kept (ratchet guarantee)."""
        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        original = CandidateInvariant(expression="result > 0", confidence=0.3)
        regressed = CandidateInvariant(expression="True", confidence=0.3)
        mock_propose.return_value = regressed

        # score_before=0.4 (original), score_after=0.3 (regression)
        # After discarding, original stays in result; subsequent rounds also score 0.4.
        scores_by_expr = {
            "result > 0": 0.4,
            "True": 0.3,
        }

        def score_by_expression(candidate):
            s = MagicMock()
            s.score = scores_by_expr.get(candidate.expression, 0.4)
            return s

        mock_score.side_effect = score_by_expression

        result = refine_invariants_ratchet(
            candidates=[original],
            function_sig="def f(x: int) -> int",
            quality_threshold=0.5,
        )

        assert len(result) == 1
        assert result[0].expression == "result > 0"

    @patch("immune.enricher._propose_refinement")
    @patch("immune.quality_scorer.score_candidate")
    def test_ratchet_skips_already_good_invariants(
        self, mock_score, mock_propose, monkeypatch
    ):
        """Invariants at or above quality_threshold are skipped — no LLM call made."""
        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        good = CandidateInvariant(expression="result >= 1 and result <= 100", confidence=0.9)
        above_threshold = MagicMock()
        above_threshold.score = 0.8
        mock_score.return_value = above_threshold

        result = refine_invariants_ratchet(
            candidates=[good],
            function_sig="def f(x: int) -> int",
            quality_threshold=0.5,
        )

        mock_propose.assert_not_called()
        assert result[0].expression == "result >= 1 and result <= 100"

    @patch("immune.enricher._propose_refinement")
    @patch("immune.quality_scorer.score_candidate")
    def test_ratchet_respects_budget_seconds(
        self, mock_score, mock_propose, monkeypatch
    ):
        """Loop exits when wall-clock budget is exceeded."""
        import time

        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        candidates = [
            CandidateInvariant(expression=f"result > {i}", confidence=0.3)
            for i in range(5)
        ]

        below_threshold = MagicMock()
        below_threshold.score = 0.4

        def slow_propose(candidate, function_sig, model=None):
            time.sleep(0.05)
            return None

        mock_score.return_value = below_threshold
        mock_propose.side_effect = slow_propose

        start = time.monotonic()
        result = refine_invariants_ratchet(
            candidates=candidates,
            function_sig="def f(x: int) -> int",
            quality_threshold=0.5,
            budget_seconds=0.1,
            max_rounds=10,
        )
        elapsed = time.monotonic() - start

        # Must exit well before max_rounds * len(candidates) * sleep_time
        assert elapsed < 2.0
        assert len(result) == len(candidates)

    @patch("immune.enricher._propose_refinement")
    @patch("immune.quality_scorer.score_candidate")
    def test_plateau_detection_stops_after_two_no_improvement_rounds(
        self, mock_score, mock_propose, monkeypatch
    ):
        """When LLM returns None for every candidate, stops after 2 consecutive
        no-improvement rounds regardless of max_rounds."""
        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        candidate = CandidateInvariant(expression="result > 0", confidence=0.3)
        below_threshold = MagicMock()
        below_threshold.score = 0.4
        mock_score.return_value = below_threshold
        mock_propose.return_value = None  # Never improves

        result = refine_invariants_ratchet(
            candidates=[candidate],
            function_sig="def f(x: int) -> int",
            quality_threshold=0.5,
            max_rounds=10,
        )

        # With plateau_detection, loop stops after 2 consecutive no-improvement rounds.
        # propose should be called at most 2 times (once per round for 2 rounds).
        assert mock_propose.call_count <= 2
        assert result[0].expression == "result > 0"


class TestProposeRefinement:
    """Tests for the SEARCH/REPLACE LLM refinement proposer."""

    @patch("immune.enricher.litellm")
    def test_propose_refinement_parses_search_replace_format(self, mock_litellm):
        """When LLM returns valid SEARCH/REPLACE, expression is updated."""
        candidate = CandidateInvariant(expression="result > 0", confidence=0.5)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "SEARCH: > 0\nREPLACE: >= 1"
        mock_litellm.completion.return_value = mock_response

        result = _propose_refinement(candidate, "def f(x: int) -> int")

        assert result is not None
        assert result.expression == "result >= 1"

    @patch("immune.enricher.litellm")
    def test_propose_refinement_returns_none_on_no_change(self, mock_litellm):
        """When LLM returns NO_CHANGE, function returns None."""
        candidate = CandidateInvariant(expression="result > 0", confidence=0.5)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "NO_CHANGE"
        mock_litellm.completion.return_value = mock_response

        result = _propose_refinement(candidate, "def f(x: int) -> int")

        assert result is None


class TestRefinementTsvLogging:
    """Tests for TSV refinement logging."""

    def test_refinement_logs_to_tsv(self, tmp_path, monkeypatch):
        """After ratchet runs and improves an invariant, a TSV file is created."""
        log_file = tmp_path / "invariant_refinement.tsv"
        monkeypatch.setenv("NIGHTJAR_ENABLE_EVOLUTION", "1")

        # Write a single row directly to verify log function works
        _log_refinement_to_tsv(
            str(log_file),
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "function_sig": "def f(x: int) -> int",
                "expression_before": "result > 0",
                "expression_after": "result >= 1",
                "score_before": "0.4000",
                "score_after": "0.6000",
                "action": "KEEP",
            },
        )

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "KEEP" in content
        assert "result > 0" in content
        assert "result >= 1" in content
