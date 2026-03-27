"""Immune system trace storage — SQLite backend.

Append-only storage for all trace types (type, value, API, error) and
invariant lifecycle (candidate → verified → applied).

References:
- [REF-C05] Dynamic Invariant Mining — trace storage requirements
- [REF-T12] MonkeyType — type trace storage pattern (SQLite)
- [REF-T15] OpenTelemetry — API trace format
- [REF-P17] MINES — API invariant mining data model
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import Optional

from immune.types import (
    ApiTrace,
    ErrorTrace,
    InvariantCandidate,
    InvariantStatus,
    TypeTrace,
    ValueTrace,
    VerifiedInvariant,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS type_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    function TEXT NOT NULL,
    arg_name TEXT NOT NULL,
    observed_type TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    function TEXT NOT NULL,
    variable TEXT NOT NULL,
    value_repr TEXT NOT NULL,
    value_type TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    request_shape TEXT NOT NULL DEFAULT '',
    response_shape TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    trace_id TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exception_class TEXT NOT NULL,
    message_template TEXT NOT NULL,
    stack_fingerprint TEXT NOT NULL,
    function TEXT NOT NULL DEFAULT '',
    module TEXT NOT NULL DEFAULT '',
    input_shape TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invariant_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    function TEXT NOT NULL,
    expression TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    observation_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'candidate',
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verified_invariants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    function TEXT NOT NULL,
    expression TEXT NOT NULL,
    kind TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    card_spec_id TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_type_traces_function ON type_traces(function);
CREATE INDEX IF NOT EXISTS idx_type_traces_module ON type_traces(module);
CREATE INDEX IF NOT EXISTS idx_value_traces_function ON value_traces(function);
CREATE INDEX IF NOT EXISTS idx_api_traces_url ON api_traces(url);
CREATE INDEX IF NOT EXISTS idx_api_traces_method ON api_traces(method);
CREATE INDEX IF NOT EXISTS idx_error_traces_fingerprint ON error_traces(stack_fingerprint);
CREATE INDEX IF NOT EXISTS idx_error_traces_function ON error_traces(function);
CREATE INDEX IF NOT EXISTS idx_candidates_function ON invariant_candidates(function);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON invariant_candidates(status);
CREATE INDEX IF NOT EXISTS idx_verified_function ON verified_invariants(function);
"""


def _ts_to_str(dt: datetime) -> str:
    """Convert datetime to ISO-format string for storage."""
    return dt.isoformat()


def _str_to_ts(s: str) -> datetime:
    """Convert ISO-format string back to datetime."""
    return datetime.fromisoformat(s)


