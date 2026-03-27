---
card-version: "1.0"
id: immune_otel
title: Immune System - OTel API Trace Collector
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "OTelCollector.span_count never exceeds max_spans — record_span silently drops spans when the buffer is full"
    rationale: "The in-memory buffer is bounded; silent drop on overflow is preferable to OOM crashes in high-traffic services"
  - id: INV-02
    tier: property
    statement: "extract_json_shape preserves the structural keys of a dict but replaces all leaf values with their Python type name string"
    rationale: "MINES-style mining needs the shape (field names + types) not the values; shape extraction must be lossless for structure and lossy only for values"
  - id: INV-03
    tier: property
    statement: "extract_json_shape represents a non-empty list as a single-element list containing the shape of the first element — [shape_of_first]"
    rationale: "API lists are homogeneous collections; capturing the first element's shape is the MINES convention for representing list schemas"
  - id: INV-04
    tier: property
    statement: "normalize_url replaces all UUID path segments with /{uuid} before replacing numeric segments with /{id} — UUID patterns take priority over numeric patterns"
    rationale: "UUIDs contain hyphens and would partially match the numeric pattern; applying UUID substitution first prevents partial corruption of UUID placeholders"
  - id: INV-05
    tier: property
    statement: "export_api_traces produces exactly one ApiTrace per recorded HttpSpan, in the same order spans were recorded"
    rationale: "Trace count must be deterministic; mining pipelines that correlate spans to invariants depend on order-preserving export"
  - id: INV-06
    tier: example
    statement: "get_spans with no filter arguments returns all recorded spans; each filter (url, method, status_min, status_max) narrows results independently"
    rationale: "Filters are conjunctive; each applied independently from the full span list allows flexible querying without complex query logic"
---

## Intent

Collects HTTP request/response spans from OpenTelemetry instrumentation and exports them
as `ApiTrace` objects for MINES-style API invariant mining.

Normalizes URLs (replacing numeric IDs and UUIDs with placeholders) to group similar
endpoints. Extracts JSON body shapes (type-only, not values) for schema invariant mining.
Thread-safe in-memory buffer with a configurable max_spans cap.

References:
- [REF-T15] OpenTelemetry — distributed tracing framework
- [REF-P17] MINES (ICSE 2026) — inferring web API invariants from HTTP logs

## Acceptance Criteria

- [ ] `OTelCollector.record_span(span)` drops the span silently when `span_count >= max_spans`
- [ ] `span_count` property reflects the current number of recorded spans
- [ ] `extract_json_shape(dict)` replaces leaf values with type name strings, preserves keys
- [ ] `extract_json_shape([])` returns `[]`; `extract_json_shape([1, 2, 3])` returns `["int"]`
- [ ] `normalize_url` replaces UUID segments with `/{uuid}` then numeric segments with `/{id}`
- [ ] `get_url_patterns()` returns sorted list of unique normalized URL patterns from all spans
- [ ] `export_api_traces()` returns one `ApiTrace` per span; `request_shape` and `response_shape` are empty strings when body is None
- [ ] `clear()` removes all recorded spans (span_count returns 0 after clear)
- [ ] `record_span` is thread-safe (protected by `threading.Lock`)

## Functional Requirements

1. **extract_json_shape(data)** — recursive: dicts map `{k: extract_json_shape(v)}`; non-empty lists return `[extract_json_shape(data[0])]`; empty lists return `[]`; all other values return `type(data).__name__`
2. **HttpSpan dataclass** — fields: `method: str`, `url: str`, `status_code: int`, `request_body: Any = None`, `response_body: Any = None`, `duration_ms: int = 0`, `trace_id: str = ""`
3. **OTelCollector.__init__(max_spans=50000)** — initializes `_spans: list[HttpSpan]`, `_max_spans: int`, `_lock: threading.Lock()`
4. **OTelCollector.span_count** — property returning `len(self._spans)`
5. **record_span(span)** — acquires `_lock`; appends only if `len(_spans) < _max_spans`; silent no-op on overflow
6. **get_spans(url, method, status_min, status_max)** — copies `_spans` list; applies each filter as independent predicate; returns filtered list
7. **normalize_url(url)** — static method; applies `_UUID_PATTERN` substitution to `/{uuid}` first, then `_NUMERIC_ID` substitution to `/{id}`
8. **get_url_patterns()** — applies `normalize_url` to all span URLs; returns `sorted(set(patterns))`
9. **export_api_traces()** — iterates `_spans`; for each span: calls `extract_json_shape` on `request_body` (if not None) and `response_body` (if not None), serializes with `json.dumps(shape, separators=(",", ":"))`, sets empty string when body is None; constructs and returns `list[ApiTrace]`
10. **clear()** — acquires `_lock`; calls `_spans.clear()`
