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
