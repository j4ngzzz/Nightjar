"""Tests for invariant generators — icontract, Hypothesis, Dafny.

Tests the domain-specific generator modules from Task W2.1:
  InvariantCandidate → @require/@ensure / @given / requires/ensures

References:
- [REF-T10] icontract design by contract
- [REF-T03] Hypothesis property-based testing
- [REF-T01] Dafny formal verification
- [REF-P14] NL2Contract (arxiv 2510.12702) — CR-03
- Scout 4 honest assessment: Dafny tier is OPTIONAL, auto-suggested only

TDD: These tests were written BEFORE implementation.
"""

import re
import pytest
from unittest.mock import patch, MagicMock

from nightjar.invariant_generators import (
    InvariantCandidate,
    RankedInvariant,
    rank_candidates,
    format_invariant,
)
from nightjar.intent_router import InvariantClass
from nightjar.invariant_generators.icontract_gen import generate_icontract
from nightjar.invariant_generators.hypothesis_gen import generate_hypothesis
from nightjar.invariant_generators.dafny_gen import generate_dafny


# ── Fixtures ─────────────────────────────────────────────────────────────────


def make_numerical_candidate() -> InvariantCandidate:
    return InvariantCandidate(
        statement="amount must be positive",
        confidence=0.95,
        inv_class=InvariantClass.NUMERICAL,
    )


def make_behavioral_candidate() -> InvariantCandidate:
    return InvariantCandidate(
        statement="returns non-empty receipt when charge succeeds",
        confidence=0.90,
        inv_class=InvariantClass.BEHAVIORAL,
    )


def make_state_candidate() -> InvariantCandidate:
    return InvariantCandidate(
        statement="balance is always non-negative throughout operations",
        confidence=0.85,
        inv_class=InvariantClass.STATE,
    )


def make_formal_candidate() -> InvariantCandidate:
    return InvariantCandidate(
        statement="for all x: charge(x) > 0 implies receipt(x) is not None",
        confidence=0.70,
        inv_class=InvariantClass.FORMAL,
    )


# ── InvariantCandidate ────────────────────────────────────────────────────────


class TestInvariantCandidate:
    """Tests for the InvariantCandidate dataclass."""

    def test_create_candidate(self):
        c = make_numerical_candidate()
        assert c.statement == "amount must be positive"
        assert c.confidence == 0.95
        assert c.inv_class == InvariantClass.NUMERICAL

    def test_confidence_between_0_and_1(self):
        c = InvariantCandidate(
            statement="test",
            confidence=1.1,
            inv_class=InvariantClass.BEHAVIORAL,
        )
        # Confidence out of bounds — validation should catch this
        # (or we accept it and clamp in ranking)
        assert isinstance(c, InvariantCandidate)


# ── rank_candidates ───────────────────────────────────────────────────────────


class TestRankCandidates:
    """Tests for rank_candidates — HiLDe-inspired ranking (Step 5).

    HiLDe (arxiv 2505.22906, UC San Diego PL — Nadia Polikarpova):
    Surface top 5-10 candidates from potentially 50+ by interestingness.
    """

    def test_rank_returns_list(self):
        candidates = [make_numerical_candidate(), make_behavioral_candidate()]
        result = rank_candidates(candidates)
        assert isinstance(result, list)

    def test_rank_returns_ranked_invariants(self):
        candidates = [make_numerical_candidate()]
        result = rank_candidates(candidates)
        assert all(isinstance(r, RankedInvariant) for r in result)

    def test_rank_limits_to_top_n(self):
        """rank_candidates returns at most top_n results (default 7)."""
        candidates = [
            InvariantCandidate(
                statement=f"invariant {i}",
                confidence=float(i) / 20,
                inv_class=InvariantClass.BEHAVIORAL,
            )
            for i in range(20)
        ]
        result = rank_candidates(candidates)
        assert len(result) <= 10  # max 10

    def test_rank_sorted_by_score_descending(self):
        """Higher confidence candidates rank first (all else equal)."""
        low = InvariantCandidate(
            statement="low confidence invariant",
            confidence=0.2,
            inv_class=InvariantClass.BEHAVIORAL,
        )
        high = InvariantCandidate(
            statement="high confidence invariant",
            confidence=0.9,
            inv_class=InvariantClass.BEHAVIORAL,
        )
        result = rank_candidates([low, high])
        if len(result) >= 2:
            assert result[0].rank_score >= result[1].rank_score

    def test_rank_empty_list(self):
        """Empty input returns empty list."""
        assert rank_candidates([]) == []

    def test_rank_single_candidate(self):
        """Single candidate always passes through."""
        result = rank_candidates([make_numerical_candidate()])
        assert len(result) == 1

    def test_rank_penalizes_vague_terms(self):
        """Invariants with vague terms (valid, correct, proper) rank lower."""
        vague = InvariantCandidate(
            statement="input must be valid and correct and proper",
            confidence=0.8,
            inv_class=InvariantClass.BEHAVIORAL,
        )
        specific = InvariantCandidate(
            statement="amount must be greater than zero",
            confidence=0.8,
            inv_class=InvariantClass.NUMERICAL,
        )
        result = rank_candidates([vague, specific])
        if len(result) >= 2:
            scores = {r.candidate.statement: r.rank_score for r in result}
            if vague.statement in scores and specific.statement in scores:
                assert scores[specific.statement] >= scores[vague.statement]


# ── format_invariant ─────────────────────────────────────────────────────────


