---
card-version: "1.0"
id: pydantic-validators
title: Pydantic v2 Validators — Community Spec
status: active
module:
  owns:
    - define_model()
    - validate_input()
    - validate_field()
    - safe_model_validate()
  depends-on:
    pydantic: ">=2.0.0,<3.0.0"
  excludes:
    - "pydantic v1 compatibility layer (pydantic.v1.*)"
    - "ORM mode / from_orm() patterns — use model_validate(obj, from_attributes=True)"
    - "JSON Schema generation for OpenAPI specs (delegated to FastAPI/APIRouter)"
contract:
  inputs:
    - name: data
      type: object
      constraints: "data is a dict, JSON-serializable object, or ORM model instance"
    - name: model_class
      type: type
      constraints: "model_class is a subclass of pydantic.BaseModel"
    - name: strict
      type: bool
      constraints: "bool type — True disables all type coercion"
    - name: field_value
      type: "any"
      constraints: "no constraint on raw input — validators must handle unexpected types"
  outputs:
    - name: ValidatedModel
      type: object
      schema:
        model_dump: object
        model_fields_set: object
        model_extra: "object or None"
  errors:
    - ValidationError
    - PydanticUserError
    - SerializationError
    - StrictModeViolation
constraints:
  migration: "pydantic v2 has a compatibility layer (pydantic.v1) but @validator decorators from v1 are silently ignored in native v2 models — ALL validators must be migrated to @field_validator"
  security: "strict=True must be used for any security-sensitive fields (user IDs, amounts, enum discriminators)"
  performance: "model_validate() p95 latency < 1ms for models with <= 20 fields"
invariants:
  - id: PYD-INV-001
    tier: property
    statement: "a BaseModel subclass containing @validator decorator (pydantic v1 API) emits a PydanticUserError or DeprecationWarning — v1 validators are silently skipped in pydantic v2 native models"
    rationale: "The most dangerous pydantic v1 → v2 migration bug: @validator decorators that look valid are silently ignored by pydantic v2 native models. The validation appears to 'run' (no import error), but the validator function is never called. A security validator like @validator('amount') def amount_must_be_positive(cls, v): if v <= 0: raise ValueError... simply never executes. The fix is @field_validator('amount') with mode='before'. Detection requires either a PydanticUserError at class definition time or a DeprecationWarning."
  - id: PYD-INV-002
    tier: formal
    statement: "safe_model_validate(data, model_class, strict=True) raises ValidationError when data contains a string where an int field is declared — '100' must not coerce to 100 in strict mode"
    rationale: "Pydantic's default (non-strict) mode silently coerces '100' → 100, 'true' → True, '1.5' → 1 (int). This coercion is convenient but dangerous for security-sensitive fields: a permission level of '0' might be intended as a string error code but gets coerced to 0 (admin-level integer). In strict mode, the type must match exactly. The invariant formalizes that strict=True actually prevents string-to-int coercion."
  - id: PYD-INV-003
    tier: formal
    statement: "safe_model_validate() raises ValidationError when extra fields are present and model is configured with model_config = ConfigDict(extra='forbid')"
    rationale: "A model accepting extra fields silently can lead to prototype pollution patterns or unexpected state. An attacker can inject extra fields into a validated model (e.g., adding is_admin=True to a UserCreate model). ConfigDict(extra='forbid') rejects extra fields, but only if explicitly set — the default is extra='ignore' which silently drops unknown fields. The invariant ensures that models intended to be strict about their schema actually are."
  - id: PYD-INV-004
    tier: property
    statement: "@model_validator(mode='before') functions must handle inputs where any field value may be str, int, None, or missing — the 'before' validator receives unvalidated raw data"
    rationale: "A common bug in mode='before' validators: the developer accesses `values['amount']` expecting a float (because the model declares amount: float), then calls values['amount'] * 1.1. But in mode='before', pydantic has not yet run field validation. The input is raw. If amount is '50.0' (a string from JSON) or missing entirely, the validator throws a TypeError or KeyError. The invariant requires that mode='before' validators defensively handle any input type."
  - id: PYD-INV-005
    tier: property
    statement: "a @field_validator('amount', mode='after') on a field declared as float receives a float — validate_field() with input='50.0' (string) and mode='after' must never deliver a str to the validator body"
    rationale: "mode='after' validators run after pydantic's type coercion. The input is guaranteed to match the declared type annotation. A validator that writes `assert isinstance(v, float)` will never fail. This is the inverse of PYD-INV-004 and is testable: given a model with amount: float and a mode='after' validator, Hypothesis can generate str inputs and assert the validator body always sees a float — if it sees a str, the mode='before' / mode='after' wiring is wrong."
  - id: PYD-INV-006
    tier: example
    statement: "safe_model_validate({'name': 'Alice', 'age': 30}, UserModel) returns a UserModel instance where .name == 'Alice' and .age == 30"
    rationale: "Smoke test: basic round-trip validation. Confirms the model parses a well-formed dict correctly and the field values are accessible on the resulting model instance."
