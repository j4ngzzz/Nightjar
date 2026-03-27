---
card-version: "1.0"
id: watch
title: Watch Daemon
status: active
module:
  owns: [start_watch, run_tiered_verification, CardChangeHandler, TierEvent]
  depends-on:
    watchdog: "watchdog>=3.0"
    nightjar.parser: "internal"
    nightjar.stages.pbt: "internal"
    nightjar.stages.formal: "internal"
contract:
  inputs:
    - name: card_dir
      type: str
      constraints: "path to directory containing .card.md files"
    - name: callback
      type: Callable[[TierEvent], None]
      constraints: "called after each tier completes; must not raise"
  outputs:
    - name: observer
      type: Observer
      schema: {}
invariants:
  - id: INV-01
    tier: property
    statement: "CardChangeHandler.on_modified ignores events where event.is_directory is True or src_path does not end with '.card.md'"
    rationale: "Only .card.md file modifications should trigger verification; directory events and other file types are filtered out"
  - id: INV-02
    tier: property
    statement: "run_tiered_verification executes tiers in order 0, 1, 2, 3 and stops after the first tier that returns False"
    rationale: "Short-circuit prevents wasting time on deeper tiers when a shallower check already failed"
  - id: INV-03
    tier: property
    statement: "Tier 2 (_run_tier_2) and Tier 3 (_run_tier_3) emit TierEvent with status='skip' when no generated code files exist in the audit directory"
    rationale: "Specs without generated code cannot be property- or formally-verified; skip is the correct signal"
  - id: INV-04
    tier: property
    statement: "Every TierEvent emitted by any tier has tier value in {0, 1, 2, 3}"
    rationale: "Callers index into tier-specific handling; out-of-range values would cause KeyError or silent bugs"
  - id: INV-05
    tier: example
    statement: "DEBOUNCE_SECONDS equals 0.5 (matching the Dafny LSP idle delay from Scout 5 F2)"
    rationale: "The debounce constant is the agreed architectural parameter; changes break latency guarantees"
  - id: INV-06
    tier: property
    statement: "start_watch returns a running Observer with recursive=True monitoring of card_dir"
    rationale: "Specs in subdirectories of .card/ must also be watched; recursive is required"
---

## Intent

The watch daemon monitors a `.card/` directory for `.card.md` file changes and runs streaming tiered verification on each modified file. It implements a 4-tier verification ladder (syntax → structural → property → formal) with a 500ms debounce matching the Dafny LSP idle pattern. Tiers run in increasing cost order, and the first failure short-circuits all deeper tiers, giving sub-second first feedback (Tier 0 fires in <100ms) while formal verification completes in the background when available.

## Acceptance Criteria

### Story 1 — File Watching (P0)

**As a** developer editing specs, **I want** verification to run automatically within 500ms of saving a `.card.md` file, **so that** I get instant feedback without running any command.

1. **Given** start_watch is called, **When** a `.card.md` file is modified, **Then** the callback receives TierEvent(tier=0, ...) within ~600ms
2. **Given** a `.py` file is modified, **When** the event fires, **Then** the callback is NOT called

### Story 2 — Tiered Short-Circuit (P1)

**As a** developer with a syntax error in a spec, **I want** verification to stop after Tier 0 fails, **so that** I'm not waiting for Hypothesis or Dafny on an already-broken file.

1. **Given** a .card.md with no frontmatter, **When** run_tiered_verification is called, **Then** only TierEvent(tier=0, status='fail') is emitted; no tier 1/2/3 events
2. **Given** a valid spec with no generated code, **When** run_tiered_verification is called, **Then** tier 0 and tier 1 pass, then tiers 2 and 3 emit 'skip'

### Edge Cases

- card_dir does not exist → watchdog Observer may raise; caller is responsible for the directory
- .card.md file is unreadable (permission error) → Tier 0 emits TierEvent(status='fail', message contains error)
- Rapid repeated saves within debounce window → only one verification run fires (previous timer cancelled)

## Functional Requirements

- **FR-001**: CardChangeHandler MUST implement a debounce timer of DEBOUNCE_SECONDS (0.5s) per Scout 5 F2
- **FR-002**: run_tiered_verification MUST call each tier function with (card_path, callback) signature
- **FR-003**: Tier 0 MUST complete in under 100ms for normal .card.md files
- **FR-004**: start_watch MUST start the Observer before returning it
- **FR-005**: The debounce timer MUST cancel the previous timer on each new modification event before scheduling a new one
