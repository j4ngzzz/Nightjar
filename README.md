# contractd

**Contract-Anchored Regenerative Development** — the verification layer every vibe coding tool needs.

Developers write `.card.md` specs (intent + contracts + tiered invariants). AI generates code. `contractd` mathematically proves the code satisfies the invariants. Code is regenerated from scratch on every build — never manually edited.

## Why CARD?

96% of developers don't fully trust AI-generated code. Only 48% verify before committing. The result: **verification debt** — the gap between AI code volume and verification coverage.

CARD closes this gap with a 5-stage verification pipeline that costs ~$0.001 per run and completes in under 60 seconds.

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
```

## MCP Server

CARD ships as an MCP server for universal IDE integration:

- `verify_contract` — Run verification on generated code
- `get_violations` — Get detailed violation report
- `suggest_fix` — LLM-suggested fix for violations

Compatible with Cursor, Windsurf, Claude Code, VS Code, and any MCP-supporting tool.

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
| LLM | litellm | [REF-T16] |
| Verification | Dafny 4.x | [REF-T01] |
| PBT | Hypothesis | [REF-T03] |
| Schema | Pydantic v2 | [REF-T08] |
| MCP | MCP SDK | [REF-T18] |

## License

MIT