---

## Intent

Formalize correct usage of pydantic v2's validator system. Pydantic v2 (2.0+,
released June 2023) introduced breaking API changes from v1: @validator became
@field_validator, validators: classmethod pattern changed, and strict mode
semantics changed. The pydantic v1 compatibility layer (pydantic.v1.*) still
works but native v2 models silently ignore v1 decorator syntax.

The three failure modes this spec addresses: (1) @validator decorators that
appear valid but are silently skipped in v2 native models, meaning security
validators never run; (2) type coercion in non-strict mode allowing string-encoded
numbers to pass integer type checks; (3) mode='before' vs mode='after' confusion
causing validators to receive unexpected types.

## Acceptance Criteria

### Story 1 — Field Validation (P1)

**As a** data ingestion service, **I want** to validate incoming JSON payloads, **so that** only well-typed data enters the system.

1. **Given** UserModel with field amount: int and input {'amount': '100'}, strict=False, **When** safe_model_validate() is called, **Then** model.amount == 100 (string coerced to int)
2. **Given** UserModel with field amount: int and input {'amount': '100'}, strict=True, **When** safe_model_validate() is called, **Then** ValidationError is raised — '100' is not an int
3. **Given** UserModel with model_config = ConfigDict(extra='forbid') and input {'name': 'Alice', 'is_admin': True}, **When** safe_model_validate() is called, **Then** ValidationError is raised — 'is_admin' is an extra field
4. **Given** a model class using @validator('name') (v1 API), **When** the class is defined, **Then** a PydanticUserError or DeprecationWarning is emitted

### Story 2 — Validator Modes (P2)

**As a** developer writing custom validators, **I want** to use the correct validator mode, **so that** validators receive expected types.

1. **Given** a @model_validator(mode='before') that accesses raw_data['amount'], **When** input is {'amount': '50.0'} (string), **Then** the validator handles the string gracefully (no KeyError or TypeError)
2. **Given** a @field_validator('amount', mode='after') on amount: float, **When** validation runs, **Then** the validator receives a float, not a string
3. **Given** a @field_validator('email', mode='before') on email: str, **When** input is None, **Then** the validator handles None without raising AttributeError

### Edge Cases

- What if a field has both @field_validator and a Pydantic constraint (gt=0)? → Both run; validator runs first in 'before' mode, constraint runs last
- What if strict=True and the field is Optional[int] with input None? → Accepted — None is a valid Optional value even in strict mode
- What if extra='ignore' (default) and extra fields are passed? → Extra fields are silently dropped — no error
- What if a @field_validator raises a ValueError with a message? → Message is included in ValidationError.errors()

## Functional Requirements

- **FR-PYD-001**: System MUST use @field_validator (pydantic v2 API) — @validator (v1 API) is forbidden in all native v2 models
- **FR-PYD-002**: System MUST use strict=True for security-sensitive fields (user IDs, permission levels, financial amounts)
- **FR-PYD-003**: System MUST configure model_config = ConfigDict(extra='forbid') for any model that processes untrusted external input
- **FR-PYD-004**: System MUST write mode='before' validators to defensively handle any Python type for each accessed field
- **FR-PYD-005**: System MUST NOT rely on pydantic.v1 compatibility shim for new models — migration must be complete
- **FR-PYD-006**: System MUST validate that validator return values match the declared field type — validators that return None for a non-Optional field will cause a ValidationError at runtime
