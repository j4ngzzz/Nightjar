# CARD — Contract-Anchored Regenerative Development

CARD is a verification layer for AI-generated code. Developers write specs (`.card.md` files containing intent, contracts, and tiered invariants). AI generates code from these specs. CARD's 5-stage verification pipeline mathematically proves the generated code satisfies the invariants. Code is regenerated from scratch on every build — never manually edited.

---

## MANDATORY: Reference-First Development

**Before implementing ANY component, you MUST:**

1. Open `docs/REFERENCES.md` and find the relevant `[REF-XXX]` entries for your task
2. Fetch the cited URL (paper, repo, or tool documentation)
3. Read and understand the pattern/algorithm described in the reference
4. ONLY THEN write code that implements it

**Do NOT implement from memory or training data.** Every pattern in CARD traces to a specific citation. If you cannot find a reference for what you're implementing, STOP and ask.

**Example:** Before implementing the retry loop, read [REF-P03] (Clover pattern) and [REF-P06] (DafnyPro structured errors). Fetch both papers. Implement THEIR pattern, not your own invention.

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
| Frontend | Next.js 15 + shadcn/ui + Tremor | | [REF-T21, REF-T22, REF-T23] |

---

## Directory Structure

```
project/
├── CLAUDE.md                       # THIS FILE — read first
├── contractd.toml                  # CLI configuration
├── deps.lock                       # Sealed dependency manifest [REF-C08]
├── .card/
│   ├── constitution.card.md        # Project-level invariants
│   ├── auth.card.md                # Module specs (one per module)
│   ├── payment.card.md
│   ├── audit/                      # Read-only generated code (git-tracked)
│   ├── cache/                      # Verification cache (hash → verified)
│   └── verify.json                 # Last verification report
├── dist/                           # Compiled verified artifacts
├── tests/
│   ├── generated/                  # Auto-generated PBT tests
│   └── manual/                     # Human-written example tests
├── src/
│   ├── contractd/                  # CLI source
│   │   ├── __init__.py
│   │   ├── cli.py                  # Click commands [REF-T17]
│   │   ├── parser.py               # .card.md parser
│   │   ├── generator.py            # LLM generation pipeline [REF-C03]
│   │   ├── verifier.py             # 5-stage verification pipeline
│   │   ├── stages/
│   │   │   ├── preflight.py        # Stage 0
│   │   │   ├── deps.py             # Stage 1 [REF-C08]
│   │   │   ├── schema.py           # Stage 2 [REF-T08]
│   │   │   ├── pbt.py              # Stage 3 [REF-T03]
│   │   │   └── formal.py           # Stage 4 [REF-T01]
│   │   ├── retry.py                # Clover retry loop [REF-C02]
│   │   └── mcp_server.py           # MCP server [REF-T18]
│   └── immune/                     # Immune system (month 2-3)
│       ├── collector.py            # Trace collection [REF-T12, REF-T15]
│       ├── miner.py                # Invariant mining [REF-C05]
│       ├── enricher.py             # LLM enrichment [REF-C06]
│       └── enforcer.py             # Runtime enforcement [REF-T10]
└── docs/
    ├── REFERENCES.md               # Citation library — READ THIS
    ├── ARCHITECTURE.md             # System design
    └── POSITIONING.md              # Strategy and positioning
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

### Commit Convention

- `feat: description` — new feature
- `fix: description` — bug fix
- `ref: description` — reference implementation from paper
- `test: description` — test only
- `docs: description` — documentation

### The Reference-First Commit Tag

When implementing a pattern from a reference, use:
```
ref: implement Clover retry loop [REF-P03]
```

This makes the git history traceable back to academic sources.

---

## Anti-Patterns — What NOT To Do

1. **DO NOT implement from training data.** Every algorithm must come from a cited reference. If you find yourself writing "I know how Dafny works," STOP and fetch [REF-T01] documentation.

2. **DO NOT manually edit generated code.** The `.card/audit/` directory is READ-ONLY. All changes go through `.card.md` specs. This is the core principle [REF-C07].

3. **DO NOT skip the verification pipeline.** Even for "simple" changes, run `contractd verify`. The pipeline catches what intuition misses.

4. **DO NOT add dependencies without updating deps.lock.** The sealed manifest [REF-C08] is a security boundary. `contractd lock` to update.

5. **DO NOT use Fuzzingbook code in production.** The license is CC-BY-NC-SA (non-commercial). Reimplement the Daikon algorithm under MIT. See [REF-T13] warning.

6. **DO NOT call LLM providers directly.** All LLM calls go through litellm [REF-T16] for model-agnosticism.

7. **DO NOT hardcode model names.** Use `CARD_MODEL` environment variable. The system must work with Claude, GPT, DeepSeek, or any litellm-supported model.

---

## How To Run

```bash
# Install dependencies
pip install -e ".[dev]"

# Initialize a module spec
contractd init payment

# Generate code from spec
contractd generate --model claude-sonnet-4-6

# Verify generated code
contractd verify

# Full pipeline (generate + verify + compile)
contractd build --target py

# Run tests
pytest tests/ -v
```

---

## Key Documents

| Document | What It Contains | When To Read |
|----------|-----------------|-------------|
| `docs/REFERENCES.md` | All citations, tools, papers, concepts | BEFORE implementing anything |
| `docs/ARCHITECTURE.md` | System design with reference citations | Before starting any component |
| `docs/POSITIONING.md` | Why CARD exists, competitors, strategy | For context and motivation |
| `docs/superpowers/plans/*.md` | Implementation plan with tasks | To find your next task |

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Oracle** (3619 symbols, 10035 relationships, 231 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
