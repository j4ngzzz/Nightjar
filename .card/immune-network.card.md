---
card-version: "1.0"
id: immune_network
title: Immune System - Network Effect (Pattern Library, Herd Immunity, Privacy, Abstraction)
status: draft
module:
  owns:
    - PatternLibrary
    - InvariantPattern
    - check_herd_immunity
    - promote_eligible_patterns
    - evaluate_patterns
    - add_laplace_noise
    - dp_count
    - dp_mean
    - abstract_trace
    - abstract_type
    - StructuralSignature
  depends-on:
    sqlite3: "append-only pattern storage"
    opendp: "Laplace mechanism (optional, reimplemented natively) [REF-T20]"
contract:
  inputs:
    - name: pattern
      type: InvariantPattern
      constraints: "all fields non-empty; tenant_count_dp and confidence_dp are DP-protected floats"
    - name: dp_config
      type: DPConfig
      constraints: "epsilon > 0 (strictly); delta >= 0"
    - name: trace
      type: dict
      constraints: "keys: exception, message, function, args, stack; args is a dict"
  outputs:
    - name: pattern_id
      type: str
      constraints: "non-empty; UUID if not provided by caller"
    - name: herd_result
      type: HerdResult
      constraints: "eligible=True only when tenant_count_dp >= threshold AND confidence_dp >= threshold"
    - name: signature
      type: StructuralSignature
      constraints: "fingerprint is a 16-hex-char SHA-256 prefix; contains no PII"
  errors:
    - DPConfig raises ValueError for epsilon <= 0 or delta < 0
    - PatternLibrary operations raise sqlite3 errors on DB failure (not caught internally)
invariants:
  - id: INV-01
    tier: property
    statement: "DPConfig raises ValueError with message containing 'epsilon must be strictly positive' when epsilon <= 0"
    rationale: "Zero or negative epsilon breaks the Laplace mechanism (division by zero or meaningless noise); this must be a hard error"
  - id: INV-02
    tier: property
    statement: "dp_count returns a non-negative float for any non-negative integer true_count and any positive epsilon"
    rationale: "A count can never be negative even after DP noise; the result is clamped to max(0.0, noised)"
  - id: INV-03
    tier: property
    statement: "dp_mean returns a float in [0.0, 1.0] for any true_mean in [0.0, 1.0], any count >= 1, and any positive epsilon"
    rationale: "Confidence scores are probability values; DP noise must not produce values outside [0, 1]"
  - id: INV-04
    tier: property
    statement: "abstract_trace returns a StructuralSignature whose fingerprint is deterministic: two calls with the same exception class and args shape always produce the same fingerprint"
    rationale: "Cross-tenant error grouping relies on fingerprint equality; non-determinism would silently split error groups"
  - id: INV-05
    tier: property
    statement: "abstract_type and abstract_value never return strings containing the original field names or string content of dict/str values — only type-level patterns are preserved"
    rationale: "PII-free abstraction is the core privacy guarantee that enables cross-tenant sharing; any field name or value leakage would violate it"
  - id: INV-06
    tier: property
    statement: "check_herd_immunity returns HerdResult(eligible=True) if and only if pattern.tenant_count_dp >= config.tenant_count_threshold AND pattern.confidence_dp >= config.confidence_threshold; eligible=False if either condition fails"
    rationale: "Herd immunity promotion requires both thresholds simultaneously; this is the network effect gate [REF-C10]"
  - id: INV-07
    tier: property
    statement: "PatternLibrary.add_pattern is append-only: get_count() after add_pattern is always get_count_before + 1"
    rationale: "The pattern library must never shrink; patterns are permanently retained even if superseded, preserving the audit history"
  - id: INV-08
    tier: property
    statement: "promote_eligible_patterns returns a list containing only pattern_ids that were not already universal (already_universal=False) before the call"
    rationale: "Re-promoting an already-universal pattern is a no-op; the returned list must not include patterns already at universal status"
  - id: INV-09
    tier: property
    statement: "abstract_trace on a trace with exception='ValueError' and args={'x': 42} produces the same fingerprint as abstract_trace on a trace with exception='ValueError' and args={'y': 99}"
    rationale: "Fingerprinting is based on exception_class and input type SHAPE (both args are IntType), not field names or values — this is the structural abstraction guarantee"
  - id: INV-10
    tier: property
    statement: "add_laplace_noise expected value over many samples with fixed value and sensitivity equals value (unbiased): E[add_laplace_noise(v, s, e)] ≈ v"
    rationale: "The Laplace mechanism is unbiased by construction; the noise is zero-mean so the noised value is a consistent estimator of the true value"
