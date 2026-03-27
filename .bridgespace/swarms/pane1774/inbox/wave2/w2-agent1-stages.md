# W2-Agent1-Stages Report

**Agent:** W2-1
**Date:** 2026-03-27
**Commit:** ref: CrossHair backend + deal preflight + sbomlyze drift [Scout 9 W2-1]

---

## Summary

All 3 stage upgrades implemented and tested. 1,260/1,265 tests pass; 5 failures are pre-existing (CLI `init` template missing `card-version` — not touched by this agent).

---

## Task 1: CrossHair + Hypothesis Backend (`pbt.py`)

**Source researched:** `pschanely/hypothesis-crosshair` (PyPI: `hypothesis-crosshair`)

**Key finding:** CrossHair's Hypothesis integration lives in a *separate* package (`hypothesis-crosshair`, not `crosshair`). It self-registers as a backend via an entry-point hook at import time:
```
hypothesis_crosshair_provider:_hypothesis_setup_hook
→ AVAILABLE_PROVIDERS["crosshair"] = CrossHairPrimitiveProvider
```
Activation requires only `settings(backend="crosshair")` — no test code changes.

**Implementation:** Added `_make_pbt_settings()` in `pbt.py`:
- Checks `NIGHTJAR_CROSSHAIR_BACKEND=1` env var
- If set and `hypothesis-crosshair` is installed: returns `settings(deadline=None, database=None, backend="crosshair")`
- Falls back silently to `NIGHTJAR_PBT_SETTINGS` if package is unavailable (ImportError)
- Modified `run_pbt` to call `_make_pbt_settings()` instead of using `NIGHTJAR_PBT_SETTINGS` directly

**Behavior difference when enabled:** CrossHair uses Z3 SMT solver to exhaustively enumerate symbolic paths rather than random sampling. Path exhaustion signals `BackendCannotProceed("verified")` — the property is proven for ALL inputs in the strategy space, not just sampled ones. `deadline=None` → CrossHair defaults to 2.5s per SMT path.

**Gate:** `NIGHTJAR_CROSSHAIR_BACKEND=1` — opt-in, zero impact by default.

---

## Task 2: deal Partial-Execution Linter (`preflight.py`)

**Source researched:** `life4/deal` linter internals (`_contract.py`, `_template.py`, `_rules.py`, `value.py`)

**Key finding:** deal's linter does NOT enumerate boundary values — it extracts *literal values from source code* and executes contract lambdas against them. For dead constraint detection in our context (where we have expression strings, not source code callsites), the relevant pattern is: `exec(compile(expr, mode='exec'), fresh_namespace)`, read `result` out, catch only `NameError` for silent skip (external deps = unknowable), treat all other outcomes as decidable.

**Implementation:** Added to `preflight.py`:

1. `_BOUNDARY_VALUES` — 15 representative inputs: `[0, -1, 1, sys.maxsize, -(sys.maxsize+1), 0.0, -1.0, "", "x", None, [], [0], [1,2], {}, False, True]`
2. `_UNKNOWN` sentinel — marks undecidable results (per deal's UNKNOWN pattern)
3. `_SAFE_BUILTINS` — restricted exec namespace allowing `len`, `isinstance`, `abs`, etc.
4. `_try_eval_invariant(expr, val)` — compiles `bool({expr})`, execs with `{x: val, result: val}`, returns bool or `_UNKNOWN`. SyntaxError (natural language) → UNKNOWN, NameError → UNKNOWN, other exceptions → UNKNOWN.
5. `check_dead_constraints(invariants)` — for each invariant, collects decided outcomes across all boundary values. All-True → `dead_constraint` error. All-False → `unsatisfiable_constraint` error. Mixed/undecidable → pass.
6. Wired into `run_preflight` as step 5.5, before the short-circuit check.

**Correctness notes:**
- Natural language invariants (all current fixtures) → SyntaxError → fully undecidable → skipped → no false positives
- `x >= 0` → False at val=-1 → mixed outcomes → not flagged
- `True` or `1 > 0` → all True → flagged as dead (correct)
- `len(result) >= 0` → all True for str/list values → flagged as dead (correct — len is always ≥ 0)

---

## Task 3: sbomlyze Drift Detection (`deps.py`)

**Source researched:** `rezmoss/sbomlyze` (`internal/analysis/drift.go`)

**Key finding:** sbomlyze's `ClassifyDrift` uses strict priority ordering: **integrity > version > metadata**. Integrity drift (hash changed, version unchanged) is evaluated BEFORE version drift so the `high` signal is reserved exclusively for the anomalous case. The cryptographic ground truth (hash) is treated as authoritative; when it disagrees with the declared version, the version declaration is untrusted.

**Implementation:** Added `detect_drift(current, baseline)` in `deps.py`:

- Iterates over union of all package names (sorted)
- `added`/`removed` → `severity: info`
- `hash_changed AND NOT version_changed` → `drift_type: integrity`, `severity: high` (supply chain signal)
- `version_changed` → `drift_type: version`, `severity: info`
- Metadata drift (license/maintainer) → not detectable from deps.lock format (hash+version only) — documented as a limitation

Added optional `baseline_lock_path` parameter to `run_deps_check`:
- If provided, parses baseline, calls `detect_drift(allowed, baseline)`
- Integrity events → `_fail(start, drift_errors)` — Stage 1 FAIL
- Version/added/removed → ignored in Stage 1 flow (informational)
- No baseline → skip drift check entirely (backward compatible)

**Supply chain rationale:** Hash-without-version-bump is the XZ utils / event-stream attack vector: an attacker with registry write access replaces a package artifact at an existing version. Version-only comparison misses this. Hash comparison catches it without requiring a vulnerability database.

---

## Files Modified

| File | Lines Added | What |
|------|------------|------|
| `src/nightjar/stages/pbt.py` | +31 | `_make_pbt_settings()`, `run_pbt` uses it |
| `src/nightjar/stages/preflight.py` | +92 | imports, constants, `_try_eval_invariant`, `check_dead_constraints`, wired into `run_preflight` |
| `src/nightjar/stages/deps.py` | +87 | `detect_drift()`, `run_deps_check` extended with optional `baseline_lock_path` |

## Test Results

```
36 stage-specific tests: PASS (pbt: 15, preflight: 9, deps: 12)
Full suite (not integration): 1260 passed, 1 skipped, 7 deselected
Pre-existing failures: 5 (CLI init template missing card-version — not this agent's scope)
```
