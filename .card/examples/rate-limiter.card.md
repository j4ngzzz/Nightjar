---
card-version: "1.0"
id: rate-limiter-example
title: Rate Limiter — Example Spec
status: active
module:
  owns: [check_rate_limit(), record_request(), reset_window(), get_remaining()]
  depends-on: {}
  excludes:
    - "Distributed rate limiting (Redis)"
    - "Per-endpoint limits"
contract:
  inputs:
    - name: max_requests
      type: int
      constraints: "max_requests >= 1"
    - name: window_seconds
      type: float
      constraints: "window_seconds > 0"
    - name: burst_allowance
      type: int
      constraints: "burst_allowance >= 0"
    - name: user_id
      type: string
      constraints: "len(user_id) > 0"
  outputs:
    - name: RateLimitResult
      type: object
      schema:
        allowed: bool
        remaining: int
        reset_at: float
        current_count: int
  errors:
    - RateLimitExceededError
    - InvalidWindowError
    - InvalidLimitError
invariants:
  - id: RATE-INV-001
    tier: property
    statement: "current_count is always non-negative — current_count >= 0"
    rationale: "Decrementing on concurrent requests can push the counter negative. A negative count makes remaining = max_requests - current_count > max_requests, effectively disabling the limit."
  - id: RATE-INV-002
    tier: property
    statement: "window_seconds is always strictly positive — window_seconds > 0"
    rationale: "A zero-second window causes division-by-zero in requests-per-second calculations. A negative window makes reset_at < now, causing every request to appear as a new window."
  - id: RATE-INV-003
    tier: formal
    statement: "current_count <= max_requests + burst_allowance at all times"
    rationale: "The rate limiter must enforce the ceiling. A count exceeding max_requests + burst means requests were allowed beyond the configured limit."
  - id: RATE-INV-004
    tier: formal
    statement: "reset_at > time.time() when a window is active"
    rationale: "This is the litellm budget_manager bug pattern: `created_at = time.time()` as a default argument is evaluated once at import time. If reset_at is computed relative to a stale timestamp, every new window is immediately treated as expired."
  - id: RATE-INV-005
    tier: property
    statement: "burst_allowance is always non-negative — burst_allowance >= 0"
    rationale: "Negative burst allowance would reduce the effective limit below max_requests, causing requests to be rejected before reaching the configured limit."
  - id: RATE-INV-006
    tier: property
    statement: "remaining = max(0, max_requests + burst_allowance - current_count)"
    rationale: "Remaining must never be negative. A caller seeing remaining < 0 cannot interpret the value correctly. Clamp to 0."
  - id: RATE-INV-007
    tier: property
    statement: "check_rate_limit returns allowed=False and raises RateLimitExceededError when current_count >= max_requests + burst_allowance"
    rationale: "The rejection must be consistent: the boolean and the exception must agree. Returning allowed=False without raising (or vice versa) creates inconsistent caller behaviour."
  - id: RATE-INV-008
    tier: formal
    statement: "after reset_window(), current_count == 0 and reset_at > time.time()"
    rationale: "A reset that leaves current_count > 0 means the window was not fully cleared. A reset that sets reset_at <= now means the window immediately expires and the next check triggers another reset."
  - id: RATE-INV-009
    tier: property
    statement: "max_requests >= 1 — a limit of 0 requests is meaningless and blocks all traffic"
    rationale: "A rate limiter configured with max_requests=0 would reject every request including the first, making the service inaccessible. Reject this configuration at construction time."
---

## Intent

Enforce per-user request rate limits within a sliding time window. Allow a
configurable burst above the sustained limit. Track the count atomically.
Always compute reset timestamps from the current time, not from a cached value.

This spec is an example for Nightjar tutorials. It demonstrates rate limiter
invariants that are frequently violated: the mutable-default-argument timestamp
bug (found in litellm 1.82.6), the negative-count underflow, and the
remaining-count clamping requirement.

## Acceptance Criteria

### Story 1 — Allow Request (P1)

**As a** rate-limited API, **I want** to allow requests within the limit, **so that** legitimate traffic is served.

1. **Given** max_requests=10, current_count=5, **When** check_rate_limit() is called, **Then** allowed=True, remaining=5 is returned
2. **Given** max_requests=10, current_count=10, burst_allowance=0, **When** check_rate_limit() is called, **Then** allowed=False, RateLimitExceededError is raised
3. **Given** max_requests=10, current_count=10, burst_allowance=2, **When** check_rate_limit() is called, **Then** allowed=True (within burst), remaining=2

### Story 2 — Reset Window (P2)

**As a** rate limiter, **I want** to reset the counter when the window expires, **so that** limits refresh as configured.

1. **Given** a window that expired 1 second ago, **When** check_rate_limit() is called, **Then** reset_window() fires, current_count resets to 0, the request is allowed
2. **Given** reset_window() is called, **When** the state is inspected, **Then** current_count == 0 and reset_at > time.time()

### Story 3 — Concurrent Requests (P3)

**As a** high-traffic service, **I want** the counter to stay accurate under concurrent load, **so that** the limit is respected.

1. **Given** 10 concurrent requests against a limit of 10, **When** all resolve, **Then** current_count == 10, no negative counts, exactly 10 allowed
2. **Given** current_count == 0 and a decrement bug fires, **When** get_remaining() is called, **Then** remaining >= 0 (clamped, never negative)

### Edge Cases

- What if max_requests=0? → InvalidLimitError raised at construction
- What if window_seconds=0.0? → InvalidWindowError raised at construction
- What if burst_allowance=0 (default)? → Limit is exactly max_requests, no burst
- What if reset_at is computed with a mutable default argument? → Fails RATE-INV-004 (reset_at will be in the past for long-running processes)

## Functional Requirements

- **FR-RATE-001**: System MUST reject max_requests < 1 at construction with InvalidLimitError
- **FR-RATE-002**: System MUST reject window_seconds <= 0 at construction with InvalidWindowError
- **FR-RATE-003**: System MUST compute reset_at as time.time() + window_seconds at window creation (never at module import time)
- **FR-RATE-004**: System MUST clamp remaining to 0 when current_count exceeds the limit
- **FR-RATE-005**: System MUST return consistent allowed=False and raise RateLimitExceededError together when limit is reached
- **FR-RATE-006**: System MUST reset current_count to exactly 0 (not decrement) on window reset
