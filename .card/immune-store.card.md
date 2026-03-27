---
card-version: "1.0"
id: immune_store
title: Immune System - Trace Store
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "All insert_* methods append new rows and never update or delete existing rows — the store is strictly append-only for all six tables"
    rationale: "Append-only semantics are the audit trail guarantee: existing observations must never be retroactively modified or erased"
  - id: INV-02
    tier: property
    statement: "insert_type_trace, insert_value_trace, insert_api_trace, insert_error_trace, insert_candidate, and insert_verified_invariant each return the SQLite lastrowid of the newly inserted row"
    rationale: "Callers need the row ID for cross-referencing and status updates; the return value must reflect the actual inserted row"
  - id: INV-03
    tier: property
    statement: "update_candidate_status is the only mutation method on the store — it updates the 'status' column of invariant_candidates; no other column is modified by any method"
    rationale: "Status transitions (candidate -> verified -> applied) are the only legitimate mutation; all other data is immutable after insert"
  - id: INV-04
    tier: property
    statement: "TraceStore uses thread-local connections (threading.local) — each thread gets its own sqlite3.Connection; no connection is shared across threads"
    rationale: "sqlite3 connections are not thread-safe; thread-local storage prevents concurrent access errors without requiring a connection pool"
  - id: INV-05
    tier: property
    statement: "get_type_traces, get_value_traces, get_api_traces, get_error_traces, get_candidates, and get_verified_invariants all return results ordered by ascending primary key (id)"
    rationale: "Monotonically increasing id order preserves insertion order, ensuring reproducible query results for mining pipelines that process traces sequentially"
  - id: INV-06
    tier: example
    statement: "The database schema includes exactly six tables: type_traces, value_traces, api_traces, error_traces, invariant_candidates, verified_invariants — all created with IF NOT EXISTS on initialization"
    rationale: "Schema completeness at init time ensures no missing-table errors at runtime; IF NOT EXISTS makes initialization idempotent"
---

## Intent

SQLite-backed append-only storage for all immune system trace types (type, value, API, error)
and the invariant lifecycle (candidate -> verified -> applied).

Thread-safe via thread-local connections (one connection per thread). WAL journal mode
is enabled for concurrent read performance. The store never deletes or overwrites data —
every insert adds a new row, preserving the full audit trail.

References:
- [REF-C05] Dynamic Invariant Mining — trace storage requirements
- [REF-T12] MonkeyType — type trace storage pattern (SQLite)
- [REF-T15] OpenTelemetry — API trace format
- [REF-P17] MINES — API invariant mining data model

## Acceptance Criteria

- [ ] `TraceStore.__init__(db_path)` creates all six tables if they do not exist (idempotent)
- [ ] WAL journal mode and foreign keys are enabled on every new connection
- [ ] Each `insert_*` method commits immediately and returns `cursor.lastrowid`
- [ ] `insert_value_traces_bulk` inserts multiple value traces in a single `executemany` transaction
- [ ] `update_candidate_status` updates only the `status` column of `invariant_candidates`; no other mutation methods exist
- [ ] All `get_*` methods support optional keyword filters and return results ordered by `id ASC`
- [ ] `get_trace_counts()` returns a dict with counts for all four trace tables
- [ ] `get_candidate_counts_by_status()` groups candidates by `InvariantStatus` enum value
- [ ] `close()` closes the thread-local connection and sets it to None
- [ ] `list_tables()` returns the names of all tables in the database

## Functional Requirements

1. **Schema** — six tables initialized with `CREATE TABLE IF NOT EXISTS`:
   - `type_traces(id, module, function, arg_name, observed_type, timestamp)`
   - `value_traces(id, function, variable, value_repr, value_type, timestamp)`
   - `api_traces(id, method, url, status_code, request_shape, response_shape, duration_ms, trace_id, timestamp)`
   - `error_traces(id, exception_class, message_template, stack_fingerprint, function, module, input_shape, timestamp)`
   - `invariant_candidates(id, function, expression, kind, source, confidence, observation_count, status, timestamp)`
   - `verified_invariants(id, function, expression, kind, verification_method, card_spec_id, timestamp)`
2. **Indexes** — created for high-cardinality query fields: function, module, url, method, stack_fingerprint, status
3. **Thread-local connections** — `_get_conn()` uses `threading.local()` to return one `sqlite3.Connection` per thread; WAL mode and foreign keys set on new connections
4. **insert_type_trace(TypeTrace)** — inserts one row; returns `lastrowid`
5. **insert_value_trace(ValueTrace)** — inserts one row; returns `lastrowid`
6. **insert_value_traces_bulk(list[ValueTrace])** — bulk insert via `executemany`; no return value
7. **insert_api_trace(ApiTrace)** — inserts one row; returns `lastrowid`
8. **insert_error_trace(ErrorTrace)** — inserts one row; returns `lastrowid`
9. **insert_candidate(InvariantCandidate)** — inserts one row; returns `lastrowid`
10. **update_candidate_status(id, InvariantStatus)** — updates `status` column only
11. **insert_verified_invariant(VerifiedInvariant)** — inserts one row; returns `lastrowid`
12. **get_type_traces(function, module)** — optional filters; ORDER BY id
13. **get_value_traces(function)** — optional filter; ORDER BY id
14. **get_api_traces(url, method)** — optional filters; ORDER BY id
15. **get_error_traces(function, fingerprint)** — optional filters; ORDER BY id
16. **get_candidates(function, status)** — optional filters; ORDER BY id
17. **get_verified_invariants(function, verification_method)** — optional filters; ORDER BY id
18. **get_trace_counts()** — returns `{"type_traces": N, "value_traces": N, "api_traces": N, "error_traces": N}`
19. **get_candidate_counts_by_status()** — returns `{InvariantStatus: count}` dict
