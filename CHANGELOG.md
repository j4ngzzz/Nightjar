# Changelog

All notable changes to Nightjar are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.2] - 2026-03-29

### Added
- `nightjar spec` — unified entry point (smart routes to scan/infer/auto)
- `nightjar hook install|remove|list` — coding agent integration (Claude Code, Cursor, Windsurf, Kiro)
- `nightjar mcp` — start MCP server from CLI
- `nightjar badge --svg|--shields-json|--readme` — enhanced badge generation
- `nightjar verify --security-pack owasp` — OWASP invariant injection
- NightjarGroup tiered `--help` output with Quick Start
- hook_installer.py (291 lines, 62 tests)
- smithery.yaml + npm shim for MCP registry
- Vericoding page on nightjarcode.dev with FAQPage JSON-LD
- 7 SEO comparison pages, 5 community specs, 5 CI configs
- docs/bugs.md — structured 74-finding page
- Badge CI workflow (.github/workflows/nightjar-badge.yml)
- src/nightjar/py.typed (PEP 561)
- .python-version

### Changed
- scan-lab/ → research/ (professional naming)
- Removed deprecated-nightjarzzz/ from repo
- Internal strategy docs removed from public repo

### Fixed
- .gitignore: 37 patterns, untracked files 104→22
- bugs.md package count 32→34

---

## [0.1.1] - 2026-03-29

### Added

- `nightjar immune run|collect|status` — immune system CLI commands wiring the 8K-line mining pipeline
- `nightjar serve` — launches Nightjar Canvas web UI locally (requires [canvas] extras)
- `nightjar verify --tui` — Textual TUI dashboard during verification
- `build --target` now calls compiler.py for cross-language compilation (js/ts/go/java/cs)
- `ship` command generates SHA-256 provenance hash via ship.py
- Salsa-style verification cache in verifier.py (NIGHTJAR_DISABLE_CACHE=1 to bypass)
- tui.py and web_server.py import guards (graceful when Textual/FastAPI absent)
- `nightjar scan <dir>` — directory scanning with smart sort, parallel workers, security-critical file prioritization
- `nightjar infer` — LLM + CrossHair contract inference with generate→verify→repair loop
- `nightjar audit` — PyPI package scanner with terminal report card, letter grades A-F, CVE check via OSV
- `nightjar benchmark` — academic benchmark runner (vericoding POPL 2026, DafnyBench) with pass@k scoring
- `nightjar verify --format=vscode` — VS Code problem matcher output format
- `nightjar verify --output-sarif` — SARIF 2.1.0 file writer for GitHub Code Scanning
- Graduated confidence display: real path counts with mathematical confidence bounds
- Dafny error translation: 20 patterns with Python-developer-friendly explanations
- Docker image with Dafny 4.8.0 bundled — multi-stage build, ~300MB (`ghcr.io/j4ngzzz/nightjar`)
- 3 tutorials: quickstart, CI integration, FastAPI verification
- 3 example `.card.md` specs: payment, auth, rate-limiter
- VHS demo recording script (`aha-moment.tape`)
- 74 confirmed bugs across 34 packages (Wave 4 hunt complete)

### Fixed

- DSPy SIMBA renamed to "LLM prompt optimization (hill-climbing)" — DSPy not used
- Sentry integration clarified as "Sentry webhook payload parser" — no sentry_sdk dependency
- `nightjar watch` gives actionable error message instead of ImportError traceback
- optimizer crash on fresh install (missing JSON seed files now created on first run)
- Default model fallback changed from deepseek to `claude-sonnet-4-6`
- Stage 2.5 (negation proof) now visible in display output
- `generate` command no longer dumps full dataclass repr
- `hashlib.md5` uses `usedforsecurity=False` for FIPS compatibility
- CrossHair runner functions deduplicated (~80 lines removed)
- Duplicated config and import-to-package dicts consolidated
- `litellm` import made lazy in `formal.py`

---

## [0.2.0] - Planned

### Planned

- `nightjar hook install` — new `hook` CLI command group (`install` / `list` / `remove`) writing
  PostToolUse hooks for Claude Code, Cursor, Windsurf, and Kiro; atomic JSON merge with no-clobber
  safety invariants (`hook_installer.py`)
