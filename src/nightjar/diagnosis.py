"""LP Dual Root-Cause Diagnosis — U1.3.

When formal verification fails, relax invariant constraints to a continuous
LP and solve for the minimum-violation assignment. Dual variables (shadow
prices) rank which constraint is the binding root cause.

Per [REF-NEW-09] duality-verification:
  "A shadow price of λᵢ means relaxing constraint i by one unit reduces
   total violation by λᵢ. Highest shadow price = binding constraint = root cause."

Two modes:
  result_value provided: compute violations at the counterexample point;
    shadow price = violation amount (fast, no LP needed).
  result_value absent: solve the soft LP (min total slack) to find the
    minimum-violation feasible point; dual variables give the ranking.

References:
- [REF-NEW-09] duality-verification (github.com/mellowyellow71/duality-verification)
- scipy.optimize.linprog (BSD, HiGHS solver) — scipy>=1.12
- nightjar-upgrade-plan.md U1.3
"""

import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import numpy as np
    from scipy.optimize import linprog
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


# ─── Constraint parsing ───────────────────────────────────────────────────────

_BOUND_PATTERN = re.compile(
    r"(?:result|output|value)\s*(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _parse_constraint_bound(
    constraint: str,
) -> tuple[Optional[float], Optional[float]]:
    """Parse a constraint string and return (lower_bound, upper_bound).

    Extracts numeric bounds from statements like 'result >= 0',
    'result <= 100', 'result == 5'. For strict inequalities (>, <),
    returns the boundary value (treated as non-strict for LP purposes).

    Args:
        constraint: Invariant statement string.

    Returns:
        Tuple (lb, ub) where lb/ub is the numeric bound or None.
        For 'result >= lb': (lb, None)
        For 'result <= ub': (None, ub)
        For 'result == val': (val, val)
        For unparseable: (None, None)
    """
    m = _BOUND_PATTERN.search(constraint)
    if not m:
        return None, None
    op = m.group(1)
    val = float(m.group(2))
    if op in (">=", ">"):
        return val, None
    if op in ("<=", "<"):
        return None, val
    if op == "==":
        return val, val
    return None, None


# ─── DiagnosisResult ─────────────────────────────────────────────────────────

@dataclass
class DiagnosisResult:
    """Result from LP dual root-cause diagnosis.

    Attributes:
        binding_constraint: The invariant statement with the highest shadow
            price — the primary root cause of the verification failure.
        ranked_constraints: All constraints sorted by shadow price descending.
            Each entry is (constraint_text, shadow_price).
        diagnosis_available: False when no parseable constraints or scipy
            is unavailable. True when diagnosis was performed.
    """
    binding_constraint: str
    ranked_constraints: list[tuple[str, float]] = field(default_factory=list)
    diagnosis_available: bool = True


# ─── LP-based diagnosis (no counterexample) ──────────────────────────────────

def _diagnose_via_lp(
    parsed: list[tuple[str, Optional[float], Optional[float]]],
) -> list[tuple[str, float]]:
    """Solve the soft LP and extract shadow prices from dual.

    LP formulation (per [REF-NEW-09]):
      Variables: [x, ξ₁, ..., ξₙ] — result variable + slack per constraint
      Objective: min sum(ξᵢ)  — minimize total violation
      For result >= lb: -x - ξᵢ ≤ -lb  (x + ξᵢ ≥ lb)
      For result <= ub: x - ξᵢ ≤ ub    (ξᵢ ≥ x - ub)
      Bounds: x free, ξᵢ ≥ 0

    Dual variable abs(λᵢ) = shadow price for constraint row i.
    Mapped back to original constraints (max across their LP rows).

    Returns:
        List of (constraint_text, shadow_price) sorted descending.
    """
    n = len(parsed)
    n_vars = n + 1  # x + n slacks

    c = [0.0] + [1.0] * n  # minimize sum of slacks
    A_ub: list[list[float]] = []
    b_ub: list[float] = []
    # Track which LP rows belong to each constraint
    constraint_lp_rows: list[list[int]] = [[] for _ in range(n)]
    lp_row = 0

    for i, (_, lb, ub) in enumerate(parsed):
        xi_col = i + 1
        if lb is not None:
            row = [0.0] * n_vars
            row[0] = -1.0    # -x
            row[xi_col] = -1.0  # -ξᵢ
            A_ub.append(row)
            b_ub.append(-lb)
            constraint_lp_rows[i].append(lp_row)
            lp_row += 1
        if ub is not None:
            row = [0.0] * n_vars
            row[0] = 1.0     # x
            row[xi_col] = -1.0  # -ξᵢ
            A_ub.append(row)
            b_ub.append(ub)
            constraint_lp_rows[i].append(lp_row)
            lp_row += 1

    if not A_ub:
        return [(c_text, 0.0) for c_text, _, _ in parsed]

    bounds = [(None, None)] + [(0.0, None)] * n  # x free, ξᵢ ≥ 0

    result = linprog(
        c=c,
        A_ub=np.array(A_ub),
        b_ub=np.array(b_ub),
        bounds=bounds,
        method="highs",
    )

    if not result.success or not hasattr(result, "ineqlin"):
        return [(c_text, 0.0) for c_text, _, _ in parsed]

    marginals = result.ineqlin.marginals  # shape: (n_lp_rows,)

    # Map LP row shadow prices back to original constraints
    constraint_prices: list[float] = []
    for rows in constraint_lp_rows:
        if rows:
            price = max(abs(float(marginals[r])) for r in rows)
        else:
            price = 0.0
        constraint_prices.append(price)

    ranked = sorted(
        zip([c_text for c_text, _, _ in parsed], constraint_prices),
        key=lambda pair: -pair[1],
    )
    return ranked


