---
card-version: "1.0"
id: ship
title: Artifact Signing with Provenance
status: draft
module:
  owns: [hash_artifact(), build_provenance(), write_provenance()]
  depends-on: {}
  excludes:
    - "Deployment — only generates provenance record, does not push artifacts"
    - "Verification — reads verification results but does not run them"
invariants:
  - id: INV-01
    tier: property
    statement: "hash_artifact() returns an empty string when the path does not exist; never raises FileNotFoundError"
    rationale: "A missing artifact must produce a detectable (empty) hash rather than crashing the build"
  - id: INV-02
    tier: property
    statement: "For directory artifacts, hash_artifact() includes relative file paths in the hash computation (sorted by posix path), making the hash sensitive to both file content and directory structure"
    rationale: "A rename or move within the output directory must invalidate the hash"
  - id: INV-03
    tier: property
    statement: "Provenance.timestamp is always a UTC ISO-8601 string; it is set in __post_init__ if not provided at construction time"
    rationale: "Every provenance record must be timestamped for audit ordering"
  - id: INV-04
    tier: property
    statement: "write_provenance() creates parent directories as needed and writes valid JSON; the output is pretty-printed with indent=2"
    rationale: "Human-readable, git-diff-friendly provenance is required for compliance review"
  - id: INV-05
    tier: property
    statement: "build_provenance() always calls hash_artifact() on the given path and stores the result in Provenance.artifact_hash"
    rationale: "The provenance record is only trustworthy if it includes a content hash of the actual artifact"
---

## Intent

After a successful build, compute the SHA-256 hash of the output artifact and write provenance metadata (model, verification status, stage counts, target, timestamp) to `.card/verify.json`. This creates an auditable record tying generated code to its verification results.

## Acceptance Criteria

### Story 1 — Hash an Artifact

**As a** build pipeline, **I want** to hash build artifacts, **so that** provenance records are tamper-evident.

1. **Given** a regular file, **When** `hash_artifact()` is called, **Then** returns the SHA-256 hex of its raw bytes
2. **Given** a directory with files `a.py` and `b/c.py`, **When** `hash_artifact()` is called, **Then** hashes files sorted by relative posix path and includes path strings in hash input
3. **Given** a path that does not exist, **When** `hash_artifact()` is called, **Then** returns `""`

### Story 2 — Build and Write Provenance

1. **Given** verification passed with 5/5 stages, **When** `build_provenance()` is called, **Then** `Provenance.verified is True` and `stages_passed == 5`
2. **Given** a `Provenance` object, **When** `write_provenance()` is called with path `.card/verify.json`, **Then** a valid JSON file exists at that path with all fields present
3. **Given** `.card/` directory does not exist, **When** `write_provenance()` is called, **Then** creates the directory and writes the file successfully

## Functional Requirements

- **FR-001**: MUST compute SHA-256 for both file and directory artifacts
- **FR-002**: MUST include relative posix paths in directory hash to detect structural changes
- **FR-003**: MUST set `timestamp` to `datetime.now(timezone.utc).isoformat()` when not provided
- **FR-004**: MUST write JSON with `indent=2` and a trailing newline
- **FR-005**: MUST create parent directories with `mkdir(parents=True, exist_ok=True)` before writing
- **FR-006**: Provenance fields: `artifact_hash`, `model`, `verified`, `stages_passed`, `stages_total`, `target`, `timestamp`
