# W3-3 Report: .card.md Specs for Verification Stages

**Agent:** W3-3
**Date:** 2026-03-27
**Task:** Write accurate .card.md specs for Nightjar's verification stages and supporting modules

---

## Summary

7 .card.md specs written and validated. All YAML frontmatter parses cleanly. 46 invariants total, all tier=property (accurate to current code — no formal-tier invariants in the stage implementations themselves).

---

## Specs Written

| File | ID | Title | Invariants | Status |
|------|----|-------|------------|--------|
| `.card/stage-preflight.card.md` | `stage_preflight` | Stage 0 - Pre-flight Verification | 7 | PASS |
| `.card/stage-deps.card.md` | `stage_deps` | Stage 1 - Dependency Manifest Check | 6 | PASS |
| `.card/stage-schema.card.md` | `stage_schema` | Stage 2 - Schema Validation | 6 | PASS |
| `.card/stage-pbt.card.md` | `stage_pbt` | Stage 3 - Property-Based Testing | 7 | PASS |
| `.card/stage-formal.card.md` | `stage_formal` | Stage 4 - Dafny Formal Verification | 7 | PASS |
| `.card/negation-proof.card.md` | `negation_proof` | Stage 2.5 - Negation-Proof Spec Validation | 6 | PASS |
| `.card/dafny-pro.card.md` | `dafny_pro` | DafnyPro Wrapper - Three-Component Annotation Pipeline | 7 | PASS |

---

## Key Invariants Captured Per Stage

**Stage 0 (preflight):** stage/name identity, PASS only when all 5 checks clear, FAIL always carries non-empty errors, PASS always has empty errors, dead constraint detection skips non-Python statements, duration_ms non-negative, short-circuit on missing file.

**Stage 1 (deps):** stage/name identity, FAIL on any unlisted third-party import, stdlib never flagged, alias map applied before allowlist check, integrity drift (hash change without version bump) causes FAIL while version-only drift does not, FAIL when deps.lock absent.

**Stage 2 (schema):** stage/name identity, PASS on empty outputs, PASS when any one object schema validates successfully, FAIL only when all schemas fail, Pydantic errors have message/output/field/type keys, models built via create_model from object-typed outputs only.

**Stage 3 (pbt):** stage/name identity, SKIP when no property/formal invariants, FAIL+counterexample when any invariant violated, FAIL with syntax_error type on SyntaxError in exec, dev=10 examples/derandomize/ci=200 examples per NIGHTJAR_TEST_PROFILE, CrossHair SMT backend via NIGHTJAR_CROSSHAIR_BACKEND=1 with graceful fallback, run_pbt_extended uses 10K examples.

**Stage 4 (formal):** stage/name identity, SKIP when no formal invariants, PASS on returncode=0 with no error-pattern output, FAIL with structured errors on non-zero or error-pattern output, TIMEOUT status on TimeoutExpired, FAIL with dafny_not_found type on FileNotFoundError, dafny verify called with all 5 optimisation flags.

**negation_proof:** trivial-pass on no formal invariants, weak_specs populated on CrossHair returncode=0, not populated on returncode=1, FileNotFoundError/TimeoutExpired/OSError silently skipped, passed iff weak_specs empty, negate_postcondition is purely syntactic wrapping.

**dafny_pro:** check_diff False on new method signatures, check_diff True only on valid subsequence, prune_invariants removes trivially-true patterns, prune_invariants deduplicates annotations, augment_hints no-op on empty errors, apply short-circuits on diff failure, pipeline order is check_diff then prune then augment.

---

## Validation

All 7 specs validated by Python yaml.safe_load:
- Required fields card-version and id: present in all specs
- All invariant tiers: valid (property only, no invalid values)
- YAML parses cleanly: no syntax errors

Screenshot: `.bridgespace/swarms/pane1774/inbox/wave3/w3-agent3-stages-screenshot.png`
HTML results: `.bridgespace/swarms/pane1774/inbox/wave3/w3-agent3-stages-results.html`

---

## Notes

- All 46 invariants use tier=property because they describe observable runtime contracts of the stage implementations, not mathematical proofs. The stages themselves verify other code; they don't need formal proofs of their own internals in this spec layer.
- StageResult data model confirmed from `src/nightjar/types.py`: fields are stage (int), name (str), status (VerifyStatus), duration_ms (int), errors (list[dict]), counterexample (Optional[dict]).
- VerifyStatus values: PASS, FAIL, SKIP, TIMEOUT — all four appear in the stage specs where accurate.
- negation_proof returns NegProofResult (not StageResult) — spec accurately reflects this distinct return type.