# ─── Direct violation diagnosis (with counterexample) ────────────────────────

def _diagnose_via_violation(
    parsed: list[tuple[str, Optional[float], Optional[float]]],
    result_value: float,
) -> list[tuple[str, float]]:
    """Compute constraint violations at the counterexample point.

    For a given result_value, the shadow price = violation amount:
      - lower bound violated: max(0, lb - result_value)
      - upper bound violated: max(0, result_value - ub)
      - equality violated: abs(result_value - eq_val)

    Returns:
        List of (constraint_text, shadow_price) sorted descending.
    """
    prices: list[tuple[str, float]] = []
    for c_text, lb, ub in parsed:
        violation = 0.0
        if lb is not None and ub is not None and lb == ub:
            # Equality constraint
            violation = abs(result_value - lb)
        else:
            if lb is not None:
                violation += max(0.0, lb - result_value)
            if ub is not None:
                violation += max(0.0, result_value - ub)
        prices.append((c_text, violation))
    return sorted(prices, key=lambda pair: -pair[1])


# ─── Public API ──────────────────────────────────────────────────────────────

def diagnose_failure(
    constraints: list[str],
    result_value: Optional[float] = None,
) -> DiagnosisResult:
    """LP dual root-cause diagnosis [REF-NEW-09].

    Given a list of invariant constraint strings and an optional counterexample
    result value, identifies the most binding (root-cause) constraint.

    When result_value is given: shadow price = violation amount at that value.
    When result_value is None: solves soft LP; dual variables rank constraints.

    Args:
        constraints: Invariant statement strings (e.g., "result >= 0").
        result_value: The failing result from the counterexample, or None.

    Returns:
        DiagnosisResult with binding_constraint and ranked_constraints.
    """
    if not constraints:
        return DiagnosisResult(
            binding_constraint="",
            ranked_constraints=[],
            diagnosis_available=False,
        )

    parsed = [
        (c, *_parse_constraint_bound(c))
        for c in constraints
    ]

    # Filter to constraints that have parseable numeric bounds
    parseable = [(c, lb, ub) for c, lb, ub in parsed if lb is not None or ub is not None]
    unparseable = [(c, 0.0) for c, lb, ub in parsed if lb is None and ub is None]

    if not parseable:
        return DiagnosisResult(
            binding_constraint=constraints[0] if constraints else "",
            ranked_constraints=[(c, 0.0) for c in constraints],
            diagnosis_available=False,
        )

    if result_value is not None:
        ranked = _diagnose_via_violation(parseable, result_value)
    elif _SCIPY_AVAILABLE:
        ranked = _diagnose_via_lp(parseable)
    else:
        # Fallback: equal weight (no LP available)
        ranked = [(c, 0.0) for c, _, _ in parseable]

    # Merge unparseable constraints at the end with shadow price 0
    ranked_map = dict(ranked)
    for c, _ in unparseable:
        if c not in ranked_map:
            ranked.append((c, 0.0))

    ranked_sorted = sorted(ranked, key=lambda pair: -pair[1])

    binding = ranked_sorted[0][0] if ranked_sorted else ""
    return DiagnosisResult(
        binding_constraint=binding,
        ranked_constraints=ranked_sorted,
        diagnosis_available=True,
    )


def diagnose_from_spec(
    spec: "CardSpec",
    result_value: Optional[float] = None,
) -> DiagnosisResult:
    """Diagnose a failing spec by running LP diagnosis on its invariants.

    Extracts invariant statements from the spec and delegates to
    diagnose_failure(). Convenience wrapper for integration with explain.py.

    Args:
        spec: The CardSpec whose invariants failed verification.
        result_value: Optional counterexample result value.

    Returns:
        DiagnosisResult with binding_constraint and ranked_constraints.
    """
    from nightjar.types import CardSpec  # late import to avoid circular
    constraints = [inv.statement for inv in spec.invariants]
    return diagnose_failure(constraints, result_value=result_value)
