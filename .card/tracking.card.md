---
card-version: "1.0"
id: tracking
title: Verification Tracking Database
status: draft
module:
  owns: [TrackingDB, record_run, get_pass_rate, get_pass_rate_by_model, get_pass_rate_by_spec, get_recent_runs, get_run_count]
  depends-on:
    sqlite3: "standard library — append-only audit store"
contract:
  inputs:
    - name: spec_id
      type: str
      constraints: "non-empty module identifier"
    - name: model
      type: str
      constraints: "LLM model string, e.g. 'claude-sonnet-4-6'"
    - name: verified
      type: bool
      constraints: "True if all verification stages passed"
    - name: stage_results
      type: list[dict]
      constraints: "JSON-serializable list of stage result dicts"
    - name: retry_count
      type: int
      constraints: ">= 0"
    - name: total_cost
      type: float
      constraints: ">= 0.0, USD"
  outputs:
    - name: run_id
      type: int
      schema: {autoincrement: true, positive: true}
  errors:
    - sqlite3.OperationalError
invariants:
  - id: INV-01
    tier: property
    statement: "record_run always returns a positive integer run ID (AUTOINCREMENT PRIMARY KEY)"
    rationale: "SQLite AUTOINCREMENT guarantees monotonically increasing IDs; the caller needs the ID for linking"
  - id: INV-02
    tier: property
    statement: "get_pass_rate returns 0.0 when there are no runs, never raises ZeroDivisionError"
    rationale: "Pass rate is total/count; the zero-count guard (if total > 0) prevents division by zero"
  - id: INV-03
    tier: property
    statement: "get_pass_rate_by_model and get_pass_rate_by_spec return values in [0.0, 1.0]"
    rationale: "Pass rate is a fraction of verified/total; it cannot exceed 1.0 or go below 0.0"
  - id: INV-04
    tier: property
    statement: "record_run stores verified as INTEGER (0 or 1); get_recent_runs deserializes it back to bool"
    rationale: "SQLite has no native boolean; the round-trip INTEGER<->bool conversion must be consistent"
  - id: INV-05
    tier: property
    statement: "record_run serializes stage_results as JSON string; get_recent_runs deserializes it back to list[dict]"
    rationale: "JSON round-trip must preserve the stage results structure for downstream replay and optimization"
  - id: INV-06
    tier: property
    statement: "Existing run rows are never modified or deleted — the table is append-only"
    rationale: "The audit trail must be immutable; historical pass rates must remain reproducible"
---

## Intent

Record every verification run to a SQLite database for self-evolution analysis. Each run captures the spec, model, outcome, per-stage results, retry count, and cost. The database feeds three downstream systems: experience replay (retrieve similar past successes), DSPy SIMBA optimization (pass rate as evaluation metric), and AutoResearch hill climbing. The schema is append-only to preserve a tamper-evident audit trail.

## Acceptance Criteria

### Story 1 — Record and Query (P0)

**As a** self-evolution pipeline, **I want** to record every verification run and query aggregate pass rates, **so that** I can measure whether prompts and models are improving.

1. **Given** 10 runs with 7 verified, **When** get_pass_rate is called, **Then** returns 0.7
2. **Given** 5 runs for model A (3 verified) and 3 for model B (1 verified), **When** get_pass_rate_by_model("A") is called, **Then** returns 0.6
3. **Given** no runs recorded yet, **When** get_pass_rate is called, **Then** returns 0.0

### Story 2 — Recent Runs (P0)

**As a** dashboard, **I want** the most recent N runs with all fields deserialized, **so that** I can display recent activity.

1. **Given** 20 recorded runs, **When** get_recent_runs(limit=5) is called, **Then** returns 5 dicts ordered by timestamp descending
2. **Given** any run dict returned, **When** inspected, **Then** verified field is bool and stage_results field is list

## Functional Requirements

- **FR-001**: MUST create runs table and three indexes (spec_id, model, timestamp DESC) on first init
- **FR-002**: MUST store verified as INTEGER 0/1, not as bool
- **FR-003**: MUST serialize stage_results to JSON string before insert
- **FR-004**: get_pass_rate, get_pass_rate_by_model, get_pass_rate_by_spec MUST return 0.0 (not raise) when no matching rows exist
- **FR-005**: MUST NOT update or delete any existing rows — all mutations are inserts only
