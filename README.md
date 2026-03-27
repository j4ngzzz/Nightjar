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
  <sub>Generate, verify, prove. In 60 seconds.</sub>
</div>

---

## The problem

> *"I 'Accept All' always, I don't read the diffs anymore."*
> -- [Andrej Karpathy](https://x.com/karpathy)

84% of developers use AI coding tools. 96% don't fully trust what comes out ([Sonar 2025](https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/)). Only half even bother to verify before committing.

Meanwhile, 45% of AI-generated code ships with OWASP vulnerabilities ([Veracode 2025](https://www.getautonoma.com/blog/vibe-coding-security-risks)). Georgetown CSET measured an 86% XSS failure rate. AI-coauthored code carries **2.74× higher vulnerability rates** than human-written code — and 35 new CVEs from AI-generated code landed in March 2026 alone.

There's a gap between "the AI wrote it" and "you can trust it." Nightjar closes it with math.

> *"The limiting factor will not be the technology, but the culture change required for people to realise that formal methods have become viable in practice."*
> — [Martin Kleppmann](https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html), 2025

Nightjar's job is to make that culture change unnecessary. Vericoding — formally verified code generation — should require zero PhD and five minutes of setup.

> *"An AI that generates provably correct code is qualitatively different
> from one that merely generates plausible code."*
> -- [Leonardo de Moura](https://leodemoura.github.io/blog/2026/02/28/when-ai-writes-the-worlds-software.html), creator of Lean and Z3

---

## What Nightjar does

```bash
pip install nightjar
nightjar verify payment.py
```

Five verification stages, cheapest first, short-circuit on failure:

| Stage | What | Time | What you get |
|-------|------|------|-----------|
| 0. Preflight | Syntax, imports | <100ms | Valid Python |
| 1. Dependencies | CVE scan, SBOM | <500ms | No known vulns |
| 2. Schema | Type checking | <200ms | Type-correct |
| 3. Property | Hypothesis PBT | 300ms-8s | Statistical confidence |
| 4. Formal | Dafny/CrossHair | 1-30s | Mathematical proof |

Simple functions skip Dafny and go straight to CrossHair (about 70% faster). Complex ones get the full treatment. Nightjar figures out which is which by measuring cyclomatic complexity and AST depth.

The difference between finding bugs and proving they can't exist.

---

## Quick start

```bash
# Install
pip install nightjar

# Describe what you want in plain English
nightjar auto "payment processor that charges credit cards"

# Verify the generated code
nightjar verify

# Or leave it running in the background
nightjar watch
```

You need Python 3.11+ and optionally [Dafny 4.x](https://github.com/dafny-lang/dafny/releases) for Stage 4. Without Dafny, verification gracefully falls back to CrossHair and Hypothesis. You still get a confidence score; it just won't hit 100.

---

## See it work

```bash
# Here's some insecure code
$ cat demo/payment.py
def deduct(balance, amount):
    return balance - amount   # BUG: allows negative balance

# Nightjar catches it with a concrete counterexample
$ nightjar verify -c demo/payment.card.md
Stage 4 FAIL: counterexample balance=0.01, amount=50 -> -49.99

# Generate a safe spec from plain English
$ nightjar auto "payment processor with balance >= 0 invariant"
Created spec: .card/payment.card.md (8 invariants, 6 approved)

# Now it passes
$ nightjar verify -c .card/payment.card.md
VERIFIED -- all stages passed (confidence: 85/100)
```

---

## What makes it different

We looked at what else exists. The short version: nobody else does formal proof + auto-invariants + watch mode in a single CLI tool.

| | Nightjar | Cursor | Kiro | Tessl | Axiom | CodeRabbit |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Generates code | yes | yes | yes | yes | yes | no |
| Formal proof | **yes** | no | no | no | yes | no |
| Security proof | **yes** | no | no | no | no | no |
| Auto invariants | **yes** | no | partial | partial | no | no |
| Watch mode | **yes** | no | no | no | no | no |
| Safety gate | **yes** | no | no | no | no | no |
| Price | free | $20/mo | free | beta | enterprise | $15/seat |
| Open source | AGPL | no | no | partial | no | no |

---

## Features worth knowing about

**Shadow CI.** A GitHub Action that runs verification on every PR but never fails the build. It just leaves a comment. The first time it catches a real SQL injection that passed all your tests, it sells itself.

```yaml
- uses: nightjar/verify@v1
  with:
    mode: shadow
    security-pack: owasp
```

**Zero-friction mode.** You type `nightjar auto "payment processor"` and it generates invariants from your description, classifies them (numerical, behavioral, state, formal), lets you approve each one, and writes the `.card.md`. The whole thing takes about 30 seconds of your time.

**Watch mode.** Runs in the background. When you save a `.card.md` file, it runs four tiers of verification (syntax in <100ms, structural in <2s, property in <10s, formal in 1-30s). Repeat runs with no changes finish in under 50ms thanks to Salsa-style per-stage caching.

**Confidence score.** Every verification produces a score from 0 to 100: pyright (+15), deal static analysis (+10), CrossHair symbolic (+35), Hypothesis PBT (+20), Dafny formal proof (+20). You always know exactly where you stand.

**Safety gate.** Before regenerating code, Nightjar compares new proofs against the previous verified state. If any invariants would be lost, it blocks the regeneration. If the confidence score drops, it warns you.

**OWASP security pack.** Invariant templates that formally prove the absence of SQL injection, XSS, and command injection. Not pattern-matching. Actual proof. The EU CRA compliance deadline is September 2026, and Nightjar can generate the structured compliance certificates you'll need.

**Spec preprocessing.** 19 deterministic rewrite rules (from [Proven](https://github.com/melek/proven), MIT) normalize your specs before they touch the LLM. This roughly doubles Dafny success rates on local models, and pushes Claude Sonnet from 65% to 78%.

**CEGIS retry.** When Dafny fails, Nightjar parses the concrete counterexample and includes it in the retry prompt. "Your spec fails on input X=5, Y=-3 because..." is a lot more useful to an LLM than a generic error message.

---

## The immune system

Nightjar learns from your production failures. When something breaks, it gets smarter.

```
Sentry errors + runtime traces
        |
        v
   Collector (sys.monitoring, PEP 669, <5% overhead)
        |
        v
   Miner (19 Ernst/Daikon templates)
        |
        v
   Quality gate (Wonda scoring, filters out trivial invariants)
        |
        v
   Adversarial debate (a skeptic agent tries to refute each candidate)
        |
        v
   Houdini filter (Z3 finds the maximal inductive subset)
        |
        v
   CrossHair + Hypothesis (verify with 1000+ inputs)
        |
        v
   Auto-append to .card.md (your spec evolves)
```

Old invariants decay over time if no new observations confirm them. New observations can supersede stale ones. The spec stays current with how your code actually behaves.

Three tiers of mining run in parallel: semantic (LLM-based), runtime (Daikon + Houdini), and API-level (MINES, from OTel logs).

---

## CLI

```
nightjar init [module]       Scaffold a .card.md spec
nightjar auto "intent"       Generate spec from plain English
nightjar generate            Generate code from spec via LLM
nightjar verify              Run the verification pipeline
nightjar verify --fast       Stages 0-3 only (skip Dafny)
nightjar build               Generate + verify + compile
nightjar ship                Build + sign artifact
nightjar retry               Counterexample-guided repair loop
nightjar lock                Freeze deps into deps.lock
nightjar explain             Root-cause diagnosis (LP dual variables)
nightjar watch               Background daemon, 4-tier streaming
nightjar badge               Shields.io badge from last verification
nightjar optimize            DSPy SIMBA prompt optimization
nightjar immune              Run immune system mining cycle
```

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
    +-- Stage 2.5: Negation-Proof (catch weak specs early)
    +-- Stage 3: Property (Hypothesis PBT)
    +-- Stage 4: Formal (Dafny + CrossHair + fallback)
    |
    v
Verified Artifact + Proof Certificate (.card/verify.json)
    |
    v
Immune System (Sentry + runtime mining -> stronger specs over time)
```

---

## The .card.md format

You write specs. AI generates code. Nightjar proves the code matches the spec.

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

Invariants come in three tiers. `example` generates unit tests (any developer can write these). `property` generates Hypothesis property-based tests (requires some testing experience). `formal` generates Dafny proofs or CrossHair symbolic checks (for security-critical code).

---

## Model agnostic

All LLM calls go through litellm. Swap models with an environment variable:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # Default
NIGHTJAR_MODEL=deepseek/deepseek-chat  # Budget option
NIGHTJAR_MODEL=openai/o3               # Premium option
```

---

## MCP server

Nightjar is also an MCP server, so it works inside any IDE that supports the protocol: Cursor, Windsurf, Claude Code, VS Code.

Three tools: `verify_contract` (run verification), `get_violations` (get the report), `suggest_fix` (LLM-suggested repair).

---

## Contractual computing

The idea behind Nightjar is that the contract (the `.card.md` spec) is the permanent artifact, not the code. Code gets regenerated every build. The spec is what survives.

This leads to some interesting properties: contracts are discoverable (the immune system mines them from runtime), transferable (any agent can verify any code against a spec), and they compound (your codebase gets safer the longer you run it, because more invariants accumulate).

We call this "contractual computing." As far as we can tell, nobody else has claimed the term.

---

## Tech stack

| Component | Tool |
|-----------|------|
| Language | Python 3.11+ |
| CLI | Click |
| TUI | Textual |
| LLM | litellm |
| Formal verification | Dafny 4.x |
| Property-based testing | Hypothesis |
| Symbolic execution | CrossHair |
| Runtime contracts | icontract |
| Schema | Pydantic v2 |
| Invariant mining | sys.monitoring (PEP 669) |
| Invariant filtering | Z3 via Houdini algorithm |
| Quality scoring | Wonda-style AST normalization |
| Spec preprocessing | Proven (MIT) |
| File watching | watchdog |
| Error tracking | Sentry |
| MCP | MCP SDK |

---

## References

The algorithms in Nightjar come from published papers. If you want to understand why something works the way it does, these are the places to look:

- [Proven](https://github.com/melek/proven) - spec preprocessing rewrite rules
- [DafnyPro](https://arxiv.org/abs/2601.05385) - diff-checker, invariant pruner, hint-augmentation
- [VerMCTS](https://arxiv.org/abs/2402.08147) - BFS proof search
- [SpecLoop](https://arxiv.org/abs/2603.02895) - CEGIS counterexample-guided retry
- [Wonda](https://arxiv.org/abs/2603.15510) - invariant quality scoring
- [Ernst 2007](https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf) - dynamic invariant detection
- [Houdini](https://dl.acm.org/doi/10.1145/587051.587054) - greatest-fixpoint invariant filter
- [SafePilot](https://arxiv.org/abs/2603.21523) - complexity-discriminated routing

Full citation library: [docs/REFERENCES.md](docs/REFERENCES.md)

---

## 夜鹰 (Nightjar)

你的 LLM 写代码，夜鹰证明代码是正确的。

### 问题

84% 的开发者在使用 AI 编程工具，但 96% 的人不完全信任生成的代码。45% 的 AI 生成代码包含 OWASP 安全漏洞。我们写了越来越多的代码，却越来越少地去验证它。

### 夜鹰是什么

夜鹰是一个面向 AI 生成代码的形式化验证平台。你用 `.card.md` 文件描述意图和约束条件，AI 生成代码，夜鹰用数学方法证明代码满足所有约束。

核心流程:

```bash
# 安装
pip install nightjar

# 用自然语言描述你的需求
nightjar auto "支付处理器，余额不能为负"

# 验证生成的代码
nightjar verify

# 后台持续监控
nightjar watch
```

### 五阶段验证流水线

| 阶段 | 内容 | 耗时 | 保证 |
|------|------|------|------|
| 0. 预检 | 语法、导入 | <100ms | 合法 Python |
| 1. 依赖 | CVE 扫描 | <500ms | 无已知漏洞 |
| 2. 模式 | 类型检查 | <200ms | 类型正确 |
| 3. 属性 | Hypothesis PBT | 300ms-8s | 统计覆盖 |
| 4. 形式化 | Dafny/CrossHair | 1-30s | 数学证明 |

### 核心功能

**影子 CI** - GitHub Action，只报告不阻塞构建。第一次捕获真正的 SQL 注入时，它就会成为团队标配。

**零摩擦模式** - `nightjar auto "你的需求"` 自动生成所有不变式，30 秒内完成审批。

**监控模式** - 保存文件时自动验证，首次反馈 <100ms。

**免疫系统** - 从生产故障中学习。Sentry 错误自动进入挖掘流水线，生成新的不变式。每次失败都让下次构建更安全。

**OWASP 安全包** - 形式化证明不存在 SQL 注入、XSS、命令注入。不是模式匹配，是数学证明。

**安全闸门** - 如果重新生成的代码丢失了之前已证明的不变式，夜鹰会阻止部署。

### 合约计算

夜鹰实现了"合约计算"范式: 合约 (`.card.md`) 是唯一的永久产物，代码每次构建都重新生成。合约可以被发现 (免疫系统从运行时挖掘)、可以转移 (任何代理都能验证任何代码)、可以累积 (代码库随时间变得更安全)。

不是测试。是**证明**。

---

## Verified with Nightjar

Nightjar's own parser and spec engine are verified using Nightjar itself.

```bash
nightjar verify --spec .card/parser.card.md --fast
# ✓ Stage 0: preflight   12ms
# ✓ Stage 1: deps         8ms
# ✓ Stage 2: schema       3ms
# ✓ Stage 3: property-tests  847ms
# VERIFIED — 4 stages passed
```

---

## Commercial License

Nightjar is [AGPL-3.0](LICENSE). If your organization cannot comply with AGPL (e.g., embedding Nightjar in a proprietary product), a commercial license is available.

**Pricing:** $2,400/yr (teams) · $12,000/yr (enterprise)
**Contact:** nightjar-license@proton.me

> One enterprise deal funds months of development. The AGPL is not punitive — it's a structural incentive to keep the ecosystem open.

---

## License

AGPL-3.0. Free for open source. Commercial license for enterprises — see above.

---

## Support

- [GitHub Sponsors](https://github.com/sponsors/nightjar-dev) — $5/mo supporter · $25/mo cloud beta · $99/mo priority support
- Commercial license for enterprise embedding
- Star the repo if Nightjar saved you from a bug
