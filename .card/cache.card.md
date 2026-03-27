---
card-version: "1.0"
id: cache
title: Verification Cache — Monolithic and Salsa-Style Per-Stage
status: draft
module:
  owns: [compute_cache_key(), store_result(), get_cached_result(), is_cache_valid(), invalidate_cache(), hash_stage_inputs(), store_stage_cache(), get_stage_cache(), should_skip_stage(), check_early_cutoff()]
  depends-on: {}
  excludes:
    - "Cache eviction policy — no TTL or size limit; entries persist until explicit invalidation"
    - "Cross-process locking — no file locks; concurrent writes may produce partial entries"
invariants:
  - id: INV-01
    tier: property
    statement: "is_cache_valid() returns True only when a cache entry exists AND entry.verified is True; a failed verification result is never a valid cache hit"
    rationale: "Users fix bugs between runs; a cached failure must not skip re-verification after a fix"
  - id: INV-02
    tier: property
    statement: "compute_cache_key() is deterministic: SHA-256(spec_content_bytes + sorted_invariant_bytes); any change to spec or invariants produces a different key"
    rationale: "Cache correctness depends on keys changing whenever inputs change"
  - id: INV-03
    tier: property
    statement: "hash_stage_inputs() uses null-byte (0x00) delimiters between all fields so ('ab','c') and ('a','bc') produce different hashes"
    rationale: "Concatenation without delimiters allows collision attacks and false cache hits"
  - id: INV-04
    tier: property
    statement: "should_skip_stage() returns True only when (stage_name, input_hash) has a cached entry with status 'pass' or 'skip'; status 'fail' always returns False"
    rationale: "Failed stages must re-run after user fixes; only passing results are safe to skip"
  - id: INV-05
    tier: property
    statement: "check_early_cutoff() compares new_result_hash against the latest stored result hash (not by input_hash lookup); returns False when no prior result exists"
    rationale: "Early cutoff fires when output is unchanged even if input changed — e.g. spec intent edited but parsed AST identical"
  - id: INV-06
    tier: property
    statement: "invalidate_cache() with key='*' deletes all *.json files in cache_dir; with a specific key deletes only {key}.json; missing files do not raise exceptions"
    rationale: "Wildcard invalidation must be a clean-slate reset; partial invalidation must be surgical"
  - id: INV-07
    tier: property
    statement: "get_stage_cache() returns None when the stored entry's input_hash or stage_name does not match the requested values"
    rationale: "Filename-based lookup must be validated against stored content to prevent hash-prefix collisions"
---

## Intent

Provide two levels of verification caching: a monolithic cache keyed on `SHA-256(spec + invariants)` that skips the entire pipeline when the spec is unchanged, and a Salsa-style per-stage cache keyed on `(stage_name, input_hash)` that enables fine-grained incremental reruns. Failed verifications are never cached as valid hits.

## Acceptance Criteria

### Story 1 — Monolithic Cache Hit/Miss

1. **Given** a spec was previously verified successfully, **When** `is_cache_valid(key, cache_dir)` is called with the same key, **Then** returns `True`
2. **Given** a spec was previously verified but FAILED, **When** `is_cache_valid(key, cache_dir)` is called, **Then** returns `False`
3. **Given** no cache entry exists, **When** `is_cache_valid()` is called, **Then** returns `False`

### Story 2 — Cache Key Determinism

1. **Given** identical spec content and invariants, **When** `compute_cache_key()` is called twice, **Then** both calls return the same key
2. **Given** spec content with one character changed, **When** `compute_cache_key()` is called, **Then** returns a different key

### Story 3 — Per-Stage Skip Logic (Salsa)

1. **Given** Stage 1 previously passed with input_hash H, **When** `should_skip_stage("stage1", H, cache_dir)` is called, **Then** returns `True`
2. **Given** Stage 1 previously failed with input_hash H, **When** `should_skip_stage("stage1", H, cache_dir)` is called, **Then** returns `False`
3. **Given** new_result_hash == previous result_hash, **When** `check_early_cutoff()` is called, **Then** returns `True`

### Story 4 — Invalidation

1. **Given** multiple cache entries exist, **When** `invalidate_cache("*", cache_dir)` is called, **Then** all `.json` files are deleted
2. **Given** a specific key exists, **When** `invalidate_cache(key, cache_dir)` is called, **Then** only that key's file is deleted

## Functional Requirements

- **FR-001**: MUST use SHA-256 for all cache key computation
- **FR-002**: MUST store monolithic entries as `{cache_dir}/{cache_key}.json`
- **FR-003**: MUST store per-stage entries as `{cache_dir}/stage_{stage_name}_{input_hash[:16]}.json`
- **FR-004**: MUST use null-byte delimiters in `hash_stage_inputs()` between stage_name and each input field
- **FR-005**: MUST store latest result hash in `{cache_dir}/stage_latest_{stage_name}.json` on every `store_stage_cache()` call
- **FR-006**: MUST validate stored entry's `input_hash` and `stage_name` against requested values in `get_stage_cache()`
- **FR-007**: Failed stages (status="fail") MUST NOT allow skip via `should_skip_stage()`
