---
card-version: "1.0"
id: lock
title: Sealed Dependency Manifest Generator
status: draft
module:
  owns: [scan_project_imports(), resolve_package_versions(), compute_package_hash(), generate_lock_file(), parse_lock_entry()]
  depends-on: {}
  excludes:
    - "CVE scanning — handled by pip-audit (REF-T06)"
    - "Hash verification at build time — handled by stages/deps.py"
invariants:
  - id: INV-01
    tier: property
    statement: "Every entry written to deps.lock has the format `package==version --hash=sha256:HASH` where HASH is a non-empty hex string"
    rationale: "The sealed manifest format must be parseable by stages/deps.py; entries without hashes are silently dropped"
  - id: INV-02
    tier: property
    statement: "compute_package_hash() always uses SHA-256 via hashlib.sha256(); no other hash algorithm is used"
    rationale: "The lock line format specifies sha256: prefix explicitly — algorithm must be consistent"
  - id: INV-03
    tier: property
    statement: "scan_project_imports() never yields stdlib module names (checked against sys.stdlib_module_names)"
    rationale: "Stdlib packages have no version or hash and must not appear in the manifest"
  - id: INV-04
    tier: property
    statement: "scan_project_imports() skips directories in _SKIP_DIRS and any directory whose name starts with '.'"
    rationale: "Virtual environments and build artifacts must not pollute the dependency scan"
  - id: INV-05
    tier: property
    statement: "parse_lock_entry() returns None for any line that does not match the `package==version [--hash=algo:hex]` pattern"
    rationale: "Comment lines and blank lines in deps.lock must not raise exceptions"
  - id: INV-06
    tier: property
    statement: "generate_lock_file() writes entries in sorted package-name order"
    rationale: "Deterministic output ensures stable git diffs when lock file is regenerated"
---

## Intent

Scan the project source tree for third-party imports, resolve installed versions via `importlib.metadata`, compute SHA-256 hashes of distribution metadata, and write a `deps.lock` sealed manifest. This prevents supply-chain attacks from AI-hallucinated packages [REF-P27] by ensuring only human-approved, installed packages enter the build.

## Acceptance Criteria

### Story 1 — Generate Lock File

**As a** developer, **I want** to run `nightjar lock` and get a deps.lock, **so that** my build is protected from hallucinated dependencies.

1. **Given** a project with `import click` in source, **When** `generate_lock_file()` is called, **Then** `deps.lock` contains a `click==<version> --hash=sha256:<hash>` line
2. **Given** `import os` (stdlib), **When** `generate_lock_file()` is called, **Then** no `os` entry appears in deps.lock
3. **Given** a `.venv/` directory containing Python files, **When** scanning, **Then** those files are skipped entirely

### Story 2 — Parse Lock Entry

1. **Given** `"click==8.1.7 --hash=sha256:abc123"`, **When** `parse_lock_entry()` is called, **Then** returns `LockEntry(package="click", version="8.1.7", hash="abc123")`
2. **Given** `"# comment line"`, **When** `parse_lock_entry()` is called, **Then** returns `None`
3. **Given** `""` (empty string), **When** `parse_lock_entry()` is called, **Then** returns `None`

### Story 3 — Hash Integrity

1. **Given** package `click`, **When** `compute_package_hash()` is called, **Then** returns a 64-char lowercase hex string (SHA-256)
2. **Given** a package not installed, **When** `compute_package_hash()` is called, **Then** returns `""`

## Functional Requirements

- **FR-001**: MUST use SHA-256 for all package hashing via `hashlib.sha256()`
- **FR-002**: MUST hash the distribution METADATA file; fall back to `PKG-INFO`; fall back to `name==version` string
- **FR-003**: MUST resolve import-to-package name mappings (e.g. `yaml` → `pyyaml`, `cv2` → `opencv-python`)
- **FR-004**: MUST skip directories: `.venv`, `venv`, `.env`, `env`, `.git`, `__pycache__`, `node_modules`, `.tox`, `.nox`, `dist`, `build`, `.card`, and all dot-prefixed directories
- **FR-005**: MUST write deps.lock with header comments and entries sorted by package name
- **FR-006**: MUST only include entries where `compute_package_hash()` returns a non-empty string (packages with no hash are excluded)
