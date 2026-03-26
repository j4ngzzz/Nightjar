# CARD Demo — Payment Processing

This demo shows the full `contractd` pipeline using a payment processing module.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run the demo
bash demo/run_demo.sh
```

## What the Demo Shows

1. **Spec Parsing** — `.card/payment.card.md` is parsed into structured types
2. **Tiered Invariants** — 5 invariants across example, property, and formal tiers
3. **Pre-flight Verification** — Stage 0 validates spec structure
4. **Generation Pipeline** — Analyst -> Formalizer -> Coder (3 LLM calls via litellm)
5. **MCP Integration** — 3 tools for IDE integration
6. **Full Test Suite** — 169+ tests passing

## The Payment Spec

The demo uses `.card/payment.card.md` which defines:

- **3 inputs**: amount (integer), currency (string), user_id (string)
- **1 output**: PaymentResult (object with transaction_id, status, amount_charged, fee)
- **4 error types**: InvalidAmountError, InsufficientFundsError, CurrencyNotSupportedError, PaymentGatewayError
- **5 invariants**:
  - `INV-001` (example): Basic happy path smoke test
  - `INV-002` (property): Financial integrity — amount + fee = total
  - `INV-003` (property): Refund correctness
  - `INV-004` (formal): Accounting invariant — mathematical proof
  - `INV-005` (property): Input boundary enforcement

## Model Swap

CARD is model-agnostic. Swap the LLM and the same verification passes:

```bash
# Default: Claude
CARD_MODEL=claude-sonnet-4-6 contractd build --contract .card/payment.card.md

# Budget: DeepSeek (10x cheaper)
CARD_MODEL=deepseek/deepseek-chat contractd build --contract .card/payment.card.md

# Premium: OpenAI o3
CARD_MODEL=openai/o3 contractd build --contract .card/payment.card.md
```

Different models produce different code, but the verification pipeline ensures all outputs satisfy the same invariants.

## CLI Commands

```bash
contractd init payment          # Scaffold a new spec
contractd verify --contract .card/payment.card.md        # Run verification
contractd verify --fast --contract .card/payment.card.md  # Skip Dafny (stages 0-3)
contractd build --contract .card/payment.card.md          # Generate + verify + compile
contractd explain --contract .card/payment.card.md        # Show last failure
```
