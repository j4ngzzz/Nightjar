"""Tests for OpenTelemetry API trace collection.

Validates HTTP span capture, shape extraction, and conversion
to immune system ApiTrace format.

References:
- [REF-T15] OpenTelemetry — distributed tracing
- [REF-P17] MINES — API invariant mining from HTTP logs
"""

import pytest

from immune.otel_collector import (
    OTelCollector,
    extract_json_shape,
    HttpSpan,
)
from immune.types import ApiTrace


# ---------------------------------------------------------------------------
# Test: JSON shape extraction
# ---------------------------------------------------------------------------

class TestJsonShapeExtraction:
    def test_simple_object(self):
        data = {"name": "John", "age": 30}
        shape = extract_json_shape(data)
        assert shape == {"name": "str", "age": "int"}

    def test_nested_object(self):
        data = {"user": {"name": "John", "id": 1}}
        shape = extract_json_shape(data)
        assert shape == {"user": {"name": "str", "id": "int"}}

    def test_list_value(self):
        data = {"items": [1, 2, 3]}
        shape = extract_json_shape(data)
        assert shape == {"items": ["int"]}

    def test_empty_list(self):
        data = {"items": []}
        shape = extract_json_shape(data)
        assert shape == {"items": []}

    def test_none_value(self):
        data = {"value": None}
        shape = extract_json_shape(data)
        assert shape == {"value": "NoneType"}

    def test_bool_value(self):
        data = {"active": True}
        shape = extract_json_shape(data)
        assert shape == {"active": "bool"}

    def test_string_input(self):
        shape = extract_json_shape("hello")
        assert shape == "str"

    def test_int_input(self):
        shape = extract_json_shape(42)
        assert shape == "int"

    def test_none_input(self):
        shape = extract_json_shape(None)
        assert shape == "NoneType"


# ---------------------------------------------------------------------------
# Test: HttpSpan data model
# ---------------------------------------------------------------------------

class TestHttpSpan:
    def test_create_span(self):
        span = HttpSpan(
            method="GET",
            url="/api/v1/users",
            status_code=200,
            request_body=None,
            response_body={"users": [{"id": 1}]},
            duration_ms=50,
            trace_id="abc123",
        )
        assert span.method == "GET"
        assert span.url == "/api/v1/users"
        assert span.status_code == 200
        assert span.duration_ms == 50


# ---------------------------------------------------------------------------
# Test: OTelCollector construction
# ---------------------------------------------------------------------------

class TestOTelCollectorConstruction:
    def test_create_collector(self):
        collector = OTelCollector()
        assert collector is not None

    def test_starts_empty(self):
        collector = OTelCollector()
        assert collector.span_count == 0

    def test_get_spans_empty(self):
        collector = OTelCollector()
        assert collector.get_spans() == []


# ---------------------------------------------------------------------------
# Test: Recording spans
# ---------------------------------------------------------------------------

class TestRecordingSpans:
    def test_record_span(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/api/users", status_code=200,
            duration_ms=100,
        ))
        assert collector.span_count == 1

    def test_record_multiple_spans(self):
        collector = OTelCollector()
        for i in range(5):
            collector.record_span(HttpSpan(
                method="GET", url=f"/api/item/{i}", status_code=200,
                duration_ms=50,
            ))
        assert collector.span_count == 5

    def test_get_spans_by_url(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/api/users", status_code=200,
        ))
        collector.record_span(HttpSpan(
            method="POST", url="/api/orders", status_code=201,
        ))
        user_spans = collector.get_spans(url="/api/users")
        assert len(user_spans) == 1
        assert user_spans[0].method == "GET"

    def test_get_spans_by_method(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/api/users", status_code=200,
        ))
        collector.record_span(HttpSpan(
            method="POST", url="/api/users", status_code=201,
        ))
        gets = collector.get_spans(method="GET")
        assert len(gets) == 1

    def test_get_spans_by_status_range(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/a", status_code=200,
        ))
        collector.record_span(HttpSpan(
            method="GET", url="/b", status_code=500,
        ))
        errors = collector.get_spans(status_min=400)
        assert len(errors) == 1
        assert errors[0].status_code == 500


# ---------------------------------------------------------------------------
# Test: Export as ApiTrace
# ---------------------------------------------------------------------------

class TestExportApiTraces:
    def test_export_produces_api_traces(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="POST",
            url="/api/users",
            status_code=201,
            request_body={"name": "test", "email": "t@t.com"},
            response_body={"id": 1, "name": "test"},
            duration_ms=150,
            trace_id="trace-001",
        ))
        traces = collector.export_api_traces()
        assert len(traces) == 1
        t = traces[0]
        assert isinstance(t, ApiTrace)
        assert t.method == "POST"
        assert t.url == "/api/users"
        assert t.status_code == 201
        assert t.duration_ms == 150
        assert t.trace_id == "trace-001"

    def test_export_includes_shapes(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="POST",
            url="/api/items",
            status_code=200,
            request_body={"quantity": 5},
            response_body={"ok": True},
        ))
        traces = collector.export_api_traces()
        assert len(traces) == 1
        # Shapes should be JSON-serialized
        assert "quantity" in traces[0].request_shape
        assert "ok" in traces[0].response_shape

    def test_export_handles_no_body(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/api/health", status_code=200,
        ))
        traces = collector.export_api_traces()
        assert len(traces) == 1
        assert traces[0].request_shape == ""
        assert traces[0].response_shape == ""


# ---------------------------------------------------------------------------
# Test: URL pattern normalization
# ---------------------------------------------------------------------------

class TestUrlPatterns:
    def test_normalize_numeric_ids(self):
        """URLs with numeric IDs should be grouped."""
        collector = OTelCollector()
        patterns = collector.normalize_url("/api/users/123/orders/456")
        assert patterns == "/api/users/{id}/orders/{id}"

    def test_normalize_uuid_ids(self):
        collector = OTelCollector()
        patterns = collector.normalize_url(
            "/api/items/550e8400-e29b-41d4-a716-446655440000"
        )
        assert "{uuid}" in patterns

    def test_get_url_patterns(self):
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="GET", url="/api/users/1", status_code=200,
        ))
        collector.record_span(HttpSpan(
            method="GET", url="/api/users/2", status_code=200,
        ))
        collector.record_span(HttpSpan(
            method="GET", url="/api/users/3", status_code=200,
        ))
        patterns = collector.get_url_patterns()
        assert "/api/users/{id}" in patterns
