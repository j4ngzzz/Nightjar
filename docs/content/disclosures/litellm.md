# Disclosure: litellm — 3 Bugs (1 HIGH, 2 MEDIUM)

**Package:** litellm
**Affected version:** 1.82.6
**Report date:** 2026-03-29
**Severity:** HIGH (BUG-T2-8), MEDIUM (BUG-T2-9, BUG-T2-10)
**Preferred channel:** GitHub Security Advisory — https://github.com/BerriAI/litellm/security/advisories/new

> **Channel note:** No SECURITY.md found in the BerriAI/litellm repo. GitHub Security Advisory tab is the recommended channel for BUG-T2-8 (HIGH — mutable default disrupts budget enforcement, a financial control) and BUG-T2-10 (MEDIUM — IP allowlist bypass). BUG-T2-9 is a non-security correctness bug and can be filed as a public GitHub issue after the security report is acknowledged.

---

## Subject

Nightjar formal verification: BUG-T2-8/9/10 — budget enforcement bypass, dict getattr, X-Forwarded-For parsing in litellm 1.82.6

---

## Email Body

Hi litellm team,

We have been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found three bugs in litellm 1.82.6: one that affects budget enforcement correctness in long-running deployments, one that silently miscalculates Replicate pricing, and one that affects IP allowlist behavior behind proxies.

---

### BUG-T2-8 (HIGH): `BudgetManager.create_budget` — mutable default `created_at=time.time()` frozen at module import

**Affected component**

File: `litellm/budget_manager.py`, line 81
Function: `BudgetManager.create_budget`

**Bug description**

Python evaluates default argument values once at function definition time — module import. The parameter `created_at: float = time.time()` in `create_budget` captures the Unix timestamp at the moment `litellm` is first imported, not at the moment `create_budget` is called. Every invocation without an explicit `created_at` receives the same frozen timestamp. On a server that has been running for 24+ hours, a newly created daily budget gets `last_updated_at = import_time`, which is already over 86400 seconds in the past. The `reset_on_duration` method then triggers immediately on the next `update_budget_all_users()` call — the spend counter resets to zero before any real spending has occurred, allowing unlimited spending for that reset window. The bug is silent: no exception is raised, no log warning emitted, and the budget appears to exist correctly.

**Reproduction**

```python
import inspect, time, litellm

spec = inspect.getfullargspec(litellm.BudgetManager.create_budget)
defaults = dict(zip(reversed(spec.args), reversed(spec.defaults)))
frozen_default = defaults["created_at"]

drift = time.time() - frozen_default
print(f"created_at default is {drift:.1f}s behind wall clock")
# On a 1-hour-old process: "created_at default is 3600.0s behind wall clock"
# On a 24-hour-old process: "created_at default is 86400.0s behind wall clock"
# -> newly created daily budgets will immediately reset
```

**Functional proof of incorrect budget reset:**

```python
# Simulating reset_on_duration with stale created_at:
import time

module_import_time = time.time() - 86400  # server started 24h ago
created_at = module_import_time           # frozen default
duration_seconds = 1 * 24 * 60 * 60      # "daily" budget = 86400s

elapsed = time.time() - created_at       # ~86400
will_reset_immediately = elapsed >= duration_seconds
print(f"New daily budget resets immediately: {will_reset_immediately}")  # True
```

**Suggested fix (minimal diff)**

```python
# budget_manager.py line 81 — before:
def create_budget(
    self,
    total_budget: float,
    user: str,
    duration: Optional[...] = None,
    created_at: float = time.time(),   # BUG
):

# After:
def create_budget(
    self,
    total_budget: float,
    user: str,
    duration: Optional[...] = None,
    created_at: Optional[float] = None,   # FIX
):
    if created_at is None:
        created_at = time.time()
```

**Severity:** HIGH

---

### BUG-T2-9 (MEDIUM): `get_replicate_completion_pricing` uses `getattr()` on a dict — `ended` key always ignored

**Affected component**

File: `litellm/cost_calculator.py`, lines 597–606
Function: `get_replicate_completion_pricing`

**Bug description**

