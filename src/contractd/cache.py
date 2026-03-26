"""Verification cache system — skip re-verification when spec unchanged.

Computes SHA-256(spec_content + invariant_hashes) to create a cache key.
If .card/cache/{hash}.json exists with a passing result, verification is
skipped entirely. Any change to the spec or its invariants automatically
invalidates the cache (different hash = different key = cache miss).

This follows the same hash-based integrity pattern as the sealed
dependency manifest [REF-C08].

References:
- [REF-C08] Sealed Dependency Manifest — hash-based integrity pattern
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CacheEntry:
    """A cached verification result.

    Stored as .card/cache/{cache_key}.json.
    """

    cache_key: str
    verified: bool
    stages_passed: int
    stages_total: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "cache_key": self.cache_key,
            "verified": self.verified,
            "stages_passed": self.stages_passed,
            "stages_total": self.stages_total,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Deserialize from dict."""
        return cls(
            cache_key=data["cache_key"],
            verified=data["verified"],
            stages_passed=data["stages_passed"],
            stages_total=data["stages_total"],
            timestamp=data.get("timestamp", ""),
        )


def compute_cache_key(spec_content: str, invariant_statements: list[str]) -> str:
    """Compute a deterministic cache key from spec content and invariants.

    The key is SHA-256(spec_content + sorted invariant statements).
    Any change to the spec or invariants produces a different key,
    which means automatic cache invalidation.

    Args:
        spec_content: The full text of the .card.md spec file.
        invariant_statements: List of invariant statement strings.

    Returns:
        Hex-encoded SHA-256 hash string (64 chars).
    """
    hasher = hashlib.sha256()
    hasher.update(spec_content.encode("utf-8"))
    for inv in invariant_statements:
        hasher.update(inv.encode("utf-8"))
    return hasher.hexdigest()


def store_result(entry: CacheEntry, cache_dir: str) -> None:
    """Store a verification result in the cache.

    Writes to {cache_dir}/{cache_key}.json.

    Args:
        entry: The cache entry to store.
        cache_dir: Path to the cache directory (typically .card/cache/).
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    output = cache_path / f"{entry.cache_key}.json"
    output.write_text(
        json.dumps(entry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def get_cached_result(cache_key: str, cache_dir: str) -> CacheEntry | None:
    """Retrieve a cached verification result.

    Args:
        cache_key: The SHA-256 cache key.
        cache_dir: Path to the cache directory.

    Returns:
        CacheEntry if found, None on cache miss.
    """
    cache_file = Path(cache_dir) / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return CacheEntry.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def is_cache_valid(cache_key: str, cache_dir: str) -> bool:
    """Check if a cached result exists and passed verification.

    Only returns True if there's a cache hit AND the cached result
    was verified=True. Failed verifications are not considered valid
    cache hits (the user likely wants to re-verify after fixing).

    Args:
        cache_key: The SHA-256 cache key.
        cache_dir: Path to the cache directory.

    Returns:
        True only if cache hit with verified=True.
    """
    entry = get_cached_result(cache_key, cache_dir)
    if entry is None:
        return False
    return entry.verified


def invalidate_cache(cache_key: str, cache_dir: str) -> None:
    """Invalidate a cache entry (or all entries).

    Args:
        cache_key: The cache key to invalidate, or '*' for all entries.
        cache_dir: Path to the cache directory.
    """
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return

    if cache_key == "*":
        for f in cache_path.glob("*.json"):
            f.unlink()
    else:
        target = cache_path / f"{cache_key}.json"
        if target.exists():
            target.unlink()
