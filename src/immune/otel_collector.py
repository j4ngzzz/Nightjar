"""OpenTelemetry API trace collection for MINES-style invariant mining.

Collects HTTP span data (method, URL, status, request/response shapes)
for API invariant mining. Provides URL pattern normalization for grouping
similar endpoints.

References:
- [REF-T15] OpenTelemetry — distributed tracing framework
- [REF-P17] MINES (ICSE 2026) — inferring web API invariants from HTTP logs
"""

from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from immune.types import ApiTrace

# Patterns for URL normalization
_NUMERIC_ID = re.compile(r"/\d+(?=/|$)")
_UUID_PATTERN = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)"
)


def extract_json_shape(data: Any) -> Any:
    """Extract the type-shape of a JSON-like data structure.

    Recursively maps values to their type names, preserving structure.
    Lists are represented by the shape of their first element.

    Args:
        data: A JSON-like Python object (dict, list, str, int, etc.)

    Returns:
        The shape as a nested structure of type names.

    Examples:
        >>> extract_json_shape({"name": "John", "age": 30})
        {"name": "str", "age": "int"}
        >>> extract_json_shape([1, 2, 3])
        ["int"]
    """
    if isinstance(data, dict):
        return {k: extract_json_shape(v) for k, v in data.items()}
    elif isinstance(data, list):
        if not data:
            return []
        return [extract_json_shape(data[0])]
    else:
        return type(data).__name__


@dataclass
class HttpSpan:
    """An HTTP request/response span.

    Attributes:
        method: HTTP method (GET, POST, etc.).
        url: Request URL path.
        status_code: HTTP response status code.
        request_body: Parsed request body (dict/list/None).
        response_body: Parsed response body (dict/list/None).
        duration_ms: Request duration in milliseconds.
        trace_id: OpenTelemetry trace ID.
    """
    method: str
    url: str
    status_code: int
    request_body: Any = None
    response_body: Any = None
    duration_ms: int = 0
    trace_id: str = ""


class OTelCollector:
    """Collects and organizes HTTP spans for MINES-style mining.

    Stores HTTP request/response spans, normalizes URLs to patterns,
    and exports data as immune system ApiTrace objects.

    Usage:
        collector = OTelCollector()
        collector.record_span(HttpSpan(
            method="POST", url="/api/users",
            status_code=201, request_body={"name": "test"},
            response_body={"id": 1},
        ))
        traces = collector.export_api_traces()

    References:
    - [REF-T15] OpenTelemetry
    - [REF-P17] MINES paper — API invariant mining
    """

    def __init__(self, max_spans: int = 50000) -> None:
        self._spans: list[HttpSpan] = []
        self._max_spans = max_spans
        self._lock = threading.Lock()

    @property
    def span_count(self) -> int:
        """Number of recorded spans."""
        return len(self._spans)

    def record_span(self, span: HttpSpan) -> None:
        """Record an HTTP span."""
        with self._lock:
            if len(self._spans) < self._max_spans:
                self._spans.append(span)

    def get_spans(
        self,
        url: Optional[str] = None,
        method: Optional[str] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
    ) -> list[HttpSpan]:
        """Retrieve spans with optional filters.

        Args:
            url: Filter by exact URL.
            method: Filter by HTTP method.
            status_min: Minimum status code (inclusive).
            status_max: Maximum status code (inclusive).
        """
        result = list(self._spans)
        if url is not None:
            result = [s for s in result if s.url == url]
        if method is not None:
            result = [s for s in result if s.method == method]
        if status_min is not None:
            result = [s for s in result if s.status_code >= status_min]
        if status_max is not None:
            result = [s for s in result if s.status_code <= status_max]
        return result

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize a URL by replacing IDs with placeholders.

        Replaces numeric path segments with {id} and UUIDs with {uuid}
        for grouping similar API endpoints.

        Args:
            url: The raw URL path.

        Returns:
            Normalized URL pattern.
        """
        result = _UUID_PATTERN.sub("/{uuid}", url)
        result = _NUMERIC_ID.sub("/{id}", result)
        return result

    def get_url_patterns(self) -> list[str]:
        """Get unique normalized URL patterns from recorded spans."""
        patterns: set[str] = set()
        for span in self._spans:
            patterns.add(self.normalize_url(span.url))
        return sorted(patterns)

    def export_api_traces(self) -> list[ApiTrace]:
        """Export recorded spans as immune system ApiTrace objects.

        Extracts JSON shapes from request/response bodies and serializes
        them for storage.

        Returns:
            List of ApiTrace objects.
        """
        traces: list[ApiTrace] = []
        for span in self._spans:
            request_shape = ""
            if span.request_body is not None:
                shape = extract_json_shape(span.request_body)
                request_shape = json.dumps(shape, separators=(",", ":"))

            response_shape = ""
            if span.response_body is not None:
                shape = extract_json_shape(span.response_body)
                response_shape = json.dumps(shape, separators=(",", ":"))

            traces.append(ApiTrace(
                method=span.method,
                url=span.url,
                status_code=span.status_code,
                request_shape=request_shape,
                response_shape=response_shape,
                duration_ms=span.duration_ms,
                trace_id=span.trace_id,
            ))
        return traces

    def clear(self) -> None:
        """Clear all recorded spans."""
        with self._lock:
            self._spans.clear()
