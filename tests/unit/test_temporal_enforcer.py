"""Tests for temporal fact supersession in invariant store (U2.4).

Validates the Supermemory temporal fact model:
- Static + dynamic layers for invariant lifecycle
- Confidence decay without new observations
- Supersession when behavior legitimately evolves

References:
- Supermemory temporal fact model — static+dynamic layers, conflict resolution (MIT)
  https://github.com/supermemoryai/supermemory
- [REF-T10] icontract — Python Design by Contract
"""

from __future__ import annotations

import time

import pytest

from immune.enforcer import InvariantStore, TemporalInvariant


# ---------------------------------------------------------------------------
# TemporalInvariant data model
# ---------------------------------------------------------------------------


class TestTemporalInvariant:
    def test_stores_expression(self):
        """TemporalInvariant holds the invariant expression."""
        inv = TemporalInvariant(expression="x > 0")
        assert inv.expression == "x > 0"

    def test_has_timestamp(self):
        """TemporalInvariant records creation timestamp."""
        before = time.time()
        inv = TemporalInvariant(expression="x > 0")
        after = time.time()
        assert before <= inv.timestamp <= after

    def test_default_observation_count_is_one(self):
        """Freshly created invariant has observation_count = 1."""
        inv = TemporalInvariant(expression="x > 0")
        assert inv.observation_count == 1

    def test_default_confidence_is_one(self):
        """Default confidence is 1.0 (fully trusted at creation)."""
        inv = TemporalInvariant(expression="x > 0")
        assert inv.confidence == 1.0

    def test_not_superseded_by_default(self):
        """Newly created invariants are not superseded."""
        inv = TemporalInvariant(expression="x > 0")
        assert inv.superseded_by is None

    def test_custom_half_life(self):
        """half_life is configurable."""
        inv = TemporalInvariant(expression="x > 0", half_life=3600.0)
        assert inv.half_life == 3600.0


# ---------------------------------------------------------------------------
# InvariantStore — add_observation
# ---------------------------------------------------------------------------


class TestInvariantStoreAddObservation:
    def test_add_creates_invariant(self):
        """add_observation creates and returns a TemporalInvariant."""
        store = InvariantStore()
        inv = store.add_observation("x > 0")
        assert isinstance(inv, TemporalInvariant)
        assert inv.expression == "x > 0"

    def test_add_same_expression_increments_count(self):
        """Observing the same expression twice increments observation_count."""
        store = InvariantStore()
        store.add_observation("x > 0")
        inv = store.add_observation("x > 0")
        assert inv.observation_count == 2

    def test_observation_reinforces_timestamp(self):
        """Adding a newer observation updates the stored timestamp."""
        store = InvariantStore()
        past = time.time() - 3600.0
        store.add_observation("x > 0", timestamp=past)
        now = time.time()
        inv = store.add_observation("x > 0", timestamp=now)
        assert inv.timestamp == pytest.approx(now, abs=1.0)

    def test_add_stores_explanation(self):
        """explanation is stored on the invariant."""
        store = InvariantStore()
        inv = store.add_observation("x > 0", explanation="Must be positive")
        assert inv.explanation == "Must be positive"

    def test_add_uses_current_time_by_default(self):
        """When no timestamp provided, defaults to now."""
        before = time.time()
        store = InvariantStore()
        inv = store.add_observation("x > 0")
        after = time.time()
        assert before <= inv.timestamp <= after


# ---------------------------------------------------------------------------
# InvariantStore — supersession
# ---------------------------------------------------------------------------


