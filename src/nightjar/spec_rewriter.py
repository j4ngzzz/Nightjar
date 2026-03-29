"""Spec Preprocessing Rewrite Rules — U1.1.

5 rule groups covering 19 normalization patterns applied to .card.md specs BEFORE
LLM generation. Based on Proven (github.com/melek/proven, MIT) which demonstrates
these rules double Dafny success rates: 19%→41% on local models, 65%→78% on Claude Sonnet.

Pipeline insertion: .card.md → spec_rewriter.py → rewritten spec → LLM generation

Rule groups (19 rules total):
  Group 1 — Quantifier normalization (3 rules)
  Group 2 — Compound postcondition decomposition (3 rules)
  Group 3 — Syntactic sugar expansion (6 rules)
  Group 4 — Contract constraint normalization (4 rules)
  Group 5 — Invariant deduplication + ordering (3 rules)

References:
- Proven (MIT): github.com/melek/proven — 19 deterministic spec rewrite rules
- nightjar-upgrade-plan.md U1.1
"""

import copy
import re
from dataclasses import dataclass, field

from nightjar.types import (
    CardSpec, Contract, ContractInput, Invariant, InvariantTier,
)


@dataclass
class RewriteResult:
    """Result from applying rewrite rules to a CardSpec.

    Attributes:
        spec: Rewritten CardSpec (new object, original unchanged).
        original: Original CardSpec (unmodified).
        rules_applied: List of rule names that fired (for audit/debug).
    """
    spec: CardSpec
    original: CardSpec
    rules_applied: list[str] = field(default_factory=list)


# ─── Rule Group 1: Quantifier Normalization ──────────────────────────────────
# Per Proven Rule 1-3: Normalize ambiguous natural-language quantifiers to
# explicit bounded forms that Z3 and Dafny can parse directly.
# "for all x" → "forall x :: " (Dafny quantifier syntax)
# "there exists n" → "exists n :: "

_FORALL_PATTERNS = [
    (re.compile(r"\bfor all\s+(\w+),?\s*", re.IGNORECASE), r"forall \1 :: "),
    (re.compile(r"\bfor every\s+(\w+),?\s*", re.IGNORECASE), r"forall \1 :: "),
    (re.compile(r"\bfor each\s+(\w+),?\s*", re.IGNORECASE), r"forall \1 :: "),
]

_EXISTS_PATTERNS = [
    (re.compile(r"\bthere exists\s+(\w+)\s+such that\s*", re.IGNORECASE), r"exists \1 :: "),
    (re.compile(r"\bexists\s+(?:a\s+)?(\w+)\s+(?:such that|where|with)\s*", re.IGNORECASE), r"exists \1 :: "),
]


def _apply_quantifier_normalization(
    invariants: list[Invariant],
    rules_applied: list[str],
) -> list[Invariant]:
    """Rule 1-3: Normalize 'for all'/'there exists' to explicit Dafny syntax."""
    result = []
    changed = False
    for inv in invariants:
        stmt = inv.statement
        for pattern, replacement in _FORALL_PATTERNS + _EXISTS_PATTERNS:
            new_stmt = pattern.sub(replacement, stmt)
            if new_stmt != stmt:
                stmt = new_stmt
                changed = True
        new_inv = copy.copy(inv)
        new_inv.statement = stmt
        result.append(new_inv)
    if changed and "quantifier_normalization" not in rules_applied:
        rules_applied.append("quantifier_normalization")
    return result


# ─── Rule Group 2: Compound Postcondition Decomposition ──────────────────────
# Per Proven Rule 4-6: Split 'A and B and C' into separate invariants.
# Z3 handles atomic predicates more efficiently; avoids single large conjunction.
# Only splits FORMAL and PROPERTY tier invariants.

_AND_SPLIT_PATTERN = re.compile(r"\s+and\s+", re.IGNORECASE)


def _split_compound_invariant(inv: Invariant) -> list[Invariant]:
    """Split a compound 'X and Y' invariant into two separate invariants."""
    # Only split formal/property tier invariants
    if inv.tier not in (InvariantTier.FORMAL, InvariantTier.PROPERTY):
        return [inv]
    # Don't split if it looks like a range ('A <= x and x <= B' pattern)
    range_pattern = re.compile(r"[\d\w]+\s*<=?\s*\w+\s+and\s+\w+\s*<=?\s*[\d\w]+", re.IGNORECASE)
    if range_pattern.search(inv.statement):
        return [inv]
    parts = _AND_SPLIT_PATTERN.split(inv.statement)
    if len(parts) < 2:
        return [inv]
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        new_inv = copy.copy(inv)
        new_inv.id = f"{inv.id}-{i+1}" if len(parts) > 1 else inv.id
        new_inv.statement = part
        result.append(new_inv)
    return result if len(result) > 1 else [inv]