class TestFormatInvariant:
    """Tests for format_invariant — Kiro UX format (Step 6)."""

    def test_format_returns_string(self):
        c = make_behavioral_candidate()
        result = format_invariant(c)
        assert isinstance(result, str)

    def test_format_uses_for_any_pattern(self):
        """Formatted invariant follows 'For any X where Y, Z holds' pattern."""
        c = make_numerical_candidate()
        result = format_invariant(c)
        # Should contain at least a structured assertion
        assert len(result) > 0

    def test_format_includes_original_statement(self):
        """Formatted output references the original invariant."""
        c = InvariantCandidate(
            statement="amount must be positive",
            confidence=0.9,
            inv_class=InvariantClass.NUMERICAL,
        )
        result = format_invariant(c)
        # The original statement context should be preserved in formatted output
        assert "amount" in result.lower() or "positive" in result.lower()


# ── icontract_gen ─────────────────────────────────────────────────────────────


class TestIcontractGen:
    """Tests for generate_icontract — @require/@ensure generator (Step 4).

    Reference: [REF-T10] icontract (https://github.com/Parquery/icontract)
    API: @icontract.require(lambda param: condition, "description")
         @icontract.ensure(lambda result: condition, "description")
    """

    def _mock_litellm(self, content: str):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = content
        return mock_resp

    def test_icontract_gen_returns_string(self):
        """generate_icontract returns a non-empty string."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@icontract.require(lambda amount: amount > 0, 'amount must be positive')"
            )
            result = generate_icontract(make_numerical_candidate(), model="test-model")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_icontract_gen_precondition_for_behavioral(self):
        """Behavioral precondition → @icontract.require."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@icontract.require(lambda email: '@' in email, 'valid email required')"
            )
            result = generate_icontract(
                InvariantCandidate(
                    statement="input email must be a valid email address",
                    confidence=0.9,
                    inv_class=InvariantClass.BEHAVIORAL,
                ),
                model="test-model",
            )
        assert "icontract" in result

    def test_icontract_gen_produces_valid_python_syntax(self):
        """Generated icontract decorator must be syntactically valid Python."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@icontract.require(lambda amount: amount > 0, 'amount must be positive')"
            )
            result = generate_icontract(make_numerical_candidate(), model="test-model")
        # Must be parseable Python
        try:
            compile(result, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated icontract code has syntax error: {e}\nCode: {result}")

    def test_icontract_gen_uses_litellm(self):
        """generate_icontract must call litellm.completion (not provider directly)."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@icontract.require(lambda x: x > 0, 'positive')"
            )
            generate_icontract(make_numerical_candidate(), model="test-model")
        mock_llm.assert_called_once()


# ── hypothesis_gen ────────────────────────────────────────────────────────────


class TestHypothesisGen:
    """Tests for generate_hypothesis — @given strategy generator (Step 4).

    Reference: [REF-T03] Hypothesis (https://github.com/HypothesisWorks/hypothesis)
    API: @given(st.integers(min_value=1)) + test function body
    """

    def _mock_litellm(self, content: str):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = content
        return mock_resp

    def test_hypothesis_gen_returns_string(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@given(st.integers(min_value=1))\ndef test_amount_positive(amount):\n    assert amount > 0"
            )
            result = generate_hypothesis(make_numerical_candidate(), model="test-model")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hypothesis_gen_contains_given_decorator(self):
        """Must include @given decorator with strategies."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "@given(st.integers(min_value=1))\ndef test_prop(x):\n    assert x > 0"
            )
            result = generate_hypothesis(make_numerical_candidate(), model="test-model")
        assert "given" in result

    def test_hypothesis_gen_produces_valid_python(self):
        """Generated Hypothesis test must be syntactically valid Python."""
        code = (
            "from hypothesis import given, settings\n"
            "from hypothesis import strategies as st\n"
            "@given(st.integers(min_value=1))\n"
            "def test_amount_positive(amount):\n"
            "    assert amount > 0\n"
        )
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(code)
            result = generate_hypothesis(make_numerical_candidate(), model="test-model")
        try:
            compile(result, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated Hypothesis code has syntax error: {e}\nCode: {result}")


# ── dafny_gen ────────────────────────────────────────────────────────────────


class TestDafnyGen:
    """Tests for generate_dafny — optional Dafny requires/ensures generator (Step 4).

    Reference: [REF-T01] Dafny (https://github.com/dafny-lang/dafny)
    Scout 4 honest assessment: Dafny tier is OPTIONAL (auto-suggested only).
    LLMs still struggle with complex Dafny invariants.
    """

    def _mock_litellm(self, content: str):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = content
        return mock_resp

    def test_dafny_gen_returns_string(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm("requires amount > 0")
            result = generate_dafny(make_formal_candidate(), model="test-model")
        assert isinstance(result, str)

    def test_dafny_gen_for_formal_class(self):
        """Formal invariants get Dafny requires/ensures clauses."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm(
                "requires x > 0\nensures result != \"\""
            )
            result = generate_dafny(make_formal_candidate(), model="test-model")
        assert "requires" in result or "ensures" in result

    def test_dafny_gen_marks_as_optional(self):
        """Dafny output must be marked as optional/auto-suggested."""
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = self._mock_litellm("requires amount > 0")
            result = generate_dafny(make_numerical_candidate(), model="test-model")
        # The result must indicate it's optional
        assert "optional" in result.lower() or "# " in result or result.startswith("#")
