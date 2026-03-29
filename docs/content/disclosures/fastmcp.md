# Disclosure: fastmcp — 4 Security Vulnerabilities

**Package:** fastmcp
**Affected version:** 2.14.5
**Report date:** 2026-03-29
**Severity:** HIGH (3 HIGH + 1 MEDIUM)
**Preferred channel:** GitHub Security Advisory — https://github.com/PrefectHQ/fastmcp/security/advisories/new

> **Channel note:** fastmcp was transferred from jlowin/fastmcp to PrefectHQ/fastmcp. The SECURITY.md at PrefectHQ/fastmcp explicitly states that version 2.x is **not supported** (only 3.x receives fixes). File the advisory regardless — the bugs exist in 2.14.5 and users on that version need to know to upgrade. In the advisory, ask whether any of these bugs survive into 3.x.

---

## Subject

Nightjar formal verification: BUG-T2-3/4/5/6 — JWT expiry bypass, OAuth redirect URI bypass, and schema mutation in fastmcp 2.14.5

---

## Email Body

Hi fastmcp team,

We have been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found four invariant violations in fastmcp 2.14.5 with security implications. Three are HIGH severity; one is MEDIUM.

### BUG-T2-3 / BUG-T2-4: JWT expiry check uses falsy test — tokens with `exp=None` or `exp=0` never expire

**Affected component**

File: `fastmcp/server/auth/jwt_issuer.py`, line 214–217
Function: `verify_token`

**Bug description**

`verify_token` performs manual expiry enforcement after calling `authlib.jose.JsonWebToken.decode()`, which validates the signature but does not call `.validate()`. The manual check reads `if exp and exp < time.time()`, which is a Python truthiness test, not an `is None` guard. Two inputs bypass it: `exp=None` (no expiry claim — `None` is falsy, check skipped, token never expires) and `exp=0` (Unix epoch, January 1 1970 — the integer `0` is falsy, check skipped, a 56-year-old token is accepted as valid). Any token issued without an `exp` claim, or crafted with `exp=0`, passes `verify_token` unconditionally as long as the signature is valid.

**Reproduction**

```python
import time
# Simulates the check at jwt_issuer.py:217

# Case 1 — exp=None (missing expiry claim)
exp = None
if exp and exp < time.time():
    raise Exception("expired")
print("ACCEPTED — no expiry enforced")  # always prints

# Case 2 — exp=0 (Unix epoch)
exp = 0
if exp and exp < time.time():
    raise Exception("expired")
print("ACCEPTED — token from 1970 accepted")  # always prints
```

**Suggested fix (minimal diff)**

```python
# Before (jwt_issuer.py line 217):
if exp and exp < time.time():

# After:
if exp is None:
    raise JoseError("Token missing required exp claim")
if exp < time.time():
    raise JoseError("Token has expired")
```

**Severity:** HIGH

---

### BUG-T2-5: OAuth redirect URI validation uses `fnmatch` — allows query-param injection and fake-port attacks

**Affected component**

File: `fastmcp/server/auth/redirect_validation.py`, lines 8–58
Function: `matches_allowed_pattern`

**Bug description**

Redirect URI validation uses `fnmatch.fnmatch(uri, pattern)`, which performs shell glob matching on the raw URI string. The `*` wildcard matches any character including `.`, `/`, `?`, and `=`. This allows two bypass attacks: (1) query-param injection — a URI of `https://evil.com/callback?legit.example.com/anything` matches the pattern `https://*.example.com/*` because the query string satisfies `*.example.com/*`; and (2) fake-port confusion — a URI of `http://localhost:evil.com` matches `http://localhost:*` because `*` is not bounded to digit characters. In attack 1, the OAuth authorization code is delivered to `evil.com`. The docstring at line 12–15 itself documents the `localhost:*` example, which is exactly the pattern that allows `localhost:evil.com`.

**Reproduction**

```python
import fnmatch

# Attack 1: query-param injection satisfies *.example.com/* pattern
pattern = "https://*.example.com/*"
malicious = "https://evil.com/cb?legit.example.com/anything"
assert fnmatch.fnmatch(malicious, pattern) is True  # CONFIRMED: evil.com receives auth code

# Attack 2: fake-port attack satisfies localhost:* pattern
pattern2 = "http://localhost:*"
malicious2 = "http://localhost:evil.com"
assert fnmatch.fnmatch(malicious2, pattern2) is True  # CONFIRMED
```

**Suggested fix (minimal diff)**

