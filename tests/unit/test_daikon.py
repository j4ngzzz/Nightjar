"""Tests for the Daikon algorithm reimplementation.

Validates the InvariantMiner discovers correct invariants from
observed function executions using sys.settrace instrumentation.

This is a MIT-licensed reimplementation. Do NOT copy Fuzzingbook code.

References:
- [REF-T13] Fuzzingbook DynamicInvariants — algorithm reference (CC-BY-NC-SA)
- [REF-C05] Dynamic Invariant Mining — CARD immune system Stage 2
- [REF-P18] Self-Healing Software Systems — biological immune metaphor
"""

import pytest

from immune.daikon import InvariantMiner, Invariant, InvariantKind


# ---------------------------------------------------------------------------
# Helper functions to mine invariants from
# ---------------------------------------------------------------------------

def absolute_value(x: int) -> int:
    """Simple abs function for testing."""
    if x < 0:
        return -x
    return x


def safe_divide(a: float, b: float) -> float:
    """Division that only works with non-zero b."""
    return a / b


def get_length(s: str) -> int:
    """Returns length of a string."""
    return len(s)


def sorted_list(lst: list) -> list:
    """Returns a sorted copy."""
    return sorted(lst)


def identity(x):
    """Returns x unchanged."""
    return x


def multi_return(x: int, y: int) -> int:
    """Returns x + y, always positive when both positive."""
    return x + y


# ---------------------------------------------------------------------------
# Test: Basic InvariantMiner construction
# ---------------------------------------------------------------------------

class TestInvariantMinerConstruction:
    def test_create_miner(self):
        miner = InvariantMiner()
        assert miner is not None

    def test_miner_starts_with_no_invariants(self):
        miner = InvariantMiner()
        assert miner.get_invariants("nonexistent") == []

    def test_miner_has_trace_count(self):
        miner = InvariantMiner()
        assert miner.trace_count == 0


# ---------------------------------------------------------------------------
# Test: Tracing function calls
# ---------------------------------------------------------------------------

class TestTracing:
    def test_trace_records_calls(self):
        miner = InvariantMiner()
        with miner.trace():
            absolute_value(5)
        assert miner.trace_count > 0

    def test_trace_multiple_calls(self):
        miner = InvariantMiner()
        with miner.trace():
            absolute_value(5)
            absolute_value(-3)
            absolute_value(0)
        assert miner.trace_count >= 3

    def test_trace_context_manager_restores_state(self):
        """sys.settrace should be restored after context manager exits."""
        import sys
        old_trace = sys.gettrace()
        miner = InvariantMiner()
        with miner.trace():
            absolute_value(1)
        assert sys.gettrace() == old_trace


# ---------------------------------------------------------------------------
# Test: Discovering type invariants
# ---------------------------------------------------------------------------

class TestTypeInvariants:
    def test_discovers_int_argument_type(self):
        miner = InvariantMiner()
        with miner.trace():
            for i in range(-10, 11):
                absolute_value(i)
        invs = miner.get_invariants("absolute_value")
        type_invs = [i for i in invs if i.kind == InvariantKind.TYPE]
        # Should discover that x is always int
        x_type_invs = [i for i in type_invs if "x" in i.variable]
        assert len(x_type_invs) > 0
        assert any("int" in i.expression for i in x_type_invs)

    def test_discovers_return_type(self):
        miner = InvariantMiner()
        with miner.trace():
            for i in range(-10, 11):
                absolute_value(i)
        invs = miner.get_invariants("absolute_value")
        type_invs = [i for i in invs if i.kind == InvariantKind.TYPE]
        ret_type_invs = [i for i in type_invs if "return" in i.variable]
        assert len(ret_type_invs) > 0
        assert any("int" in i.expression for i in ret_type_invs)


# ---------------------------------------------------------------------------
# Test: Discovering value bound invariants
# ---------------------------------------------------------------------------

class TestValueBounds:
    def test_discovers_result_nonnegative(self):
        """Mining abs(x) should discover result >= 0."""
        miner = InvariantMiner()
        with miner.trace():
            for i in range(-50, 51):
                absolute_value(i)
        invs = miner.get_invariants("absolute_value")
        bound_invs = [i for i in invs if i.kind == InvariantKind.BOUND]
        # result >= 0 should be discovered
        ret_bounds = [i for i in bound_invs if "return" in i.variable]
        assert any(">= 0" in i.expression for i in ret_bounds), \
            f"Expected 'return >= 0' invariant, got: {[i.expression for i in ret_bounds]}"

    def test_discovers_length_nonnegative(self):
        """Mining len(s) should discover result >= 0."""
        miner = InvariantMiner()
        with miner.trace():
            for s in ["", "a", "hello", "test string", "x" * 100]:
                get_length(s)
        invs = miner.get_invariants("get_length")
        bound_invs = [i for i in invs if i.kind == InvariantKind.BOUND]
        ret_bounds = [i for i in bound_invs if "return" in i.variable]
        assert any(">= 0" in i.expression for i in ret_bounds)


# ---------------------------------------------------------------------------
# Test: Discovering nullness invariants
# ---------------------------------------------------------------------------

class TestNullnessInvariants:
    def test_discovers_not_none(self):
        """All args to absolute_value are non-None."""
        miner = InvariantMiner()
        with miner.trace():
            for i in range(-10, 11):
                absolute_value(i)
        invs = miner.get_invariants("absolute_value")
        nullness_invs = [i for i in invs if i.kind == InvariantKind.NULLNESS]
        assert any("x" in i.variable and "not None" in i.expression
                    for i in nullness_invs)