class TestInvariantStoreSupersession:
    def test_new_observation_supersedes_old_invariant(self):
        """New runtime observation marks old invariant as superseded. [Supermemory pattern]

        When system behavior legitimately evolves, old invariants should be
        superseded rather than silently enforced — preventing stale contracts.
        """
        store = InvariantStore()
        store.add_observation("x > 0", explanation="Initial observation")
        store.supersede("x > 0", "x >= 0", explanation="Behavior relaxed to allow zero")

        # Old invariant is marked as superseded
        old = store._invariants.get("x > 0")
        assert old is not None
        assert old.superseded_by == "x >= 0"

    def test_superseded_invariant_excluded_from_active(self):
        """Superseded invariants are absent from get_active_invariants()."""
        store = InvariantStore()
        store.add_observation("x > 0")
        store.supersede("x > 0", "x >= 0")

        active_exprs = [i.expression for i in store.get_active_invariants()]
        assert "x > 0" not in active_exprs
        assert "x >= 0" in active_exprs

    def test_supersede_returns_new_invariant(self):
        """supersede() returns the newly created TemporalInvariant."""
        store = InvariantStore()
        store.add_observation("x > 0")
        new_inv = store.supersede("x > 0", "x >= 0")
        assert new_inv.expression == "x >= 0"
        assert new_inv.superseded_by is None

    def test_supersede_nonexistent_old_creates_new_only(self):
        """Superseding a non-existent invariant just creates the new one."""
        store = InvariantStore()
        new_inv = store.supersede("never_seen", "new_expr")
        assert new_inv.expression == "new_expr"
        active = store.get_active_invariants()
        assert any(i.expression == "new_expr" for i in active)


# ---------------------------------------------------------------------------
# InvariantStore — confidence decay
# ---------------------------------------------------------------------------


class TestInvariantStoreConfidenceDecay:
    def test_confidence_is_one_immediately_after_observation(self):
        """Confidence is 1.0 immediately after observation (no elapsed time)."""
        store = InvariantStore()
        now = time.time()
        store.add_observation("x > 0", timestamp=now)
        confidence = store.get_confidence("x > 0", current_time=now)
        assert confidence == pytest.approx(1.0)

    def test_confidence_decays_without_new_observations(self):
        """Confidence halves after one half_life without new observations. [Supermemory pattern]

        The Supermemory model uses exponential decay for dynamic-layer facts:
            confidence(t) = base * 0.5^(elapsed / half_life)
        """
        store = InvariantStore()
        half_life = 100.0
        past_time = time.time() - half_life  # exactly one half-life ago
        inv = store.add_observation("x > 0", timestamp=past_time)
        inv.half_life = half_life  # set for this test

        current = store.get_confidence("x > 0", current_time=time.time())
        assert 0.45 < current < 0.55  # ~0.5 ± tolerance

    def test_confidence_decays_to_quarter_after_two_half_lives(self):
        """Confidence is ~0.25 after two half-lives."""
        store = InvariantStore()
        half_life = 50.0
        past_time = time.time() - 2 * half_life
        inv = store.add_observation("y > 0", timestamp=past_time)
        inv.half_life = half_life

        current = store.get_confidence("y > 0", current_time=time.time())
        assert 0.20 < current < 0.30  # ~0.25 ± tolerance

    def test_get_confidence_returns_zero_for_unknown_expression(self):
        """Querying an unknown expression returns 0.0."""
        store = InvariantStore()
        assert store.get_confidence("nonexistent") == 0.0


# ---------------------------------------------------------------------------
# InvariantStore — get_active_invariants
# ---------------------------------------------------------------------------


class TestInvariantStoreActive:
    def test_active_excludes_superseded(self):
        """Only non-superseded invariants appear in get_active_invariants()."""
        store = InvariantStore()
        store.add_observation("a > 0")
        store.add_observation("b > 0")
        store.supersede("a > 0", "a >= 0")

        active_exprs = [i.expression for i in store.get_active_invariants()]
        assert "b > 0" in active_exprs
        assert "a >= 0" in active_exprs
        assert "a > 0" not in active_exprs

    def test_active_empty_on_new_store(self):
        """Fresh store has no active invariants."""
        store = InvariantStore()
        assert store.get_active_invariants() == []

    def test_multiple_active_invariants(self):
        """Multiple non-superseded invariants all appear as active."""
        store = InvariantStore()
        for expr in ["x > 0", "y >= 0", "z != 0"]:
            store.add_observation(expr)
        active = store.get_active_invariants()
        assert len(active) == 3
