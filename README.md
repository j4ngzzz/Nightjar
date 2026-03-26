# Nightjar

**Your LLM writes code. Nightjar proves it.** Not tested. *Proved.*

Nightjar is the verification layer for AI-generated code. Write `.card.md` specs (intent + contracts + tiered invariants). AI generates code. Nightjar mathematically proves it satisfies the invariants. Code is regenerated from scratch on every build -- never manually edited.

## The 60-Second Demo

```bash
# See the insecure code
$ cat demo/payment.py
def deduct(balance, amount):
    return balance - amount   # BUG: allows negative balance

# Nightjar catches it -- formal proof FAILS
$ nightjar verify -c demo/payment.card.md
Stage 4 FAIL: counterexample balance=0.01, amount=50 -> -49.99

# Auto-generate safe spec from plain English
$ nightjar auto "payment processor with balance >= 0 invariant"
Created spec: .card/payment.card.md (8 invariants, 6 approved)

# Verify the fixed code -- PROVED
$ nightjar verify -c .card/payment.card.md
VERIFIED -- all stages passed (confidence: 85/100)
```

## Why Nightjar?

- **96%** of developers don't fully trust AI-generated code (Sonar 2025)
- **53%** of AI-generated code contains OWASP Top 10 vulnerabilities (Veracode 2025)
- **86%** XSS failure rate in AI-generated code (Georgetown CSET)
- **0** tools formally prove AI code correctness -- until now

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Create a module spec
nightjar init payment

# Edit .card/payment.card.md with your intent, contracts, and invariants

# Generate + verify + compile
nightjar build --contract .card/payment.card.md --target py

# Or just verify
nightjar verify --contract .card/payment.card.md
```

### Prerequisites

- Python 3.11+
- Dafny 4.x (for formal verification): [Install Dafny](https://github.com/dafny-lang/dafny/releases)
  - Or set `DAFNY_PATH` environment variable
  - Stage 4 gracefully degrades to CrossHair/Hypothesis if Dafny is not installed

## CLI Commands

```
nightjar init [module]       Scaffold a .card.md spec
nightjar auto "intent"       Generate spec from natural language (zero-friction)
nightjar generate            Generate code from spec via LLM
nightjar verify              Run 5-stage verification pipeline
nightjar verify --fast       Stages 0-3 only (skip Dafny)
nightjar build               Generate + verify + compile
nightjar ship                Build + sign artifact
nightjar retry               Force LLM repair loop (BFS proof search)
nightjar lock                Freeze deps into deps.lock
nightjar explain             Show last failure in human-readable form (LLM-enhanced)
nightjar watch               Start persistent file-watching daemon
nightjar badge               Generate "Nightjar Verified" shields.io badge
nightjar optimize            Run DSPy SIMBA prompt optimization
nightjar immune              Run immune system cycle on error traces
```

## Verification Pipeline

Five stages, ordered cheapest-first with short-circuit on failure:

```
Stage 0: Pre-flight     [~0.5s]  AST parse + YAML schema validation
Stage 1: Dependency      [~1-2s]  Sealed manifest check
Stage 2: Schema          [~0.5s]  Pydantic v2 contract validation
Stage 3: PBT             [~3-8s]  Hypothesis property-based testing
Stage 4: Formal          [~5-20s] Dafny mathematical verification
```

### Confidence Score (0-100)

Every verification produces a confidence score:

| Stage | Points | What it proves |
|-------|--------|---------------|
| pyright type check | +15 | Static type correctness |
| deal static analysis | +10 | Pre/postcondition satisfiability |
| CrossHair symbolic | +35 | Symbolic proof for explored paths |
| Hypothesis PBT | +20 | Statistical coverage (10K+ examples) |
| Dafny formal proof | +20 | Full mathematical correctness |

### Graceful Degradation

If Dafny times out, Nightjar doesn't stop:
```
Dafny timeout -> CrossHair symbolic verification
CrossHair timeout -> Hypothesis PBT extended (10K examples)
All fail -> Report partial confidence score with gap notation
```

### Behavioral Safety Gate

Nightjar prevents regressions: new code is compared against the previous verified state. If invariants are lost, regeneration is blocked.

## Zero-Friction Mode

```bash
nightjar auto "Build a payment processor that charges credit cards"
```

The `auto` command generates verification specs from plain English:
1. Parse natural language intent
2. LLM generates candidate invariants
3. Intent router classifies: numerical / behavioral / state / formal
4. Domain generators: icontract `@require/@ensure`, Hypothesis `@given`, Dafny `requires/ensures`
5. Ranking + human approval (Y/n/modify)
6. Write to `.card.md` and run verification

## Watch Mode

```bash
nightjar watch
```

4-tier streaming verification with sub-second first feedback:

| Tier | Scope | Latency |
|------|-------|---------|
| 0: Syntax | AST parse, YAML frontmatter | <100ms |
| 1: Structural | Deps, schema, CrossHair quick | <2s |
| 2: Property | Hypothesis PBT, CrossHair watch | <10s |
| 3: Formal | Dafny with caching (on demand) | 1-30s |

Repeat verifications with no changes complete in <50ms (Salsa-style caching).

## Security Mode

Nightjar catches OWASP vulnerabilities that pass all tests:

```yaml
# .github/workflows/nightjar.yml
- uses: nightjar/verify@v1
  with:
    mode: shadow     # NEVER fail the build -- just report
    report: full
    security-pack: owasp
