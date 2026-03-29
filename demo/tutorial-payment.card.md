---
card-version: "1.0"
id: tutorial-payment
title: Payment Processing
status: draft
module:
  owns: [process_charge]
  depends-on: {}
contract:
  inputs:
    - name: amount
      type: float
      constraints: "> 0"
    - name: currency
      type: str
      constraints: "len == 3 and isupper"
    - name: quantity
      type: int
      constraints: ">= 1"
  outputs:
    - name: result
      type: dict
      constraints: "result['total'] == amount * quantity"
invariants:
  - tier: property
    rule: "process_charge(amount, currency, quantity) requires amount > 0"
  - tier: property
    rule: "process_charge(amount, currency, quantity) requires len(currency) == 3 and currency.isupper()"
  - tier: property
    rule: "process_charge(amount, currency, quantity).total == amount * quantity"
  - tier: schema
    rule: "amount must be strictly positive — never zero, never negative"
  - tier: schema
    rule: "currency must be exactly 3 uppercase ASCII letters (ISO 4217)"
  - tier: schema
    rule: "total charge must not exceed 10000 per transaction"
---

## Intent

A payment charge processor that bills customers.

The critical invariant: **charge amounts must always be strictly positive.**
No merchant should ever process a zero or negative charge — that would credit
the customer instead of charging them, or silently accept malformed requests.

## Acceptance Criteria

### Story 1 — Valid Charge (P0)

**As a** payment processor, **I want** to charge valid amounts only,
**so that** merchants never accidentally credit instead of charge.

1. **Given** amount=29.99, currency="USD", quantity=1, **When** process_charge(), **Then** total=29.99
2. **Given** amount=9.99, currency="GBP", quantity=3, **When** process_charge(), **Then** total=29.97
3. **Given** amount=-0.01, currency="USD", **When** process_charge(), **Then** REJECTED (negative amount)
4. **Given** amount=0, currency="USD", **When** process_charge(), **Then** REJECTED (zero amount)

### Story 2 — Currency Validation (P0)

1. **Given** currency="USD", **When** process_charge(), **Then** accepted
2. **Given** currency="usd", **When** process_charge(), **Then** REJECTED (lowercase)
3. **Given** currency="US", **When** process_charge(), **Then** REJECTED (too short)
4. **Given** currency="USDD", **When** process_charge(), **Then** REJECTED (too long)

## Functional Requirements

- **FR-001**: System MUST reject any charge where amount <= 0
- **FR-002**: System MUST reject any currency not matching /^[A-Z]{3}$/
- **FR-003**: System MUST reject any single transaction total exceeding $10,000
- **FR-004**: result.total MUST equal amount * quantity exactly
