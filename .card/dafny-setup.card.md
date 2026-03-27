---
card-version: "1.0"
id: dafny_setup
title: Dafny Binary Setup and Detection
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "find_dafny returns a non-None path if and only if shutil.which('dafny') finds a binary OR DAFNY_PATH env var points to an existing file"
    rationale: "Two-step lookup ensures PATH-installed and manually configured Dafny installations are both found"
  - id: INV-02
    tier: property
    statement: "find_dafny returns None when 'dafny' is absent from PATH and DAFNY_PATH is unset or points to a non-existent file"
    rationale: "None return is the sentinel for 'not found' — callers must handle this before invoking Dafny"
  - id: INV-03
    tier: example
    statement: "ensure_dafny raises RuntimeError with an install URL when find_dafny returns None"
    rationale: "Clear error message with https://github.com/dafny-lang/dafny/releases and PATH/DAFNY_PATH instructions reduces developer friction"
  - id: INV-04
    tier: example
    statement: "ensure_dafny returns the same path as find_dafny when Dafny is present"
    rationale: "ensure_dafny is a thin wrapper — it delegates to find_dafny and raises on None"
  - id: INV-05
    tier: property
    statement: "get_dafny_version uses subprocess.run with timeout=10 seconds — never blocks indefinitely"
    rationale: "Version check must not hang the CI pipeline; 10-second timeout is the enforced bound"
---

## Intent

Provides portable Dafny binary detection for Stage 4 (formal verification).
Abstracts platform differences behind a two-step lookup: standard PATH first,
then the `DAFNY_PATH` environment variable for non-standard installs.

Keeps Stage 4 (formal.py) free of binary-location logic.

References:
- [REF-T01] Dafny — verification-aware programming language
- https://github.com/dafny-lang/dafny/releases

## Acceptance Criteria

- [ ] `find_dafny()` returns the binary path when `dafny` is on PATH
- [ ] `find_dafny()` returns the binary path when `DAFNY_PATH` points to an existing file
- [ ] `find_dafny()` returns `None` when neither lookup succeeds
- [ ] `ensure_dafny()` raises `RuntimeError` with install URL when Dafny is absent
- [ ] `get_dafny_version()` completes within 10 seconds (subprocess timeout enforced)
- [ ] `get_dafny_version()` returns the stripped stdout string from `dafny --version`

## Functional Requirements

1. **find_dafny() -> Optional[str]** — two-step lookup:
   - Step 1: `shutil.which("dafny")` — returns path if found on PATH
   - Step 2: `os.environ.get("DAFNY_PATH")` — returns path if env var set and `os.path.isfile(path)` is True
   - Returns `None` if both steps fail
2. **ensure_dafny() -> str** — calls `find_dafny()`; if result is not None returns it; otherwise raises `RuntimeError` with message including install URL and PATH/DAFNY_PATH instructions
3. **get_dafny_version(dafny_path: str) -> str** — runs `[dafny_path, "--version"]` with `subprocess.run(capture_output=True, text=True, timeout=10)`; returns `result.stdout.strip()`
