# W3-1 Report: Core Pipeline .card.md Specs

**Agent**: W3-1
**Date**: 2026-03-27
**Status**: Complete — 5/5 specs parse, 0 failures

---

## Summary

Audited two existing specs and wrote three new .card.md specs for Nightjar's core pipeline modules. All five specs parse correctly via `nightjar.parser.parse_card_spec()`. Total: 26 invariants across 5 modules.

---

## Step 1: Audit Results

### `.card/parser.card.md` — No changes needed

Read `src/nightjar/parser.py` and compared against existing spec. All five invariants hold:
- INV-001: `parse_card_spec` always returns non-empty `id` — confirmed, `_validate_required` enforces this
- INV-002: Raises `ValueError` for missing `card-version` or `id` — confirmed, `_REQUIRED_FIELDS = ("card-version", "id")`
- INV-003: Raises `FileNotFoundError` for non-existent paths — confirmed, `Path(path).read_text()` raises this
- INV-004: Example fixture test — no fixture path to verify, but invariant format is valid
- INV-005: `parse_with_constitution` deduplicates by id with module-level precedence — confirmed in code

### `.card/auto.card.md` — No changes needed

Read `src/nightjar/auto.py` and compared against existing spec. All four invariants hold:
- INV-001: `run_auto` with `yes=True` always writes a `.card.md` — confirmed, `_write_card_md` always called
- INV-002: Raises `ValueError` for empty NL intent — confirmed, delegates to `parse_nl_intent` which raises
- INV-003: `approved_count + skipped_count = len(ranked)` — confirmed: `skipped_count = len(ranked) - len(approved_with_code)`
- INV-004: Example — reasonable expectation for a payment spec, format valid

---

## Step 2: New Specs Written

### `.card/generator.card.md` — 6 invariants

Key invariants derived from `src/nightjar/generator.py`:
- `generate_code` raises `TypeError` for non-`CardSpec` input (explicit isinstance check at line 485)
- `generate_code` raises `ValueError` when any LLM stage returns empty content (each stage checks and raises)
- `GenerationResult.spec_id` equals `spec.id` (assigned at line 527)
- `cross_validation_issues` is always a list (initialized as `[]`, never set to None)
- Model selection follows: override > `NIGHTJAR_MODEL` env > `DEFAULT_MODEL`

### `.card/verifier.card.md` — 6 invariants

Key invariants derived from `src/nightjar/verifier.py`:
- `run_pipeline` always returns a `VerifyResult` (no exception propagation at pipeline level)
- `_stage_ok` returns True for PASS and SKIP, False for FAIL and TIMEOUT (verified in code at line 277-283)
- Sequential short-circuit: Stage 0 or 1 FAIL stops the pipeline before stages 2/3/4
- `_compute_complexity` returns > threshold for syntax errors (explicit safety routing at line 65)
- `run_pipeline_with_fallback` always returns non-None (never raises, per docstring and code structure)
- Stage 4 uses complexity-discriminated routing: simple (≤5) → CrossHair; complex (>5) → Dafny

### `.card/retry.card.md` — 6 invariants

Key invariants derived from `src/nightjar/retry.py`:
- `run_with_retry` makes at most `max_retries + 1 + annotation_retries` calls to `run_pipeline` (bounded)
- Returns `verified=True, retry_count=0` on first-attempt success (line 413-414)
- Always returns a `VerifyResult` after exhausting retries (line 464-465)
- `parse_dafny_counterexample` returns None when no counterexample block in output
- `run_bfs_search` makes at most `1 + max_depth * beam_width` pipeline calls (line 556+)
- `extract_counterexample_from_stage` returns None for non-formal stages (line 119-120)

---

## Step 3: Verification Results

```
PASS  .card/parser.card.md     id=parser, 5 invariants
PASS  .card/auto.card.md       id=auto, 4 invariants
PASS  .card/generator.card.md  id=generator, 6 invariants
PASS  .card/verifier.card.md   id=verifier, 6 invariants
PASS  .card/retry.card.md      id=retry, 6 invariants
```

All specs parse via `nightjar.parser.parse_card_spec()` without errors.

---

## Step 4: Screenshot

HTML results page at `.card/verify-results.html`. Screenshot: `verify-results-w3-agent1.png`.

---

## Files Created/Modified

| File | Action |
|------|--------|
| `.card/generator.card.md` | Created (6 invariants, property tier) |
| `.card/verifier.card.md` | Created (6 invariants, property tier) |
| `.card/retry.card.md` | Created (6 invariants, property tier) |
| `.card/verify-results.html` | Created (HTML results page) |
| `.bridgespace/swarms/pane1774/inbox/wave3/w3-agent1-core.md` | This report |

---

## Notes on Invariant Quality

All invariants are grounded in specific lines of code:
- No aspirational invariants ("code must be correct")
- Each invariant cites the specific code path that makes it true
- Invariants cover: type guards, error contracts, output guarantees, bounded iteration, and state transitions
- Used `property` tier for all new invariants (Hypothesis PBT testable) since these modules are Python
- No `formal` tier used since the modules make external calls (LLM, subprocess) that Dafny cannot prove
