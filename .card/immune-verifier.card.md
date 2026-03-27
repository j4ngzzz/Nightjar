---
card-version: "1.0"
id: immune_verifier
title: Immune System - Dual Verifier (PBT + Symbolic)
status: draft
module:
  owns:
    - verify_invariant_pbt
    - verify_invariant_symbolic
    - PBTResult
    - PBTVerdict
    - SymbolicResult
    - SymbolicVerdict
  depends-on:
    hypothesis: "given, settings, strategies [REF-T03]"
    crosshair: "crosshair check CLI via subprocess [REF-T09]"
contract:
  inputs:
    - name: func_source
      type: str
      constraints: "non-empty Python source of the function to verify"
    - name: func_name
      type: str
      constraints: "name of the function in func_source"
    - name: invariant
      type: str
      constraints: "non-empty Python boolean expression; 'result' refers to return value"
    - name: preconditions
      type: list[str] | None
      constraints: "optional filter expressions applied before checking the invariant"
  outputs:
    - name: pbt_result
      type: PBTResult
      schema:
        verdict: "PASS | FAIL | ERROR"
        num_examples: int
        counterexample: dict | None
        error: str | None
    - name: symbolic_result
      type: SymbolicResult
      schema:
        verdict: "VERIFIED | COUNTEREXAMPLE | TIMEOUT | ERROR"
        counterexample: dict | None
        error: str | None
  errors:
    - Both functions return ERROR verdict on setup failure; never raise uncaught exceptions
invariants:
  - id: INV-01
    tier: property
    statement: "verify_invariant_pbt with empty invariant returns PBTResult(verdict=PBTVerdict.ERROR) with a non-empty error string"
    rationale: "An empty invariant expression is not a verifiable property; ERROR must be returned immediately without running Hypothesis"
  - id: INV-02
    tier: property
    statement: "verify_invariant_pbt with empty func_source returns PBTResult(verdict=PBTVerdict.ERROR)"
    rationale: "No function source means no function to test; ERROR prevents running Hypothesis against undefined code"
  - id: INV-03
    tier: property
    statement: "verify_invariant_pbt PASS verdict implies counterexample is None"
    rationale: "A passing run found no counterexample; the counterexample field must not be populated on success"
  - id: INV-04
    tier: property
    statement: "verify_invariant_pbt FAIL verdict implies counterexample is a non-None dict containing at least one entry"
    rationale: "A FAIL must always include the specific input that violated the invariant for downstream diagnosis"
  - id: INV-05
    tier: property
    statement: "verify_invariant_symbolic with empty invariant returns SymbolicResult(verdict=SymbolicVerdict.ERROR)"
    rationale: "Same guard as PBT — empty expressions must be rejected before CrossHair is invoked"
  - id: INV-06
    tier: property
    statement: "verify_invariant_symbolic replaces standalone 'result' with '__return__' in PEP316 docstring contracts before calling CrossHair"
    rationale: "CrossHair's PEP316 mode uses __return__ for the return value; failing to translate causes all postconditions to be silently ignored"
  - id: INV-07
    tier: safety
    statement: "verify_invariant_symbolic returns SymbolicResult(verdict=SymbolicVerdict.ERROR) when CrossHair is not installed; never raises FileNotFoundError or ImportError to the caller"
    rationale: "CrossHair absence is a deployment issue, not a logic error; the verifier must degrade gracefully"
  - id: INV-08
    tier: safety
    statement: "verify_invariant_symbolic returns SymbolicResult(verdict=SymbolicVerdict.TIMEOUT) when CrossHair subprocess exceeds timeout_sec; never raises subprocess.TimeoutExpired"
    rationale: "Timeout is a normal outcome for complex invariants; the pipeline must handle it as a non-error verdict"
---

## Intent

Provide dual verification for candidate invariants using complementary approaches:

**PBT verifier** (`verifier_pbt.py`) — generates 1000+ random inputs with Hypothesis [REF-T03], calls the function with each input, and asserts the invariant on the result. Preconditions are applied via Hypothesis `assume()`. Returns PASS (no counterexample found), FAIL (with the falsifying input), or ERROR (setup/compilation failure).

**Symbolic verifier** (`verifier_symbolic.py`) — injects PEP316 `pre:`/`post:` contracts into the function's docstring and runs CrossHair [REF-T09] to prove the invariant holds for all valid inputs via Z3-backed symbolic execution. Returns VERIFIED, COUNTEREXAMPLE (with the falsifying input), TIMEOUT, or ERROR.

The two verifiers are designed to be used together in the pipeline (`_is_verified` in pipeline.py): either passing is sufficient by default; both must pass when `require_both_verifiers=True`. This complementarity is grounded in [REF-P10]: PBT raises correction rates from 46.6% to 75.9%.

## Acceptance Criteria

### Story 1 — PBT Finds Counterexamples for Invalid Invariants (P0)

**As a** pipeline stage, **I want** PBT to return a FAIL verdict with the counterexample when an invariant is false, **so that** weak invariants are excluded from the spec.

1. **Given** a function `def f(x: int): return x + 1` and invariant `result > 10`, **When** verify_invariant_pbt is called, **Then** returns PBTResult(verdict=FAIL) with counterexample containing the x value
2. **Given** a function `def f(x: int): return abs(x)` and invariant `result >= 0`, **When** verify_invariant_pbt is called, **Then** returns PBTResult(verdict=PASS)

### Story 2 — Symbolic Verifier Degrades Gracefully (P0)

**As a** deployment environment, **I want** CrossHair absence to produce ERROR verdict, **so that** missing tools don't crash the pipeline.

1. **Given** CrossHair is not installed, **When** verify_invariant_symbolic is called, **Then** returns SymbolicResult(verdict=ERROR, error contains "CrossHair not installed")

### Story 3 — 'result' Is Correctly Translated for PEP316 (P0)

**As a** symbolic verifier, **I want** 'result' in invariant expressions to be translated to '__return__', **so that** CrossHair's PEP316 mode recognizes postconditions correctly.

1. **Given** invariant="result >= 0", **When** _normalize_invariant is called, **Then** returns "__return__ >= 0"
2. **Given** invariant="results >= 0" (plural), **When** _normalize_invariant is called, **Then** returns "results >= 0" (not modified — word boundary match)

## Functional Requirements

- **FR-001**: verify_invariant_pbt MUST use Hypothesis `assume()` to apply preconditions, not `if` guards that silently skip
- **FR-002**: verify_invariant_pbt MUST pass `suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]` to avoid false ERROR results on legitimate slow strategies
- **FR-003**: verify_invariant_symbolic MUST write source to a temporary file and clean it up in a `finally` block
- **FR-004**: verify_invariant_symbolic MUST use `--per_condition_timeout` CLI flag when calling CrossHair
- **FR-005**: verify_invariant_pbt MUST run with `Phase.generate` only (no shrinking) for speed in the verification context
- **FR-006**: Both verifiers MUST handle the case where func_source compiles but func_name is not found in the resulting namespace, returning ERROR with an informative message
