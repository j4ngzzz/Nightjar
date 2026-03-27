---
card-version: "1.0"
id: spec_rewriter
title: Spec Preprocessing Rewrite Rules
status: draft
invariants:
  - id: INV-01
    tier: formal
    statement: "rewrite_spec does not mutate the input spec — the original CardSpec is preserved unchanged in RewriteResult.original"
    rationale: "All transformations operate on deep copies; the pipeline must be able to compare original vs rewritten for audit purposes"
  - id: INV-02
    tier: property
    statement: "rewrite_spec is idempotent — applying it twice produces the same output as applying it once"
    rationale: "All 19 rules normalize toward canonical forms; a canonical form is already canonical and re-application is a no-op"
  - id: INV-03
    tier: property
    statement: "compound_decomposition only splits FORMAL and PROPERTY tier invariants — EXAMPLE tier invariants are never split"
    rationale: "Splitting example invariants would change test semantics; only proof-relevant tiers benefit from atomic decomposition"
  - id: INV-04
    tier: property
    statement: "compound_decomposition does not split range expressions matching the pattern 'A <= x and x <= B'"
    rationale: "Range constraints are a single semantic unit; splitting them would produce ill-formed half-bounds"
  - id: INV-05
    tier: property
    statement: "dedup_and_ordering removes invariants with duplicate statement strings (case-insensitive, stripped) — keeping the first occurrence"
    rationale: "Duplicate invariants waste LLM tokens and confuse Z3; deduplication reduces noise"
  - id: INV-06
    tier: property
    statement: "tier_ordering places FORMAL before PROPERTY before EXAMPLE in the output invariant list"
    rationale: "Dafny's BFS proves stronger invariants first; ordering strongest-first improves proof success rates"
  - id: INV-07
    tier: example
    statement: "RewriteResult.rules_applied lists only the rule groups that actually fired — groups that made no changes are absent"
    rationale: "The audit log should reflect actual transformations; empty rule groups add noise without value"
---

## Intent

Applies 19 deterministic rewrite rules to `.card.md` specs before LLM generation,
transforming natural-language invariants and contract constraints into forms that
Z3 and Dafny handle more efficiently.

Based on Proven (github.com/melek/proven, MIT license), which demonstrated these
rules double Dafny success rates: 19% to 41% on local models, 65% to 78% on
Claude Sonnet.

Pipeline position: `.card.md` → `spec_rewriter.py` → rewritten spec → LLM generation

References:
- Proven (MIT): github.com/melek/proven — 19 deterministic spec rewrite rules
- nightjar-upgrade-plan.md U1.1

## Acceptance Criteria

- [ ] `rewrite_spec` does not mutate the input `CardSpec`
- [ ] `RewriteResult.original` is the exact input spec object (identity, not copy)
- [ ] Quantifier normalization converts "for all x" → "forall x :: " (Dafny syntax)
- [ ] Sugar expansion converts "result is positive" → "result > 0"
- [ ] Compound decomposition splits "A and B" into two invariants for FORMAL/PROPERTY tier
- [ ] Range patterns ("A <= x and x <= B") are NOT split by compound decomposition
- [ ] Constraint normalization converts "must be positive" → "{name} > 0"
- [ ] Deduplication removes invariants with identical normalized statements
- [ ] Tier ordering places FORMAL before PROPERTY before EXAMPLE
- [ ] `rules_applied` in the result lists only groups that made changes

## Functional Requirements

1. **RewriteResult** — dataclass with (spec: CardSpec, original: CardSpec, rules_applied: list[str]); spec is the transformed copy, original is the unmodified input
2. **rewrite_spec(spec) -> RewriteResult** — applies all 19 rules in order:
   - Rules 1-3 (quantifier_normalization): "for all/every/each X" → "forall X :: "; "there exists X such that" → "exists X :: "
   - Rules 7-12 (sugar_expansion): runs BEFORE decomposition; converts "result is positive/non-negative/negative/bounded between A and B/at least N/at most N" to explicit numeric predicates
   - Rules 4-6 (compound_decomposition): splits "A and B" into two invariants for FORMAL/PROPERTY tier only; skips range patterns
   - Rules 13-16 (constraint_normalization): "must be positive/non-negative/not empty/non-empty" → typed predicates using input name
   - Rules 17-19 (dedup_and_ordering): removes duplicate statements (case-insensitive), sorts by tier strength (FORMAL=0, PROPERTY=1, EXAMPLE=2)
3. **Rule application order**: quantifier normalization → sugar expansion → compound decomposition → constraint normalization → dedup+ordering
4. **Non-mutation guarantee**: uses `copy.copy()` for invariants and contract inputs; never modifies the input spec in place
