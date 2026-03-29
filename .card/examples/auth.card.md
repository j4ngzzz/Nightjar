---
card-version: "1.0"
id: auth-example
title: Authentication Module — Example Spec
status: active
module:
  owns: [login(), logout(), create_session(), validate_token(), lock_account()]
  depends-on: {}
  excludes:
    - "OAuth2 / OIDC flows"
    - "Multi-factor authentication"
contract:
  inputs:
    - name: username
      type: string
      constraints: "len(username) >= 1"
    - name: password
      type: string
      constraints: "len(password) >= 8"
    - name: token
      type: string
      constraints: "len(token) > 0"
    - name: session_id
      type: string
      constraints: "len(session_id) > 0"
  outputs:
    - name: LoginResult
      type: object
      schema:
        session_id: string
        token: string
        expires_at: float
        user_id: string
  errors:
    - InvalidCredentialsError
    - AccountLockedError
    - WeakPasswordError
    - TokenExpiredError
    - SessionNotFoundError
invariants:
  - id: AUTH-INV-001
    tier: property
    statement: "password must be at least 8 characters — len(password) >= 8"
    rationale: "Passwords shorter than 8 characters are rejected at login time. Matching the fastmcp bug pattern: checking len >= 8 rather than > 7 is correct, but LLMs frequently generate len > 7 or len >= 7 (off-by-one)."
  - id: AUTH-INV-002
    tier: formal
    statement: "token expiry is always in the future — expires_at > time.time() at creation"
    rationale: "This is the fastmcp JWT bug: `if exp and exp < time.time()` treats exp=0 and exp=None as valid. The correct check is `if exp is None or exp < time.time()`. Tokens with expiry 0 (epoch 1970) must be rejected."
  - id: AUTH-INV-003
    tier: property
    statement: "failed_login_count is always non-negative — failed_login_count >= 0"
    rationale: "Decrementing a counter that is already 0 produces a negative count, which can bypass the lockout threshold check."
  - id: AUTH-INV-004
    tier: formal
    statement: "account locks after exactly 5 consecutive failed login attempts"
    rationale: "The lockout threshold must be enforced precisely. 4 attempts must succeed; the 5th must trigger the lock. Off-by-one errors here are a brute-force vulnerability."
  - id: AUTH-INV-005
    tier: property
    statement: "session_id is a non-empty unique string — len(session_id) > 0"
    rationale: "An empty string session ID would be shared across all sessions with empty IDs, granting any session holder access to all such accounts."
  - id: AUTH-INV-006
    tier: property
    statement: "login() raises AccountLockedError when failed_login_count >= 5"
    rationale: "The lockout must fire on the attempt that reaches 5, not after it. The counter increment and the lockout check must be atomic."
  - id: AUTH-INV-007
    tier: property
    statement: "validate_token() raises TokenExpiredError when expires_at <= time.time()"
    rationale: "Expired tokens must be rejected on validation, not just at creation. A token valid at issue time may expire before use."
  - id: AUTH-INV-008
    tier: formal
    statement: "login() raises WeakPasswordError when len(password) < 8, before any credential check"
    rationale: "Password length validation must occur before the database lookup. Otherwise, a 1-character password attempt reveals whether the username exists (timing oracle)."
---

## Intent

Authenticate users securely. Issue session tokens with bounded expiry.
Enforce lockout after repeated failures. Reject weak passwords at the entry
point before any credential verification.

This spec is an example for Nightjar tutorials. It demonstrates authentication
invariants that are frequently violated by LLM-generated code: the JWT expiry
falsy-check bug (found in fastmcp 2.14.5), the lockout off-by-one, and the
password-before-lookup ordering requirement.

## Acceptance Criteria

### Story 1 — Login (P1)

**As a** registered user, **I want** to log in, **so that** I can access my account.

1. **Given** valid credentials, **When** login() is called, **Then** a LoginResult with a non-empty session_id and expires_at > now is returned
2. **Given** password="short" (7 chars), **When** login() is called, **Then** WeakPasswordError is raised before any DB lookup
3. **Given** 4 failed attempts then valid credentials, **When** login() is called for the 5th time with valid credentials, **Then** login succeeds (lockout activates on the 5th *failed* attempt, not the 5th attempt)
4. **Given** 5 consecutive failed attempts, **When** login() is called again, **Then** AccountLockedError is raised regardless of password correctness

### Story 2 — Token Validation (P2)

**As a** protected API endpoint, **I want** to validate the session token, **so that** only authenticated users access the resource.

1. **Given** a valid unexpired token, **When** validate_token() is called, **Then** the user_id is returned
2. **Given** a token with expires_at=0 (epoch 1970), **When** validate_token() is called, **Then** TokenExpiredError is raised
3. **Given** a token with expires_at=None, **When** validate_token() is called, **Then** TokenExpiredError is raised
4. **Given** an empty string token, **When** validate_token() is called, **Then** TokenExpiredError or SessionNotFoundError is raised

### Edge Cases

- What if password has exactly 8 characters? → Valid, no WeakPasswordError
- What if password has 7 characters? → WeakPasswordError raised
- What if failed_login_count is already at 5 and decremented by a bug? → Must remain >= 0
- What if session_id is " " (single space)? → len > 0, but effectively unusable — spec does not prohibit this, but real implementation should trim

## Functional Requirements

- **FR-AUTH-001**: System MUST validate len(password) >= 8 before any credential check
- **FR-AUTH-002**: System MUST generate session_id with sufficient entropy (>= 128 bits)
- **FR-AUTH-003**: System MUST set expires_at to a Unix timestamp strictly greater than time.time() at creation
- **FR-AUTH-004**: System MUST increment failed_login_count atomically with the login check
- **FR-AUTH-005**: System MUST reject token validation when expires_at is None, 0, or any value <= time.time()
- **FR-AUTH-006**: System MUST lock account and return AccountLockedError when failed_login_count reaches 5
