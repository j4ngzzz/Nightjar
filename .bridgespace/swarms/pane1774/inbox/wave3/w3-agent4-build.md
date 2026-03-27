# W3-4 Report — Build & Security Module Specs

**Agent:** W3-4
**Date:** 2026-03-27
**Task:** Write accurate .card.md specs for Nightjar's build and security modules

---

## Summary

6 specs written, all YAML-valid, 0 parse errors, 34 total invariants.

| Spec | Source | Invariants | Parse |
|------|--------|-----------|-------|
| `.card/compiler.card.md` | `src/nightjar/compiler.py` | 5 | PASS |
| `.card/lock.card.md` | `src/nightjar/lock.py` | 6 | PASS |
| `.card/ship.card.md` | `src/nightjar/ship.py` | 5 | PASS |
| `.card/safety-gate.card.md` | `src/nightjar/safety_gate.py` | 6 | PASS |
| `.card/cache.card.md` | `src/nightjar/cache.py` | 7 | PASS |
| `.card/audit.card.md` | `src/nightjar/audit.py` | 5 | PASS |

Screenshot: `.card/w3-4-validation-screenshot.png`

---

## Key Invariants Per Module

**compiler:** Target validation is a hard gate before subprocess (SUPPORTED_TARGETS frozenset). On timeout, success=False and stderr contains the timeout message. DAFNY_PATH env var respected.

**lock:** SHA-256 only (hashlib.sha256). Stdlib modules never appear (sys.stdlib_module_names). Entries with empty hashes silently dropped. Output sorted by package name for stable diffs. parse_lock_entry() returns None on non-matching lines (no exceptions).

**ship:** hash_artifact() returns "" on missing path (never raises). Directory hashing includes relative posix paths for structure sensitivity. UTC ISO-8601 timestamp set in __post_init__. write_provenance() creates parent dirs and writes indent=2 JSON.

**safety-gate:** Regression = PASS→FAIL or PASS→TIMEOUT only. SKIP→FAIL and MISSING→FAIL are not regressions (per Scout 7 S12.S1). verify.json only updated on no-regression. Confidence drop is non-blocking warning only. load_previous_result() returns None on missing/malformed JSON.

**cache:** is_cache_valid() requires verified=True (failed caches never hit). hash_stage_inputs() uses null-byte delimiters to prevent collision. should_skip_stage() never skips status="fail". check_early_cutoff() uses latest result hash (not input_hash) so it fires even when inputs change but output is identical. invalidate_cache("*") deletes all *.json.

**audit:** Read-only permissions (S_IRUSR|S_IRGRP|S_IROTH) enforced after every archive. DO-NOT-EDIT header idempotent (not prepended if already present). archive_artifact() returns False on missing source. is_audit_current() strips header before hashing for drift detection.

---

## Validation

HTML results page: `.card/w3-4-validation.html`
Screenshot confirms: 6 YAML VALID, 34 TOTAL INVARIANTS, 0 PARSE ERRORS
