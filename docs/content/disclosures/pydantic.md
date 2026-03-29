# Disclosure: pydantic — 3 Bugs (2 HIGH, 1 MEDIUM)

**Package:** pydantic
**Affected version:** 2.12.5
**Report date:** 2026-03-29
**Severity:** HIGH (BUG-1, BUG-3), MEDIUM (BUG-2)
**Preferred channel:** GitHub Security Advisory — https://github.com/pydantic/pydantic/security/advisories/new

> **Channel note:** No SECURITY.md found in the pydantic/pydantic repository at the standard paths. The GitHub Security Advisory tab is the appropriate channel for BUG-1 and BUG-3, which involve validators being bypassed or producing unexpected exceptions in production contexts. BUG-2 (`model_copy` shallow by default) is a documented behavior but operationally dangerous — it can be filed as a public GitHub issue alongside a documentation clarity request, after the security advisory is acknowledged.

---

## Subject

Nightjar formal verification: `model_validator(mode='before')` raises `TypeError` (not `ValidationError`), `model_copy(update=)` bypasses all validators, `model_copy()` shallow reference aliasing in pydantic 2.12.5

---

## Email Body

Hi pydantic team,

We have been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found three bugs in pydantic 2.12.5. Two involve validator enforcement being bypassed or failing in ways that cause incorrect runtime behavior in production FastAPI applications.

---

## BUG-1 (HIGH): `model_validator(mode='before')` raises raw `TypeError` on string inputs — bypasses FastAPI's 422 handler, causes 500

**Affected component**

Core pydantic `model_validator` with `mode='before'`
Python: 3.14, pydantic 2.12.5

**Bug description**

`model_validator(mode='before')` validators receive raw, uncoerced input. When a validator performs arithmetic on what are expected to be numeric fields, but the input arrives as strings (common in HTTP form data, some JSON clients, or certain ORM adapters that return everything as strings), Python's type system raises `TypeError` inside the validator body. Pydantic does not wrap `TypeError` exceptions from `mode='before'` validators in a `ValidationError`. The `TypeError` propagates as a raw Python exception. In a FastAPI application, this bypasses the 422 validation error handler — FastAPI catches `ValidationError` and returns a structured 422 response, but a `TypeError` from a validator escapes to Starlette's 500 handler and returns an opaque internal server error. Users see a 500 where they should see a 422 with a clear message about which field had the wrong type. This causes application breakage in production when string-typed payloads hit validators with arithmetic operations.

**Reproduction (100% confirmed)**

```python
from pydantic import BaseModel, model_validator

class OrderModel(BaseModel):
    price: float
    quantity: int

    @model_validator(mode='before')
    @classmethod
    def validate_total(cls, data):
        if isinstance(data, dict):
            # Fails when price='50.0' (str) and quantity='3' (str) — string * string
            total = data['price'] * data['quantity']
            if total > 10000:
                raise ValueError('Order total exceeds limit')
        return data

# Simulating what happens when form data or some JSON clients send strings:
try:
    OrderModel(price='50.0', quantity='3')
except TypeError as e:
    print(f"TypeError (not ValidationError): {e}")
    # Output: TypeError: can't multiply sequence by non-int of type 'str'
except Exception as e:
    print(f"Other: {type(e).__name__}: {e}")
```

**Output:**
```
TypeError: can't multiply sequence by non-int of type 'str'
```

This is not a `ValidationError`, so FastAPI returns a 500 instead of a 422.

**Suggested fix**

Option 1 (library fix): Wrap `TypeError` raised inside `mode='before'` validators in a `ValidationError` with context pointing to the fields involved.

Option 2 (user-facing docs improvement): Add a clear warning in the `model_validator(mode='before')` documentation that arithmetic on uncoerced values is unsafe and should always be preceded by explicit type-checking or use `mode='after'` for arithmetic operations.

```python
# Correct pattern — use mode='after' for arithmetic:
@model_validator(mode='after')
def validate_total(self) -> 'OrderModel':
    total = self.price * self.quantity  # types are already coerced
    if total > 10000:
        raise ValueError('Order total exceeds limit')
    return self
```

**Severity:** HIGH

---

## BUG-3 (HIGH): `model_copy(update=)` bypasses ALL field validators and type coercion

**Affected component**

`BaseModel.model_copy(update: dict | None = None)`
Python: 3.14, pydantic 2.12.5

**Bug description**

