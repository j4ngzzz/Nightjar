# Changelog

All notable changes to Nightjar are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
