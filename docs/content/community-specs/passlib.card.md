---
card-version: "1.0"
id: passlib
title: passlib Password Hashing — Community Spec
status: active
module:
  owns:
    - hash_password()
    - verify_password()
    - needs_rehash()
    - build_context()
  depends-on:
    passlib: ">=1.7.4"
    bcrypt: ">=4.0.0"
  excludes:
    - "Password strength estimation (use zxcvbn)"
    - "Password reset token generation (use secrets)"
    - "argon2-cffi direct usage — route through passlib CryptContext only"
contract:
  inputs:
    - name: password
      type: string
      constraints: "len(password) >= 1 AND len(password.encode('utf-8')) <= 72 when scheme is bcrypt"
    - name: password_hash
      type: string
      constraints: "len(password_hash) > 0 AND password_hash.startswith(('$2b$', '$argon2', '$pbkdf2-sha256$'))"
    - name: rounds
      type: integer
      constraints: "rounds >= 600000 when scheme is pbkdf2_sha256 OR rounds >= 12 when scheme is bcrypt"
    - name: scheme
      type: string
      constraints: "scheme IN ('argon2', 'bcrypt', 'pbkdf2_sha256') — deprecated schemes forbidden"
  outputs:
    - name: HashResult
      type: object
      schema:
        hash: string
        scheme: string
        needs_rehash: bool
  errors:
    - WeakPasswordError
    - PasswordTooLongError
    - DeprecatedSchemeError
    - InvalidHashError
    - TimingLeakError
constraints:
  security: "NIST SP 800-63B and SP 800-132 (2023) compliance required"
  performance: "hash_password() p95 latency < 500ms for bcrypt rounds=12"
  compliance: "bcrypt 72-byte truncation must be handled — reject or pre-hash passwords > 72 bytes"
invariants:
  - id: PASS-INV-001
    tier: property
    statement: "hash_password() raises PasswordTooLongError when len(password.encode('utf-8')) > 72 and scheme is bcrypt — bcrypt silently truncates at 72 bytes"
    rationale: "bcrypt has a hard 72-byte input limit. A password of 73+ bytes is hashed identically to its first 72 bytes. This means 'password123AAAA...73chars' and 'password123AAAA...999chars' verify as equal. Applications that do not guard this boundary silently accept passwords that only match on a 72-byte prefix. The fix is to either reject > 72 bytes or pre-hash with SHA-256 before bcrypt (bcrypt+SHA256 pattern)."
  - id: PASS-INV-002
    tier: property
    statement: "verify_password() execution time is independent of how many leading bytes of the password match the stored hash — constant-time comparison must be used"
    rationale: "A timing oracle attack measures response time across many password guesses. If comparison exits early on the first non-matching character, the attacker can brute-force one character at a time. passlib uses hmac.compare_digest internally, but wrapper code that compares verify() return values via `if result == True` on a boolean is safe. This is a property-tier invariant (not formal) because Dafny and CrossHair do not model execution time — it must be verified empirically via a timing measurement harness that asserts stddev(correct_times) ≈ stddev(wrong_times). Hypothesis can drive the property across many input lengths."
  - id: PASS-INV-003
    tier: property
    statement: "build_context() raises DeprecatedSchemeError when the schemes list contains 'md5_crypt', 'des_crypt', 'sha1_crypt', or 'plaintext'"
    rationale: "CryptContext accepts any scheme name silently. Legacy code frequently includes md5_crypt as a fallback for migrating old hashes. If the deprecated scheme is listed as a non-deprecated entry, new passwords may be hashed with MD5. The correct pattern is to list legacy schemes only in deprecated_schemes=[] for read-only verification during migration."
  - id: PASS-INV-004
    tier: property
    statement: "build_context() raises ValueError when using pbkdf2_sha256 scheme and rounds < 600000"
    rationale: "NIST SP 800-132 (2023) recommends 600,000 iterations for PBKDF2-HMAC-SHA256. The passlib default of 29000 rounds (set in 2013) is 20x below the 2023 recommendation. Code copied from old tutorials silently uses the outdated default. This invariant enforces the current NIST floor at configuration time rather than at runtime."
  - id: PASS-INV-005
    tier: property
    statement: "needs_rehash() returns True for any hash produced with rounds below current scheme minimums (bcrypt < 12, pbkdf2_sha256 < 600000)"
    rationale: "Rehash-on-login is the migration pattern for upgrading password hashes to stronger parameters. If needs_rehash() does not fire for underpowered hashes, users whose passwords were stored with weak parameters are never upgraded, permanently weakening their security posture."
  - id: PASS-INV-006
    tier: formal
    statement: "for all passwords p and q where p != q, hash_password(p) != hash_password(q) — distinct passwords never produce the same hash"
    rationale: "Collision resistance: two different passwords must never verify against each other's hash. This is a formal postcondition provable by the pigeonhole principle over the hash output space. While cryptographic hash collisions are theoretically possible, the invariant formalizes that the implemented verify() function rejects cross-password verification — it does not verify hash collision resistance itself but the application-layer guarantee that verify_password(p, hash_password(q)) returns False when p != q."
  - id: PASS-INV-007
    tier: example
    statement: "hash_password('correct-horse-battery') returns a string starting with '$2b$' when scheme is bcrypt"
    rationale: "Smoke test: bcrypt hashes start with '$2b$' (version 2b). A hash starting with '$2a$' indicates the older, potentially vulnerable version. '$2y$' is PHP-specific. Any other prefix indicates the wrong scheme was selected."
