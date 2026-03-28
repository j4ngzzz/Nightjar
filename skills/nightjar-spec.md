---
name: nightjar-spec
description: Interactively build a .card.md spec for a Python module. No YAML knowledge required. The skill reads your code, asks a few questions, and writes the spec.
---

# Nightjar Spec Builder

Write a formal spec for a Python module interactively. No prior knowledge of the .card.md format required.

## When to use

- Starting a new module and want to spec it before writing code
- Have existing Python code and want to add formal verification
- Just ran `nightjar init` and stared at an empty template
- Want to add invariants but don't know which tier to use
- The nightjar-verify skill detected no spec for the current module

## What to do

### Step 1: Identify the target

Ask: "Which Python file do you want to write a spec for?"

Or detect from context (the file they're editing or currently discussing).

### Step 2: Read the code

Read the Python file using the Read tool. Extract:

- All function signatures (name, parameters, return type)
- Type annotations on parameters and return values
- Docstrings (Google-style: Args, Returns, Raises sections)
- Guard clauses: `if X: raise Y` patterns
- Any `assert` statements in the body
- Any existing tests that test this module (look in `tests/`)

Before asking any questions, assemble what you already know. For each function found, note:

- **Schema candidates**: parameter types → "param_name must be a \<type\>"
- **Guard candidates**: `if x <= 0: raise` → "x must be > 0"
- **Return candidates**: return type hint → "result is always a \<type\>"
- **Raises candidates**: docstring Raises section → preconditions

Show the user a summary:

```
I've read [filename]. I found:
  - 2 functions: process_payment, refund
  - 5 type hints → 5 schema invariant candidates
  - 3 guard clauses → 3 precondition candidates
  - 1 docstring Raises section → 1 error condition

Let me confirm a few things before writing your spec.
```

### Step 3: Ask only what you cannot infer

For each question, show your best guess first and ask to confirm or correct.

**Q1 — Module identity**
```
Module ID: payment  (from filename payment.py)
Title: Payment Processing
Is this correct? [Y/edit]:
```

**Q2 — Confirm inferred preconditions**
For each guard clause found:
```
I see: `if amount <= 0: raise InvalidAmountError`
Invariant candidate: "amount must be a positive integer"
Accept? [Y/n/edit]:
```

**Q3 — Add missing postconditions**
If no postconditions were inferred:
```
What can you guarantee about what process_payment returns?
For example: "always returns a PaymentResult with non-null transaction_id"
(Press Enter to skip, or type your invariant):
```

**Q4 — What should it NEVER do?** (Often the easiest question)
```
What should process_payment NEVER do, even in edge cases?
For example: "never charge more than 1,000,000 cents", "never return null"
(Press Enter to skip):
```

**Q5 — Tier confirmation** (only if user is unsure)

If the user seems uncertain about tier, explain simply:

- **schema** — type checking: "amount must be an integer" — checked by Pydantic
- **property** — behavioral: "amount must be positive" — checked by Hypothesis with random inputs
- **formal** — mathematical proof: "no money is created or destroyed" — proved by Dafny (optional)

For most developers, schema + property is enough. Only suggest formal if they mention accounting, financial integrity, or "mathematical proof."

### Step 4: Write the spec

Use the Write tool to create `.card/<module_id>.card.md` with the following structure:

```yaml
---
card-version: "1.0"
id: <module_id>
title: <title>
status: draft
generated-by: nightjar-spec-skill
module:
  owns: [<discovered_function_names>]
  depends-on: {}
contract:
  inputs:
    - name: <param_name>
      type: <type>
      constraints: "<constraint_from_guard_or_hint>"
  outputs:
    - name: <return_name>
      type: <return_type>
      schema: {}
invariants:
  - id: INV-001
    tier: schema
    statement: "<confirmed_schema_invariant>"
    rationale: "From type hint"
  - id: INV-002
    tier: property
    statement: "<confirmed_property_invariant>"
    rationale: "From guard clause / docstring / user answer"
---

## Intent

<one_sentence_from_user_or_docstring>

## Acceptance Criteria

### Story 1 — <title> (P1)

**As a** developer, **I want** <module_purpose>, **so that** my code is verified.

1. **Given** valid inputs, **When** <function_name> is called, **Then** all invariants hold.

## Functional Requirements

<invariants_as_FRs>
```

### Step 5: Confirm and run verification

After writing the spec:

```
Spec written to .card/<module_id>.card.md
  3 schema invariants
  4 property invariants
  0 formal invariants (optional — add later if you need mathematical proof)

Next step: nightjar verify --spec .card/<module_id>.card.md
Run it now? [Y/n]:
```

If yes, run `nightjar verify --spec .card/<module_id>.card.md` and report results. If a stage FAILs, show the counterexample and suggest a fix.

## Tier guide (keep handy)

| Tier | What it checks | Engine | When to use |
|------|---------------|--------|-------------|
| `schema` | Types, nullability, field presence | Pydantic | Always — for all typed inputs/outputs |
| `property` | Behavioral bounds, relationships | Hypothesis | For numeric ranges, ordering, business rules |
| `formal` | Mathematical proofs | Dafny | Only for financial integrity, crypto, safety-critical |
| `example` | Specific input/output pairs | pytest | For documenting known-good examples |

## Common invariant patterns

```yaml
# Schema — types
statement: "user_id is always a non-empty string"
tier: schema

# Property — numeric bounds
statement: "amount must be greater than zero and at most 1,000,000"
tier: property

# Property — output guarantee
statement: "process_payment always returns a PaymentResult with non-null transaction_id on success"
tier: property

# Property — error condition
statement: "process_payment raises InvalidAmountError when amount is not positive"
tier: property

# Formal — accounting invariant
statement: "the sum of all payments minus all refunds equals net_revenue"
tier: formal

# Example — smoke test
statement: "process_payment(1000, 'USD', valid_user) returns status='ok'"
tier: example
```

## Install Nightjar

```bash
pip install nightjar-verify
```
