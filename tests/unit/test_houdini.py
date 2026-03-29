"""Tests for Houdini fixed-point invariant filter.

Validates CR-14: clean-room implementation from Flanagan & Leino FME 2001.
The Houdini algorithm finds the maximal inductive subset of candidate invariants
via greatest-fixpoint computation using CTI (Counterexample to Induction) elimination.

References:
- Flanagan, C., & Leino, K.R.M. (2001). Houdini, an annotation assistant for ESC/Java.
  Proceedings of FME 2001. https://dl.acm.org/doi/10.1145/587051.587054
- Scout 10 Rank 2 — Houdini filter for post-Daikon invariant validation
- Clean-room CR-14: implement from FME 2001 paper algorithm, no existing Houdini code
"""

from __future__ import annotations

import pytest

z3 = pytest.importorskip("z3", reason="z3-solver not installed; skipping Houdini Z3 tests")

from immune.daikon import Invariant, InvariantKind
from immune.houdini import houdini_filter, HoudiniResult


# ---------------------------------------------------------------------------
# Helpers: build Invariant objects for testing
# ---------------------------------------------------------------------------


def make_inv(func: str, var: str, kind: InvariantKind, expr: str) -> Invariant:
    return Invariant(function=func, variable=var, kind=kind, expression=expr)


# ---------------------------------------------------------------------------
# Test: houdini_filter retains inductive invariants
# ---------------------------------------------------------------------------


class TestHoudiniRetainsInductive:
    """Inductive invariants: no CTI exists under Z3 symbolic reasoning.

    An invariant C is INDUCTIVE given others O if: no model exists satisfying
    all of O while violating C. Formally: O ⊨ C (the others imply C).
    Reference: Flanagan & Leino FME 2001 — inductive invariant definition.
    """

    def test_houdini_retains_inductive(self):
        """An invariant is retained when it is implied by the stronger others.

        "x > 0" IS implied by "x > 4" (if x>4 then certainly x>0).
        CTI check for x>0 given {x>4}: EXISTS x. (x>4) AND NOT(x>0)
          = EXISTS x. x>4 AND x<=0 = UNSAT.
        No CTI -> x>0 is INDUCTIVE -> RETAINED.

        "x > 4" is NOT implied by "x > 0" alone.
        CTI check for x>4 given {x>0}: EXISTS x. (x>0) AND NOT(x>4)
          = EXISTS x. x>0 AND x<=4 = SAT (x=1).
        CTI exists -> x>4 NOT inductive -> ELIMINATED.

        Reference: Flanagan & Leino FME 2001 — maximal inductive subset.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x > 0"),   # weaker: x>4 implies x>0
            make_inv("f", "x", InvariantKind.BOUND, "x > 4"),   # stronger: x>0 does not imply x>4
        ]
        result = houdini_filter(candidates)
        retained_exprs = [i.expression for i in result.retained]
        eliminated_exprs = [i.expression for i in result.eliminated]

        # x > 0 is implied by x > 4 => inductive => retained
        assert "x > 0" in retained_exprs, (
            f"Expected 'x > 0' retained (implied by x > 4), got: {retained_exprs}"
        )
        # x > 4 is NOT implied by x > 0 => non-inductive => eliminated
        assert "x > 4" in eliminated_exprs, (
            f"Expected 'x > 4' eliminated (not implied by x > 0), got: "
            f"{eliminated_exprs}"
        )

    def test_houdini_retains_single_inductive(self):
        """Single invariant with no peers: retained (no CTI possible without peers).

        When other_constraints is empty, there is no formal context for a CTI.
        The candidate is trivially retained per Houdini's implicit assumption that
        program semantics provide additional context beyond candidate invariants.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 0"),
        ]
        result = houdini_filter(candidates)
        assert len(result.retained) == 1
        assert result.retained[0].expression == "x >= 0"

    def test_houdini_empty_input_returns_empty(self):
        """Empty candidate set returns empty result."""
        result = houdini_filter([])
        assert result.retained == []
        assert result.eliminated == []


# ---------------------------------------------------------------------------
# Test: houdini_filter eliminates non-inductive invariants
# ---------------------------------------------------------------------------


