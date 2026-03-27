---
card-version: "1.0"
id: types
title: Shared Types
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "InvariantTier enum has exactly three members: EXAMPLE, PROPERTY, FORMAL — no additions without Coordinator approval"
    rationale: "types.py is the shared interface; enum completeness prevents silent contract gaps across builders"
  - id: INV-02
    tier: property
    statement: "VerifyStatus enum covers exactly four terminal states: PASS, FAIL, SKIP, TIMEOUT — every verification outcome maps to one"
    rationale: "Missing status values would cause unhandled cases in the verification pipeline"
  - id: INV-03
    tier: property
    statement: "TrustLevel thresholds are monotonically ordered: FORMALLY_VERIFIED >= 0.75 > PROPERTY_VERIFIED >= 0.50 > SCHEMA_VERIFIED >= 0.25 > UNVERIFIED"
    rationale: "Trust algebra (arxiv:2603.00195) requires strict ordering so trust comparisons are unambiguous"
  - id: INV-04
    tier: example
    statement: "CardSpec.invariants is an empty list by default — not None — to prevent NoneType errors during iteration"
    rationale: "Dataclass field(default_factory=list) ensures safe iteration without null checks"
  - id: INV-05
    tier: property
    statement: "VerifyResult.verified is False when any stage has status FAIL"
    rationale: "A single failed stage must not allow the overall result to report verified=True"
  - id: INV-06
    tier: example
    statement: "StageResult.errors defaults to empty list; counterexample defaults to None — both optional for passing stages"
    rationale: "Passing stages produce no errors or counterexamples; defaults keep the data model clean"
---

## Intent

Defines all shared dataclasses, enums, and type contracts used across the Nightjar
verification pipeline. Every builder imports types from here — this module is the
single source of truth for the data model.

This file must not be modified without Coordinator approval because it forms the
shared interface between all pipeline stages (parser, generator, verifier, stages).

References:
- [REF-C01] Tiered invariants — CARD's invention (EXAMPLE / PROPERTY / FORMAL)
- [REF-T03] Hypothesis PBT for property tier
- [REF-T01] Dafny mathematical proof for formal tier
- arxiv:2603.00195 DY-Skill threat model — TrustLevel trust algebra

## Acceptance Criteria

- [ ] `InvariantTier` has exactly EXAMPLE, PROPERTY, FORMAL as members
- [ ] `VerifyStatus` covers PASS, FAIL, SKIP, TIMEOUT with no gaps
- [ ] `TrustLevel` thresholds are monotonically ordered per trust algebra
- [ ] All dataclasses use `field(default_factory=list)` for collection fields — never `None` defaults
- [ ] `CardSpec` captures all parsed .card.md front-matter fields
- [ ] `VerifyResult` includes `trust_level: Optional[TrustLevel]` for SkillFortify integration

## Functional Requirements

1. **InvariantTier** — three-valued enum (EXAMPLE, PROPERTY, FORMAL); values are lowercase strings for YAML round-trip compatibility
2. **VerifyStatus** — four-valued enum (PASS, FAIL, SKIP, TIMEOUT); values are lowercase strings for JSON serialization
3. **TrustLevel** — four-valued enum aligned with SkillFortify thresholds (0.75 / 0.50 / 0.25); values are SCREAMING_SNAKE_CASE for upstream SkillFortify compatibility
4. **Invariant** — dataclass with (id: str, tier: InvariantTier, statement: str, rationale: str = "")
5. **ContractInput** — dataclass with (name: str, type: str, constraints: str = "")
6. **ContractOutput** — dataclass with (name: str, type: str, schema: dict = {})
7. **ModuleBoundary** — dataclass with (owns: list[str], depends_on: dict[str, str], excludes: list[str]); all defaults empty
8. **Contract** — dataclass aggregating inputs, outputs, errors, events_emitted; all defaults empty lists
9. **CardSpec** — dataclass capturing all parsed .card.md fields including card_version, id, title, status, module, contract, invariants, constraints, intent, acceptance_criteria, functional_requirements
10. **StageResult** — captures stage number, name, status, duration_ms, errors list, and optional counterexample
11. **VerifyResult** — captures verified bool, stages list, total_duration_ms, retry_count, optional confidence score, optional trust_level
