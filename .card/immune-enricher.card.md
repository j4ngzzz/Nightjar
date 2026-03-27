---
card-version: "1.0"
id: immune_enricher
title: Immune System - LLM Invariant Enricher
status: draft
module:
  owns: [enrich_invariants, build_enrichment_prompt, _call_llm, _parse_assert_statements]
  depends-on:
    litellm: "litellm.completion [REF-T16]"
contract:
  inputs:
    - name: function_signature
      type: str
      constraints: "Python function def line or full signature; non-empty"
    - name: observed_invariants
      type: list[str]
      constraints: "list of Daikon-mined expressions; may be empty"
    - name: error_trace
      type: str | None
      constraints: "optional production error/exception trace"
  outputs:
    - name: result
      type: EnrichmentResult
      schema:
        candidates: list[CandidateInvariant]
        raw_response: str
        error: str | None
  errors:
    - EnrichmentResult with error set; never raises uncaught exceptions
invariants:
  - id: INV-01
    tier: property
    statement: "enrich_invariants always calls litellm.completion — never any provider SDK directly"
    rationale: "All LLM calls must go through litellm for model-agnosticism [REF-T16]; direct provider calls violate the anti-pattern rule"
  - id: INV-02
    tier: property
    statement: "enrich_invariants with any LLM exception returns EnrichmentResult with error set to a non-empty string and candidates as an empty list"
    rationale: "LLM failures are non-fatal; the enricher must never propagate exceptions to the pipeline"
  - id: INV-03
    tier: property
    statement: "build_enrichment_prompt returns a string containing the function_signature verbatim"
    rationale: "The LLM must see the exact function signature to generate correct parameter-aware assertions"
  - id: INV-04
    tier: property
    statement: "_parse_assert_statements returns only CandidateInvariant objects whose expression is non-empty"
    rationale: "Empty expressions are not valid Python assert conditions and must be filtered before reaching the verifiers"
  - id: INV-05
    tier: property
    statement: "_parse_assert_statements assigns confidence=0.8 when the parsed expression exactly matches an observed invariant, 0.7 when there is partial overlap, and 0.5 otherwise"
    rationale: "Observed-invariant corroboration is the only basis for confidence > 0.5; this must be deterministic"
  - id: INV-06
    tier: property
    statement: "enrich_invariants model selection reads NIGHTJAR_MODEL environment variable; falls back to 'deepseek/deepseek-chat' when unset"
    rationale: "Model name must never be hardcoded — NIGHTJAR_MODEL controls which litellm-supported model is used"
---

## Intent

Take raw Daikon-mined invariants, function signatures, and optional error traces, then use an LLM via litellm to generate semantically richer Python `assert` statements that would have caught the observed failure. This enrichment step converts low-level dynamic-analysis outputs into human-readable, verifiable property candidates ready for the dual-verifier stage.

The enrichment prompt follows the Agentic PBT pattern [REF-P15]: the LLM is presented with observed invariants plus failure context and asked to propose stronger executable assertions. All LLM calls must go through litellm [REF-T16].

## Acceptance Criteria

### Story 1 — Enrichment Is Model-Agnostic and Fail-Safe (P0)

**As a** pipeline stage, **I want** LLM failures to produce an EnrichmentResult with error set, **so that** a model outage never crashes the immune cycle.

1. **Given** litellm raises an exception, **When** enrich_invariants is called, **Then** returns EnrichmentResult with error set and candidates=[]
2. **Given** NIGHTJAR_MODEL=claude-sonnet-4-6, **When** _call_llm is called, **Then** litellm.completion is called with model="claude-sonnet-4-6"

### Story 2 — Prompt Contains All Required Context (P1)

**As a** formal verification LLM, **I want** the prompt to contain both the signature and observed invariants, **so that** I can generate parameter-aware assertions.

1. **Given** function_signature="def add(x: int, y: int) -> int" and observed_invariants=["x >= 0"], **When** build_enrichment_prompt is called, **Then** the returned string contains "def add(x: int, y: int) -> int" and "x >= 0"

### Story 3 — Parse Only Valid Assert Lines (P1)

**As a** downstream verifier, **I want** only syntactically valid assert expressions to reach me, **so that** I never receive empty-expression candidates.

1. **Given** LLM response contains a mix of assert lines and explanatory text, **When** _parse_assert_statements is called, **Then** only lines matching `assert <expr>` are returned as CandidateInvariants

## Functional Requirements

- **FR-001**: _call_llm MUST use litellm.completion; MUST NOT import or call openai, anthropic, or any other provider SDK directly
- **FR-002**: enrich_invariants MUST return EnrichmentResult with error populated on ANY exception from _call_llm; MUST NOT re-raise
- **FR-003**: _parse_assert_statements MUST skip lines starting with '#' or '```'
- **FR-004**: build_enrichment_prompt MUST include the error_trace block only when error_trace is not None
- **FR-005**: _call_llm MUST set temperature=0.3 and max_tokens=1000 for reproducibility
- **FR-006**: enrich_invariants MUST NOT mutate observed_invariants input list