- `nightjar spec smart router` — CLI surface for the NL intent router: classify natural-language
  intent into structured spec targets and route to the correct `.card.md` pipeline stage
  (`intent_router.py` module already built; CLI command not yet exposed)
- `nightjar mcp CLI` — `nightjar mcp` subcommand that starts the MCP server over stdio transport,
  enabling `uvx nightjar-verify[mcp] mcp` as a zero-config entry point for Smithery and Kiro
- Enhanced badge — SVG badge generation with pass-rate colour scale (green/yellow/red/grey),
  `--readme` flag with auto-detected repo URL, `--format=shields` JSON endpoint payload, and
  `.github/workflows/nightjar-badge.yml` CI auto-update workflow (extends the shields.io URL
  generator shipped in v0.1.0)
- `nightjar verify --security-pack owasp` — exposes the OWASP check pack as a first-class `verify`
  flag; OWASP compliance report generation and EU CRA integration exist in `compliance.py` but the
  `--security-pack` CLI option is not yet wired
- Smithery listing — `smithery.yaml` registry metadata at repo root enabling one-command MCP install
  via Smithery; `@nightjar/mcp` listed as the canonical Smithery entry
- npm shim — `@nightjar/mcp` npm package (`npm/package.json` + `npm/bin/nightjar-mcp.js`) so
  `npx -y @nightjar/mcp` starts the MCP server with zero Python environment setup required
- 10 seed specs — community `.card.md` specs for `jwt-validation`, `sql-injection-prevention`,
  `file-upload-validation`, `pagination`, `password-hashing`, `api-key-rotation`,
  `session-management`, `csrf-protection`, `input-sanitization`, and `webhook-validation`; seeding
  the `nightjarcode/spec-registry` Apache 2.0 repo
- BAIF benchmark results — run Nightjar's CEGIS pipeline against the BAIF vericoding benchmark
  Dafny subset (3,029 tasks), publish pass@1 and pass@5 vs Claude Opus 4.1 baseline; benchmark
  runner (`benchmark_runner.py`, `benchmark_adapter.py`, `nightjar benchmark` CLI) already built
  in v0.1.1 — results not yet published

> **Groundwork already shipped (not yet user-facing):** `intent_router.py` (spec smart router
> logic), `mcp_server.py` (MCP server, no CLI entry point), `badge.py` (shields.io URL — SVG
> generation pending), `compliance.py` + `shadow_ci_runner.py` (OWASP pack internals — `--security-pack`
> flag not wired), `benchmark_runner.py` + `benchmark_adapter.py` (runner built — no published
> results yet).

---

## [0.1.0] - 2026-03-27

### Added

**Core Verification Pipeline**
- 5-stage pipeline: preflight, dependency audit, schema validation (Pydantic v2), property-based testing (Hypothesis), formal verification (Dafny + CrossHair)
- Stage 2.5: Negation-proof spec validation
- Verification confidence score 0-100
- Behavioral safety gate

**Advanced Verification Engine**
- Spec preprocessing with 19 Proven rewrite rules
- CEGIS counterexample-guided retry loop
- LP dual root-cause diagnosis with shadow prices
- Complexity-discriminated routing (CrossHair for simple, Dafny for complex)
- DafnyPro structured error extraction

**Immune System — Runtime Invariant Mining**
- Clean-room Daikon trace mining via sys.monitoring
- Houdini fixed-point filter
- MINES web API pattern mining
- Wonda quality scoring (4-criteria filter)
- Test oracle lifting from existing assertions
- Adversarial debate for invariant validation
- Temporal fact supersession with exponential decay

**Developer Experience**
- `nightjar auto`: generate .card.md specs from natural language intent
- `nightjar watch`: file-watching daemon with tiered verification
- `nightjar badge`: shields.io badge generation
- Textual TUI dashboard
- Rich streaming DisplayCallback interface
- VHS declarative demo tapes

**Observability & Compliance**
- Sentry error tracking with immune system feed
- Blast radius analysis hooks
- Playwright browser end-to-end tests
- EU CRA compliance report generation
- OWASP security pack
- Shadow CI GitHub Actions integration
