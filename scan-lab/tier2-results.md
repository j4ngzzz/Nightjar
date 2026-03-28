# Tier 2 Code Scan Results
**Packages scanned:** fastmcp 2.14.5, litellm (installed)
**Date:** 2026-03-28
**Method:** Source inspection via `inspect` + runtime verification of each finding

---

## Summary

| # | Package | File | Bug | Severity | Confirmed |
|---|---------|------|-----|----------|-----------|
| 1 | fastmcp | `server/auth/jwt_issuer.py` | JWT expiry check uses falsy test — `exp=None` skips check | HIGH | Yes |
| 2 | fastmcp | `server/auth/jwt_issuer.py` | `exp=0` bypasses expiry check (0 is falsy in Python) | HIGH | Yes |
| 3 | fastmcp | `server/auth/redirect_validation.py` | `fnmatch` wildcard allows query-param redirect URI bypass | HIGH | Yes |
| 4 | fastmcp | `server/auth/redirect_validation.py` | `OAuthProxyProvider` doc says `None=localhost-only` but code allows all | MEDIUM | Yes |
| 5 | fastmcp | `utilities/json_schema.py` | `_prune_param` and `_single_pass_optimize` mutate input schema in-place despite "immutable" docstring | MEDIUM | Yes |
| 6 | litellm | `budget_manager.py` | Mutable default argument `created_at=time.time()` frozen at module import | HIGH | Yes |
| 7 | litellm | `cost_calculator.py` | `getattr(dict_response, 'ended', ...)` silently returns default instead of dict value | MEDIUM | Yes |
| 8 | litellm | `proxy/auth/auth_utils.py` | Raw `X-Forwarded-For` header used verbatim without parsing comma-separated IPs | MEDIUM | Yes |

---

## Detailed Findings

---

### BUG-1 (HIGH): fastmcp JWT expiry check — missing `exp` not enforced

**File:** `fastmcp/server/auth/jwt_issuer.py`, line 214–217

**Code:**
```python
def verify_token(self, token: str) -> dict[str, Any]:
    payload = self._jwt.decode(token, self._signing_key)  # returns JWTClaims dict

    # Validate expiration
    exp = payload.get("exp")
    if exp and exp < time.time():           # BUG: 'if exp' is truthy check
        raise JoseError("Token has expired")
```

**Problem:** `authlib.jose.JsonWebToken.decode()` does NOT call `.validate()` — it only verifies the signature. The expiry check is done manually by fastmcp. The manual check uses `if exp and ...`, which means:

- Token with no `exp` field: `exp = None`, `if None` = `False` → check skipped → token never expires
- Token with `exp = 0` (Unix epoch): `if 0` = `False` → check skipped → 1970-era token accepted

**Verified empirically:**
```python
payload_no_exp = {'iss': ..., 'aud': ..., 'client_id': ..., 'jti': ...}
token = jwt.encode(header, payload_no_exp, key).decode()
decoded = jwt.decode(token, key)
exp = decoded.get('exp')  # None
# if exp and exp < time.time() evaluates to False
# Token is ACCEPTED with no expiry enforcement
```

**Correct fix:** `if exp is None: raise JoseError("Token missing exp claim")` or `if not exp or exp < time.time():`

**Real-world impact:** If an attacker obtains the HS256 signing key (or finds a scenario where the proxy issues a token without `exp`), they can create non-expiring tokens. The missing-exp case also applies to any token issued by a buggy code path that omits the field.

---

### BUG-2 (HIGH): fastmcp JWT `exp=0` bypass

Same function as BUG-1. An integer `0` is falsy in Python. Any token crafted with `"exp": 0` passes `if exp and ...` silently. While `exp=0` (Unix epoch, Jan 1 1970) would not appear in legitimately issued tokens, the check is fragile and should be `if exp is None` rather than `if not exp`.

---

### BUG-3 (HIGH): fastmcp redirect URI — `fnmatch` wildcard bypass

**File:** `fastmcp/server/auth/redirect_validation.py`, lines 8–58

**Code:**
```python
import fnmatch

def matches_allowed_pattern(uri: str, pattern: str) -> bool:
    return fnmatch.fnmatch(uri, pattern)
```

**Problem:** `fnmatch` does shell glob matching on the raw URI string, not on parsed URL components. The `*` wildcard matches any characters including `.`, `/`, `?`, and `=`. This enables:

