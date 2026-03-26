"""Tests for verification cache system.

The cache system computes SHA-256(spec_content + invariant_hashes) to
create a cache key. If .card/cache/{hash}.json exists with a passing
result, verification can be skipped. Any spec change invalidates the
cache entry automatically.

References:
- [REF-C08] Sealed Dependency Manifest — same hash-based integrity pattern
"""

import json
import hashlib
from pathlib import Path

import pytest

from nightjar.cache import (
    compute_cache_key,
    get_cached_result,
    get_stage_cache,
    hash_stage_inputs,
    StageCacheEntry,
    should_skip_stage,
    store_stage_cache,
    check_early_cutoff,
    store_result,
    invalidate_cache,
    is_cache_valid,
    CacheEntry,
)


# ── compute_cache_key ────────────────────────────────────


class TestComputeCacheKey:
    """Compute deterministic cache key from spec content."""

    def test_returns_hex_string(self):
        """Key should be a 64-char hex SHA-256."""
        key = compute_cache_key("spec content", ["inv1", "inv2"])
        assert isinstance(key, str)
        assert len(key) == 64
        int(key, 16)

    def test_deterministic(self):
        """Same inputs produce same key."""
        k1 = compute_cache_key("spec", ["a", "b"])
        k2 = compute_cache_key("spec", ["a", "b"])
        assert k1 == k2

    def test_different_spec_different_key(self):
        """Different spec content produces different key."""
        k1 = compute_cache_key("spec v1", ["a"])
        k2 = compute_cache_key("spec v2", ["a"])
        assert k1 != k2

    def test_different_invariants_different_key(self):
        """Different invariants produce different key."""
        k1 = compute_cache_key("spec", ["inv1"])
        k2 = compute_cache_key("spec", ["inv2"])
        assert k1 != k2

    def test_invariant_order_matters(self):
        """Order of invariants should affect the key."""
        k1 = compute_cache_key("spec", ["a", "b"])
        k2 = compute_cache_key("spec", ["b", "a"])
        assert k1 != k2

    def test_empty_invariants(self):
        """Empty invariant list should still produce a valid key."""
        key = compute_cache_key("spec", [])
        assert len(key) == 64


# ── CacheEntry ───────────────────────────────────────────


class TestCacheEntry:
    """Cache entry data structure."""

    def test_to_dict(self):
        """Should serialize to dict."""
        entry = CacheEntry(
            cache_key="abc123",
            verified=True,
            stages_passed=5,
            stages_total=5,
            timestamp="2026-03-26T00:00:00Z",
        )
        d = entry.to_dict()
        assert d["cache_key"] == "abc123"
        assert d["verified"] is True

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "cache_key": "abc123",
            "verified": True,
            "stages_passed": 5,
            "stages_total": 5,
            "timestamp": "2026-03-26T00:00:00Z",
        }
        entry = CacheEntry.from_dict(d)
        assert entry.cache_key == "abc123"
        assert entry.verified is True

    def test_has_timestamp(self):
        """Should auto-generate timestamp if not provided."""
        entry = CacheEntry(cache_key="abc", verified=True, stages_passed=5, stages_total=5)
        assert entry.timestamp
        assert isinstance(entry.timestamp, str)


# ── store_result + get_cached_result ─────────────────────


class TestStoreAndRetrieve:
    """Store and retrieve cache entries."""

    def test_store_creates_file(self, tmp_path):
        """Storing a result should create a JSON file."""
        entry = CacheEntry(
            cache_key="abc123",
            verified=True,
            stages_passed=5,
            stages_total=5,
        )
        store_result(entry, str(tmp_path))
        assert (tmp_path / "abc123.json").exists()

    def test_retrieve_stored_entry(self, tmp_path):
        """Should retrieve a previously stored entry."""
        entry = CacheEntry(
            cache_key="abc123",
            verified=True,
            stages_passed=5,
            stages_total=5,
        )
        store_result(entry, str(tmp_path))
        result = get_cached_result("abc123", str(tmp_path))
        assert result is not None
        assert result.verified is True
        assert result.cache_key == "abc123"

    def test_returns_none_for_miss(self, tmp_path):
        """Cache miss should return None."""
        result = get_cached_result("nonexistent", str(tmp_path))
        assert result is None

    def test_store_overwrites_existing(self, tmp_path):
        """Storing with same key should overwrite."""
        entry1 = CacheEntry(cache_key="abc", verified=False, stages_passed=3, stages_total=5)
        entry2 = CacheEntry(cache_key="abc", verified=True, stages_passed=5, stages_total=5)
        store_result(entry1, str(tmp_path))
        store_result(entry2, str(tmp_path))
        result = get_cached_result("abc", str(tmp_path))
        assert result is not None
        assert result.verified is True


# ── is_cache_valid ───────────────────────────────────────