---

## Intent

Implement the network effect layer of the Nightjar immune system: the mechanism by which one customer's bug immunizes all others. Four cooperating modules are combined:

**pattern_library.py** — SQLite-backed append-only store for abstracted invariant patterns with DP-protected metadata (tenant_count_dp, confidence_dp). Patterns are never deleted; `is_universal` is promoted when herd immunity thresholds are met.

**herd.py** — Threshold logic for promoting patterns to universal status. A pattern becomes universal when DP-protected tenant_count >= 50 AND DP-protected confidence >= 0.95 (configurable via HerdConfig). Universal invariants are applied to all new Nightjar builds.

**privacy.py** — OpenDP-compatible differential privacy primitives [REF-T20]: Laplace mechanism (`add_laplace_noise`), DP count (`dp_count`), and DP mean (`dp_mean`). Only frequency/count metadata is noised — invariant statement text is never perturbed.

**abstraction.py** — Converts concrete failure traces to PII-free structural signatures. All field names, string values, and numeric values are replaced with type-level labels (`StringType`, `IntType`, `ObjectType{f0: StringType}`). Fingerprints are SHA-256 prefixes of exception_class + input_shape.

## Acceptance Criteria

### Story 1 — Privacy Bounds Are Enforced (P0)

**As a** cross-tenant data processor, **I want** DP outputs to always be in valid ranges, **so that** shared metadata is both private and meaningful.

1. **Given** dp_count(100, epsilon=1.0) called 1000 times, **When** results are averaged, **Then** the mean is approximately 100 (within ±5 of the true value)
2. **Given** dp_mean(0.9, count=100, epsilon=1.0), **When** called, **Then** result is in [0.0, 1.0]
3. **Given** DPConfig(epsilon=0.0), **When** constructed, **Then** raises ValueError

### Story 2 — Abstraction Strips All PII (P0)

**As a** privacy auditor, **I want** abstract_trace to produce signatures with no field names or values, **so that** cross-tenant pattern sharing is safe.

1. **Given** trace={"exception": "KeyError", "args": {"user_email": "alice@example.com"}}, **When** abstract_trace is called, **Then** StructuralSignature.input_shape contains "StringType" and does NOT contain "alice" or "user_email"
2. **Given** two traces with different field names but same type shapes, **When** abstract_trace is called on both, **Then** both return the same fingerprint

### Story 3 — Herd Immunity Promotion Is Threshold-Gated (P0)

**As a** network effect engine, **I want** patterns to be promoted only when both thresholds are met, **so that** weak patterns don't become universal invariants.

1. **Given** pattern with tenant_count_dp=49.0 and confidence_dp=0.96, **When** check_herd_immunity is called with default HerdConfig, **Then** HerdResult(eligible=False)
2. **Given** pattern with tenant_count_dp=51.0 and confidence_dp=0.96, **When** check_herd_immunity is called, **Then** HerdResult(eligible=True)

## Functional Requirements

- **FR-001**: DPConfig MUST validate epsilon > 0 in __post_init__; MUST validate delta >= 0
- **FR-002**: dp_count MUST use sensitivity=1.0 (adding/removing one tenant changes count by 1)
- **FR-003**: dp_mean MUST use sensitivity=1/max(count,1) to prevent division by zero
- **FR-004**: abstract_type MUST abstract dict field names to positional indices (f0, f1, ...) — never expose original key strings
- **FR-005**: _compute_fingerprint MUST use SHA-256 and return the first 16 hex characters
- **FR-006**: PatternLibrary MUST create the patterns table with CREATE TABLE IF NOT EXISTS on __init__
- **FR-007**: promote_eligible_patterns MUST call library.promote_to_universal only for patterns where eligible=True AND already_universal=False
- **FR-008**: PatternLibrary MUST create indexes on fingerprint and is_universal columns for query performance