`model_copy(update=...)` creates a new model instance with specified field overrides but does not run any validators — not `field_validator`, not `model_validator`, and not type validation. This means that any business logic invariant expressed as a pydantic validator can be trivially bypassed by any code that uses `model_copy(update=)` on an existing valid instance. The resulting model instance contains fields with values that were explicitly rejected by validators on initial construction. Common use cases where this becomes dangerous: ORM update patterns that use `existing_record.model_copy(update=incoming_changes)`, middleware that transforms response models, and caching layers that create "modified copies" of models.

**Reproduction (100% confirmed)**

```python
from pydantic import BaseModel, field_validator

class BankAccount(BaseModel):
    owner: str
    balance: float
    account_id: str

    @field_validator('balance')
    @classmethod
    def check_balance(cls, v):
        if v < 0:
            raise ValueError('Balance cannot be negative')
        return v

# Normal construction: validator fires correctly
try:
    BankAccount(owner='Alice', balance=-100.0, account_id='ACC-001')
    assert False, "Should have raised"
except Exception as e:
    print(f"Construction correctly rejected: {e}")  # ValidationError

# model_copy bypass: validator is NOT called
acc = BankAccount(owner='Alice', balance=1000.0, account_id='ACC-001')
bad_copy = acc.model_copy(update={
    'balance': -99999.0,  # below zero — validator skipped
    'account_id': None,   # wrong type — type validator skipped
})

print(f"balance: {bad_copy.balance}")      # -99999.0 — validator bypassed
print(f"account_id: {bad_copy.account_id}")  # None — type validator bypassed
assert bad_copy.balance < 0               # True — invariant violated
```

**Impact**

Any code path that relies on `field_validator` to enforce business invariants (positive balances, valid enums, non-null required fields) can produce invalid model instances via `model_copy(update=)`. Because pydantic is widely used as the single source of model validation truth in FastAPI applications, this creates a pattern where validators are written once (on construction) but bypassed in all update paths.

**Suggested workaround (document clearly in the API)**

```python
# Safe update pattern — re-validates all fields:
safe_copy = BankAccount.model_validate(
    acc.model_dump() | {'balance': -99999.0}
)
# Raises ValidationError: balance cannot be negative
```

**Suggested library improvement:** Add a `validate=True` parameter to `model_copy()`:

```python
model_copy(update={'balance': -99999.0}, validate=True)
# Runs full validation on the result before returning
```

**Severity:** HIGH

---

## BUG-2 (MEDIUM): `model_copy()` is shallow by default — mutating nested fields in copy mutates original

**Affected component**

`BaseModel.model_copy(deep: bool = False)`
Python: 3.14, pydantic 2.12.5

**Bug description**

`model_copy()` returns a shallow copy by default. Nested mutable fields (`list`, `dict`) are shared by reference between the original and the copy. Mutating the copy's nested fields mutates the original. This is technically documented behavior (the `deep` parameter exists), but the default is the dangerous option and the docs do not prominently warn about this. The practical consequence is that code creating "modified copies" of request models for audit logging, middleware transformation, or test setup silently corrupts the original model. This is particularly dangerous in async FastAPI handlers where the original model may still be processing when the copy is mutated.

**Reproduction (100% confirmed)**

```python
from pydantic import BaseModel

class Config(BaseModel):
    tags: list = []
    metadata: dict = {}

c1 = Config(tags=[1, 2, 3], metadata={'key': 'value'})
c2 = c1.model_copy()  # default: deep=False

c2.tags.append(99)
c2.metadata['new_key'] = 'mutated'

print(c1.tags)       # [1, 2, 3, 99] — ORIGINAL MUTATED
print(c1.metadata)   # {'key': 'value', 'new_key': 'mutated'} — ORIGINAL MUTATED
```

**Fix:** Use `model_copy(deep=True)` whenever the copy will have nested mutable fields modified. Consider changing the default to `deep=True` in a future major version, or at minimum adding a `DeprecationWarning` when `deep=False` (the default) is used and the model contains nested mutable fields.

**Severity:** MEDIUM

---

## Disclosure Timeline

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

- **Day 0 (2026-03-29):** this report
- **Day 3:** please confirm receipt
- **Day 90 (2026-06-27):** public disclosure, or earlier if fixes or documentation updates are released

BUG-1 and BUG-3 are the priority. BUG-2 can be filed as a public GitHub issue at any point after acknowledgment if you prefer that channel for documented-but-dangerous behavior.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, pydantic 2.12.5, Windows 11. All three findings verified by direct execution (100% reproducible). No network access required.*