**Attack 1 — Query param bypass for `*.domain` patterns:**
```python
pattern = "https://*.example.com/*"
uri     = "https://evil.com/cb?legit.example.com/x"

fnmatch.fnmatch(uri, pattern)  # True — BUG
# But urlparse(uri).hostname == "evil.com"
# The OAuth authorization code is sent to evil.com
```

**Attack 2 — `localhost:*` matches non-localhost domains:**
```python
pattern = "http://localhost:*"
uri     = "http://localhost:evil.com"

fnmatch.fnmatch(uri, pattern)  # True — BUG
# urlparse raises ValueError because "evil.com" is not a valid port
# But the server-side validation runs before any redirect
```

**Docstring** at line 12–15 even says `http://localhost:*` matches "any localhost port" — but `*` is not bounded to port-number characters.

**Correct fix:** Parse the URI with `urllib.parse.urlparse` first, then match on `netloc`/`path` separately. For port wildcards, check `hostname == "localhost"` and `port` is a valid integer.

---

### BUG-4 (MEDIUM): fastmcp `OAuthProxyProvider` — documented default contradicts behavior

**File:** `fastmcp/server/auth/oauth_proxy.py`, line 677

**Docstring:**
```
allowed_client_redirect_uris: If None (default), only localhost redirect URIs are allowed.
```

**Actual behavior (`redirect_validation.py` line 50–51):**
```python
if allowed_patterns is None:
    return True  # "for DCR compatibility"
```

When `allowed_client_redirect_uris=None` (the default), `validate_redirect_uri` returns `True` for every URI including `https://evil.com`. The two files have contradictory comments about what `None` means.

**Impact:** Developers who read the `OAuthProxyProvider` docs and rely on the "default is secure" assumption leave their proxy open to arbitrary redirect URIs without knowing it.

---

### BUG-5 (MEDIUM): fastmcp `compress_schema` / `_prune_param` — in-place mutation despite "immutable" claim

**File:** `fastmcp/utilities/json_schema.py`

**Docstrings claim:**
- `_prune_param`: "Return a **new** schema with `*param*` removed"
- `_single_pass_optimize`: "**Immutable design** prevents shared reference bugs"

**Actual behavior — all mutations happen in-place:**
```python
schema = {'type': 'object', 'title': 'Foo', 'properties': {...}, 'required': [...]}
result = compress_schema(schema, prune_params=['ctx'], prune_titles=True)

result is schema          # True — same object
'title' in schema         # False — original mutated
'ctx' in schema['properties']  # False — original mutated
```

The codebase has one working patch (`tool_transform.py` line 613: `deepcopy` before calling `compress_schema`) but most callers (`tools/tool.py`, `prompts/prompt.py`, `server/context.py`, `server/elicitation.py`) do not deep-copy. Any caller that stores a schema reference and then passes it to `compress_schema` will see their stored schema silently modified.

**Confirmed workaround in the codebase:**
```python
# tool_transform.py line 613:
# "Deep copy to prevent compress_schema from mutating parent tool's $defs"
parent_defs = deepcopy(parent_tool.parameters.get("$defs", {}))
```

---

### BUG-6 (HIGH): litellm `BudgetManager.create_budget` — mutable default argument `time.time()`

**File:** `litellm/budget_manager.py`, line 81

**Code:**
```python
def create_budget(
    self,
    total_budget: float,
    user: str,
    duration: Optional[Literal["daily", "weekly", "monthly", "yearly"]] = None,
    created_at: float = time.time(),   # BUG: evaluated ONCE at module import
):
```

**Problem:** Python evaluates default argument values once at function definition time (module import). Every call to `create_budget()` without an explicit `created_at` gets the **same** timestamp — the time the litellm module was first imported.

**Impact via `reset_on_duration`:**
```python
def reset_on_duration(self, user: str):
    last_updated_at = self.user_dict[user]["last_updated_at"]
    duration_in_seconds = self.user_dict[user]["duration"] * HOURS_IN_A_DAY * 60 * 60
    if current_time - last_updated_at >= duration_in_seconds:
        self.reset_cost(user)  # resets the spend counter
```

