# Agent Framework Bug Scan Results

**Scan date:** 2026-03-28
**Scanner:** CODE SCANNER agent (claude-sonnet-4-6)
**Method:** Direct code execution, manual edge-case probing, assertion-based verification

---

## Packages Attempted

| Package | Status | Version Tested |
|---------|--------|----------------|
| openai-agents | SKIP — not installable on this environment | — |
| browser-use | SKIP — not installable on this environment | — |
| openhands-ai | SKIP — not installable on this environment | — |
| pydantic | SCANNED | 2.12.5 |
| click | SCANNED | 8.3.1 |
| hypothesis | SCANNED | 6.151.9 |
| openai | SCANNED | 2.30.0 |

---

## Confirmed Bugs

### BUG-1: pydantic `model_validator(mode='before')` raises `TypeError` instead of `ValidationError` when inputs are strings

**Package:** pydantic 2.12.5
**Severity:** HIGH
**Reproducible:** Yes (100%)

**Reproduction:**
```python
from pydantic import BaseModel, model_validator

class OrderModel(BaseModel):
    price: float
    quantity: int

    @model_validator(mode='before')
    @classmethod
    def validate_total(cls, data):
        if isinstance(data, dict):
            total = data['price'] * data['quantity']  # <-- crashes here
            if total > 10000:
                raise ValueError('Order total exceeds limit')
        return data

OrderModel(price='50.0', quantity='3')
# Raises: TypeError: can't multiply sequence by non-int of type 'str'
# Expected: pydantic.ValidationError
```

**Why it matters:** `mode='before'` validators receive raw, uncoerced input. When an API endpoint receives JSON that deserializes to strings (which is common with some HTTP clients or form data), arithmetic in the validator raises `TypeError` — a Python runtime exception that bypasses FastAPI/Starlette's 422 handler and causes a 500 error instead.

**Confirmed output:**
```
BUG TypeError: can't multiply sequence by non-int of type 'str'
```

**Workaround:** Use `mode='after'` when doing arithmetic on field values. The `mode='after'` validator receives already-coerced types.

```python
@model_validator(mode='after')
def validate_total(self) -> 'OrderModel':
    total = self.price * self.quantity  # types are correct
    if total > 10000:
        raise ValueError('Order total exceeds limit')
    return self
```

---

### BUG-2: `model_copy()` is shallow by default — mutating nested fields in a copy mutates the original

**Package:** pydantic 2.12.5
**Severity:** MEDIUM
**Reproducible:** Yes (100%)

**Reproduction:**
```python
from pydantic import BaseModel

class Config(BaseModel):
    tags: list = []
    metadata: dict = {}

c1 = Config(tags=[1, 2, 3], metadata={'key': 'value', 'nested': [1, 2]})
c2 = c1.model_copy()  # default: deep=False

c2.tags.append(99)
c2.metadata['new_key'] = 'new_val'

print(c1.tags)      # [1, 2, 3, 99]  <-- MUTATED
print(c1.metadata)  # {'key': 'value', 'nested': [1, 2], 'new_key': 'new_val'}  <-- MUTATED
```

**Confirmed output:**
```
c1.tags: [1, 2, 3, 99]   (AFFECTED BY c2 mutation!)
c1.metadata: {'key': 'value', 'nested': [1, 2], 'new_key': 'new_val'}   (AFFECTED!)
```

**Why it matters:** Code that creates "modified copies" of request/response models (common in FastAPI middleware, caching layers, audit logging) silently corrupts the original object. This is particularly dangerous in async handlers where the original model may still be in use.

**Fix:** Always use `model_copy(deep=True)` when the copy will have its nested fields mutated.

---

### BUG-3: `model_copy(update=)` bypasses ALL validators including type and field validators

**Package:** pydantic 2.12.5
**Severity:** HIGH
**Reproducible:** Yes (100%)

**Reproduction:**
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

acc = BankAccount(owner='Alice', balance=1000.0, account_id='ACC-001')

# Developer expects validators to run — they DON'T
bad_copy = acc.model_copy(update={
    'balance': -99999.0,  # Negative balance — validator skipped
    'account_id': None,   # Wrong type — type validator skipped
})

print(bad_copy.balance)      # -99999.0  <-- validator bypassed
print(bad_copy.account_id)   # None      <-- type validator bypassed
```

**Confirmed output:**
```
balance: -99999.0   <-- NEGATIVE, validator bypassed!
account_id: None    <-- None, type validator bypassed!
```

**Why it matters:** Business logic invariants placed in `field_validator` give a false sense of security. Any code path that uses `model_copy(update=)` — including pydantic-based ORM patterns and response transformation — can produce invalid model instances.

**Fix:** Use `model_validate(instance.model_dump() | updates)` to get full validation on updates.

---

### BUG-4: `click` `required=True` option allows empty string and whitespace-only values

**Package:** click 8.3.1
**Severity:** MEDIUM
**Reproducible:** Yes (100%)

**Reproduction:**
```python
import click
from click.testing import CliRunner

@click.command()
@click.option('--name', required=True)
def cmd(name):
    click.echo(f'name={repr(name)}')

runner = CliRunner()

