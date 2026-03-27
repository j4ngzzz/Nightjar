---
card-version: "1.0"
id: safety-gate
title: Behavioral Safety Gate — Regression Detection
status: draft
module:
  owns: [check_regression(), load_previous_result(), save_verify_result(), run_safety_gate()]
  depends-on:
    nightjar.types: "internal"
  excludes:
    - "New failures on first run — no previous state means no regression"
    - "Performance regression — only stage pass/fail status is checked"
invariants:
  - id: INV-01
    tier: property
    statement: "A regression is defined strictly as: a stage whose previous status was PASS and whose new status is FAIL or TIMEOUT; SKIP→FAIL and MISSING→FAIL are never regressions"
    rationale: "Per Scout 7 S12.S1: only proven stages can regress; unproven stages cannot"
  - id: INV-02
    tier: property
    statement: "run_safety_gate() always passes (SafetyGateResult.passed=True) when no previous verify.json exists"
    rationale: "First run has no baseline to regress from"
  - id: INV-03
    tier: property
    statement: "run_safety_gate() saves the new result to verify.json only when no regressions are detected"
    rationale: "A regressing result must not overwrite the last-good baseline — the baseline must remain at the last passing state"
  - id: INV-04
    tier: property
    statement: "A confidence score drop (new < previous) produces a non-empty confidence_warning but does not set passed=False"
    rationale: "Confidence drop is informational only; it must not block the build per Scout 7 S12.S1"
  - id: INV-05
    tier: property
    statement: "load_previous_result() returns None (not an exception) for a missing file or malformed JSON"
    rationale: "Corrupted or absent verify.json must degrade gracefully to first-run behavior"
  - id: INV-06
    tier: property
    statement: "check_regression() ignores stages present in previous_result but absent from new_result (does not count absence as regression)"
    rationale: "Pipeline changes may legitimately add or remove stages; absence is not a failure"
---

## Intent

Compare each new verification run against the previous `verify.json`. Block the build if any previously-passing stage now fails or times out. On the first run (no baseline), always pass. Never allow a regressing result to overwrite the good baseline.

## Acceptance Criteria

### Story 1 — Detect Regression

**As a** build pipeline, **I want** regressions blocked, **so that** verified code cannot degrade silently.

1. **Given** Stage 3 was PASS before and is now FAIL, **When** `check_regression()` runs, **Then** `SafetyGateResult.passed is False` and `regressions` contains one entry for Stage 3
2. **Given** Stage 3 was PASS before and is now TIMEOUT, **When** `check_regression()` runs, **Then** `passed is False`
3. **Given** Stage 3 was SKIP before and is now FAIL, **When** `check_regression()` runs, **Then** `passed is True` (no regression)

### Story 2 — First Run Passes

1. **Given** no verify.json exists, **When** `run_safety_gate()` is called, **Then** `passed is True` and verify.json is written

### Story 3 — Baseline Preservation

1. **Given** a regression is detected, **When** `run_safety_gate()` returns, **Then** verify.json is NOT overwritten (old baseline preserved)
2. **Given** no regression is detected, **When** `run_safety_gate()` returns, **Then** verify.json IS updated to the new result

### Story 4 — Confidence Warning

1. **Given** new confidence is 70 and previous was 85, **When** `check_regression()` runs, **Then** `confidence_drop == 15` and `confidence_warning` is non-empty but `passed` remains True

## Functional Requirements

- **FR-001**: MUST detect PASS→FAIL and PASS→TIMEOUT transitions as regressions
- **FR-002**: MUST NOT detect SKIP→FAIL, MISSING→FAIL, or any PASS→PASS as regressions
- **FR-003**: MUST return `passed=True` when no previous verify.json exists
- **FR-004**: MUST only save new verify.json when `passed is True`
- **FR-005**: MUST handle `json.JSONDecodeError`, `KeyError`, and `ValueError` from malformed verify.json by returning None from `load_previous_result()`
- **FR-006**: MUST expose confidence drop as non-blocking warning with exact point delta
