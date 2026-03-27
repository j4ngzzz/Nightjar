---
card-version: "1.0"
id: immune_enforcer
title: Immune System - Runtime Enforcer
status: draft
module:
  owns:
    - generate_enforced_source
    - parse_invariant_to_contract
    - enforce_with_transitions
    - capture_pre_state
    - check_transition_postcondition
    - InvariantStore
    - TemporalInvariant
  depends-on:
    icontract: "@require, @ensure decorators [REF-T10]"
contract:
  inputs:
    - name: func_source
      type: str
      constraints: "non-empty Python source containing a function named func_name"
    - name: func_name
      type: str
      constraints: "must match a def statement in func_source"
    - name: invariants
      type: list[InvariantSpec]
      constraints: "non-empty list; each has expression and optional explanation"
  outputs:
    - name: result
      type: str
      constraints: "valid Python source with icontract decorators prepended"
  errors:
    - Returns source with 'import icontract' only if func_name def line not found
    - Never raises uncaught exceptions from generate_enforced_source or check_transition_postcondition
invariants:
  - id: INV-01
    tier: property
    statement: "generate_enforced_source always begins its output with 'import icontract'"
    rationale: "The generated source must import icontract before any decorator can run; this invariant is unconditional"
  - id: INV-02
    tier: property
    statement: "generate_enforced_source output contains exactly one @icontract.require or @icontract.ensure decorator for each InvariantSpec in invariants"
    rationale: "Each verified invariant must be enforced at runtime — no silently dropped contracts"
  - id: INV-03
    tier: property
    statement: "parse_invariant_to_contract returns a string containing '@icontract.ensure' when the expression contains the word 'result', and '@icontract.require' otherwise"
    rationale: "Expressions referencing the return value are postconditions; all others are preconditions — auto-detection must be correct"
  - id: INV-04
    tier: safety
    statement: "check_transition_postcondition returns True on any eval exception, never raising — fail-open on unevaluable invariants"
    rationale: "Production code must never crash due to an invariant that cannot be evaluated; safety takes precedence over strictness"
  - id: INV-05
    tier: safety
    statement: "enforce_with_transitions raises TransitionViolationError only when at least one transition postcondition explicitly evaluates to False; it never raises for non-transition invariants"
    rationale: "Only transition postconditions (those containing OLD) are checked by this function; static pre/postconditions are icontract's responsibility"
  - id: INV-06
    tier: property
    statement: "InvariantStore.get_active_invariants returns only entries whose superseded_by field is None"
    rationale: "Superseded invariants are retained for audit history but must not be returned for active enforcement"
  - id: INV-07
    tier: property
    statement: "InvariantStore.get_confidence returns a value in [0.0, 1.0] for any expression; returns 0.0 for unknown expressions; confidence decays monotonically as current_time increases beyond timestamp"
    rationale: "Temporal confidence must be bounded and must decay via the exponential half-life model — stale invariants should not be enforced with full confidence"
---

## Intent

Generate icontract-decorated Python source from verified invariants, and enforce state-transition postconditions at runtime using the OLD-state snapshot pattern. The enforcer also implements temporal confidence decay (Supermemory model) so stale runtime-observed invariants lose confidence over time.

Three independent subsystems are provided:
1. **Source generator** (`generate_enforced_source`) — injects `@icontract.require`/`@ensure` decorators into function source
2. **Transition enforcer** (`enforce_with_transitions`) — wraps function calls to check OLD-pattern postconditions without requiring icontract at runtime
3. **Temporal store** (`InvariantStore`) — manages invariants with exponential confidence decay and supersession for audit history

## Acceptance Criteria

### Story 1 — Decorated Source Is Safe and Correct (P0)

**As a** code generator, **I want** the enforced source to be syntactically valid and have one decorator per invariant, **so that** it can be written to disk and imported without errors.

1. **Given** a function source and list of InvariantSpecs, **When** generate_enforced_source is called, **Then** the output starts with "import icontract", contains all decorators, and the original function body is unchanged
2. **Given** an expression without 'result', **When** parse_invariant_to_contract is called, **Then** the output uses @icontract.require

### Story 2 — Fail-Open on Unevaluable Postconditions (P0)

**As a** production service, **I want** transition postcondition evaluation failures to be silent, **so that** a bad invariant expression never causes downtime.

1. **Given** an invariant expression that raises NameError when evaluated, **When** check_transition_postcondition is called, **Then** it returns True and emits a warning

### Story 3 — Temporal Confidence Decay (P1)

**As a** monitoring system, **I want** runtime-observed invariants to lose confidence over time, **so that** stale contracts are not enforced at full strength.

1. **Given** a TemporalInvariant with half_life=86400, **When** get_confidence is called at timestamp + 86400 seconds, **Then** returned confidence is approximately 0.5 * base_confidence

## Functional Requirements

- **FR-001**: generate_enforced_source MUST place @require decorators before @ensure decorators on the same function
- **FR-002**: generate_enforced_source MUST preserve the original function body unchanged
- **FR-003**: check_transition_postcondition MUST return True (not raise) on any eval exception, and MUST emit a warnings.warn call
- **FR-004**: enforce_with_transitions MUST capture pre-state before calling func, not after
- **FR-005**: capture_pre_state MUST use copy.deepcopy for list, dict, set, and bytearray arguments; copy.copy for all others
- **FR-006**: InvariantStore.supersede MUST set superseded_by on the old expression and MUST NOT delete it
- **FR-007**: InvariantStore.get_confidence decay formula MUST be: base_confidence * 0.5^(elapsed / half_life), clamped to [0.0, 1.0]
