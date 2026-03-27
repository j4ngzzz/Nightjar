---
card-version: "1.0"
id: confidence
title: Verification Confidence Score
status: draft
module:
  owns: [compute_confidence, compute_trust_level, ConfidenceScore]
  depends-on:
    nightjar.types: "StageResult, TrustLevel, VerifyResult, VerifyStatus"
contract:
  inputs:
    - name: result
      type: VerifyResult
      constraints: "stages list may be empty; each stage has a name, stage number, and VerifyStatus"
  outputs:
    - name: confidence
      type: ConfidenceScore
      schema: {total: int, breakdown: dict, gap: list}
  errors: []
invariants:
  - id: INV-01
    tier: property
    statement: "compute_confidence always returns a ConfidenceScore with total in [0, 100]"
    rationale: "The total is clamped with max(0, min(100, total)) before return"
  - id: INV-02
    tier: property
    statement: "Only stages with VerifyStatus.PASS contribute points; FAIL, SKIP, and TIMEOUT stages contribute 0"
    rationale: "Partial credit is never awarded — a stage must fully pass to earn its points"
  - id: INV-03
    tier: property
    statement: "sum(breakdown.values()) equals ConfidenceScore.total for any result"
    rationale: "The total must be exactly the sum of awarded per-stage points with no rounding error"
  - id: INV-04
    tier: property
    statement: "compute_confidence sets result.trust_level on the input VerifyResult as a side effect"
    rationale: "Callers do not need a second call to get the trust level — compute_confidence is the single source"
  - id: INV-05
    tier: property
    statement: "compute_trust_level(score) returns FORMALLY_VERIFIED iff score >= 0.75, PROPERTY_VERIFIED iff 0.50 <= score < 0.75, SCHEMA_VERIFIED iff 0.25 <= score < 0.50, else UNVERIFIED"
    rationale: "Thresholds match SkillFortify trust algebra constants exactly"
  - id: INV-06
    tier: property
    statement: "Stage named 'schema' maps to the 'crosshair' canonical tier worth 35 points, not a separate bucket"
    rationale: "The pipeline uses 'schema' for Stage 2 but the confidence framework maps it to CrossHair tier for scoring"
  - id: INV-07
    tier: property
    statement: "STAGE_POINTS values sum to exactly 100: preflight(15) + deps(10) + crosshair(35) + pbt(20) + formal(20) = 100"
    rationale: "The point budget must be exhaustive — no more, no less than 100 total available points"
---

## Intent

Compute a principled 0–100 confidence score from a VerifyResult. Each of the five verification stages (preflight, deps, schema/crosshair, pbt, formal) contributes a fixed number of points when it passes. The score enables transparent partial-verification reporting: a codebase that fails Dafny still has 80/100 confidence from stages 0–3. Maps the normalized score to a SkillFortify TrustLevel enum for downstream consumers.

## Acceptance Criteria

### Story 1 — Score Computation (P0)

**As a** CLI consumer, **I want** a numeric confidence score from 0 to 100, **so that** I can display how much verification coverage was achieved.

1. **Given** all 5 stages passed, **When** compute_confidence is called, **Then** returns ConfidenceScore(total=100) and sets trust_level=FORMALLY_VERIFIED
2. **Given** only preflight and deps passed (stages 0+1), **When** compute_confidence is called, **Then** returns total=25 and trust_level=SCHEMA_VERIFIED
3. **Given** empty stages list, **When** compute_confidence is called, **Then** returns total=0 and trust_level=UNVERIFIED
4. **Given** stage named 'schema' with PASS status, **When** compute_confidence is called, **Then** awards 35 points under canonical name 'crosshair'

### Story 2 — Trust Level Mapping (P0)

**As a** SkillFortify integration, **I want** a TrustLevel enum, **so that** I can enforce graduated access policies.

1. **Given** score >= 75, **When** compute_trust_level is called with score/100, **Then** returns FORMALLY_VERIFIED
2. **Given** score = 0, **When** compute_trust_level is called, **Then** returns UNVERIFIED

## Functional Requirements

- **FR-001**: MUST clamp total to [0, 100] even if stage point values change
- **FR-002**: MUST set result.trust_level as a side effect of compute_confidence
- **FR-003**: MUST map pipeline stage name 'schema' to canonical 'crosshair' bucket
- **FR-004**: MUST return gap list containing canonical names of FAIL or TIMEOUT stages (SKIP stages are NOT added to gap)
- **FR-005**: MUST use STAGE_POINTS dict as single source of truth — no magic numbers in compute logic