# These should fail with exit_code=2, but they don't:
result = runner.invoke(cmd, ['--name', ''])
print(result.exit_code)   # 0  (expected 2)
print(result.output)      # name=''

result = runner.invoke(cmd, ['--name', '   '])
print(result.exit_code)   # 0  (expected 2)
print(result.output)      # name='   '

# This correctly fails:
result = runner.invoke(cmd, [])
print(result.exit_code)   # 2 -- Missing option '--name'
```

**Confirmed output:**
```
--name "" (empty string): exit_code 0  (EXPECTED 2 for required)
--name "   " (whitespace): exit_code 0  (EXPECTED 2 for required)
no --name: exit_code 2  (correct)
```

**Why it matters:** CLI tools that require non-empty credentials, file paths, or identifiers accept blank inputs silently. Downstream code then fails with confusing errors. Particularly bad for `--api-key`, `--token`, `--output-file` style options.

**Workaround:** Add explicit validation in the callback, or use a custom `type=` with a validator.

```python
def non_empty_string(value):
    if not value or not value.strip():
        raise click.BadParameter('value cannot be empty')
    return value

@click.option('--name', required=True, type=non_empty_string)
```

---

### FINDING-5: click envvar whitespace inconsistency

**Package:** click 8.3.1
**Severity:** LOW
**Reproducible:** Yes

**Behavior:**
- `API_TOKEN=""` (empty string) → treated as **missing**, exit code 2 (correct)
- `API_TOKEN="   "` (whitespace only) → treated as **valid value**, exit code 0 (inconsistent)

```python
runner.invoke(cmd, [], env={'API_TOKEN': ''})    # exit=2, Missing option
runner.invoke(cmd, [], env={'API_TOKEN': '   '}) # exit=0, token accepted
```

**Why it matters:** Configuration management tools or deployment scripts might set environment variables to spaces as a "blank" placeholder. These pass click's required check, reaching application code as whitespace strings.

---

### FINDING-6: `openai.OpenAI(api_key='')` accepts empty string without error

**Package:** openai 2.30.0
**Severity:** LOW
**Reproducible:** Yes

```python
from openai import OpenAI

OpenAI(api_key=None)   # Raises OpenAIError immediately -- correct
OpenAI(api_key='')     # Silently creates client -- BUG
```

The empty-string client will fail with a confusing auth error on the first actual API call rather than at construction time. `None` is correctly rejected at construction. The inconsistency makes it harder to validate credentials before use.

---

### FINDING-7: `openai.OpenAI` accepts negative `timeout` and `max_retries` without validation

**Package:** openai 2.30.0
**Severity:** LOW
**Reproducible:** Yes

```python
client = OpenAI(api_key='sk-test', timeout=-1.0, max_retries=-5)
# No error raised; client.timeout == -1.0, client.max_retries == -5
```

Negative retries in the retry loop and negative timeouts in httpx could produce confusing failures at request time rather than a clear `ValueError` at construction.

---

## Clean / No Bug Found

| Package | What was tested | Result |
|---------|----------------|--------|
| hypothesis 6.151.9 | `st.integers(min > max)`, `st.floats(impossible bounds)`, `st.lists(min_size > max_size)` | Correctly raises `InvalidArgument` |
| hypothesis 6.151.9 | `assume(False)` always-failing | Correctly raises `Unsatisfiable` |
| hypothesis 6.151.9 | `st.text(alphabet='')` | Correctly returns empty strings |
| hypothesis 6.151.9 | `find()` with impossible predicate | Correctly raises `NoSuchExample` |
| hypothesis 6.151.9 | Stateful `RuleBasedStateMachine` | Correctly finds counterexample |
| pydantic 2.12.5 | `field_validator` with `Optional` fields + `None` | Correctly handles None |
| pydantic 2.12.5 | `extra='forbid'` config | Correctly rejects extra fields |
| pydantic 2.12.5 | Subclass equality | Correctly returns False (different types) |
| click 8.3.1 | `IntRange` boundary values | Correct boundary enforcement |
| click 8.3.1 | `Choice` case sensitivity | Correctly rejects wrong case |
| click 8.3.1 | `--version` without required option | Eager option correctly exits 0 |

---

## Summary

| ID | Package | Bug | Severity | Confirmed |
|----|---------|-----|----------|-----------|
| BUG-1 | pydantic 2.12.5 | `model_validator(mode='before')` TypeError on string inputs | HIGH | Yes |
| BUG-2 | pydantic 2.12.5 | `model_copy()` shallow — mutating copy mutates original | MEDIUM | Yes |
| BUG-3 | pydantic 2.12.5 | `model_copy(update=)` bypasses all validators | HIGH | Yes |
| BUG-4 | click 8.3.1 | `required=True` allows empty string and whitespace | MEDIUM | Yes |
| F-5 | click 8.3.1 | envvar: empty string rejected, whitespace passes | LOW | Yes |
| F-6 | openai 2.30.0 | `api_key=''` accepted; fails only on first call | LOW | Yes |
| F-7 | openai 2.30.0 | Negative `timeout`/`max_retries` not validated | LOW | Yes |

BUGs 1–4 are the most actionable: all reproducible with a single file, no network required.

openai-agents, browser-use, and openhands-ai could not be installed in this environment and were not scanned.
