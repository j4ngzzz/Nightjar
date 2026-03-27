---
card-version: "1.0"
id: immune_spec_updater
title: Immune System - Spec Updater
status: draft
module:
  owns: [append_invariant, build_invariant_entry, _split_card_md]
  depends-on:
    yaml: "PyYAML safe_load, dump"
    pathlib: "Path"
contract:
  inputs:
    - name: card_path
      type: str
      constraints: "path to an existing .card.md file with YAML frontmatter"
    - name: expression
      type: str
      constraints: "verified Python invariant expression"
    - name: explanation
      type: str
      constraints: "human-readable explanation of the invariant"
    - name: origin_failure_id
      type: str | None
      constraints: "optional ID of the production failure that triggered this invariant"
    - name: verification_method
      type: str | None
      constraints: "optional description of how the invariant was verified"
  outputs:
    - name: result
      type: SpecUpdateResult
      schema:
        success: bool
        invariant_id: str
        error: str | None
  errors:
    - SpecUpdateResult(success=False, error=...) on file not found, read failure, YAML parse error, or write failure
invariants:
  - id: INV-01
    tier: property
    statement: "append_invariant with a non-existent card_path returns SpecUpdateResult(success=False) with error containing 'File not found'"
    rationale: "Missing files must produce a clear error rather than creating new files or raising an exception"
  - id: INV-02
    tier: property
    statement: "append_invariant on a valid .card.md file returns SpecUpdateResult(success=True) with invariant_id matching the pattern INV-AUTO-[A-F0-9]{8}"
    rationale: "Auto-generated invariant IDs must use the INV-AUTO- prefix to distinguish them from human-written invariants [REF-C01]"
  - id: INV-03
    tier: property
    statement: "append_invariant preserves the markdown body (everything after the closing triple-dash delimiter) unchanged"
    rationale: "The spec updater operates only on YAML frontmatter; the markdown sections must not be touched"
  - id: INV-04
    tier: property
    statement: "build_invariant_entry always includes id, tier, statement, rationale, and origin keys; tier is always property"
    rationale: "Auto-mined invariants always go into the property tier [REF-C01]; the origin block provides the audit trail required by [REF-C09]"
  - id: INV-05
    tier: property
    statement: "build_invariant_entry origin dict always contains 'timestamp' in ISO 8601 UTC format; adds 'failure_id' only when origin_failure_id is not None; adds 'verification_method' only when verification_method is not None"
    rationale: "Optional fields must not pollute entries when absent; timestamp is always required for the audit trail"
  - id: INV-06
    tier: property
    statement: "append_invariant called twice on the same card_path produces a file with exactly two additional invariant entries in the invariants list"
    rationale: "The function is append-only and idempotent per call; each call adds exactly one entry"
---

## Intent

Close the immune system loop by appending verified invariants back into `.card.md` specification files. Takes a verified invariant expression (confirmed by CrossHair and/or Hypothesis), builds a structured YAML entry with an auto-generated `INV-AUTO-` ID and origin audit metadata, then atomically updates the `invariants:` list in the file's YAML frontmatter while preserving the markdown body unchanged.

This implements the append-only history principle from [REF-C09]: production failures become permanent spec entries so future builds enforce the hard-won invariants automatically. The `INV-AUTO-` prefix distinguishes immune-system-generated entries from human-authored ones, making provenance auditable.

## Acceptance Criteria

### Story 1 — Verified Invariant Lands in the Spec (P0)

**As a** production failure handler, **I want** a verified invariant to be appended to the .card.md, **so that** future builds enforce it.

1. **Given** a valid .card.md with existing invariants, **When** append_invariant is called with a verified expression, **Then** the file now contains the new invariant with id starting "INV-AUTO-" and tier="property"
2. **Given** a .card.md with no invariants key, **When** append_invariant is called, **Then** creates invariants list and appends successfully

### Story 2 — File Errors Produce Clean Results (P0)

**As a** pipeline orchestrator, **I want** file errors to return SpecUpdateResult(success=False), **so that** I can log them without crashing the cycle.

1. **Given** card_path="/nonexistent/path.card.md", **When** append_invariant is called, **Then** returns SpecUpdateResult(success=False, error contains "File not found")

### Story 3 — Markdown Body Is Preserved (P1)

**As a** spec author, **I want** my markdown sections to survive invariant appends, **so that** the human-readable documentation is never corrupted.

1. **Given** a .card.md with "## Intent\n\nSome intent text", **When** append_invariant is called, **Then** the output file still contains "## Intent\n\nSome intent text" verbatim

## Functional Requirements

- **FR-001**: append_invariant MUST use yaml.safe_load for parsing; MUST NOT use yaml.load (unsafe)
- **FR-002**: append_invariant MUST use yaml.dump with sort_keys=False to preserve key order
- **FR-003**: build_invariant_entry MUST generate invariant_id as "INV-AUTO-" + uuid4().hex[:8].upper()
- **FR-004**: append_invariant MUST reconstruct the file as f"{prefix}---\n{new_frontmatter}---{body}" exactly
- **FR-005**: append_invariant MUST return SpecUpdateResult(success=False, error=...) for YAML parse errors; MUST NOT raise yaml.YAMLError
- **FR-006**: append_invariant MUST NOT create the file if it does not exist
