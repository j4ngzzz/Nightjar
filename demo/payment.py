"""Insecure payment processor -- the 60-second Nightjar demo.

This file intentionally has a bug: deduct() allows negative balances.
Nightjar catches it via formal verification and regenerates safe code.

Demo script (Scout 2 S2):
  [0-5s]   $ cat demo/payment.py          -- show the insecure code
  [5-15s]  $ nightjar verify -c demo/payment.card.md  -- FAIL: balance=-49.99
  [15-30s] $ nightjar auto "payment processor with balance >= 0 invariant"
  [30-45s] $ nightjar verify -c .card/payment.card.md -- PASS: proved
  [45-60s] "Your LLM writes code. Nightjar proves it. Not tested. PROVED."
"""


def deduct(balance: float, amount: float) -> float:
    """Deduct amount from balance.

    BUG: No guard against negative balance.
    Nightjar proves: for all balance >= 0 and amount >= 0,
    deduct(balance, amount) >= 0 ONLY IF amount <= balance.

    Counterexample: balance=0.01, amount=50.0 -> returns -49.99
    """
    return balance - amount


def deposit(balance: float, amount: float) -> float:
    """Deposit amount into balance.

    Invariant: amount > 0 and result > balance.
    """
    return balance + amount


def transfer(from_balance: float, to_balance: float, amount: float) -> tuple[float, float]:
    """Transfer amount between two accounts.

    BUG: No atomicity -- if deduct succeeds but deposit fails,
    money vanishes. Also inherits deduct's negative balance bug.
    """
    new_from = deduct(from_balance, amount)
    new_to = deposit(to_balance, amount)
    return new_from, new_to
