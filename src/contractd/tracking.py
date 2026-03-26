"""Verification tracking database.

Records every verification run in SQLite for self-evolution analysis.
Schema: runs(id, spec_id, model, timestamp, verified, stage_results_json,
retry_count, total_cost). Computes rolling pass rate per model, per spec.

This data powers the experience replay (C2), DSPy SIMBA optimization (C3),
and AutoResearch hill climbing (C4) systems.

References:
- ARCHITECTURE.md Section 6 — self-evolution pipeline
- [REF-C02] Closed-loop verification — tracking outcomes enables improvement
- [REF-P04] AlphaVerus — self-improving loop uses historical performance data
"""

import json
import sqlite3
import time
from typing import Any


class TrackingDB:
    """SQLite-backed verification run tracker.

    Append-only for audit trail. Each run records the spec, model,
    outcome, stage-level results, retry count, and cost.

    References:
    - [REF-C02] Closed-loop verification tracks outcomes
    - [REF-P04] AlphaVerus self-improving loop
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create the runs table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    verified INTEGER NOT NULL,
                    stage_results_json TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    total_cost REAL NOT NULL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_spec_id ON runs(spec_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC)
            """)
            conn.commit()
        finally:
            conn.close()

    def record_run(
        self,
        spec_id: str,
        model: str,
        verified: bool,
        stage_results: list[dict[str, Any]],
        retry_count: int,
        total_cost: float,
    ) -> int:
        """Record a verification run. Returns the run ID.

        Args:
            spec_id: The .card.md module identifier.
            model: LLM model used (e.g. "claude-sonnet-4-6").
            verified: Whether verification passed.
            stage_results: List of stage result dicts.
            retry_count: Number of retry loop iterations.
            total_cost: Total LLM API cost in USD.

        Returns:
            The auto-incremented run ID.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO runs
                   (spec_id, model, timestamp, verified, stage_results_json,
                    retry_count, total_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    spec_id,
                    model,
                    time.time(),
                    int(verified),
                    json.dumps(stage_results),
                    retry_count,
                    total_cost,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_pass_rate(self) -> float:
        """Overall pass rate across all runs. Returns 0.0 if no runs."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), SUM(verified) FROM runs"
            ).fetchone()
            total, passed = row[0], row[1] or 0
            return passed / total if total > 0 else 0.0
        finally:
            conn.close()

    def get_pass_rate_by_model(self, model: str) -> float:
        """Pass rate for a specific model. Returns 0.0 if no runs."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), SUM(verified) FROM runs WHERE model = ?",
                (model,),
            ).fetchone()
            total, passed = row[0], row[1] or 0
            return passed / total if total > 0 else 0.0
        finally:
            conn.close()

    def get_pass_rate_by_spec(self, spec_id: str) -> float:
        """Pass rate for a specific spec. Returns 0.0 if no runs."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), SUM(verified) FROM runs WHERE spec_id = ?",
                (spec_id,),
            ).fetchone()
            total, passed = row[0], row[1] or 0
            return passed / total if total > 0 else 0.0
        finally:
            conn.close()

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve the most recent runs, ordered by timestamp descending.

        Returns list of dicts with all run fields. stage_results is
        deserialized from JSON.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT id, spec_id, model, timestamp, verified,
                          stage_results_json, retry_count, total_cost
                   FROM runs ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "spec_id": r[1],
                    "model": r[2],
                    "timestamp": r[3],
                    "verified": bool(r[4]),
                    "stage_results": json.loads(r[5]),
                    "retry_count": r[6],
                    "total_cost": r[7],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_run_count(self) -> int:
        """Total number of recorded runs."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
            return row[0]
        finally:
            conn.close()


# --- Module-level convenience functions ---
# These open a fresh connection per call for simple scripting use.


def record_run(
    db_path: str,
    spec_id: str,
    model: str,
    verified: bool,
    stage_results: list[dict[str, Any]],
    retry_count: int,
    total_cost: float,
) -> int:
    """Record a verification run. Convenience wrapper around TrackingDB."""
    db = TrackingDB(db_path)
    return db.record_run(spec_id, model, verified, stage_results, retry_count, total_cost)


def get_pass_rate(db_path: str) -> float:
    """Overall pass rate. Convenience wrapper."""
    return TrackingDB(db_path).get_pass_rate()


def get_pass_rate_by_model(db_path: str, model: str) -> float:
    """Pass rate for a model. Convenience wrapper."""
    return TrackingDB(db_path).get_pass_rate_by_model(model)


def get_pass_rate_by_spec(db_path: str, spec_id: str) -> float:
    """Pass rate for a spec. Convenience wrapper."""
    return TrackingDB(db_path).get_pass_rate_by_spec(spec_id)


def get_recent_runs(db_path: str, limit: int = 10) -> list[dict[str, Any]]:
    """Recent runs. Convenience wrapper."""
    return TrackingDB(db_path).get_recent_runs(limit)


def get_run_count(db_path: str) -> int:
    """Total run count. Convenience wrapper."""
    return TrackingDB(db_path).get_run_count()
