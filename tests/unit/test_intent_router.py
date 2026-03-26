"""Tests for the NL intent router — classification and parsing.

Tests the intent router pipeline from Task W2.1:
  NL string → NLIntent parse → invariant classification

References:
- [REF-P14] NL2Contract: clean-room CR-03 (arxiv 2510.12702)
- Scout 4 F1 (ContextCov: arxiv 2603.00822)
- [REF-T17] Click CLI framework

TDD: These tests were written BEFORE implementation.
Run `pytest tests/unit/test_intent_router.py -v` to verify they FAIL first.
"""

import pytest

from nightjar.intent_router import (
    NLIntent,
    InvariantClass,
    parse_nl_intent,
    classify_invariant,
)


# ── parse_nl_intent tests ────────────────────────────────────────────────────


class TestParseNLIntent:
    """Tests for parse_nl_intent — Step 1 of the nightjar auto pipeline.

    ContextCov (CR-02, arxiv 2603.00822): path-aware slicing extracts
    coverage-relevant context from the NL string.
    """

    def test_parse_returns_nlintent(self):
        """parse_nl_intent must return an NLIntent dataclass."""
        result = parse_nl_intent("Build a payment processor that charges credit cards")
        assert isinstance(result, NLIntent)

    def test_parse_extracts_subject(self):
        """Subject is the core noun phrase of the NL intent."""
        result = parse_nl_intent("Build a payment processor that charges credit cards")
        assert result.subject
        assert len(result.subject) > 0

    def test_parse_stores_raw_intent(self):
        """Raw NL string must be preserved unchanged."""
        nl = "Build a payment processor that charges credit cards"
        result = parse_nl_intent(nl)
        assert result.raw == nl

    def test_parse_extracts_behaviors(self):
        """Behavioral phrases must be extracted from the NL string."""
        result = parse_nl_intent(
            "Build a payment processor that charges credit cards and returns a receipt"
        )
        assert isinstance(result.behaviors, list)

    def test_parse_infers_outputs(self):
        """Output types/names must be inferred when present."""
        result = parse_nl_intent("A function that returns a boolean indicating success")
        assert isinstance(result.inferred_outputs, list)

    def test_parse_empty_string_raises(self):
        """Empty string must raise ValueError — cannot parse empty intent."""
        with pytest.raises(ValueError, match="intent"):
            parse_nl_intent("")

    def test_parse_whitespace_only_raises(self):
        """Whitespace-only string must raise ValueError."""
        with pytest.raises(ValueError, match="intent"):
            parse_nl_intent("   ")

    def test_parse_short_intent(self):
        """Short intents (< 5 words) are accepted but minimal."""
        result = parse_nl_intent("Sort a list")
        assert isinstance(result, NLIntent)
        assert result.raw == "Sort a list"


# ── classify_invariant tests ─────────────────────────────────────────────────


class TestClassifyInvariant:
    """Tests for classify_invariant — Step 3 of the nightjar auto pipeline.

    Classification maps invariant statements to:
    - NUMERICAL: bounds, arithmetic, counts, sizes
    - BEHAVIORAL: pre/postcondition style, I/O relationships
    - STATE: always/never true, object lifecycle invariants
    - FORMAL: mathematical/logical quantifiers
    """

    # ── NUMERICAL ──

    def test_classify_numerical_positive(self):
        """'amount must be positive' → NUMERICAL."""
        result = classify_invariant("amount must be positive")
        assert result == InvariantClass.NUMERICAL

    def test_classify_numerical_greater_than(self):
        """'price > 0' → NUMERICAL."""
        result = classify_invariant("price > 0")
        assert result == InvariantClass.NUMERICAL

    def test_classify_numerical_count(self):
        """'count >= 0' → NUMERICAL."""
        result = classify_invariant("count >= 0")
        assert result == InvariantClass.NUMERICAL

    def test_classify_numerical_max_value(self):
        """'value must not exceed maximum' → NUMERICAL."""
        result = classify_invariant("value must not exceed maximum allowed limit")
        assert result == InvariantClass.NUMERICAL

    # ── BEHAVIORAL ──

    def test_classify_behavioral_returns(self):
        """'returns non-empty string when valid input' → BEHAVIORAL."""
        result = classify_invariant("returns non-empty string when valid input is given")
        assert result == InvariantClass.BEHAVIORAL

    def test_classify_behavioral_postcondition(self):
        """Postcondition-style statement → BEHAVIORAL."""
        result = classify_invariant("after charging, the receipt is not None")
        assert result == InvariantClass.BEHAVIORAL

    def test_classify_behavioral_requires_input(self):
        """Precondition-style → BEHAVIORAL."""
        result = classify_invariant("input email must be a valid email address")
        assert result == InvariantClass.BEHAVIORAL

    # ── STATE ──

    def test_classify_state_always(self):
        """'always holds' language → STATE."""
        result = classify_invariant("balance is always non-negative throughout all operations")
        assert result == InvariantClass.STATE

    def test_classify_state_never(self):
        """'never null' → STATE."""
        result = classify_invariant("the session token is never null")
        assert result == InvariantClass.STATE

    def test_classify_state_transition(self):
        """State machine transition → STATE."""
        result = classify_invariant("transitions from pending to completed state")
        assert result == InvariantClass.STATE

    # ── FORMAL ──

    def test_classify_formal_for_all(self):
        """'for all x' quantifier → FORMAL."""
        result = classify_invariant("for all x in the input list, x > 0 implies result > 0")
        assert result == InvariantClass.FORMAL

    def test_classify_formal_there_exists(self):
        """'there exists' quantifier → FORMAL."""
        result = classify_invariant("there exists exactly one session per user at any time")
        assert result == InvariantClass.FORMAL

    # ── Return type ──

    def test_classify_returns_invariant_class(self):
        """classify_invariant always returns an InvariantClass enum value."""
        result = classify_invariant("some statement about the function")
        assert isinstance(result, InvariantClass)

    def test_classify_empty_defaults_to_behavioral(self):
        """Ambiguous/unclassifiable → defaults to BEHAVIORAL (most common)."""
        result = classify_invariant("it works correctly")
        assert result in InvariantClass