def _apply_compound_decomposition(
    invariants: list[Invariant],
    rules_applied: list[str],
) -> list[Invariant]:
    """Rule 4-6: Decompose compound 'A and B' postconditions."""
    result = []
    changed = False
    for inv in invariants:
        parts = _split_compound_invariant(inv)
        if len(parts) > 1:
            changed = True
        result.extend(parts)
    if changed and "compound_decomposition" not in rules_applied:
        rules_applied.append("compound_decomposition")
    return result


# ─── Rule Group 3: Syntactic Sugar Expansion ─────────────────────────────────
# Per Proven Rule 7-12: Expand shorthand natural-language predicates to
# explicit numeric forms Z3 can evaluate directly.

_SUGAR_RULES: list[tuple[re.Pattern, str]] = [
    # Rule 7: positive → > 0
    (re.compile(r"\b(result|output|return value|value)\s+is\s+positive\b", re.IGNORECASE), r"result > 0"),
    (re.compile(r"\breturns?\s+(?:a\s+)?positive\b", re.IGNORECASE), r"result > 0"),
    # Rule 8: non-negative → >= 0
    (re.compile(r"\b(result|output)\s+is\s+non-negative\b", re.IGNORECASE), r"result >= 0"),
    (re.compile(r"\breturns?\s+(?:a\s+)?non-negative\b", re.IGNORECASE), r"result >= 0"),
    # Rule 9: negative → < 0
    (re.compile(r"\b(result|output)\s+is\s+negative\b", re.IGNORECASE), r"result < 0"),
    # Rule 10: bounded between A and B → A <= result <= B
    (re.compile(
        r"\b(result|output)\s+is\s+bounded\s+between\s+(\d+)\s+and\s+(\d+)\b",
        re.IGNORECASE,
    ), lambda m: f"{m.group(2)} <= result <= {m.group(3)}"),
    # Rule 11: at least N → >= N
    (re.compile(r"\b(result|output)\s+is\s+at\s+least\s+(\d+)\b", re.IGNORECASE),
     lambda m: f"result >= {m.group(2)}"),
    # Rule 12: at most N → <= N
    (re.compile(r"\b(result|output)\s+is\s+at\s+most\s+(\d+)\b", re.IGNORECASE),
     lambda m: f"result <= {m.group(2)}"),
]


def _apply_sugar_expansion(
    invariants: list[Invariant],
    rules_applied: list[str],
) -> list[Invariant]:
    """Rule 7-12: Expand syntactic sugar to explicit numeric predicates."""
    result = []
    changed = False
    for inv in invariants:
        stmt = inv.statement
        for pattern, replacement in _SUGAR_RULES:
            if callable(replacement):
                new_stmt = pattern.sub(replacement, stmt)
            else:
                new_stmt = pattern.sub(replacement, stmt)
            if new_stmt != stmt:
                stmt = new_stmt
                changed = True
        new_inv = copy.copy(inv)
        new_inv.statement = stmt
        result.append(new_inv)
    if changed and "sugar_expansion" not in rules_applied:
        rules_applied.append("sugar_expansion")
    return result


# ─── Rule Group 4: Contract Constraint Normalization ─────────────────────────
# Per Proven Rule 13-16: Normalize natural-language input/output constraints
# to typed preconditions LLM and Z3 can use.

_CONSTRAINT_RULES: list[tuple[re.Pattern, str]] = [
    # Rule 13: must be positive → x > 0
    (re.compile(r"\bmust\s+be\s+positive\b", re.IGNORECASE), "{name} > 0"),
    # Rule 14: must be non-negative → x >= 0
    (re.compile(r"\bmust\s+be\s+non-negative\b", re.IGNORECASE), "{name} >= 0"),
    # Rule 15: must not be empty (strings) → len(x) > 0
    (re.compile(r"\bmust\s+not\s+be\s+empty\b", re.IGNORECASE), "len({name}) > 0"),
    # Rule 16: must be non-empty → len(x) > 0
    (re.compile(r"\bmust\s+be\s+non-empty\b", re.IGNORECASE), "len({name}) > 0"),
]


