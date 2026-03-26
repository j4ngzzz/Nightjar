"""Verification cache system — monolithic + per-stage Salsa-style caching.

MONOLITHIC CACHE (original):
  Computes SHA-256(spec_content + invariant_hashes) → single pass/fail entry.
  Skips entire verification when spec unchanged.

SALSA-STYLE PER-STAGE CACHE (W3.3 addition):
  Content-addressed per-stage results with dependency-aware invalidation.
  Ported from Salsa red-green algorithm (Rust, MIT) to Python [Scout 5 F3].

  Algorithm [Scout 5 F3]:
  1. Forward flood: input changes → mark downstream stages "red" (stale)
  2. Backward verify: recompute only stages whose inputs actually changed
  3. Early cutoff: if recomputed stage produces same result hash → skip downstream

  Dependency graph for Nightjar pipeline:
    spec content → Stage 0 → Stage 1 → Stage 2 → Stage 3 → Stage 4
  With per-stage caching:
    - Change to intent only → Stage 0 reruns → if AST unchanged → skip 1-4
    - Change to invariant → Stages 0, 3, 4 rerun → skip 1, 2
    - Change to deps → Stages 0, 1 rerun → if lock unchanged → skip 2-4

This follows the same hash-based integrity pattern as [REF-C08].

References:
- [REF-C08] Sealed Dependency Manifest — hash-based integrity pattern
- Scout 5 Finding 3 — Salsa incremental computation framework
- Salsa repo: https://github.com/salsa-rs/salsa (MIT)
"""

import hashlib
import json
from dataclasses import dataclass, field
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


# ── Salsa-style per-stage caching [Scout 5 F3] ───────────────────────────
#
# Content-addressed per-stage results with dependency-aware invalidation.
# Ported from Salsa red-green algorithm to Python.
# Source: https://github.com/salsa-rs/salsa (MIT)


@dataclass
class StageCacheEntry:
    """Per-stage cache entry for Salsa-style incremental caching [Scout 5 F3].

    Keyed by (stage_name, input_hash) — one entry per stage per unique input.
    Stores result_hash for early-cutoff checks (if result unchanged, skip downstream).

    Stored as .card/cache/stage_{stage_name}_{input_hash[:16]}.json
    """

    stage_name: str       # e.g., "stage0", "pbt", "formal"
    input_hash: str       # SHA-256 of all inputs to this stage
    result_hash: str      # SHA-256 of the stage's output (for early cutoff)
    status: str           # "pass", "fail", or "skip"
    duration_ms: int
    timestamp: str = field(default="")

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "stage_name": self.stage_name,
            "input_hash": self.input_hash,
            "result_hash": self.result_hash,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StageCacheEntry":
        """Deserialize from dict."""
        return cls(
            stage_name=data["stage_name"],
            input_hash=data["input_hash"],
            result_hash=data["result_hash"],
            status=data["status"],
            duration_ms=data["duration_ms"],
            timestamp=data.get("timestamp", ""),
        )


def hash_stage_inputs(stage_name: str, *inputs: str) -> str:
    """Compute deterministic SHA-256 hash of a stage's inputs.

    Includes the stage name in the hash so different stages with identical
    input strings produce different hashes.

    Args:
        stage_name: Name of the stage (e.g., 'stage0', 'pbt', 'formal').
        *inputs: All input strings for this stage (spec content, code, etc.).

    Returns:
        Hex-encoded SHA-256 hash (64 chars).
    """
    hasher = hashlib.sha256()
    hasher.update(stage_name.encode("utf-8"))
    for inp in inputs:
        hasher.update(inp.encode("utf-8"))
    return hasher.hexdigest()


def _stage_cache_filename(stage_name: str, input_hash: str) -> str:
    """Compute the filename for a per-stage cache entry."""
    return f"stage_{stage_name}_{input_hash[:16]}.json"


def store_stage_cache(entry: StageCacheEntry, cache_dir: str) -> None:
    """Store a per-stage verification result in the cache.

    Writes to {cache_dir}/stage_{stage_name}_{input_hash[:16]}.json.

    Args:
        entry: The per-stage cache entry to store.
        cache_dir: Path to the cache directory (typically .card/cache/).
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    filename = _stage_cache_filename(entry.stage_name, entry.input_hash)
    (cache_path / filename).write_text(
        json.dumps(entry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def get_stage_cache(
    stage_name: str,
    input_hash: str,
    cache_dir: str,
) -> "StageCacheEntry | None":
    """Retrieve a per-stage cached result.

    Args:
        stage_name: Name of the stage.
        input_hash: SHA-256 of the stage's inputs.
        cache_dir: Path to the cache directory.

    Returns:
        StageCacheEntry if cache hit, None on miss.
    """
    filename = _stage_cache_filename(stage_name, input_hash)
    cache_file = Path(cache_dir) / filename
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        entry = StageCacheEntry.from_dict(data)
        # Validate that stored entry matches the requested input_hash
        if entry.input_hash != input_hash or entry.stage_name != stage_name:
            return None
        return entry
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def should_skip_stage(stage_name: str, input_hash: str, cache_dir: str) -> bool:
    """Check if a stage can be skipped due to unchanged inputs [Scout 5 F3].

    Returns True only when:
    - There is a cache hit for (stage_name, input_hash)
    - The cached result was status="pass" (or "skip")
    - Failed stages always re-run (user may have fixed the issue)

    This is the Salsa "backward verify" step: inputs unchanged → skip.

    Args:
        stage_name: Name of the stage to potentially skip.
        input_hash: SHA-256 of the current stage inputs.
        cache_dir: Path to the cache directory.

    Returns:
        True if the stage can safely be skipped.
    """
    entry = get_stage_cache(stage_name, input_hash, cache_dir)
    if entry is None:
        return False
    # Only skip on pass/skip; failed stages must be re-verified
    return entry.status in ("pass", "skip")


def check_early_cutoff(
    stage_name: str,
    input_hash: str,
    new_result_hash: str,
    cache_dir: str,
) -> bool:
    """Early cutoff: if result unchanged, downstream stages can skip [Scout 5 F3].

    This is the Salsa "early cutoff" optimization: after recomputing a stage,
    if the result hash is identical to the cached result hash, all downstream
    stages can skip (their inputs — this stage's output — haven't changed).

    Example:
        - Spec intent changed → Stage 0 reruns → same AST → early cutoff
        - Stages 1-4 can skip because Stage 0's output is identical

    Args:
        stage_name: Name of the stage that was just recomputed.
        input_hash: SHA-256 of the stage inputs (to look up the prior result).
        new_result_hash: SHA-256 of the newly computed result.
        cache_dir: Path to the cache directory.

    Returns:
        True if result is unchanged (downstream can skip), False otherwise.
    """
    entry = get_stage_cache(stage_name, input_hash, cache_dir)
    if entry is None:
        return False  # No prior result to compare
    return entry.result_hash == new_result_hash
