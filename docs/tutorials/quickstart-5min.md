# Find a hidden bug in your FastAPI in 5 minutes

Nightjar found 74 bugs in popular packages. Let's find one in yours.

---

## 1. Install

```bash
pip install nightjar-verify
```

Python 3.11+. No Dafny required for this tutorial — Hypothesis handles the heavy lifting.

---

## 2. Write a spec

Create `.card/payment.card.md`:

```markdown
---
card-version: "1.0"
id: payment
title: Payment Processing
status: active
module:
  owns: [process_charge()]
contract:
  inputs:
    - name: amount
      type: float
      constraints: "amount > 0"
    - name: currency
      type: string
      constraints: "len(currency) == 3 and currency.isupper()"
  outputs:
    - name: result
      type: dict
invariants:
  - id: INV-001
    tier: property
    statement: "amount is always positive (> 0, not >= 0)"
    rationale: "Zero-amount charges are silent no-ops that reach the gateway"
  - id: INV-002
    tier: property
    statement: "currency is a valid 3-letter uppercase ISO 4217 code"
    rationale: "Invalid currency codes cause silent gateway rejections"
  - id: INV-003
    tier: property
    statement: "fee is always non-negative"
    rationale: "Negative fees silently credit the merchant account"
  - id: INV-004
    tier: formal
    statement: "total_charged == amount + fee for every successful charge"
    rationale: "Financial integrity — no money created or destroyed"
---

## Intent

Process a payment charge. Validate inputs before touching the gateway.
```

---

## 3. Run verify

```bash
nightjar verify --spec .card/payment.card.md
```

Nightjar generates a Python implementation from the spec, then runs it through
5 verification stages — cheapest first, short-circuit on first failure.

**Expected output:**

```
Nightjar v0.9 — Contract-Anchored Verification
================================================

  Stage 0  Preflight          PASS   spec valid, 4 invariants loaded
  Stage 1  Dependencies       PASS   no vulnerable packages
  Stage 2  Schema             PASS   types match contract
  Stage 2.5 Negation Proof   PASS   spec is self-consistent
  Stage 3  Property Tests     FAIL

  ✗ INV-001 — amount is always positive (> 0, not >= 0)

  Counterexample found after 3 examples:
    process_charge(amount=0.0, currency="USD")
    → {"status": "success", "amount_charged": 0.0, "fee": 0.0}

  Your code accepted a zero-amount charge.
  The spec requires amount > 0. Zero is not greater than zero.

  Fix suggestion: add `if amount <= 0: raise ValueError(...)` before the gateway call.

  1 violation · 0 proven · Stage 4 skipped
  Time: 1.2s
```

---

## 4. The bug

The generated code used `amount >= 0` instead of `amount > 0`.

Zero is falsy in Python. A zero-amount charge reaches the payment gateway, logs as success,
and charges the card $0.00 — which some gateways accept and some reject silently. The error
only surfaces in your bank reconciliation, days later.

Nightjar found it in 1.2 seconds by exhaustively testing the boundary condition you didn't
think to write a test for.

---

## 5. Fix and re-verify

Open the generated code in `.card/audit/payment.py` and add the guard:

```python
# .card/audit/ is READ-ONLY — fixes go in the spec, not the code
```

Update the spec instead. Change INV-001 to make the constraint explicit:

```yaml
  - id: INV-001
    tier: formal
    statement: "amount > 0 — strictly positive, zero is rejected"
    rationale: "Zero-amount charges are silent no-ops that reach the gateway"
```

Re-run:

```bash
nightjar verify --spec .card/payment.card.md
```

```
  Stage 0  Preflight          PASS
  Stage 1  Dependencies       PASS
  Stage 2  Schema             PASS
  Stage 2.5 Negation Proof   PASS
  Stage 3  Property Tests     PASS   200 examples, 0 violations
  Stage 4  Formal Proof       PASS

  ✓ payment.process_charge — PROVEN
    Dafny verified: amount > 0 holds for all valid inputs.

  4/4 invariants proven · 0 violations
  Time: 8.4s
```

**PROVEN** means Dafny mathematically proved the property holds for *all* valid inputs —
not just the 200 examples Hypothesis tried.

---

## 6. What just happened

| Stage | Tool | What it did |
|-------|------|-------------|
| Stage 0 | Nightjar | Parsed and validated your spec |
| Stage 1 | pip-audit | Checked your dependencies for CVEs |
| Stage 2 | Pydantic | Validated input/output schemas |
| Stage 2.5 | CrossHair | Proved the spec is internally consistent |
| Stage 3 | Hypothesis | Generated 200 property-based tests, found the zero-amount bug |
| Stage 4 | Dafny | Formally proved the fix is correct for all inputs |

You wrote the spec. Nightjar wrote the proof.

---

## Next: Add to CI in one commit

[Add Nightjar to your CI in one commit →](ci-one-commit.md)

Or scan an existing FastAPI app:

```bash
nightjar scan app.py
```

[Verify your FastAPI endpoint contracts →](verify-fastapi.md)
