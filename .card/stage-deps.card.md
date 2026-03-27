---
card-version: "1.0"
id: stage_deps
title: Stage 1 - Dependency Manifest Check
status: draft
invariants:
  - id: INV-DEPS-01
    tier: property
    statement: "stage=1 and name='deps' on every returned StageResult"
    rationale: "Stage identity is fixed — consumers route on stage and name fields."
  - id: INV-DEPS-02
    tier: property
    statement: "status is FAIL when any third-party import in the generated code is not present in deps.lock; each error dict MUST contain a 'package' key equal to the disallowed import name and a 'message' key containing the string 'not in sealed manifest'; one error per unique disallowed package (sorted, deduplicated)"
    rationale: "Every unrecognised package is a potential hallucinated or slopsquatted dependency — must be rejected before install. Exact error structure is required so downstream tooling can parse and display actionable rejection reasons."
  - id: INV-DEPS-03
    tier: property
    statement: "stdlib modules are never flagged as disallowed regardless of deps.lock contents"
    rationale: "Standard library modules do not need to appear in deps.lock; treating them as third-party would produce false positives."
  - id: INV-DEPS-04
    tier: property
    statement: "import-name to package-name aliasing is applied before allowlist lookup (e.g., 'yaml' resolves to 'pyyaml')"
    rationale: "Many packages have import names that differ from PyPI names; the alias map prevents false positives for well-known packages."
  - id: INV-DEPS-05
    tier: property
    statement: "when a package's hash changes without a version change between baseline and current deps.lock, detect_drift MUST return an entry with drift_type='integrity' and severity='high'; run_deps_check MUST return FAIL with an error dict containing type='integrity_drift', severity='high', and the affected package name; version-only drift, added packages, and removed packages MUST NOT cause FAIL"
    rationale: "Hash change at same version is the classical supply chain attack signal (event-stream, XZ utils); the exact drift_type and severity fields are required so consumers can distinguish supply chain alerts from routine update noise."
  - id: INV-DEPS-06
    tier: property
    statement: "status is FAIL when deps.lock file does not exist, with error message referencing 'nightjar lock'"
    rationale: "The sealed manifest is mandatory; absent manifest means the security boundary has not been established."
---

## Intent

Stage 1 enforces the sealed dependency manifest (`deps.lock`). It prevents AI-hallucinated or slopsquatted packages from entering the build by comparing every third-party import in generated code against an explicit allowlist. Research shows 19.7% of AI-generated dependencies are hallucinated (`[REF-P27]`); this stage is the last line of defence before those packages could be installed.

Stage 1 also runs optional drift detection when a baseline `deps.lock` snapshot is provided. An integrity drift event — where a package's hash changes without a version bump — is treated as a potential supply chain attack (the event-stream and XZ utils attack pattern) and causes a FAIL. Version-only changes are informational.

## Acceptance Criteria

- Returns `StageResult(stage=1, name="deps", status=PASS)` when: the code file exists and parses as valid AST, `deps.lock` exists, all third-party imports resolve to packages in `deps.lock`, and no integrity drift is detected.
- Returns `StageResult(stage=1, name="deps", status=FAIL, errors=[...])` for: missing code file, missing deps.lock, any unrecognised third-party import, or integrity drift in the baseline comparison.
- Disallowed import errors include `{"message": "...", "package": "<name>"}` for each unique disallowed package (sorted, deduplicated).
- Integrity drift errors include `{"type": "integrity_drift", "package": ..., "version": ..., "baseline_hash": ..., "current_hash": ..., "severity": "high", ...}`.
- `sys.stdlib_module_names` is used to identify standard library modules; multi-level imports are resolved by their root component.

## Functional Requirements

### FR-DEPS-01: Code File Validation
Checks that `code_path` exists and can be read. If not, returns FAIL immediately.

### FR-DEPS-02: deps.lock Existence
Checks that `deps_lock_path` exists. If not, returns FAIL with a message instructing the user to run `nightjar lock`.

### FR-DEPS-03: Import Extraction via AST
Parses the code file as a Python AST and walks all `ast.Import` and `ast.ImportFrom` nodes. Collects the root module name from each (first segment before `.`).

### FR-DEPS-04: Allowlist Check
For each extracted import, skips it if it is a stdlib module. Otherwise, looks it up directly in the `deps.lock` package dict (case-insensitive), then via the `_IMPORT_TO_PACKAGE` alias map. If neither matches, the package is disallowed.

### FR-DEPS-05: deps.lock Parsing
Parses `deps.lock` line by line. Each non-comment, non-empty line must match `package==version [--hash=algorithm:hex]`. Package names are stored lowercase. Missing hash fields are stored as empty strings (not an error).

### FR-DEPS-06: Drift Detection (optional)
When `baseline_lock_path` is provided and the baseline file is non-empty, runs sbomlyze-style drift detection. Classifies changes as: `integrity` (hash changed, version same — HIGH severity), `version` (version changed — info), `added` (new package — info), `removed` (package gone — info). Only `integrity` events cause FAIL.

## Test Scenarios

These concrete input/output pairs exercise INV-DEPS-02 and INV-DEPS-05 and MUST be covered by the PBT harness:

- **Allowlist bypass (INV-DEPS-02):** Given Python code containing `import fake_package` where `fake_package` is not present in deps.lock → `run_deps_check` returns `StageResult(stage=1, name='deps', status=FAIL)` with `errors` list containing exactly one dict with `package='fake_package'` and `message` containing `'not in sealed manifest'`.

- **Multi-import allowlist bypass (INV-DEPS-02):** Given code importing both `fake_package` and `evil_lib`, neither in deps.lock → FAIL with two error dicts, one per package, sorted alphabetically: `[{'package': 'evil_lib', ...}, {'package': 'fake_package', ...}]`.

- **Integrity drift (INV-DEPS-05):** Given baseline deps.lock with `requests==2.31.0 --hash=sha256:abc123` and current deps.lock with `requests==2.31.0 --hash=sha256:xyz789` (same version, different hash) → `detect_drift` returns a list containing one entry with `drift_type='integrity'`, `severity='high'`, `package='requests'`; `run_deps_check` returns FAIL with an error dict containing `type='integrity_drift'` and `severity='high'`.

- **Version-only drift (INV-DEPS-05):** Given baseline with `requests==2.30.0` and current with `requests==2.31.0` (version bumped) → `detect_drift` returns entry with `drift_type='version'`, `severity='info'`; `run_deps_check` returns PASS (not FAIL).

- **Added package drift (INV-DEPS-05):** Given baseline without `newpkg` and current deps.lock with `newpkg==1.0.0` → `detect_drift` returns entry with `drift_type='added'`, `severity='info'`; `run_deps_check` returns PASS (not FAIL).
