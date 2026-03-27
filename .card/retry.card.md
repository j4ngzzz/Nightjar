---
card-version: "1.0"
id: retry
title: Clover Retry Loop and BFS Proof Search
status: active
generated-by: nightjar-dogfood
module:
  owns: [run_with_retry, run_bfs_search, build_repair_prompt, build_cegis_repair_prompt, parse_dafny_counterexample, extract_counterexample_from_stage]
  depends-on:
    litellm: ">=1.0"
    nightjar.verifier: "run_pipeline"
    nightjar.types: "CardSpec, VerifyResult, VerifyStatus"
    nightjar.stages.formal: "attempt_annotation_repair"
contract:
  inputs:
    - name: spec
      type: CardSpec
      constraints: "parsed .card.md specification"
    - name: code
      type: str
      constraints: "initial generated code to verify"
    - name: max_retries
      type: int
      constraints: "non-negative integer; default 5"
  outputs:
    - name: result
      type: VerifyResult
      schema: {}
  errors: []
invariants:
  - id: INV-001
    tier: property
    statement: "run_with_retry makes at most max_retries + 1 + annotation_retries calls to run_pipeline"
    rationale: "Bounded retry prevents infinite loops; total pipeline calls = 1 initial + up to annotation_retries + up to max_retries"
  - id: INV-002
    tier: property
    statement: "run_with_retry returns a VerifyResult with verified=True and retry_count=0 when the initial code passes verification"
    rationale: "No retry should occur if the first verification passes"
  - id: INV-003
    tier: property
    statement: "run_with_retry always returns a VerifyResult (never raises), even after exhausting all retries"
    rationale: "Exhausted retries result in human escalation, not an exception"
  - id: INV-004
    tier: property
    statement: "parse_dafny_counterexample returns None when the output string contains no counterexample block"
    rationale: "Most Dafny failures do not include counterexamples; None is the correct absence value"
  - id: INV-005
    tier: property
    statement: "run_bfs_search makes at most 1 + (max_depth * beam_width) calls to run_pipeline"
    rationale: "BFS is bounded: 1 initial check + at most max_depth*beam_width candidate verifications"
  - id: INV-006
    tier: property
    statement: "extract_counterexample_from_stage returns None for any stage with name != 'formal'"
    rationale: "Only Dafny formal stages produce counterexamples; all other stages return None"
---

## Intent

Implement the Clover-pattern closed-loop retry [REF-C02, REF-P03]: generate → verify → repair → re-verify.
On verification failure, collects structured error context (and CEGIS counterexamples when available
[REF-NEW-03]), builds a repair prompt, calls the LLM via litellm, and re-runs the full pipeline.
Before each full LLM regeneration, attempts surgical annotation repair (insert one invariant/assert
at the error location) per dafny-annotator greedy pattern [REF-T02]. Also implements BFS proof
search [CR-12] as a tree-structured alternative to flat retry — beam of candidates per depth level
with verifier-in-the-loop scoring.

## Acceptance Criteria

### Story 1 — Successful First Attempt (P0)

**As a** nightjar user, **I want** the retry loop to skip retries when initial code passes, **so that** fast paths stay fast.

1. **Given** code that passes verification immediately, **When** run_with_retry is called, **Then** returns VerifyResult.verified=True with retry_count=0
2. **Given** code that fails all retries, **When** run_with_retry is called with max_retries=5, **Then** returns a VerifyResult with retry_count=5 and verified=False

### Story 2 — CEGIS Counterexample (P1)

**As a** nightjar pipeline, **I want** Dafny counterexamples to be included in the repair prompt, **so that** the LLM has concrete failing inputs to fix.

1. **Given** Dafny output with a counterexample block, **When** parse_dafny_counterexample is called, **Then** returns a non-empty dict of variable names to values
2. **Given** Dafny output without a counterexample block, **When** parse_dafny_counterexample is called, **Then** returns None

### Edge Cases

- annotation_repair returns None (no line numbers) → annotation phase skipped, falls through to full LLM repair
- BFS with max_depth=0 → only initial verification runs (beam never generated)
- NIGHTJAR_ANNOTATION_RETRIES env var missing or invalid → defaults to 3

## Functional Requirements

- **FR-001**: run_with_retry MUST try annotation repair before full LLM regeneration when formal stage fails
- **FR-002**: Full LLM repair MUST use CEGIS-style prompt when a counterexample is available
- **FR-003**: All LLM calls MUST go through litellm via _call_llm_with_prompt
- **FR-004**: run_with_retry MUST return a VerifyResult regardless of retry outcome
- **FR-005**: run_bfs_search MUST select the highest-scoring candidate (fewest errors) at each depth
