---
card-version: "1.0"
id: httpx
title: httpx HTTP Client — Community Spec
status: active
module:
  owns:
    - make_request()
    - build_client()
    - safe_get()
    - safe_post()
  depends-on:
    httpx: ">=0.27.0"
  excludes:
    - "WebSocket connections"
    - "HTTP/3 (QUIC) transport"
    - "Multipart file upload chunking strategy"
contract:
  inputs:
    - name: url
      type: string
      constraints: "(url.startswith('https://') OR url.startswith('http://')) AND NOT is_private_ip(url)"
    - name: timeout
      type: float
      constraints: "timeout > 0 AND timeout <= 300"
    - name: verify
      type: bool
      constraints: "verify == True — SSL verification must not be disabled"
    - name: follow_redirects
      type: bool
      constraints: "bool type"
    - name: headers
      type: object
      constraints: "headers does not contain Authorization when follow_redirects=True and redirect may change origin"
  outputs:
    - name: HTTPResponse
      type: object
      schema:
        status_code: integer
        headers: object
        content: bytes
        url: string
        elapsed_ms: float
  errors:
    - SSRFAttemptError
    - SSLVerificationError
    - TimeoutConfigurationError
    - RedirectAuthLeakError
    - PrivateIPError
constraints:
  security: "OWASP SSRF Prevention Cheat Sheet — validate all URLs before dispatch"
  performance: "default timeout must be finite — never None or math.inf"
  compliance: "HTTPS required for all production endpoints; HTTP allowed only for localhost in tests"
invariants:
  - id: HTTPX-INV-001
    tier: property
    statement: "build_client() raises TimeoutConfigurationError when timeout is not explicitly set — httpx.Client() with no timeout argument is forbidden"
    rationale: "httpx 0.23+ sets a default 5-second timeout, but this default is easy to override to None. More importantly, code that worked in httpx 0.22 (no default timeout) silently hangs forever when the server stops responding. The invariant requires explicit timeout declaration at client construction time — implicit reliance on library defaults creates invisible fragility across version upgrades. A missing timeout in a production service causes thread exhaustion under slow/stuck upstream connections. This is property-tier (not formal) because Dafny/CrossHair cannot distinguish between a parameter being 'explicitly passed' versus 'defaulted' — that distinction is about call-site API usage, not mathematical postconditions. Hypothesis tests this by calling build_client() with and without the timeout kwarg."
  - id: HTTPX-INV-002
    tier: formal
    statement: "build_client() raises SSLVerificationError when verify=False is passed — SSL certificate verification must never be disabled"
    rationale: "httpx.Client(verify=False) silently accepts any TLS certificate, including self-signed, expired, and adversary-controlled certificates. This is functionally equivalent to no encryption. The pattern appears in production code that was 'tested' against a development server with a self-signed cert and was never changed. Once verify=False is in code, it tends to spread. The invariant makes verify=False a hard build failure."
  - id: HTTPX-INV-003
    tier: property
    statement: "make_request() raises SSRFAttemptError when the resolved IP address of the URL falls within 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, or 169.254.0.0/16 (link-local) before the request is dispatched"
    rationale: "Server-Side Request Forgery: an attacker passes a URL like 'http://192.168.1.1/admin' or 'http://169.254.169.254/latest/meta-data/' (AWS EC2 metadata endpoint). httpx will faithfully send the request to the internal network. The check must happen AFTER DNS resolution, not just on the URL string, because http://attacker.com may resolve to 192.168.1.1 via DNS rebinding. The invariant requires a post-DNS IP validation step."
  - id: HTTPX-INV-004
    tier: property
    statement: "make_request() strips the Authorization header from the forwarded request when a redirect changes the URL scheme or host — auth headers must not leak to third parties"
    rationale: "httpx follow_redirects=True sends the same headers to every redirect destination. If a redirect points from example.com to evil.com, the Authorization: Bearer <token> header is forwarded to evil.com. httpx 0.23+ strips auth on cross-origin redirects but only for headers named 'Authorization'. Custom auth header names (X-API-Key, X-Auth-Token) are not stripped. The invariant covers all auth-class headers."
  - id: HTTPX-INV-005
    tier: property
    statement: "make_request() raises an error when the URL scheme is neither 'http' nor 'https' — schemes like 'file://', 'ftp://', 'gopher://', 'dict://' must be rejected"
    rationale: "Non-HTTP schemes can be used in SSRF attacks to read local files (file://etc/passwd), trigger FTP interactions, or exploit legacy protocol handlers. httpx does not natively block these in all versions. A pre-dispatch URL scheme allowlist prevents scheme-based SSRF escalation."
  - id: HTTPX-INV-006
    tier: example
    statement: "safe_get('https://httpbin.org/status/200', timeout=5.0) returns HTTPResponse with status_code=200"
    rationale: "Integration smoke test: confirms the client can reach an external HTTPS endpoint with an explicit timeout and valid cert, proving the SSL and timeout configurations are wired correctly. NOTE: this is a network-requiring integration test and must be excluded from CI unit test runs via pytest.mark.integration."
