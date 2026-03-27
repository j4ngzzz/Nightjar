# Bug Fix Report: Medium/Low Bugs Wave 3

**Date:** 2026-03-27
**Agent:** pane1774 bug-fix agent
**Result:** All 6 bugs fixed. 1267 tests pass, 0 regressions.

---

## Bug 5 — Stage ordering anomaly (MEDIUM)

**File:** `src/nightjar/verifier.py` — `run_pipeline()`

**Problem:** `stages` list returned as [0,1,2,3,5,4] because negation_proof (stage 5) was appended before stage 4.

**Fix:** Added `stages.sort(key=lambda s: s.stage)` immediately after all stages are collected and before building the final result. This ensures the list is always in stage-number order regardless of insertion order.

---

## Bug 6 — Badge prints exit code as error (MEDIUM)

**File:** `src/nightjar/cli.py` — `badge` command

**Problem:** `generate_badge_url_from_report()` silently swallows `FileNotFoundError` internally and returns an UNKNOWN badge URL, so the outer `except FileNotFoundError` in the CLI never fired. No useful error was shown to the user.

**Fix:** Added an explicit `os.path.exists(report)` check at the top of the badge try-block. If the file is missing, it immediately echoes "No verification report found. Run `nightjar verify` first." and exits with `EXIT_CONFIG_ERROR`.

---

## Bug 7 — Build accepts missing --target (MEDIUM)

**File:** `src/nightjar/cli.py` — `build` command Click option

**Problem:** `--target` defaulted to `None` in the Click decorator, relying on a config fallback deep in the call chain. If config was also missing, the value could be None when it reached LLM calls.

**Fix:** Changed the Click option `default=None` to `default="py"` so Python is always the target when not explicitly specified, before any config lookup or LLM calls.

---

## Bug 8 — Display shows (0.00) when confidence is None (MEDIUM)

**File:** `src/nightjar/display.py`

**Problem:** Four locations formatted `(confidence_val:.2f)` using `0.0` as fallback for `None` confidence, producing `(0.00)` in the trust level line.

**Fix:** All four display paths updated:
1. `format_verify_result()` Rich path — checks `result.confidence is not None`, omits parenthetical if None.
2. `_format_verify_result_plain()` plain path — same guard.
3. `RichStreamingDisplay._build_renderable()` streaming path — checks `pipeline_confidence_val != 0.0`.
4. `RichStreamingDisplay._build_plain()` plain streaming fallback — same guard.

When confidence is None, the trust line reads `Trust: FORMALLY_VERIFIED` (no score). When present it reads `Trust: FORMALLY_VERIFIED (0.95)`.

---

## Bug 9 — Init accepts empty/invalid names (LOW)

**File:** `src/nightjar/cli.py` — `init` command

**Problem:** Empty string or names with spaces/special chars could create malformed filenames.

**Note:** The Bug 4 (path traversal) agent had already added the regex validation block before this agent ran. The current code at lines 341-353 already contains the required `^[a-zA-Z][a-zA-Z0-9_-]*$` check with a clear error message, compatible with the path containment added by Bug 4. No duplicate code was needed.

---

## Bug 10 — Incremental pipeline missing negation_proof (LOW)

**File:** `src/nightjar/verifier.py` — `_build_incremental_noop_result()`

**Problem:** The full-cache-hit path synthesized stages [preflight, deps, schema, pbt, formal] (stages 0-4) but omitted negation_proof (stage 5), creating a discrepancy with `run_pipeline()` output.

**Fix:** Added a `StageResult(stage=5, name="negation_proof", status=VerifyStatus.SKIP, duration_ms=0)` append after the existing five synthetic stages. SKIP is correct for a noop result — nothing changed so negation proof is implicitly passing (cached).

---

## Test Results

```
1267 passed, 1 skipped in 80.20s
```

Zero regressions. The 1 skip was pre-existing.
