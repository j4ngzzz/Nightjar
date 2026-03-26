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
