---
card-version: "1.0"
id: immune_pipeline
title: Immune System - Pipeline Orchestrator
status: draft
module:
  owns: [run_immune_cycle, run_mining_tiers, _merge_invariants]
  depends-on:
    immune.enricher: "enrich_invariants, CandidateInvariant, EnrichmentResult"
    immune.enforcer: "InvariantSpec, generate_enforced_source"
    immune.spec_updater: "append_invariant"
    immune.verifier_pbt: "PBTResult, PBTVerdict, verify_invariant_pbt"
    immune.verifier_symbolic: "SymbolicResult, SymbolicVerdict, verify_invariant_symbolic"
    immune.daikon: "InvariantMiner"
    immune.houdini: "houdini_filter"
    immune.mines: "mine_from_otel_spans"
contract:
  inputs:
    - name: function_source
      type: str
      constraints: "non-empty Python source of the function under test"
    - name: function_name
      type: str
      constraints: "name of the function in function_source"
    - name: observed_invariants
      type: list[str]
      constraints: "optional list of Daikon-mined expressions; defaults to []"
    - name: config
      type: ImmuneCycleConfig
      constraints: "optional; defaults applied if None"
  outputs:
    - name: result
      type: ImmuneCycleResult
      schema:
        candidates_proposed: int
        candidates_verified: int
        candidates_appended: int
        verified_expressions: list[str]
        enforced_source: str
        errors: list[str]
  errors:
    - Returns ImmuneCycleResult with errors populated; never raises uncaught exceptions
invariants:
  - id: INV-01
    tier: property
    statement: "run_immune_cycle with empty function_source returns ImmuneCycleResult with candidates_proposed=0 and a non-empty errors list, never raising"
    rationale: "Empty source is a user error; the pipeline must surface it gracefully via errors rather than crashing"
  - id: INV-02
    tier: property
    statement: "run_immune_cycle with valid inputs always returns ImmuneCycleResult where candidates_appended <= candidates_verified <= candidates_proposed"
    rationale: "Pipeline monotonicity: you can only verify candidates that were proposed, and only append those that were verified"
  - id: INV-03
    tier: property
    statement: "run_immune_cycle returns ImmuneCycleResult where len(verified_expressions) == candidates_verified"
    rationale: "verified_expressions must be in 1:1 correspondence with the candidates_verified count"
  - id: INV-04
    tier: property
    statement: "run_immune_cycle with config.require_both_verifiers=True only counts a candidate as verified when both CrossHair and Hypothesis pass"
    rationale: "require_both_verifiers enforces strict consensus — either verifier failing must exclude the candidate"
  - id: INV-05
    tier: property
    statement: "run_mining_tiers with func=None and spans=None returns MiningOrchestrationResult with empty merged list and empty tier_counts"
    rationale: "No input sources means no mining can occur; result must be empty rather than an error"
  - id: INV-06
    tier: property
    statement: "_merge_invariants never increases the length of the output list beyond the length of the input list"
    rationale: "Deduplication can only reduce or preserve the count, never introduce new invariants"
  - id: INV-07
    tier: property
    statement: "_merge_invariants selects max(confidences) when multiple tiers produce the same expression, and concatenates source strings with '+'"
    rationale: "Merged entries must carry the highest-confidence attribution across all contributing tiers"
---

## Intent

Wire all immune-system components into a single closed-loop pipeline. Two entry points are provided:

`run_immune_cycle` — the legacy single-function cycle: LLM enrichment → dual-verifier check (CrossHair + Hypothesis) → append verified invariants to .card.md → generate icontract-decorated source.

`run_mining_tiers` — a 3-tier mining orchestrator (Scout 6 Section 3): Tier 1 SEMANTIC (LLM hypothesis, zero overhead), Tier 2 RUNTIME (Daikon + Houdini, low overhead via sys.monitoring), Tier 3 API-LEVEL (MINES from OTel spans, no overhead). All tiers run independently; failures in one tier are recorded in errors and do not abort other tiers.

## Acceptance Criteria

### Story 1 — Full Cycle Produces Verified Enforced Source (P0)

**As a** production error handler, **I want** the immune cycle to transform an error trace into enforced source code, **so that** the same failure cannot recur undetected.

1. **Given** valid function_source, function_name, and observed_invariants from Daikon, **When** run_immune_cycle is called, **Then** returns ImmuneCycleResult with candidates_proposed >= 0, candidates_verified <= candidates_proposed, and non-empty enforced_source if any candidates were verified
2. **Given** empty function_source, **When** run_immune_cycle is called, **Then** returns result with errors containing "Function source is empty"

### Story 2 — 3-Tier Mining Deduplicates Across Tiers (P1)

**As a** mining orchestrator, **I want** invariants from different tiers to be deduplicated, **so that** the same expression produced by both Daikon and LLM is not counted twice.

1. **Given** func and trace_args and spans all provided, **When** run_mining_tiers is called, **Then** result.merged contains no duplicate expressions
2. **Given** a tier that raises an exception internally, **When** run_mining_tiers runs, **Then** the error is appended to result.errors and the other tiers complete normally

## Functional Requirements

- **FR-001**: run_immune_cycle MUST call _call_enricher before _call_symbolic_verifier or _call_pbt_verifier
- **FR-002**: run_immune_cycle MUST NOT append to card_path if card_path is None
- **FR-003**: run_immune_cycle MUST generate enforced_source via generate_enforced_source only when verified_candidates is non-empty
- **FR-004**: run_mining_tiers MUST call _merge_invariants on all collected tier results before returning
- **FR-005**: Tier 1 (SEMANTIC) MUST only run when run_tier1=True is explicitly passed
- **FR-006**: All three mining tier failures MUST be recorded in MiningOrchestrationResult.errors without propagating as exceptions
- **FR-007**: ImmuneCycleResult.enforced_source MUST be an empty string when no candidates pass verification
