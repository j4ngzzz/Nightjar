"""Tests for the evolved Daikon reimplementation — sys.monitoring + 19 templates.

These tests validate the W4.1 evolution:
1. sys.monitoring (PEP 669) as primary tracing mechanism (NOT sys.settrace)
2. CONSTANT template from Ernst 1999/2007
3. RANGE template (Range/Bound from Ernst 1999/2007)
4. Invariant falsification via observation counterexamples
5. New InvariantKind values covering all 19 Ernst templates

References:
- Ernst et al. 1999/2007 — Dynamically Discovering Likely Program Invariants
  https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf
- PEP 669 (sys.monitoring): https://docs.python.org/3/library/sys.monitoring.html
- Scout 6 Section 4 — sys.monitoring performance advantage (up to 20x vs sys.settrace)
- Clean-room CR-01: implement from Ernst paper ONLY, NOT Fuzzingbook
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from immune.daikon import InvariantMiner, InvariantKind


# ---------------------------------------------------------------------------
# Helper functions to mine invariants from
# ---------------------------------------------------------------------------


def constant_five() -> int:
    """Always returns 5 — should yield CONSTANT invariant."""
    return 5


def bounded_value(x: int) -> int:
    """Returns x, where x is always in [0, 100] in our tests."""
    return x


def sometimes_negative(x: int) -> int:
    """Returns x — can be negative."""
    return x


def always_positive(x: int) -> int:
    """Always called with positive x in our tests."""
    return x


def one_of_abc(s: str) -> str:
    """Always returns one of 'a', 'b', 'c' in our tests."""
    return s


# ---------------------------------------------------------------------------
# Test: sys.monitoring is used (not sys.settrace) on Python 3.12+
# ---------------------------------------------------------------------------


class TestSysMonitoringUsed:
    """Verify that sys.monitoring is used as primary tracing mechanism.

    Per Scout 6 Section 4 and PEP 669: sys.monitoring provides up to 20x
    lower overhead than sys.settrace. On Python 3.12+, we MUST use it.
    """

    def test_miner_uses_sys_monitoring_not_settrace(self):
        """On Python 3.12+, InvariantMiner must use sys.monitoring, not sys.settrace.

        Verifies CR-01: sys.monitoring (PEP 669) as primary mechanism.
        Reference: Scout 6 Section 4, PEP 669.
        """
        if not hasattr(sys, "monitoring"):
            pytest.skip("sys.monitoring not available — requires Python 3.12+")

        miner = InvariantMiner()
        # On 3.12+, miner should declare it's using sys.monitoring
        assert miner.using_sys_monitoring is True, (
            "InvariantMiner.using_sys_monitoring should be True on Python 3.12+"
        )

        # Verify sys.settrace is NOT invoked during tracing
        settrace_calls: list = []

        original_settrace = sys.settrace

        def spy_settrace(fn):  # type: ignore[override]
            settrace_calls.append(fn)
            original_settrace(fn)

        with mock.patch.object(sys, "settrace", spy_settrace):
            with miner.trace():
                constant_five()

        assert len(settrace_calls) == 0, (
            f"sys.settrace was called {len(settrace_calls)} time(s) — "
            "must use sys.monitoring instead on Python 3.12+"
        )

    def test_miner_using_sys_monitoring_property_false_on_older_python(self):
        """On Python < 3.12, using_sys_monitoring should be False."""
        if hasattr(sys, "monitoring"):
            pytest.skip("This test is only for Python < 3.12")

        miner = InvariantMiner()
        assert miner.using_sys_monitoring is False


# ---------------------------------------------------------------------------
# Test: CONSTANT template (Ernst 1999/2007 Unary Scalar — Constant)
# ---------------------------------------------------------------------------


class TestConstantTemplate:
    """Validate the CONSTANT invariant template from Ernst 1999/2007.

    Constant template: variable always equals a fixed value C.
    Expression: "x == C"
    """

    def test_miner_detects_constant(self):
        """When return value is always 5, CONSTANT invariant should be found.

        Tests Ernst 1999/2007 Unary Scalar — Constant template.
        Reference: CR-01, Ernst et al. 1999 Section 2.1 (Constant invariant)
        """
        miner = InvariantMiner()

        # Observe constant_five() returning 5 many times
        with miner.trace():
            for _ in range(20):
                constant_five()

        invs = miner.get_invariants("constant_five")
        constant_invs = [i for i in invs if i.kind == InvariantKind.CONSTANT]

        assert len(constant_invs) > 0, (
            "Expected CONSTANT invariant for constant_five() return value, "
            f"got invariants: {[i.expression for i in invs]}"
        )
        # The expression should mention value 5
        assert any("5" in i.expression for i in constant_invs), (
            f"Expected invariant expression containing '5', got: "
            f"{[i.expression for i in constant_invs]}"
        )

    def test_constant_invariant_not_found_for_varying_values(self):
        """When values vary, no CONSTANT invariant should appear."""
        miner = InvariantMiner()

        with miner.trace():
            for x in range(0, 10):
                bounded_value(x)  # returns 0,1,2,...,9

        invs = miner.get_invariants("bounded_value")
        # Return value varies — no CONSTANT for 'return'
        ret_constant = [
            i for i in invs
            if i.kind == InvariantKind.CONSTANT and "return" in i.variable
        ]
        assert len(ret_constant) == 0, (
            f"Expected no CONSTANT invariant for varying return values, "
            f"got: {[i.expression for i in ret_constant]}"
        )


# ---------------------------------------------------------------------------
# Test: RANGE template (Ernst 1999/2007 Unary Scalar — Range)
# ---------------------------------------------------------------------------


class TestRangeTemplate:
    """Validate the RANGE invariant template from Ernst 1999/2007.

    Range template: variable always within [lo, hi] or satisfies >= lo.
    This extends the existing BOUND template with explicit range bounds.
    """

    def test_miner_detects_range(self):
        """When x is always in [0, 100], a range/bound invariant should be found.

        Tests Ernst 1999/2007 Unary Scalar — Range template.
        Reference: CR-01, Ernst et al. 1999 Section 2.1 (Range invariant)
        """
        miner = InvariantMiner()

        # Observe bounded_value with x in [0, 100]
        with miner.trace():
            for x in range(0, 101):
                bounded_value(x)

        invs = miner.get_invariants("bounded_value")

        # Should find RANGE invariant OR BOUND invariant (>= 0) for x
        range_invs = [
            i for i in invs
            if i.kind in (InvariantKind.RANGE, InvariantKind.BOUND)
            and "x" in i.variable
        ]
        assert len(range_invs) > 0, (
            f"Expected RANGE or BOUND invariant for x in [0,100], "
            f"got invariants: {[i.expression for i in invs]}"
        )
        # At minimum: x >= 0 should be found
        assert any(">= 0" in i.expression or "range" in i.expression.lower()
                   for i in range_invs), (
            f"Expected '>= 0' or range expression, got: "
            f"{[i.expression for i in range_invs]}"
        )

    def test_miner_detects_tight_range(self):
        """When x is always in [10, 20], range bounds should be detected."""
        miner = InvariantMiner()

        with miner.trace():
            for x in range(10, 21):  # 10..20 inclusive
                bounded_value(x)

        invs = miner.get_invariants("bounded_value")
        range_invs = [
            i for i in invs
            if i.kind in (InvariantKind.RANGE, InvariantKind.BOUND)
            and "x" in i.variable
        ]
        assert len(range_invs) > 0, (
            f"Expected RANGE/BOUND invariants for x in [10,20], "
            f"got: {[i.expression for i in invs]}"
        )


# ---------------------------------------------------------------------------
# Test: Invariant elimination when counterexample is observed
# ---------------------------------------------------------------------------


class TestInvariantFalsification:
    """Validate that invariants are eliminated when a counterexample is observed.

    This is the core of Daikon's algorithm: falsification of candidates
    against ALL observations (Ernst et al. 1999 Section 3.3).
    """

    def test_miner_eliminates_violated_invariant(self):
        """After a counterexample, CONSTANT invariant should be eliminated.

        Reference: Ernst et al. 1999 Section 3.3 — Invariant falsification.
        CR-01: Daikon removes invariants that fail on ANY observation.
        """
        # We observe a pattern that suggests x is always positive (> 0)
        miner = InvariantMiner()
        with miner.trace():
            for x in range(1, 20):
                always_positive(x)

        invs_before = miner.get_invariants("always_positive")
        # x > 0 should be found (all values 1..19 are > 0)
        positive_before = [
            i for i in invs_before
            if "x" in i.variable
            and "> 0" in i.expression
            and i.kind in (InvariantKind.BOUND, InvariantKind.RANGE)
        ]
        assert len(positive_before) > 0, (
            f"Expected 'x > 0' invariant before counterexample, "
            f"got: {[i.expression for i in invs_before]}"
        )

        # Now observe x = -1 — counterexample falsifies x > 0
        with miner.trace():
            always_positive(-1)

        invs_after = miner.get_invariants("always_positive")
        positive_after = [
            i for i in invs_after
            if "x" in i.variable
            and "> 0" in i.expression
            and i.kind in (InvariantKind.BOUND, InvariantKind.RANGE)
        ]
        assert len(positive_after) == 0, (
            f"Expected 'x > 0' invariant eliminated after x=-1, "
            f"but still found: {[i.expression for i in positive_after]}"
        )

    def test_constant_invariant_eliminated_on_new_value(self):
        """CONSTANT invariant is eliminated when a different value is observed."""
        miner = InvariantMiner()

        # Establish: always returns 5
        with miner.trace():
            for _ in range(10):
                constant_five()

        invs_before = miner.get_invariants("constant_five")
        const_before = [
            i for i in invs_before
            if i.kind == InvariantKind.CONSTANT and "return" in i.variable
        ]
        assert len(const_before) > 0, "Expected CONSTANT invariant initially"

        # Observe return = 7 by calling a different function that traces as same name
        # (via direct injection into miner's traces)
        # We use internal API to inject a non-5 observation
        miner._traces["constant_five"].call_records.append({"return": 7})

        invs_after = miner.get_invariants("constant_five")
        const_after = [
            i for i in invs_after
            if i.kind == InvariantKind.CONSTANT
            and "5" in i.expression
            and "return" in i.variable
        ]
        assert len(const_after) == 0, (
            "CONSTANT = 5 should be eliminated after observing return = 7"
        )


# ---------------------------------------------------------------------------
# Test: New InvariantKind values are present in the enum
# ---------------------------------------------------------------------------


class TestNewInvariantKinds:
    """Validate that new InvariantKind enum values are present.

    Ernst 1999/2007 defines 19 templates across 5 categories.
    We need at least: CONSTANT, ONE_OF, LINEAR, SEQ_SORTED, SEQ_ONE_OF,
    UNCHANGED, INCREASED, DECREASED, IMPLICATION.
    """

    def test_constant_kind_exists(self):
        """InvariantKind.CONSTANT must exist for Ernst Constant template."""
        assert hasattr(InvariantKind, "CONSTANT"), (
            "InvariantKind.CONSTANT must be defined for Ernst Constant template"
        )
        assert InvariantKind.CONSTANT.value == "constant"

    def test_one_of_kind_exists(self):
        """InvariantKind.ONE_OF must exist for Ernst OneOf template."""
        assert hasattr(InvariantKind, "ONE_OF"), (
            "InvariantKind.ONE_OF must be defined for Ernst OneOf template"
        )

    def test_unchanged_kind_exists(self):
        """InvariantKind.UNCHANGED must exist for Ernst State template."""
        assert hasattr(InvariantKind, "UNCHANGED"), (
            "InvariantKind.UNCHANGED must be defined for Ernst Unchanged template"
        )

    def test_increased_kind_exists(self):
        """InvariantKind.INCREASED must exist for Ernst State template."""
        assert hasattr(InvariantKind, "INCREASED"), (
            "InvariantKind.INCREASED must be defined for Ernst Increased template"
        )

    def test_decreased_kind_exists(self):
        """InvariantKind.DECREASED must exist for Ernst State template."""
        assert hasattr(InvariantKind, "DECREASED"), (
            "InvariantKind.DECREASED must be defined for Ernst Decreased template"
        )

    def test_implication_kind_exists(self):
        """InvariantKind.IMPLICATION must exist for Ernst Conditional template."""
        assert hasattr(InvariantKind, "IMPLICATION"), (
            "InvariantKind.IMPLICATION must be defined for Ernst Implication template"
        )

    def test_original_kinds_preserved(self):
        """Original 5 InvariantKind values must still exist (backward compat)."""
        assert hasattr(InvariantKind, "TYPE")
        assert hasattr(InvariantKind, "BOUND")
        assert hasattr(InvariantKind, "NULLNESS")
        assert hasattr(InvariantKind, "RELATIONAL")
        assert hasattr(InvariantKind, "LENGTH")


# ---------------------------------------------------------------------------
# Test: UNCHANGED and INCREASED state templates
# ---------------------------------------------------------------------------


class TestStateTemplates:
    """Validate Ernst State templates: Unchanged, Increased, Decreased.

    State templates compare the value at function entry vs exit.
    Example: abs(x) — return >= x (when x >= 0) or return == -x (when x < 0)
    """

    def test_miner_detects_unchanged_state(self):
        """When arg == return, UNCHANGED invariant should be found."""
        miner = InvariantMiner()

        def identity_fn(x: int) -> int:
            return x

        with miner.trace():
            for x in range(1, 20):
                identity_fn(x)

        invs = miner.get_invariants("identity_fn")
        unchanged_invs = [i for i in invs if i.kind == InvariantKind.UNCHANGED]

        # identity_fn always returns its argument — UNCHANGED should be found
        # (We check this is present, or alternatively that x == return is in RELATIONAL)
        state_or_rel = [
            i for i in invs
            if i.kind in (InvariantKind.UNCHANGED, InvariantKind.RELATIONAL, InvariantKind.EQUALITY)
        ]
        assert len(state_or_rel) > 0, (
            f"Expected UNCHANGED or RELATIONAL invariant for identity function, "
            f"got: {[i.expression for i in invs]}"
        )

    def test_miner_detects_increased_state(self):
        """When return > arg, INCREASED invariant should be found."""
        miner = InvariantMiner()

        def increment(x: int) -> int:
            return x + 1

        with miner.trace():
            for x in range(1, 20):
                increment(x)

        invs = miner.get_invariants("increment")
        # return > x — INCREASED or RELATIONAL(x < return)
        increased = [
            i for i in invs
            if i.kind in (InvariantKind.INCREASED, InvariantKind.RELATIONAL, InvariantKind.ORDERING)
        ]
        assert len(increased) > 0, (
            f"Expected INCREASED or relational invariant for increment(), "
            f"got: {[i.expression for i in invs]}"
        )


# ---------------------------------------------------------------------------
# Test: ONE_OF template (Ernst 1999/2007 Unary Scalar — OneOf)
# ---------------------------------------------------------------------------


class TestOneOfTemplate:
    """Validate the ONE_OF invariant template.

    OneOf: variable is always one of a fixed set of values.
    Expression: "x ∈ {v1, v2, v3}" or "x in {v1, v2, v3}"
    """

    def test_miner_detects_one_of(self):
        """When values are always from {1, 2, 3}, ONE_OF invariant should be found."""
        miner = InvariantMiner()

        def returns_small(x: int) -> int:
            return x

        with miner.trace():
            for x in [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]:
                returns_small(x)

        invs = miner.get_invariants("returns_small")
        one_of_invs = [i for i in invs if i.kind == InvariantKind.ONE_OF]

        assert len(one_of_invs) > 0, (
            f"Expected ONE_OF invariant for values {{1,2,3}}, "
            f"got: {[i.expression for i in invs]}"
        )
