---
card-version: "1.0"
id: constitution
title: Project Constitution
status: active
global-invariants:
  - id: GLOBAL-001
    tier: property
    statement: "All API responses must include a request_id for tracing"
    rationale: "Observability requirement — every response is traceable"
  - id: GLOBAL-002
    tier: formal
    statement: "No function may return both an error and a success value simultaneously"
    rationale: "Result type correctness — exactly one of success or error"
  - id: GLOBAL-003
    tier: property
    statement: "All monetary amounts must be represented as integers (cents), never floats"
    rationale: "Floating point arithmetic causes rounding errors in financial calculations"
constraints:
  security: "OWASP Top 10 compliance required for all modules"
  performance: "p99 latency < 5000ms for all endpoints"
---

## Intent

Project-level invariants that apply to ALL modules. These are inherited
by every .card.md spec during parsing, per [REF-T25] Spec Kit constitution pattern.

## Global Rules

- All modules MUST satisfy the global invariants listed above
- Module-specific invariants are additive — they do not override globals
- Constitution changes require team review
