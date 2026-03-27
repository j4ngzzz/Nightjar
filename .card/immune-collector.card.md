---
card-version: "1.0"
id: immune_collector
title: Immune System - Runtime Type Collector
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "TypeCollector.trace() restores the prior sys.setprofile handler on exit, regardless of whether an exception is raised inside the context"
    rationale: "The collector must not leave a dangling profile hook that interferes with other profilers or tests running after the trace block"
  - id: INV-02
    tier: property
    statement: "A CallTrace is only recorded when a matching 'return' event is observed — partial calls (call without return) are never emitted to _call_traces"
    rationale: "Incomplete traces (call without return) would corrupt invariant mining with missing return_type data; the pending queue ensures pairing"
  - id: INV-03
    tier: property
    statement: "For any function, len(get_call_traces(fn)) <= max_records — the per-function trace buffer is capped at the max_records constructor argument"
    rationale: "Unbounded trace accumulation would exhaust memory during long-running processes; max_records is the memory guard"
  - id: INV-04
    tier: property
    statement: "get_unique_signatures(fn) returns a subset of get_call_traces(fn) — no signature in unique_signatures is absent from the full trace list"
    rationale: "Deduplication only reduces; it must not fabricate signatures that were never actually observed"
  - id: INV-05
    tier: property
    statement: "The collector never raises an exception when tracing a frame that cannot be inspected — inspect.getargvalues failures are caught and the call is silently skipped"
    rationale: "No-crash-on-untraceable guarantee: profiling hooks run in all call frames; a crash here would propagate to the traced application"
  - id: INV-06
    tier: property
    statement: "export_type_traces(fn) returns TypeTrace objects only for argument names and the 'return' slot — no other variable names appear as arg_name"
    rationale: "TypeTrace consumers expect structured arg_name fields; exporting arbitrary local variable names would break downstream mining"
  - id: INV-07
    tier: example
    statement: "Stdlib frames (lib/python, site-packages, contextlib, threading, <frozen>) and the collector's own frame are never included in call traces"
    rationale: "Tracing stdlib noise bloats the trace store with useless data and can cause infinite recursion in the profiling callback"
---

## Intent

Collects runtime type information from executing Python functions using `sys.setprofile`,
mirroring Instagram's MonkeyType approach. The collector instruments code non-invasively —
no decorators or source modifications required — and records argument and return types for
each observed function call.

Collected type traces feed the immune system's invariant mining pipeline (daikon.py)
and are exported as `TypeTrace` objects for storage in `TraceStore`.

References:
- [REF-T12] MonkeyType — runtime type collection via sys.setprofile
- [REF-C05] Dynamic Invariant Mining — type traces as input to Stage 2 mining

## Acceptance Criteria

- [ ] `TypeCollector.trace()` is a context manager; prior profile is always restored on exit
- [ ] `trace_count` property increments by 1 for each completed (call + return) pair recorded
- [ ] `get_call_traces(fn)` returns at most `max_records` entries per function
- [ ] `get_unique_signatures(fn)` returns deduplicated traces (same arg_types + return_type only once)
- [ ] `export_type_traces(fn)` produces `TypeTrace` objects with `arg_name` set to argument name or `"return"`
- [ ] `get_all_function_names()` returns only functions that have at least one recorded trace
- [ ] `clear(fn)` removes traces for that function only; `clear()` removes all traces and resets trace_count
- [ ] Frames from stdlib, site-packages, and the collector module itself are excluded from tracing
- [ ] Dunder methods (`__init__`, `__str__`, etc.) are excluded from tracing
- [ ] No exception escapes from `_profile_callback` regardless of frame state

## Functional Requirements

1. **TypeCollector.__init__** — accepts optional `include_modules: list[str]` to restrict tracing scope, and `max_records: int` (default 10000) as per-function buffer cap
2. **TypeCollector.trace()** — context manager using `sys.setprofile`; saves and restores prior profile handler; yields control to caller
3. **_should_trace(frame)** — returns False for: the collector's own file, stdlib markers, site-packages, dunder methods, and modules not in `include_modules` (when filter is set)
4. **_profile_callback** — on `"call"` event: extracts argument types from `frame.f_locals`, pushes to per-thread `_pending` queue; on `"return"` event: pops pending call, records completed `CallTrace`; uses `threading.Lock` for thread safety
5. **get_call_traces(fn)** — returns a copy of the internal trace list for the named function (empty list if not found)
6. **get_unique_signatures(fn)** — deduplicates traces by `f"{arg_types}:{return_type}"` key; returns one trace per unique type signature
7. **export_type_traces(fn, module)** — calls `get_unique_signatures`, emits one `TypeTrace` per argument and one for the return value; uses recorded module if `module` argument is empty
8. **get_all_function_names()** — returns names of functions with non-empty trace lists
9. **clear(fn)** — removes traces for one function; `clear()` with no argument clears all and resets `_trace_count`
