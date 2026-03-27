---
card-version: "1.0"
id: display
title: Rich CLI Display
status: active
module:
  owns: [DisplayCallback, NullDisplay, RichStreamingDisplay, format_verify_result, format_stage_result, format_explain, create_progress]
  depends-on:
    rich: "rich>=13.0"
    nightjar.types: "internal"
contract:
  inputs:
    - name: result
      type: VerifyResult
      constraints: "populated VerifyResult from the verification pipeline"
    - name: report
      type: dict
      constraints: "parsed verify.json dict for format_explain"
  outputs:
    - name: terminal_output
      type: None
      schema: {}
invariants:
  - id: INV-01
    tier: property
    statement: "DisplayCallback is a runtime-checkable Protocol with exactly three methods: on_stage_start, on_stage_complete, on_pipeline_complete"
    rationale: "The protocol is the observer contract between verifier.py and all display implementations"
  - id: INV-02
    tier: property
    statement: "NullDisplay.on_stage_start, NullDisplay.on_stage_complete, and NullDisplay.on_pipeline_complete produce no stdout or stderr output"
    rationale: "NullDisplay is used in --quiet mode and tests; it must be a true no-op"
  - id: INV-03
    tier: example
    statement: "format_stage_result returns a string matching 'Stage N (name): STATUS [Xms]' where N is the stage number"
    rationale: "Consistent one-line format is required by CLI explain and test assertions"
  - id: INV-04
    tier: property
    statement: "_format_duration_ms(ms) returns '{ms}ms' when ms < 1000, and '{ms/1000:.2f}s' when ms >= 1000"
    rationale: "Duration display convention from ARCHITECTURE.md Section 8"
  - id: INV-05
    tier: property
    statement: "RichStreamingDisplay renders exactly 5 stage rows (stages 0 through 4) in the live table, regardless of how many stages have started"
    rationale: "The pipeline always has exactly 5 stages; waiting rows must appear immediately"
  - id: INV-06
    tier: property
    statement: "format_explain produces no output and returns early when report.get('verified') is True"
    rationale: "The explain command must short-circuit on passing reports to avoid confusing users"
  - id: INV-07
    tier: property
    statement: "All display functions gracefully degrade to plain text when Rich is not installed (HAS_RICH is False)"
    rationale: "Rich is an optional dependency; display must work without it in minimal environments"
---

## Intent

The display module is the output layer for the Nightjar verification pipeline. It defines the `DisplayCallback` observer protocol that `verifier.py` calls during pipeline execution, and provides two implementations: `NullDisplay` (silent) and `RichStreamingDisplay` (live Rich terminal table). It also provides standalone formatting functions (`format_verify_result`, `format_stage_result`, `format_explain`) for the CLI explain command and plain-text fallbacks for environments without Rich installed.

## Acceptance Criteria

### Story 1 — Live Streaming Display (P0)

**As a** developer running `nightjar verify`, **I want** a live-updating terminal table showing each stage's status as it runs, **so that** I get immediate feedback without waiting for the full pipeline.

1. **Given** a RichStreamingDisplay used as context manager, **When** on_stage_start(2, "schema") is called, **Then** stage row 2 shows "running..." in yellow
2. **Given** on_stage_complete is called with a PASS result, **When** rendering, **Then** the row shows "PASS" in green with the duration
3. **Given** on_pipeline_complete is called with verified=True, **Then** a green "VERIFIED" banner appears at the bottom

### Story 2 — Graceful Degradation (P1)

**As a** user in a minimal environment without Rich, **I want** display functions to fall back to plain text, **so that** the CLI works everywhere.

1. **Given** Rich is not installed (HAS_RICH = False), **When** format_verify_result is called, **Then** plain text is printed without errors

### Edge Cases

- NullDisplay called in any sequence → no output produced
- format_explain with verified=True → returns without printing failure content
- format_stage_result with 0 errors → no error count appended to string
- format_stage_result with >0 errors → "(N error(s))" appended

## Functional Requirements

- **FR-001**: DisplayCallback MUST be defined as @runtime_checkable Protocol
- **FR-002**: NullDisplay MUST satisfy isinstance(NullDisplay(), DisplayCallback) check
- **FR-003**: RichStreamingDisplay MUST be usable as a context manager (implements __enter__/__exit__)
- **FR-004**: RichStreamingDisplay MUST accept an injectable console parameter for test capture
- **FR-005**: format_stage_result MUST return a string (not print to stdout)
- **FR-006**: create_progress MUST return a context manager compatible object whether or not Rich is installed