def _normalize_constraint(constraint: str, name: str) -> tuple[str, bool]:
    """Apply constraint normalization rules to a single input constraint."""
    changed = False
    for pattern, template in _CONSTRAINT_RULES:
        if pattern.search(constraint):
            normalized = template.format(name=name)
            constraint = pattern.sub(normalized, constraint)
            changed = True
    return constraint, changed


def _apply_constraint_normalization(
    contract: Contract,
    rules_applied: list[str],
) -> Contract:
    """Rule 13-16: Normalize input constraint natural language to predicates."""
    new_inputs = []
    changed = False
    for inp in contract.inputs:
        new_constraint, c = _normalize_constraint(inp.constraints, inp.name)
        if c:
            changed = True
        new_inp = copy.copy(inp)
        new_inp.constraints = new_constraint
        new_inputs.append(new_inp)
    if changed and "constraint_normalization" not in rules_applied:
        rules_applied.append("constraint_normalization")
    new_contract = copy.copy(contract)
    new_contract.inputs = new_inputs
    return new_contract


# ─── Rule Group 5: Deduplication + Ordering ──────────────────────────────────
# Per Proven Rule 17-19: Remove duplicate invariant statements. Order invariants
# FORMAL > PROPERTY > EXAMPLE (strongest first for Dafny's BFS).

_TIER_ORDER = {InvariantTier.FORMAL: 0, InvariantTier.PROPERTY: 1, InvariantTier.EXAMPLE: 2}


def _apply_dedup_and_ordering(
    invariants: list[Invariant],
    rules_applied: list[str],
) -> list[Invariant]:
    """Rule 17-19: Remove duplicate statements, order by tier strength."""
    seen: set[str] = set()
    deduped = []
    for inv in invariants:
        key = inv.statement.strip().lower()
        if key not in seen:
            seen.add(key)
            deduped.append(inv)
    if len(deduped) < len(invariants) and "deduplication" not in rules_applied:
        rules_applied.append("deduplication")

    ordered = sorted(deduped, key=lambda i: _TIER_ORDER.get(i.tier, 99))
    if ordered != deduped and "tier_ordering" not in rules_applied:
        rules_applied.append("tier_ordering")

    return ordered


# ─── Public API ──────────────────────────────────────────────────────────────

def rewrite_spec(spec: CardSpec) -> RewriteResult:
    """Apply all 5 Proven rule groups (19 normalization patterns) to a CardSpec before LLM generation.

    Rules transform specs into forms Z3/Dafny handles more efficiently:
      Group 1 (rules 1-3):  Quantifier normalization
      Group 2 (rules 4-6):  Compound postcondition decomposition
      Group 3 (rules 7-12): Syntactic sugar expansion
      Group 4 (rules 13-16): Contract constraint normalization
      Group 5 (rules 17-19): Deduplication + tier ordering

    Does NOT mutate the input spec — returns a new CardSpec.

    Per Proven: applying these rules before LLM generation increases Dafny
    success from 19%→41% (local models) and 65%→78% (Claude Sonnet).

    Args:
        spec: Parsed CardSpec from .card.md.

    Returns:
        RewriteResult with rewritten spec, original spec, and rules fired.
    """
    rules_applied: list[str] = []

    # Deep copy invariants and contract to avoid mutating the original
    invariants = [copy.copy(inv) for inv in spec.invariants]
    contract = copy.copy(spec.contract)
    contract.inputs = [copy.copy(inp) for inp in spec.contract.inputs]
    contract.outputs = list(spec.contract.outputs)

    # Apply rules in order
    # Sugar expansion runs BEFORE decomposition so bounded/range patterns
    # are expanded before the AND-split scans for compound postconditions.
    invariants = _apply_quantifier_normalization(invariants, rules_applied)  # Rules 1-3
    invariants = _apply_sugar_expansion(invariants, rules_applied)           # Rules 7-12 (before decomp)
    invariants = _apply_compound_decomposition(invariants, rules_applied)    # Rules 4-6
    contract = _apply_constraint_normalization(contract, rules_applied)      # Rules 13-16
    invariants = _apply_dedup_and_ordering(invariants, rules_applied)        # Rules 17-19

    # Build rewritten spec (shallow copy + replaced fields)
    rewritten = copy.copy(spec)
    rewritten.invariants = invariants
    rewritten.contract = contract

    return RewriteResult(
        spec=rewritten,
        original=spec,
        rules_applied=rules_applied,
    )
