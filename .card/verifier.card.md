---
card-version: "1.0"
id: verifier
title: Verification Pipeline Orchestrator
status: active
generated-by: nightjar-dogfood
module:
  owns: [run_pipeline, run_pipeline_with_fallback, run_pipeline_parallel, run_pipeline_incremental, _stage_ok, _compute_complexity, _route_to_crosshair]
  depends-on:
    nightjar.types: "CardSpec, StageResult, VerifyResult, VerifyStatus"
    nightjar.stages.preflight: "run_preflight"
    nightjar.stages.deps: "run_deps_check"
    nightjar.stages.schema: "run_schema_check"
    nightjar.stages.pbt: "run_pbt"
    nightjar.stages.formal: "run_formal"
    crosshair: "optional — fallback and complexity routing"
contract:
  inputs:
    - name: spec
      type: CardSpec
      constraints: "parsed .card.md specification"
    - name: code
      type: str
      constraints: "generated source code string (may be empty)"
    - name: spec_path
      type: str
      constraints: "optional path to .card.md file for preflight; empty string is valid"
  outputs:
    - name: result
      type: VerifyResult
      schema: {}
  errors: []
invariants:
  - id: INV-001
    tier: property
    statement: "run_pipeline always returns a VerifyResult (never raises an exception)"
    rationale: "The pipeline is a data-transform function — errors are captured in StageResult.errors, not raised"
  - id: INV-002
    tier: property
    statement: "_stage_ok returns True for VerifyStatus.PASS and VerifyStatus.SKIP, and False for FAIL and TIMEOUT"
    rationale: "SKIP is not an error — missing deps.lock or no contract outputs are valid reasons to skip a stage"
  - id: INV-003
    tier: property
    statement: "run_pipeline returns VerifyResult.verified=False whenever any sequential stage (0, 1, or 4) returns FAIL or TIMEOUT"
    rationale: "Sequential short-circuit: a failing gate stage blocks all downstream stages"
  - id: INV-004
    tier: property
    statement: "run_pipeline always includes exactly the stages that ran in VerifyResult.stages, in execution order"
    rationale: "Short-circuited results include only completed stages — downstream callers must not assume 5 stages"
  - id: INV-005
    tier: property
    statement: "_compute_complexity returns a value > _COMPLEXITY_THRESHOLD for any code with a SyntaxError"
    rationale: "Unparseable code must route to full Dafny (safe default) not CrossHair-only"
  - id: INV-006
    tier: property
    statement: "run_pipeline_with_fallback always returns a non-None VerifyResult regardless of Dafny availability"
    rationale: "No user is ever blocked — graceful degradation through CrossHair then Hypothesis"
---

## Intent

Orchestrate the five-stage Nightjar verification pipeline: preflight (Stage 0), dependency check
(Stage 1), schema validation and property-based testing in parallel (Stages 2+3), negation-proof
spec validation (Stage 2.5), and formal verification (Stage 4). Implements short-circuit semantics:
any failing sequential stage stops the pipeline. Stages 2 and 3 always run in parallel. Stage 4
uses complexity-discriminated routing — simple functions (cyclomatic complexity + AST depth ≤ 5)
route to CrossHair symbolic execution; complex functions route to Dafny [REF-P06, REF-C02].

## Acceptance Criteria

### Story 1 — Happy Path (P0)

**As a** nightjar user, **I want** all five stages to run and produce a VerifyResult, **so that** I know whether my code satisfies the spec.

1. **Given** valid spec and code that passes all stages, **When** run_pipeline is called, **Then** VerifyResult.verified=True
2. **Given** valid spec and code that fails Stage 1, **When** run_pipeline is called, **Then** VerifyResult.verified=False with stages containing only stages 0 and 1

### Story 2 — Graceful Degradation (P1)

**As a** developer without Dafny installed, **I want** verification to fall back to CrossHair, **so that** I am never blocked.

1. **Given** Stage 4 Dafny timeout, **When** run_pipeline_with_fallback is called, **Then** CrossHair fallback runs
2. **Given** CrossHair not installed, **When** fallback is attempted, **Then** returns SKIP (not a hard failure)

### Edge Cases

- No deps.lock file → Stage 1 returns SKIP, pipeline continues
- Spec with no contract outputs → Stage 2 returns SKIP, pipeline continues
- Syntax error in code string → _compute_complexity returns high value → routes to Dafny
- NIGHTJAR_PARALLEL=1 env var → run_pipeline_parallel fans out stages 2, 3, 4 concurrently

## Functional Requirements

- **FR-001**: run_pipeline MUST short-circuit on FAIL or TIMEOUT at Stage 0 or Stage 1
- **FR-002**: Stages 2 and 3 MUST run concurrently in run_pipeline (ThreadPoolExecutor)
- **FR-003**: Stage 4 MUST NOT run if either Stage 2 or Stage 3 fails
- **FR-004**: VerifyResult.verified MUST equal True only if all completed stages are PASS or SKIP
- **FR-005**: _compute_complexity MUST return > _COMPLEXITY_THRESHOLD for SyntaxError inputs
- **FR-006**: run_pipeline_with_fallback MUST always return a VerifyResult (never raise)
