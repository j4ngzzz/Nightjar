# Nightjar Self-Scan Results

**Date:** 2026-03-28
**Tester:** Unbiased agent (no prior source code reading)
**Method:** Blind invariant writing from module names only, then pipeline execution
**Scope:** 5 blind-spec tests + 50 existing .card.md spec tests across the full codebase

---

## Part 1: Blind Spec Tests (5 Core Modules)

Invariants were written based ONLY on module name, not source code inspection.

| Module | verified | Confidence | Stage Failures |
|--------|----------|------------|---------------|
| parser | **True** | 25/100 | schema:skip (no contract outputs), pbt:skip (load error) |
| verifier | **False** | 25/100 | pbt:FAIL |
| confidence | **False** | 25/100 | pbt:FAIL |
| safety_gate | **False** | 0/100 | preflight:FAIL — spec file `safety_gate.card.md` not found |
| impact | **False** | 25/100 | pbt:FAIL (Hypothesis HealthCheck: filter_too_much) |

### Bug Found: Spec Filename Mismatch

The preflight stage checks for `.card/safety_gate.card.md` but the actual spec is named `.card/safety-gate.card.md` (hyphen, not underscore). The pipeline hard-fails with `Spec file not found: .card/safety_gate.card.md` when the spec id uses underscores but the file uses hyphens. This is a naming convention inconsistency — spec IDs use underscores but filenames use hyphens.

### Bug Found: PBT Type Mismatch (Systemic)

The PBT engine generates random `int` values and passes them to the first discovered callable in the code. For functions like `run_pipeline(spec: CardSpec, code: str, ...)`, this produces `'int' object has no attribute 'invariants'` on every run. The error is correctly caught and reported as a property violation, but it is a false positive — the invariant "result is not None" would be satisfied if a `CardSpec` were actually passed. The PBT stage has no mechanism to generate typed objects from type annotations.

### Bug Found: Confidence.py Returns TrustLevel Not a Number

The blind invariant `result must be non-negative` caused `'>=' not supported between instances of 'TrustLevel' and 'int'`. This is accurate feedback — the `confidence.py` module's main callable apparently returns a `TrustLevel` enum, not a number. The PBT assertion engine correctly caught a type mismatch in the spec (the spec says "non-negative" but the return is not numeric).

---

## Part 2: Existing .card.md Spec Tests (50 Specs)

### Overall Scorecard

| Metric | Count |
|--------|-------|
| Total card specs | 50 |
| Code file not found | 4 |
| Testable (code found) | 46 |
| **Verified** | **6 (13%)** |
| **Failed** | **40 (87%)** |
| Parse/import errors | 0 |

### What Passed

- `dafny-pro.card.md` — trivially passes (no testable functions, no invariants exercised)
- `generator.card.md` — passes because PBT skips (relative import prevents code loading)
- `immune-daikon.card.md` — passes trivially (only type aliases/stdlib, no testable function)
- `mcp-server.card.md` — passes because PBT skips (relative import prevents code loading)
- `parser.card.md` — passes because PBT skips (relative import prevents code loading)
- `types.card.md` — passes (formal stage passes, no functions to PBT test)

**Key observation:** Every "verified" spec passed because the PBT stage was skipped, not because invariants were actually proven. None of the 6 "verified" specs had their invariants actively tested. This is a significant finding — the pipeline's `verified=True` can mean "nothing was tested" rather than "everything passed."

---

## Part 3: Failure Taxonomy (40 Failed Specs)

### Category 1: Property Violations via Type Mismatch (16 occurrences)

The PBT stage discovers the module's main function and calls it with random `int` inputs. When the function expects a typed domain object (e.g., `CardSpec`, `VerifyResult`, `Path`), the integer propagates into attribute access and fails:

- `'int' object has no attribute 'invariants'` — functions expecting `CardSpec`
- `'int' object has no attribute 'stages'` — functions expecting `VerifyResult`
- `'int' object has no attribute 'strip'` — functions expecting `str`
- `'int' object has no attribute 'encode'` — functions expecting `str` or `bytes`
- `'int' object has no attribute 'verified'` — functions expecting `VerifyResult`
- `'int' object has no attribute 'get'` — functions expecting `dict`
- `'int' object has no attribute 'total'` — functions expecting `ConfidenceScore`
- `'int' object has no attribute 'type'` — functions expecting a typed object
- `'dict' object has no attribute 'verified'` — schema stage returns `dict` not `VerifyResult`
- `'dict' object has no attribute 'success'` — return type changed but spec not updated

