"""Payment charge processor — tutorial demo for Nightjar.

This file intentionally contains a bug: process_charge() accepts
negative and zero amounts without raising an error.

Nightjar's Stage 3 (Hypothesis property-based testing) finds the
counterexample automatically: amount=-0.01, currency="USD".

The fix is one guard clause: `if amount <= 0: raise ValueError`.
After the fix, Stage 4 (Dafny formal verification) proves correctness
for ALL valid inputs — not just the ones you tested.

Demo story:
  [bug ]  $ nightjar verify demo/tutorial-payment.card.md
           FAIL: amount=-0.01 accepted — violates "amount must be positive"
  [fix ]  add: if amount <= 0: raise ValueError("amount must be positive")
  [proof] $ nightjar verify demo/tutorial-payment.card.md
           FORMALLY VERIFIED — all invariants hold for all valid inputs
"""


def process_charge(amount: float, currency: str, quantity: int = 1) -> dict:
    """Process a charge against a customer payment method.

    BUG: No guard on amount sign or zero value.
    Nightjar finds: process_charge(-0.01, "USD") returns total=-0.01
    This violates the invariant: "amount must always be positive."

    Args:
        amount: Charge amount in the given currency. Must be > 0.
        currency: ISO 4217 currency code (3 uppercase letters, e.g. "USD").
        quantity: Number of units. Must be >= 1.

    Returns:
        dict with keys: amount, currency, quantity, total, status
    """
    # BUG: missing validation — amount <= 0 silently accepted
    total = amount * quantity
    return {
        "amount": amount,
        "currency": currency,
        "quantity": quantity,
        "total": total,
        "status": "charged",
    }


# --- FIXED VERSION (shown after Nightjar finds the bug) ---
#
# def process_charge(amount: float, currency: str, quantity: int = 1) -> dict:
#     if amount <= 0:
#         raise ValueError(f"amount must be positive, got {amount}")
#     if len(currency) != 3 or not currency.isupper():
#         raise ValueError(f"currency must be 3 uppercase letters, got {currency!r}")
#     if quantity < 1:
#         raise ValueError(f"quantity must be >= 1, got {quantity}")
#     total = amount * quantity
#     if total > 10_000:
#         raise ValueError(f"transaction total {total} exceeds $10,000 limit")
#     return {
#         "amount": amount,
#         "currency": currency,
#         "quantity": quantity,
#         "total": total,
#         "status": "charged",
#     }
