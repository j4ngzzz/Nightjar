---
card-version: "1.0"
id: python-jose
title: python-jose JWT Wrapper — Community Spec
status: active
module:
  owns:
    - create_jwt()
    - validate_jwt()
    - decode_claims()
  depends-on:
    python-jose: ">=3.3.0"
  excludes:
    - "JWE (JSON Web Encryption) — use joserfc for JWE support"
    - "JWK key management endpoints"
    - "OAuth2 token introspection"
contract:
  inputs:
    - name: token
      type: string
      constraints: "len(token) > 0 AND token contains exactly 2 dots (3 segments)"
    - name: secret
      type: string
      constraints: "len(secret) >= 32"
    - name: algorithms
      type: list
      constraints: "len(algorithms) >= 1 AND 'none' NOT IN algorithms"
    - name: claims
      type: object
      constraints: "claims.get('sub') is not None AND len(str(claims['sub'])) > 0"
  outputs:
    - name: JWTPayload
      type: object
      schema:
        sub: string
        exp: float
        iat: float
        nbf: float
  errors:
    - JWTExpiredError
    - JWTInvalidSignatureError
    - JWTAlgorithmError
    - JWTDecodeError
    - JWTNbfError
constraints:
  security: "MUST NOT accept alg=none tokens under any configuration"
  migration: "python-jose is nearly abandoned as of 2024. Consider migrating to joserfc (authlib) or PyJWT for new projects. See github.com/fastapi/fastapi/discussions/9587."
  compliance: "NIST SP 800-63B token expiry requirements"
invariants:
  - id: JOSE-INV-001
    tier: formal
    statement: "validate_jwt() raises JWTExpiredError when exp claim equals 0 — exp=0 (Unix epoch 1970) must not be treated as absent or valid"
    rationale: "The canonical python-jose wrapper bug: `if exp and exp < time.time()` uses Python's falsy check, which treats exp=0 as equivalent to 'no expiry set'. A token with exp=0 would be permanently valid. The correct check is `if exp is None or exp < time.time()`. This exact pattern was independently rediscovered in fastmcp 2.14.5, multiple FastAPI tutorials, and Auth0 blog examples."
  - id: JOSE-INV-002
    tier: formal
    statement: "validate_jwt() raises JWTAlgorithmError when the token header declares alg='none', regardless of the algorithms parameter"
    rationale: "The alg=none attack: an attacker strips the signature and sets alg=none in the JWT header. python-jose rejects this only if 'none' is absent from the algorithms list, but wrapper code that passes algorithms=None or algorithms=['none'] silently accepts unsigned tokens. The algorithms parameter must be validated before calling jose.jwt.decode()."
  - id: JOSE-INV-003
    tier: property
    statement: "validate_jwt() raises JWTAlgorithmError when the token was signed with an RSA public key used as an HMAC-SHA256 secret — calling decode(token, rsa_public_key_bytes, algorithms=['HS256']) must not accept a token that an attacker signed with those same public key bytes"
    rationale: "Algorithm confusion (CVE-2016-5431 class): an attacker obtains the server's RSA public key (often public by design). They sign a forged token using HS256 with the public key bytes as the HMAC secret. A server that accepts algorithms=['HS256', 'RS256'] together without key-type binding will verify this token successfully. The defense is to never mix asymmetric and symmetric algorithms in the same algorithms list, and to validate that the key type matches the algorithm before calling jose.jwt.decode(). Note: jose.jwt.decode() with a strict algorithms=['HS256'] list will actually reject a token with alg='RS256' in the header (different, simpler case). The dangerous scenario is algorithms=['HS256'] + RSA public key bytes as secret, where jose may verify the HMAC signature using those bytes."
  - id: JOSE-INV-004
    tier: property
    statement: "validate_jwt() raises JWTNbfError when current Unix time is less than the nbf (not-before) claim value"
    rationale: "Tokens issued for future use (e.g., scheduled tasks, pre-issued refresh tokens) carry an nbf claim. Ignoring nbf allows a token to be used before its intended activation window. python-jose validates nbf by default only if options['verify_nbf'] is not explicitly set to False."
  - id: JOSE-INV-005
    tier: example
    statement: "create_jwt(sub='user-123', exp=time.time()+3600) returns a string with 3 dot-separated segments"
    rationale: "Smoke test: a well-formed JWT has exactly 3 base64url-encoded segments separated by dots (header.payload.signature). Any other format indicates the encoder is broken."
---

## Intent

Wrap python-jose's `jwt.encode()` and `jwt.decode()` with explicit, safe defaults.
python-jose (3.3.0, 2022) is nearly abandoned — new projects should evaluate
joserfc (authlib) or PyJWT. For projects already using python-jose, this spec
enforces the invariants that wrapper code consistently violates: the exp=0 falsy
check, algorithm restriction, algorithm confusion detection, and nbf validation.

The critical insight: python-jose's decode() is safe if called correctly, but
calling it correctly requires three explicit choices (algorithms list, options dict,
and key-type awareness) that most wrapper code omits. This spec formalizes those
choices as verifiable invariants so Nightjar can prove the wrapper code is safe.

## Acceptance Criteria

### Story 1 — JWT Validation (P1)

**As a** protected API endpoint, **I want** to validate an incoming JWT, **so that** only legitimate callers access the resource.

1. **Given** a valid token with exp=time.time()+3600, **When** validate_jwt() is called, **Then** the payload dict with sub, exp, iat is returned
2. **Given** a token with exp=0 (Unix epoch 1970), **When** validate_jwt() is called, **Then** JWTExpiredError is raised
3. **Given** a token with exp=None (no exp claim), **When** validate_jwt() is called, **Then** JWTExpiredError is raised (exp is required by this spec)
4. **Given** a token with alg=none in the header, **When** validate_jwt() is called, **Then** JWTAlgorithmError is raised regardless of signature
5. **Given** a token whose nbf is 10 minutes in the future, **When** validate_jwt() is called, **Then** JWTNbfError is raised

### Story 2 — JWT Creation (P2)

**As a** login service, **I want** to issue JWTs, **so that** authenticated sessions can be established.

1. **Given** sub="user-42" and exp=now+3600, **When** create_jwt() is called, **Then** a string with 3 dot-separated segments is returned
2. **Given** a created token passed back to validate_jwt(), **When** the full round-trip runs, **Then** the returned payload sub equals the original sub
3. **Given** exp=time.time()-1 (already expired), **When** create_jwt() is called, **Then** ValueError is raised — creating already-expired tokens must be rejected at creation time

### Edge Cases

- What if exp is a float representing year 2099? → Valid, accepted
- What if exp is an integer 0? → JWTExpiredError (epoch 1970 is expired)
- What if algorithms=[] (empty list)? → JWTAlgorithmError raised before decode attempt
- What if the token has 4 segments (malformed)? → JWTDecodeError raised
- What if the secret is fewer than 32 characters? → ValueError raised before encode

## Functional Requirements

- **FR-JOSE-001**: System MUST reject tokens where exp is None, 0, or any value <= time.time()
- **FR-JOSE-002**: System MUST reject tokens where the header's alg field is 'none' or absent
- **FR-JOSE-003**: System MUST pass an explicit, non-empty algorithms list to jose.jwt.decode() — passing algorithms=None is forbidden
- **FR-JOSE-004**: System MUST reject tokens signed with an algorithm not in the configured algorithms list
- **FR-JOSE-005**: System MUST validate the nbf claim when present — tokens used before nbf are rejected
- **FR-JOSE-006**: System MUST use a secret of at least 32 bytes for HMAC-SHA256 (256-bit key space)
