# Nightjar CLI Reference

Nightjar is a contract-anchored regenerative development tool. It parses `.card.md` specs, generates code via LLM, and proves the code correct through a 5-stage verification pipeline. Code is never manually edited — it is always regenerated from specs.

**Entry point:** `nightjar` (`nightjar.cli:main`)
**Config file:** `nightjar.toml`
**Spec directory:** `.card/`

---

## Quick Reference Index

| Command | Group | Purpose |
|---------|-------|---------|
| [`init`](#nightjar-init) | Scaffold | Create a blank `.card.md` spec |
| [`scan`](#nightjar-scan) | Scaffold | Extract invariants from Python source |
| [`infer`](#nightjar-infer) | Scaffold | LLM + CrossHair contract inference |
| [`auto`](#nightjar-auto) | Scaffold | Natural language → `.card.md` spec |
| [`generate`](#nightjar-generate) | Generation | LLM code generation from spec |
| [`verify`](#nightjar-verify) | Verification | Run 5-stage verification pipeline |
| [`retry`](#nightjar-retry) | Verification | Force CEGIS repair loop |
| [`explain`](#nightjar-explain) | Verification | Human-readable failure report |
| [`build`](#nightjar-build) | Build & Release | Generate + verify + compile |
| [`ship`](#nightjar-ship) | Build & Release | Build + provenance + compliance cert |
| [`lock`](#nightjar-lock) | Utilities | Freeze deps.lock with SHA hashes |
| [`optimize`](#nightjar-optimize) | Utilities | Prompt hill-climbing optimization |
| [`badge`](#nightjar-badge) | Utilities | Generate verified status badge |
| [`benchmark`](#nightjar-benchmark) | Utilities | Run academic verification benchmark |
| [`watch`](#nightjar-watch) | Utilities | File-watching daemon |
| [`audit`](#nightjar-audit) | Analysis | PyPI package contract + CVE audit |
| [`shadow-ci`](#nightjar-shadow-ci) | CI & Server | Non-blocking CI verification mode |
| [`serve`](#nightjar-serve) | CI & Server | Launch Canvas web UI locally |
| [`immune run`](#nightjar-immune-run) | Immune System | Full invariant mining cycle |
| [`immune collect`](#nightjar-immune-collect) | Immune System | Runtime type trace collection |
| [`immune status`](#nightjar-immune-status) | Immune System | Immune system health dashboard |

---

## Global Flags

These flags are available on the top-level `nightjar` command.

| Flag | Description |
|------|-------------|
| `--version` | Print the installed Nightjar version and exit |
| `--help` | Print help text for the command or subcommand and exit |

`--help` is available on every subcommand. Example: `nightjar verify --help`.

---

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NIGHTJAR_MODEL` | string | `claude-sonnet-4-6` | LLM model name forwarded to litellm. Accepts any provider string litellm recognises (e.g. `gpt-4o`, `gemini/gemini-pro`). |
| `ANTHROPIC_API_KEY` | string | — | Required when using Claude models. |
| `OPENAI_API_KEY` | string | — | Required when using OpenAI models. |
| `DAFNY_PATH` | path | `dafny` (on `$PATH`) | Override path to the Dafny binary. Useful when Dafny is not on `PATH`. |

Model resolution priority (highest to lowest): `--model` flag > `NIGHTJAR_MODEL` env var > `nightjar.toml card.default_model` > hardcoded default `claude-sonnet-4-6`.

API keys and environment variables can be placed in a `.env` file in the project root. Nightjar loads it automatically on startup.

---

## nightjar.toml Configuration Keys

| Key | Default | Description |
|-----|---------|-------------|
| `card.version` | `"1.0"` | Spec format version |
| `card.default_target` | `"py"` | Compile target when `--target` is not specified |
| `card.default_model` | `"claude-sonnet-4-6"` | Fallback LLM model |
| `card.max_retries` | `5` | Default repair attempts for `build` and `retry` |
| `card.verification_timeout` | `30` | Per-stage timeout in seconds |
| `paths.specs` | `".card/"` | Directory where `.card.md` specs live |
| `paths.dist` | `"dist/"` | Compiled artifact output |
| `paths.audit` | `".card/audit/"` | Generated code (read-only) |
| `paths.cache` | `".card/cache/"` | Verification result cache |

---

## Global Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| `0` | `EXIT_PASS` | All stages passed |
| `1` | `EXIT_FAIL` | Verification failed |
| `2` | `EXIT_CONFIG_ERROR` | Configuration or usage error |
| `3` | `EXIT_TIMEOUT` | Stage timed out |
| `4` | `EXIT_LLM_ERROR` | LLM API call failed |
| `5` | `EXIT_MAX_RETRIES` | Max repair attempts exceeded — human escalation required |

---

## Command Composition

Commands are designed to compose into a pipeline. The canonical end-to-end workflow is:

```
scan → generate → verify → build → ship
```

**Typical onboarding workflow:**
```bash
# 1. Extract invariants from existing source
nightjar scan src/payment.py --llm

# 2. Generate code from the spec
nightjar generate --spec .card/payment.card.md

# 3. Verify the generated code
nightjar verify --spec .card/payment.card.md

# 4. Build and compile to target language
nightjar build --spec .card/payment.card.md --target py

# 5. Package with provenance for deployment
nightjar ship --spec .card/payment.card.md
```

**CI workflow:**
```bash
# Non-blocking shadow mode (never fails the build)
nightjar shadow-ci --spec .card/verify.json --mode shadow

# Blocking strict mode
nightjar shadow-ci --spec .card/verify.json --mode strict
```

**Immune system feedback loop:**
```bash
nightjar immune collect src/payment.py
nightjar immune run src/payment.py --card .card/payment.card.md
nightjar immune status
```

---

## Scaffolding Commands

---

### `nightjar init`

**Description:** Scaffold a blank `.card.md` spec file for a new module.

**Usage:**
```bash
nightjar init <module_name> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `module_name` | Yes | Module identifier. Must start with a letter and contain only letters, digits, hyphens, or underscores (`[a-zA-Z][a-zA-Z0-9_-]*`). |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-o`, `--output` | path | `.` | Project root directory. The spec is created at `<output>/.card/<module_name>.card.md`. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Create .card/payment.card.md
nightjar init payment

# Create inside a different project root
nightjar init auth --output /projects/myapp
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Spec file created successfully |
| `2` | Invalid module name, path traversal detected, or file already exists |

**Notes:**
- The command refuses to overwrite an existing spec. There is no `--force` flag; delete the file manually if you need to start over.
- Path traversal is blocked: the resolved path must stay inside `.card/`.

---

### `nightjar scan`

**Description:** Scan a Python file or directory and generate `.card.md` spec(s) by extracting invariants from type hints, guard clauses, docstrings, and assertions.

**Usage:**
```bash
nightjar scan <path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | Yes | Path to a `.py` file or a directory. Directories are scanned recursively for all `.py` files. Must exist. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--llm` | flag | `false` | Enhance extracted candidates with LLM-generated suggestions. Requires a configured model. |
| `-o`, `--output` | path | `.card/<module>.card.md` | Output path for the generated `.card.md` spec. Only applies to single-file mode. |
| `--verify` | flag | `false` | Run the verification pipeline immediately after writing the spec. |
| `--approve-all` | flag | `false` | Auto-approve all invariant candidates without interactive prompting. |
| `--workers` | int | `None` (single thread) | Number of parallel worker threads for directory scan mode. |
| `--min-signal` | choice | `low` | Minimum signal level to include in directory scan results. Choices: `low`, `medium`, `high`. |
| `--smart-sort` | flag | `false` | Sort files by security criticality before scanning (directory mode only). |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Scan a single file
nightjar scan src/payment.py

# Scan with LLM enhancement and immediate verification
nightjar scan src/payment.py --llm --verify

# Auto-approve all and write to a custom path
nightjar scan src/auth.py --approve-all --output .card/auth.card.md

# Scan entire directory, 4 workers, only high-signal files
nightjar scan src/ --workers 4 --min-signal high --smart-sort
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Spec written successfully (or directory scan completed) |
| `1` | No candidates found, or all candidates rejected |
| `2` | File not found, scan module import error, or write error |

**Interactive approval (single-file mode without `--approve-all`):**

For each invariant candidate the CLI prompts:
- `y` — accept as-is
- `n` — reject
- `m` — modify the text, then accept

---

### `nightjar infer`

**Description:** Infer preconditions and postconditions for Python functions via LLM + CrossHair symbolic verification in a generate → verify → repair loop.

**Usage:**
```bash
nightjar infer <file_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file_path` | Yes | Path to a Python source file. Must exist. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--function` | string | `None` | Name of a specific function to infer contracts for. If omitted, all public top-level functions are processed. |
| `--no-verify` | flag | `false` | Skip CrossHair symbolic verification (fast mode — produces unverified contracts). |
| `--append-to-card` | flag | `false` | Append the inferred contracts as invariants to the matching `.card.md` spec (matched by module name). |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model name. |
| `--max-iterations` | int | `5` | Maximum CrossHair repair iterations per function. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Infer contracts for a single function
nightjar infer src/payment.py --function charge

# Infer all functions, skip CrossHair (faster)
nightjar infer src/payment.py --no-verify

# Infer and append results to the spec
nightjar infer src/payment.py --append-to-card

# Target specific model with more iterations
nightjar infer src/auth.py --function validate_token --model gpt-4o --max-iterations 10
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Inference complete; no counterexamples found |
| `1` | One or more functions produced a counterexample |
| `2` | File not found, parse error, or inferrer module not available |

**Requires:** LLM API key. CrossHair is required unless `--no-verify` is set.

---

### `nightjar auto`

**Description:** Generate a `.card.md` spec from a natural language intent description. Auto-generates verification artifacts (icontract, Hypothesis, Dafny stubs).

**Usage:**
```bash
nightjar auto "<intent>" [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `intent` | No | Natural language description of the module. If omitted the command exits with an error and prints usage. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--approve-all` | flag | `false` | Auto-approve all suggested invariants without prompting. |
| `-o`, `--output` | path | `.card` | Output directory for the generated `.card.md` spec. |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model name. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Interactive approval
nightjar auto "a payment processing module that charges credit cards"

# Non-interactive, write to custom directory
nightjar auto "JWT authentication module" --approve-all --output specs/

# Use a specific model
nightjar auto "rate limiter with per-user quotas" --model claude-opus-4-5
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Spec created successfully |
| `1` | All invariants rejected or spec generation produced no output |
| `2` | `intent` argument missing or auto module not available |
| `4` | LLM API error |

**Requires:** LLM API key.

---

## Generation Commands

---

### `nightjar generate`

**Description:** Generate code from a `.card.md` spec via the Analyst → Formalizer → Coder LLM pipeline. Writes the generated Dafny file to the output directory.

**Usage:**
```bash
nightjar generate --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file. |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model name. |
| `-o`, `--output` | path | `.` | Output directory. The generated file is written as `<output>/<spec_id>.dfy`. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Generate using the default model
nightjar generate --spec .card/payment.card.md

# Generate to a specific directory with a specific model
nightjar generate --spec .card/auth.card.md --model gpt-4o --output .card/audit/
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Code generated successfully |
| `2` | Config error or generator module not available |
| `4` | LLM API error |

**Requires:** LLM API key.

---

## Verification Commands

---

### `nightjar verify`

**Description:** Run the full 5-stage verification pipeline against generated code.

Pipeline stages (in order):
- **Stage 0** — Preflight (config, file existence checks)
- **Stage 1** — Dependency audit (locked manifest check)
- **Stage 2** — Schema validation (Pydantic)
- **Stage 2.5** — Negation proof
- **Stage 3** — Property-based testing (Hypothesis)
- **Stage 4** — Formal proof (Dafny)

**Usage:**
```bash
nightjar verify --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file. |
| `--fast` | flag | `false` | Run stages 0–3 only. Skips Dafny (stage 4). Useful for rapid iteration. |
| `--stage` | int | `None` | Run only a single stage (0, 1, 2, 3, or 4). Overrides `--fast`. Stage 2.5 (negation proof) cannot be targeted individually; it runs as part of the normal pipeline between stages 2 and 3. |
| `--ci` | flag | `false` | CI mode: strict output, no interactive prompts, deterministic exit codes. |
| `--format` | choice | `None` | Output format. Choices: `text`, `vscode`, `json`. `vscode` emits VS Code problem-matcher format. |
| `--output-sarif` | path | `None` | Write SARIF 2.1.0 results to the given file path. Can be combined with any `--format`. |
| `--tui` | flag | `false` | Launch the Textual TUI dashboard (requires `pip install textual`). |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Full 5-stage pipeline
nightjar verify --spec .card/payment.card.md

# Fast check — skip Dafny
nightjar verify --spec .card/payment.card.md --fast

# Run only stage 3 (property tests)
nightjar verify --spec .card/payment.card.md --stage 3

# CI mode with SARIF output
nightjar verify --spec .card/payment.card.md --ci --output-sarif results.sarif

# VS Code problem-matcher format
nightjar verify --spec .card/payment.card.md --format vscode

# JSON output (machine-readable)
nightjar verify --spec .card/payment.card.md --format json

# TUI dashboard
nightjar verify --spec .card/payment.card.md --tui
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | All stages passed |
| `1` | One or more stages failed |
| `2` | Config error or pipeline unavailable |

**Requires:** Dafny (for stage 4, skippable with `--fast`). LLM key is not required for `verify`.

---

### `nightjar retry`

**Description:** Force the CEGIS (Counterexample-Guided Inductive Synthesis) repair loop. Collects structured Dafny errors and feeds them back to the LLM for targeted repair.

**Usage:**
```bash
nightjar retry --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file. |
| `--max` | int | `5` | Maximum repair attempts. |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model for repair calls. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Retry with defaults
nightjar retry --spec .card/payment.card.md

# Allow more attempts
nightjar retry --spec .card/payment.card.md --max 10

# Use a more capable model for hard repairs
nightjar retry --spec .card/payment.card.md --model claude-opus-4-5 --max 3
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Verification passed after repair |
| `4` | LLM API error |
| `5` | Max retries exhausted — escalate to human |

**Requires:** LLM API key. Dafny.

---

### `nightjar explain`

**Description:** Show the last verification failure in human-readable form. Reads `.card/verify.json` and formats the failure report using Rich formatting.

**Usage:**
```bash
nightjar explain --spec <path>
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file (used to locate the adjacent `verify.json`). |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Show last failure
nightjar explain --spec .card/payment.card.md
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Report printed (including "last run passed" case) |

**Notes:** If no `verify.json` report exists, the command prints a hint to run `nightjar verify` first and exits with code `0`.

---

## Build and Release Commands

---

### `nightjar build`

**Description:** Full pipeline — generate code from spec, run 5-stage verification, and compile to a target language. Automatically retries on verification failure if `--retries` is set.

**Usage:**
```bash
nightjar build --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file. |
| `-t`, `--target` | choice | `py` (or `nightjar.toml card.default_target`) | Compile target language. Choices: `py`, `js`, `ts`, `go`, `java`, `cs`. |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model name. |
| `--retries` | int | `5` (or `nightjar.toml card.max_retries`) | Maximum CEGIS repair attempts on verification failure. |
| `-o`, `--output` | path | `.` | Output directory for generated and compiled artifacts. |
| `--ci` | flag | `false` | CI mode: strict, no prompts, non-zero exit on failure. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Build to Python (default)
nightjar build --spec .card/payment.card.md

# Build to Go with 3 retries
nightjar build --spec .card/payment.card.md --target go --retries 3

# CI pipeline
nightjar build --spec .card/payment.card.md --ci --output dist/
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Build passed — artifact compiled |
| `1` | Verification failed |
| `2` | Config or compilation error |

**Notes:** Compilation to non-Dafny targets wraps `dafny build` and requires the Dafny binary. A missing Dafny binary emits a warning but does not change the exit code if verification itself passed.

**Requires:** LLM API key. Dafny (for stage 4 and compilation).

---

### `nightjar ship`

**Description:** Build + package for deployment. Runs the full build pipeline then writes a provenance record (SHA-256 artifact hash, model used, stages passed) and an EU CRA compliance certificate.

**Usage:**
```bash
nightjar ship --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--spec`, `-c`, `--contract` | path | — | **Required.** Path to the `.card.md` spec file. |
| `-t`, `--target` | choice | `py` (or `nightjar.toml card.default_target`) | Compile target language. Choices: `py`, `js`, `ts`, `go`, `java`, `cs`. |
| `--model` | string | `NIGHTJAR_MODEL` | LLM model name. |
| `--retries` | int | `5` (or `nightjar.toml card.max_retries`) | Maximum CEGIS repair attempts. |
| `-o`, `--output` | path | `.` | Output directory for artifacts. |
| `--ci` | flag | `false` | CI mode. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Ship to Python
nightjar ship --spec .card/payment.card.md

# Ship to TypeScript in CI mode
nightjar ship --spec .card/auth.card.md --target ts --ci
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Ship complete — artifact, provenance, and compliance cert written |
| `1` | Verification failed — artifact not shipped |
| `2` | Config or unexpected error |

**Output files written on success:**
- `.card/provenance.json` — artifact SHA-256 hash, model, stages passed/total, timestamp
- `.card/compliance_cert.json` — EU CRA compliance certificate (if the compliance module is available)

**Requires:** LLM API key. Dafny.

---

## Utility Commands

---

### `nightjar lock`

**Description:** Freeze the current Python environment's dependencies into `deps.lock` with SHA-256 hashes. Prevents hallucinated-package supply-chain attacks.

**Usage:**
```bash
nightjar lock [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-o`, `--output` | path | `.` | Project root directory. `deps.lock` is written to `<output>/deps.lock`. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Lock deps in the current directory
nightjar lock

# Lock deps for a different project root
nightjar lock --output /projects/myapp
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | `deps.lock` written successfully |
| `2` | Lock module unavailable or write error |

---

### `nightjar optimize`

**Description:** Run hill-climbing prompt optimization on the Analyst, Formalizer, or Coder LLM prompt using verification pass rate as the metric.

**Usage:**
```bash
nightjar optimize [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-t`, `--target` | choice | `analyst` | Which prompt stage to optimize. Choices: `analyst`, `formalizer`, `coder`. |
| `--iterations` | int | `10` | Maximum optimization iterations. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Optimize the analyst prompt with defaults
nightjar optimize

# Optimize the coder prompt with more iterations
nightjar optimize --target coder --iterations 25

# Optimize the formalizer
nightjar optimize --target formalizer --iterations 15
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Optimization complete (whether or not improvement was found) |
| `2` | Optimizer module unavailable or error |

**Notes:** Optimization reads and writes from `.card/tracking.db` and `src/nightjar/prompts/`. Results are printed as version and score deltas.

**Requires:** LLM API key.

---

### `nightjar badge`

**Description:** Generate a "Nightjar Verified" badge from the last verification result. Uses shields.io URL format.

**Usage:**
```bash
nightjar badge [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `markdown` | Output format for the badge. Choices: `url`, `markdown`, `html`. |
| `--report` | path | `.card/verify.json` | Path to the verification report JSON file. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Markdown badge (paste into README)
nightjar badge

# Raw shields.io URL
nightjar badge --format url

# HTML img tag
nightjar badge --format html

# Badge from a non-default report location
nightjar badge --report build/verify.json --format markdown
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Badge output printed |
| `2` | Report file not found or badge module unavailable |

---

### `nightjar benchmark`

**Description:** Run Nightjar against an academic verification benchmark. Supports vericoding (POPL 2026) and DafnyBench task files. Produces pass@1 and pass@k metrics comparable to published baselines.

**Usage:**
```bash
nightjar benchmark <benchmark_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `benchmark_path` | Yes | Path to a benchmark file (`.jsonl`) or directory. Must exist. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--source` | choice | `auto` | Benchmark format. Choices: `auto`, `vericoding`, `dafnybench`. `auto` detects the format. |
| `--max-attempts` | int | `5` | Maximum verification attempts per task. |
| `--timeout` | int | `120` | Per-task timeout in seconds. |
| `--workers` | int | `1` | Number of parallel worker threads. |
| `--json` | flag | `false` | Output results as JSON instead of the formatted report table. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Run vericoding benchmark (auto-detected)
nightjar benchmark tasks/vericoding_tasks.jsonl

# DafnyBench directory
nightjar benchmark tasks/dafnybench/ --source dafnybench

# Parallel run with JSON output
nightjar benchmark tasks.jsonl --max-attempts 3 --workers 4 --json
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | At least one task passed |
| `1` | Zero tasks passed |
| `2` | Benchmark file not found, load error, or module unavailable |

**Notes:** Exit code `0` means at least one task passed, not that all tasks passed. For per-task results use `--json` or inspect the printed report table.

**Requires:** LLM API key. Dafny.

---

### `nightjar watch`

**Description:** Start a persistent file-watching daemon that monitors `.card/` for changes and runs tiered verification (stages 0–3) with sub-second first feedback.

**Usage:**
```bash
nightjar watch [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--debounce` | int | `500` | Debounce interval in milliseconds. Changes within the debounce window are coalesced. |
| `--card-dir` | path | `.card` | Directory to watch for `.card.md` file changes. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Watch with defaults
nightjar watch

# Faster debounce, custom directory
nightjar watch --debounce 200 --card-dir specs/

# Press Ctrl+C to stop
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Daemon stopped cleanly (Ctrl+C) |
| `2` | Watch module unavailable or startup error |

**Notes:** Each tier event is printed as `[Tier N] STATUS (Xms)`. The daemon runs until interrupted.

---

## Analysis Commands

---

### `nightjar audit`

**Description:** Scan any PyPI package for contract coverage and known CVEs. Downloads the package, scans every `.py` file for invariant candidates, checks CVEs via OSV, and renders a terminal report card with letter grades (A+ through F).

**Usage:**
```bash
nightjar audit <package_spec> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `package_spec` | Yes | PyPI package name, optionally with version pin (e.g. `requests`, `flask==3.0.0`). |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--with-deps` | flag | `false` | Also scan declared dependencies of the package. |
| `--no-cve` | flag | `false` | Skip CVE lookup (offline mode). |
| `-o`, `--output` | path | `None` | Write a `.card.md` spec with the discovered invariant candidates to this path. |
| `--json` | flag | `false` | Output results as JSON instead of the formatted report card. |
| `--no-cache` | flag | `false` | Bypass the audit cache and force a fresh scan. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Audit the requests package
nightjar audit requests

# Audit a pinned version and its dependencies
nightjar audit flask==3.0.0 --with-deps

# Write a spec from the results
nightjar audit requests --output .card/requests.card.md

# Machine-readable JSON output
nightjar audit requests --json

# Offline mode (no CVE lookup)
nightjar audit requests --no-cve
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Overall score >= 70 and no CVEs found |
| `1` | Score < 70 or CVEs found |
| `2` | Package not found, audit error, or module unavailable |

---

## CI and Server Commands

---

### `nightjar shadow-ci`

**Description:** Run verification in CI mode — shadow (non-blocking) or strict (blocking). In shadow mode the command always exits `0` regardless of outcome so it never blocks a PR merge.

**Usage:**
```bash
nightjar shadow-ci --spec <path> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--spec` | path | — | **Required.** Path to a `verify.json` report from a previous `nightjar verify` run. Must exist on disk. Note: the Click decorator does not mark this `required=True`; omitting it raises an unhandled Click usage error rather than a clean exit code `2`. |
| `--mode` | choice | `shadow` | Operating mode. Choices: `shadow` (always exit 0), `strict` (exit 1 on failure). |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Shadow mode — add to PR pipeline without blocking merges
nightjar shadow-ci --spec .card/verify.json --mode shadow

# Strict mode — block on failure
nightjar shadow-ci --spec .card/verify.json --mode strict
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Shadow mode always; strict mode when verified |
| `1` | Strict mode only: verification report shows failure |
| `2` | Shadow CI module unavailable |

**Notes:** The command prints a PR comment summary if available, otherwise prints the raw report JSON.

---

### `nightjar serve`

**Description:** Launch the Nightjar Canvas web UI locally. Requires the canvas extras (`nightjar-verify[canvas]`).

**Usage:**
```bash
nightjar serve [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--port` | int | `8000` | TCP port to bind to. |
| `--host` | string | `127.0.0.1` | Host address to bind to. Use `0.0.0.0` to expose on all interfaces. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Start locally on default port
nightjar serve

# Expose on all interfaces on port 9000
nightjar serve --host 0.0.0.0 --port 9000
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Server stopped cleanly |
| `2` | FastAPI or uvicorn not installed |

**Requires:** `pip install nightjar-verify[canvas]`

---

## Immune System Commands

The `immune` subcommands form a self-improving verification feedback loop. They are registered under the `nightjar immune` group and require `pip install nightjar[immune]`.

**Typical workflow:**
```bash
nightjar immune collect src/payment.py   # record runtime traces
nightjar immune run src/payment.py --card .card/payment.card.md  # mine + verify + append
nightjar immune status                    # check health
```

---

### `nightjar immune run`

**Description:** Run the full 3-tier invariant mining cycle on a Python source file. Loads source, runs the mining orchestrator, verifies candidates with CrossHair + Hypothesis, and optionally appends survivors to the `.card.md` spec.

Mining tiers:
- **Tier 1 SEMANTIC** — LLM hypothesis generation
- **Tier 2 RUNTIME** — Daikon + Houdini dynamic invariant mining
- **Tier 3 API-LEVEL** — MINES span analysis

**Usage:**
```bash
nightjar immune run <source_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `source_path` | Yes | Path to a Python source file. Must exist. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--card` | path | `None` | Path to a `.card.md` file. Verified invariants are appended here. If omitted, results are only displayed and stored in the trace database. |
| `--tier` | choice | `None` (all tiers) | Run a specific mining tier only. Choices: `1` (SEMANTIC), `2` (RUNTIME), `3` (API-LEVEL). |
| `--function` | string | `None` | Restrict mining to a single named function. |
| `--db` | path | `.card/immune.db` | Path to the immune trace database. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Full mining cycle, append to spec
nightjar immune run src/payment.py --card .card/payment.card.md

# Only LLM tier for a specific function
nightjar immune run src/auth.py --tier 1 --function validate_token

# All tiers, custom database
nightjar immune run src/payment.py --card .card/payment.card.md --db .card/immune-prod.db
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Mining cycle complete |
| `1` | Import error or runtime error (raised as `click.ClickException`, which defaults to exit `1`) |

**Requires:** `pip install nightjar[immune]`. LLM API key (Tier 1). CrossHair (verification step).

---

### `nightjar immune collect`

**Description:** Collect runtime type traces from a Python module by importing it and recording type signatures via the TypeCollector. Results are saved to the immune trace database for later mining with `immune run`.

**Usage:**
```bash
nightjar immune collect <source_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `source_path` | Yes | Path to a Python source file. Must exist and be importable. |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--function` | string | `None` | Trace a specific function by name. Defaults to tracing all public functions. |
| `--db` | path | `.card/immune.db` | Path to the immune trace database. Created if it does not exist. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Collect traces from all public functions
nightjar immune collect src/payment.py

# Collect traces for a single function
nightjar immune collect src/auth.py --function validate_token

# Use a custom trace database
nightjar immune collect src/payment.py --db .card/immune-staging.db
```

**Exit codes:** Exits via `ClickException` if the module cannot be imported or if the store is unavailable; `0` on normal completion.

**Notes:** If the callable raises an exception during tracing, the error is shown as a warning but traces captured before the exception are still saved.

**Requires:** `pip install nightjar[immune]`.

---

### `nightjar immune status`

**Description:** Display a health dashboard for the immune system — trace counts by type, invariant candidates by lifecycle stage, and verified invariants ready to be applied to specs.

**Usage:**
```bash
nightjar immune status [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--db` | path | `.card/immune.db` | Path to the immune trace database to read. |
| `--help` | flag | — | Show help and exit. |

**Examples:**
```bash
# Status from default database
nightjar immune status

# Status from a custom database
nightjar immune status --db .card/immune-staging.db
```

**Exit codes:** `0` always (including when the database does not exist — a helpful message is printed instead).

**Output includes:**
- Trace database counts: type traces (MonkeyType), value traces (Daikon), API traces (OpenTelemetry), error traces (Sentry)
- Invariant candidate counts by status: Pending, Verified, Rejected, Applied to spec
- Health indicator: NO TRACES / traces collected / candidates mined / OK

**Requires:** `pip install nightjar[immune]`.

---

## Open Tasks

The following items were identified during documentation and require investigation:

1. **`NIGHTJAR_DISABLE_CACHE` env var** — referenced in task specifications but not found in `config.py` or `cli.py`. Needs confirmation whether this variable is implemented and in which module it is checked.

2. **`init --force` flag** — The `init` command error message says "Use --force to overwrite" but no `--force` flag is implemented in the Click decorator. This is a documentation/code discrepancy.

3. **`shadow-ci` missing `@click.pass_context`** — Unlike all other commands, `shadow-ci` does not use `ctx.exit()` and instead raises `SystemExit` directly. This is consistent but worth noting for future refactoring.

4. **`immune` group exit codes** — The immune subcommands raise `ClickException` on error rather than calling `ctx.exit()` with a specific code. The precise exit code for immune errors should be confirmed with `click.ClickException` defaults (exits `1`).
