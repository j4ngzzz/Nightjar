---
card-version: "1.0"
id: compiler
title: Dafny Compile-to-Target-Language Wrapper
status: draft
module:
  owns: [validate_target(), compile_dafny()]
  depends-on:
    dafny: "4.x"
  excludes:
    - "Verification — compilation only runs after verify passes"
    - "Code generation — input must already be a .dfy file"
invariants:
  - id: INV-01
    tier: property
    statement: "compile_dafny() only accepts targets in {py, js, go, java, cs}; any other value raises UnsupportedTargetError before subprocess is invoked"
    rationale: "Target validation is a hard gate — no subprocess should ever be launched for an invalid target"
  - id: INV-02
    tier: property
    statement: "On success (dafny returncode == 0), CompileResult.success is True and output_path is non-empty; on failure, output_path is the empty string"
    rationale: "Callers must not act on an output_path that was never written"
  - id: INV-03
    tier: property
    statement: "On subprocess timeout, CompileResult.success is False and stderr contains the timeout duration message"
    rationale: "Timeout must not be silently swallowed; callers need to distinguish timeout from compiler error"
  - id: INV-04
    tier: property
    statement: "The dafny binary path respects the DAFNY_PATH environment variable; defaults to 'dafny' when not set"
    rationale: "CI environments and custom Dafny installations must be supported without code changes"
  - id: INV-05
    tier: property
    statement: "output_path is always Path(output_dir) / stem(dfy_path) — never an arbitrary path"
    rationale: "Predictable output location is required by the audit archival pipeline"
---

## Intent

Wrap the Dafny compiler CLI to translate verified `.dfy` modules into target language artifacts (Python, JavaScript, Go, Java, C#). Compilation only runs after the 5-stage verification pipeline passes; this module is not responsible for verification itself.

## Acceptance Criteria

### Story 1 — Compile a Verified Module

**As a** CARD pipeline, **I want** to compile `module.dfy` to Python, **so that** the verified logic is available as a runnable artifact.

1. **Given** a valid `.dfy` file and target `py`, **When** `compile_dafny()` is called, **Then** `dafny build module.dfy --target:py --output:<output_dir/module>` is executed
2. **Given** target `java`, **When** `compile_dafny()` is called, **Then** `CompileResult.target == "java"`
3. **Given** Dafny exits 0, **When** `compile_dafny()` returns, **Then** `CompileResult.success is True` and `output_path` is non-empty

### Story 2 — Reject Unsupported Targets

1. **Given** target `rust`, **When** `compile_dafny()` is called, **Then** `UnsupportedTargetError` is raised before any subprocess is launched
2. **Given** target `""` (empty string), **When** `compile_dafny()` is called, **Then** `UnsupportedTargetError` is raised

### Story 3 — Handle Failures Gracefully

1. **Given** Dafny exits non-zero, **When** `compile_dafny()` returns, **Then** `success is False`, `output_path == ""`, and `stderr` contains error output
2. **Given** compilation exceeds `timeout` seconds, **When** `compile_dafny()` returns, **Then** `success is False` and `stderr` contains the timeout message

## Functional Requirements

- **FR-001**: MUST validate target against `SUPPORTED_TARGETS` frozenset `{py, js, go, java, cs}` before invoking dafny
- **FR-002**: MUST read `DAFNY_PATH` env var for binary location; fall back to `"dafny"` if unset
- **FR-003**: MUST capture stdout and stderr from the subprocess and include in `CompileResult`
- **FR-004**: MUST enforce `timeout` (default 120 s) via `subprocess.run(timeout=...)`; on `TimeoutExpired`, return `CompileResult.success=False`
- **FR-005**: MUST derive `output_path` as `Path(output_dir) / Path(dfy_path).stem`
