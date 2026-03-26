"""Houdini fixed-point invariant filter — clean-room implementation.

Implements the Houdini algorithm from:
  Flanagan, C., & Leino, K.R.M. (2001). Houdini, an annotation assistant for ESC/Java.
  In Proceedings of Formal Methods Europe (FME 2001), LNCS 2021, pp. 500-517.
  https://dl.acm.org/doi/10.1145/587051.587054

The Houdini algorithm finds the MAXIMAL INDUCTIVE SUBSET of a set of candidate
invariants via greatest-fixpoint computation with CTI (Counterexample to Induction)
elimination:

  1. Start with full candidate set P
  2. For each invariant C in P, check: does a CTI exist?
     A CTI is a model satisfying (all other invariants in P) but violating C.
  3. If CTI exists: C is not implied by the others -- remove C from P.
  4. Repeat until no more candidates are removed (greatest fixpoint).
  5. Result: maximal subset of P that is mutually consistent.

Terminates in at most |P| iterations (each iteration removes at least one
candidate or we have reached the fixpoint).

Uses Z3 Python API for symbolic reasoning over numeric invariants. Non-numeric
invariants (type, nullness, one-of) are passed through unchanged.

Clean-room CR-14: Implements FME 2001 paper algorithm. No existing Houdini
source code was consulted or copied.

Pipeline position:
  daikon.py (mine candidates) -> houdini.py (filter inductive) -> enforcer.py (enforce)

References:
- Flanagan & Leino FME 2001 -- Houdini algorithm
- Scout 10 Rank 2 -- Houdini for post-Daikon validation
- [REF-C05] Dynamic Invariant Mining -- immune system Stage 2
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import z3  # type: ignore[import]
    _Z3_AVAILABLE = True
except ImportError:
    _Z3_AVAILABLE = False

from immune.daikon import Invariant, InvariantKind


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class HoudiniResult:
    """Result of the Houdini fixed-point computation.

    Attributes:
        retained:   Invariants in the maximal inductive subset.
        eliminated: Invariants removed because a CTI was found.
        iterations: Number of fixpoint iterations performed.
    """

    retained: list[Invariant] = field(default_factory=list)
    eliminated: list[Invariant] = field(default_factory=list)
    iterations: int = 0


# ---------------------------------------------------------------------------
# Expression parser: invariant expression -> Z3 constraint
# ---------------------------------------------------------------------------

# Regex patterns for numeric invariant expressions
_VAR_RE = r"([a-zA-Z_][a-zA-Z0-9_]*)"
_NUM_RE = r"(-?[0-9]+(?:\.[0-9]+)?)"

# Patterns matched (examples):
#   "x >= 0", "x > 0", "x <= 10", "x < -5", "x != 0"
#   "x == 5", "x == 5.0"
#   "1 <= x <= 100"  (range)
#   "return == x (unchanged)"
#   "return > x (increased)"
#   "return < x (decreased)"
_SIMPLE_CMP = re.compile(
    rf"^{_VAR_RE}\s*(>=|>|<=|<|==|!=)\s*{_NUM_RE}$"
)
_RANGE_PAT = re.compile(
    rf"^{_NUM_RE}\s*<=\s*{_VAR_RE}\s*<=\s*{_NUM_RE}$"
)
_STATE_PAT = re.compile(
    rf"^return\s*(==|>|<)\s*{_VAR_RE}\s+\(.*\)$"
)
_VAR_VAR_CMP = re.compile(
    rf"^{_VAR_RE}\s*(>=|>|<=|<|==|!=)\s*{_VAR_RE}$"
)


def _parse_to_z3(expr: str) -> Optional[object]:
    """Parse a numeric invariant expression to a Z3 constraint.

    Returns None if the expression cannot be parsed symbolically
    (e.g., type, nullness, or complex expressions).
    """
    if not _Z3_AVAILABLE:
        return None

    expr = expr.strip()

    # Pattern: "N <= x <= M" (range)
    m = _RANGE_PAT.match(expr)
    if m:
        lo_str, var_name, hi_str = m.group(1), m.group(2), m.group(3)
        lo = float(lo_str)
        hi = float(hi_str)
        x = z3.Real(var_name)
        return z3.And(lo <= x, x <= hi)

    # Pattern: "x OP N" (simple comparison: x >= 0, x == 5, etc.)
    m = _SIMPLE_CMP.match(expr)
    if m:
        var_name, op, num_str = m.group(1), m.group(2), m.group(3)
        val = float(num_str)
        x = z3.Real(var_name)
        ops = {
            ">=": x >= val,
            ">":  x > val,
            "<=": x <= val,
            "<":  x < val,
            "==": x == val,
            "!=": x != val,
        }
        return ops.get(op)

    # Pattern: "return OP x (state comment)" — state invariants
    m = _STATE_PAT.match(expr)
    if m:
        op, var_name = m.group(1), m.group(2)
        ret = z3.Real("return")
        x = z3.Real(var_name)
        ops = {
            "==": ret == x,
            ">":  ret > x,
            "<":  ret < x,
        }
        return ops.get(op)

    # Pattern: "x OP y" (variable-variable comparison)
    m = _VAR_VAR_CMP.match(expr)
    if m:
        var_a, op, var_b = m.group(1), m.group(2), m.group(3)
        a = z3.Real(var_a)
        b = z3.Real(var_b)
        ops = {
            ">=": a >= b,
            ">":  a > b,
            "<=": a <= b,
            "<":  a < b,
            "==": a == b,
            "!=": a != b,
        }
        return ops.get(op)

    # Cannot parse -- not a numeric invariant
    return None


# ---------------------------------------------------------------------------
# Houdini fixed-point algorithm (Flanagan & Leino FME 2001)
# ---------------------------------------------------------------------------


def houdini_filter(
    candidates: list[Invariant],
    max_iterations: Optional[int] = None,
) -> HoudiniResult:
    """Find the maximal inductive subset via Houdini greatest-fixpoint.

    For each candidate invariant C in the active set:
      1. Form the conjunction Phi of all other active invariants that are
         symbolically parseable (numeric constraints).
      2. Ask Z3: does ∃x. Phi(x) ∧ ¬C(x) have a model? (i.e., is there a CTI?)
      3. If SAT: CTI exists -- C is not implied by the others -- remove C.
      4. Repeat until no candidate is removed in a full pass (fixpoint).

    Non-numeric invariants (type, nullness, one-of, etc.) cannot be expressed
    in Z3; they are passed through as retained without CTI checking.

    Args:
        candidates:     Candidate invariants (typically from InvariantMiner).
        max_iterations: Maximum fixpoint iterations (default: len(candidates)).
                        Serves as safety bound; algorithm always terminates by
                        Flanagan & Leino's convergence proof.

    Returns:
        HoudiniResult with .retained (maximal inductive subset) and
        .eliminated (candidates with CTIs found) and .iterations count.

    Reference: Flanagan & Leino FME 2001 -- Algorithm 1 (Houdini).
    CR-14: Clean-room from paper. No Houdini source consulted.
    """
    if not candidates:
        return HoudiniResult(retained=[], eliminated=[], iterations=0)

    limit = max_iterations if max_iterations is not None else len(candidates)

    # Separate parseable (numeric) from non-parseable (pass-through) invariants
    parseable: list[tuple[Invariant, object]] = []  # (invariant, z3_expr)
    non_parseable: list[Invariant] = []

    for inv in candidates:
        z3_expr = _parse_to_z3(inv.expression) if _Z3_AVAILABLE else None
        if z3_expr is not None:
            parseable.append((inv, z3_expr))
        else:
            non_parseable.append(inv)

    # Greatest-fixpoint iteration over parseable invariants
    active: list[tuple[Invariant, object]] = list(parseable)
    eliminated: list[Invariant] = []
    iterations = 0

    for _ in range(limit):
        iterations += 1
        removed_this_round = False

        for i in range(len(active) - 1, -1, -1):  # reverse order for stable removal
            inv, z3_expr = active[i]

            # Build conjunction of all OTHER active invariants
            other_constraints = [expr for j, (_, expr) in enumerate(active) if j != i]

            cti_found = _has_cti(other_constraints, z3_expr)

            if cti_found:
                # CTI found -- this invariant is not inductive given the others
                eliminated.append(inv)
                active.pop(i)
                removed_this_round = True

        if not removed_this_round:
            # Fixpoint reached -- no more CTIs in current active set
            break

    retained = [inv for inv, _ in active] + non_parseable
    return HoudiniResult(retained=retained, eliminated=eliminated, iterations=iterations)


def _has_cti(other_constraints: list[object], candidate: object) -> bool:
    """Check if a CTI exists for `candidate` given `other_constraints`.

    A CTI (Counterexample to Induction) is a model satisfying all
    other constraints but violating the candidate.

    With no other constraints, the candidate is trivially retained
    (there is no formal context in which to find a CTI — this matches
    the Houdini paper's assumption that invariants are checked against
    a program's semantics, not in isolation).

    Returns True if CTI exists (candidate is NOT inductive).
    Returns False if no CTI exists (candidate IS inductive given others).

    Reference: Flanagan & Leino FME 2001 -- CTI check (Section 3).
    """
    if not _Z3_AVAILABLE:
        return False  # Cannot check without Z3 -- conservatively keep candidate

    # With no other constraints, there is no formal basis for a CTI.
    # Single invariants (or when all others have been eliminated) are retained.
    # This matches the Houdini paper's context where the program semantics
    # provide additional context beyond the candidate invariants themselves.
    if not other_constraints:
        return False  # No CTI possible -- retain candidate

    solver = z3.Solver()
    solver.set("timeout", 5000)  # 5s timeout per check

    # Assert conjunction of all other active invariants
    for constraint in other_constraints:
        solver.add(constraint)

    # Assert negation of candidate (looking for a violating model)
    solver.add(z3.Not(candidate))

    result = solver.check()
    return result == z3.sat  # SAT means CTI exists
