"""Shared invariant pattern library — append-only.

Stores abstracted invariant patterns with DP-protected confidence
metadata. Each entry tracks: pattern_id, fingerprint, abstract_form,
abstract_invariant, tenant_count (DP-protected), confidence (DP-protected),
verification_method, and proof artifact hash.

This is the cross-tenant knowledge base. Patterns flow:
  error → abstraction → mining → verification → library → herd immunity

References:
- [REF-C09] Immune system acquired immunity — pattern accumulation
- [REF-C10] Herd immunity via differential privacy — sharing mechanism
- [REF-P18] Self-healing software — pattern library concept
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class InvariantPattern:
    """An abstracted invariant pattern in the shared library.

    All fields are PII-free. Tenant counts and confidence are
    DP-protected via the privacy module.

    References:
    - [REF-C10] Privacy-preserving pattern representation
    - [REF-C09] Immune system pattern storage
    """

    pattern_id: str
    fingerprint: str
    abstract_form: str
    abstract_invariant: str
    tenant_count_dp: float
    confidence_dp: float
    verification_method: str
    proof_hash: str
    is_universal: bool = False


class PatternLibrary:
    """SQLite-backed append-only library of invariant patterns.

    Patterns are never deleted — only added or promoted to universal.
    DP-protected metadata can be updated as more evidence accumulates.

    References:
    - [REF-C09] Immune system acquired immunity
    - [REF-C10] Herd immunity pattern library
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    abstract_form TEXT NOT NULL,
                    abstract_invariant TEXT NOT NULL,
                    tenant_count_dp REAL NOT NULL,
                    confidence_dp REAL NOT NULL,
                    verification_method TEXT NOT NULL,
                    proof_hash TEXT NOT NULL,
                    is_universal INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_fingerprint
                ON patterns(fingerprint)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_universal
                ON patterns(is_universal)
            """)
            conn.commit()
        finally:
            conn.close()

    def add_pattern(self, pattern: InvariantPattern) -> str:
        """Add a pattern to the library. Returns the pattern_id.

        If pattern_id is empty, a UUID is generated.
        """
        pattern_id = pattern.pattern_id or str(uuid.uuid4())[:12]
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO patterns
                   (pattern_id, fingerprint, abstract_form, abstract_invariant,
                    tenant_count_dp, confidence_dp, verification_method,
                    proof_hash, is_universal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern_id,
                    pattern.fingerprint,
                    pattern.abstract_form,
                    pattern.abstract_invariant,
                    pattern.tenant_count_dp,
                    pattern.confidence_dp,
                    pattern.verification_method,
                    pattern.proof_hash,
                    int(pattern.is_universal),
                ),
            )
            conn.commit()
            return pattern_id
        finally:
            conn.close()

    def get_pattern(self, pattern_id: str) -> InvariantPattern | None:
        """Get a pattern by its ID. Returns None if not found."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM patterns WHERE pattern_id = ?",
                (pattern_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_pattern(row)
        finally:
            conn.close()

    def get_by_fingerprint(self, fingerprint: str) -> list[InvariantPattern]:
        """Get all patterns matching a fingerprint."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM patterns WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchall()
            return [self._row_to_pattern(r) for r in rows]
        finally:
            conn.close()

    def search(self, query: str) -> list[InvariantPattern]:
        """Search patterns by abstract_form text match."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM patterns WHERE abstract_form LIKE ?",
                (f"%{query}%",),
            ).fetchall()
            return [self._row_to_pattern(r) for r in rows]
        finally:
            conn.close()

    def get_universal_patterns(self) -> list[InvariantPattern]:
        """Get all patterns promoted to universal status."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM patterns WHERE is_universal = 1"
            ).fetchall()
            return [self._row_to_pattern(r) for r in rows]
        finally:
            conn.close()

    def update_confidence(
        self,
        pattern_id: str,
        tenant_count_dp: float,
        confidence_dp: float,
    ) -> None:
        """Update DP-protected confidence metadata for a pattern."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE patterns SET tenant_count_dp = ?, confidence_dp = ?
                   WHERE pattern_id = ?""",
                (tenant_count_dp, confidence_dp, pattern_id),
            )
            conn.commit()
        finally:
            conn.close()

    def promote_to_universal(self, pattern_id: str) -> None:
        """Promote a pattern to universal status."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE patterns SET is_universal = 1 WHERE pattern_id = ?",
                (pattern_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_count(self) -> int:
        """Total number of patterns in the library."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()
            return row[0]
        finally:
            conn.close()

    @staticmethod
    def _row_to_pattern(row: tuple) -> InvariantPattern:
        return InvariantPattern(
            pattern_id=row[0],
            fingerprint=row[1],
            abstract_form=row[2],
            abstract_invariant=row[3],
            tenant_count_dp=row[4],
            confidence_dp=row[5],
            verification_method=row[6],
            proof_hash=row[7],
            is_universal=bool(row[8]),
        )


# --- Module-level convenience functions ---


def add_pattern(db_path: str, pattern: InvariantPattern) -> str:
    """Add a pattern. Convenience wrapper."""
    return PatternLibrary(db_path).add_pattern(pattern)


def get_pattern(db_path: str, pattern_id: str) -> InvariantPattern | None:
    """Get a pattern. Convenience wrapper."""
    return PatternLibrary(db_path).get_pattern(pattern_id)


def search_patterns(db_path: str, query: str) -> list[InvariantPattern]:
    """Search patterns. Convenience wrapper."""
    return PatternLibrary(db_path).search(query)


def get_pattern_count(db_path: str) -> int:
    """Count patterns. Convenience wrapper."""
    return PatternLibrary(db_path).get_count()


def update_confidence(
    db_path: str, pattern_id: str, tenant_count_dp: float, confidence_dp: float
) -> None:
    """Update confidence. Convenience wrapper."""
    PatternLibrary(db_path).update_confidence(pattern_id, tenant_count_dp, confidence_dp)
