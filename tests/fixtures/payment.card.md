---
card-version: "1.0"
id: payment-processing
title: Payment Processing Module
status: draft
module:
  owns: [process_payment(), validate_amount(), calculate_fee(), refund()]
  depends-on:
    postgres: "approved"
    stripe-sdk: "^5.0"
  excludes:
    - "Cryptocurrency payments"
    - "Subscription billing"
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
invariants:
  - id: INV-001
    tier: example
    statement: "Processing a $10 USD payment returns a valid transaction_id"
    rationale: "Basic smoke test for the happy path"
  - id: INV-002
    tier: property
    statement: "For any valid payment, amount_charged + fee equals the total deducted from user"
    rationale: "Financial integrity — no money created or destroyed"
  - id: INV-003
    tier: property
    statement: "A refund for amount X results in exactly X being returned to the user"
    rationale: "Refund correctness"
  - id: INV-004
    tier: formal
    statement: "The total of all processed payments minus all refunds equals the net revenue"
    rationale: "Accounting invariant — must be mathematically proven for audit compliance"
  - id: INV-005
    tier: property
    statement: "No payment with amount <= 0 or amount > 1_000_000 is ever processed"
    rationale: "Input validation boundary enforcement"
constraints:
  performance: "p95 latency < 2000ms"
  security: "PCI-DSS Level 1 compliance required"
  idempotency: "Duplicate payment requests with same idempotency key return cached result"
---

## Intent

Process payments securely and reliably. Accept payments in multiple currencies,
calculate fees, and support full and partial refunds. All financial operations
must maintain perfect accounting invariants — no money created or destroyed.

## Acceptance Criteria

### Story 1 — Process Payment (P1)

**As a** customer, **I want** to pay for my order, **so that** I can receive my goods.

1. **Given** a valid amount of 1000 cents in USD, **When** process_payment() is called, **Then** a PaymentResult with status "success" and a valid transaction_id is returned
2. **Given** an amount of 0, **When** process_payment() is called, **Then** InvalidAmountError is raised
3. **Given** an amount of 1_000_001, **When** process_payment() is called, **Then** InvalidAmountError is raised

### Story 2 — Refund (P2)

**As a** customer support agent, **I want** to refund a payment, **so that** the customer gets their money back.

1. **Given** a completed payment of 1000, **When** refund() is called with amount 1000, **Then** the full amount is refunded
2. **Given** a completed payment of 1000, **When** refund() is called with amount 500, **Then** a partial refund of 500 is processed
3. **Given** a completed payment of 1000, **When** refund() is called with amount 1500, **Then** InvalidAmountError is raised

### Edge Cases

- What happens when currency is not in supported list? → CurrencyNotSupportedError
- What happens when payment gateway is down? → PaymentGatewayError with retry suggestion
- What happens when user_id is empty string? → InvalidAmountError
- [NEEDS CLARIFICATION: What about partial refunds exceeding original amount across multiple refund calls?]

## Functional Requirements

- **FR-001**: System MUST validate amount is between 1 and 1,000,000 cents inclusive
- **FR-002**: System MUST validate currency is one of USD, EUR, GBP, JPY
- **FR-003**: System MUST calculate fee as 2.9% + 30 cents for USD, varying by currency
- **FR-004**: System SHOULD support idempotency keys to prevent duplicate charges
- **FR-005**: System MUST emit payment.processed event on successful payment
