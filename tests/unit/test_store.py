"""Tests for the immune system trace storage (SQLite).

Validates CRUD operations for all trace types and invariant lifecycle.

References:
- [REF-C05] Dynamic Invariant Mining — trace storage requirements
- [REF-T12] MonkeyType — type trace storage
- [REF-T15] OpenTelemetry — API trace storage
"""

import os
import tempfile
from datetime import datetime

import pytest

from immune.store import TraceStore
from immune.types import (
    ApiTrace,
    ErrorTrace,
    InvariantCandidate,
    InvariantStatus,
    TypeTrace,
    ValueTrace,
    VerifiedInvariant,
)


@pytest.fixture
def store(tmp_path):
    """Create a TraceStore with a temporary database."""
    db_path = str(tmp_path / "test_traces.db")
    s = TraceStore(db_path)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Test: Store creation and schema
# ---------------------------------------------------------------------------

class TestStoreCreation:
    def test_creates_database_file(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        s = TraceStore(db_path)
        assert os.path.exists(db_path)
        s.close()

    def test_creates_all_tables(self, store):
        tables = store.list_tables()
        assert "type_traces" in tables
        assert "value_traces" in tables
        assert "api_traces" in tables
        assert "error_traces" in tables
        assert "invariant_candidates" in tables
        assert "verified_invariants" in tables

    def test_idempotent_creation(self, tmp_path):
        """Creating store twice on same DB should not error."""
        db_path = str(tmp_path / "idem.db")
        s1 = TraceStore(db_path)
        s1.close()
        s2 = TraceStore(db_path)
        tables = s2.list_tables()
        assert len(tables) >= 6
        s2.close()


# ---------------------------------------------------------------------------
# Test: Type traces CRUD
# ---------------------------------------------------------------------------

class TestTypeTraces:
    def test_insert_and_retrieve(self, store):
        trace = TypeTrace(
            module="myapp.auth",
            function="login",
            arg_name="username",
            observed_type="str",
        )
        trace_id = store.insert_type_trace(trace)
        assert trace_id > 0

        retrieved = store.get_type_traces(function="login")
        assert len(retrieved) == 1
        assert retrieved[0].module == "myapp.auth"
        assert retrieved[0].arg_name == "username"
        assert retrieved[0].observed_type == "str"

    def test_insert_multiple(self, store):
        for arg in ["username", "password", "return"]:
            store.insert_type_trace(TypeTrace(
                module="myapp.auth",
                function="login",
                arg_name=arg,
                observed_type="str",
            ))
        traces = store.get_type_traces(function="login")
        assert len(traces) == 3

    def test_filter_by_module(self, store):
        store.insert_type_trace(TypeTrace(
            module="myapp.auth", function="login",
            arg_name="x", observed_type="str",
        ))
        store.insert_type_trace(TypeTrace(
            module="myapp.payment", function="charge",
            arg_name="amount", observed_type="float",
        ))
        auth_traces = store.get_type_traces(module="myapp.auth")
        assert len(auth_traces) == 1
        assert auth_traces[0].function == "login"


# ---------------------------------------------------------------------------
# Test: Value traces CRUD
# ---------------------------------------------------------------------------

class TestValueTraces:
    def test_insert_and_retrieve(self, store):
        trace = ValueTrace(
            function="abs_val",
            variable="x",
            value_repr="42",
            value_type="int",
        )
        trace_id = store.insert_value_trace(trace)
        assert trace_id > 0

        retrieved = store.get_value_traces(function="abs_val")
        assert len(retrieved) == 1
        assert retrieved[0].variable == "x"
        assert retrieved[0].value_repr == "42"

    def test_bulk_insert(self, store):
        traces = [
            ValueTrace(function="f", variable="x",
                       value_repr=str(i), value_type="int")
            for i in range(100)
        ]
        store.insert_value_traces_bulk(traces)
        retrieved = store.get_value_traces(function="f")
        assert len(retrieved) == 100


# ---------------------------------------------------------------------------
# Test: API traces CRUD
# ---------------------------------------------------------------------------

class TestApiTraces:
    def test_insert_and_retrieve(self, store):
        trace = ApiTrace(
            method="POST",
            url="/api/v1/users",
            status_code=201,
            request_shape='{"name": "str", "email": "str"}',
            response_shape='{"id": "int", "name": "str"}',
            duration_ms=150,
            trace_id="abc123",
        )
        trace_id = store.insert_api_trace(trace)
        assert trace_id > 0

        retrieved = store.get_api_traces(url="/api/v1/users")
        assert len(retrieved) == 1
        assert retrieved[0].method == "POST"
        assert retrieved[0].status_code == 201

    def test_filter_by_method(self, store):
        store.insert_api_trace(ApiTrace(
            method="GET", url="/api/users", status_code=200,
        ))
        store.insert_api_trace(ApiTrace(
            method="POST", url="/api/users", status_code=201,
        ))
        gets = store.get_api_traces(method="GET")
        assert len(gets) == 1
        assert gets[0].url == "/api/users"


# ---------------------------------------------------------------------------
# Test: Error traces CRUD
# ---------------------------------------------------------------------------

class TestErrorTraces:
    def test_insert_and_retrieve(self, store):
        trace = ErrorTrace(
            exception_class="ValueError",
            message_template="invalid literal for int() with base 10: '{}'",
            stack_fingerprint="ValueError:int:parse",
            function="parse_id",
            module="myapp.utils",
        )
        trace_id = store.insert_error_trace(trace)
        assert trace_id > 0

        retrieved = store.get_error_traces(function="parse_id")
        assert len(retrieved) == 1
        assert retrieved[0].exception_class == "ValueError"
        assert retrieved[0].stack_fingerprint == "ValueError:int:parse"

    def test_filter_by_fingerprint(self, store):
        store.insert_error_trace(ErrorTrace(
            exception_class="ValueError",
            message_template="bad value",
            stack_fingerprint="fp1",
        ))
        store.insert_error_trace(ErrorTrace(
            exception_class="TypeError",
            message_template="wrong type",
            stack_fingerprint="fp2",
        ))
        fp1_traces = store.get_error_traces(fingerprint="fp1")
        assert len(fp1_traces) == 1
        assert fp1_traces[0].exception_class == "ValueError"


# ---------------------------------------------------------------------------
# Test: Invariant candidates CRUD
# ---------------------------------------------------------------------------

class TestInvariantCandidates:
    def test_insert_and_retrieve(self, store):
        candidate = InvariantCandidate(
            function="abs_val",
            expression="return >= 0",
            kind="bound",
            source="daikon",
            confidence=0.95,
            observation_count=100,
        )
        cid = store.insert_candidate(candidate)
        assert cid > 0

        retrieved = store.get_candidates(function="abs_val")
        assert len(retrieved) == 1
        assert retrieved[0].expression == "return >= 0"
        assert retrieved[0].confidence == 0.95

    def test_update_status(self, store):
        cid = store.insert_candidate(InvariantCandidate(
            function="f", expression="x > 0",
            kind="bound", source="daikon",
        ))
        store.update_candidate_status(cid, InvariantStatus.VERIFIED)
        retrieved = store.get_candidates(function="f")
        assert retrieved[0].status == InvariantStatus.VERIFIED

    def test_filter_by_status(self, store):
        store.insert_candidate(InvariantCandidate(
            function="f", expression="x > 0",
            kind="bound", source="daikon",
            status=InvariantStatus.CANDIDATE,
        ))
        store.insert_candidate(InvariantCandidate(
            function="f", expression="x is not None",
            kind="nullness", source="daikon",
            status=InvariantStatus.VERIFIED,
        ))
        candidates = store.get_candidates(
            function="f", status=InvariantStatus.CANDIDATE
        )
        assert len(candidates) == 1
        assert candidates[0].expression == "x > 0"


# ---------------------------------------------------------------------------
# Test: Verified invariants CRUD
# ---------------------------------------------------------------------------

class TestVerifiedInvariants:
    def test_insert_and_retrieve(self, store):
        inv = VerifiedInvariant(
            function="abs_val",
            expression="return >= 0",
            kind="bound",
            verification_method="crosshair+hypothesis",
        )
        vid = store.insert_verified_invariant(inv)
        assert vid > 0

        retrieved = store.get_verified_invariants(function="abs_val")
        assert len(retrieved) == 1
        assert retrieved[0].expression == "return >= 0"
        assert retrieved[0].verification_method == "crosshair+hypothesis"

    def test_filter_by_method(self, store):
        store.insert_verified_invariant(VerifiedInvariant(
            function="f", expression="x > 0",
            kind="bound", verification_method="crosshair",
        ))
        store.insert_verified_invariant(VerifiedInvariant(
            function="f", expression="x is not None",
            kind="nullness", verification_method="hypothesis",
        ))
        crosshair_invs = store.get_verified_invariants(
            function="f", verification_method="crosshair"
        )
        assert len(crosshair_invs) == 1


# ---------------------------------------------------------------------------
# Test: Counts and stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_trace_counts(self, store):
        store.insert_type_trace(TypeTrace(
            module="m", function="f", arg_name="x", observed_type="int",
        ))
        store.insert_value_trace(ValueTrace(
            function="f", variable="x", value_repr="1", value_type="int",
        ))
        counts = store.get_trace_counts()
        assert counts["type_traces"] == 1
        assert counts["value_traces"] == 1
        assert counts["api_traces"] == 0

    def test_candidate_count_by_status(self, store):
        store.insert_candidate(InvariantCandidate(
            function="f", expression="a",
            kind="type", source="daikon",
            status=InvariantStatus.CANDIDATE,
        ))
        store.insert_candidate(InvariantCandidate(
            function="f", expression="b",
            kind="type", source="daikon",
            status=InvariantStatus.VERIFIED,
        ))
        counts = store.get_candidate_counts_by_status()
        assert counts[InvariantStatus.CANDIDATE] == 1
        assert counts[InvariantStatus.VERIFIED] == 1
