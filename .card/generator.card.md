---
card-version: "1.0"
id: generator
title: Code Generation Pipeline
status: active
generated-by: nightjar-dogfood
module:
  owns: [generate_code, run_analyst, run_formalizer, run_coder, run_spec_review, get_model, get_review_model, is_cross_validate_enabled]
  depends-on:
    litellm: ">=1.0"
    nightjar.types: "CardSpec, GenerationResult"
contract:
  inputs:
    - name: spec
      type: CardSpec
      constraints: "must be a CardSpec instance (not None)"
    - name: model
      type: str
      constraints: "optional; litellm-compatible model identifier"
  outputs:
    - name: result
      type: GenerationResult
      schema: {}
  errors:
    - TypeError
    - ValueError
invariants:
  - id: INV-001
    tier: property
    statement: "generate_code raises TypeError when spec is not a CardSpec instance"
    rationale: "Type guard at pipeline entry point — catches caller errors before any LLM call"
  - id: INV-002
    tier: property
    statement: "generate_code raises ValueError when any LLM stage (Analyst, Formalizer, Coder) returns empty content"
    rationale: "Empty LLM output cannot produce valid Dafny code; must fail fast with descriptive error"
  - id: INV-003
    tier: property
    statement: "generate_code returns a GenerationResult with non-empty dafny_code when all three LLM stages succeed"
    rationale: "Successful pipeline always produces Dafny output — the Coder stage raises ValueError on empty content"
  - id: INV-004
    tier: property
    statement: "get_model returns the override argument when override is non-empty, else NIGHTJAR_MODEL env var, else DEFAULT_MODEL"
    rationale: "Model selection priority must be deterministic: explicit > env > default"
  - id: INV-005
    tier: property
    statement: "GenerationResult.spec_id equals spec.id for any successful generate_code call"
    rationale: "Traceability — the result must record which spec produced it"
  - id: INV-006
    tier: property
    statement: "cross_validation_issues is always a list (never None) in any GenerationResult"
    rationale: "Downstream consumers iterate cross_validation_issues; None would cause AttributeError"
---

## Intent

Implement the three-agent Analyst → Formalizer → Coder code generation pipeline [REF-C03, REF-P07].
Takes a parsed CardSpec and produces a Dafny implementation ready for the verification pipeline.
The pipeline makes exactly three sequential LLM calls (six when cross-validation is enabled via
NIGHTJAR_CROSS_VALIDATE=1). All LLM calls go through litellm [REF-T16] for provider-agnosticism.

## Acceptance Criteria

### Story 1 — Full Pipeline (P0)

**As a** nightjar user, **I want** to generate Dafny code from a .card.md spec, **so that** verification can run.

1. **Given** a valid CardSpec, **When** generate_code is called, **Then** returns GenerationResult with non-empty dafny_code
2. **Given** a non-CardSpec argument, **When** generate_code is called, **Then** raises TypeError immediately

### Story 2 — Model Selection (P1)

**As a** CI pipeline, **I want** model selection to respect NIGHTJAR_MODEL env var, **so that** no model is hardcoded.

1. **Given** NIGHTJAR_MODEL=gpt-4o and no override, **When** get_model() is called, **Then** returns "gpt-4o"
2. **Given** an explicit override "claude-3-opus", **When** get_model("claude-3-opus") is called, **Then** returns "claude-3-opus" regardless of env var

### Edge Cases

- LLM returns empty string → ValueError with stage name and spec id
- Spec with no invariants → pipeline proceeds, generates empty ensures clauses
- NIGHTJAR_CROSS_VALIDATE=1 with issues found → Coder called a second time with issue context

## Functional Requirements

- **FR-001**: MUST raise TypeError for non-CardSpec input before any LLM call
- **FR-002**: MUST raise ValueError when any of the three LLM stages returns empty content
- **FR-003**: All LLM calls MUST go through litellm.completion() — never call provider APIs directly
- **FR-004**: GenerationResult.model_used MUST equal the resolved model (override or env or default)
- **FR-005**: Cross-validation MUST be off by default; only active when NIGHTJAR_CROSS_VALIDATE=1