```

- **Shadow CI**: Runs as a GitHub Action, reports findings as PR comments, never blocks your pipeline
- **OWASP Pack**: SQL injection + XSS invariant templates with formal proof of absence
- **Violation Explainer**: LLM-enhanced Dafny error translation to human-readable text
- **EU CRA Compliance**: Generates structured compliance certificates (SBOM + verification timestamp)

## Immune System

Nightjar learns from production failures and automatically strengthens specifications.

1. **Collect** -- sys.monitoring (PEP 669) captures runtime traces at <5% overhead
2. **Mine** -- Clean-room Daikon algorithm (19 Ernst templates) detects dynamic invariants
3. **Filter** -- Houdini fixed-point filter finds maximal inductive subset via Z3
4. **Enrich** -- LLM generates candidate invariants from mined patterns
5. **Verify** -- CrossHair + Hypothesis verify candidates
6. **Append** -- Verified invariants auto-append to `.card.md` specs

### Mining Stack (3-Tier)

| Tier | Method | Tool | Overhead |
|------|--------|------|----------|
| 1 | Semantic | LLM-based property generation | Zero |
| 2 | Runtime | Clean-room Daikon + Houdini | Low (sys.monitoring) |
| 3 | API-level | MINES web API mining | None (OTel logs) |

## Model Agnostic

Swap models with an environment variable -- all LLM calls go through litellm:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # Default
NIGHTJAR_MODEL=deepseek/deepseek-chat  # Budget (10x cheaper)
NIGHTJAR_MODEL=openai/o3               # Premium
```

## MCP Server

Nightjar ships as an MCP server for universal IDE integration:

- `verify_contract` -- Run verification on generated code
- `get_violations` -- Get detailed violation report
- `suggest_fix` -- LLM-suggested fix for violations

Compatible with Cursor, Windsurf, Claude Code, VS Code, and any MCP-supporting tool.

## The .card.md Format

```yaml
---
card-version: "1.0"
id: payment
title: Payment Processor
contract:
  inputs:
    - name: balance
      type: float
      constraints: ">= 0"
  outputs:
    - name: new_balance
      type: float
      constraints: ">= 0"
invariants:
  - tier: formal
    rule: "deduct(balance, amount) requires amount <= balance ensures result >= 0"
  - tier: property
    rule: "for any balance >= 0 and amount >= 0: deposit(balance, amount) > balance"
---

## Intent
A payment processor that charges credit cards safely.
```

### Tiered Invariants

| Tier | Who Writes It | What It Generates | Tool |
|------|--------------|-------------------|------|
| `example` | Any developer | Unit tests from Given/When/Then | pytest |
| `property` | Senior dev | Property-based tests | Hypothesis |
| `formal` | Security/finance | Mathematical proof | Dafny/CrossHair |

## Tech Stack

| Component | Tool | Reference |
|-----------|------|-----------|
| Language | Python 3.11+ | |
| CLI | Click | [REF-T17] |
| LLM | litellm | [REF-T16] |
| Formal verification | Dafny 4.x | [REF-T01] |
| Property-based testing | Hypothesis | [REF-T03] |
| Symbolic execution | CrossHair | [REF-T09] |
| Runtime contracts | icontract | [REF-T10] |
| Schema validation | Pydantic v2 | [REF-T08] |
| Invariant mining | sys.monitoring (PEP 669) | Ernst 2007 |
| Invariant filtering | Z3 (Houdini algorithm) | FME 2001 |
| File watching | watchdog | Apache-2.0 |
| MCP | MCP SDK | [REF-T18] |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

## References

Every pattern in Nightjar traces to a specific academic citation. See [docs/REFERENCES.md](docs/REFERENCES.md) for the complete library.

Key references:
- [DafnyPro](https://arxiv.org/abs/2601.05385) -- Diff-checker + invariant pruner + hint-augmentation
- [VerMCTS](https://arxiv.org/abs/2402.08147) -- BFS proof search with verifier-in-the-loop
- [Clover](https://arxiv.org/abs/2310.02598) -- Closed-loop verified code generation
- [Ernst 2007](https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf) -- Dynamic invariant detection
- [Houdini](https://dl.acm.org/doi/10.1145/587051.587054) -- Greatest-fixpoint invariant filter

## License

MIT
