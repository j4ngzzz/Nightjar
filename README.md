<div align="center">
  <pre>
    ╔╗╔╦╔═╗╦ ╦╔╦╗ ╦╔═╗╦═╗
    ║║║║║ ╦╠═╣ ║  ║╠═╣╠╦╝
    ╝╚╝╩╚═╝╩ ╩ ╩╚╝╩╩ ╩╩╚═
  </pre>
  <h3>Your LLM writes code. Nightjar proves it.</h3>
  <p><em>Not tested. Proved.</em></p>

  <a href="#quick-start"><img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build" /></a>
  <a href="#verification-pipeline"><img src="https://img.shields.io/badge/tests-1202%20passing-brightgreen" alt="Tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License" /></a>
  <a href="#confidence-score"><img src="https://img.shields.io/badge/verified-nightjar-00FF88" alt="Verified" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python" /></a>
</div>

<br>

<div align="center">
  <img src="demo/nightjar-demo.gif" alt="Nightjar 60-second demo" width="700" />
  <br>
  <sub>Generate → Verify → Prove. In 60 seconds.</sub>
</div>

---

## The Problem

> *"I 'Accept All' always, I don't read the diffs anymore."*
> -- [Andrej Karpathy](https://x.com/karpathy)

- **84%** of developers use AI coding tools
- **96%** don't fully trust the output ([Sonar 2025](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/))
- **Only 48%** verify before committing
- **45%** of AI-generated code has security vulnerabilities ([Veracode 2025](https://www.getautonoma.com/blog/vibe-coding-security-risks))
- AI-coauthored PRs have **1.7x** more issues

> *"An AI that generates provably correct code is qualitatively different
> from one that merely generates plausible code."*
> -- [Leonardo de Moura](https://leodemoura.github.io/blog/2026/02/28/when-ai-writes-the-worlds-software.html), creator of Lean & Z3

Other tools find bugs. Nightjar **proves their absence.**

---

## The Solution

```bash
pip install nightjar
nightjar verify payment.py
```

Nightjar runs a 5-stage verification pipeline on AI-generated code:

| Stage | What | Time | Guarantee |
|-------|------|------|-----------|
| 0. Preflight | Syntax, imports | <100ms | Valid Python |
| 1. Dependencies | CVE scan, SBOM | <500ms | No known vulns |
| 2. Schema | Type checking | <200ms | Type-correct |
| 3. Property | Hypothesis PBT | 300ms-8s | Statistical |
| 4. Formal | Dafny/CrossHair | 1-30s | **Mathematical proof** |

Simple functions route to CrossHair only (70% faster). Complex functions get full Dafny. Nightjar decides automatically.

---

## Quick Start

```bash
# Install
pip install nightjar

# Auto-generate invariants from intent
nightjar auto "payment processor that charges credit cards"

# Verify generated code
nightjar verify

# Watch mode -- verify on every save
nightjar watch
```

### Prerequisites

- Python 3.11+
- Dafny 4.x ([install](https://github.com/dafny-lang/dafny/releases)) -- or set `DAFNY_PATH`
- Stage 4 gracefully degrades to CrossHair/Hypothesis if Dafny is not installed

---

## Features

**Shadow CI** -- Non-blocking GitHub Action. Never fails your build. First time it catches a real bug, your CTO mandates it.

**OWASP Security Pack** -- Formally proves absence of SQL injection, XSS, command injection. Not pattern-matching. Mathematical proof.

**Zero-Friction Mode** -- `nightjar auto "your intent"` generates all invariants. You approve in 30 seconds.

**Watch Mode** -- Sub-second feedback. Background daemon verifies on every save with 4-tier streaming.

**Confidence Score** -- 0-100 transparent score. Know exactly how verified your code is.

**Safety Gate** -- Blocks regeneration if previously-proven invariants would be lost.

**Spec Preprocessing** -- 19 rewrite rules double Dafny success rates before code even touches the LLM.

**CEGIS Retry** -- Counterexample-guided repair. When Dafny fails, the exact failing input drives the fix.

**Root-Cause Diagnosis** -- LP dual variables pinpoint which constraint is the binding root cause.

**Immune System** -- Learns from production failures. Sentry errors feed the mining pipeline automatically.

**Adversarial Debate** -- A skeptic agent challenges every mined invariant before it enters your spec.

---

## How Nightjar Compares

| | Nightjar | Cursor | Kiro | Tessl | Axiom | CodeRabbit |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Generates code | Y | Y | Y | Y | Y | -- |
| Formal proof | **Y** | -- | -- | -- | Y | -- |
| Security proof | **Y** | -- | -- | -- | -- | -- |
| Auto invariants | **Y** | -- | partial | partial | -- | -- |
| Watch mode | **Y** | -- | -- | -- | -- | -- |
| Safety gate | **Y** | -- | -- | -- | -- | -- |
| Developer CLI | **Y** | IDE | IDE | CLI | API | GitHub |
| Price | **Free** | $20/mo | Free | Beta | Enterprise | $15/seat |
| Open source | **AGPL** | -- | -- | partial | -- | -- |

---

## The 60-Second Demo

```bash
# 1. See the insecure code
$ cat demo/payment.py
def deduct(balance, amount):
    return balance - amount   # BUG: allows negative balance

# 2. Nightjar catches it
$ nightjar verify -c demo/payment.card.md
Stage 4 FAIL: counterexample balance=0.01, amount=50 -> -49.99

# 3. Auto-generate safe spec from plain English
$ nightjar auto "payment processor with balance >= 0 invariant"
Created spec: .card/payment.card.md (8 invariants, 6 approved)

# 4. Verify the fixed code -- PROVED
$ nightjar verify -c .card/payment.card.md
VERIFIED -- all stages passed (confidence: 85/100)
```

---

## CLI Commands

```
nightjar init [module]       Scaffold a .card.md spec
nightjar auto "intent"       Generate spec from natural language
nightjar generate            Generate code from spec via LLM
nightjar verify              Run 5-stage verification pipeline
nightjar verify --fast       Stages 0-3 only (skip Dafny)
nightjar build               Generate + verify + compile
nightjar ship                Build + sign artifact
nightjar retry               CEGIS counterexample-guided repair loop
nightjar lock                Freeze deps into deps.lock
nightjar explain             Root-cause diagnosis with LP dual variables
nightjar watch               File-watching daemon with 4-tier streaming
nightjar badge               Generate "Nightjar Verified" shields.io badge
nightjar optimize            DSPy SIMBA prompt optimization
nightjar immune              Run immune system mining cycle
```

---

## Verification Pipeline

### Confidence Score (0-100)

| Stage | Points | What it proves |
|-------|--------|---------------|
| pyright type check | +15 | Static type correctness |
| deal static analysis | +10 | Pre/postcondition satisfiability |
| CrossHair symbolic | +35 | Symbolic proof for explored paths |
| Hypothesis PBT | +20 | Statistical coverage (10K+ examples) |
| Dafny formal proof | +20 | Full mathematical correctness |

### Graceful Degradation

```
Dafny timeout -> CrossHair symbolic verification
CrossHair timeout -> Hypothesis PBT extended (10K examples)
All fail -> Report partial confidence score with gap notation
```

### Complexity-Based Routing

Simple functions (low cyclomatic complexity) route to CrossHair only -- ~70% faster. Complex functions get full Dafny. Nightjar measures AST depth and cyclomatic complexity to decide automatically.

### Behavioral Safety Gate

New code is compared against the previous `verify.json`. If invariants are lost, regeneration is blocked. If confidence score drops, a warning is issued.

---

## Zero-Friction Mode

```bash
nightjar auto "Build a payment processor that charges credit cards"
```

1. Parse natural language intent
2. LLM generates candidate invariants
3. Intent router classifies: numerical / behavioral / state / formal
4. Domain generators: icontract `@require/@ensure`, Hypothesis `@given`, Dafny `requires/ensures`
5. Ranking surfaces top 5-10 (not all 50)
6. Human approval in 30 seconds (Y/n/modify)
7. Write to `.card.md` and run verification

---

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

Repeat verifications with no changes: **<50ms** (Salsa-style per-stage caching).

---

## Security Mode

```yaml
# .github/workflows/nightjar.yml
- uses: nightjar/verify@v1
  with:
    mode: shadow     # NEVER fail the build
    report: full
    security-pack: owasp
```

- **Shadow CI** -- Reports findings as PR comments. Never blocks your pipeline.
- **OWASP Pack** -- SQL injection + XSS invariant templates with formal proof of absence.
- **Violation Explainer** -- LLM-enhanced Dafny error translation to human-readable text with root-cause LP diagnosis.
- **EU CRA Compliance** -- Structured compliance certificates (SBOM + verification timestamp). EU obligations begin September 2026.

---

## Immune System

Nightjar learns from production failures and automatically strengthens specifications.

```
Production errors (Sentry) -> Collector -> Miner -> Quality Filter -> Debate -> Verifier -> .card.md
       |                                                                                      |
       +--- runtime traces, Sentry events                             stronger specs ---------+
```

1. **Collect** -- sys.monitoring (PEP 669) captures runtime traces at <5% overhead. Sentry errors feed directly into the pipeline.
2. **Mine** -- Clean-room Daikon algorithm (19 Ernst templates) detects dynamic invariants
3. **Quality Score** -- Wonda-based AST normalization filters trivial invariants
4. **Debate** -- Adversarial skeptic agent challenges each candidate before acceptance
5. **Filter** -- Houdini fixed-point finds maximal inductive subset via Z3
6. **Verify** -- CrossHair + Hypothesis verify candidates with 1000+ inputs
7. **Append** -- Verified invariants auto-append to `.card.md` specs
8. **Supersede** -- Temporal decay removes stale invariants when behavior evolves

### Mining Stack (3-Tier)

| Tier | Method | Tool | Overhead |
|------|--------|------|----------|
| 1 | Semantic | LLM-based property generation | Zero |
| 2 | Runtime | Clean-room Daikon + Houdini | Low (sys.monitoring) |
| 3 | API-level | MINES web API mining | None (OTel logs) |

---

## Architecture

```
Intent (.card.md)
    |
    +-> nightjar auto -> Generate invariants -> Approve (30s)
    |
    v
Spec Preprocessing (19 rewrite rules)
    |
    v
Generation (litellm -> any LLM)
    |
    v
Verification Pipeline
    +-- Stage 0: Preflight (AST + YAML)
    +-- Stage 1: Dependencies (pip-audit + SBOM)
    +-- Stage 2: Schema (Pydantic v2)
    +-- Stage 2.5: Negation-Proof (catch weak specs)
    +-- Stage 3: Property (Hypothesis PBT)
    +-- Stage 4: Formal (Dafny + CrossHair + fallback)
    |
    v
Verified Artifact (dist/) + Proof Certificate (.card/verify.json)
    |
    v
Immune System (Sentry + runtime mining -> new invariants -> spec evolves)
```

---

## Model Agnostic

All LLM calls go through litellm. Swap with an environment variable:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # Default
NIGHTJAR_MODEL=deepseek/deepseek-chat  # Budget (10x cheaper)
NIGHTJAR_MODEL=openai/o3               # Premium
```

---

## MCP Server

Nightjar ships as an MCP server for universal IDE integration:

- `verify_contract` -- Run verification on generated code
- `get_violations` -- Get detailed violation report
- `suggest_fix` -- LLM-suggested fix for violations

Compatible with Cursor, Windsurf, Claude Code, VS Code, and any MCP-supporting tool.

---

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
    rule: "for any balance >= 0: deposit(balance, amount) > balance"
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

---

## Contractual Computing

Nightjar implements **Contractual Computing** -- a paradigm where:

1. The **contract** is the only permanent artifact -- code is regenerated every build
2. **Generation** is commodity -- verification is the differentiator
3. Contracts are **discoverable** -- mined automatically from runtime
4. Contracts are **transferable** -- any agent can verify any code
5. Contracts **compound** -- your codebase gets safer over time

---

## Tech Stack

| Component | Tool | Reference |
|-----------|------|-----------|
| Language | Python 3.11+ | |
| CLI | Click | [REF-T17] |
| TUI | Textual | MIT |
| LLM | litellm | [REF-T16] |
| Formal verification | Dafny 4.x | [REF-T01] |
| Property-based testing | Hypothesis | [REF-T03] |
| Symbolic execution | CrossHair | [REF-T09] |
| Runtime contracts | icontract | [REF-T10] |
| Schema validation | Pydantic v2 | [REF-T08] |
| Invariant mining | sys.monitoring (PEP 669) | Ernst 2007 |
| Invariant filtering | Z3 (Houdini) | FME 2001 |
| Quality scoring | AST normalization | Wonda 2026 |
| Spec preprocessing | 19 rewrite rules | Proven (MIT) |
| File watching | watchdog | Apache-2.0 |
| Error tracking | Sentry | MIT |
| MCP | MCP SDK | [REF-T18] |

---

## References

Every pattern in Nightjar traces to a specific academic citation. See [docs/REFERENCES.md](docs/REFERENCES.md) for the complete library.

Key references:
- [Proven](https://github.com/melek/proven) -- Spec preprocessing rewrite rules (19 rules, 2x Dafny success)
- [DafnyPro](https://arxiv.org/abs/2601.05385) -- Diff-checker + invariant pruner + hint-augmentation
- [VerMCTS](https://arxiv.org/abs/2402.08147) -- BFS proof search with verifier-in-the-loop
- [SpecLoop](https://arxiv.org/abs/2603.02895) -- CEGIS counterexample-guided retry
- [Wonda](https://arxiv.org/abs/2603.15510) -- Invariant quality scoring
- [Ernst 2007](https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf) -- Dynamic invariant detection
- [Houdini](https://dl.acm.org/doi/10.1145/587051.587054) -- Greatest-fixpoint invariant filter
- [SafePilot](https://arxiv.org/abs/2603.21523) -- Complexity-discriminated verification routing

---

## 夜鹰 -- 你的LLM写代码，夜鹰证明它

夜鹰是第一个零摩擦形式化验证平台。AI生成代码，夜鹰数学证明它是正确的。

```bash
pip install nightjar
nightjar verify your_code.py
```

不是测试。是**证明**。

---

## License

AGPL-3.0 -- free for open source. Commercial license available for enterprises.
