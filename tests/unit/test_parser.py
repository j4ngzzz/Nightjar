"""Tests for .card.md parser.

Tests the parse_card_spec function against fixtures from ARCHITECTURE.md Section 2.
Validates YAML frontmatter parsing, Markdown body extraction, and error handling.

References:
- [REF-T24] Agent Skills Open Standard (YAML frontmatter + Markdown body)
- [REF-T25] GitHub Spec Kit (Given/When/Then conventions)
- [REF-C01] Tiered invariants (example/property/formal)
"""

import pytest
from pathlib import Path

from contractd.parser import parse_card_spec
from contractd.types import CardSpec, InvariantTier


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestParseMinimalSpec:
    """Parse the 30-line minimal .card.md from ARCHITECTURE.md."""

    def test_returns_card_spec(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert isinstance(spec, CardSpec)

    def test_parses_id(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert spec.id == "user-auth"

    def test_parses_card_version(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert spec.card_version == "1.0"

    def test_parses_title(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert spec.title == "User Authentication"

    def test_parses_status(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert spec.status == "draft"

    def test_parses_invariants(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert len(spec.invariants) >= 1
        assert spec.invariants[0].id == "INV-001"
        assert spec.invariants[0].tier == InvariantTier.PROPERTY
        assert "valid token" in spec.invariants[0].statement

    def test_parses_module_boundary(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert "login()" in spec.module.owns
        assert "postgres" in spec.module.depends_on

    def test_parses_contract_inputs(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert len(spec.contract.inputs) == 2
        names = [i.name for i in spec.contract.inputs]
        assert "email" in names
        assert "password" in names

    def test_parses_contract_outputs(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert len(spec.contract.outputs) == 1
        assert spec.contract.outputs[0].name == "session_token"

    def test_extracts_intent(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert "log in" in spec.intent.lower()

    def test_extracts_acceptance_criteria(self):
        spec = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert "Given" in spec.acceptance_criteria or "login" in spec.acceptance_criteria


class TestParseFullSpec:
    """Parse the full payment .card.md with all features."""

    def test_parses_id(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert spec.id == "payment-processing"

    def test_parses_multiple_inputs(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert len(spec.contract.inputs) >= 3
        names = [i.name for i in spec.contract.inputs]
        assert "amount" in names
        assert "currency" in names
        assert "user_id" in names

    def test_parses_input_constraints(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        amount_input = next(i for i in spec.contract.inputs if i.name == "amount")
        assert "amount > 0" in amount_input.constraints

    def test_parses_output_schema(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert len(spec.contract.outputs) >= 1
        result = spec.contract.outputs[0]
        assert result.name == "PaymentResult"
        assert "transaction_id" in result.schema

    def test_parses_errors(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert "InvalidAmountError" in spec.contract.errors
        assert "PaymentGatewayError" in spec.contract.errors

    def test_parses_events_emitted(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert "payment.processed" in spec.contract.events_emitted

    def test_parses_mixed_tier_invariants(self):
        """[REF-C01] Tiered invariants — at least one of each tier."""
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert len(spec.invariants) >= 3
        tiers = {inv.tier for inv in spec.invariants}
        assert InvariantTier.EXAMPLE in tiers
        assert InvariantTier.PROPERTY in tiers
        assert InvariantTier.FORMAL in tiers

    def test_parses_module_excludes(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert len(spec.module.excludes) >= 1
        assert any("Subscription" in e for e in spec.module.excludes)

    def test_parses_constraints(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert "performance" in spec.constraints
        assert "security" in spec.constraints

    def test_extracts_functional_requirements(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        assert "FR-001" in spec.functional_requirements

    def test_invariant_rationale(self):
        spec = parse_card_spec(str(FIXTURES / "payment.card.md"))
        inv = next(i for i in spec.invariants if i.id == "INV-002")
        assert "balance" in inv.rationale.lower() or "integrity" in inv.rationale.lower()


class TestParseErrors:
    """Error handling for malformed or incomplete specs."""

    def test_invalid_yaml_raises_value_error(self):
        """Malformed YAML frontmatter should raise clear error."""
        with pytest.raises(ValueError, match="Invalid .card.md"):
            parse_card_spec(str(FIXTURES / "invalid.card.md"))

    def test_missing_required_fields_raises(self):
        """Missing card-version or id should raise."""
        with pytest.raises(ValueError, match="required"):
            parse_card_spec(str(FIXTURES / "missing_fields.card.md"))

    def test_nonexistent_file_raises(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_card_spec("/nonexistent/path/spec.card.md")

    def test_no_frontmatter_delimiters_raises(self, tmp_path):
        """File without --- delimiters should raise."""
        bad_file = tmp_path / "no_delimiters.card.md"
        bad_file.write_text("Just some markdown without frontmatter")
        with pytest.raises(ValueError, match="Invalid .card.md"):
            parse_card_spec(str(bad_file))

    def test_empty_frontmatter_raises(self, tmp_path):
        """Empty frontmatter should raise for missing required fields."""
        bad_file = tmp_path / "empty_front.card.md"
        bad_file.write_text("---\n---\n## Intent\nSome text")
        with pytest.raises(ValueError, match="required"):
            parse_card_spec(str(bad_file))


class TestParseFromString:
    """Test parsing from string content via tmp_path fixtures."""

    def test_minimal_inline_spec(self, tmp_path):
        """A minimal valid spec with just required fields + one invariant."""
        content = """---
card-version: "1.0"
id: test-module
title: Test Module
status: draft
module:
  owns: [do_thing()]
contract:
  inputs:
    - name: x
      type: integer
invariants:
  - id: INV-001
    tier: example
    statement: "do_thing(1) returns 2"
---

## Intent

A test module.
"""
        spec_file = tmp_path / "test.card.md"
        spec_file.write_text(content)
        spec = parse_card_spec(str(spec_file))
        assert spec.id == "test-module"
        assert spec.invariants[0].tier == InvariantTier.EXAMPLE

    def test_spec_with_no_markdown_body(self, tmp_path):
        """A spec with only frontmatter and no markdown body should still parse."""
        content = """---
card-version: "1.0"
id: bare-spec
title: Bare Spec
status: draft
module:
  owns: [func()]
contract:
  inputs: []
invariants: []
---
"""
        spec_file = tmp_path / "bare.card.md"
        spec_file.write_text(content)
        spec = parse_card_spec(str(spec_file))
        assert spec.id == "bare-spec"
        assert spec.intent == ""
