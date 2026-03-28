# Tier 4/5 Security Package Invariant Scan Results

**Scan date:** 2026-03-28
**Scanner:** Nightjar contract-anchored invariant scanner
**Python version:** 3.14
**Method:** Black-box invariant testing + source code analysis

---

## Methodology

For each package, the scanner tested:
1. Empty/None inputs (crash resistance)
2. Algorithm confusion attacks (alg:none, algorithm switching)
3. Key material validation (empty, short, None keys)
4. Tamper detection (modified payload/signature)
5. Time-based claim enforcement (exp, nbf, max_age)
6. Cross-context confusion (salt, salt-less tokens)
7. Legacy/deprecated scheme acceptance

False positives are explicitly flagged. Behavior-as-designed is noted, not mislabeled as a vulnerability.

---

## Package 1: PyJWT 2.11.0

### FINDING-JWT-1: Weak Key Soft Enforcement (Insecure Default)

**Severity:** MEDIUM
**Function:** `jwt.encode()`, `jwt.decode()`
**Is this a known issue?** Partial — `InsecureKeyLengthWarning` was added in 2.9.0, but enforcement remains opt-in.

**Invariant violated:**
> `encode(payload, key, algorithm)` must reject keys shorter than the algorithm's minimum recommended length (32 bytes for HS256 per RFC 7518 §3.2), not merely warn.

**Counterexample:**
```python
import jwt
# 3-byte key — FAR below the 32-byte minimum for HS256
token = jwt.encode({"sub": "admin", "admin": True}, "abc", algorithm="HS256")
result = jwt.decode(token, "abc", algorithms=["HS256"])
# Returns: {'sub': 'admin', 'admin': True}
# Emits: InsecureKeyLengthWarning (only a warning, not an error)
```

**Root cause (source):**
```python
# jwt/api_jws.py line 156-159
if self.options.get("enforce_minimum_key_length", False):  # Default: False
    raise InvalidKeyError(key_length_msg)
else:
    warnings.warn(key_length_msg, InsecureKeyLengthWarning, stacklevel=2)
```

**Empty string key also accepted by default:**
```python
token = jwt.encode({"sub": "admin"}, "", algorithm="HS256")  # Works, just warns
```

**Impact:** Production code silently uses dangerously weak keys if warnings are suppressed (e.g., `warnings.filterwarnings('ignore')`). The invariant `key length >= 32 bytes for HS256` is only enforced via opt-in `enforce_minimum_key_length=True`.

**Mitigation:**
```python
from jwt import PyJWT
secure = PyJWT(options={"enforce_minimum_key_length": True})
token = secure.encode(payload, key, algorithm="HS256")
```

**Novel or known?** The _option_ was added in 2.9.0 and documented. The insecure-by-default status is a deliberate backwards-compatibility decision. This finding documents that the default remains dangerous.

**Responsible disclosure:** Not applicable — this is documented behavior, not a hidden vulnerability. File a usability issue at https://github.com/jpadilla/pyjwt/issues

---

### FINDING-JWT-2: options={'verify_signature': False} Bypass (Informational)

**Severity:** LOW (by design)
**Function:** `jwt.decode()`

**Invariant tested:**
> `decode(token, key)` must always verify the signature.

**Result:** `jwt.decode(token, options={"verify_signature": False})` accepts any token without a key. This is documented behavior for use in middleware that needs to inspect claims before verification. It is not a bug, but it is a foot-gun.

**Counterexample:**
```python
result = jwt.decode(none_alg_token, options={"verify_signature": False})
# Returns: {'sub': 'admin', 'admin': True}  — no key, no sig check
```

**Verdict:** Design decision. Applications must never expose this option to user-controlled inputs.

---

### Invariants That Hold in PyJWT 2.11.0

| Invariant | Result |
|-----------|--------|
| Must reject empty token string | PASS |
| Must reject alg:none token | PASS |
| Must reject expired token (exp claim) | PASS |
| Must reject tampered payload | PASS |
| Must not leak secret key in token | PASS |
| Must reject None/integer/list inputs | PASS |
| Must reject missing aud when audience required | PASS |
| Must reject future token (nbf claim) | PASS |

---

## Package 2: python-jose 3.5.0

### FINDING-JOSE-1: algorithms=None Bypasses Algorithm Allowlist

**Severity:** HIGH
**Function:** `jose.jwt.decode()`
**Is this a known issue?** YES — this is part of the behavior that led to CVE-2024-33663 / CVE-2024-33664. python-jose 3.5.0 is the _latest release_ and still exhibits this behavior.

