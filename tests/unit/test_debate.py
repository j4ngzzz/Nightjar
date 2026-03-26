"""Tests for adversarial debate invariant validation.

Task U2.3: Proposer + skeptic LLM agents — only invariants that survive
the skeptic challenge enter the spec.

TradingAgents adversarial debate pattern:
  1. Proposer argues why the invariant is always true
  2. Skeptic tries to find a counterexample or refutation
  3. Verdict: REFUTED → filtered out; STANDS → accepted

TDD: Tests written BEFORE implementation.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from immune.enricher import CandidateInvariant
from immune.debate import (
    DebateResult,
    debate_invariant,
    debate_invariants,
    filter_by_debate,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def make_candidate(expression: str, confidence: float = 0.7) -> CandidateInvariant:
    return CandidateInvariant(expression=expression, confidence=confidence)


def _mock_resp(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


def _two_call_mock(proposer_text: str, skeptic_text: str):
    """Return a mock that yields proposer then skeptic response."""
    return [_mock_resp(proposer_text), _mock_resp(skeptic_text)]


# ── TestDebateResult ───────────────────────────────────────────────────────────


class TestDebateResult:
    def test_has_required_fields(self):
        candidate = make_candidate("result >= 0")
        dr = DebateResult(
            candidate=candidate,
            survived=True,
            challenge="no counterexample found",
            reason="skeptic could not refute",
        )
        assert dr.candidate is candidate
        assert dr.survived is True
        assert dr.challenge == "no counterexample found"

    def test_survived_false(self):
        dr = DebateResult(
            candidate=make_candidate("x > 0"),
            survived=False,
            challenge="x can be 0 when empty list is passed",
            reason="refuted by skeptic",
        )
        assert not dr.survived


# ── TestDebateInvariant ────────────────────────────────────────────────────────


class TestDebateInvariant:
    """debate_invariant — single-invariant adversarial debate."""

    def test_returns_debate_result(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock(
                "This invariant holds because ...",
                "STANDS: I found no counterexample.",
            )
            result = debate_invariant(make_candidate("result >= 0"), model="test-model")
        assert isinstance(result, DebateResult)

    def test_debate_filters_spurious_invariants(self):
        """Required test: skeptic refutes spurious invariant → survived=False."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock(
                "This invariant should always hold ...",
                "REFUTED: counterexample found when input is -1.",
            )
            result = debate_invariant(
                make_candidate("x is always positive"), model="test-model"
            )
        assert not result.survived

    def test_debate_retains_robust_invariants(self):
        """Required test: skeptic cannot refute → survived=True."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock(
                "The return value is defined to be non-negative by the contract.",
                "STANDS: The invariant holds by construction — no counterexample.",
            )
            result = debate_invariant(
                make_candidate("result >= 0"), model="test-model"
            )
        assert result.survived

    def test_challenge_stored_in_result(self):
        """The skeptic's response is preserved in DebateResult.challenge."""
        challenge_text = "REFUTED: x can be negative when debt exceeds balance."
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("The balance ...", challenge_text)
            result = debate_invariant(make_candidate("balance >= 0"), model="test-model")
        assert "negative" in result.challenge or "REFUTED" in result.challenge

    def test_makes_two_llm_calls(self):
        """Exactly two LLM calls: proposer then skeptic."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("defence text", "STANDS: ok")
            debate_invariant(make_candidate("x > 0"), model="test-model")
        assert mock_llm.call_count == 2

    def test_uses_provided_model(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("defence", "STANDS: ok")
            debate_invariant(make_candidate("x > 0"), model="my-specific-model")
        assert mock_llm.called

    def test_candidate_preserved_in_result(self):
        candidate = make_candidate("result >= 0")
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("defence", "STANDS: ok")
            result = debate_invariant(candidate, model="test-model")
        assert result.candidate is candidate

    def test_llm_error_defaults_to_survived(self):
        """LLM failure is safe — default to survived=True (don't drop on error)."""
        with patch("litellm.completion", side_effect=Exception("API error")):
            result = debate_invariant(make_candidate("x > 0"), model="test-model")
        assert isinstance(result, DebateResult)
        # Error path: survived=True (conservative — don't drop on LLM failure)
        assert result.survived is True

    def test_stands_case_insensitive(self):
        """'stands' in any case counts as survived."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("defence", "stands: no counterexample")
            result = debate_invariant(make_candidate("x > 0"), model="test-model")
        assert result.survived

    def test_refuted_case_insensitive(self):
        """'refuted' in any case counts as rejected."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = _two_call_mock("defence", "refuted: found x=-1")
            result = debate_invariant(make_candidate("x > 0"), model="test-model")
        assert not result.survived


# ── TestDebateInvariants ───────────────────────────────────────────────────────


class TestDebateInvariants:
    """debate_invariants — batch debate."""

    def test_returns_list_of_debate_results(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [
                _mock_resp("defence A"),
                _mock_resp("STANDS: ok"),
                _mock_resp("defence B"),
                _mock_resp("STANDS: ok"),
            ]
            results = debate_invariants(
                [make_candidate("x > 0"), make_candidate("y >= 0")],
                model="test-model",
            )
        assert isinstance(results, list)
        assert all(isinstance(r, DebateResult) for r in results)

    def test_empty_input_returns_empty(self):
        results = debate_invariants([], model="test-model")
        assert results == []

    def test_length_matches_input(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [_mock_resp("d"), _mock_resp("STANDS")] * 3
            results = debate_invariants(
                [make_candidate(e) for e in ["x>0", "y>0", "z>0"]],
                model="test-model",
            )
        assert len(results) == 3


# ── TestFilterByDebate ─────────────────────────────────────────────────────────


class TestFilterByDebate:
    def test_filter_removes_refuted_invariants(self):
        """REFUTED invariants do not appear in filter output."""
        candidates = [
            make_candidate("x is always positive"),
            make_candidate("result >= 0"),
        ]
        with patch("litellm.completion") as mock_llm:
            # Candidate 1: refuted. Candidate 2: stands.
            mock_llm.side_effect = [
                _mock_resp("defence for x"),
                _mock_resp("REFUTED: x can be 0"),
                _mock_resp("defence for result"),
                _mock_resp("STANDS: no counterexample"),
            ]
            survivors = filter_by_debate(candidates, model="test-model")
        exprs = [c.expression for c in survivors]
        assert "x is always positive" not in exprs
        assert "result >= 0" in exprs

    def test_filter_retains_survived_invariants(self):
        candidates = [make_candidate("result >= 0"), make_candidate("amount > 0")]
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [
                _mock_resp("defence"),
                _mock_resp("STANDS: ok"),
                _mock_resp("defence"),
                _mock_resp("STANDS: ok"),
            ]
            survivors = filter_by_debate(candidates, model="test-model")
        assert len(survivors) == 2

    def test_filter_returns_candidate_invariants(self):
        """filter_by_debate returns list[CandidateInvariant], not DebateResult."""
        candidates = [make_candidate("result >= 0")]
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [_mock_resp("defence"), _mock_resp("STANDS: ok")]
            survivors = filter_by_debate(candidates, model="test-model")
        assert all(isinstance(c, CandidateInvariant) for c in survivors)

    def test_empty_input_returns_empty(self):
        survivors = filter_by_debate([], model="test-model")
        assert survivors == []

    def test_all_refuted_returns_empty(self):
        candidates = [make_candidate("x > 0"), make_candidate("y > 0")]
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [
                _mock_resp("d"), _mock_resp("REFUTED"),
                _mock_resp("d"), _mock_resp("REFUTED"),
            ]
            survivors = filter_by_debate(candidates, model="test-model")
        assert len(survivors) == 0

    def test_preserves_order_of_survivors(self):
        candidates = [
            make_candidate("result >= 0"),
            make_candidate("amount > 0"),
            make_candidate("x > 0"),
        ]
        with patch("litellm.completion") as mock_llm:
            mock_llm.side_effect = [
                _mock_resp("d"), _mock_resp("STANDS"),  # result>=0 survives
                _mock_resp("d"), _mock_resp("REFUTED"),  # amount>0 filtered
                _mock_resp("d"), _mock_resp("STANDS"),  # x>0 survives
            ]
            survivors = filter_by_debate(candidates, model="test-model")
        exprs = [c.expression for c in survivors]
        assert exprs.index("result >= 0") < exprs.index("x > 0")
        assert "amount > 0" not in exprs
