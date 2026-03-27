---
card-version: "1.0"
id: explain
title: Verification Failure Explainer
status: active
module:
  owns: [load_report, explain_failure, format_explanation, explain_with_llm, ExplainOutput]
  depends-on:
    litellm: "litellm>=1.0"
    nightjar.types: "internal"
contract:
  inputs:
    - name: contract_path
      type: str
      constraints: "path to a .card.md spec file; used to locate adjacent verify.json"
    - name: report
      type: dict
      constraints: "parsed verify.json report dict; may be empty or malformed"
  outputs:
    - name: explanation
      type: ExplainOutput
      schema: {}
    - name: text
      type: str
      schema: {}
  errors: []
invariants:
  - id: INV-01
    tier: property
    statement: "explain_failure returns ExplainOutput with failed_stage == -1 when no stage in the report has status 'fail' or 'timeout'"
    rationale: "The caller (CLI explain command) uses failed_stage == -1 to detect passing reports"
  - id: INV-02
    tier: property
    statement: "load_report returns None on OSError, UnicodeDecodeError, or json.JSONDecodeError — it never raises"
    rationale: "The CLI must handle missing or corrupt verify.json gracefully without a traceback"
  - id: INV-03
    tier: property
    statement: "explain_with_llm never raises; on any LLM exception it returns explanation.suggested_fix or a fallback string"
    rationale: "The explain command must always produce output even when the LLM is unavailable"
  - id: INV-04
    tier: property
    statement: "explain_with_llm reads the model name from os.environ.get('NIGHTJAR_MODEL') and never hardcodes a model string"
    rationale: "Anti-pattern: DO NOT hardcode model names — NIGHTJAR_MODEL must control all LLM calls"
  - id: INV-05
    tier: example
    statement: "_get_suggested_fix('pbt', 'fail') returns the PBT-specific advice string containing 'counterexample'"
    rationale: "Stage-specific fix suggestions from _FIX_SUGGESTIONS are tested by stage name"
  - id: INV-06
    tier: example
    statement: "_get_suggested_fix(stage_name, 'timeout') returns the _TIMEOUT_FIX string regardless of stage_name"
    rationale: "Timeout is a cross-stage condition with its own dedicated advice"
---

## Intent

The explain module transforms raw verification failure reports (`.card/verify.json`) into human-readable explanations. It has two modes: a fast heuristic path (`explain_failure` + `format_explanation`) that works offline and produces structured `ExplainOutput` objects, and an LLM-enhanced path (`explain_with_llm`) that calls litellm to turn cryptic Dafny/SMT errors into plain English with a suggested fix. Both paths fall back gracefully — the heuristic path always produces output, and the LLM path falls back to the heuristic if the LLM call fails.

## Acceptance Criteria

### Story 1 — Failure Analysis (P0)

**As a** developer, **I want** `nightjar explain --spec my.card.md` to show which stage failed and what the counterexample was, **so that** I understand what to fix without reading raw Dafny output.

1. **Given** a verify.json with stage 3 (pbt) status=fail and a counterexample, **When** explain_failure is called, **Then** ExplainOutput.failed_stage == 3 and counterexamples is non-empty
2. **Given** a verify.json where all stages passed, **When** explain_failure is called, **Then** ExplainOutput.failed_stage == -1

### Story 2 — LLM Enhancement (P1)

**As a** developer, **I want** an LLM-powered plain English explanation of why verification failed, **so that** I don't need to understand SMT solver output.

1. **Given** a valid ExplainOutput, **When** explain_with_llm is called with NIGHTJAR_MODEL set, **Then** returns a non-empty string
2. **Given** the LLM call throws any exception, **When** explain_with_llm is called, **Then** returns explanation.suggested_fix without raising

### Edge Cases

- verify.json does not exist → load_report returns None
- verify.json contains malformed JSON → load_report returns None
- ExplainOutput with empty error_messages → format_explanation omits the Errors section
- Unknown stage name in _get_suggested_fix → returns a generic fallback message

## Functional Requirements

- **FR-001**: load_report MUST check spec_dir/verify.json first, then .card/verify.json as fallback
- **FR-002**: explain_failure MUST select the FIRST failed/timeout stage (not the last)
- **FR-003**: format_explanation MUST include a stages summary section at the end
- **FR-004**: explain_with_llm MUST use max_tokens=512 and temperature=0.2 for the LLM call
- **FR-005**: ExplainOutput.root_cause field MUST default to empty string ""
