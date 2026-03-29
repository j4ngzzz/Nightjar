# Verify your FastAPI endpoint contracts

You have a FastAPI app. Nightjar will extract its contracts, find edge cases, and prove them.

---

## The app

`app.py` — a typical FastAPI payment service:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChargeRequest(BaseModel):
    amount: float
    currency: str
    user_id: str

class TransferRequest(BaseModel):
    from_user: str
    to_user: str
    amount: float

@app.post("/users")
def create_user(username: str, email: str):
    # Creates a new user account
    ...

@app.post("/charge")
def process_payment(req: ChargeRequest):
    # Charges the user's payment method
    fee = req.amount * 0.029 + 0.30
    total = req.amount + fee
    return {"status": "ok", "total": total, "fee": fee}

@app.post("/login")
def login(username: str, password: str):
    # Returns a session token
    ...

@app.get("/balance/{user_id}")
def get_balance(user_id: str):
    # Returns user's current balance
    ...

@app.post("/transfer")
def transfer(req: TransferRequest):
    # Transfers funds between users
    balance = get_balance(req.from_user)
    new_balance = balance - req.amount
    # ... update balances ...
    return {"status": "ok", "new_balance": new_balance}
```

---

## Step 1 — Scan to extract candidates

```bash
nightjar scan app.py
```

```
Nightjar scan — extracting invariant candidates
================================================

  Scanning app.py...

  create_user()
    → username must not be empty string                       [confidence: 0.91]
    → email must contain '@'                                  [confidence: 0.87]
    → returned user_id must be non-empty                      [confidence: 0.94]

  process_payment()
    → amount must be positive                                 [confidence: 0.95]
    → currency must be a 3-letter uppercase code              [confidence: 0.89]
    → fee must be non-negative                                [confidence: 0.97]
    → total == amount + fee                                   [confidence: 0.99]

  login()
    → password must be at least 8 characters                  [confidence: 0.88]
    → returned token must not be empty string                 [confidence: 0.93]
    → token expiry must be in the future                      [confidence: 0.85]

  get_balance()
    → user_id must not be empty string                        [confidence: 0.91]
    → returned balance must be non-negative                   [confidence: 0.90]

  transfer()
    → amount must be positive                                 [confidence: 0.95]
    → from_user balance after transfer must be >= 0           [confidence: 0.88]
    → transfer amount must not exceed from_user balance       [confidence: 0.91]

  15 candidates extracted. Write to .card/app.card.md? [y/N]: y

  Written: .card/app.card.md
```

Review the generated spec, promote the invariants you care about from `example`
to `property` or `formal` tier, and run verify.

---

## Step 2 — Verify

```bash
nightjar verify --spec .card/app.card.md
```

```
Nightjar v0.9 — Contract-Anchored Verification
================================================

  Stage 0  Preflight          PASS   spec valid, 15 invariants loaded
  Stage 1  Dependencies       PASS   no CVEs in fastapi, pydantic
  Stage 2  Schema             PASS
  Stage 2.5 Negation Proof   PASS
  Stage 3  Property Tests     FAIL

  ✗ INV-013 — transfer amount must not exceed from_user balance

  Counterexample found after 7 examples:
    transfer(from_user="alice", to_user="bob", amount=999999.0)
    where get_balance("alice") returns 100.0

    new_balance = 100.0 - 999999.0 = -999899.0

  Your transfer() allows negative balances.
  The spec requires: from_user balance after transfer >= 0.

  Fix: check balance before transferring, raise HTTPException(400) if insufficient.

  ✗ INV-009 — token expiry must be in the future

  Counterexample found after 1 example:
    login(username="test", password="password1")
    → {"token": "...", "expires_at": 0}

  Token expiry is set to epoch 0 (1970-01-01). This matches the fastmcp bug pattern:
  `exp = 0` is falsy — `if exp and exp < time.time()` never fires.

  Fix: use `if exp is None or exp < time.time()` to reject expired tokens.

  2 violations · 13 properties pass · Stage 4 skipped
  Time: 4.7s
```

Two real bugs. Neither would be caught by mypy, bandit, or a standard pytest suite.

---

## Step 3 — Fix and re-verify

**Fix 1 — transfer overdraft:**

```python
@app.post("/transfer")
def transfer(req: TransferRequest):
    balance = get_balance(req.from_user)
    if req.amount > balance:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    new_balance = balance - req.amount
    ...
```

**Fix 2 — token expiry:**

```python
# Bad:  if exp and exp < time.time()
# Good: if exp is None or exp < time.time()
```

Re-run:

```bash
nightjar verify --spec .card/app.card.md
```

```
  Stage 0  Preflight          PASS
  Stage 1  Dependencies       PASS
  Stage 2  Schema             PASS
  Stage 2.5 Negation Proof   PASS
  Stage 3  Property Tests     PASS   200 examples, 0 violations
  Stage 4  Formal Proof       PASS

  ✓ process_payment — PROVEN
  ✓ transfer — PROVEN
  ✓ login — PROVEN (token expiry)
  ✓ get_balance — PROVEN

  15/15 invariants proven · 0 violations
  Time: 31.2s
```

---

## Stage 3 vs Stage 4

**Stage 3 (Hypothesis)** generates random inputs to find counterexamples. It ran 200 test
cases per invariant. Fast (~5 seconds). Finds bugs by sampling the input space.

**Stage 4 (Dafny)** formally proves the property holds for *all* valid inputs — not just the
ones Hypothesis tried. Slower (~25 seconds). If Stage 4 passes, the property is mathematically
proven, not statistically likely.

Nightjar runs them in sequence: Stage 3 finds the bugs cheaply, Stage 4 proves the fixes
completely. If you're in a hurry, `--fast` skips Stage 4 and gives you Stage 3 coverage.

```bash
nightjar verify --fast  # Hypothesis only, ~5 seconds
nightjar verify         # Full proof, ~30 seconds
```

---

## Confidence scores

Each invariant shows a confidence score after verification:

```
INV-001  amount > 0          PROVEN     100%  (Dafny formal proof)
INV-002  currency is valid   PROVEN     100%  (Dafny formal proof)
INV-009  token expiry        VERIFIED    97%  (200 Hypothesis examples, no Dafny)
INV-013  no overdraft        PROVEN     100%  (Dafny formal proof)
```

A 100% score means Dafny proved it. A 97% score means Hypothesis tested it exhaustively
but Dafny timed out or wasn't available. Both are good — the scores are honest about
what kind of evidence backs them.

---

## Next

- [Quickstart: Find a hidden bug in 5 minutes →](quickstart-5min.md)
- [Add to CI in one commit →](ci-one-commit.md)
- [Example specs →](../../.card/examples/)
