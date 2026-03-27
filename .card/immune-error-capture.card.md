---
card-version: "1.0"
id: immune_error_capture
title: Immune System - Error Capture
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "strip_pii(message) never raises an exception for any string input — all regex substitutions are applied sequentially and the result is always a string"
    rationale: "strip_pii runs inside exception handlers; a crash here would mask the original error and corrupt the error capture pipeline"
  - id: INV-02
    tier: property
    statement: "compute_semantic_fingerprint returns a 16-character hex string — never shorter, never longer"
    rationale: "SHA-256[:16] always produces exactly 16 hex characters; downstream grouping logic depends on this fixed-width key"
  - id: INV-03
    tier: property
    statement: "Two calls with the same exception_class, the same PII-stripped message, and the same function name always produce the same fingerprint"
    rationale: "Semantic grouping requires deterministic fingerprinting: identical error patterns must hash to the same bucket regardless of runtime-specific values (IPs, UUIDs, etc.)"
  - id: INV-04
    tier: property
    statement: "capture_exception() raises RuntimeError when called outside an except block (when sys.exc_info() returns (None, None, None))"
    rationale: "Calling capture_exception outside a handler is a programming error; a clear RuntimeError is more useful than a silent empty trace or NoneType crash"
  - id: INV-05
    tier: property
    statement: "ErrorCapture.watch() catches all Exception subclasses; the captured ErrorTrace is appended to self.captured before re-raise (if reraise=True)"
    rationale: "The trace must be recorded before the exception propagates, so the trace is available even if the caller handles the re-raised exception immediately"
  - id: INV-06
    tier: example
    statement: "input_shape from _extract_input_shape includes at most 10 variables, skips names starting with '_', and formats each as 'name:type' or 'name:type[len]'"
    rationale: "The shape is a compact diagnostic aid; capping at 10 prevents excessively large store entries from functions with many locals"
---

## Intent

Captures unhandled exceptions as structured `ErrorTrace` objects with PII-stripped message
templates and semantic fingerprints for grouping identical error classes across different
execution contexts.

Inspired by Sentry's error grouping approach: the raw error message is scrubbed of
user-specific data (emails, IPs, UUIDs, phone numbers, large numeric IDs), then hashed
with the exception class and function name to produce a stable grouping key.

Feeds the immune system's error-driven invariant discovery pipeline.

References:
- [REF-C05] Dynamic Invariant Mining — error-driven invariant discovery
- ARCHITECTURE.md Section 6, Stage 1 — third collection signal (error traces)

## Acceptance Criteria

- [ ] `strip_pii(msg)` replaces: email addresses with `{EMAIL}`, UUIDs with `{UUID}`, IPv4 with `{IP}`, phone numbers with `{PHONE}`, long numerics (6+ digits) with `{ID}`, quoted strings with `'{VALUE}'` or `"{VALUE}"`
- [ ] `compute_semantic_fingerprint` returns exactly 16 hex characters
- [ ] Same inputs to `compute_semantic_fingerprint` always produce the same output
- [ ] `capture_exception()` raises `RuntimeError` when called outside an except block
- [ ] `capture_exception()` captures: `exception_class`, `message_template` (PII-stripped), `stack_fingerprint`, `function` (innermost frame), `module`, `input_shape`
- [ ] `ErrorCapture.watch()` appends to `self.captured` for all `Exception` subclasses
- [ ] When `reraise=True`, the exception is re-raised after capture; when `reraise=False`, it is suppressed
- [ ] `_extract_input_shape` skips variables starting with `_`, limits to 10 variables, formats as `name:type` or `name:type[len]`

## Functional Requirements

1. **PII patterns** — six ordered regex patterns applied sequentially:
   - Email: `[a-zA-Z0-9_.+-]+@...` → `{EMAIL}`
   - UUID (8-4-4-4-12 hex groups) → `{UUID}`
   - IPv4 (`\b\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}\b`) → `{IP}`
   - Phone (international/US, 8+ digits) → `{PHONE}`
   - Long numeric IDs (6+ digit `\b` word) → `{ID}`
   - Single-quoted values → `'{VALUE}'`; double-quoted values → `"{VALUE}"`
2. **strip_pii(message)** — applies all six patterns in order; returns the cleaned string
3. **compute_semantic_fingerprint(exception_class, message, function)** — calls `strip_pii(message)`, constructs key `f"{exception_class}:{template}:{function}"`, returns `sha256(key.encode("utf-8")).hexdigest()[:16]`
4. **capture_exception()** — uses `sys.exc_info()`; raises `RuntimeError` if all three are None; walks `tb.tb_next` to reach innermost frame; extracts `function`, `module`, `input_shape`; calls `strip_pii` on raw message; calls `compute_semantic_fingerprint`; returns `ErrorTrace`
5. **_extract_input_shape(locals_dict)** — iterates `sorted(locals_dict.items())`; skips names starting with `_`; formats as `name:type[len]` if `len()` succeeds, else `name:type`; caps at first 10 entries; joins with `", "`
6. **ErrorCapture.__init__(reraise=False)** — stores `reraise` flag; initializes `captured: list[ErrorTrace] = []`
7. **ErrorCapture.watch()** — context manager; catches `Exception`; calls `capture_exception()`, appends result to `self.captured`; re-raises if `self.reraise is True`