class TraceStore:
    """SQLite-backed storage for immune system traces and invariants.

    Thread-safe. Append-only for audit trail compliance.

    Usage:
        store = TraceStore("traces.db")
        store.insert_type_trace(TypeTrace(...))
        traces = store.get_type_traces(function="login")
        store.close()
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def list_tables(self) -> list[str]:
        """List all tables in the database."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row["name"] for row in cursor.fetchall()]

    # ----- Type traces -----

    def insert_type_trace(self, trace: TypeTrace) -> int:
        """Insert a type trace. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO type_traces (module, function, arg_name, observed_type, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (trace.module, trace.function, trace.arg_name,
             trace.observed_type, _ts_to_str(trace.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def get_type_traces(
        self,
        function: Optional[str] = None,
        module: Optional[str] = None,
    ) -> list[TypeTrace]:
        """Retrieve type traces with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM type_traces WHERE 1=1"
        params: list = []
        if function is not None:
            query += " AND function = ?"
            params.append(function)
        if module is not None:
            query += " AND module = ?"
            params.append(module)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            TypeTrace(
                id=r["id"], module=r["module"], function=r["function"],
                arg_name=r["arg_name"], observed_type=r["observed_type"],
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- Value traces -----

    def insert_value_trace(self, trace: ValueTrace) -> int:
        """Insert a value trace. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO value_traces (function, variable, value_repr, value_type, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (trace.function, trace.variable, trace.value_repr,
             trace.value_type, _ts_to_str(trace.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def insert_value_traces_bulk(self, traces: list[ValueTrace]) -> None:
        """Bulk insert value traces for performance."""
        conn = self._get_conn()
        conn.executemany(
            "INSERT INTO value_traces (function, variable, value_repr, value_type, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (t.function, t.variable, t.value_repr,
                 t.value_type, _ts_to_str(t.timestamp))
                for t in traces
            ],
        )
        conn.commit()

    def get_value_traces(
        self, function: Optional[str] = None,
    ) -> list[ValueTrace]:
        """Retrieve value traces with optional function filter."""
        conn = self._get_conn()
        query = "SELECT * FROM value_traces WHERE 1=1"
        params: list = []
        if function is not None:
            query += " AND function = ?"
            params.append(function)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            ValueTrace(
                id=r["id"], function=r["function"], variable=r["variable"],
                value_repr=r["value_repr"], value_type=r["value_type"],
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- API traces -----

    def insert_api_trace(self, trace: ApiTrace) -> int:
        """Insert an API trace. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO api_traces "
            "(method, url, status_code, request_shape, response_shape, "
            "duration_ms, trace_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (trace.method, trace.url, trace.status_code,
             trace.request_shape, trace.response_shape,
             trace.duration_ms, trace.trace_id,
             _ts_to_str(trace.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def get_api_traces(
        self,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ) -> list[ApiTrace]:
        """Retrieve API traces with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM api_traces WHERE 1=1"
        params: list = []
        if url is not None:
            query += " AND url = ?"
            params.append(url)
        if method is not None:
            query += " AND method = ?"
            params.append(method)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            ApiTrace(
                id=r["id"], method=r["method"], url=r["url"],
                status_code=r["status_code"],
                request_shape=r["request_shape"],
                response_shape=r["response_shape"],
                duration_ms=r["duration_ms"], trace_id=r["trace_id"],
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- Error traces -----

    def insert_error_trace(self, trace: ErrorTrace) -> int:
        """Insert an error trace. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO error_traces "
            "(exception_class, message_template, stack_fingerprint, "
            "function, module, input_shape, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trace.exception_class, trace.message_template,
             trace.stack_fingerprint, trace.function,
             trace.module, trace.input_shape,
             _ts_to_str(trace.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def get_error_traces(
        self,
        function: Optional[str] = None,
        fingerprint: Optional[str] = None,
    ) -> list[ErrorTrace]:
        """Retrieve error traces with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM error_traces WHERE 1=1"
        params: list = []
        if function is not None:
            query += " AND function = ?"
            params.append(function)
        if fingerprint is not None:
            query += " AND stack_fingerprint = ?"
            params.append(fingerprint)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            ErrorTrace(
                id=r["id"],
                exception_class=r["exception_class"],
                message_template=r["message_template"],
                stack_fingerprint=r["stack_fingerprint"],
                function=r["function"], module=r["module"],
                input_shape=r["input_shape"],
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- Invariant candidates -----

    def insert_candidate(self, candidate: InvariantCandidate) -> int:
        """Insert an invariant candidate. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO invariant_candidates "
            "(function, expression, kind, source, confidence, "
            "observation_count, status, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (candidate.function, candidate.expression, candidate.kind,
             candidate.source, candidate.confidence,
             candidate.observation_count, candidate.status.value,
             _ts_to_str(candidate.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def update_candidate_status(
        self, candidate_id: int, status: InvariantStatus
    ) -> None:
        """Update the status of an invariant candidate."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE invariant_candidates SET status = ? WHERE id = ?",
            (status.value, candidate_id),
        )
        conn.commit()

    def get_candidates(
        self,
        function: Optional[str] = None,
        status: Optional[InvariantStatus] = None,
    ) -> list[InvariantCandidate]:
        """Retrieve invariant candidates with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM invariant_candidates WHERE 1=1"
        params: list = []
        if function is not None:
            query += " AND function = ?"
            params.append(function)
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            InvariantCandidate(
                id=r["id"], function=r["function"],
                expression=r["expression"], kind=r["kind"],
                source=r["source"], confidence=r["confidence"],
                observation_count=r["observation_count"],
                status=InvariantStatus(r["status"]),
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- Verified invariants -----

    def insert_verified_invariant(self, inv: VerifiedInvariant) -> int:
        """Insert a verified invariant. Returns the row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO verified_invariants "
            "(function, expression, kind, verification_method, "
            "card_spec_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (inv.function, inv.expression, inv.kind,
             inv.verification_method, inv.card_spec_id,
             _ts_to_str(inv.timestamp)),
        )
        conn.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("INSERT did not produce a row ID")
        return row_id

    def get_verified_invariants(
        self,
        function: Optional[str] = None,
        verification_method: Optional[str] = None,
    ) -> list[VerifiedInvariant]:
        """Retrieve verified invariants with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM verified_invariants WHERE 1=1"
        params: list = []
        if function is not None:
            query += " AND function = ?"
            params.append(function)
        if verification_method is not None:
            query += " AND verification_method = ?"
            params.append(verification_method)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()
        return [
            VerifiedInvariant(
                id=r["id"], function=r["function"],
                expression=r["expression"], kind=r["kind"],
                verification_method=r["verification_method"],
                card_spec_id=r["card_spec_id"],
                timestamp=_str_to_ts(r["timestamp"]),
            )
            for r in rows
        ]

    # ----- Stats -----

    def get_trace_counts(self) -> dict[str, int]:
        """Get counts for each trace table."""
        conn = self._get_conn()
        counts = {}
        for table in ["type_traces", "value_traces", "api_traces",
                       "error_traces"]:
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            counts[table] = row["c"]
        return counts

    def get_candidate_counts_by_status(self) -> dict[InvariantStatus, int]:
        """Get counts of candidates grouped by status."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT status, COUNT(*) as c FROM invariant_candidates "
            "GROUP BY status"
        ).fetchall()
        return {InvariantStatus(r["status"]): r["c"] for r in rows}
