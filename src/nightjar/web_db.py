"""SQLite database layer for Nightjar Verification Canvas.

Stores verification runs, SSE events, and discovered invariants in
``.card/tracking.db``. The schema is append-only — rows are never
updated so the canvas has an immutable audit trail.

Uses Python's stdlib ``sqlite3`` module only (no SQLAlchemy).

Schema:
    runs        — one row per verification run
    events      — SSE events emitted during a run (ordered by seq)
    invariants  — invariants discovered during a run
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL_RUNS = """
CREATE TABLE IF NOT EXISTS canvas_runs (
    run_id      TEXT    PRIMARY KEY,
    spec_id     TEXT    NOT NULL DEFAULT '',
    model       TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'pending',
    verified    INTEGER NOT NULL DEFAULT 0,
    trust_level TEXT    NOT NULL DEFAULT 'UNVERIFIED',
    created_at  REAL    NOT NULL,
    finished_at REAL,
    meta_json   TEXT    NOT NULL DEFAULT '{}'
);
"""

_DDL_EVENTS = """
CREATE TABLE IF NOT EXISTS canvas_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT    NOT NULL REFERENCES canvas_runs(run_id),
    seq         INTEGER NOT NULL DEFAULT 0,
    event_type  TEXT    NOT NULL,
    payload_json TEXT   NOT NULL DEFAULT '{}',
    ts          REAL    NOT NULL
);
"""

_DDL_INVARIANTS = """
CREATE TABLE IF NOT EXISTS canvas_invariants (
    invariant_id TEXT   PRIMARY KEY,
    run_id       TEXT   NOT NULL REFERENCES canvas_runs(run_id),
    tier         TEXT   NOT NULL,
    statement    TEXT   NOT NULL,
    rationale    TEXT   NOT NULL DEFAULT '',
    discovered_at REAL  NOT NULL
);
"""

_DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_canvas_events_run ON canvas_events(run_id, seq)",
    "CREATE INDEX IF NOT EXISTS idx_canvas_runs_spec ON canvas_runs(spec_id)",
    "CREATE INDEX IF NOT EXISTS idx_canvas_invariants_run ON canvas_invariants(run_id)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _db_path_from_config(config: Optional[dict[str, Any]] = None) -> str:
    """Resolve the tracking DB path from config or fall back to default.

    The default is ``.card/tracking.db`` relative to the current working
    directory — matching the location used by the existing TrackingDB class
    in ``tracking.py``.
    """
    if config:
        paths = config.get("paths", {})
        specs = paths.get("specs", ".card/")
        return str(Path(specs) / "tracking.db")
    return ".card/tracking.db"


def init_db(db_path: Optional[str] = None, config: Optional[dict[str, Any]] = None) -> str:
    """Create database tables if they do not exist.

    Args:
        db_path: Explicit path to the SQLite file.  If ``None``, resolved
            from *config* or falls back to ``.card/tracking.db``.
        config: Nightjar config dict (from ``config.load_config``).

    Returns:
        The resolved ``db_path`` string (useful for callers that omit it).
    """
    resolved = db_path or _db_path_from_config(config)
    # Ensure parent directory exists
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(resolved)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(_DDL_RUNS)
        conn.execute(_DDL_EVENTS)
        conn.execute(_DDL_INVARIANTS)
        for idx_sql in _DDL_INDEXES:
            conn.execute(idx_sql)
        conn.commit()
    finally:
        conn.close()

    return resolved


def create_run(
    db_path: str,
    spec_id: str = "",
    model: str = "",
    meta: Optional[dict[str, Any]] = None,
) -> str:
    """Insert a new run record and return its ``run_id``.

    Args:
        db_path: Path to the SQLite file (must already be initialised via
            :func:`init_db`).
        spec_id: The module/card identifier being verified.
        model: LLM model name used for this run.
        meta: Arbitrary extra metadata stored as JSON.

    Returns:
        A new UUID4 ``run_id`` string.
    """
    run_id = str(uuid.uuid4())
    now = time.time()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            INSERT INTO canvas_runs
                (run_id, spec_id, model, status, verified, trust_level,
                 created_at, finished_at, meta_json)
            VALUES (?, ?, ?, 'pending', 0, 'UNVERIFIED', ?, NULL, ?)
            """,
            (run_id, spec_id, model, now, json.dumps(meta or {})),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def get_run(db_path: str, run_id: str) -> Optional[dict[str, Any]]:
    """Return a full run snapshot as a dict, or ``None`` if not found.

    The returned dict includes a ``events`` key with the ordered event log
    and an ``invariants`` key with all invariants discovered during the run.

    Args:
        db_path: Path to the SQLite file.
        run_id: The UUID run identifier.

    Returns:
        A dict with run fields, events list, and invariants list, or
        ``None`` if the *run_id* does not exist.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        row = conn.execute(
            "SELECT * FROM canvas_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None

        run = dict(row)
        run["verified"] = bool(run["verified"])
        run["meta"] = json.loads(run.pop("meta_json", "{}"))

        # Attach event log
        event_rows = conn.execute(
            """
            SELECT event_id, run_id, seq, event_type, payload_json, ts
            FROM canvas_events WHERE run_id = ?
            ORDER BY seq ASC, event_id ASC
            """,
            (run_id,),
        ).fetchall()
        run["events"] = [
            {
                "event_id": r["event_id"],
                "run_id": r["run_id"],
                "seq": r["seq"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]),
                "ts": r["ts"],
            }
            for r in event_rows
        ]

        # Attach invariants
        inv_rows = conn.execute(
            "SELECT * FROM canvas_invariants WHERE run_id = ? ORDER BY discovered_at ASC",
            (run_id,),
        ).fetchall()
        run["invariants"] = [dict(r) for r in inv_rows]

        return run
    finally:
        conn.close()


def store_event(
    db_path: str,
    run_id: str,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
    seq: int = 0,
    ts: Optional[float] = None,
) -> int:
    """Append an event to the event log for a run.

    Args:
        db_path: Path to the SQLite file.
        run_id: The UUID run identifier (must already exist in canvas_runs).
        event_type: One of the :class:`web_events.EventType` values.
        payload: Arbitrary JSON-serialisable event data.
        seq: Sequence number within the run (monotonically increasing).
        ts: Event timestamp; defaults to ``time.time()``.

    Returns:
        The auto-incremented ``event_id``.
    """
    resolved_ts = ts if ts is not None else time.time()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.execute(
            """
            INSERT INTO canvas_events (run_id, seq, event_type, payload_json, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, seq, event_type, json.dumps(payload or {}), resolved_ts),
        )
        conn.commit()
        event_id = cursor.lastrowid
        if event_id is None:
            raise RuntimeError("INSERT into canvas_events did not return a row ID")
        return event_id
    finally:
        conn.close()


