"""Tests for contract_library.py — domain-knowledge few-shot example library.

TDD: tests written first before implementation.

References:
- [REF-NEW-08] NL2Contract: few-shot contract examples pattern
- [REF-NEW-12] PropertyGPT: RAG over verified contracts
"""

import pytest

from nightjar.contract_library import DOMAIN_PATTERNS, retrieve_examples


class TestDomainPatterns:
    """Tests for the DOMAIN_PATTERNS seed data."""

    def test_patterns_is_nonempty_list(self):
        assert isinstance(DOMAIN_PATTERNS, list)
        assert len(DOMAIN_PATTERNS) > 0

    def test_patterns_have_required_keys(self):
        for p in DOMAIN_PATTERNS:
            assert "name" in p, f"Pattern missing 'name' key: {p}"
            assert "keywords" in p, f"Pattern missing 'keywords' key: {p}"
            assert "examples" in p, f"Pattern missing 'examples' key: {p}"

    def test_at_least_12_patterns(self):
        assert len(DOMAIN_PATTERNS) >= 12

    def test_examples_are_nonempty_strings(self):
        for p in DOMAIN_PATTERNS:
            for ex in p["examples"]:
                assert isinstance(ex, str), f"Pattern {p['name']} example is not a str: {ex!r}"
                assert len(ex) > 0, f"Pattern {p['name']} has empty example string"

    def test_no_assert_prefix_in_examples(self):
        """Examples must be expressions, not assert statements."""
        for p in DOMAIN_PATTERNS:
            for ex in p["examples"]:
                assert not ex.strip().startswith("assert "), (
                    f"Pattern {p['name']!r} example has 'assert ' prefix: {ex!r}"
                )

    def test_keywords_are_nonempty_lists(self):
        for p in DOMAIN_PATTERNS:
            assert isinstance(p["keywords"], list), f"Pattern {p['name']} keywords not a list"
            assert len(p["keywords"]) > 0, f"Pattern {p['name']} has no keywords"


class TestRetrieveExamples:
    """Tests for the retrieve_examples() function."""

    def test_returns_empty_on_no_match(self):
        result = retrieve_examples("frobnicate_widget", ["foo", "bar"], top_k=3)
        assert result == []

    def test_matches_age_via_param_name(self):
        result = retrieve_examples("validate", ["age"], top_k=5)
        assert "age >= 0" in result
        assert "age <= 150" in result

    def test_matches_price_via_function_name(self):
        result = retrieve_examples("calculate_price", [], top_k=3)
        assert len(result) > 0
        assert any(">= 0" in ex for ex in result), f"Expected '>= 0' in results: {result}"

    def test_matches_email_via_param_name(self):
        result = retrieve_examples("check_input", ["email"], top_k=3)
        assert len(result) > 0
        assert any("@" in ex for ex in result), f"Expected '@' check in results: {result}"

    def test_matches_password_via_param_name(self):
        result = retrieve_examples("authenticate_user", ["password"], top_k=3)
        assert len(result) > 0
        assert any(">= 8" in ex for ex in result), f"Expected '>= 8' in results: {result}"

    def test_top_k_limits_results(self):
        # Many params match multiple patterns, but top_k caps output
        result = retrieve_examples("process", ["age", "price", "discount", "score"], top_k=2)
        assert len(result) <= 2

    def test_returns_list_of_strings(self):
        result = retrieve_examples("validate_age", ["age"], top_k=3)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_matches_url_via_param_name(self):
        result = retrieve_examples("fetch_resource", ["url"], top_k=3)
        assert len(result) > 0
        assert any("http" in ex for ex in result), f"Expected 'http' in results: {result}"

    def test_matches_timeout_via_function_name(self):
        result = retrieve_examples("set_timeout", [], top_k=3)
        assert len(result) > 0
        assert any("> 0" in ex for ex in result), f"Expected '> 0' in results: {result}"

    def test_matches_score_via_param_name(self):
        result = retrieve_examples("assign_grade", ["score"], top_k=3)
        assert len(result) > 0
        assert any("score" in ex for ex in result), f"Expected 'score' in results: {result}"

    def test_returns_empty_list_not_none(self):
        """Must return [] not None on no match."""
        result = retrieve_examples("xyz", [], top_k=3)
        assert result is not None
        assert result == []

    def test_top_k_zero_returns_empty(self):
        result = retrieve_examples("validate_age", ["age"], top_k=0)
        assert result == []
