# W3-7 Report — Immune System Collection Module Specs

**Agent:** W3-7
**Wave:** 3
**Date:** 2026-03-27
**Status:** COMPLETE

---

## Deliverables

6 `.card.md` specs written, validated (all YAML parseable), and screenshotted.

| Spec File | Module | Invariants | Validation |
|-----------|--------|------------|------------|
| `.card/immune-collector.card.md` | `src/immune/collector.py` | 7 | VALID |
| `.card/immune-daikon.card.md` | `src/immune/daikon.py` | 7 | VALID |
| `.card/immune-store.card.md` | `src/immune/store.py` | 6 | VALID |
| `.card/immune-fingerprint.card.md` | `src/immune/fingerprint.py` | 6 | VALID |
| `.card/immune-error-capture.card.md` | `src/immune/error_capture.py` | 6 | VALID |
| `.card/immune-otel.card.md` | `src/immune/otel_collector.py` | 6 | VALID |

Total: **38 invariants** across 6 specs.

---

## Key Invariants Per Module

### immune-collector (TypeCollector)
- INV-01: `trace()` restores prior `sys.setprofile` on exit even on exceptions
- INV-02: `CallTrace` only emitted when call+return pair is complete (pending queue discipline)
- INV-03: per-function buffer capped at `max_records`
- INV-05: no exception escapes `_profile_callback` on uninspectable frames

### immune-daikon (InvariantMiner)
- INV-01: every returned invariant holds for ALL observed call records (Ernst falsification principle)
- INV-02: returns `[]` on zero observations
- INV-03: `trace()` restores `sys.monitoring` slot / `sys.settrace` on exit
- INV-05: graceful fallback to `sys.settrace` on Python 3.11 or when monitoring slots exhausted
- INV-06: CONSTANT invariant requires ALL values identical (not just majority)

### immune-store (TraceStore)
- INV-01: all `insert_*` methods are append-only; no UPDATE/DELETE on trace tables
- INV-03: `update_candidate_status` is the only mutation allowed
- INV-04: thread-local connections via `threading.local` (one conn per thread)
- INV-05: all `get_*` queries return results ordered by id ASC

### immune-fingerprint
- INV-01: `similarity_score` always in [0.0, 1.0]
- INV-02: returns 0.0 for empty fingerprint
- INV-04: match threshold default 0.7 — no sub-threshold pairs returned
- INV-05: greedy one-to-one assignment (each function matched at most once)

### immune-error-capture
- INV-02: `compute_semantic_fingerprint` returns exactly 16 hex chars (SHA-256[:16])
- INV-03: same inputs always produce same fingerprint (deterministic grouping)
- INV-04: `capture_exception()` raises `RuntimeError` when called outside except block
- INV-05: trace appended to `self.captured` before re-raise

### immune-otel (OTelCollector)
- INV-01: `span_count` never exceeds `max_spans`; overflow silently dropped
- INV-02: `extract_json_shape` preserves dict structure, replaces values with type names
- INV-04: UUID replacement applied before numeric replacement in `normalize_url`
- INV-05: `export_api_traces` produces exactly one `ApiTrace` per span, in order

---

## Method

1. Read all 6 source files in full
2. Mapped actual code behavior (not assumptions) to invariants
3. Validated YAML frontmatter with Python yaml parser — all 6 passed
4. Generated HTML results page with summary table + full invariant listing
5. Screenshotted with Playwright (full-page, 1200px wide)

---

## Screenshot

Playwright screenshot saved to: `w3-7-validation.png` (in Playwright output directory)

Validation result: **6/6 specs valid**, **38 total invariants**
