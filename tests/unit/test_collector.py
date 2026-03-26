"""Tests for MonkeyType-style type trace collection.

Validates runtime type collection using sys.setprofile, storage
integration, and type signature extraction.

References:
- [REF-T12] MonkeyType — runtime type collection pattern
- [REF-C05] Dynamic Invariant Mining — type trace as input
"""

import pytest

from immune.collector import TypeCollector, CallTrace
from immune.types import TypeTrace


# ---------------------------------------------------------------------------
# Helper functions to trace
# ---------------------------------------------------------------------------

def add(a: int, b: int) -> int:
    return a + b


def greet(name: str) -> str:
    return f"Hello, {name}!"


def divide(a: float, b: float) -> float:
    return a / b


def no_return(x: int) -> None:
    _ = x + 1


def multi_type(x):
    """Accepts different types."""
    return str(x)


# ---------------------------------------------------------------------------
# Test: TypeCollector construction
# ---------------------------------------------------------------------------

class TestTypeCollectorConstruction:
    def test_create_collector(self):
        tc = TypeCollector()
        assert tc is not None

    def test_starts_with_no_traces(self):
        tc = TypeCollector()
        assert tc.trace_count == 0

    def test_starts_with_no_call_traces(self):
        tc = TypeCollector()
        assert tc.get_call_traces("nonexistent") == []


# ---------------------------------------------------------------------------
# Test: Tracing function calls
# ---------------------------------------------------------------------------

class TestTracing:
    def test_trace_records_call(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        assert tc.trace_count > 0

    def test_trace_multiple_calls(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
            add(3, 4)
            greet("world")
        assert tc.trace_count >= 3

    def test_trace_restores_profile(self):
        """sys.setprofile should be restored after context manager."""
        import sys
        old_profile = sys.getprofile()
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        assert sys.getprofile() == old_profile


# ---------------------------------------------------------------------------
# Test: CallTrace data model
# ---------------------------------------------------------------------------

class TestCallTrace:
    def test_call_trace_has_fields(self):
        ct = CallTrace(
            module="test",
            function="add",
            arg_types={"a": "int", "b": "int"},
            return_type="int",
        )
        assert ct.module == "test"
        assert ct.function == "add"
        assert ct.arg_types == {"a": "int", "b": "int"}
        assert ct.return_type == "int"


# ---------------------------------------------------------------------------
# Test: Type discovery
# ---------------------------------------------------------------------------

class TestTypeDiscovery:
    def test_discovers_int_args(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        traces = tc.get_call_traces("add")
        assert len(traces) >= 1
        trace = traces[0]
        assert trace.arg_types.get("a") == "int"
        assert trace.arg_types.get("b") == "int"

    def test_discovers_return_type(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        traces = tc.get_call_traces("add")
        assert traces[0].return_type == "int"

    def test_discovers_str_types(self):
        tc = TypeCollector()
        with tc.trace():
            greet("world")
        traces = tc.get_call_traces("greet")
        assert len(traces) >= 1
        assert traces[0].arg_types.get("name") == "str"
        assert traces[0].return_type == "str"

    def test_discovers_float_types(self):
        tc = TypeCollector()
        with tc.trace():
            divide(10.0, 3.0)
        traces = tc.get_call_traces("divide")
        assert len(traces) >= 1
        assert traces[0].arg_types.get("a") == "float"

    def test_discovers_none_return(self):
        tc = TypeCollector()
        with tc.trace():
            no_return(5)
        traces = tc.get_call_traces("no_return")
        assert len(traces) >= 1
        assert traces[0].return_type == "NoneType"


# ---------------------------------------------------------------------------
# Test: Export as TypeTrace
# ---------------------------------------------------------------------------

class TestExportTypeTraces:
    def test_export_produces_type_traces(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        type_traces = tc.export_type_traces("add")
        assert len(type_traces) > 0
        for tt in type_traces:
            assert isinstance(tt, TypeTrace)

    def test_export_includes_args_and_return(self):
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        type_traces = tc.export_type_traces("add")
        arg_names = [tt.arg_name for tt in type_traces]
        assert "a" in arg_names
        assert "b" in arg_names
        assert "return" in arg_names

    def test_export_has_correct_types(self):
        tc = TypeCollector()
        with tc.trace():
            greet("test")
        type_traces = tc.export_type_traces("greet")
        name_traces = [tt for tt in type_traces if tt.arg_name == "name"]
        assert len(name_traces) == 1
        assert name_traces[0].observed_type == "str"


# ---------------------------------------------------------------------------
# Test: Function filtering
# ---------------------------------------------------------------------------

class TestFunctionFiltering:
    def test_include_modules_filter(self):
        tc = TypeCollector(include_modules=[__name__])
        with tc.trace():
            add(1, 2)
        assert tc.get_call_traces("add") != []

    def test_excludes_stdlib(self):
        """Should not trace stdlib functions like len, print, etc."""
        tc = TypeCollector()
        with tc.trace():
            add(1, 2)
        assert tc.get_call_traces("len") == []
        assert tc.get_call_traces("print") == []


# ---------------------------------------------------------------------------
# Test: Multiple observations consolidation
# ---------------------------------------------------------------------------

class TestConsolidation:
    def test_get_unique_signatures(self):
        """Multiple calls with same types should consolidate."""
        tc = TypeCollector()
        with tc.trace():
            for i in range(10):
                add(i, i + 1)
        sigs = tc.get_unique_signatures("add")
        # All calls have same types, should consolidate to 1
        assert len(sigs) == 1
        assert sigs[0].arg_types == {"a": "int", "b": "int"}
        assert sigs[0].return_type == "int"