class TestIsCacheValid:
    """Check if a spec's verification result is cached and valid."""

    def test_valid_when_cached_pass(self, tmp_path):
        """Should return True when cache has a passing result."""
        entry = CacheEntry(cache_key="abc", verified=True, stages_passed=5, stages_total=5)
        store_result(entry, str(tmp_path))
        assert is_cache_valid("abc", str(tmp_path)) is True

    def test_invalid_when_no_cache(self, tmp_path):
        """Should return False when no cache entry exists."""
        assert is_cache_valid("missing", str(tmp_path)) is False

    def test_invalid_when_cached_fail(self, tmp_path):
        """Should return False when cached result was a failure."""
        entry = CacheEntry(cache_key="abc", verified=False, stages_passed=3, stages_total=5)
        store_result(entry, str(tmp_path))
        assert is_cache_valid("abc", str(tmp_path)) is False


# ── invalidate_cache ─────────────────────────────────────


class TestInvalidateCache:
    """Invalidate cache entries."""

    def test_removes_single_entry(self, tmp_path):
        """Should remove a specific cache entry."""
        entry = CacheEntry(cache_key="abc", verified=True, stages_passed=5, stages_total=5)
        store_result(entry, str(tmp_path))
        assert (tmp_path / "abc.json").exists()
        invalidate_cache("abc", str(tmp_path))
        assert not (tmp_path / "abc.json").exists()

    def test_noop_for_missing_entry(self, tmp_path):
        """Invalidating nonexistent entry should not error."""
        invalidate_cache("missing", str(tmp_path))  # should not raise

    def test_invalidate_all(self, tmp_path):
        """Should remove all cache entries when key is '*'."""
        for i in range(3):
            entry = CacheEntry(
                cache_key=f"key{i}",
                verified=True,
                stages_passed=5,
                stages_total=5,
            )
            store_result(entry, str(tmp_path))
        assert len(list(tmp_path.glob("*.json"))) == 3
        invalidate_cache("*", str(tmp_path))
        assert len(list(tmp_path.glob("*.json"))) == 0


# ── W3.3: Salsa-style per-stage caching [Scout 5 F3] ─────────────────────


class TestHashStageInputs:
    """Content-addressed hash for per-stage inputs [Scout 5 F3]."""

    def test_returns_hex_string(self):
        """Stage input hash must be a 64-char hex SHA-256."""
        h = hash_stage_inputs("stage0", "spec content")
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_deterministic(self):
        """Same stage name + inputs produce same hash."""
        h1 = hash_stage_inputs("pbt", "invariant text", "code text")
        h2 = hash_stage_inputs("pbt", "invariant text", "code text")
        assert h1 == h2

    def test_stage_name_affects_hash(self):
        """Different stage names produce different hashes for same inputs."""
        h1 = hash_stage_inputs("stage0", "same input")
        h2 = hash_stage_inputs("stage1", "same input")
        assert h1 != h2

    def test_different_inputs_produce_different_hash(self):
        """Different inputs produce different hash (no collisions for small inputs)."""
        h1 = hash_stage_inputs("pbt", "input_v1")
        h2 = hash_stage_inputs("pbt", "input_v2")
        assert h1 != h2

    def test_no_hash_boundary_confusion(self):
        """Different input splits must produce different hashes (null-byte delimiters)."""
        h1 = hash_stage_inputs("s", "ab", "c")
        h2 = hash_stage_inputs("s", "a", "bc")
        assert h1 != h2, (
            "hash_stage_inputs('s', 'ab', 'c') must differ from "
            "hash_stage_inputs('s', 'a', 'bc') — null-byte delimiters required"
        )


class TestStageCacheEntry:
    """Per-stage cache entry stores stage result + hashes [Scout 5 F3]."""

    def test_has_required_fields(self):
        """StageCacheEntry must track stage, input hash, result hash, status."""
        entry = StageCacheEntry(
            stage_name="pbt",
            input_hash="abc" * 21 + "a",
            result_hash="def" * 21 + "d",
            status="pass",
            duration_ms=300,
        )
        assert entry.stage_name == "pbt"
        assert entry.status == "pass"
        assert entry.duration_ms == 300

    def test_serialization_roundtrip(self):
        """to_dict / from_dict roundtrip preserves all fields."""
        entry = StageCacheEntry(
            stage_name="schema",
            input_hash="a" * 64,
            result_hash="b" * 64,
            status="pass",
            duration_ms=150,
            timestamp="2026-03-26T00:00:00Z",
        )
        d = entry.to_dict()
        restored = StageCacheEntry.from_dict(d)
        assert restored.stage_name == entry.stage_name
        assert restored.input_hash == entry.input_hash
        assert restored.result_hash == entry.result_hash
        assert restored.status == entry.status
        assert restored.duration_ms == entry.duration_ms