On a server that has been running for 24+ hours, a **newly created daily budget** will immediately trigger `reset_on_duration` because `last_updated_at` points to module import time (>24 hours ago), not the actual creation time. The spend counter resets on the very first `update_budget_all_users()` call, allowing unbounded spending.

**Verified:**
```python
module_import_time = time.time() - 86400  # server started 24h ago
def create_budget(..., created_at=module_import_time): ...

budget = create_budget(100.0, 'alice', duration='daily')
elapsed = time.time() - budget['last_updated_at']  # ~86400 seconds
will_reset = elapsed >= 86400  # True — immediately resets
```

**Correct fix:** `created_at: float = None` and `created_at = created_at or time.time()` inside the body.

---

### BUG-7 (MEDIUM): litellm `get_replicate_completion_pricing` — `getattr` on dict returns wrong value

**File:** `litellm/cost_calculator.py`, lines 597–606

**Code:**
```python
def get_replicate_completion_pricing(completion_response: dict, total_time=0.0):
    if total_time == 0.0:
        start_time = completion_response.get("created", time.time())  # correct
        end_time = getattr(completion_response, "ended", time.time())  # BUG
        total_time = end_time - start_time
    return a100_80gb_price_per_second_public * total_time / 1000
```

**Problem:** `start_time` uses `.get()` (correct for dicts), but `end_time` uses `getattr()`. When `completion_response` is a `dict`, `getattr(d, "ended", default)` always returns `default` because dicts don't have an `ended` attribute. The `"ended"` key in the dict is ignored.

**Result:** `end_time` is always `time.time()`, making `total_time = time.time() - start_time` instead of the correct `end_time - start_time`. For a response that completed at `created=T0` and `ended=T0+5s`, the calculated cost uses the wall-clock time since the request, not the actual GPU time.

**Correct fix:** `end_time = completion_response.get("ended", time.time())`

---

### BUG-8 (MEDIUM): litellm IP allowlist — raw `X-Forwarded-For` not parsed per RFC 7239

**File:** `litellm/proxy/auth/auth_utils.py`, lines 16–30

**Code:**
```python
def _get_request_ip_address(request, use_x_forwarded_for=False):
    if use_x_forwarded_for is True and "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"]  # raw header
    ...

def _check_valid_ip(allowed_ips, request, use_x_forwarded_for=False):
    client_ip = _get_request_ip_address(...)
    if client_ip not in allowed_ips:   # exact string match
        return False, client_ip
```

**Two bugs in one:**

**8a — Allowlist bypass (when `use_x_forwarded_for=True`):**
An attacker behind a proxy can set `X-Forwarded-For: 1.2.3.4` (a whitelisted IP). The function returns the raw header value `"1.2.3.4"`, which matches `allowed_ips = ["1.2.3.4"]`. The real originating IP is never checked.

**8b — Legitimate multi-hop proxies always blocked:**
RFC 7239 specifies `X-Forwarded-For` as a comma-separated list: `"client, proxy1, proxy2"`. If the header is `"1.2.3.4, 10.0.0.1"`, the raw string `"1.2.3.4, 10.0.0.1"` is not in `allowed_ips = ["1.2.3.4"]`, so the legitimate request is blocked. The client IP is in the value but the exact-match check fails.

**Note:** `use_x_forwarded_for` is `False` by default, so this only affects deployments that explicitly enable it.

---

## What Was NOT Found (False Positive Avoidance)

- **fastmcp `JWTIssuer.issue_access_token`:** Correctly always sets `exp = now + expires_in`. The bug is only in `verify_token`.
- **fastmcp OAuth `load_refresh_token`:** Correctly validates `client_id` ownership before returning.
- **fastmcp `load_access_token`:** Two-tier validation (JWT + upstream provider) is architecturally sound.
- **litellm `is_admin`:** Simple scope check is correct given the JWT handler validates the token first.
- **litellm `update_valid_token_with_end_user_params`:** Correctly guards with `is not None` checks to avoid clobbering custom auth values.
- **`check_if_auth_required`** (fastmcp): Returns `False` for 5xx errors (auth not required). This is a design choice for pre-flight checks, not a security bypass, since the actual MCP endpoint always enforces auth independently.

---

## Packages Unavailable (Disk Full on C:)

- **langchain-core** — install failed (`No space left on device` on C:)
- **pydantic-ai** — install failed (same reason)

These could not be scanned in this session. Retry after clearing C: drive space.