class TestHoudiniEliminatesNonInductive:
    """Non-inductive invariants: Z3 can find a CTI (violates the invariant while
    satisfying all others)."""

    def test_houdini_eliminates_non_inductive(self):
        """Core test: non-inductive invariant should be ELIMINATED.

        Given invariants: "x >= 1", "x <= 3", "x > 2"
        - "x > 2" is not implied by "x >= 1 AND x <= 3"
          (CTI: x=1 satisfies x>=1 and x<=3 but violates x>2)
        - So "x > 2" should be eliminated.

        Reference: Flanagan & Leino FME 2001 — CTI elimination.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 1"),
            make_inv("f", "x", InvariantKind.BOUND, "x <= 3"),
            make_inv("f", "x", InvariantKind.BOUND, "x > 2"),  # NOT implied by range
        ]
        result = houdini_filter(candidates)
        retained_exprs = [i.expression for i in result.retained]
        eliminated_exprs = [i.expression for i in result.eliminated]

        # x > 2 should be eliminated (CTI: x=1 is in [1,3] but violates x>2)
        assert "x > 2" in eliminated_exprs, (
            f"Expected 'x > 2' eliminated (non-inductive), but retained: "
            f"{retained_exprs}"
        )

    def test_houdini_eliminates_overly_specific_bound(self):
        """Overly specific bound not implied by range should be eliminated.

        Given: "x >= 0", "x <= 10", "x > 7"
        CTI for "x > 7": x=0 satisfies x>=0 and x<=10 but violates x>7.
        So "x > 7" should be eliminated.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 0"),
            make_inv("f", "x", InvariantKind.BOUND, "x <= 10"),
            make_inv("f", "x", InvariantKind.BOUND, "x > 7"),
        ]
        result = houdini_filter(candidates)
        eliminated = [i.expression for i in result.eliminated]
        assert "x > 7" in eliminated, (
            f"Expected 'x > 7' to be eliminated, but eliminated: {eliminated}"
        )


# ---------------------------------------------------------------------------
# Test: termination guarantee
# ---------------------------------------------------------------------------


class TestHoudiniTermination:
    def test_houdini_terminates_in_p_iterations(self):
        """Houdini terminates in at most |P| iterations.

        With 5 candidates, houdini_filter should complete and report iterations.
        Reference: Flanagan & Leino FME 2001 — termination in <=|P| steps.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 0"),
            make_inv("f", "x", InvariantKind.BOUND, "x > 0"),
            make_inv("f", "x", InvariantKind.BOUND, "x <= 100"),
            make_inv("f", "x", InvariantKind.BOUND, "x != 0"),
            make_inv("f", "x", InvariantKind.CONSTANT, "x == 5"),
        ]
        result = houdini_filter(candidates)

        # Must terminate and report iteration count <= |P|
        assert result.iterations <= len(candidates), (
            f"Expected iterations <= {len(candidates)}, got: {result.iterations}"
        )
        assert result.iterations >= 1, "Must run at least 1 iteration"


# ---------------------------------------------------------------------------
# Test: HoudiniResult structure
# ---------------------------------------------------------------------------


class TestHoudiniResult:
    def test_result_has_retained_and_eliminated(self):
        """HoudiniResult must expose .retained and .eliminated lists."""
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 0"),
        ]
        result = houdini_filter(candidates)
        assert hasattr(result, "retained")
        assert hasattr(result, "eliminated")
        assert hasattr(result, "iterations")
        assert isinstance(result.retained, list)
        assert isinstance(result.eliminated, list)
        assert isinstance(result.iterations, int)

    def test_retained_plus_eliminated_equals_input(self):
        """All candidates must be in either retained or eliminated."""
        candidates = [
            make_inv("f", "x", InvariantKind.BOUND, "x >= 0"),
            make_inv("f", "x", InvariantKind.BOUND, "x > 0"),
            make_inv("f", "x", InvariantKind.BOUND, "x > 5"),
        ]
        result = houdini_filter(candidates)
        total = len(result.retained) + len(result.eliminated)
        assert total == len(candidates), (
            f"retained({len(result.retained)}) + eliminated({len(result.eliminated)}) "
            f"!= input({len(candidates)})"
        )


# ---------------------------------------------------------------------------
# Test: non-numeric invariants passed through unchanged
# ---------------------------------------------------------------------------


class TestHoudiniPassThrough:
    def test_non_numeric_invariants_retained(self):
        """Non-numeric invariants (TYPE, NULLNESS) are passed through unchanged.

        Z3 can't reason about these symbolically, so Houdini leaves them alone.
        """
        candidates = [
            make_inv("f", "x", InvariantKind.TYPE, "isinstance(x, int)"),
            make_inv("f", "x", InvariantKind.NULLNESS, "x is not None"),
        ]
        result = houdini_filter(candidates)
        # Should retain both (can't form CTI for type/nullness invariants)
        assert len(result.retained) == 2, (
            f"Expected non-numeric invariants retained, got: "
            f"{[i.expression for i in result.retained]}"
        )


# ---------------------------------------------------------------------------
# Test: pipeline integration (daikon -> houdini)
# ---------------------------------------------------------------------------


class TestHoudiniPipeline:
    """Integration test: Houdini filters Daikon-mined invariants."""

    def test_daikon_to_houdini_pipeline(self):
        """Houdini should accept invariants from InvariantMiner.get_invariants()."""
        from immune.daikon import InvariantMiner

        def bounded_fn(x: int) -> int:
            return x * 2

        miner = InvariantMiner()
        with miner.trace():
            for x in range(1, 20):
                bounded_fn(x)

        # Daikon mines invariants
        daikon_invs = miner.get_invariants("bounded_fn")
        assert len(daikon_invs) > 0, "Daikon should produce some invariants"

        # Houdini filters for inductiveness
        result = houdini_filter(daikon_invs)
        assert result.iterations >= 1
        # All invariants accounted for
        assert len(result.retained) + len(result.eliminated) == len(daikon_invs)
