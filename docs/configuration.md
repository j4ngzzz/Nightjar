# Nightjar Configuration Reference

Complete reference for `nightjar.toml` project settings and all environment variables recognized by the Nightjar pipeline.

---

## Table of Contents

1. [nightjar.toml Reference](#nightjartoml-reference)
2. [Model Selection Precedence](#model-selection-precedence)
3. [Environment Variables](#environment-variables)
   - [Model & LLM](#model--llm)
   - [Verification Pipeline](#verification-pipeline)
   - [Property-Based Testing (Stage 3)](#property-based-testing-stage-3)
   - [Repair & CEGIS Loop](#repair--cegis-loop)
   - [Canvas Web Server](#canvas-web-server)
   - [Shadow CI / GitHub Actions](#shadow-ci--github-actions)
   - [External Tools](#external-tools)
   - [GitHub Actions Platform Variables](#github-actions-platform-variables)
4. [Optional Extras](#optional-extras)
5. [Exit Codes](#exit-codes)
6. [Open Tasks](#open-tasks)

---

## nightjar.toml Reference

Place `nightjar.toml` in the project root. All keys are optional — any key you omit falls back to the default shown below.

```toml
# nightjar.toml — Nightjar project configuration
# Reference: [REF-T17] Click CLI framework

[card]
version = "1.0"                      # Spec format version (informational)
default_target = "py"                # Compile target: py | js | ts | go | java | cs
default_model = "claude-sonnet-4-6"  # LLM model used when no CLI flag or env var is set
max_retries = 5                      # CEGIS repair loop retry budget
verification_timeout = 30            # Per-stage timeout in seconds

[paths]
specs = ".card/"                     # Directory where .card.md spec files live
dist = "dist/"                       # Compiled verified output
audit = ".card/audit/"               # READ-ONLY generated code archive
cache = ".card/cache/"               # Verification result cache (hash → verified)
```

### Key Details

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `card.version` | string | `"1.0"` | Spec format version. Informational; not currently enforced by the pipeline. |
| `card.default_target` | string | `"py"` | Target language for `nightjar build`. Passed to the compiler. |
| `card.default_model` | string | `"claude-sonnet-4-6"` | Third-priority model fallback. See [precedence chain](#model-selection-precedence). |
| `card.max_retries` | int | `5` | Maximum CEGIS iterations before the pipeline gives up and escalates to human review (exit code 5). |
| `card.verification_timeout` | int | `30` | Intended per-stage timeout in seconds. Currently present in config schema and referenced in error messages (`src/nightjar/explain.py`) but not yet enforced as an active kill timer in the pipeline. Reserve this key — future stages will honour it. |
| `paths.specs` | string | `".card/"` | Root directory scanned for `*.card.md` files. |
| `paths.dist` | string | `"dist/"` | Output directory for compiled verified artifacts. |
| `paths.audit` | string | `".card/audit/"` | Archive of LLM-generated code. **Never edit files here directly.** |
| `paths.cache` | string | `".card/cache/"` | Stores hashed verification results. Delete to force full re-verification. |

**Partial configs are safe.** The loader uses `.get()` with per-key fallbacks throughout, so a `nightjar.toml` with only `[card]` still has valid `[paths]` defaults.

---

## Model Selection Precedence

All LLM calls pass through litellm [REF-T16]. The model name is resolved at call time using this priority chain:

```
1. --model CLI flag          (highest priority)
2. NIGHTJAR_MODEL env var
3. nightjar.toml card.default_model
4. "claude-sonnet-4-6"       (hardcoded fallback — lowest priority)
```

Implemented in `src/nightjar/config.py:get_model()`. The same chain is applied independently in `generator.py`, `retry.py`, `enricher.py`, `mines.py`, and `explain.py` — all read `NIGHTJAR_MODEL` directly rather than receiving it via argument.

**Any litellm-compatible model identifier works** — e.g. `gpt-4o`, `gemini/gemini-1.5-pro`, `ollama/codellama`. The pipeline never hard-validates model names.

---

## Environment Variables

### Model & LLM

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_MODEL` | string | `"claude-sonnet-4-6"` | Primary model for all generation stages (Analyst, Formalizer, Coder), retry repair calls, invariant enrichment, and the MCP server. Overrides `nightjar.toml default_model`. |
| `NIGHTJAR_REVIEW_MODEL` | string | *(same as generation model)* | Model used for spec cross-validation when `NIGHTJAR_CROSS_VALIDATE=1`. Defaults to the same model as generation so that a single env var controls everything. Set to a different model (e.g. `gpt-4o`) to get a second opinion from a different provider. Read by `src/nightjar/generator.py`. |
| `NIGHTJAR_CROSS_VALIDATE` | `"0"` or `"1"` | `"0"` | When `"1"`, enables cross-model spec validation: after code generation, a review model inspects the spec for contradictions, ambiguities, or impossible constraints. Adds one extra LLM call per generation run. Off by default to keep the standard 3-call pipeline. Read by `src/nightjar/generator.py`. |

### Verification Pipeline

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_DISABLE_CACHE` | any non-empty string | *(not set)* | When set to any value (e.g. `"1"`), bypasses the hash-based verification cache and forces all 5 stages to re-run. Useful in CI or when debugging stale cache hits. Read by `src/nightjar/verifier.py`. |
| `NIGHTJAR_PARALLEL` | `"0"` or `"1"` | `"0"` | When `"1"`, runs Stage 2 (schema) and Stage 3 (PBT) concurrently using `ThreadPoolExecutor` while Stage 4 (Dafny) remains sequential. Stages 0 and 1 always run sequentially as gates. Read by `src/nightjar/verifier.py`. |

### Property-Based Testing (Stage 3)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_TEST_PROFILE` | `"dev"` or `"ci"` | `"dev"` | Selects the Hypothesis settings profile. `"dev"`: 10 examples, derandomized (fast, local). `"ci"`: 200 examples, `suppress_health_check=[too_slow]` (thorough, pre-merge). Read by `src/nightjar/stages/pbt.py`. |
| `NIGHTJAR_ENABLE_STRATEGY_DB` | `"0"` or `"1"` | `"0"` | When `"1"`, loads and stores PBT strategy candidates in the strategy database to guide future Hypothesis example generation. Read by `src/nightjar/stages/pbt.py`. |
| `NIGHTJAR_CROSSHAIR_BACKEND` | `"0"` or `"1"` | `"0"` | When `"1"`, switches the Hypothesis backend to CrossHair for symbolic execution instead of random sampling. Requires `pip install hypothesis-crosshair`. CrossHair finds edge cases that random sampling misses. Read by `src/nightjar/stages/pbt.py`. |

### Repair & CEGIS Loop

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_ANNOTATION_RETRIES` | int (string) | `3` | Maximum surgical annotation repair attempts before falling back to full LLM regeneration. Annotation repair inserts a single invariant/assert/decreases clause at the Dafny error site. Cheaper than full regeneration. Read by `src/nightjar/retry.py`. |
| `NIGHTJAR_REPAIR_BUDGET_SECONDS` | float (string) | `120` | Wall-clock budget in seconds for the ratchet search loop. Only active when `NIGHTJAR_ENABLE_EVOLUTION=1`. Hard-stops the loop regardless of retry count remaining. Parse errors fall back to `120.0`. Read by `src/nightjar/retry.py`. |
| `NIGHTJAR_ENABLE_EVOLUTION` | `"0"` or `"1"` | `"0"` | When `"1"`, activates AlphaEvolve features: the ratchet search loop (population-based hill-climbing), MAP-Elites strategy database, and run logging to `.card/verify_log.tsv`. When `"0"` (default), the ratchet search immediately delegates to the flat BFS loop with zero overhead. Read by `src/nightjar/retry.py` and `src/immune/enricher.py`. |

### Canvas Web Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_ALLOWED_ORIGINS` | comma-separated string | `"*"` | CORS `allowed_origins` list for the FastAPI Canvas server (`nightjar serve`). Comma-separated, e.g. `"https://app.example.com,https://staging.example.com"`. Read by `src/nightjar/web_server.py`. Requires `pip install nightjar-verify[canvas]`. |
| `NIGHTJAR_BIN` | string | `"nightjar"` | Path to the `nightjar` binary used by the web scanner to spawn verification subprocesses. Override when the binary is not on `PATH` or when running from a virtualenv in a non-standard location. Read by `src/nightjar/web_scanner.py`. |

> **Security warning — NIGHTJAR_ALLOWED_ORIGINS:** The default `"*"` allows all origins and is appropriate only for local development. In production, set explicit origins. The server never sets `allow_credentials=True` with the wildcard because the CORS spec prohibits credentialed requests with `"*"` — but cross-origin state-changing requests (POST, DELETE) are still permitted from any origin with the default. Always set explicit origins before deploying the Canvas server publicly.

### Shadow CI / GitHub Actions

These variables configure the `nightjar` GitHub Action and the `shadow_ci_runner` module. They are typically set in `action.yml` rather than in a developer's `.env` file.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_CI_MODE` | `"shadow"` or `"strict"` | `"shadow"` | `"shadow"`: CI always exits 0 (non-blocking, observation-only). `"strict"`: exits non-zero on verification failure, blocking the PR merge. Read by `src/nightjar/shadow_ci_runner.py`. |
| `NIGHTJAR_CI_REPORT` | `"full"` or `"summary"` | `"full"` | Controls PR comment verbosity. `"full"` includes per-stage detail; `"summary"` posts a single pass/fail line. Read by `src/nightjar/shadow_ci_runner.py`. |
| `NIGHTJAR_CI_VERIFY_JSON` | string (path) | `".card/verify.json"` | Path to the verification report JSON consumed by the CI runner. Override when `nightjar.toml paths.dist` points elsewhere. Read by `src/nightjar/shadow_ci_runner.py`. |
| `NIGHTJAR_SECURITY_PACK` | string | `"none"` | Security scanner pack to run alongside verification. Read by `src/nightjar/shadow_ci_runner.py`. |

### External Tools

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DAFNY_PATH` | string (path) | *(not set)* | Absolute path to the Dafny binary. Used when `dafny` is not on `PATH` — e.g. a custom install location or a version-pinned binary. Falls back to `shutil.which("dafny")` if unset. Read by `src/nightjar/dafny_setup.py`, `src/nightjar/compiler.py`, and `src/nightjar/stages/formal.py`. |
| `SENTRY_DSN` | string (URL) | *(not set)* | Sentry Data Source Name for the immune system integration. When set, Sentry error events are ingested as invariant candidates and fed into the mining pipeline. Leave unset to disable Sentry. Read by `src/nightjar/sentry_integration.py`. |

### GitHub Actions Platform Variables

These are standard GitHub Actions variables injected automatically by the runner. Nightjar reads them when posting PR comments from Shadow CI. You do not set them manually.

| Variable | Set by | Description |
|----------|--------|-------------|
| `GITHUB_TOKEN` | GitHub Actions | API token used to authenticate PR comment POST requests. |
| `GITHUB_REPOSITORY` | GitHub Actions | `owner/repo` string (e.g. `j4ngzzz/Nightjar`). Required for the PR comment API URL. |
| `PR_NUMBER` | action.yml | Pull request number. Set in `action.yml`; not auto-injected by GitHub. |
| `GITHUB_OUTPUT` | GitHub Actions | Path to the file where action output variables are written (`key=value` pairs). |

---

## Optional Extras

The base install (`pip install nightjar-verify`) includes Click, litellm, Pydantic, Hypothesis, PyYAML, Rich, and Textual.

| Extra | Install command | Adds |
|-------|----------------|------|
| `fast` | `pip install nightjar-verify[fast]` | `watchdog` — file-watching daemon for `nightjar watch` |
| `canvas` | `pip install nightjar-verify[canvas]` | `fastapi`, `uvicorn` — REST + SSE API for `nightjar serve` |
| `compliance` | `pip install nightjar-verify[compliance]` | `cyclonedx-bom` — CycloneDX SBOM generation for EU CRA compliance reports |
| `dev` | `pip install nightjar-verify[dev]` | `pytest`, `pytest-asyncio`, `playwright`, `mcp`, `watchdog` — full development toolchain |

Install multiple extras at once: `pip install nightjar-verify[canvas,compliance,dev]`

---

## Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| `0` | `EXIT_PASS` | All verification stages passed. |
| `1` | `EXIT_FAIL` | One or more verification stages failed. |
| `2` | `EXIT_CONFIG_ERROR` | Configuration error (missing file, bad toml, missing dependency). |
| `3` | `EXIT_TIMEOUT` | A stage exceeded `verification_timeout`. |
| `4` | `EXIT_LLM_ERROR` | LLM API call failed (network error, rate limit, invalid key). |
| `5` | `EXIT_MAX_RETRIES` | CEGIS repair loop exhausted `max_retries` without passing. Human review required. |

These codes are defined in `src/nightjar/cli.py` and are stable across versions. Use them in CI `if` checks:

```yaml
- run: nightjar verify
  id: verify
- if: steps.verify.outcome == 'failure'
  run: nightjar explain
```

---

## Open Tasks

The 23 environment variables documented above were found by auditing every `os.environ.get()` and `os.getenv()` call in `src/`. To verify completeness after future changes, run:

```bash
grep -rn 'os\.environ\.get\|os\.getenv' src/ | grep -v '^\s*#' | sort
```

Compare the output against this document. Any `NIGHTJAR_*`, `DAFNY_*`, or `SENTRY_*` variable not listed here should be added.
