<div align="center">
  <pre>
    ╔╗╔╦╔═╗╦ ╦╔╦╗ ╦╔═╗╦═╗
    ║║║║║ ╦╠═╣ ║  ║╠═╣╠╦╝
    ╝╚╝╩╚═╝╩ ╩ ╩╚╝╩╩ ╩╩╚═
  </pre>
  <h3>Your LLM writes code. Nightjar proves it.</h3>
  <p><em>Not tested. Proved.</em></p>

  <a href="#quick-start"><img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build" /></a>
  <a href="#verification-pipeline"><img src="https://img.shields.io/badge/tests-1265%20passing-brightgreen" alt="Tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License" /></a>
  <a href="#confidence-score"><img src="https://img.shields.io/badge/verified-nightjar-00FF88" alt="Verified" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python" /></a>
</div>

<br>

<div align="center">
  <img src="demo/nightjar-demo.gif" alt="Nightjar 60-second demo" width="700" />
  <br>
  <sub>Generate. Verify. Prove. 60 seconds.</sub>
</div>

---

## The problem

> *"I 'Accept All' always, I don't read the diffs anymore."*
> -- [Andrej Karpathy](https://x.com/karpathy)

84% of developers use AI coding tools. 96% don't fully trust the output ([Sonar 2025](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/)). Only 48% verify before committing. 45% of AI-generated code has security vulnerabilities ([Veracode 2025](https://www.getautonoma.com/blog/vibe-coding-security-risks)). AI-coauthored PRs have 1.7x more issues.

Nobody reads the diffs. The code ships anyway.

> *"An AI that generates provably correct code is qualitatively different
> from one that merely generates plausible code."*
> -- [Leonardo de Moura](https://leodemoura.github.io/blog/2026/02/28/when-ai-writes-the-worlds-software.html), creator of Lean and Z3

Every other tool finds bugs after the fact. Nightjar proves they can't exist.

---

## What it does

```bash
pip install nightjar
nightjar verify payment.py
```

Five verification stages, cheapest first, short-circuit on failure:

| Stage | What | Time | Guarantee |
|-------|------|------|-----------|
| 0. Preflight | Syntax, imports | <100ms | Valid Python |
| 1. Dependencies | CVE scan, SBOM | <500ms | No known vulns |
| 2. Schema | Type checking | <200ms | Type-correct |
| 3. Property | Hypothesis PBT | 300ms-8s | Statistical |
| 4. Formal | Dafny/CrossHair | 1-30s | Mathematical proof |

Simple functions (low cyclomatic complexity) skip Dafny and go straight to CrossHair, which is about 70% faster. Complex functions get the full treatment. Nightjar measures AST depth and decides.

---

## Quick start

```bash
# Install
pip install nightjar

# Auto-generate invariants from plain English
nightjar auto "payment processor that charges credit cards"

# Verify generated code
nightjar verify

# Watch mode: verify on every save
nightjar watch
```

You need Python 3.11+ and optionally Dafny 4.x ([install](https://github.com/dafny-lang/dafny/releases)). If Dafny isn't installed, Stage 4 falls back to CrossHair and extended Hypothesis instead of refusing to run.

---

## What you get

`nightjar auto` takes a sentence and turns it into a `.card.md` spec with typed invariants. You review them in 30 seconds. `nightjar watch` re-verifies on every save, with the first tier finishing in under 100ms. `nightjar badge` generates a shields.io badge from your last verification run.

The Shadow CI GitHub Action runs verification on every PR but never blocks the build. It just posts a comment. The first time it catches something real (and it will, statistically), your team starts paying attention.

The OWASP Security Pack goes further: formal proof that SQL injection and XSS can't happen. Not pattern-matching. Actual mathematical proof of absence. The Violation Explainer turns Dafny's cryptic SMT output into English, with the exact input that breaks your code.

When Dafny says "UNSAT" and you have no idea why, the LP root-cause diagnosis relaxes the Boolean constraints into a continuous linear program, solves for minimum violation, and uses dual variables to rank which constraint is actually the problem. It turns "verification failed" into "line 47 is the issue."

EU CRA compliance certificates come out of the box. Reporting obligations start September 2026.

The confidence score (0-100) breaks down exactly what each stage proved:

| Stage | Points | What it covers |
|-------|--------|---------------|
| pyright type check | +15 | Static types |
| deal static analysis | +10 | Pre/post satisfiability |
| CrossHair symbolic | +35 | Symbolic proof |
| Hypothesis PBT | +20 | 10K+ random inputs |
| Dafny formal proof | +20 | Full mathematical proof |

The safety gate compares new code against the previous `verify.json`. If invariants are lost, regeneration is blocked. If the confidence score drops, you get a warning.

---

## How it compares

| | Nightjar | Cursor | Kiro | Tessl | Axiom | CodeRabbit |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Generates code | Y | Y | Y | Y | Y | -- |
| Formal proof | Y | -- | -- | -- | Y | -- |
| Security proof | Y | -- | -- | -- | -- | -- |
| Auto invariants | Y | -- | partial | partial | -- | -- |
| Watch mode | Y | -- | -- | -- | -- | -- |
| Safety gate | Y | -- | -- | -- | -- | -- |
| Developer CLI | Y | IDE | IDE | CLI | API | GitHub |
| Price | Free | $20/mo | Free | Beta | Enterprise | $15/seat |
| Open source | AGPL | -- | -- | partial | -- | -- |

---

## The 60-second demo

```bash
# 1. The insecure code
$ cat demo/payment.py
def deduct(balance, amount):
    return balance - amount   # BUG: allows negative balance

# 2. Nightjar catches it
$ nightjar verify -c demo/payment.card.md
Stage 4 FAIL: counterexample balance=0.01, amount=50 -> -49.99

# 3. Auto-generate safe spec
$ nightjar auto "payment processor with balance >= 0 invariant"
Created spec: .card/payment.card.md (8 invariants, 6 approved)

# 4. Verify the fixed code
$ nightjar verify -c .card/payment.card.md
VERIFIED -- all stages passed (confidence: 85/100)
```

---

## CLI

```
nightjar init [module]       Scaffold a .card.md spec
nightjar auto "intent"       Generate spec from natural language
nightjar generate            Generate code from spec via LLM
nightjar verify              Run 5-stage verification pipeline
nightjar verify --fast       Stages 0-3 only (skip Dafny)
nightjar build               Generate + verify + compile
nightjar ship                Build + sign artifact
nightjar retry               CEGIS counterexample-guided repair
nightjar lock                Freeze deps into deps.lock
nightjar explain             Root-cause diagnosis (LP dual variables)
nightjar watch               File-watching daemon, 4-tier streaming
nightjar badge               shields.io badge from verify.json
nightjar optimize            DSPy SIMBA prompt optimization
nightjar immune              Run immune system mining cycle
```

---

## Watch mode

```bash
nightjar watch
```

Four tiers of verification, streaming:

| Tier | What | Latency |
|------|------|---------|
| 0: Syntax | AST parse, YAML frontmatter | <100ms |
| 1: Structural | Deps, schema, CrossHair quick | <2s |
| 2: Property | Hypothesis PBT, CrossHair watch | <10s |
| 3: Formal | Dafny with caching | 1-30s |

If nothing changed, re-verification takes under 50ms (Salsa-style per-stage caching with content-addressed hashing).

---

## Security mode

```yaml
# .github/workflows/nightjar.yml
- uses: nightjar/verify@v1
  with:
    mode: shadow
    report: full
    security-pack: owasp
```

Shadow mode posts findings as PR comments. Never fails the build. The OWASP pack covers SQL injection, XSS, and command injection with formal proofs. The violation explainer makes Dafny's SMT output readable. EU CRA compliance certificates are generated automatically.

---

## Immune system

Nightjar watches production. When things break, it gets smarter.

```
Production errors (Sentry) -> Collector -> Miner -> Quality Filter -> Debate -> Verifier -> .card.md
       |                                                                                      |
       +--- runtime traces, Sentry events                             stronger specs ---------+
```

The pipeline:

1. sys.monitoring (PEP 669) captures runtime traces at <5% overhead. Sentry errors feed in directly.
2. Clean-room Daikon (19 Ernst templates) detects invariants from those traces.
3. Wonda-based quality scoring filters out the trivial ones.
4. An adversarial "skeptic" LLM tries to break each candidate. Only survivors proceed.
5. Houdini fixed-point filtering (via Z3) finds the maximal inductive subset.
6. CrossHair + Hypothesis verify the survivors with 1000+ inputs.
7. Verified invariants append to `.card.md` specs automatically.
8. Temporal decay removes stale invariants when behavior legitimately evolves.

The mining runs across three tiers: semantic (LLM-based), runtime (Daikon + Houdini), and API-level (MINES, from OTel logs).

---

## The .card.md format

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

Three tiers of invariants:

| Tier | Who writes it | What it generates | Tool |
|------|--------------|-------------------|------|
| `example` | Any developer | Unit tests from Given/When/Then | pytest |
| `property` | Senior dev | Property-based tests | Hypothesis |
| `formal` | Security/finance | Mathematical proof | Dafny/CrossHair |

You pick the tier that matches your risk tolerance. Most teams start with `property` and add `formal` for the functions that handle money or auth.

---

## Architecture

```
Intent (.card.md)
    |
    +-> nightjar auto -> Generate invariants -> Approve (30s)
    |
    v
Spec Preprocessing (19 rewrite rules from Proven)
    |
    v
Generation (litellm -> any LLM)
    |
    v
Verification Pipeline
    +-- Stage 0: Preflight (AST + YAML)
    +-- Stage 1: Dependencies (pip-audit + SBOM)
    +-- Stage 2: Schema (Pydantic v2)
    +-- Stage 2.5: Negation-Proof (catch weak specs early)
    +-- Stage 3: Property (Hypothesis PBT)
    +-- Stage 4: Formal (Dafny + CrossHair + fallback ladder)
    |
    v
Verified Artifact (dist/) + Proof Certificate (.card/verify.json)
    |
    v
Immune System (Sentry + runtime mining -> new invariants -> spec evolves)
```

The spec preprocessing step (19 rewrite rules from [Proven](https://github.com/melek/proven)) normalizes quantifier scoping and decomposes compound postconditions before anything touches the LLM. This roughly doubles Dafny success rates on local models.

---

## Contractual Computing

Nightjar is built around an idea we call Contractual Computing:

The contract is the permanent artifact. Code gets regenerated every build. Verification is what matters, not generation. Contracts are discoverable (the immune system mines them from runtime). Contracts are transferable (any agent can verify any code). And contracts compound: your codebase gets safer over time without anyone doing extra work.

---

## Model agnostic

All LLM calls go through litellm. Set the model with an environment variable:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # Default
NIGHTJAR_MODEL=deepseek/deepseek-chat  # 10x cheaper
NIGHTJAR_MODEL=openai/o3               # When you need it
```

---

## MCP server

Nightjar is also an MCP server. Three tools: `verify_contract`, `get_violations`, `suggest_fix`. Works with Cursor, Windsurf, Claude Code, VS Code, or anything that speaks MCP.

---

## Tech stack

| Component | Tool |
|-----------|------|
| Language | Python 3.11+ |
| CLI | Click |
| TUI | Textual |
| LLM | litellm |
| Formal verification | Dafny 4.x |
| Property testing | Hypothesis |
| Symbolic execution | CrossHair |
| Runtime contracts | icontract |
| Schema | Pydantic v2 |
| Invariant mining | sys.monitoring (PEP 669) |
| Invariant filtering | Z3 (Houdini algorithm) |
| Quality scoring | Wonda-style AST normalization |
| Spec preprocessing | Proven (19 rules) |
| File watching | watchdog |
| Error tracking | Sentry |
| MCP | MCP SDK |

---

## References

Every algorithm traces to a paper. See [docs/REFERENCES.md](docs/REFERENCES.md) for the full list.

- [Proven](https://github.com/melek/proven) -- 19 spec rewrite rules, ~2x Dafny success on local models
- [DafnyPro](https://arxiv.org/abs/2601.05385) -- Diff-checker + invariant pruner + hint-augmentation
- [VerMCTS](https://arxiv.org/abs/2402.08147) -- BFS proof search, verifier-in-the-loop
- [SpecLoop](https://arxiv.org/abs/2603.02895) -- CEGIS counterexample-guided retry
- [Wonda](https://arxiv.org/abs/2603.15510) -- Invariant quality scoring
- [Ernst 2007](https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf) -- Dynamic invariant detection
- [Houdini](https://dl.acm.org/doi/10.1145/587051.587054) -- Greatest-fixpoint invariant filter
- [SafePilot](https://arxiv.org/abs/2603.21523) -- Complexity-discriminated routing

---

## 夜鹰 -- 你的LLM写代码，夜鹰证明它

夜鹰是第一个零摩擦形式化验证平台。AI生成代码，夜鹰数学证明它是正确的。

```bash
pip install nightjar
nightjar verify your_code.py
```

不是测试。是证明。

---

## License

AGPL-3.0. Free for open source. [Commercial license](mailto:hello@nightjar.dev) for everything else.
