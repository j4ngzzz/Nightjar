# contractd

**Contract-Anchored Regenerative Development** — the verification layer every vibe coding tool needs.

Developers write `.card.md` specs (intent + contracts + tiered invariants). AI generates code. `contractd` mathematically proves the code satisfies the invariants. Code is regenerated from scratch on every build — never manually edited.

## Why CARD?

96% of developers don't fully trust AI-generated code. Only 48% verify before committing. The result: **verification debt** — the gap between AI code volume and verification coverage.

CARD closes this gap with a 5-stage verification pipeline that costs ~$0.001 per run and completes in under 60 seconds.

## Prerequisites

- Python 3.11+
- Dafny 4.x (for formal verification): [Install Dafny](https://github.com/dafny-lang/dafny/releases)
  - Or set `DAFNY_PATH` environment variable to your Dafny binary
  - Stage 4 (formal) is skipped gracefully if Dafny is not installed

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Create a module spec
contractd init payment

# Edit .card/payment.card.md with your intent, contracts, and invariants

# Generate + verify + compile
contractd build --contract .card/payment.card.md --target py

# Or just verify
contractd verify --contract .card/payment.card.md
```

## The .card.md Format

A `.card.md` file is YAML frontmatter (machine-readable) + Markdown body (human-readable):

```yaml
---
card-version: "1.0"
id: user-auth
title: User Authentication
status: draft
module:
  owns: [login(), logout(), validate_token()]
contract:
  inputs:
    - name: email
      type: string
    - name: password
      type: string
  outputs:
    - name: session_token
      type: string
invariants:
  - id: INV-001
    tier: property
    statement: "A valid token corresponds to exactly one active user session"
---

## Intent
Let users log in with email/password and get a session token.

## Acceptance Criteria
### Story 1 — Login (P1)
1. **Given** valid credentials, **When** login(), **Then** JWT returned
2. **Given** invalid password, **When** login(), **Then** AuthError raised
```

### Tiered Invariants

| Tier | Who Writes It | What It Generates | Tool |
|------|--------------|-------------------|------|
| `example` | Any developer | Unit tests from Given/When/Then | pytest |
| `property` | Senior dev | Property-based tests auto-generated | Hypothesis |
| `formal` | Security/finance | Dafny mathematical proof | Dafny CLI |

## Verification Pipeline

Five stages, ordered cheapest-first with short-circuit on failure:

```
Stage 0: Pre-flight     [~0.5s]  AST parse + YAML schema validation
Stage 1: Dependency      [~1-2s]  Sealed manifest check [REF-C08]
Stage 2: Schema          [~0.5s]  Pydantic v2 contract validation
Stage 3: PBT             [~3-8s]  Hypothesis property-based testing
Stage 4: Formal          [~5-20s] Dafny mathematical verification
```

Stages 2 and 3 run in parallel. On failure, the Clover retry loop repairs code via structured LLM feedback.

## Code Generation

Three sequential LLM calls via litellm (model-agnostic):

```
.card.md → Analyst → Formalizer → Coder → module.dfy → verified artifact
```

Swap models with an environment variable:
```bash
CARD_MODEL=claude-sonnet-4-6      # Default
CARD_MODEL=deepseek/deepseek-chat  # Budget (10x cheaper)
CARD_MODEL=openai/o3               # Premium
```

## CLI Commands

```
contractd init [module]     Scaffold a .card.md spec
contractd generate          Generate code from spec via LLM
contractd verify            Run 5-stage verification pipeline
contractd verify --fast     Stages 0-3 only (skip Dafny)
contractd build             Generate + verify + compile
contractd ship              Build + sign artifact
contractd retry             Force LLM repair loop
contractd lock              Freeze deps into deps.lock
contractd explain           Show last failure in human-readable form
contractd optimize          Run DSPy SIMBA prompt optimization
contractd immune            Run immune system cycle on error traces
```

## MCP Server

CARD ships as an MCP server for universal IDE integration:

- `verify_contract` — Run verification on generated code
- `get_violations` — Get detailed violation report
- `suggest_fix` — LLM-suggested fix for violations

Compatible with Cursor, Windsurf, Claude Code, VS Code, and any MCP-supporting tool.

## Immune System

CARD's immune system learns from production failures and automatically strengthens specifications. Every failure makes the next build safer.

### How It Works

1. **Collect** -- MonkeyType [REF-T12] captures runtime type traces, OpenTelemetry [REF-T15] captures API spans, and Sentry-style error capture records failures with semantic fingerprinting
2. **Mine** -- Daikon algorithm (MIT reimplementation, see [REF-T13] warning) mines dynamic invariants from collected traces
3. **Enrich** -- LLM generates candidate invariants from mined patterns combined with error context, routed through litellm [REF-T16]
4. **Verify** -- CrossHair [REF-T09] (symbolic execution) and Hypothesis [REF-T03] (property-based testing) verify candidates with 1000+ inputs
5. **Append** -- Verified invariants auto-append to `.card.md` specs, strengthening the contract for future builds
6. **Enforce** -- icontract [REF-T10] decorators inject runtime guards into generated code

### Architecture

```
Production traces --> Collector --> Miner --> Enricher --> Verifier --> .card.md
       |                                                                  |
       +--- errors, types, spans                    stronger specs -------+
```

The immune cycle runs via `contractd immune` and can be triggered automatically on error ingestion or scheduled as a periodic job.

## Self-Evolution

CARD improves its own verification pipeline over time. Instead of static prompts, the system tracks what works and adapts.

- **Verification Tracking** -- SQLite database tracks every verification run: model used, pass rate, cost, latency, and failure modes
- **Experience Replay** -- Successful (spec, prompt, code) tuples are stored and become few-shot examples for future generation runs
- **DSPy SIMBA** [REF-T26] -- Optimizes the Analyst/Formalizer/Coder prompts for higher pass rates using automated prompt tuning
- **AutoResearch** -- Hill-climbing approach: try one prompt variation per run, keep it if the pass rate improves over the baseline
- **Versioned Prompts** -- All LLM prompts are externalized files with version metadata and performance tracking, not hardcoded strings

Run prompt optimization manually:
```bash
contractd optimize
```

## Network Effect

When multiple teams use CARD, failures discovered anywhere protect everyone. A single team's production bug becomes a verified invariant pattern available to all participants.

- **Structural Abstraction** -- Failures are transformed into PII-free type-level signatures before sharing, preserving privacy while retaining structural insight
- **Differential Privacy** -- OpenDP [REF-T20] applies Laplace noise to frequency metadata, ensuring no individual team's data can be reconstructed
- **Pattern Library** -- An append-only library of verified invariant patterns, each tagged with the domain and tier where it was proven
- **Herd Immunity** -- When a pattern holds across 50+ tenants at >95% confidence, it is promoted to a universal invariant and included in new project scaffolds automatically

The network effect creates a positive feedback loop: more teams produce more traces, which mine more invariants, which catch more bugs before they reach production.

## Demo

```bash
bash demo/run_demo.sh
```

See [demo/README.md](demo/README.md) for details.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design with reference citations.

## References

Every pattern in CARD traces to a specific academic citation. See [docs/REFERENCES.md](docs/REFERENCES.md) for the complete library of 35 papers, 25 tools, and 11 concepts.

Key references:
- [REF-P03] Clover — Closed-loop verified code generation (Stanford)
- [REF-P06] DafnyPro — Structured error format for LLM repair
- [REF-P07] ReDeFo — Analyst/Formalizer/Coder multi-agent pipeline
- [REF-P12] Dafny as IL — NL to verified target language (Amazon AWS)
- [REF-P02] Vericoding — 82-96% Dafny success rate benchmark

## Tech Stack

| Component | Tool | Reference |
|-----------|------|-----------|
| Language | Python 3.11+ | |
| CLI | Click | [REF-T17] |
| CLI formatting | Rich | -- |
| LLM | litellm | [REF-T16] |
| Verification | Dafny 4.x | [REF-T01] |
| PBT | Hypothesis | [REF-T03] |
| Schema | Pydantic v2 | [REF-T08] |
| Runtime contracts | icontract | [REF-T10] |
| Symbolic verification | CrossHair | [REF-T09] |
| Type tracing | MonkeyType | [REF-T12] |
| Telemetry | OpenTelemetry | [REF-T15] |
| Prompt optimization | DSPy SIMBA | [REF-T26] |
| Differential privacy | OpenDP | [REF-T20] |
| MCP | MCP SDK | [REF-T18] |

## License

MIT
