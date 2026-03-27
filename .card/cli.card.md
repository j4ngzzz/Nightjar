---
card-version: "1.0"
id: cli
title: Nightjar CLI
status: active
module:
  owns: [main, init, verify, generate, build, ship, retry, lock, explain, auto, watch, badge, optimize]
  depends-on:
    click: "click>=8.0"
    nightjar.config: "internal"
    nightjar.parser: "internal"
    nightjar.generator: "internal"
    nightjar.verifier: "internal"
    nightjar.retry: "internal"
    nightjar.lock: "internal"
    nightjar.explain: "internal"
    nightjar.display: "internal"
contract:
  inputs:
    - name: argv
      type: list[str]
      constraints: "CLI arguments passed by the shell"
  outputs:
    - name: exit_code
      type: int
      schema: {}
  errors:
    - SystemExit
invariants:
  - id: INV-01
    tier: property
    statement: "The CLI exits with a code in {0, 1, 2, 3, 4, 5}; no other exit code is ever produced"
    rationale: "All exit paths use the named EXIT_* constants defined at module level"
  - id: INV-02
    tier: property
    statement: "verify exits 0 when result.verified is True and exits 1 when result.verified is False"
    rationale: "CI pipelines depend on the exit code being a reliable pass/fail signal"
  - id: INV-03
    tier: example
    statement: "init refuses to overwrite an existing .card.md file and exits 2 (EXIT_CONFIG_ERROR)"
    rationale: "Prevents accidental spec loss; user must delete or use --force explicitly"
  - id: INV-04
    tier: property
    statement: "Model name is resolved in priority order: --model CLI flag > NIGHTJAR_MODEL env var > config file > default constant"
    rationale: "Anti-pattern: DO NOT hardcode model names — all LLM calls must be model-agnostic"
  - id: INV-05
    tier: example
    statement: "build --target only accepts values in {py, js, ts, go, java, cs}; any other value causes Click to exit with a usage error"
    rationale: "Target language is constrained via click.Choice to prevent invalid artifact generation"
  - id: INV-06
    tier: example
    statement: "retry exits 5 (EXIT_MAX_RETRIES) when the retry loop exhausts all attempts without passing verification"
    rationale: "Exhausted retries must trigger human escalation, not a generic failure exit code"
  - id: INV-07
    tier: property
    statement: "When invoked without a subcommand, main prints help text and exits 0"
    rationale: "ctx.invoked_subcommand is None branch calls click.echo(ctx.get_help())"
---

## Intent

The CLI is the primary entry point for Nightjar. It exposes twelve subcommands (init, generate, verify, build, ship, retry, lock, explain, auto, watch, badge, optimize) implemented as Click commands grouped under a single `main` group. The CLI does not implement verification logic itself — it delegates to the appropriate internal modules (verifier, generator, retry, lock, explain) and translates their results into exit codes and terminal messages.

## Acceptance Criteria

### Story 1 — Verification Workflow (P0)

**As a** developer, **I want** `nightjar verify --spec my.card.md` to run the 5-stage pipeline and exit 0/1 based on pass/fail, **so that** I can wire it into CI.

1. **Given** a valid spec path, **When** `nightjar verify --spec path.card.md` is run and all stages pass, **Then** the CLI prints "VERIFIED -- all stages passed" and exits 0
2. **Given** a valid spec path with a failing stage, **When** `nightjar verify --spec path.card.md` runs, **Then** the CLI prints "FAILED -- verification did not pass" and exits 1

### Story 2 — Spec Scaffolding (P1)

**As a** developer, **I want** `nightjar init payment` to create `.card/payment.card.md`, **so that** I have a valid starting template.

1. **Given** no existing spec, **When** `nightjar init payment` runs, **Then** `.card/payment.card.md` is created with the standard template
2. **Given** an existing spec, **When** `nightjar init payment` runs again, **Then** the CLI exits 2 and prints an error without overwriting the file

### Edge Cases

- Missing --spec argument for verify/generate/build → Click prints usage error
- LLM call failure → exits 4 (EXIT_LLM_ERROR)
- Max retries reached in retry loop → exits 5 (EXIT_MAX_RETRIES)
- Verifier or retry module not importable → exits 2 with error message

## Functional Requirements

- **FR-001**: CLI MUST define exactly the exit codes 0–5 as named constants (EXIT_PASS through EXIT_MAX_RETRIES)
- **FR-002**: All LLM calls MUST go through litellm via the model-resolver (_get_model) — never call provider APIs directly
- **FR-003**: The verify command MUST accept --spec/-s/-c as aliases for the contract path argument
- **FR-004**: The build command MUST accept --target restricted to {py, js, ts, go, java, cs} via click.Choice
- **FR-005**: The init command MUST refuse to overwrite an existing spec without --force
- **FR-006**: All subcommands MUST load config via _load_config() on invocation through the Click context object
