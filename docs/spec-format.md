# .card.md Spec Format Reference

This document is the authoritative reference for the `.card.md` specification format used by Nightjar. It covers every field the parser accepts, the three invariant tiers, how specs connect to source code, and the preprocessing rules that run before verification.

For step-by-step walkthroughs, see the tutorials in `docs/superpowers/plans/`.

---

## 1. Overview

A `.card.md` file is the single source of truth for one module. It specifies:

- **What the module owns** — the functions and classes it is responsible for
- **What inputs and outputs it accepts** — typed, constrained
- **What invariants must hold** — example-level, property-level, or formally proven
- **What the intent is** — in human-readable prose

Nightjar generates code from specs and mathematically proves the generated code satisfies them. The spec is never derived from the code; the code is derived from the spec.

**Canonical location:** `.card/<module-name>.card.md`

**One spec per module.** The spec owns its module boundary; modules do not share specs.

**Format:** YAML frontmatter (between `---` delimiters) followed by a Markdown body. The parser is strict about the delimiter format — the file must start with `---\n`.

---

## 2. File Structure

```
---
<YAML frontmatter>
---

## Intent

...

## Acceptance Criteria

...

## Functional Requirements

...
```

The YAML frontmatter is parsed into a `CardSpec` dataclass. The Markdown body is plain Markdown; the parser extracts three named sections (`Intent`, `Acceptance Criteria`, `Functional Requirements`) and ignores all others.

---

## 3. YAML Frontmatter Reference

