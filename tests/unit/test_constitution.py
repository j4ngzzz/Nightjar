"""Tests for constitution.card.md inheritance.

Validates that project-level invariants from constitution.card.md are
merged into every module's invariant set during parsing, per [REF-T25]
GitHub Spec Kit constitution pattern.

References:
- [REF-T25] GitHub Spec Kit (constitution.md for project-level invariants)
- [REF-C01] Tiered invariants (example/property/formal)
"""

import pytest
from pathlib import Path

from contractd.parser import parse_card_spec, load_constitution, parse_with_constitution
from contractd.types import CardSpec, InvariantTier

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadConstitution:
    """Test loading and parsing constitution.card.md."""

    def test_load_returns_invariants(self):
        """Constitution file should return a list of global invariants."""
        invariants = load_constitution(str(FIXTURES / "constitution.card.md"))
        assert len(invariants) == 3

    def test_load_parses_invariant_ids(self):
        """Each global invariant should have its ID preserved."""
        invariants = load_constitution(str(FIXTURES / "constitution.card.md"))
        ids = [inv.id for inv in invariants]
        assert "GLOBAL-001" in ids
        assert "GLOBAL-002" in ids
        assert "GLOBAL-003" in ids

    def test_load_parses_tiers(self):
        """Global invariants should have correct tiers."""
        invariants = load_constitution(str(FIXTURES / "constitution.card.md"))
        tier_map = {inv.id: inv.tier for inv in invariants}
        assert tier_map["GLOBAL-001"] == InvariantTier.PROPERTY
        assert tier_map["GLOBAL-002"] == InvariantTier.FORMAL
        assert tier_map["GLOBAL-003"] == InvariantTier.PROPERTY

    def test_load_parses_statements(self):
        """Global invariants should have non-empty statements."""
        invariants = load_constitution(str(FIXTURES / "constitution.card.md"))
        for inv in invariants:
            assert inv.statement, f"Invariant {inv.id} has empty statement"

    def test_load_nonexistent_returns_empty(self):
        """Missing constitution file should return empty list, not error."""
        invariants = load_constitution(str(FIXTURES / "nonexistent.card.md"))
        assert invariants == []


class TestParseWithConstitution:
    """Test that constitution invariants merge into module specs."""

    def test_module_gets_global_invariants(self):
        """Parsing a module with a constitution should include global invariants."""
        spec = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        ids = [inv.id for inv in spec.invariants]
        # Module's own invariant
        assert "INV-001" in ids
        # Global invariants inherited
        assert "GLOBAL-001" in ids
        assert "GLOBAL-002" in ids
        assert "GLOBAL-003" in ids

    def test_module_invariants_come_first(self):
        """Module-specific invariants should appear before global ones."""
        spec = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        # The module's INV-001 should come before any GLOBAL-* invariants
        ids = [inv.id for inv in spec.invariants]
        inv001_idx = ids.index("INV-001")
        global001_idx = ids.index("GLOBAL-001")
        assert inv001_idx < global001_idx

    def test_no_duplicate_invariants(self):
        """Each invariant ID should appear exactly once."""
        spec = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        ids = [inv.id for inv in spec.invariants]
        assert len(ids) == len(set(ids)), f"Duplicate invariant IDs: {ids}"

    def test_total_invariant_count(self):
        """Module should have its own + all constitution invariants."""
        spec = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        # minimal.card.md has 1 invariant, constitution has 3
        assert len(spec.invariants) == 4

    def test_payment_module_gets_globals(self):
        """Payment module should also inherit constitution invariants."""
        spec = parse_with_constitution(
            str(FIXTURES / "payment.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        ids = [inv.id for inv in spec.invariants]
        # Payment has 5 own invariants + 3 global = 8 total
        assert len(spec.invariants) == 8
        assert "GLOBAL-001" in ids
        assert "INV-005" in ids  # payment's own

    def test_no_constitution_returns_module_only(self):
        """If constitution path doesn't exist, return module invariants only."""
        spec = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "nonexistent_constitution.card.md"),
        )
        assert len(spec.invariants) == 1
        assert spec.invariants[0].id == "INV-001"

    def test_other_spec_fields_unchanged(self):
        """Constitution should only affect invariants, not other fields."""
        spec_with = parse_with_constitution(
            str(FIXTURES / "minimal.card.md"),
            str(FIXTURES / "constitution.card.md"),
        )
        spec_without = parse_card_spec(str(FIXTURES / "minimal.card.md"))
        assert spec_with.id == spec_without.id
        assert spec_with.title == spec_without.title
        assert spec_with.contract == spec_without.contract
        assert spec_with.module == spec_without.module
        assert spec_with.intent == spec_without.intent
