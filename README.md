<div align="center">
  <pre>
    ╔╗╔╦╔═╗╦ ╦╔╦╗ ╦╔═╗╦═╗
    ║║║║║ ╦╠═╣ ║  ║╠═╣╠╦╝
    ╝╚╝╩╚═╝╩ ╩ ╩╚╝╩╩ ╩╩╚═
  </pre>
  <p><strong>Your LLM writes code. Nightjar proves it.</strong></p>
  <p><em>Not tested. Proved.</em></p>

  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python" /></a>
  <a href="https://pypi.org/project/nightjarzzz/"><img src="https://img.shields.io/pypi/v/nightjarzzz" alt="PyPI" /></a>
</div>

<br>

[English](README.md) | [中文](README-zh.md)

---

```
$ nightjar verify --spec .card/payment.card.md

  Stage 0 (preflight)    PASS    12ms
  Stage 1 (deps)         PASS    45ms
  Stage 2 (schema)       PASS    23ms
  Stage 3 (pbt)          FAIL    340ms
    INV-01 violated: counterexample x=0 -> ZeroDivisionError
  Stage 4 (formal)       SKIP

  Result: 1 violation found
  Trust: PROPERTY_VERIFIED (0.60)
```

---

## Bugs it found in real packages

We ran Nightjar against some popular packages. Here's what came out.

**fastmcp 2.14.5 — JWT tokens never expire** (`server/auth/jwt_issuer.py:214`):

```python
exp = payload.get("exp")
if exp and exp < time.time():   # "if exp" is a truthy test, not a None check
    raise JoseError("Token has expired")
```

Token missing an `exp` field: `exp = None`, `if None` is `False`, check skipped, token accepted forever. We caught this with a 3-line spec:

```yaml
invariants:
  - tier: property
    rule: "token missing exp claim must be rejected"
```

```
Stage 3 (pbt) FAIL — counterexample: exp=None -> token accepted
```

**httpx 0.28.1 — crash on empty Digest auth header** (`httpx._utils.unquote`):

```python
def unquote(value: str) -> str:
    return value[1:-1] if value[0] == value[-1] == '"' else value
    #                      ^ IndexError when value == ""
```

A server that responds with `Digest realm=,nonce=abc` produces an empty `realm` value. `unquote("")` crashes with `IndexError` instead of the `ProtocolError` the caller catches. Hypothesis found it in 500 examples.

**litellm — budget windows never reset** (`budget_manager.py`):

```python
def track_cost(self, user, cost, created_at=time.time()):
#                                            ^ evaluated once at module import, not per call
```

Classic mutable default argument bug. Every call shares the same `created_at` timestamp — the one from when the module loaded. Budget reset logic that depends on this value never fires correctly.

---

## Install

```bash
pip install nightjarzzz
nightjar init mymodule
nightjar verify --spec .card/mymodule.card.md
```

Python 3.11+. [Dafny 4.x](https://github.com/dafny-lang/dafny/releases) is optional — without it, Nightjar falls back to CrossHair and Hypothesis and still gives you a confidence score, just not a full proof.

---

## How it works

You write a `.card.md` spec describing what your code must do. An LLM generates the implementation. Nightjar runs five verification stages, cheapest first, and short-circuits on the first failure. Either you get a proof certificate or you get the exact counterexample that broke it.

| Stage | What | Time |
|-------|------|------|
| 0. Preflight | Syntax, imports | <100ms |
| 1. Dependencies | CVE scan | <500ms |
| 2. Schema | Pydantic v2 type check | <200ms |
| 3. Property | Hypothesis PBT | 300ms–8s |
| 4. Formal | Dafny / CrossHair | 1–30s |

Simple functions skip Dafny and go to CrossHair instead (about 70% faster). The routing is automatic — Nightjar measures cyclomatic complexity and AST depth and picks the right tool.

When Dafny fails, the CEGIS retry loop extracts the concrete counterexample and puts it in the next prompt. "Your spec fails on input X=5, Y=-3 because..." works better than pasting the raw Dafny error.

---

## Quick start

```bash
# Scaffold a spec
nightjar init payment

# Edit .card/payment.card.md and add your invariants, then:
nightjar generate --model claude-sonnet-4-6
nightjar verify --spec .card/payment.card.md

# Skip Dafny (faster, less rigorous)
nightjar verify --spec .card/payment.card.md --fast
```

Swap models with an env var:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # default
NIGHTJAR_MODEL=deepseek/deepseek-chat  # cheaper
NIGHTJAR_MODEL=openai/o3               # more expensive, worth it for hard proofs
```

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

Three invariant tiers: `example` generates unit tests. `property` generates Hypothesis PBT. `formal` generates Dafny proofs or CrossHair symbolic checks.

---

## MCP server

Nightjar also runs as an MCP server — Cursor, Windsurf, Claude Code, VS Code.

Three tools: `verify_contract`, `get_violations`, `suggest_fix`.

```json
{
  "mcpServers": {
    "nightjar": {
      "command": "nightjar",
      "args": ["mcp"]
    }
  }
}
```

---

## CLI

```
nightjar init [module]    Scaffold a .card.md spec
nightjar auto "intent"    Generate spec from plain English
nightjar generate         Generate code from spec via LLM
nightjar verify           Run the full pipeline
nightjar verify --fast    Stages 0–3 only (no Dafny)
nightjar build            Generate + verify + compile
nightjar watch            Re-verify on file save
nightjar retry            Counterexample-guided repair loop
nightjar explain          Root-cause diagnosis
nightjar lock             Freeze deps into deps.lock
nightjar badge            Shields.io badge from last verification
nightjar immune           Run invariant mining cycle
```

---

## Docs

- [Architecture](docs/ARCHITECTURE.md) — how the pipeline works internally
- [References](docs/REFERENCES.md) — papers the algorithms come from
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security](SECURITY.md)

---

## License

[AGPL-3.0](LICENSE). Free for open source.

Commercial license for teams that can't work with AGPL: $2,400/yr (teams) · $12,000/yr (enterprise). Contact: nightjar-license@proton.me
