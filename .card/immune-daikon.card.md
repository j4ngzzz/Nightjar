---
card-version: "1.0"
id: immune_daikon
title: Immune System - Dynamic Invariant Miner
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "Every Invariant returned by get_invariants(fn) holds for ALL call records observed — no invariant is emitted that was falsified by even one observation"
    rationale: "This is the core Daikon falsification principle (Ernst et al. 1999 Section 3.3): candidates are eliminated against every observation; survivors are the discovered invariants"
  - id: INV-02
    tier: property
    statement: "get_invariants(fn) returns [] when no call records exist for fn — mining on zero observations produces no invariants"
    rationale: "Generating invariants from zero data is unsound; the empty-trace guard prevents phantom invariants"
  - id: INV-03
    tier: property
    statement: "InvariantMiner.trace() restores prior tracing state on exit (sys.monitoring tool slot freed, or sys.settrace handler restored) regardless of exceptions inside the block"
    rationale: "Leaking a monitoring tool slot or settrace hook would break other profilers, debuggers, and test frameworks running after the miner exits"
  - id: INV-04
    tier: property
    statement: "For any function, len(trace.call_records) <= max_records — the per-function call buffer is capped at the max_records constructor argument"
    rationale: "Memory guard: long-running applications generate unbounded call volumes; max_records prevents OOM crashes"
  - id: INV-05
    tier: property
    statement: "On Python 3.12+, using_sys_monitoring is True after trace() starts; on Python 3.11 (or when all monitoring slots are taken), the miner falls back to sys.settrace without raising an exception"
    rationale: "Graceful fallback ensures correctness on Python 3.11 while exploiting the 20x overhead advantage of sys.monitoring when available"
  - id: INV-06
    tier: property
    statement: "A CONSTANT invariant (var == C) is only emitted when ALL observed values are the identical value C — not merely the majority"
    rationale: "Ernst Constant template: a single observation with a different value falsifies the invariant; majority is not sufficient"
  - id: INV-07
    tier: property
    statement: "A TYPE invariant (isinstance(var, T)) is only emitted when all observed values have the same runtime type — mixed-type observations produce no type invariant"
    rationale: "Ernst IsType template: one counter-example (different type) falsifies the invariant"
---

## Intent

Implements the Daikon dynamic invariant detection algorithm (Ernst et al. 2007) as a
clean-room MIT reimplementation. Traces function executions, records argument and return
values, generates candidate invariants from 19 Ernst 1999/2007 templates, then falsifies
any candidate that fails even one observation.

Uses `sys.monitoring` (PEP 669, Python 3.12+) as the primary tracing mechanism for
up to 20x lower overhead than `sys.settrace`. Falls back to `sys.settrace` on Python 3.11
or when monitoring slots are exhausted.

The 19 template categories: Constant, IsType, IsNull/NonNull, Range/Bound, OneOf,
SeqLength, SeqSorted, SeqOneOf, Relational (binary), Equality, Ordering, Linear,
Unchanged, Increased, Decreased, Implication.

References:
- [REF-C05] Dynamic Invariant Mining — immune system Stage 2
- Ernst et al. 2007 — The Daikon system (Science of Computer Programming, 69(1-3))
- PEP 669 — sys.monitoring (Python 3.12+)
- Scout 6 mining-report.md — 20x overhead advantage with sys.monitoring

## Acceptance Criteria

- [ ] `InvariantMiner.trace()` is a context manager; monitoring state is fully restored on exit
- [ ] `get_invariants(fn)` returns `[]` when the function has no recorded call records
- [ ] Every returned invariant holds across all recorded call records (falsification)
- [ ] `using_sys_monitoring` property reflects actual tracing mechanism in use
- [ ] CONSTANT invariant is emitted only when all observations share the same value
- [ ] TYPE invariant is emitted only when all observations share the same runtime type
- [ ] NULLNESS invariant is emitted only when all observations are None, or all are not None
- [ ] RANGE invariant captures actual [min, max] from observed numeric values
- [ ] ONE_OF invariant is only emitted when distinct value count is <= `_ONE_OF_MAX_CARDINALITY` (5)
- [ ] `trace_count` increments once per completed (call + return) pair
- [ ] Per-function call records are capped at `max_records`
- [ ] Stdlib, site-packages, dunder methods, and daikon.py itself are excluded from tracing

## Functional Requirements

1. **InvariantMiner.__init__** — accepts `include_modules: list[str]` filter and `max_records: int` (default 10000)
2. **InvariantMiner.trace()** — on Python 3.12+: acquires sys.monitoring tool slot (tries IDs 4, 5), registers CALL + PY_RETURN callbacks; on Python 3.11 or slot exhaustion: uses sys.settrace; restores all state on exit
3. **_should_trace_code(code, module_name)** — excludes: daikon.py itself, stdlib markers (lib/python, Lib\\, site-packages, importlib, \<frozen\>, \<string\>), dunder methods, modules outside include_modules filter
4. **get_invariants(fn)** — iterates all 19 Ernst templates; returns only candidates that survived falsification against all call records
5. **_mine_constant_invariants** — emits CONSTANT if all values are identical (hashable check; unhashable values skipped)
6. **_mine_type_invariants** — emits TYPE if all values have the same `type(v).__name__`
7. **_mine_nullness_invariants** — emits NonNull if all non-None; emits IsNull if all None
8. **_mine_bound_invariants** — emits BOUND for numeric variables (>=0, >0, <=0, <0 patterns)
9. **_mine_range_invariants** — emits RANGE(lo, hi) for explicit observed min/max bounds
10. **_mine_one_of_invariants** — emits ONE_OF if distinct values <= _ONE_OF_MAX_CARDINALITY (5)
11. **_mine_length_invariants** — emits LENGTH bound for sequences (len >= 0, len > 0)
12. **_mine_seq_sorted_invariants** — emits SEQ_SORTED if all observed lists are in sorted order
13. **_mine_seq_one_of_invariants** — emits SEQ_ONE_OF if all sequence elements stay within a fixed observed set
14. **_mine_relational_invariants** — emits binary RELATIONAL, EQUALITY, ORDERING, LINEAR between pairs of numeric variables
15. **_mine_state_invariants** — emits UNCHANGED, INCREASED, DECREASED comparing entry arg to return value within each call record
16. **_mine_implication_invariants** — emits IMPLICATION for conditional patterns between variables