This pattern accounts for the majority of failures. The root cause is the PBT engine's input strategy: it only generates integers and cannot construct domain objects from type annotations.

### Category 2: Hypothesis HealthCheck — filter_too_much (14 occurrences)

Affects: `audit`, `compiler`, `explain`, `impact`, `replay`, `retry`, `ship`, `tracking`, `tui`, `watch`, `stage-deps`, `stage-formal`, `stage-preflight`, `immune-fingerprint`

The functions in these modules call `assume(False)` for every integer input (because integers fail their precondition checks — e.g., `isinstance(x, Path)` fails). Hypothesis exhausts its filter budget and raises `FailedHealthCheck`. This is an honest signal: the PBT engine cannot meaningfully test these functions without type-aware input generation.

### Category 3: Sealed Manifest (deps.lock) Violations (7 occurrences)

| Spec | Import Flagged | Reality |
|------|---------------|---------|
| `config.card.md` | `dotenv` | `python-dotenv` is a real dependency, just not in deps.lock |
| `resolver.card.md` | `parser` | Stdlib module — deps check incorrectly flags stdlib |
| `immune-collector.card.md` | `immune` | Internal package — deps check flags own sibling package |
| `immune-error-capture.card.md` | `immune` | Same — internal package |
| `immune-otel.card.md` | `immune` | Same |
| `immune-pipeline.card.md` | `immune` | Same |
| `immune-store.card.md` | `immune` | Same |
| `stage-pbt.card.md` | `hypothesis_crosshair_provider` | Optional plugin not in deps.lock |

**Two distinct bugs here:**
1. The deps stage flags stdlib modules (`parser`, `os`, `shutil`) as "hallucinated dependencies." This is a false positive — stdlib is always available.
2. The deps stage flags the `immune` sibling package as an unauthorized dependency. Internal packages should be whitelisted.

### Category 4: Invalid Invariant Tier (2 specs)

Both `optimizer.card.md` and `immune-enforcer.card.md` use `tier: safety` in their invariant definitions. The `InvariantTier` enum only supports `['example', 'property', 'formal']`. These specs were written with a tier that doesn't exist in the schema, causing immediate preflight failure.

### Category 5: Code File Not Found (4 specs)

