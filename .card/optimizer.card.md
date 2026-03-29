---
card-version: "1.0"
id: optimizer
title: LLM Prompt Optimizer (Hill-Climbing)
status: draft
module:
  owns: [PromptOptimizer, OptimizationConfig, OptimizationResult, run_optimization, evaluate_prompt]
  depends-on:
    litellm: ">=1.0 — all LLM calls go through litellm [REF-T16]"
    nightjar.tracking: "TrackingDB.get_pass_rate"
    nightjar.prompts: "PromptTemplate, PromptRegistry"
contract:
  inputs:
    - name: config
      type: OptimizationConfig
      constraints: "target_prompt must match a registered template; max_iterations >= 1; improvement_threshold >= 0.0"
  outputs:
    - name: result
      type: OptimizationResult
      schema: {improved: bool, best_score: float, iterations_run: int}
  errors:
    - ValueError
invariants:
  - id: INV-01
    tier: property
    statement: "optimize raises ValueError if no template exists for config.target_prompt"
    rationale: "Cannot optimize a prompt that has not been registered — fail fast with a clear message"
  - id: INV-02
    tier: property
    statement: "optimize returns OptimizationResult.iterations_run <= config.max_iterations"
    rationale: "The loop is bounded by max_iterations; LLM failures cause continue not extra iterations"
  - id: INV-03
    tier: property
    statement: "A new prompt version is registered only when candidate_score > best_score + improvement_threshold"
    rationale: "Strict improvement gate prevents noisy variations from polluting the registry"
  - id: INV-04
    tier: property
    statement: "OptimizationResult.improved is True iff best_score > original_score + improvement_threshold"
    rationale: "The improved flag is the canonical signal; it must agree with the score comparison"
  - id: INV-05
    tier: safety
    statement: "LLM call failure inside _call_llm_for_variation never propagates — the iteration is skipped via continue"
    rationale: "A transient LLM error must not abort the optimization run; remaining iterations still execute"
  - id: INV-06
    tier: property
    statement: "All LLM calls use the model resolved from NIGHTJAR_MODEL env var or the hardcoded default 'claude-sonnet-4-6'; no provider API is called directly"
    rationale: "Model-agnosticism is enforced via litellm [REF-T16]; hardcoding provider SDKs is forbidden"
---

## Intent

Implement a hill-climbing prompt self-improvement loop (inspired by the SIMBA pattern from [REF-T26]). For each iteration: fetch the current best prompt, ask the LLM to generate a variation, evaluate the variation using the tracking DB pass rate as proxy metric, and register the candidate only if it clears the improvement threshold. Over multiple runs this produces a self-improving prompt registry grounded in real verification outcomes.

## Acceptance Criteria

### Story 1 — Bounded Optimization Loop (P0)

**As a** self-evolution pipeline, **I want** the optimizer to run at most max_iterations times, **so that** runtime is predictable.

1. **Given** max_iterations=3 and no improvement found, **When** optimize is called, **Then** returns iterations_run=3 and improved=False
2. **Given** LLM fails on every iteration, **When** optimize is called, **Then** does not raise and returns iterations_run=max_iterations

### Story 2 — Improvement Gate (P0)

**As a** prompt registry, **I want** only genuinely better prompts to be registered, **so that** the registry does not degrade.

1. **Given** candidate_score = original_score + improvement_threshold, **When** compared, **Then** candidate is NOT registered (strict greater-than required)
2. **Given** candidate_score > original_score + improvement_threshold, **When** compared, **Then** candidate IS registered and best_score is updated

### Story 3 — Missing Template Guard (P0)

**As a** CLI, **I want** a clear error when the target prompt is missing, **so that** users get actionable feedback.

1. **Given** target_prompt not in registry, **When** optimize is called, **Then** raises ValueError with the prompt name in the message

## Functional Requirements

- **FR-001**: MUST raise ValueError when no template is found for target_prompt before any LLM call
- **FR-002**: MUST use litellm.completion for all LLM calls — never call provider SDKs directly
- **FR-003**: MUST resolve model from NIGHTJAR_MODEL env var with fallback to "claude-sonnet-4-6"
- **FR-004**: MUST skip iterations where variation_text is empty or falsy
- **FR-005**: iterations_run MUST equal the number of loop iterations executed (not the number of improvements)
