---
card-version: "1.0"
id: payment
title: Payment Processor
status: draft
module:
  owns: [deduct, deposit, transfer]
  depends-on: {}
contract:
  inputs:
    - name: balance
      type: float
      constraints: ">= 0"
    - name: amount
      type: float
      constraints: ">= 0"
  outputs:
    - name: new_balance
      type: float
      constraints: ">= 0"
invariants:
  - tier: formal
    rule: "deduct(balance, amount) requires amount <= balance ensures result >= 0"
  - tier: property
    rule: "for any balance >= 0 and amount >= 0 where amount <= balance: deduct(balance, amount) >= 0"
  - tier: example
    rule: "deduct(100.0, 50.0) == 50.0"
  - tier: formal
    rule: "deposit(balance, amount) requires amount > 0 ensures result > balance"
  - tier: formal
    rule: "transfer preserves total: from_balance + to_balance == new_from + new_to"
---

## Intent

A payment processor that charges credit cards and manages account balances.
The critical invariant: **no account balance may ever go negative.**

This is the canonical Nightjar demo -- it shows formal verification catching
a real bug (negative balance) that unit tests would miss.

## Acceptance Criteria

### Story 1 -- Safe Deduction (P0)

**As a** payment system, **I want** balance deductions to be safe,
**so that** no account ever goes negative.

1. **Given** balance=100, amount=50, **When** deduct(), **Then** result=50
2. **Given** balance=0.01, amount=50, **When** deduct(), **Then** REJECTED (amount > balance)

### Edge Cases

- What happens when amount == balance? -> Returns 0.0 (allowed)
- What happens when amount == 0? -> Returns balance (no-op, allowed)
- What happens when balance == 0 and amount > 0? -> REJECTED

## Functional Requirements

- **FR-001**: System MUST ensure deduct() never produces negative balance
- **FR-002**: System MUST ensure deposit() always increases balance
- **FR-003**: System MUST ensure transfer() preserves total across accounts