---

## Intent

Wrap passlib's CryptContext with explicit, safe defaults that enforce current
NIST guidance. passlib 1.7.4 (2022) is in maintenance mode — the core library
still works, but bcrypt bindings have been externalized to the bcrypt package
which requires separate pinning.

The two common failure modes in passlib usage: (1) bcrypt 72-byte truncation
goes undetected, silently accepting passwords that share a 72-byte prefix with
the stored hash; (2) round counts from 2015-era documentation are used, which
are 10-20x below current NIST minimums. This spec formalizes both as
verifiable, compiler-checkable invariants.

## Acceptance Criteria

### Story 1 — Hash Password (P1)

**As a** registration service, **I want** to hash a new user's password, **so that** it can be stored securely.

1. **Given** password="correct-horse-battery-staple", scheme=bcrypt, rounds=12, **When** hash_password() is called, **Then** a $2b$12$... hash string is returned
2. **Given** password="a" * 73 (73 'a' characters, 73 bytes UTF-8), scheme=bcrypt, **When** hash_password() is called, **Then** PasswordTooLongError is raised
3. **Given** password="correct-horse", scheme=pbkdf2_sha256, rounds=100, **When** hash_password() is called, **Then** ValueError is raised — rounds < 600000 is rejected at call time
4. **Given** scheme='md5_crypt' in the context's schemes list as a non-deprecated entry, **When** build_context() is called, **Then** DeprecatedSchemeError is raised

### Story 2 — Verify and Rehash (P2)

**As a** login service, **I want** to verify a password and upgrade weak hashes, **so that** users are protected by current security standards.

1. **Given** a hash produced with rounds=1000 (old default), **When** needs_rehash() is called, **Then** True is returned
2. **Given** a hash produced with current rounds, **When** needs_rehash() is called, **Then** False is returned
3. **Given** password="correct", hash=hash_password("correct"), **When** verify_password() is called, **Then** True is returned
4. **Given** password="wrong", hash=hash_password("correct"), **When** verify_password() is called, **Then** False is returned in constant time

### Edge Cases

- What if password is exactly 72 bytes (bcrypt)? → Accepted — 72 is the boundary
- What if password is 73 bytes (bcrypt)? → PasswordTooLongError
- What if password is empty string? → WeakPasswordError (not a bcrypt concern, an app-level guard)
- What if the stored hash is from an unknown scheme? → InvalidHashError

## Functional Requirements

- **FR-PASS-001**: System MUST reject passwords > 72 UTF-8 bytes when bcrypt is the active scheme
- **FR-PASS-002**: System MUST reject CryptContext configuration with rounds < 600000 for pbkdf2_sha256
- **FR-PASS-003**: System MUST reject CryptContext configuration with rounds < 12 for bcrypt
- **FR-PASS-004**: System MUST never list md5_crypt, des_crypt, sha1_crypt, or plaintext as non-deprecated schemes
- **FR-PASS-005**: System MUST call needs_rehash() after every successful verify and re-hash if True
- **FR-PASS-006**: System MUST use bcrypt version 2b (prefix $2b$) — not 2a or 2y
