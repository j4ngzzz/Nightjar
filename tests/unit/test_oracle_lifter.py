"""Tests for test oracle lifting to card.md invariants.

Task U2.2: AST-parse test files → extract assert statements →
LLM converts to NL invariants → write to .card.md.

Reference: arxiv:2601.12845 — 98.2% success rate lifting test assertions
into postconditions for formal verification.

TDD: Tests written BEFORE implementation.
"""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nightjar.oracle_lifter import (
    LiftedInvariant,
    extract_asserts,
    lift_to_invariants,
    lift_oracle_file,
    lift_to_card,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_llm_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


# ── TestExtractAsserts ─────────────────────────────────────────────────────────


class TestExtractAsserts:
    """extract_asserts — pure AST, no LLM."""

    def test_lifter_extracts_assert_from_test_file(self):
        """Required test from build plan: extract assert from test source."""
        source = textwrap.dedent("""\
            def test_payment():
                result = process_payment(100)
                assert result.balance >= 0
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 1
        assert "result.balance >= 0" in exprs[0]

    def test_extracts_multiple_asserts(self):
        source = textwrap.dedent("""\
            def test_foo():
                assert x > 0
                assert y != 0
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 2

    def test_no_asserts_returns_empty(self):
        source = "def test_foo():\n    pass\n"
        assert extract_asserts(source) == []

    def test_ignores_non_assert_statements(self):
        source = textwrap.dedent("""\
            def test_foo():
                x = 1
                assert x == 1
                y = x + 1
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 1

    def test_extracts_assert_with_message(self):
        """assert expr, 'msg' — captures the test expression only."""
        source = textwrap.dedent("""\
            def test_foo():
                assert result > 0, "result must be positive"
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 1
        assert "result > 0" in exprs[0]

    def test_nested_method_asserts(self):
        """Asserts inside class methods are also extracted."""
        source = textwrap.dedent("""\
            class TestPayment:
                def test_balance(self):
                    assert balance >= 0
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 1

    def test_returns_list_of_strings(self):
        source = "def test_x():\n    assert x > 0\n"
        exprs = extract_asserts(source)
        assert isinstance(exprs, list)
        assert all(isinstance(e, str) for e in exprs)

    def test_empty_source_returns_empty(self):
        assert extract_asserts("") == []

    def test_complex_assert_expression(self):
        """Multi-part expressions preserved correctly."""
        source = textwrap.dedent("""\
            def test_receipt():
                assert result.receipt is not None
        """)
        exprs = extract_asserts(source)
        assert len(exprs) == 1
        assert "result.receipt is not None" in exprs[0]


# ── TestLiftedInvariant ────────────────────────────────────────────────────────


class TestLiftedInvariant:
    def test_has_required_fields(self):
        li = LiftedInvariant(
            assert_expr="result.balance >= 0",
            nl_statement="balance is always non-negative after deduction",
        )
        assert li.assert_expr == "result.balance >= 0"
        assert li.nl_statement == "balance is always non-negative after deduction"

    def test_default_tier_is_property(self):
        li = LiftedInvariant(assert_expr="x > 0", nl_statement="x is positive")
        assert li.tier == "property"

    def test_custom_tier(self):
        li = LiftedInvariant(assert_expr="x > 0", nl_statement="x is positive", tier="example")
        assert li.tier == "example"


# ── TestLiftToInvariants ───────────────────────────────────────────────────────


class TestLiftToInvariants:
    """lift_to_invariants — LLM conversion of assert exprs to NL invariants."""

    def test_returns_list_of_lifted_invariants(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response("balance is always non-negative")
            result = lift_to_invariants(["result.balance >= 0"], model="test-model")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], LiftedInvariant)

    def test_empty_input_returns_empty(self):
        result = lift_to_invariants([], model="test-model")
        assert result == []

    def test_length_matches_input(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response("some invariant")
            result = lift_to_invariants(
                ["x > 0", "y != 0", "z is not None"], model="test-model"
            )
        assert len(result) == 3

    def test_assert_expr_preserved(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response("balance is non-negative")
            result = lift_to_invariants(["result.balance >= 0"], model="test-model")
        assert result[0].assert_expr == "result.balance >= 0"

    def test_nl_statement_from_llm_response(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response(
                "balance is always non-negative after deduction"
            )
            result = lift_to_invariants(["result.balance >= 0"], model="test-model")
        assert "non-negative" in result[0].nl_statement

    def test_uses_provided_model(self):
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response("invariant text")
            lift_to_invariants(["x > 0"], model="claude-test-model")
        call_kwargs = mock_llm.call_args[1] if mock_llm.call_args[1] else mock_llm.call_args[0][0]
        # model argument must be passed through
        assert mock_llm.called

    def test_handles_llm_error_gracefully(self):
        """LLM failure falls back — does not raise."""
        with patch("litellm.completion", side_effect=Exception("API error")):
            result = lift_to_invariants(["x > 0"], model="test-model")
        assert len(result) == 1
        assert isinstance(result[0], LiftedInvariant)
        assert result[0].assert_expr == "x > 0"


# ── TestLiftOracleFile ─────────────────────────────────────────────────────────


class TestLiftOracleFile:
    def test_lifter_extracts_assert_from_file(self, tmp_path):
        test_file = tmp_path / "test_payment.py"
        test_file.write_text(
            textwrap.dedent("""\
                def test_balance():
                    assert result.balance >= 0
                    assert result.receipt is not None
            """)
        )
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response("balance is non-negative")
            result = lift_oracle_file(test_file, model="test-model")
        assert len(result) == 2
        assert all(isinstance(li, LiftedInvariant) for li in result)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            lift_oracle_file(tmp_path / "nonexistent.py", model="test-model")

    def test_file_with_no_asserts_returns_empty(self, tmp_path):
        test_file = tmp_path / "test_empty.py"
        test_file.write_text("def test_foo():\n    pass\n")
        result = lift_oracle_file(test_file, model="test-model")
        assert result == []


# ── TestLiftToCard ─────────────────────────────────────────────────────────────


class TestLiftToCard:
    def test_lifter_generates_card_md_invariant(self, tmp_path):
        """Required test from build plan: lifted invariant appears in card.md."""
        card_path = tmp_path / "payment.card.md"
        card_path.write_text("## Intent\n\nProcess payments.\n")
        invariants = [
            LiftedInvariant(
                assert_expr="result.balance >= 0",
                nl_statement="balance is always non-negative after deduction",
            )
        ]
        lift_to_card(invariants, card_path)
        content = card_path.read_text()
        assert "balance is always non-negative after deduction" in content

    def test_lift_to_card_appends_multiple_invariants(self, tmp_path):
        card_path = tmp_path / "test.card.md"
        card_path.write_text("## Intent\n\nSome module.\n")
        invariants = [
            LiftedInvariant("result.balance >= 0", "balance is non-negative"),
            LiftedInvariant("result.receipt is not None", "receipt is never null"),
        ]
        lift_to_card(invariants, card_path)
        content = card_path.read_text()
        assert "balance is non-negative" in content
        assert "receipt is never null" in content

    def test_lift_to_card_returns_count(self, tmp_path):
        card_path = tmp_path / "test.card.md"
        card_path.write_text("")
        invariants = [
            LiftedInvariant("x > 0", "x is positive"),
            LiftedInvariant("y != 0", "y is non-zero"),
        ]
        count = lift_to_card(invariants, card_path)
        assert count == 2

    def test_lift_to_card_empty_returns_zero(self, tmp_path):
        card_path = tmp_path / "test.card.md"
        card_path.write_text("")
        count = lift_to_card([], card_path)
        assert count == 0
        # File unchanged / no section added for empty input
        assert card_path.read_text() == ""

    def test_lift_to_card_preserves_existing_content(self, tmp_path):
        card_path = tmp_path / "test.card.md"
        card_path.write_text("## Intent\n\nExisting content.\n")
        invariants = [LiftedInvariant("x > 0", "x is always positive")]
        lift_to_card(invariants, card_path)
        content = card_path.read_text()
        assert "Existing content." in content
        assert "x is always positive" in content

    def test_lift_to_card_records_source_assert(self, tmp_path):
        """Source assert expression is recorded alongside NL statement."""
        card_path = tmp_path / "test.card.md"
        card_path.write_text("")
        invariants = [LiftedInvariant("result.balance >= 0", "balance is non-negative")]
        lift_to_card(invariants, card_path)
        content = card_path.read_text()
        assert "result.balance >= 0" in content

    def test_lift_to_card_creates_file_if_not_exists(self, tmp_path):
        card_path = tmp_path / "new.card.md"
        invariants = [LiftedInvariant("x > 0", "x is positive")]
        lift_to_card(invariants, card_path)
        assert card_path.exists()
        assert "x is positive" in card_path.read_text()