class TestStageCache:
    """Salsa-style per-stage cache — skip unchanged stages [Scout 5 F3]."""

    def test_cache_skips_unchanged_stage(self, tmp_path):
        """If stage inputs unchanged and cache has a pass, should_skip returns True."""
        stage = "pbt"
        input_hash = hash_stage_inputs(stage, "invariants unchanged")
        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=input_hash,
            result_hash="x" * 64,
            status="pass",
            duration_ms=300,
        )
        store_stage_cache(entry, str(tmp_path))
        assert should_skip_stage(stage, input_hash, str(tmp_path)) is True

    def test_cache_does_not_skip_on_miss(self, tmp_path):
        """Cache miss (no entry) → should_skip returns False."""
        assert should_skip_stage("pbt", "a" * 64, str(tmp_path)) is False

    def test_cache_does_not_skip_failed_stage(self, tmp_path):
        """Failed stage is not skippable (must re-verify after fix)."""
        stage = "formal"
        input_hash = hash_stage_inputs(stage, "code v1")
        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=input_hash,
            result_hash="x" * 64,
            status="fail",
            duration_ms=5000,
        )
        store_stage_cache(entry, str(tmp_path))
        assert should_skip_stage(stage, input_hash, str(tmp_path)) is False

    def test_cache_invalidates_on_upstream_change(self, tmp_path):
        """When input hash changes, old stage cache is no longer valid."""
        stage = "pbt"
        old_hash = hash_stage_inputs(stage, "invariants v1")
        new_hash = hash_stage_inputs(stage, "invariants v2")  # upstream changed

        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=old_hash,
            result_hash="x" * 64,
            status="pass",
            duration_ms=300,
        )
        store_stage_cache(entry, str(tmp_path))

        # Old hash still valid
        assert should_skip_stage(stage, old_hash, str(tmp_path)) is True
        # New hash is a miss — must re-run
        assert should_skip_stage(stage, new_hash, str(tmp_path)) is False

    def test_store_and_retrieve_stage_cache(self, tmp_path):
        """store_stage_cache + get_stage_cache roundtrip."""
        stage = "schema"
        input_hash = hash_stage_inputs(stage, "contract schema")
        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=input_hash,
            result_hash="y" * 64,
            status="pass",
            duration_ms=120,
        )
        store_stage_cache(entry, str(tmp_path))
        retrieved = get_stage_cache(stage, input_hash, str(tmp_path))
        assert retrieved is not None
        assert retrieved.stage_name == stage
        assert retrieved.status == "pass"

    def test_get_stage_cache_returns_none_on_miss(self, tmp_path):
        """get_stage_cache returns None when no entry exists."""
        result = get_stage_cache("formal", "a" * 64, str(tmp_path))
        assert result is None


class TestEarlyCutoff:
    """Early cutoff: if result unchanged, downstream stages skip [Scout 5 F3].

    This is the Salsa red-green optimization:
    If a recomputed stage produces the SAME result hash as before,
    all downstream stages can skip (their inputs haven't actually changed).
    """

    def test_early_cutoff_when_result_unchanged(self, tmp_path):
        """If stage result hash is same as cached, downstream can skip."""
        stage = "stage0"
        input_hash = hash_stage_inputs(stage, "new spec content")
        same_result_hash = "a" * 64

        # Store entry with this result hash
        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=input_hash,
            result_hash=same_result_hash,
            status="pass",
            duration_ms=50,
        )
        store_stage_cache(entry, str(tmp_path))

        # Check: same result_hash → early cutoff (downstream can skip)
        assert check_early_cutoff(stage, input_hash, same_result_hash, str(tmp_path)) is True

    def test_no_early_cutoff_when_result_changes(self, tmp_path):
        """If stage result hash changed, downstream must re-run."""
        stage = "stage0"
        input_hash = hash_stage_inputs(stage, "spec content")
        old_result_hash = "a" * 64
        new_result_hash = "b" * 64  # result changed

        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=input_hash,
            result_hash=old_result_hash,
            status="pass",
            duration_ms=50,
        )
        store_stage_cache(entry, str(tmp_path))

        # Different result_hash → no early cutoff
        assert check_early_cutoff(stage, input_hash, new_result_hash, str(tmp_path)) is False

    def test_no_early_cutoff_on_cache_miss(self, tmp_path):
        """Cache miss → no early cutoff (no prior result to compare)."""
        assert check_early_cutoff("stage0", "a" * 64, "b" * 64, str(tmp_path)) is False

    def test_early_cutoff_when_input_changed_but_result_same(self, tmp_path):
        """Early cutoff fires even when input_hash changed, as long as result is same.

        This is the key Salsa early-cutoff use case: spec intent changes (new
        input_hash) but the parsed AST is identical (same result_hash) — so
        downstream stages can still skip.
        """
        stage = "stage0"
        old_input_hash = hash_stage_inputs(stage, "spec v1")
        new_input_hash = hash_stage_inputs(stage, "spec v2")  # input changed
        same_result_hash = "a" * 64  # but result (e.g. parsed AST) is same

        # Stage ran with old input, stored latest result
        entry = StageCacheEntry(
            stage_name=stage,
            input_hash=old_input_hash,
            result_hash=same_result_hash,
            status="pass",
            duration_ms=50,
        )
        store_stage_cache(entry, str(tmp_path))

        # Input changed (new_input_hash) but result is same → early cutoff
        assert check_early_cutoff(stage, new_input_hash, same_result_hash, str(tmp_path)) is True