**Invariant violated:**
> `decode(token, key, algorithms=None)` must require an explicit algorithm list. Passing `algorithms=None` must not bypass the algorithm check.

**Counterexample:**
```python
from jose import jwt
token = jwt.encode({"sub": "admin", "admin": True}, "secret", algorithm="HS256")
result = jwt.decode(token, "secret", algorithms=None)
# Returns: {'sub': 'admin', 'admin': True}
# The algorithm allowlist check is SKIPPED
```

**Root cause (source — jose/jws.py line 257):**
```python
def _verify_signature(signing_input, header, signature, key="", algorithms=None):
    alg = header.get("alg")
    if not alg:
        raise JWSError("No algorithm was specified in the JWS header.")

    if algorithms is not None and alg not in algorithms:  # <-- None skips this check
        raise JWSError("The specified alg value is not allowed")
    # Signature IS still verified, but with WHATEVER algorithm the token header claims
```

**Impact:** Any application passing `algorithms=None` (or omitting the parameter, since `None` is the default!) accepts tokens signed with any algorithm. An attacker who can sign tokens with an unintended algorithm (e.g., if the application uses RS256 for outbound tokens but accepts HS256 inbound) can forge tokens.

**Concrete scenario:**
1. Application issues RS256 tokens (asymmetric, private key kept server-side)
2. Attacker knows the RS256 public key (it's public by definition)
3. Attacker signs an HS256 token using the public key as the HMAC secret
4. Server calls `jose_jwt.decode(token, public_key)` without specifying `algorithms`
5. With `algorithms=None`, the HS256 algorithm is not blocked — verification succeeds

**Verification:**
```python
# Confirmed: algorithms=None accepts token regardless of algorithm in header
jose_jwt.decode(valid_hs256_token, SECRET, algorithms=None)
# -> {'sub': 'admin', 'admin': True}  -- NO algorithm restriction enforced

# Contrast with algorithms=[] which correctly rejects:
jose_jwt.decode(valid_hs256_token, SECRET, algorithms=[])
# -> JWTError: The specified alg value is not allowed
```

**Mitigation:** Always pass an explicit algorithms list. Never pass `algorithms=None`.

**Responsible disclosure:** This behavior is tracked in the python-jose GitHub issues. The project appears semi-maintained; the last commit was in 2024. File at https://github.com/mpdavis/python-jose/issues. CVE references: CVE-2024-33663, CVE-2024-33664 (python-jose 3.3.0+).

---

### FINDING-JOSE-2: Empty String Secret Key Accepted

**Severity:** MEDIUM
**Function:** `jose.jwt.encode()`, `jose.jwt.decode()`
**Is this a known issue?** Similar to PyJWT but with no warning emitted.

**Invariant violated:**
> `encode(claims, key, algorithm)` must reject an empty string as a cryptographic key.

**Counterexample:**
```python
from jose import jwt
token = jwt.encode({"sub": "admin"}, "", algorithm="HS256")
result = jwt.decode(token, "", algorithms=["HS256"])
# Returns: {"sub": "admin"} — no warning, no error
```

**Impact:** Worse than PyJWT (which at least warns). python-jose silently accepts empty keys.

---

### FINDING-JOSE-3: None Passed to decode() Raises AttributeError, Not Structured Error

**Severity:** LOW
**Function:** `jose.jwt.decode()`

**Counterexample:**
```python
jose_jwt.decode(None, "secret", algorithms=["HS256"])
# Raises: AttributeError (not JWTError/JWSError)
# Calling code expecting JWTError will miss the None case
```

**Impact:** Applications catching `JWTError` to handle malformed tokens will NOT catch this case and may expose an unhandled `AttributeError` exception.

---

### Invariants That Hold in python-jose 3.5.0

| Invariant | Result |
|-----------|--------|
| Must reject alg:none token (when algorithms specified) | PASS |
| Must reject alg:None / alg:NONE variants (when algorithms specified) | PASS |
| Must reject tampered payload | PASS |
| Must reject expired token | PASS |
| Must reject None key | PASS |
| Must reject empty algorithms list | PASS |

---

## Package 3: passlib 1.7.4

### FINDING-PASS-1: Incompatible with bcrypt 4.x/5.x — Silent Failure Risk

**Severity:** HIGH (operational / supply chain)
**Functions:** `CryptContext.hash()`, `CryptContext.verify()` with bcrypt scheme
**Is this a known issue?** YES — tracked in passlib's GitHub issues since 2023. passlib is effectively abandoned (last release: September 2020, Python 3.14 incompatibilities accumulating).

**Invariant violated:**
> A password hashing library must be able to hash and verify passwords using its advertised schemes without raising internal errors.

**Counterexample:**
```python
from passlib.context import CryptContext
ctx = CryptContext(schemes=["bcrypt"])
ctx.hash("password")
# Raises: MissingBackendError / AttributeError: module 'bcrypt' has no attribute '__about__'
# Root cause: passlib reads bcrypt.__about__.__version__, removed in bcrypt 4.x
```

**Root cause (passlib/handlers/bcrypt.py line 620):**
```python
version = _bcrypt.__about__.__version__  # AttributeError: bcrypt 4.x/5.x removed __about__
```

**Impact:** Any production application using `passlib[bcrypt]` on a system with `bcrypt>=4.0.0` will fail to hash or verify passwords. This is a complete denial-of-service for authentication.

**Mitigation options:**
1. Pin `bcrypt<4.0.0` (insecure — older bcrypt has its own issues)
2. Switch from passlib to `bcrypt` directly, or to `argon2-cffi`, or `django.contrib.auth.hashers`
3. Use a maintained fork: `passlib2` or switch to `pwdlib`

---

### FINDING-PASS-2: Empty Password Accepted Without Enforcement

**Severity:** MEDIUM
**Function:** `pbkdf2_sha256.hash()`, `pbkdf2_sha256.verify()`

**Invariant tested:**
> `hash("")` must reject empty passwords (or at minimum, `verify("", hash_of_empty))` must return False for any non-empty input.

**Counterexample:**
```python
from passlib.hash import pbkdf2_sha256
h = pbkdf2_sha256.hash("")
pbkdf2_sha256.verify("", h)       # Returns: True
pbkdf2_sha256.verify("other", h)  # Returns: False (correct)
```

**Verdict:** passlib correctly distinguishes empty from non-empty passwords. The issue is that passlib places no restriction on empty passwords — this is a policy decision the application must enforce. passlib provides no `min_length` parameter.

**Impact:** Applications that forget to validate password length before hashing can accept empty passwords as valid credentials.

---

### FINDING-PASS-3: sha256_crypt Rejects Null Bytes; pbkdf2_sha256 Does Not

**Severity:** LOW (inconsistency)
**Functions:** `sha256_crypt.hash()` vs `pbkdf2_sha256.hash()`

**Counterexample:**
```python
from passlib.hash import pbkdf2_sha256, sha256_crypt

# pbkdf2_sha256: handles null bytes transparently
h = pbkdf2_sha256.hash("pass\x00word")
pbkdf2_sha256.verify("pass\x00word", h)  # True
pbkdf2_sha256.verify("pass", h)          # False — no truncation, correct

# sha256_crypt: raises PasswordValueError
sha256_crypt.hash("pass\x00word")
# Raises: PasswordValueError: sha256_crypt does not allow NULL bytes in password
```

**Impact:** Inconsistent null-byte handling across passlib schemes. If an application switches from sha256_crypt to pbkdf2_sha256, null-byte passwords that previously raised errors will silently start working. This is an inconsistency, not a direct vulnerability, but can cause confusion during migrations.

---

### Invariants That Hold in passlib 1.7.4

| Invariant | Result |
|-----------|--------|
| Must not verify wrong password | PASS |
| Must reject None as password | PASS |
| Must signal deprecated schemes via needs_update() | PASS |
| pbkdf2_sha256: no null-byte truncation | PASS |

---

## Package 4: itsdangerous 2.2.0

### FINDING-ISD-1: max_age=0 Does Not Expire Token Immediately

**Severity:** LOW
**Function:** `URLSafeTimedSerializer.loads(token, max_age=0)`

**Invariant violated:**
> `loads(token, max_age=0)` should either raise `SignatureExpired` immediately (token older than 0 seconds is expired) or document that 0 means "no expiry".

**Counterexample:**
```python
from itsdangerous import URLSafeTimedSerializer
ts = URLSafeTimedSerializer("secret")
token = ts.dumps({"user": "test"})
result = ts.loads(token, max_age=0)
# Returns: {"user": "test"}  — token is NOT expired with max_age=0
```

**Root cause:** The comparison is `age > max_age`, not `age >= max_age`. A token signed "just now" has age ~0, which is not `> 0`. The behavior is technically correct mathematically but violates the intuition that `max_age=0` means "never valid."

**Impact:** Code that uses `max_age=0` expecting it to disable acceptance of any token will behave unexpectedly. A one-time token scheme where the developer uses `max_age=0` as "disabled" would be broken.

**Mitigation:** Do not use `max_age=0`. Use `max_age=1` for near-immediate expiry, or document explicitly that `max_age=0` is a no-op expiry.

---

### FINDING-ISD-2: Empty String as Secret Key Accepted

**Severity:** MEDIUM
**Function:** `URLSafeSerializer("")`, `URLSafeTimedSerializer("")`

**Invariant violated:**
> Constructor must reject empty string as secret key.

**Counterexample:**
```python
from itsdangerous import URLSafeSerializer
s = URLSafeSerializer("")
token = s.dumps({"user": "admin"})  # Works
result = s.loads(token)             # Works: {"user": "admin"}
```

**Impact:** Applications that inadvertently pass an empty string (e.g., from an unset environment variable `os.environ.get("SECRET_KEY", "")`) will create tokens with no cryptographic protection, since the HMAC key is empty.

---

### FINDING-ISD-3: Shared Token Space When No Salt Specified

**Severity:** LOW (by design, but underdocumented)
**Function:** `URLSafeSerializer(secret)` without salt

**Invariant tested:**
> Tokens created for different purposes (e.g., session tokens vs. password reset links) must not be cross-usable.

**Result:**
```python
s1 = URLSafeSerializer("mysecret")   # No salt
s2 = URLSafeSerializer("mysecret")   # No salt, same secret
token = s1.dumps({"user": "admin"})
s2.loads(token)  # Returns: {"user": "admin"} — cross-context works
```

**With salt (correct usage):**
```python
s1 = URLSafeSerializer("secret", salt="user-session")
s2 = URLSafeSerializer("secret", salt="password-reset")
token = s1.dumps({"user": "admin"})
s2.loads(token)  # Raises: BadSignature — correct, salt prevents confusion
```

**Impact:** Applications not using the `salt` parameter expose all token types to cross-context use. A password-reset token could be used as a session token.

---

### Invariants That Hold in itsdangerous 2.2.0

| Invariant | Result |
|-----------|--------|
| Must reject tampered token | PASS |
| Must reject expired token (max_age > 0) | PASS |
| Must reject None as secret key | PASS (TypeError) |
| Must reject None input to loads() | PASS |
| Salt differentiation prevents cross-context use | PASS |

---

## Package 5: authlib 1.6.9

### FINDING-AUTH-1: Short/Empty OctKey Accepted Without Enforcement

**Severity:** MEDIUM
**Function:** `OctKey.import_key()`, `jwt.encode()`, `jwt.decode()`
**Is this a known issue?** Not publicly documented as a specific issue.

**Invariant violated:**
> `OctKey.import_key(key_bytes)` must reject keys shorter than 32 bytes for use with HS256.

**Counterexample:**
```python
from authlib.jose import jwt, OctKey

# 5-byte key
short_key = OctKey.import_key(b"short")
token = jwt.encode({"alg": "HS256"}, {"sub": "admin"}, short_key)
claims = jwt.decode(token, short_key)
claims.validate()
# Returns: {"sub": "admin"} — no error, no warning

# Empty key
empty_key = OctKey.import_key(b"")
token = jwt.encode({"alg": "HS256"}, {"sub": "admin"}, empty_key)
# Also accepted
```

**Impact:** Same impact as PyJWT's insecure default: production code with weak keys silently produces "signed" tokens with negligible security.

---

### FINDING-AUTH-2: validate() Does Not Check iss/aud by Default

**Severity:** MEDIUM (by design)
**Function:** `JWTClaims.validate()`

**Invariant tested:**
> `validate()` must verify that the `iss` (issuer) and `aud` (audience) claims match expected values.

**Result:**
```python
from authlib.jose import jwt, OctKey
key = OctKey.import_key(b"a" * 32)
token = jwt.encode({"alg": "HS256"}, {
    "sub": "user",
    "iss": "attacker.com",     # Wrong issuer
    "aud": "not-my-service",   # Wrong audience
    "exp": time.time() + 3600
}, key)
claims = jwt.decode(token, key)
claims.validate()   # No error raised
```

**Root cause:** authlib requires explicit options dict to validate iss/aud:
```python
claims.validate(now=time.time(), leeway=0)  # Still doesn't check iss/aud
# Must use: claims.validate_iss({"iss": "expected.issuer"})
# Or: use authlib's ResourceProtector with configured issuer
```

**Impact:** Applications that call `claims.validate()` expecting full JWT validation are not checking issuer or audience. Tokens from any issuer or for any audience will pass validation.

**Mitigation:**
```python
claims.validate_iss({"iss": "expected.issuer.com"})
claims.validate_aud({"aud": "my-service"})
```

---

### Invariants That Hold in authlib 1.6.9

| Invariant | Result |
|-----------|--------|
| Must reject alg:none token | PASS |
| Must reject tampered payload | PASS |
| Must reject expired token | PASS |
| Must reject empty/malformed token strings | PASS |
| Must reject None input (AttributeError — not structured) | SEMI-PASS |

---

## Summary Table

| Package | Version | Finding | Severity | Novel? |
|---------|---------|---------|----------|--------|
| PyJWT | 2.11.0 | Weak key soft enforcement (warns, not rejects by default) | MEDIUM | No — opt-in enforcement added in 2.9.0 |
| PyJWT | 2.11.0 | Empty string secret accepted by default | MEDIUM | No |
| python-jose | 3.5.0 | `algorithms=None` bypasses algorithm allowlist | HIGH | No — related to CVE-2024-33663/33664; still present in 3.5.0 |
| python-jose | 3.5.0 | Empty string secret silently accepted (no warning) | MEDIUM | No |
| python-jose | 3.5.0 | `None` token input raises AttributeError not JWTError | LOW | No |
| passlib | 1.7.4 | Incompatible with bcrypt 4.x/5.x — auth DoS risk | HIGH | No — tracked issue, project abandoned |
| passlib | 1.7.4 | Empty password accepted (no min-length enforcement) | MEDIUM | No — by design, must enforce in application |
| passlib | 1.7.4 | Inconsistent null-byte handling across schemes | LOW | No |
| itsdangerous | 2.2.0 | `max_age=0` does not expire token immediately | LOW | No |
| itsdangerous | 2.2.0 | Empty string secret key accepted | MEDIUM | No |
| itsdangerous | 2.2.0 | Shared token space without salt | LOW | By design, underdocumented |
| authlib | 1.6.9 | Short/empty OctKey accepted without warning | MEDIUM | No |
| authlib | 1.6.9 | `validate()` skips iss/aud by default | MEDIUM | By design, underdocumented |

---

## Critical Findings (Actionable)

**Highest priority for operator attention:**

1. **python-jose `algorithms=None`** — The default API call pattern `jose.jwt.decode(token, key)` omits `algorithms`, defaulting to `None`, which silently disables the algorithm allowlist. Any caller using this pattern is vulnerable to algorithm confusion attacks. Since python-jose appears semi-abandoned and the CVEs are 18+ months old with no patch, **migration to PyJWT or authlib is strongly recommended.**

2. **passlib bcrypt incompatibility** — passlib 1.7.4 will break authentication in any app that upgrades bcrypt to 4.x or 5.x. The project is effectively abandoned. **Migrate to a maintained password hashing library.**

3. **Empty string keys (all packages)** — PyJWT, python-jose, itsdangerous, and authlib all accept empty string secret keys. This is a foot-gun for apps that read secrets from environment variables without validation. **Add `assert SECRET_KEY, "SECRET_KEY must not be empty"` before any cryptographic operation.**

---

## False Positives Explicitly Excluded

The following were tested and found to be non-issues:

- PyJWT `alg:none` attack — correctly rejected in 2.11.0
- PyJWT tampered payload — correctly rejected
- itsdangerous tampered token — correctly rejected
- authlib alg:none — correctly rejected
- authlib tampered payload — correctly rejected
- passlib wrong password verification — correctly returns False
- All packages: well-formed tokens with valid credentials — correctly accepted

---

## Responsible Disclosure Contacts

| Package | Contact | Status |
|---------|---------|--------|
| PyJWT | https://github.com/jpadilla/pyjwt/security | Active project, report via GitHub Security tab |
| python-jose | https://github.com/mpdavis/python-jose/issues | Semi-maintained, no private security channel visible |
| passlib | https://foss.heptapod.net/python-libs/passlib | Effectively abandoned; no active maintainer |
| itsdangerous | https://github.com/pallets/itsdangerous/security | Active project (Pallets), security@palletsprojects.com |
| authlib | https://github.com/lepture/authlib/security | Active project, report via GitHub Security tab |

---

*Scan performed with black-box invariant testing. No exploitation was attempted beyond local proof-of-concept. All findings were verified to reproduce before inclusion. Confidence level: HIGH for all MEDIUM/HIGH findings (reproduced with exact counterexamples); LOW findings are accurately characterized as edge cases or design decisions.*