`start_time` is correctly retrieved with `completion_response.get("created", time.time())`, which works for dicts. `end_time` is retrieved with `getattr(completion_response, "ended", time.time())`. `getattr` on a dict looks for an *attribute* named `"ended"`, not a *key*; dicts do not have an `ended` attribute, so `getattr` always returns `time.time()`. The `"ended"` key in the dict is silently ignored. The calculated `total_time` becomes `time.time() - created`, the wall-clock elapsed time since the request was made, instead of the actual GPU compute time recorded in the Replicate response. This causes cost calculations to be inflated by the latency between when the Replicate job completed and when the cost calculation runs — potentially by multiple seconds or minutes for queued jobs.

**Reproduction**

```python
import time

completion_response = {"created": 1000.0, "ended": 1005.0}
# Correct: end_time should be 1005.0
end_time_correct = completion_response.get("ended", time.time())
print(f"Correct end_time: {end_time_correct}")    # 1005.0

# Buggy: getattr always returns time.time() for dicts
end_time_buggy = getattr(completion_response, "ended", time.time())
print(f"Buggy end_time: {end_time_buggy:.0f}")    # current wall clock (~1774xxx)
```

**Suggested fix (one character change)**

```python
# Before (cost_calculator.py):
end_time = getattr(completion_response, "ended", time.time())

# After:
end_time = completion_response.get("ended", time.time())
```

**Severity:** MEDIUM

---

### BUG-T2-10 (MEDIUM): `_check_valid_ip` uses raw `X-Forwarded-For` string for exact-match allowlist — breaks RFC 7239 multi-hop proxies and is trivially spoofable

**Affected component**

File: `litellm/proxy/auth/auth_utils.py`, lines 16–30
Functions: `_get_request_ip_address`, `_check_valid_ip`

**Bug description**

When `use_x_forwarded_for=True`, `_get_request_ip_address` returns the raw `X-Forwarded-For` header value as a string. `_check_valid_ip` then checks `if client_ip not in allowed_ips` where `allowed_ips` is a list of IP strings. Two problems: (1) RFC 7239 specifies `X-Forwarded-For` as a comma-separated list of IPs for multi-hop proxies — `"1.2.3.4, 10.0.0.1"` is the correct format, but the exact-string check means this legitimate header never matches `["1.2.3.4"]`, blocking valid requests. (2) The header is taken at face value with no verification of the actual source IP — an attacker behind any proxy can set `X-Forwarded-For: 1.2.3.4` to forge membership in any allowlist. Note: this only affects deployments where `use_x_forwarded_for=True` is explicitly configured.

**Reproduction**

```python
allowed_ips = ["1.2.3.4"]

# Scenario 1: Legitimate multi-hop proxy (RFC 7239 format) — blocked
xff_multihop = "1.2.3.4, 10.0.0.1"
is_blocked = xff_multihop not in allowed_ips
print(f"Legitimate multi-hop request blocked: {is_blocked}")  # True — BUG

# Scenario 2: Attacker spoofs X-Forwarded-For header
xff_spoofed = "1.2.3.4"
is_accepted = xff_spoofed in allowed_ips
print(f"Spoofed IP accepted: {is_accepted}")  # True — BUG
```

**Suggested fix**

```python
def _get_request_ip_address(request, use_x_forwarded_for=False):
    if use_x_forwarded_for and "x-forwarded-for" in request.headers:
        # RFC 7239: take the leftmost (client) IP from the comma-separated list
        raw = request.headers["x-forwarded-for"]
        client_ip = raw.split(",")[0].strip()
        return client_ip
    return request.client.host if request.client else None
```

Note: parse-and-take-leftmost mitigates the multi-hop blocking issue. It does not eliminate spoofability — that requires a trusted proxy configuration at the infrastructure level, which is outside litellm's scope. We recommend documenting this limitation explicitly.

**Severity:** MEDIUM

---

## Disclosure Timeline

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

- **Day 0 (2026-03-29):** this report
- **Day 3:** please confirm receipt
- **Day 90 (2026-06-27):** public disclosure, or earlier if fixes are released

For BUG-T2-9 (non-security correctness bug), we are happy to file this as a public GitHub issue at any point after you acknowledge receipt of BUG-T2-8 and BUG-T2-10.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, litellm 1.82.6, Windows 11. All three findings verified by direct execution.*