### 3.1 Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `card-version` | string | **Yes** | — | Spec format version. Always `"1.0"`. |
| `id` | string | **Yes** | — | Unique module identifier. Becomes the filename base and the key for verification cache lookups. Pattern: `[a-zA-Z][a-zA-Z0-9_-]*`. |
| `title` | string | No | `""` | Human-readable display name. |
| `status` | string | No | `"draft"` | Lifecycle status. Conventional values: `draft`, `active`, `deprecated`. Not enforced by the parser. |
| `module` | mapping | No | `{}` | Module boundary declaration. See [Section 3.2](#32-module-block). |
| `contract` | mapping | No | `{}` | Function-level input/output contract. See [Section 3.3](#33-contract-block). |
| `invariants` | sequence | No | `[]` | List of invariants to verify. See [Section 3.4](#34-invariants). |
| `constraints` | mapping | No | `{}` | Free-form key/value metadata (performance, security, compliance). See [Section 3.5](#35-constraints). |

The parser silently ignores any unknown top-level keys. The two fields that raise `ValueError` when absent are `card-version` and `id`.

### 3.2 `module:` Block

Declares the ownership boundary for this spec.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `owns` | list[string] | No | `[]` | Function and class signatures this module is responsible for. Convention: include `()` for functions. |
| `depends-on` | mapping or list | No | `{}` | External dependencies. As a mapping: `{name: version-constraint}`. As a list: bare names with no version pinning. |
| `excludes` | list[string] | No | `[]` | Explicit scope exclusions — functionality this spec deliberately does not cover. Documents non-requirements. |

```yaml
module:
  owns:
    - process_payment()
    - validate_amount()
    - calculate_fee()
    - refund()
  depends-on:
    postgres: "approved"
    stripe-sdk: "^5.0"
  excludes:
    - "Cryptocurrency payments"
    - "Subscription billing"
```

`depends-on` as a list is also valid when version pinning is not needed:

```yaml
module:
  depends-on:
    - postgres
    - redis
```

### 3.3 `contract:` Block

Declares the formal input/output contract for the module's public interface.

#### `contract.inputs`

A list of input parameter declarations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Parameter name. |
| `type` | string | **Yes** | Type annotation (`integer`, `float`, `string`, `bool`, `object`, etc.). |
| `constraints` | string | No | Predicate string — a precondition that must hold on this input. |

The `constraints` field is a free-form predicate string. The spec preprocessor (see [Section 9](#9-spec-preprocessing)) normalizes natural-language constraint patterns into explicit predicates before LLM generation.

```yaml
contract:
  inputs:
    - name: amount
      type: integer
      constraints: "amount > 0 AND amount <= 1_000_000"
    - name: currency
      type: string
      constraints: "currency IN ('USD', 'EUR', 'GBP', 'JPY')"
    - name: user_id
      type: string
      constraints: "len(user_id) > 0"
```

#### `contract.outputs`

A list of output declarations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Output name. Conventionally the return type name. |
| `type` | string | **Yes** | Type annotation. |
| `schema` | mapping | No | Field-level schema for object outputs. Keys are field names, values are type strings. |

```yaml
contract:
  outputs:
    - name: PaymentResult
      type: object
      schema:
        transaction_id: string
        status: string
        amount_charged: integer
        fee: integer
        currency: string
```

#### `contract.errors`

A list of exception class names this module may raise.

```yaml
contract:
  errors:
    - InsufficientFundsError
    - InvalidAmountError
    - CurrencyNotSupportedError
    - PaymentGatewayError
```

#### `contract.events-emitted`

A list of event names this module emits (for event-driven systems).

```yaml
contract:
  events-emitted:
    - payment.processed
    - payment.failed
    - payment.refunded
```

Note the hyphen in `events-emitted` — this is the YAML key exactly as the parser reads it. Using `events_emitted` (underscore) will be silently ignored.

### 3.4 `invariants:`

The core of the spec. A list of verifiable claims about the module's behavior. Each invariant maps to one verification step in the pipeline.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | **Yes** | — | Unique identifier within the spec. Convention: `<MODULE>-INV-<NNN>`. Used as the cache key for incremental verification. |
| `tier` | string | No | `"example"` | Verification method. One of: `example`, `property`, `formal`. See [Section 4](#4-invariant-tiers). |
| `statement` | string | No | `""` | The invariant claim. May be natural language, a predicate, or Dafny syntax depending on tier. |
| `rationale` | string | No | `""` | Why this invariant exists. Explains the real-world consequence of violating it. |

```yaml
invariants:
  - id: INV-001
    tier: example
    statement: "Processing a $10 USD payment returns a valid transaction_id"
    rationale: "Basic smoke test for the happy path"

  - id: INV-002
    tier: property
    statement: "For any valid payment, amount_charged + fee equals the total deducted from user"
    rationale: "Financial integrity — no money created or destroyed"

  - id: INV-004
    tier: formal
    statement: "The total of all processed payments minus all refunds equals the net revenue"
    rationale: "Accounting invariant — must be mathematically proven for audit compliance"
```

If `tier` contains an unrecognized value, the parser defaults to `example` without raising an error.

### 3.5 `constraints:`

A free-form key/value mapping for non-functional requirements and metadata. The parser passes this through as `dict[str, str]` without validation.

```yaml
constraints:
  performance: "p95 latency < 2000ms"
  security: "PCI-DSS Level 1 compliance required"
  idempotency: "Duplicate payment requests with same idempotency key return cached result"
```

Any key names are accepted. Common conventions: `performance`, `security`, `compliance`, `idempotency`, `availability`.

---

## 4. Invariant Tiers

Tiers define which verification engine runs against an invariant. Higher tiers provide stronger guarantees at higher compute cost. The preprocessor reorders invariants `formal > property > example` before verification (Rule Group 5, see [Section 9](#9-spec-preprocessing)).

| Tier | Verifier | Cost | Guarantee | When to Use |
|------|----------|------|-----------|-------------|
| `example` | Unit test (pytest) | Low | The specific input/output pair holds | Smoke tests, happy-path checks, regression pins |
| `property` | Hypothesis PBT | Medium | Holds across hundreds of random inputs | Boundary conditions, type invariants, error-path checks |
| `formal` | Dafny / CrossHair | High | Holds for all possible inputs (mathematical proof) | Financial accounting, security boundaries, safety-critical logic |

### `example` tier

Natural language or concrete input/output pair. Generates a unit test.

```yaml
- id: PAY-INV-001
  tier: example
  statement: "process_payment(1000, 'USD') returns a ChargeResult with status='success'"
  rationale: "Smoke test — confirms the happy path runs without exception"
```

### `property` tier

A predicate that must hold across all valid inputs. Hypothesis generates up to 200 random examples by default.

```yaml
- id: PAY-INV-002
  tier: property
  statement: "amount > 0 for all calls to process_payment()"
  rationale: "Zero-amount charges reach the gateway and consume rate limit quota"
```

The preprocessor normalizes natural-language patterns before Hypothesis generation:

- `"amount is always positive"` → `"result > 0"`
- `"must be non-negative"` → `">= 0"`
- `"for all x, ..."` → `"forall x :: ..."`

### `formal` tier

A Dafny postcondition or CrossHair contract. Must be a predicate that Dafny's SMT solver (Z3) or CrossHair's symbolic execution can evaluate.

```yaml
- id: PAY-INV-004
  tier: formal
  statement: "total == amount + fee for every successful charge"
  rationale: "Financial integrity — no money created or destroyed"
```

```yaml
- id: AUTH-INV-002
  tier: formal
  statement: "token expiry is always in the future — expires_at > time.time() at creation"
  rationale: "Tokens with expiry=0 or expiry=None must be rejected"
```

Formal invariants run through the SafePilot complexity router: simple predicates go to CrossHair, complex recursive invariants go to Dafny.

---

## 5. Markdown Body Sections

The parser extracts three `## Level-2 heading` sections from the Markdown body. All other sections are valid Markdown but not consumed by the pipeline.

| Section | Field in CardSpec | Description |
|---------|-------------------|-------------|
| `## Intent` | `intent` | One-paragraph summary of what the module does and why. Used by the LLM generator as context. |
| `## Acceptance Criteria` | `acceptance_criteria` | Given/When/Then scenarios per [REF-T25] GitHub Spec Kit. Drives test generation. |
| `## Functional Requirements` | `functional_requirements` | `FR-NNN:` numbered requirements. Used for completeness checking. |

Sections are extracted with their full content (including any nested `###` subheadings and lists). Trailing/leading whitespace is stripped.

### Acceptance Criteria format

Use Given/When/Then numbered steps under story subheadings:

```markdown
## Acceptance Criteria

### Story 1 — Process Payment (P1)

**As a** customer, **I want** to pay for my order, **so that** I can receive my goods.

1. **Given** amount=1000, currency="USD", **When** process_payment() is called, **Then** a PaymentResult with status="success" is returned
2. **Given** amount=0, **When** process_payment() is called, **Then** InvalidAmountError is raised

### Edge Cases

- What if currency is not in the supported list? → CurrencyNotSupportedError
```

---

## 6. Complete Annotated Example

The following is a minimal but complete spec covering all fields. Comments (`#`) are for documentation here — YAML does not support inline comments on the same line as certain values, but block comments are valid.

```yaml
---
# Required: format version (always "1.0")
card-version: "1.0"

# Required: unique module ID — used as cache key and audit filename
id: payment-processing

# Optional: human-readable display name
title: Payment Processing Module

# Optional: lifecycle status (draft | active | deprecated)
status: active

# Optional: module boundary declaration
module:
  # Functions this spec is responsible for
  owns:
    - process_payment()
    - validate_amount()
    - calculate_fee()
    - refund()
  # External dependencies {name: version-constraint}
  depends-on:
    postgres: "approved"
    stripe-sdk: "^5.0"
  # Explicit scope exclusions
  excludes:
    - "Cryptocurrency payments"
    - "Subscription billing"

# Optional: formal input/output contract
contract:
  inputs:
    - name: amount
      type: integer
      constraints: "amount > 0 AND amount <= 1_000_000"
    - name: currency
      type: string
      constraints: "currency IN ('USD', 'EUR', 'GBP', 'JPY')"
    - name: user_id
      type: string
      constraints: "len(user_id) > 0"
  outputs:
    - name: PaymentResult
      type: object
      schema:
        transaction_id: string
        status: string
        amount_charged: integer
        fee: integer
        currency: string
  errors:
    - InsufficientFundsError
    - InvalidAmountError
    - CurrencyNotSupportedError
    - PaymentGatewayError
  events-emitted:
    - payment.processed
    - payment.failed
    - payment.refunded

# Optional: invariants to verify — the core of the spec
invariants:
  # example tier: generates a single unit test
  - id: INV-001
    tier: example
    statement: "Processing a $10 USD payment returns a valid transaction_id"
    rationale: "Basic smoke test for the happy path"

  # property tier: Hypothesis generates hundreds of random inputs
  - id: INV-002
    tier: property
    statement: "For any valid payment, amount_charged + fee equals the total deducted from user"
    rationale: "Financial integrity — no money created or destroyed"

  # property tier: error-path boundary
  - id: INV-003
    tier: property
    statement: "No payment with amount <= 0 or amount > 1_000_000 is ever processed"
    rationale: "Input validation boundary enforcement"

  # formal tier: mathematically proven by Dafny/CrossHair
  - id: INV-004
    tier: formal
    statement: "The total of all processed payments minus all refunds equals the net revenue"
    rationale: "Accounting invariant — must be mathematically proven for audit compliance"

# Optional: non-functional constraints (free-form key/value)
constraints:
  performance: "p95 latency < 2000ms"
  security: "PCI-DSS Level 1 compliance required"
  idempotency: "Duplicate requests with same idempotency key return cached result"
---

## Intent

Process payments securely and reliably. Accept payments in multiple currencies,
calculate fees, and support full and partial refunds. All financial operations
must maintain perfect accounting invariants — no money created or destroyed.

## Acceptance Criteria

### Story 1 — Process Payment (P1)

**As a** customer, **I want** to pay for my order, **so that** I can receive my goods.

1. **Given** amount=1000, currency="USD", **When** process_payment() is called, **Then** a PaymentResult with status="success" and a valid transaction_id is returned
2. **Given** amount=0, **When** process_payment() is called, **Then** InvalidAmountError is raised
3. **Given** amount=1_000_001, **When** process_payment() is called, **Then** InvalidAmountError is raised

### Story 2 — Refund (P2)

**As a** support agent, **I want** to refund a payment, **so that** the customer gets their money back.

1. **Given** a completed payment of 1000, **When** refund(1000) is called, **Then** the full amount is refunded
2. **Given** a completed payment of 1000, **When** refund(500) is called, **Then** a partial refund of 500 is processed
3. **Given** a completed payment of 1000, **When** refund(1500) is called, **Then** InvalidAmountError is raised

### Edge Cases

- What if currency is not in the supported list? → CurrencyNotSupportedError
- What if the payment gateway is unreachable? → PaymentGatewayError

## Functional Requirements

- **FR-001**: System MUST validate amount is between 1 and 1,000,000 inclusive
- **FR-002**: System MUST validate currency is one of USD, EUR, GBP, JPY
- **FR-003**: System MUST calculate fee as 2.9% + 30 cents for USD, varying by currency
- **FR-004**: System MUST emit payment.processed event on successful payment
```

---

## 7. Constitution Files

A constitution file (`.card/constitution.card.md`) defines project-level invariants that are automatically inherited by every module spec. It uses `global-invariants:` instead of `invariants:` in its frontmatter.

```yaml
---
card-version: "1.0"
id: constitution
title: Project-Level Invariants
status: active

global-invariants:
  - id: GLOBAL-INV-001
    tier: property
    statement: "No function logs plaintext passwords or API keys"
    rationale: "PII/secrets must never appear in log output"

  - id: GLOBAL-INV-002
    tier: property
    statement: "All user-facing error messages are non-empty strings"
    rationale: "Silent failure with empty error strings violates the error contract"
---

## Intent

Project-level invariants inherited by all module specs.
```

**Merge behavior:** Module-level invariants take precedence over global invariants when IDs conflict. Global invariants are appended after module-level invariants in the merged list.

**Loading:** `parse_with_constitution(spec_path, constitution_path)` handles the merge. If the constitution file does not exist, parsing proceeds normally with module invariants only.

**Note:** The `global-invariants:` key is only meaningful in a constitution file. Using it in a regular module spec will silently cause those invariants to be ignored by `parse_card_spec()`.

---

## 8. Spec Generation Commands

Specs can be created four ways, ordered from least to most LLM involvement:

### `nightjar init <module-name>`

Scaffolds a blank template at `.card/<module-name>.card.md`. No LLM, no AST analysis. Starting point for manual spec writing.

```bash
nightjar init payment
# Creates .card/payment.card.md with empty owns, contract, invariants
```

Module name must match `[a-zA-Z][a-zA-Z0-9_-]*`.

### `nightjar scan <path>`

Extracts invariant candidates from a Python file or directory by analyzing type hints, guard clauses, docstrings, and assertions. No LLM required by default.

```bash
nightjar scan src/payment.py
nightjar scan src/payment.py --llm              # LLM-enhanced suggestions
nightjar scan src/payment.py --llm --verify     # Verify immediately after scan
nightjar scan src/ --workers 4 --smart-sort     # Whole directory, security-sorted
```

Options:

| Flag | Description |
|------|-------------|
| `--llm` | Enhance AST candidates with LLM suggestions |
| `--verify` | Run the verification pipeline after spec generation |
| `--approve-all` | Accept all candidates without interactive prompt |
| `--workers N` | Parallel workers for directory mode |
| `--min-signal low\|medium\|high` | Filter candidates by signal confidence |
| `--smart-sort` | Order files by security criticality before scanning |

### `nightjar infer <file> [--function <name>]`

Generates preconditions and postconditions for Python functions via an LLM, then symbolically verifies them with CrossHair in a generate-verify-repair loop. Produces higher-quality invariants than `scan` at higher cost.

```bash
nightjar infer src/payment.py --function process_payment
nightjar infer src/payment.py                    # All top-level functions
nightjar infer src/payment.py --append-to-card   # Merge into existing .card.md
nightjar infer src/payment.py --no-verify        # Skip CrossHair (fast mode)
```

Options:

| Flag | Description |
|------|-------------|
| `--function <name>` | Target one function (default: all top-level functions) |
| `--no-verify` | Skip CrossHair verification loop (fast, lower-quality) |
| `--append-to-card` | Merge inferred contracts into the matching `.card.md` |
| `--max-iterations N` | CrossHair repair iteration limit (default: 5) |

### `nightjar auto "<intent>"`

Takes a natural-language description and generates a complete `.card.md` spec with interactive invariant approval.

```bash
nightjar auto "process credit card payments with fee calculation and refunds"
nightjar auto "rate limit API requests per user" --approve-all
```

Options:

| Flag | Description |
|------|-------------|
| `--approve-all` | Auto-approve all suggested invariants without prompting |
| `--output <dir>` | Output directory for the generated spec (default: `.card`) |

### Manual authoring

Write `.card.md` files directly using the schema in this document. This is the power-user path — use it when you need precise control over invariant statements, especially for `formal` tier invariants targeting specific Dafny syntax.

---

## 9. Spec Preprocessing

Before passing a spec to the LLM generator, Nightjar applies 19 deterministic normalization rules in 5 groups. These rules transform natural-language invariant statements into forms that Z3 and Dafny handle more efficiently.

**Effect on verification success rates (per [Proven, github.com/melek/proven]):**
- Local models: 19% → 41% Dafny success
- Claude Sonnet: 65% → 78% Dafny success

Rules run in this order: Group 1 → Group 3 → Group 2 → Group 4 → Group 5. Sugar expansion (Group 3) runs before compound decomposition (Group 2) so that bounded range patterns are expanded before the AND-split scans for compound postconditions.

### Rule Groups

| Group | Rules | Name | Applies To | What it Does |
|-------|-------|------|------------|--------------|
| 1 | 1–3 | Quantifier normalization | `formal`, `property` invariants | `"for all x"` → `"forall x :: "` / `"there exists n such that"` → `"exists n :: "` |
| 2 | 4–6 | Compound decomposition | `formal`, `property` invariants | Splits `"A and B"` into two invariants. Skips range patterns like `0 <= x and x <= 100`. |
| 3 | 7–12 | Syntactic sugar expansion | All invariants | Expands shorthands: `"result is positive"` → `"result > 0"`, `"returns non-negative"` → `"result >= 0"`, `"bounded between N and M"` → `"N <= result <= M"`, etc. |
| 4 | 13–16 | Constraint normalization | `contract.inputs[*].constraints` | Normalizes: `"must be positive"` → `"{name} > 0"`, `"must not be empty"` → `"len({name}) > 0"` |
| 5 | 17–19 | Dedup + ordering | All invariants | Removes duplicate statements (case-insensitive). Orders: `formal` first, then `property`, then `example`. |

### Sugar expansion patterns (Group 3)

| Pattern | Normalized form |
|---------|-----------------|
| `result is positive` / `returns positive` | `result > 0` |
| `result is non-negative` / `returns non-negative` | `result >= 0` |
| `result is negative` | `result < 0` |
| `result is bounded between N and M` | `N <= result <= M` |
| `result is at least N` | `result >= N` |
| `result is at most N` | `result <= N` |

### Constraint normalization patterns (Group 4)

| Pattern | Normalized form |
|---------|-----------------|
| `must be positive` | `{name} > 0` |
| `must be non-negative` | `{name} >= 0` |
| `must not be empty` | `len({name}) > 0` |
| `must be non-empty` | `len({name}) > 0` |

Preprocessing does not mutate the `CardSpec` object — it returns a new `RewriteResult` with a fresh copy. The `rules_applied` list in `RewriteResult` records which rule names fired, useful for debugging unexpected invariant transformations.

---

## 10. Linking Specs to Code

### `module.owns` connects specs to functions

The `module.owns` list declares which functions and classes this spec governs. The generator uses this list to decide what code to produce and what to annotate with `icontract` preconditions/postconditions.

Convention: include `()` for functions to visually distinguish from class names.

```yaml
module:
  owns:
    - process_payment()    # function
    - validate_amount()    # function
    - PaymentProcessor     # class (no parentheses)
```

The immune system's trace collector (`src/immune/collector.py`) uses `include_modules` to scope which execution traces to capture for invariant mining. The `module.owns` list informs which functions the immune pipeline should mine invariants for.

### `id` connects specs to generated artifacts

The spec `id` is used as the base filename for all generated artifacts:

- `.card/audit/<id>.py` — generated Python code (READ-ONLY)
- `.card/audit/<id>.dfy` — generated Dafny proof (READ-ONLY)
- `.card/cache/<id>.json` — per-invariant verification cache
- `verify.json` — last full verification report

The `id` must be stable — renaming it invalidates the verification cache.

### `module.depends-on` documents external boundaries

The `depends-on` field declares approved external dependencies. The Stage 1 (deps) verification step checks these against `deps.lock` to ensure no unapproved packages are in the dependency graph.

Version constraint format follows pip version specifiers (`^5.0`, `>=2.0,<3.0`, `approved`). The value `"approved"` means the dependency is allowed without a version constraint.

---

## 11. Incremental Recompilation

The parser provides two functions for tracking spec changes without re-running full verification:

### `hash_invariants(spec) → dict[str, str]`

Returns `{invariant_id: sha256_hex}` for each invariant in the spec. The hash covers the invariant's `statement`, `tier`, and `rationale`. Changing any of these produces a different hash, triggering re-verification of only that invariant.

### `diff_specs(old_hashes, new_hashes) → SpecDiff`

Compares two hash maps and returns a `SpecDiff` with four lists:

| Field | Contents |
|-------|---------|
| `added` | Invariant IDs new in `new_hashes` |
| `removed` | Invariant IDs absent from `new_hashes` |
| `changed` | IDs in both maps but with different hashes |
| `unchanged` | IDs in both maps with identical hashes |

All lists are sorted for deterministic output.

**Usage pattern:**

```python
from nightjar.parser import parse_card_spec, hash_invariants, diff_specs

old_spec = parse_card_spec(".card/payment.card.md")
old_hashes = hash_invariants(old_spec)

# ... spec file is edited ...

new_spec = parse_card_spec(".card/payment.card.md")
new_hashes = hash_invariants(new_spec)

diff = diff_specs(old_hashes, new_hashes)
# Only re-verify diff.added + diff.changed
```

The verifier's incremental pipeline (`run_pipeline_incremental`) consumes `SpecDiff` to skip unchanged invariants.

---

## 12. Open Tasks

### Check: does the parser accept any undocumented fields?

**Finding:** The parser uses `data.get()` for all fields and does not call `yaml.safe_load` with a strict schema. This means **unknown keys at any level are silently ignored** — in the top-level frontmatter, in `module:`, in `contract:`, in individual invariant or input/output entries.

Practical consequence: a typo in a field name (e.g., `invarient:` instead of `invariants:`) will silently produce an empty invariant list with no error. Users should validate specs with `nightjar verify` before relying on them.

Candidate fix: add a schema validation step (using Pydantic or a YAML schema) that warns on unknown keys.

### `module.path` field — planned but not implemented

Some documentation references a `module.path` field for specifying the source file path. As of the current parser (`src/nightjar/parser.py`), `ModuleBoundary` has three fields: `owns`, `depends_on`, `excludes`. There is no `path` field. If `module.path:` is present in a spec's YAML, it is silently ignored.

If this field is added in a future iteration, `_parse_module()` in `parser.py` and the `ModuleBoundary` dataclass in `types.py` both need updating.

### `global-invariants` is constitution-only

The `global-invariants:` key is only read by `load_constitution()`. If a non-constitution spec uses `global-invariants:` instead of `invariants:`, those invariants will be silently discarded by `parse_card_spec()`. There is no validation guard for this.