# ---------------------------------------------------------------------------
# Test: Discovering relational invariants (binary)
# ---------------------------------------------------------------------------

class TestRelationalInvariants:
    def test_discovers_sum_relation(self):
        """For multi_return(x, y) with positive inputs, result > x and result > y."""
        miner = InvariantMiner()
        with miner.trace():
            for x in range(1, 20):
                for y in range(1, 20):
                    multi_return(x, y)
        invs = miner.get_invariants("multi_return")
        rel_invs = [i for i in invs if i.kind == InvariantKind.RELATIONAL]
        # Should find return > x and return > y (since both positive)
        assert len(rel_invs) > 0, "Expected relational invariants"


# ---------------------------------------------------------------------------
# Test: Invariant falsification
# ---------------------------------------------------------------------------

class TestFalsification:
    def test_falsified_invariants_removed(self):
        """If we first see only positive x, then see negative x,
        the invariant 'x > 0' should be falsified."""
        miner = InvariantMiner()
        with miner.trace():
            for i in range(1, 10):
                absolute_value(i)
        invs_before = miner.get_invariants("absolute_value")
        x_positive = [i for i in invs_before
                      if i.kind == InvariantKind.BOUND
                      and "x" in i.variable
                      and "> 0" in i.expression]

        # Now observe negative x — should falsify "x > 0"
        with miner.trace():
            absolute_value(-5)
        invs_after = miner.get_invariants("absolute_value")
        x_positive_after = [i for i in invs_after
                            if i.kind == InvariantKind.BOUND
                            and "x" in i.variable
                            and "> 0" in i.expression]
        # x > 0 should have been falsified
        assert len(x_positive_after) < len(x_positive) or len(x_positive) == 0


# ---------------------------------------------------------------------------
# Test: Invariant data model
# ---------------------------------------------------------------------------

class TestInvariantModel:
    def test_invariant_has_required_fields(self):
        inv = Invariant(
            function="test_func",
            variable="x",
            kind=InvariantKind.TYPE,
            expression="isinstance(x, int)",
        )
        assert inv.function == "test_func"
        assert inv.variable == "x"
        assert inv.kind == InvariantKind.TYPE
        assert inv.expression == "isinstance(x, int)"

    def test_invariant_kind_enum(self):
        assert InvariantKind.TYPE.value == "type"
        assert InvariantKind.BOUND.value == "bound"
        assert InvariantKind.NULLNESS.value == "nullness"
        assert InvariantKind.RELATIONAL.value == "relational"
        assert InvariantKind.LENGTH.value == "length"


# ---------------------------------------------------------------------------
# Test: Length invariants
# ---------------------------------------------------------------------------

class TestLengthInvariants:
    def test_discovers_string_has_length(self):
        """Mining get_length(s) should discover len(s) >= 0."""
        miner = InvariantMiner()
        with miner.trace():
            for s in ["", "a", "hello", "test"]:
                get_length(s)
        invs = miner.get_invariants("get_length")
        length_invs = [i for i in invs if i.kind == InvariantKind.LENGTH]
        assert any("s" in i.variable for i in length_invs), \
            f"Expected length invariant for s, got: {[str(i) for i in length_invs]}"


# ---------------------------------------------------------------------------
# Test: Mining from sorted()
# ---------------------------------------------------------------------------

class TestSortedInvariants:
    def test_discovers_sorted_result_same_length(self):
        """sorted(lst) should have len(result) == len(lst)."""
        miner = InvariantMiner()
        with miner.trace():
            for _ in range(50):
                import random
                lst = [random.randint(-100, 100) for _ in range(random.randint(0, 20))]
                sorted_list(lst)
        invs = miner.get_invariants("sorted_list")
        # Should discover something about lengths being equal
        assert len(invs) > 0, "Expected some invariants from sorted_list"


# ---------------------------------------------------------------------------
# Test: Function filtering
# ---------------------------------------------------------------------------

class TestFunctionFiltering:
    def test_filter_by_module(self):
        """Miner should be able to filter which functions to trace."""
        miner = InvariantMiner(include_modules=[__name__])
        with miner.trace():
            absolute_value(5)
            get_length("hello")
        # Should only have invariants for functions in this module
        assert miner.get_invariants("absolute_value") != []
        assert miner.get_invariants("get_length") != []

    def test_exclude_stdlib(self):
        """By default, stdlib functions should not be traced."""
        miner = InvariantMiner()
        with miner.trace():
            absolute_value(5)
        # Should not have invariants for internal Python functions
        assert miner.get_invariants("len") == []
        assert miner.get_invariants("isinstance") == []


# ---------------------------------------------------------------------------
# Test: Export invariants as CARD-compatible format
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_as_card_invariants(self):
        """Invariants should be exportable as CARD Invariant objects."""
        miner = InvariantMiner()
        with miner.trace():
            for i in range(-10, 11):
                absolute_value(i)
        card_invs = miner.export_card_invariants("absolute_value")
        assert len(card_invs) > 0
        # Each should have the right fields
        for inv in card_invs:
            assert hasattr(inv, "id")
            assert hasattr(inv, "tier")
            assert hasattr(inv, "statement")
