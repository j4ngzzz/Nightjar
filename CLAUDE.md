# Nightjar — Contract-Anchored Regenerative Development

Nightjar is a verification layer for AI-generated code. Developers write specs (`.card.md` files). AI generates code. Nightjar's pipeline mathematically proves the code satisfies the specs. Code is regenerated from scratch on every build — never manually edited.

---

## Swarm Quick-Start (30 seconds)

**Project name:** Nightjar | **CLI entry point:** `nightjar` (`nightjar.cli:main`)
**Config file:** `nightjar.toml` (was `contractd.toml` — that name is gone)
**Env var for model:** `NIGHTJAR_MODEL` (e.g. `claude-sonnet-4-6`)
**Source lives in:** `src/nightjar/` and `src/immune/`
**Specs live in:** `.card/*.card.md`
**Generated/audit code:** `.card/audit/` (READ-ONLY — never edit)

The three things you must not do:
1. Implement without reading the cited reference first (see [Reference-First Development](#mandatory-reference-first-development))
2. Edit files in `.card/audit/` directly
3. Call LLM providers directly — use litellm

**Find your next task:** `docs/superpowers/plans/*.md`

---

## MANDATORY: Reference-First Development

**Before implementing ANY component, you MUST:**

1. Open `docs/REFERENCES.md` — find the `[REF-XXX]` entries for your task
2. Fetch the cited URL (paper, repo, or tool doc) using WebFetch or brave-search
3. Read and understand the pattern/algorithm described
4. ONLY THEN write code that implements it

**Do NOT implement from memory or training data.** Every pattern in Nightjar traces to a specific citation. If you cannot find a reference for what you're implementing, STOP and ask.

**Practical workflow:**
```
# Step 1: Find refs for your task
grep "REF-" docs/REFERENCES.md | grep "your-topic"

# Step 2: Fetch the paper
WebFetch https://arxiv.org/abs/XXXX.XXXXX

# Step 3: Implement from the paper, not from intuition

# Step 4: Tag commit with ref
ref: implement CEGIS repair loop [REF-NEW-02, REF-P03]
```

---

## Tech Stack

| Component | Tool | Version | Reference |
|-----------|------|---------|-----------|
| Language | Python | 3.11+ | |
| CLI framework | Click | latest | [REF-T17] |
| LLM interface | litellm | latest | [REF-T16] |
| Verification engine | Dafny | 4.x | [REF-T01] |
| Property-based testing | Hypothesis | latest | [REF-T03] |
| Schema validation | Pydantic | v2 | [REF-T08] |
| Dependency security | uv + pip-audit | latest | [REF-T05, REF-T06] |
| Symbolic execution | CrossHair | latest | [REF-T09] |
| Runtime contracts | icontract | latest | [REF-T10] |
| Type tracing | MonkeyType | latest | [REF-T12] |
| MCP server | mcp SDK | latest | [REF-T18] |
| TUI dashboard | Textual | latest | [REF-T27] |
| Frontend | Next.js 15 + shadcn/ui + Tremor | | [REF-T21, REF-T22, REF-T23] |

---

## Directory Structure

```
project/
├── CLAUDE.md                       # THIS FILE
├── nightjar.toml                   # CLI configuration
├── pyproject.toml                  # Package metadata + entry point (v0.1.1)
├── deps.lock                       # Sealed dependency manifest [REF-C08]
├── smithery.yaml                   # Smithery MCP registry manifest
├── npm/                            # npm wrapper package for MCP distribution
├── .card/
│   ├── constitution.card.md        # Project-level invariants
│   ├── auth.card.md                # Module specs (one per module)
│   ├── payment.card.md
│   ├── audit/                      # READ-ONLY generated code (git-tracked)
│   ├── cache/                      # Verification cache (hash → verified)
│   └── verify.json                 # Last verification report
├── dist/                           # Compiled verified artifacts
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests (require Dafny/LLM)
│   ├── generated/                  # Auto-generated PBT tests
│   ├── manual/                     # Human-written example tests
│   └── e2e/                        # Playwright browser tests
├── demo/
│   ├── nightjar-demo.tape          # VHS declarative demo recording
│   └── nightjar-tui.tape
├── src/
│   ├── nightjar/                   # Main CLI + verification pipeline
│   │   ├── cli.py                  # Click commands [REF-T17]
│   │   ├── parser.py               # .card.md parser
│   │   ├── generator.py            # Analyst → Formalizer → Coder [REF-C03]
│   │   ├── verifier.py             # Pipeline orchestrator
│   │   ├── spec_rewriter.py        # 5 rule groups / 19 normalization patterns [REF-NEW-01]
│   │   ├── retry.py                # CEGIS retry loop [REF-NEW-02, REF-C02]
│   │   ├── diagnosis.py            # LP dual root-cause [REF-NEW-03]
│   │   ├── negation_proof.py       # Stage 2.5 [REF-NEW-07]
│   │   ├── oracle_lifter.py        # Test oracle lifting [REF-NEW-06]
│   │   ├── tui.py                  # Textual TUI dashboard
│   │   ├── display.py              # Rich streaming DisplayCallback
│   │   ├── sentry_integration.py   # Sentry webhook payload → immune candidates
│   │   ├── gitnexus_hooks.py       # Blast radius warnings
│   │   ├── mcp_server.py           # MCP server [REF-T18]
│   │   ├── scanner.py              # `nightjar scan` — invariant extraction from existing code
│   │   ├── inferrer.py             # `nightjar infer` — LLM + CrossHair contract inference
│   │   ├── pkg_auditor.py          # `nightjar audit` — PyPI package security audit
│   │   ├── benchmark_adapter.py    # Benchmark harness adapter (vericoding/DafnyBench)
│   │   ├── benchmark_runner.py     # `nightjar benchmark` — academic benchmark runner
│   │   ├── sarif_writer.py         # SARIF output for IDE/CI integration
│   │   ├── immune_commands.py      # `nightjar immune` subcommand group
│   │   ├── hook_installer.py       # `nightjar hook` — coding agent config installer
│   │   ├── shadow_ci.py            # `nightjar shadow-ci` — non-blocking CI mode
│   │   ├── shadow_ci_runner.py     # Shadow CI execution helpers
│   │   ├── watch.py                # `nightjar watch` — file-change re-verify daemon
│   │   ├── web_server.py           # `nightjar serve` — web UI server
│   │   ├── auto.py                 # `nightjar auto` — fully autonomous verify+fix loop
│   │   ├── badge.py                # `nightjar badge` — SVG + shields.io badge generation
│   │   ├── compliance.py           # CycloneDX SBOM / EU CRA compliance helpers
│   │   ├── dafny_pro.py            # DafnyPro structured error parsing
│   │   ├── dafny_setup.py          # Dafny binary auto-installer
│   │   ├── optimizer.py            # LLM prompt optimization (hill-climbing)
│   │   ├── strategy_db.py          # MAP-Elites strategy database
│   │   ├── tracking.py             # Card tracking / ratchet loop
│   │   ├── replay.py               # Verification run replay
│   │   ├── safety_gate.py          # SafePilot complexity routing
│   │   ├── intent_router.py        # Natural-language intent routing
│   │   ├── formatters/             # Output formatters (JSON, SARIF, VS Code, etc.)
│   │   ├── invariant_generators/   # Per-tier code generators
│   │   ├── security/               # OWASP security checks (owasp_pack.py)
│   │   └── stages/
│   │       ├── preflight.py        # Stage 0
│   │       ├── deps.py             # Stage 1 [REF-C08]
│   │       ├── schema.py           # Stage 2 [REF-T08]
│   │       ├── pbt.py              # Stage 3 [REF-T03]
│   │       └── formal.py           # Stage 4 [REF-T01]
│   └── immune/                     # Immune system
│       ├── collector.py            # Trace collection [REF-T12, REF-T15]
│       ├── daikon.py               # Daikon reimplementation (MIT) [REF-T13]
│       ├── mines.py                # Invariant mining [REF-C05]
│       ├── enricher.py             # LLM enrichment [REF-C06]
│       ├── enforcer.py             # Runtime enforcement + temporal supersession
│       ├── quality_scorer.py       # Wonda quality scoring [REF-NEW-05]
│       ├── debate.py               # Adversarial debate [REF-NEW-10]
│       ├── spec_updater.py         # Append invariants to .card.md
│       ├── houdini.py              # Houdini invariant pruning
│       ├── pipeline.py             # Immune pipeline orchestrator
│       └── store.py                # Invariant persistence store
└── docs/
    ├── REFERENCES.md               # Citation library — READ THIS FIRST
    ├── ARCHITECTURE.md             # Full system design
    ├── POSITIONING.md              # Strategy and positioning
    └── superpowers/plans/*.md      # Implementation plans with tasks
```

---

## What's Built vs What's Next

**Built (Phases 1-6 + Waves 0-3):**
- Full 6-stage verification pipeline (Stage 0–4 + Stage 2.5 negation-proof)
- CEGIS retry loop with structured Dafny error format
- Analyst → Formalizer → Coder generation pipeline
- 19 top-level CLI commands (`init`, `generate`, `verify`, `build`, `ship`, `retry`, `lock`, `explain`, `optimize`, `auto`, `watch`, `badge`, `scan`, `infer`, `audit`, `benchmark`, `serve`, `mcp`, `shadow-ci`) + command groups: `hook` (`install`, `remove`, `list`) and `immune` (`run`, `collect`, `status`)
- MCP server with 3 tools (`verify_contract`, `get_violations`, `suggest_fix`) + `nightjar mcp` CLI launcher
- `nightjar hook install` — auto-installs verification hooks into Claude Code, Cursor, Windsurf, and Kiro agent configs
- `nightjar shadow-ci` — non-blocking CI mode (shadow/strict); never breaks a PR in shadow mode
- `nightjar badge --svg` — standalone SVG badge generation + shields.io JSON endpoint
- `nightjar benchmark` — runs against vericoding (POPL 2026) and DafnyBench academic task files
- OWASP security pack (`security/owasp_pack.py`) with `--owasp` flag on verify
- Immune system: trace collection, Daikon reimplementation, LLM enrichment, Wonda quality scoring, adversarial debate, temporal supersession, Houdini pruning
- Textual TUI dashboard with `--tui` flag
- Sentry webhook payload parser (no sentry_sdk — parses Sentry-format JSON into invariant candidates)
- LP dual root-cause diagnosis on retry exhaustion
- 5 Proven rule groups covering 19 normalization patterns (pre-generation normalization)
- SafePilot complexity routing (CrossHair vs Dafny)
- Test oracle lifter (existing tests → `.card.md` invariants)
- GitNexus blast radius hooks
- LLM prompt optimization (hill-climbing) (`nightjar optimize`)
- Smithery registry manifest + npm wrapper for MCP distribution
- CycloneDX SBOM / EU CRA compliance report generation (`compliance` extra)

**Known gaps / Next tasks:** Check `docs/superpowers/plans/` for the active plan file.

---

## How To Run

```bash
# Install dependencies
pip install -e ".[dev]"

# Initialize a module spec
nightjar init payment

# Generate code from spec
nightjar generate --model claude-sonnet-4-6

# Verify generated code (full pipeline)
nightjar verify

# Fast check (skip Stage 2.5 + Dafny)
nightjar verify --fast

# Full pipeline (generate + verify + compile)
nightjar build --target py

# Run tests
pytest tests/ -v

# Run tests excluding integration (no Dafny/LLM required)
pytest tests/ -v -m "not integration"

# Launch with TUI dashboard
nightjar verify --tui

# Scan existing code for invariants
nightjar scan src/

# Infer contracts via LLM + CrossHair
nightjar infer app.py

# Audit a PyPI package
nightjar audit requests

# Run immune system mining
nightjar immune run src/payment.py

# Watch for file changes and re-verify
nightjar watch

# Launch web UI
nightjar serve

# Start the MCP server (stdio transport for coding agent integration)
nightjar mcp

# Install verification hooks into detected coding agents
nightjar hook install

# Remove hooks from a specific agent
nightjar hook remove --target cursor

# Run in non-blocking CI shadow mode
nightjar shadow-ci --mode shadow --spec .card/verify.json

# Run against an academic verification benchmark
nightjar benchmark path/to/benchmark.json --source vericoding
```

---

## Available Tools & MCP

MCP servers available in this project's Claude Code environment:

| MCP Server | Key Tools | Use For |
|-----------|-----------|---------|
| `gitnexus` | `gitnexus_query`, `gitnexus_context`, `gitnexus_impact`, `gitnexus_rename`, `gitnexus_detect_changes` | Code intelligence, blast radius, safe rename |
| `brave-search` | `brave_web_search` | Fetch papers, tool docs, reference URLs |
| `playwright` | `browser_navigate`, `browser_snapshot`, `browser_take_screenshot` | E2E tests, UI verification |
| `github` | `get_file_contents`, `search_code`, `create_pull_request` | Cross-repo lookups, PRs |
| `context7` | `resolve-library-id`, `query-docs` | Up-to-date library documentation |
| `sequential-thinking` | `sequentialthinking` | Complex multi-step reasoning |
| `webresearch` | `search_google`, `visit_page` | Web search for reference material |

**Note:** brave-search, exa, coingecko, ccxt, duckdb are available but not relevant to Nightjar.

---

## Superpowers Skills

Skills are invoked via the Skill tool. Use them when the task matches:

| Task | Skill |
|------|-------|
| Starting feature work, need isolation | `superpowers:using-git-worktrees` |
| Have a spec, starting multi-step implementation | `superpowers:writing-plans` |
| Executing an implementation plan | `superpowers:executing-plans` |
| 2+ independent tasks to parallelize | `superpowers:dispatching-parallel-agents` |
| Found a bug, need to debug systematically | `superpowers:systematic-debugging` |
| About to claim work is done | `superpowers:verification-before-completion` |
| Implementing any feature or fix | `superpowers:test-driven-development` |
| Receiving code review feedback | `superpowers:receiving-code-review` |
| Understanding how code works | `gitnexus-exploring` |
| Blast radius before changing a symbol | `gitnexus-impact-analysis` |
| Renaming / moving / extracting code | `gitnexus-refactoring` |

---

## Code Intelligence (GitNexus)

GitNexus indexes this repo as **Oracle** (see `gitnexus://repo/Oracle/context` for current count). It's available but not mandatory for every edit. Use it when it helps:

```
# Find code by concept
gitnexus_query({query: "verification pipeline"})

# 360-degree view of a symbol before touching it
gitnexus_context({name: "run_pipeline"})

# Blast radius before a risky edit
gitnexus_impact({target: "verify_contract", direction: "upstream"})

# Safe rename across the codebase
gitnexus_rename({symbol_name: "old_name", new_name: "new_name", dry_run: true})
```

If the index is stale after commits, refresh it:
```bash
npx gitnexus analyze
```

---

## Development Conventions

### TDD (Test-Driven Development)

1. Write the failing test FIRST
2. Run it to verify it fails
3. Write minimal code to make it pass
4. Run test to verify it passes
5. Commit

### Code Style

- Python: follow PEP 8, use type hints everywhere
- Functions: small, single-responsibility
- No classes unless state management requires it (prefer functions)
- All LLM calls go through litellm [REF-T16] — never call provider APIs directly
- Model name from `NIGHTJAR_MODEL` env var — never hardcode

### Commit Convention

- `feat: description` — new feature
- `fix: description` — bug fix
- `ref: description [REF-XXX]` — reference implementation from paper
- `test: description` — test only
- `docs: description` — documentation

When implementing a pattern from a reference, tag it:
```
ref: implement Clover retry loop [REF-P03]
```
This makes git history traceable back to academic sources.

---

## Anti-Patterns — What NOT To Do

1. **DO NOT implement from training data.** Every algorithm must come from a cited reference. If you find yourself writing "I know how Dafny works," STOP and fetch [REF-T01] documentation.

2. **DO NOT manually edit generated code.** `.card/audit/` is READ-ONLY. All changes go through `.card.md` specs. This is the core principle [REF-C07].

3. **DO NOT skip the verification pipeline.** Even for "simple" changes, run `nightjar verify`. The pipeline catches what intuition misses.

4. **DO NOT add dependencies without updating deps.lock.** The sealed manifest [REF-C08] is a security boundary. Run `nightjar lock` to update.

5. **DO NOT use Fuzzingbook code in production.** The license is CC-BY-NC-SA (non-commercial). The Daikon algorithm is reimplemented from scratch under MIT. See `src/immune/daikon.py`.

6. **DO NOT call LLM providers directly.** All LLM calls go through litellm [REF-T16] for model-agnosticism.

7. **DO NOT hardcode model names.** Use the `NIGHTJAR_MODEL` environment variable.

8. **DO NOT use `contractd` anywhere.** The CLI and package are both `nightjar`. The config file is `nightjar.toml`.

---

## Key Documents

| Document | Contents | When To Read |
|----------|---------|-------------|
| `docs/REFERENCES.md` | All citations, tools, papers, concepts | BEFORE implementing anything |
| `docs/ARCHITECTURE.md` | Full system design with citations | Before starting any component |
| `docs/POSITIONING.md` | Why Nightjar exists, competitors, strategy | For context and motivation |
| `docs/superpowers/plans/*.md` | Implementation plans with task checklists | To find your next task |

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Oracle** (6253 symbols, 16201 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/Oracle/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Oracle/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Oracle/clusters` | All functional areas |
| `gitnexus://repo/Oracle/processes` | All execution flows |
| `gitnexus://repo/Oracle/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
