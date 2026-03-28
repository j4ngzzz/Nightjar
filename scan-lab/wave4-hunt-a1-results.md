# Wave 4 Hunt A1 — Security Audit Results

**Auditor:** Independent security researcher
**Date:** 2026-03-29
**Packages:**
- `langchain-core` 1.2.23
- `langgraph` 1.1.3
- `langgraph-checkpoint` 4.0.1
**Python:** 3.14.3
**Hypothesis:** 6.151.9 (max_examples=200 per test)

**Methodology:** Read source via `inspect.getsource()` → identify contracts → write Hypothesis PBT → run → manual 3x reproduction → cross-check GitHub issues → report only what Hypothesis actually caught.

**GitHub/CVE pre-check:**
- CVE-2025-68664 was the prior `langchain-core` serialization injection CVE — regression-tested here, confirmed patched.
- No open CVEs found for langgraph 1.1.3.
- GitHub langgraph issue #3267 and related issues discuss the silent routing behavior — it is a known, unfixed design behavior as of this version.

---

## Summary

| Target | Contract | Result |
|--------|----------|--------|
| langchain-core `dumps()`/`dumpd()` + `loads()` round-trip | Content, type, and `additional_kwargs` survive without mutation | CLEAN |
| langchain-core lc-injection guard | User dicts with `lc` key are escaped, not instantiated as LC objects | CLEAN (CVE-2025-68664 patch confirmed effective) |
| langgraph `add_conditional_edges()` with `path_map` | Invalid return raises `KeyError` | CLEAN |
| langgraph `add_conditional_edges()` without `path_map` | Invalid return raises exception | **BUG CONFIRMED** |
| `InMemorySaver` checkpoint put/get round-trip | `get_tuple()` returns the last-put checkpoint | CLEAN (with correct uuid6 IDs) |
| `InMemorySaver` metadata round-trip | Metadata survives put/get without mutation | CLEAN |

---

## Finding 1 — langgraph: Silent Routing Failure (No `path_map`, Invalid Return)

**Status:** BUG CONFIRMED — Hypothesis found counterexample, reproduced 3/3 times
**Severity:** MEDIUM (logic correctness; not a remote code execution vector)
**Already known:** Yes — existing repro at `scan-lab/repro_langgraph_silent_routing.py` confirms this is the same bug previously documented in this scan-lab. GitHub issues exist but it remains unfixed in 1.1.3.

### Description

When `add_conditional_edges()` is called **without a `path_map`**, the router's return value is used directly as a node name. If the return value is not a registered node name, the graph does **not raise an exception**. It emits a `WARNING`-level log message and silently continues, returning the current state unchanged. The intended downstream node never executes.

This is a **silent logic failure**: the graph reports success, no exception propagates, and the caller has no indication that routing was dropped.

With a `path_map` supplied, the behavior is correct: a `KeyError` is raised immediately.

### Hypothesis Counterexample

Minimized by Hypothesis:

```
thread_id = '0'   (any string not equal to a valid node name)
```

The router returns `'0'` (or any string that is not a registered node). With no `path_map`, the graph compiles successfully and `invoke()` returns without error.

### Standalone Repro (3x confirmed)

```python
# langgraph==1.1.3, langgraph-checkpoint==4.0.1
import logging
import warnings
warnings.filterwarnings("ignore")

from langgraph.graph import StateGraph, END

for run in range(1, 4):
    visited = []

    def process(state):
        visited.append(True)
        return state

    builder = StateGraph(dict)
    builder.add_node("validate", lambda s: s)
    builder.add_node("process", process)
    builder.set_entry_point("validate")

    # Router returns a node name that does NOT exist
    builder.add_conditional_edges(
        "validate",
        lambda s: "nod_e",   # typo: 'node' misspelled, not registered
        # NOTE: no path_map
    )
    builder.add_edge("process", END)

    graph = builder.compile()
    result = graph.invoke({"amount": 100})

    # Expected: exception raised. Actual: success, 'process' never ran.
    assert not visited, f"Run {run}: BUG — process ran when it should not have"
    assert result == {"amount": 100}, f"Run {run}: result was {result!r}"
    print(f"Run {run}: REPRODUCED — invoke() returned {result!r}, 'process' never ran")
```

**Output (all 3 runs):**
```
Run 1: REPRODUCED — invoke() returned {'amount': 100}, 'process' never ran
Run 2: REPRODUCED — invoke() returned {'amount': 100}, 'process' never ran
Run 3: REPRODUCED — invoke() returned {'amount': 100}, 'process' never ran
```

### Root Cause

In `langgraph/pregel/_write.py`, when `ChannelWrite.do_write()` encounters a destination channel that is not registered, it logs a warning and drops the write:

```
Task {name} with path {path} wrote to unknown channel branch:to:{dest}, ignoring it.
```

This is handled at the Pregel execution layer, after the branch routing has already fired. There is no upstream validation in `_finish()` (in `_branch.py`) that checks whether the returned destination is actually a registered node when `self.ends is None` (no `path_map`).

