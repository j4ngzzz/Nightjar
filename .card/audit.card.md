---
card-version: "1.0"
id: audit
title: Audit Branch — Read-Only Generated Code Archive
status: draft
module:
  owns: [get_audit_path(), archive_artifact(), list_audited_modules(), is_audit_current()]
  depends-on: {}
  excludes:
    - "Manual edits — audit files must never be manually modified"
    - "Verification — only archives already-verified artifacts"
invariants:
  - id: INV-01
    tier: property
    statement: "Every archived file has read-only permissions (no write bits set) after archive_artifact() completes"
    rationale: "REF-C07: generated code is read-only; write bits must be cleared to enforce the no-manual-edit policy at the filesystem level"
  - id: INV-02
    tier: property
    statement: "Every archived file contains a 'GENERATED FROM SPEC — DO NOT EDIT' header comment prepended before the source content (unless already present)"
    rationale: "The header is the machine-readable marker that distinguishes generated from hand-written code"
  - id: INV-03
    tier: property
    statement: "archive_artifact() returns False (not an exception) when the source file does not exist"
    rationale: "Missing source is a pipeline state error; the audit module must report it cleanly"
  - id: INV-04
    tier: property
    statement: "is_audit_current() compares SHA-256(source_content) against SHA-256(audit_content_with_header_stripped); returns False if either file is missing"
    rationale: "Drift detection must be header-agnostic — only the generated logic matters for freshness"
  - id: INV-05
    tier: property
    statement: "get_audit_path() maps targets {py, js, ts, go, java, cs, dfy} to extensions {.py, .js, .ts, .go, .java, .cs, .dfy}; unknown targets use '.{target}' as extension"
    rationale: "Audit paths must be deterministic and consistent across the pipeline"
---

## Intent

After every successful build, copy generated code to `.card/audit/` with a language-appropriate "DO NOT EDIT" header and read-only filesystem permissions. This creates a git-trackable compliance record of every verified generation, enforcing the principle that generated code is never manually modified [REF-C07].

## Acceptance Criteria

### Story 1 — Archive an Artifact

**As a** build pipeline, **I want** generated Python archived to `.card/audit/`, **so that** the compliance record is immutable.

1. **Given** `payment.py` generated successfully, **When** `archive_artifact("payment.py", "payment", "py", ".card/audit/")` is called, **Then** `.card/audit/payment.py` exists with read-only permissions and the DO-NOT-EDIT header
2. **Given** source does not exist, **When** `archive_artifact()` is called, **Then** returns `False`
3. **Given** existing read-only audit file, **When** `archive_artifact()` is called again, **Then** the file is updated (write permission temporarily granted, then revoked)

### Story 2 — Header Idempotency

1. **Given** source already contains `"GENERATED FROM SPEC"`, **When** `archive_artifact()` is called, **Then** the header is NOT prepended again

### Story 3 — Currency Check

1. **Given** source and audit file have identical content (modulo header), **When** `is_audit_current()` is called, **Then** returns `True`
2. **Given** source was regenerated and differs from audit, **When** `is_audit_current()` is called, **Then** returns `False`
3. **Given** audit file is missing, **When** `is_audit_current()` is called, **Then** returns `False`

### Story 4 — List Audited Modules

1. **Given** `.card/audit/` contains `payment.py`, `auth.go`, **When** `list_audited_modules()` is called, **Then** returns `["auth", "payment"]` (sorted, stems only)

## Functional Requirements

- **FR-001**: MUST set file permissions to `S_IRUSR | S_IRGRP | S_IROTH` (read-only) after every archive
- **FR-002**: MUST temporarily grant write permission before overwriting an existing read-only file
- **FR-003**: MUST prepend language-appropriate header comment only if `"GENERATED FROM SPEC"` is not already in content
- **FR-004**: MUST support targets: py (.py), js (.js), ts (.ts), go (.go), java (.java), cs (.cs), dfy (.dfy)
- **FR-005**: `is_audit_current()` MUST strip header lines (starting with `#` or `//`) and leading blank lines before hashing audit content
- **FR-006**: MUST create audit directory with `mkdir(parents=True, exist_ok=True)` if it does not exist
