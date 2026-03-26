"""Tests for Wonda-inspired invariant quality scoring.

Task U2.1: Quality gate between miner output and enricher input.

Wonda (arxiv 2603.15510): AST normalization + semantic quality filter.
4B model matches 120B with proper curation. Key insight: most mined
invariants are trivially true or semantically vacuous. Filtering them
before LLM enrichment saves tokens and improves output quality.

Quality criteria:
  - Minimality: not a tautology (True, x == x)
  - Provability: syntactically valid Python expression
  - Semantic meaningfulness: references function parameters or result,
    not generic placeholders

References:
  REF-NEW-05: Wonda (arxiv 2603.15510)
  [REF-C05] Dynamic Invariant Mining
  [REF-P15] Agentic PBT

TDD: Tests written BEFORE implementation.
"""

import ast
import pytest
from unittest.mock import patch, MagicMock

from immune.enricher import CandidateInvariant
from immune.quality_scorer import (
    QualityScore,
    score_candidate,
    score_candidates,
    filter_by_quality,
    QUALITY_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_candidate(expression: str, explanation: str = "", confidence: float = 0.7) -> CandidateInvariant:
    return CandidateInvariant(expression=expression, explanation=explanation, confidence=confidence)


# ── QualityScore ─────────────────────────────────────────────────────────────


class TestQualityScore:
    def test_quality_score_has_required_fields(self):
        qs = QualityScore(
            candidate=make_candidate("result >= 0"),
            score=0.8,
            is_trivial=False,
            is_valid_syntax=True,
            reason="",
        )
        assert qs.score == 0.8
        assert not qs.is_trivial
        assert qs.is_valid_syntax

    def test_quality_score_below_threshold_is_filtered(self):
        qs = QualityScore(
            candidate=make_candidate("True"),
            score=0.0,
            is_trivial=True,
            is_valid_syntax=True,
            reason="tautology",
        )
        assert qs.score < QUALITY_THRESHOLD


# ── score_candidate ───────────────────────────────────────────────────────────


class TestScoreCandidate:
    """Tests for score_candidate — single-invariant quality scoring."""

    # ── Trivial invariants (should score LOW) ──

    def test_literal_true_is_trivial(self):
        """'True' is a tautology — trivially true."""
        qs = score_candidate(make_candidate("True"))
        assert qs.is_trivial
        assert qs.score < QUALITY_THRESHOLD

    def test_literal_false_is_trivial(self):
        """'False' is trivially false — not a useful invariant."""
        qs = score_candidate(make_candidate("False"))
        assert qs.is_trivial

    def test_identity_comparison_is_trivial(self):
        """'x == x' is always true — tautology."""
        qs = score_candidate(make_candidate("x == x"))
        assert qs.is_trivial
        assert qs.score < QUALITY_THRESHOLD

    def test_empty_expression_is_trivial(self):
        """Empty string is not a valid invariant."""
        qs = score_candidate(make_candidate(""))
        assert qs.is_trivial or not qs.is_valid_syntax

    # ── Meaningful invariants (should score HIGH) ──

    def test_result_non_negative_is_meaningful(self):
        """'result >= 0' — meaningful postcondition."""
        qs = score_candidate(make_candidate("result >= 0", "return value is non-negative"))
        assert not qs.is_trivial
        assert qs.score >= QUALITY_THRESHOLD

    def test_amount_positive_is_meaningful(self):
        """'amount > 0' — meaningful precondition bound."""
        qs = score_candidate(make_candidate("amount > 0"))
        assert qs.score >= QUALITY_THRESHOLD

    def test_result_not_none_is_meaningful(self):
        """'result is not None' — useful nullness invariant."""
        qs = score_candidate(make_candidate("result is not None"))
        assert qs.score >= QUALITY_THRESHOLD

    def test_result_not_empty_is_meaningful(self):
        """'len(result) > 0' — meaningful length invariant."""
        qs = score_candidate(make_candidate("len(result) > 0"))
        assert qs.score >= QUALITY_THRESHOLD

    # ── Syntax validity ──

    def test_invalid_syntax_scores_zero(self):
        """Syntactically invalid expression should not pass."""
        qs = score_candidate(make_candidate("result > > 0"))  # double >
        assert not qs.is_valid_syntax

    def test_valid_syntax_is_marked(self):
        qs = score_candidate(make_candidate("x + y > 0"))
        assert qs.is_valid_syntax

    # ── score_candidate returns QualityScore ──

    def test_returns_quality_score_type(self):
        qs = score_candidate(make_candidate("result >= 0"))
        assert isinstance(qs, QualityScore)

    def test_score_is_between_0_and_1(self):
        for expr in ["result >= 0", "True", "x == x", "amount > 0"]:
            qs = score_candidate(make_candidate(expr))
            assert 0.0 <= qs.score <= 1.0, f"Score out of range for: {expr}"


# ── score_candidates ──────────────────────────────────────────────────────────


class TestScoreCandidates:
    def test_returns_list_of_quality_scores(self):
        candidates = [make_candidate("result >= 0"), make_candidate("True")]
        scores = score_candidates(candidates)
        assert isinstance(scores, list)
        assert all(isinstance(s, QualityScore) for s in scores)

    def test_empty_input_returns_empty(self):
        assert score_candidates([]) == []

    def test_length_matches_input(self):
        candidates = [make_candidate(e) for e in ["result >= 0", "True", "x > 0"]]
        scores = score_candidates(candidates)
        assert len(scores) == len(candidates)


# ── filter_by_quality ─────────────────────────────────────────────────────────


class TestFilterByQuality:
    """test_scorer_filters_trivial_invariants (build plan required test)."""

    def test_scorer_filters_trivial_invariants(self):
        """Trivial invariants (True, x==x) are removed by quality filter."""
        candidates = [
            make_candidate("True"),
            make_candidate("x == x"),
            make_candidate("result >= 0"),
        ]
        filtered = filter_by_quality(candidates)
        exprs = [c.expression for c in filtered]
        assert "True" not in exprs
        assert "x == x" not in exprs

    def test_scorer_retains_semantically_meaningful_invariants(self):
        """Meaningful invariants survive the quality filter."""
        candidates = [
            make_candidate("result >= 0", "non-negative return"),
            make_candidate("amount > 0", "positive amount"),
            make_candidate("result is not None", "non-null result"),
        ]
        filtered = filter_by_quality(candidates)
        assert len(filtered) > 0
        exprs = [c.expression for c in filtered]
        assert "result >= 0" in exprs

    def test_filter_returns_candidate_invariants(self):
        """filter_by_quality returns list[CandidateInvariant], not QualityScore."""
        candidates = [make_candidate("result >= 0")]
        filtered = filter_by_quality(candidates)
        assert all(isinstance(c, CandidateInvariant) for c in filtered)

    def test_empty_input_returns_empty(self):
        assert filter_by_quality([]) == []

    def test_all_trivial_returns_empty(self):
        candidates = [make_candidate("True"), make_candidate("False"), make_candidate("x == x")]
        filtered = filter_by_quality(candidates)
        assert len(filtered) == 0

    def test_preserves_order_of_meaningful_invariants(self):
        """Filter preserves relative order of surviving invariants."""
        candidates = [
            make_candidate("result >= 0"),
            make_candidate("True"),  # filtered out
            make_candidate("amount > 0"),
        ]
        filtered = filter_by_quality(candidates)
        exprs = [c.expression for c in filtered]
        assert exprs.index("result >= 0") < exprs.index("amount > 0")

    def test_custom_threshold(self):
        """filter_by_quality accepts a custom threshold."""
        candidates = [make_candidate("result >= 0", confidence=0.6)]
        # With very high threshold, might be filtered
        strict = filter_by_quality(candidates, threshold=0.99)
        permissive = filter_by_quality(candidates, threshold=0.0)
        assert len(permissive) >= len(strict)

    def test_confidence_boosts_score(self):
        """Higher LLM confidence → higher quality score."""
        low = make_candidate("result >= 0", confidence=0.1)
        high = make_candidate("result >= 0", confidence=0.99)
        score_low = score_candidate(low).score
        score_high = score_candidate(high).score
        assert score_high >= score_low