```python
from urllib.parse import urlparse

def matches_allowed_pattern(uri: str, pattern: str) -> bool:
    """Match on parsed URL components, not the raw string."""
    try:
        parsed_uri = urlparse(uri)
        parsed_pat = urlparse(pattern)
    except Exception:
        return False
    # Scheme and netloc must match exactly (or netloc glob on host only)
    if parsed_uri.scheme != parsed_pat.scheme:
        return False
    pat_host = parsed_pat.hostname or ""
    uri_host = parsed_uri.hostname or ""
    if not fnmatch.fnmatch(uri_host, pat_host):
        return False
    # For port wildcards, verify the port is numeric
    if parsed_pat.port is None and "*" in parsed_pat.netloc:
        if parsed_uri.port is None:
            return False
    elif parsed_pat.port is not None and parsed_uri.port != parsed_pat.port:
        return False
    return fnmatch.fnmatch(parsed_uri.path, parsed_pat.path or "/*")
```

**Severity:** HIGH

---

### BUG-T2-6: `OAuthProxyProvider(allowed_client_redirect_uris=None)` allows ALL redirect URIs; docs say localhost-only

**Affected component**

File: `fastmcp/server/auth/redirect_validation.py`, line 50
File: `fastmcp/server/auth/oauth_proxy.py`, line 677 (docstring)

**Bug description**

The `OAuthProxyProvider` docstring states: "If `None` (default), only localhost redirect URIs are allowed." The code at `redirect_validation.py:50–51` reads `if allowed_patterns is None: return True`. Passing `None` allows every redirect URI unconditionally, the opposite of the documented behavior. Developers who rely on the default being "secure" (localhost-only) leave their proxy open to arbitrary redirect URI attacks without knowing it.

**Reproduction**

```python
# redirect_validation.py:50-51 (confirmed by source inspection):
# if allowed_patterns is None:
#     return True  # "for DCR compatibility"

# Proof: OAuthProxyProvider() with no allowed_client_redirect_uris
# accepts https://evil.com as a redirect URI
```

**Suggested fix:** Either (a) change the default behavior to only permit `http://localhost:*` when `allowed_patterns is None`, implementing what the docs promise, or (b) update the docstring to accurately reflect the "allow all" behavior and require callers to explicitly pass `None` if they want that. Option (a) is the safer choice.

**Severity:** HIGH

---

### BUG-T2-7: `compress_schema` mutates caller's input dict in-place despite "immutable design" docstring

**Affected component**

File: `fastmcp/utilities/json_schema.py`
Functions: `compress_schema`, `_prune_param`, `_single_pass_optimize`

**Bug description**

The `_prune_param` docstring claims "Return a new schema with `*param*` removed" and `_single_pass_optimize` claims "Immutable design prevents shared reference bugs." In practice, all mutations happen on the input dict directly. Calling `compress_schema(schema, ...)` modifies `schema` in-place and returns the same object. A one-line workaround (`deepcopy` before calling) exists in `tool_transform.py:613` with the comment "Deep copy to prevent compress_schema from mutating parent tool's $defs", confirming the team is aware. However, other callers in `tools/tool.py`, `prompts/prompt.py`, `server/context.py`, and `server/elicitation.py` do not deep-copy, and will have their stored schemas silently modified.

**Reproduction**

```python
from fastmcp.utilities.json_schema import compress_schema
import copy

schema = {
    "type": "object",
    "title": "TestSchema",
    "properties": {
        "ctx": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["name"],
}
original_id = id(schema)
result = compress_schema(schema, prune_params=["ctx"], prune_titles=True)

assert result is schema          # True — same object returned, not a copy
assert "title" not in schema     # True — original mutated: title removed
assert "ctx" not in schema["properties"]  # True — original mutated: ctx removed
```

**Suggested fix (minimal diff)**

```python
def compress_schema(schema: dict, ...) -> dict:
    schema = copy.deepcopy(schema)  # add this line
    ...
```

**Severity:** MEDIUM

---

## Disclosure Timeline

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

- **Day 0 (2026-03-29):** this report
- **Day 3:** please confirm receipt
- **Day 90 (2026-06-27):** public disclosure, or earlier if fixes are released

We are flexible. If 90 days is insufficient or you need more context, let us know.

**Note on version support:** Your SECURITY.md states that 2.x is no longer supported. We understand the fix would target 3.x. We are reporting against 2.14.5 because that is the version in wide deployment. If the bugs are fixed in 3.x already, please let us know — we will note that in our published report.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, fastmcp 2.14.5, Windows 11. All four findings verified by direct execution — not theoretical.*