By contrast, when `self.ends` is set (`path_map` was provided), `_finish()` does:
```python
destinations = [r if isinstance(r, Send) else self.ends[r] for r in result]
```
This raises `KeyError` immediately if `r` is not in `self.ends`.

### Impact

- Any application that uses `add_conditional_edges()` without `path_map` and where the router can return an unregistered node name will silently skip execution of the intended node.
- Downstream invariants (state updates, side effects, payment processing, etc.) are silently dropped.
- The only observable signal is a `WARNING`-level log entry, which is often suppressed in production.
- This is particularly dangerous in agentic workflows where routing determines whether safety/validation/payment nodes execute.

### Contrast: With `path_map`

```python
# With path_map — CORRECT behavior (raises immediately):
builder.add_conditional_edges(
    "validate",
    lambda s: "bad_key",
    path_map={"good_key": "process"},
)
graph.compile().invoke({})
# -> KeyError: 'bad_key'   ← exception raised, caller is informed
```

---

## Targets That Were CLEAN

### Target 1: langchain-core `dumps()`/`dumpd()` + `loads()` Round-trip

**200 examples each, no counterexample found.**

Tests run:
- `test_aimessage_content_roundtrip` — arbitrary text content survives without mutation
- `test_humanmessage_roundtrip` — arbitrary text content survives
- `test_aimessage_metadata_roundtrip` — `additional_kwargs` with primitive values serializes to valid JSON
- `test_binary_content_aimessage` — binary-decoded strings do not crash serialization

All passed. The round-trip is faithful for all tested inputs.

### Target 1b: lc-Injection Guard (CVE-2025-68664 Regression)

**200 examples, no counterexample found.**

Tests run:
- `test_lc_key_injection_in_additional_kwargs` — dicts with `"lc"` key are escaped via `__lc_escaped__` wrapper; `loaded.additional_kwargs` comes back as a plain dict, not an instantiated object
- `test_serialization_injection_via_lc_object_shaped_dict` — dicts shaped exactly like `{"lc": 1, "type": "constructor", "id": [...], "kwargs": {}}` are escaped and returned as plain dicts

The `_needs_escaping` / `_escape_dict` protection in `langchain_core/load/_validation.py` correctly blocks injection via `additional_kwargs`. CVE-2025-68664 patch is confirmed effective.

Manual verification of the worst-case input:
```python
injection = {"lc": 1, "type": "constructor", "id": ["os", "system"], "kwargs": {}}
msg = AIMessage(content="harmless", additional_kwargs=injection)
loaded = loads(dumps(msg))
# loaded.additional_kwargs == {"lc": 1, "type": "constructor", "id": ["os", "system"], "kwargs": {}}
# type(loaded) == AIMessage   <-- correct, no class instantiation
```

### Target 2: `add_conditional_edges()` With `path_map`

**200 examples, no counterexample found.**

`test_conditional_edge_with_invalid_return_raises`: when `path_map` is provided and the router returns a key not in the map, `KeyError` is raised during `invoke()`. The caller is correctly notified. This path is safe.

### Target 3: `InMemorySaver` Checkpoint Put/Get Round-trip

**200 examples, no counterexample found** (after correcting test to match actual API contract).

`test_checkpoint_put_get_roundtrip`: a single put/get round-trip returns the same checkpoint ID. Clean.

`test_checkpoint_metadata_roundtrip`: metadata `writes` field survives serialization via `JsonPlusSerializer` (msgpack). Clean.

**Note on `test_checkpoint_multiple_puts_returns_latest`:** Hypothesis initially flagged this with uuid4 IDs. Investigation confirmed this is a **test design flaw, not a library bug**. The real Pregel loop generates `uuid6` (time-sortable) checkpoint IDs (see `langgraph/pregel/_checkpoint.py`). `InMemorySaver.get_tuple()` uses `max(checkpoints.keys())` to find the "latest" checkpoint, which is correct when keys are `uuid6` strings (lexicographic order == chronological order). External callers who inject `uuid4` IDs into `put()` would get incorrect "latest" semantics, but there is no input validation preventing this — it is a documentation/contract gap, not a security vulnerability.

---

## Test Artifacts

- **Hypothesis test file:** `scan-lab/wave4_a1_hypothesis_tests.py`
- **Standalone repro (silent routing):** `scan-lab/repro_langgraph_silent_routing.py`
- **Prior test files (same bug confirmed independently):** `scan-lab/wave4_hunt_a1_tests.py`, `scan-lab/wave4_hunt_a1_tests_v2.py`

---

## Verdict

| Finding | Classification |
|---------|---------------|
| Silent routing failure on invalid node name (no `path_map`) | **BUG — confirmed, known, unfixed in 1.1.3** |
| All other targets | **CLEAN** |

One confirmed bug. No new CVEs identified. No remote code execution vectors found. The `lc`-injection guard introduced to fix CVE-2025-68664 is working correctly.
