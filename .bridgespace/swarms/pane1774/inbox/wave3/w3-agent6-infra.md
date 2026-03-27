# W3-6 Infrastructure Specs Report

**Agent:** W3-6
**Wave:** 3
**Date:** 2026-03-27
**Status:** COMPLETE — 6/6 specs written, all YAML valid

---

## Summary

| Spec File | Module | Invariants | Status |
|-----------|--------|-----------|--------|
| `.card/types.card.md` | types | 6 | PASS |
| `.card/resolver.card.md` | resolver | 7 | PASS |
| `.card/dafny-setup.card.md` | dafny_setup | 5 | PASS |
| `.card/spec-rewriter.card.md` | spec_rewriter | 7 | PASS |
| `.card/shadow-ci.card.md` | shadow_ci | 7 | PASS |
| `.card/intent-router.card.md` | intent_router | 7 | PASS |

**Total invariants:** 39
**Failures:** 0

---

## Key Invariants Per Module

### types.card.md
- INV-01/02: Enum completeness — InvariantTier (3 members), VerifyStatus (4 states)
- INV-03: TrustLevel threshold monotonic ordering (0.75 / 0.50 / 0.25) per SkillFortify trust algebra
- INV-05: VerifyResult.verified is False when any stage has FAIL status

### resolver.card.md
- INV-01/02 (formal): Kahn's algorithm produces each module exactly once in topological order
- INV-03 (property): CyclicDependencyError raised iff cycle detected in in-set dependency graph
- INV-06/07 (property): constitution.card.md always excluded; equal-priority order is lexicographic

### dafny-setup.card.md
- INV-01 (property): find_dafny covers both PATH and DAFNY_PATH env var lookups
- INV-03 (example): ensure_dafny raises RuntimeError with install URL when Dafny absent
- INV-05 (property): get_dafny_version enforces 10-second subprocess timeout

### spec-rewriter.card.md
- INV-01 (formal): rewrite_spec is non-mutating — original CardSpec preserved in RewriteResult.original
- INV-02 (property): idempotent — applying twice produces the same output as once
- INV-03/04 (property): decomposition skips EXAMPLE tier and never splits range patterns

### shadow-ci.card.md
- INV-01 (formal): shadow mode always returns exit_code == 0 regardless of verification outcome
- INV-03 (property): missing/unreadable report degrades gracefully (no crash, status "no_report")
- INV-06/07 (property/example): _post_pr_comment never raises; runner reads from env vars (OWASP A03 prevention)

### intent-router.card.md
- INV-01 (property): parse_nl_intent raises ValueError on empty/whitespace input
- INV-04/05 (property): FORMAL wins on logical quantifier markers; priority chain is FORMAL > STATE > NUMERICAL > BEHAVIORAL
- INV-07 (example): comparison operators give NUMERICAL a +3 score boost

---

## Validation Screenshot

Screenshot saved to: `.bridgespace/swarms/pane1774/w3-agent6-results.png`
HTML results page: `.bridgespace/swarms/pane1774/w3-agent6-results.html`

---

## Notes

- All specs read source code directly before writing — invariants match actual implementation behavior
- resolver.card.md uses 2 formal-tier invariants for the Kahn's algorithm correctness guarantee
- shadow-ci.card.md is a combined spec covering both shadow_ci.py and shadow_ci_runner.py
- dafny-setup.card.md has 5 invariants (below the 7 max) — appropriate for a focused 3-function helper
- spec-rewriter.card.md captures the non-mutation and idempotency invariants which are the safety-critical properties for the Proven rewrite pipeline
