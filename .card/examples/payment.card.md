---
card-version: "1.0"
id: payment-example
title: Payment Processing — Example Spec
status: active
module:
  owns: [process_charge(), calculate_fee(), refund(), validate_amount()]
  depends-on: {}
  excludes:
    - "Cryptocurrency payments"
    - "Subscription billing"
contract:
  inputs:
    - name: amount
      type: float
      constraints: "amount > 0 AND amount <= 1_000_000"
    - name: currency
      type: string
      constraints: "len(currency) == 3 AND currency.isupper()"
    - name: quantity
      type: int
      constraints: "quantity >= 1"
    - name: fee_pct
      type: float
      constraints: "0 <= fee_pct <= 100"
  outputs:
    - name: ChargeResult
      type: object
      schema:
        transaction_id: string
        status: string
        amount_charged: float
        fee: float
        total: float
        currency: string
  errors:
    - InvalidAmountError
    - InvalidCurrencyError
    - RefundExceedsChargeError
    - OverflowError
invariants:
  - id: PAY-INV-001
    tier: property
    statement: "amount is always strictly positive — amount > 0, never amount >= 0"
    rationale: "Zero-amount charges are silent no-ops. $0.00 charges reach the gateway and count against rate limits without moving money."
  - id: PAY-INV-002
    tier: property
    statement: "currency is a valid ISO 4217 code — exactly 3 uppercase ASCII letters"
    rationale: "Invalid currency codes cause silent gateway rejections logged as 'invalid_request', which appear in reconciliation but not in application logs."
  - id: PAY-INV-003
    tier: formal
    statement: "total == amount + fee for every successful charge"
    rationale: "Financial integrity — no money created or destroyed. Accounting systems downstream will flag any discrepancy."
  - id: PAY-INV-004
    tier: property
    statement: "fee is always non-negative — fee >= 0"
    rationale: "Negative fees silently credit the merchant account. A fee of -$0.01 per transaction compounds to significant loss at scale."
  - id: PAY-INV-005
    tier: formal
    statement: "refund amount <= original charge amount"
    rationale: "Refunding more than charged is an over-refund. Over-refunds have caused real financial losses in production systems."
  - id: PAY-INV-006
    tier: property
    statement: "fee_pct is in range [0, 100] inclusive"
    rationale: "A fee percentage > 100 means charging more in fees than the transaction amount. A negative percentage means paying the customer."
  - id: PAY-INV-007
    tier: formal
    statement: "total = amount * quantity does not overflow float range"
    rationale: "Large quantity * large amount can silently overflow to inf or wrap around. Use Decimal for production financial calculations."
  - id: PAY-INV-008
    tier: property
    statement: "process_charge raises InvalidAmountError when amount <= 0"
    rationale: "Precondition enforcement — the error must surface at the entry point, not silently propagate."
  - id: PAY-INV-009
    tier: property
    statement: "process_charge raises InvalidCurrencyError when currency is not 3 uppercase letters"
    rationale: "Currency codes like 'usd', 'US', 'USDX' must all be rejected at the validation boundary."
---

## Intent

Process payment charges securely. Validate all inputs before touching the gateway.
Maintain perfect financial accounting — every cent charged must equal every cent
received by the merchant plus fees.

This spec is an example for Nightjar tutorials. It demonstrates common payment
invariants that LLM-generated code frequently violates on first generation:
amount boundary (>0 vs >=0), currency format, fee sign, and refund ceiling.

## Acceptance Criteria

### Story 1 — Process Charge (P1)

**As a** checkout system, **I want** to charge a customer, **so that** an order can be fulfilled.

1. **Given** amount=1000, currency="USD", **When** process_charge() is called, **Then** a ChargeResult with status="success" and total=1029.30 (2.9% + $0.30) is returned
2. **Given** amount=0.0, currency="USD", **When** process_charge() is called, **Then** InvalidAmountError is raised
3. **Given** amount=-1.0, currency="USD", **When** process_charge() is called, **Then** InvalidAmountError is raised
4. **Given** amount=1000, currency="usd", **When** process_charge() is called, **Then** InvalidCurrencyError is raised
5. **Given** amount=1000, currency="USDX", **When** process_charge() is called, **Then** InvalidCurrencyError is raised

### Story 2 — Refund (P2)

**As a** support agent, **I want** to refund a charge, **so that** the customer gets their money back.

1. **Given** a completed charge of 1000.0, **When** refund(amount=1000.0) is called, **Then** the full amount is refunded
2. **Given** a completed charge of 1000.0, **When** refund(amount=500.0) is called, **Then** a partial refund of 500.0 is processed
3. **Given** a completed charge of 1000.0, **When** refund(amount=1500.0) is called, **Then** RefundExceedsChargeError is raised

### Edge Cases

- What if fee_pct = 0? → fee = 0.0, total = amount — valid
- What if fee_pct = 100? → fee = amount, total = 2 * amount — valid (unusual but permitted by spec)
- What if quantity * amount approaches float max? → OverflowError raised
- What if currency = "" (empty string)? → InvalidCurrencyError raised

## Functional Requirements

- **FR-PAY-001**: System MUST reject amount <= 0 with InvalidAmountError before any gateway call
- **FR-PAY-002**: System MUST reject currency unless exactly 3 uppercase ASCII letters
- **FR-PAY-003**: System MUST calculate fee as fee_pct / 100 * amount, minimum 0
- **FR-PAY-004**: System MUST ensure total == amount + fee (no rounding discrepancy > 0.001)
- **FR-PAY-005**: System MUST reject refunds exceeding the original charge amount
