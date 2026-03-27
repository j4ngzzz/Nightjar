---
card-version: "1.0"
id: tui
title: Textual TUI Dashboard
status: active
module:
  owns: [NightjarTUI, StagePanel]
  depends-on:
    textual: "textual>=0.40"
    nightjar.types: "internal"
contract:
  inputs:
    - name: stage_events
      type: StageResult
      constraints: "emitted by verifier.py during pipeline execution"
    - name: pipeline_result
      type: VerifyResult
      constraints: "emitted once when pipeline completes"
  outputs:
    - name: terminal_ui
      type: None
      schema: {}
invariants:
  - id: INV-01
    tier: example
    statement: "NightjarTUI.compose() yields exactly 5 StagePanel widgets with ids stage-0 through stage-4, plus Header, ProgressBar, Static banner, and Footer"
    rationale: "The pipeline always has 5 stages; the TUI layout is fixed and predictable"
  - id: INV-02
    tier: property
    statement: "NightjarTUI.on_stage_start, on_stage_complete, and on_pipeline_complete use post_message to post thread-safe messages rather than updating widgets directly"
    rationale: "Verifier runs in a background thread; Textual widgets must only be modified from the main event loop"
  - id: INV-03
    tier: example
    statement: "StagePanel.render() returns a string in the format '{icon} Stage {N}: {name:<16} {dur:<12} {status}'"
    rationale: "Fixed-width layout prevents column shifts as status values change during execution"
  - id: INV-04
    tier: example
    statement: "After on_pipeline_complete with verified=True, the banner widget shows '✓  VERIFIED' with color #00FF88; with verified=False it shows '✗  FAIL' with color red"
    rationale: "The banner is the primary pass/fail signal in the TUI; it must match the two possible outcomes"
  - id: INV-05
    tier: property
    statement: "StagePanel.stage_status_val starts as 'waiting' and transitions only to 'running', 'pass', 'fail', 'skip', or 'timeout'"
    rationale: "Status values are constrained to the keys defined in _STATUS_ICONS and _STATUS_COLORS"
---

## Intent

The TUI module provides a Textual-based terminal dashboard for live verification progress. `NightjarTUI` implements the `DisplayCallback` protocol so `verifier.py` can drive it directly with stage events. The dashboard renders five collapsible `StagePanel` widgets (one per pipeline stage) that transition from waiting through running to pass/fail as verification executes, plus a confidence `ProgressBar` and a final pass/fail banner. Thread safety is achieved through Textual's `post_message` pattern — the DisplayCallback methods can be called from background threads.

## Acceptance Criteria

### Story 1 — Live Pipeline Dashboard (P0)

**As a** developer running `nightjar verify` interactively, **I want** a full-screen TUI showing each stage's progress in real time, **so that** I can see which stage is running and how long it takes.

1. **Given** the TUI is started, **When** compose() is called, **Then** 5 stage panels are visible in the stages container, all showing "waiting" (○ icon)
2. **Given** on_stage_start(1, "deps") is called from a background thread, **When** the event loop processes the message, **Then** panel #stage-1 shows "running" (▶ icon, amber color)
3. **Given** on_stage_complete is called with a PASS result for stage 1, **Then** panel #stage-1 shows "✓" and the duration in milliseconds

### Story 2 — Pipeline Completion Banner (P1)

**As a** developer, **I want** a clear PASS/FAIL banner at the bottom of the TUI after all stages complete, **so that** the final verdict is immediately visible.

1. **Given** on_pipeline_complete with verified=True, **Then** banner shows "✓  VERIFIED" in green (#00FF88)
2. **Given** on_pipeline_complete with verified=False, **Then** banner shows "✗  FAIL" in red

### Edge Cases

- on_pipeline_complete with confidence=None → ProgressBar not updated (no AttributeError)
- on_pipeline_complete with confidence.score=non-numeric → ProgressBar not updated (no crash)
- StagePanel for an unknown status value → render() uses "?" icon

## Functional Requirements

- **FR-001**: NightjarTUI MUST implement the DisplayCallback protocol (on_stage_start, on_stage_complete, on_pipeline_complete)
- **FR-002**: All DisplayCallback methods MUST call self.post_message() — never update widgets directly from these methods
- **FR-003**: StagePanel MUST use Textual reactive attributes for stage_status_val, stage_name_str, and duration_ms
- **FR-004**: The CSS color for each status MUST be applied in watch_stage_status_val via self.styles.color
- **FR-005**: NightjarTUI MUST handle AttributeError/TypeError/ValueError from confidence.score without crashing