---

## Intent

Wrap httpx's async and sync clients with security-first defaults. httpx is actively
maintained (0.27+ as of 2024) and is the modern replacement for requests. However,
its flexibility — particularly the ability to set verify=False, timeout=None, and
follow_redirects=True without any warnings — makes it easy to write insecure
production code.

The three failure modes this spec addresses: (1) missing or explicitly disabled
timeout causing thread exhaustion under slow upstream servers; (2) SSL verification
disabled for convenience in development and never re-enabled; (3) SSRF via redirect
chaining to internal network addresses. All three have caused real production
incidents.

## Acceptance Criteria

### Story 1 — Safe GET Request (P1)

**As a** backend service, **I want** to make HTTP requests to external APIs, **so that** I can integrate with third-party services.

1. **Given** url="https://api.example.com/data", timeout=10.0, **When** safe_get() is called, **Then** an HTTPResponse with the response data is returned
2. **Given** url="https://192.168.1.1/admin", **When** safe_get() is called, **Then** SSRFAttemptError is raised before any network connection is made
3. **Given** url="http://169.254.169.254/latest/meta-data/", **When** safe_get() is called, **Then** SSRFAttemptError is raised (AWS metadata endpoint)
4. **Given** url="file:///etc/passwd", **When** safe_get() is called, **Then** SSRFAttemptError is raised
5. **Given** no timeout argument, **When** build_client() is called, **Then** TimeoutConfigurationError is raised

### Story 2 — SSL and Redirects (P2)

**As a** security-conscious developer, **I want** SSL verification to be always enabled, **so that** TLS certificates are validated.

1. **Given** verify=False, **When** build_client() is called, **Then** SSLVerificationError is raised
2. **Given** a URL that redirects from https://trusted.com to https://evil.com, **When** make_request() follows the redirect, **Then** the Authorization header is not present in the request to evil.com
3. **Given** a redirect that changes scheme from HTTPS to HTTP, **When** make_request() follows the redirect, **Then** the redirect is blocked or the auth headers are stripped

### Edge Cases

- What if the URL hostname resolves to both public and private IPs (split-horizon DNS)? → All resolved IPs checked; any private IP triggers SSRFAttemptError
- What if timeout=0.001 (1ms, effectively always times out)? → Accepted — unreasonable but valid
- What if timeout=300 (5 minutes)? → Accepted — at the boundary
- What if timeout=301? → TimeoutConfigurationError — above the configured maximum
- What if follow_redirects=False? → Auth header check not needed (no redirects)

## Functional Requirements

- **FR-HTTPX-001**: System MUST require explicit timeout parameter at client construction — no default reliance
- **FR-HTTPX-002**: System MUST reject verify=False with a hard error (not a warning)
- **FR-HTTPX-003**: System MUST validate the resolved IP address against private IP ranges after DNS resolution
- **FR-HTTPX-004**: System MUST strip Authorization, X-API-Key, X-Auth-Token, and Cookie headers on cross-origin redirects
- **FR-HTTPX-005**: System MUST reject non-HTTP/HTTPS URL schemes at URL parsing time
- **FR-HTTPX-006**: System MUST log the final URL after redirect resolution (for audit trail)
