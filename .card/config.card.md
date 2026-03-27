---
card-version: "1.0"
id: config
title: Nightjar Configuration Loader
status: draft
module:
  owns: [load_config, get_model, get_specs_dir]
  depends-on:
    tomllib: "standard library (Python 3.11+) — TOML parsing"
    dotenv: "optional — python-dotenv for .env loading; falls back to manual parsing"
    os: "standard library — environment variable access"
contract:
  inputs:
    - name: project_root
      type: str
      constraints: "valid directory path; defaults to '.'"
    - name: cli_model
      type: str | None
      constraints: "optional CLI-supplied model name"
  outputs:
    - name: config
      type: dict
      schema: {card: {version, default_target, default_model, max_retries, verification_timeout}, paths: {specs, dist, audit, cache}}
    - name: model
      type: str
      schema: {non-empty: true}
  errors:
    - OSError
invariants:
  - id: INV-01
    tier: property
    statement: "get_model respects strict precedence: cli_model > NIGHTJAR_MODEL env var > config['card']['default_model'] > hardcoded 'deepseek/deepseek-chat'"
    rationale: "Model resolution must be deterministic and follow the documented priority chain"
  - id: INV-02
    tier: property
    statement: "load_config returns DEFAULT_CONFIG when neither nightjar.toml nor a toml file exists at project_root"
    rationale: "The system must work out-of-the-box with no configuration files present"
  - id: INV-03
    tier: property
    statement: "load_config loads the .env file into os.environ before returning if .env exists at project_root"
    rationale: "API keys in .env must be available in the environment for all subsequent LLM calls"
  - id: INV-04
    tier: property
    statement: "get_model never returns an empty string or None"
    rationale: "Every code path in get_model terminates with a non-empty string (hardcoded fallback guarantees this)"
  - id: INV-05
    tier: safety
    statement: "_load_dotenv_simple falls back to manual KEY=VALUE parsing when python-dotenv is not installed"
    rationale: "python-dotenv is an optional dependency; the config loader must work in minimal environments"
---

## Intent

Load project configuration from two sources: `.env` files for API keys (via python-dotenv with fallback to manual parsing), and `nightjar.toml` for project settings (via tomllib). Provide model resolution with a four-level precedence chain: CLI flag > NIGHTJAR_MODEL env var > config default > hardcoded fallback. All LLM calls in the system use `get_model()` to remain model-agnostic ([REF-T16]).

## Acceptance Criteria

### Story 1 — Model Resolution (P0)

**As a** CLI, **I want** model selection to follow a clear precedence chain, **so that** users can override the model at any level.

1. **Given** cli_model="gpt-4o" and NIGHTJAR_MODEL="claude-3", **When** get_model is called, **Then** returns "gpt-4o"
2. **Given** cli_model=None and NIGHTJAR_MODEL="claude-3", **When** get_model is called, **Then** returns "claude-3"
3. **Given** cli_model=None, no env var, config={'card': {'default_model': 'gemini'}}, **When** get_model is called, **Then** returns "gemini"
4. **Given** cli_model=None, no env var, no config, **When** get_model is called, **Then** returns "deepseek/deepseek-chat"

### Story 2 — Config Loading (P0)

**As a** project, **I want** config to fall back gracefully when files are missing, **so that** a fresh clone works without setup.

1. **Given** no nightjar.toml exists, **When** load_config is called, **Then** returns DEFAULT_CONFIG
2. **Given** .env file exists with MY_KEY=secret, **When** load_config is called, **Then** os.environ["MY_KEY"] == "secret"

## Functional Requirements

- **FR-001**: MUST load .env before returning config (side effect on os.environ)
- **FR-002**: MUST return a copy of DEFAULT_CONFIG (not the shared dict) when no toml file exists
- **FR-003**: get_model MUST never return empty string or None
- **FR-004**: _load_dotenv_simple MUST handle comment lines (starting with #) and blank lines silently
- **FR-005**: _load_dotenv_simple MUST strip surrounding quotes from values (single or double)