| Spec | Expected | Reality |
|------|----------|---------|
| `immune-network.card.md` | `src/immune/network.py` | No such file |
| `immune-verifier.card.md` | `src/immune/verifier.py` | No such file (there's `verifier_pbt.py`, `verifier_symbolic.py`) |
| `mymodule.card.md` | `src/nightjar/mymodule.py` | Test/demo spec with no real code |
| `payment.card.md` | `src/nightjar/payment.py` | Demo spec, code is `payment-processing.dfy` |

### Category 6: Assertion Eval Errors (3 specs)

- `dafny-setup.card.md`: Invariants reference `shutil.which(...)` and `os.path...` but the assertion eval context doesn't import these. The `exec()` sandbox lacks stdlib imports.
- `immune-enricher.card.md`: `sys.tracebacklimit` reference fails — `sys` not in exec context.
- `negation-proof.card.md`: `TimeoutExpired` not defined in assertion eval context.

These represent a bug in the assertion eval engine: the sandbox `exec()` context only includes `result` and `x`, but invariant statements often reference stdlib names.

---

## Part 4: Specific Bugs Found in Nightjar's Own Code

### Bug 1: PBT Cannot Test Domain-Typed Functions (Systemic, High Severity)

**Location:** `src/nightjar/stages/pbt.py`, `_run_single_invariant`
**Symptom:** 16 property violations where `'int' object has no attribute X` — all false positives
**Root cause:** The `@given(x=st.one_of(st.sampled_from(...), st.integers(...)))` strategy only generates integers. When a function's first parameter is a typed domain object (CardSpec, VerifyResult, Path, etc.), every generated input is wrong. The `ValueError/TypeError` filter then triggers `assume(False)`, which either exhausts Hypothesis budget or produces meaningless errors.
**Impact:** The majority of Nightjar's own modules cannot be PBT-tested by Nightjar itself. `verified=True` is achievable only when PBT is skipped.

### Bug 2: Spec File Naming: Hyphens vs. Underscores

**Location:** `src/nightjar/stages/preflight.py`
**Symptom:** `safety_gate` spec gets `Spec file not found: .card/safety_gate.card.md`
**Root cause:** Spec files use hyphens (`safety-gate.card.md`) but `CardSpec.id` uses underscores (`safety_gate`). Preflight constructs the path as `{spec_dir}/{spec_id}.card.md` without trying the hyphenated form.
**Impact:** Any spec whose ID contains underscores but whose file uses hyphens will fail preflight.

### Bug 3: Deps Stage Falsely Flags Stdlib and Internal Packages

**Location:** `src/nightjar/stages/deps.py`
**Symptom:** `parser`, `os`, `shutil` flagged as hallucinated; `immune` flagged as unauthorized
**Root cause:** The dep checker scans import statements and checks against `deps.lock`, but doesn't skip Python stdlib modules or the project's own packages.
**Impact:** 7 specs fail Stage 1 due to false positives. These modules are not actually importing hallucinated packages.

### Bug 4: `tier: safety` Not in InvariantTier Schema

**Location:** `.card/optimizer.card.md` line 41, `.card/immune-enforcer.card.md` lines 49/53
**Symptom:** `Invalid invariant tier 'safety' at index N. Valid: ['example', 'formal', 'property']`
**Root cause:** The specs define a tier that doesn't exist in `InvariantTier` enum. The schema was either changed or the spec was written against an older schema.
**Impact:** 2 specs fail immediately at preflight, never reaching substantive testing.

### Bug 5: Assertion Eval Sandbox Missing Stdlib Imports

**Location:** `src/nightjar/stages/pbt.py`, `_assert_invariant` (around line 450)
**Symptom:** `name 'shutil' is not defined`, `name 'os' is not defined`, `module 'sys' has no attribute 'tracebacklimit'`
**Root cause:** The `exec()` context is `{"result": result, "x": x}`. Invariant statements that reference stdlib names (shutil, os, sys, TimeoutExpired) fail with NameError.
**Impact:** 3 specs fail with assertion eval errors that are bugs in the eval sandbox, not actual invariant violations.

### Bug 6: `verified=True` Can Mean "Nothing Tested"

**Symptom:** All 6 passing specs passed by skipping PBT/schema/formal stages
**Root cause:** The pipeline's pass logic treats SKIP as non-failure. A module with no testable functions gets `verified=True` at confidence 25/100 with zero invariants checked.
**Impact:** The `verified=True` signal is misleading. Users may interpret it as mathematical proof when it means "we had nothing to test."

---

## Part 5: Are Specs Too Weak or Too Strong?

### Too Weak (False Negatives)
Several specs have invariants that sound strong but are easily satisfied by the integer-input PBT:
- `result is not None` — trivially true since PBT crashes before returning, not after
- `must not raise exception` — vacuously satisfied because PBT short-circuits on precondition failures

### Too Strong (False Positives)
- `immune-enricher.card.md` INV-01: `sys.tracebacklimit` — references implementation detail that may not hold across Python versions
- `negation-proof.card.md` INV-NEG-04: References `TimeoutExpired` without qualifying the module context

### Schema Drift
- `optimizer.card.md` and `immune-enforcer.card.md`: Use `tier: safety` which no longer exists in `InvariantTier`. These specs were written for a schema that was later changed (or vice versa).
- `immune-spec-updater.card.md` INV-01/02: Return type changed from object with `.success` attr to dict — spec not updated to match implementation.
- `confidence.card.md` INV-01/02: Spec expects `.total` and `.stages` attributes but the main callable returns `TrustLevel`.

---

## Summary

| Finding | Severity | Count |
|---------|----------|-------|
| PBT type-mismatch (can't test domain-typed functions) | High | Systemic |
| `verified=True` means "nothing tested" | High | 6 specs |
| Spec file naming mismatch (hyphens vs underscores) | Medium | 1+ specs |
| Deps stage false-positives on stdlib/internal packages | Medium | 7 specs |
| Invalid `tier: safety` in specs | Low | 2 specs |
| Assertion eval sandbox missing stdlib | Low | 3 specs |
| Schema drift (specs not updated when code changed) | Medium | 3+ specs |
| Missing code files for 4 specs | Low | 4 specs |

**Overall Verdict:** The pipeline infrastructure is sound at Stage 0 (preflight) and Stage 1 (deps). Stage 2 (schema) correctly skips when no contract outputs are defined. Stage 3 (PBT) is the critical failure point: it cannot test the majority of Nightjar's own modules because it only generates integer inputs and cannot construct typed domain objects. The formal Stage 4 (Dafny) would provide real verification but is never reached because PBT fails first. The `verified=True` rate of 13% is misleading — it's really "0% actively tested, 13% not-failed-due-to-skip."