def get_events(db_path: str, run_id: str) -> list[dict[str, Any]]:
    """Return the ordered event log for a run.

    Args:
        db_path: Path to the SQLite file.
        run_id: The UUID run identifier.

    Returns:
        List of event dicts ordered by (seq, event_id).  Returns an empty
        list if the run does not exist or has no events.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT event_id, run_id, seq, event_type, payload_json, ts
            FROM canvas_events WHERE run_id = ?
            ORDER BY seq ASC, event_id ASC
            """,
            (run_id,),
        ).fetchall()
        return [
            {
                "event_id": r["event_id"],
                "run_id": r["run_id"],
                "seq": r["seq"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]),
                "ts": r["ts"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def store_invariant(
    db_path: str,
    run_id: str,
    tier: str,
    statement: str,
    rationale: str = "",
    invariant_id: Optional[str] = None,
) -> str:
    """Persist an invariant discovered during a run.

    Args:
        db_path: Path to the SQLite file.
        run_id: The UUID run identifier.
        tier: Invariant tier (``"example"``, ``"property"``, ``"formal"``).
        statement: The invariant statement text.
        rationale: Optional explanation of why this invariant holds.
        invariant_id: Explicit ID; generated as UUID4 if not provided.

    Returns:
        The ``invariant_id`` used.
    """
    iid = invariant_id or str(uuid.uuid4())
    now = time.time()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            INSERT INTO canvas_invariants
                (invariant_id, run_id, tier, statement, rationale, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (iid, run_id, tier, statement, rationale, now),
        )
        conn.commit()
    finally:
        conn.close()
    return iid


def update_run_status(
    db_path: str,
    run_id: str,
    status: str,
    verified: bool = False,
    trust_level: str = "UNVERIFIED",
) -> None:
    """Update a run's status fields when it finishes.

    Args:
        db_path: Path to the SQLite file.
        run_id: The UUID run identifier.
        status: New status string (e.g. ``"complete"``, ``"failed"``).
        verified: Whether the full pipeline verified the module.
        trust_level: Graduated trust label (e.g. ``"FORMALLY_VERIFIED"``).
    """
    now = time.time()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            UPDATE canvas_runs
            SET status = ?, verified = ?, trust_level = ?, finished_at = ?
            WHERE run_id = ?
            """,
            (status, int(verified), trust_level, now, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_trust_score(db_path: str, spec_id: str) -> dict[str, Any]:
    """Compute the current trust score for a spec.

    Scans the last 10 canvas runs for the given *spec_id* and derives:

    - ``pass_rate``  — fraction of runs that verified successfully
    - ``trust_level``— the trust level of the most recent completed run
    - ``run_count``  — total number of recorded runs for this spec

    Args:
        db_path: Path to the SQLite file.
        spec_id: The module/card identifier.

    Returns:
        A dict with keys: ``spec_id``, ``pass_rate``, ``trust_level``,
        ``run_count``.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT verified, trust_level
            FROM canvas_runs
            WHERE spec_id = ? AND status = 'complete'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (spec_id,),
        ).fetchall()

        total = len(rows)
        passed = sum(1 for r in rows if r["verified"])
        pass_rate = passed / total if total > 0 else 0.0
        latest_trust = rows[0]["trust_level"] if rows else "UNVERIFIED"

        return {
            "spec_id": spec_id,
            "pass_rate": pass_rate,
            "trust_level": latest_trust,
            "run_count": total,
        }
    finally:
        conn.close()
