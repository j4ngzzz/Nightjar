---
card-version: "1.0"
id: auto
title: Auto Spec Generator
status: active
generated-by: nightjar-dogfood
module:
  owns: [run_auto]
  depends-on:
    litellm: ">=1.0"
    nightjar.intent_router: "parse_nl_intent, classify_invariant"
    nightjar.invariant_generators: "rank_candidates, format_invariant"
contract:
  inputs:
    - name: nl_intent
      type: str
      constraints: "non-empty, describes a software component"
    - name: output_path
      type: str
      constraints: "valid writable file path"
    - name: yes
      type: bool
      constraints: "if True, auto-approve all candidates"
  outputs:
    - name: result
      type: AutoResult
      schema: {}
  errors:
    - ValueError
invariants:
  - id: INV-001
    tier: property
    statement: "run_auto with yes=True always writes a .card.md file for any non-empty nl_intent"
    rationale: "Non-interactive mode must always produce output"
  - id: INV-002
    tier: property
    statement: "run_auto raises ValueError for empty or whitespace-only nl_intent"
    rationale: "Empty intent cannot produce meaningful spec"
  - id: INV-003
    tier: property
    statement: "AutoResult.approved_count + AutoResult.skipped_count equals total candidates presented"
    rationale: "Every candidate must be either approved or skipped — no silent drops"
  - id: INV-004
    tier: example
    statement: "run_auto('payment processor that deducts from balance', yes=True) produces spec with at least 3 invariants"
    rationale: "A minimal payment spec must have at least: non-negative balance, non-negative amount, result >= 0"
---

## Intent

Generate `.card.md` specification files from natural language intent. Takes a plain English description and auto-generates verification artifacts (icontract decorators, Hypothesis strategies, optional Dafny proofs), presenting them for human review before writing to disk.

## Acceptance Criteria

### Story 1 — Non-Interactive Generation (P0)

**As a** CI pipeline, **I want** to generate specs without prompts, **so that** automation works without human input.

1. **Given** valid nl_intent and yes=True, **When** run_auto is called, **Then** writes .card.md and returns AutoResult with approved_count >= 1
2. **Given** empty nl_intent, **When** run_auto is called, **Then** raises ValueError immediately

## Functional Requirements

- **FR-001**: MUST raise ValueError for empty/whitespace nl_intent before any LLM call
- **FR-002**: MUST write valid parseable .card.md (parse_card_spec must succeed on output)
- **FR-003**: approved_count + skipped_count MUST equal total candidates ranked
