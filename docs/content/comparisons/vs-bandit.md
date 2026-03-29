---
title: Nightjar vs Bandit — Python Security Linting vs Behavioral Proof
description: Bandit finds known vulnerability patterns. Nightjar proves behavioral invariants hold for all inputs. They guard different layers.
slug: vs-bandit
competitor: Bandit
competitor_version: "1.7.x (PyCQA, 2025)"
version_checked: "2026-03-29"
---

# Nightjar vs Bandit

## Security scanning and correctness proofs are different problems — and you need both.

Bandit is the go-to security linter for Python. It scans your code for known vulnerability patterns — hardcoded passwords, use of `pickle`, calls to `subprocess` with `shell=True`. Fast, well-maintained, widely integrated. If you write Python and care about security, you are probably already running Bandit.

Nightjar is not a replacement for Bandit. It proves something Bandit cannot: that your code satisfies behavioral invariants for *all possible inputs*, not just the ones that match a known pattern.

> **The gap:** Bandit knows `eval()` is dangerous. Nightjar knows your `transfer_funds` function can never produce a negative balance. These are different claims, and both matter.

---

## What Bandit Does Well

Bandit (v1.7.x, PyCQA) is a mature, battle-tested static analysis tool with a focused mission: find common security issues in Python code via AST analysis.

- **Speed**: Processes 1 GB of Python code in under 10 seconds. Runs in any CI pipeline without overhead.
- **Breadth**: Covers 120+ security tests organized into plugin categories: injection, cryptography, hardcoded secrets, insecure deserialization, and more.
- **Confidence levels**: Reports findings as LOW/MEDIUM/HIGH severity + confidence, letting teams triage by risk.
- **Zero configuration start**: `pip install bandit && bandit -r .` — that's it.
- **Ecosystem integration**: Built into MegaLinter, Semgrep, GitHub Advanced Security, and virtually every Python CI template.
- **Extensibility**: Custom plugins via the bandit plugin API for organization-specific rules.
- **Known false positive rate**: ~5-8% on typical codebases (lower than most SAST tools), well-understood and suppressible with `# nosec` annotations.

---

## Where Bandit Hits Its Limits

Bandit is a pattern matcher. It checks whether your code contains known dangerous patterns. It cannot:

**Check behavioral invariants.** Bandit cannot verify that `normalize_name("vit\uff41lik.eth")` returns a value different from `normalize_name("vitalik.eth")`. That bug (found by Nightjar in web3.py 7.14.1) has no dangerous AST pattern — it's a logic error that a pattern scanner will never detect.

**Prove absence of violations.** Bandit finding zero issues does not mean your code is correct. It means your code does not contain any of the 120+ known-bad patterns. Logic bugs, off-by-one errors, invariant violations — these are invisible to Bandit.

**Handle AI-generated code's failure modes.** LLMs generate code that looks structurally clean but violates behavioral contracts. AI code rarely uses `eval()` unsafely, but it frequently makes subtle logic errors that only manifest at specific input boundaries. Bandit misses all of these.

**Verify contracts for all inputs.** Bandit cannot tell you whether `budget_manager.create_budget()` has a default argument that evaluates at import time (the litellm bug Nightjar found). The code passes all security pattern checks; the invariant still breaks.

---

## Feature Comparison

| Feature | Nightjar | Bandit |
|---------|----------|--------|
| **Analysis type** | Formal proof + PBT + symbolic execution | Pattern matching (AST) |
| **Security vulnerability detection** | Partial (via Stage 1 dep audit) | Yes — primary purpose |
| **Behavioral invariant proving** | Yes — all inputs, mathematically | No |
| **Property-based testing (Hypothesis)** | Yes — Stage 3 | No |
| **Symbolic execution (CrossHair)** | Yes — Stage 2.5 | No |
| **Formal proof (Dafny)** | Yes — Stage 4 | No |
| **Spec format (.card.md)** | Yes | No |
| **AI-generated code gap** | Detects logic bugs LLMs produce | Does not apply |
| **Dependency CVE scanning** | Yes — Stage 1 (pip-audit) | No |
| **CEGIS repair loop** | Yes | No |
| **False positive rate** | Zero on confirmed bugs (74 bugs, 0 FP) | ~5-8% typical |
| **Configuration required** | Zero-friction (`nightjar scan`) | Zero-friction |
| **CI integration** | GitHub Actions, pre-commit, pytest | Widely supported |
| **License** | AGPL-3.0 (commercial license available) | Apache 2.0 |
| **Language support** | Python (primary) | Python only |
| **Speed (scan mode)** | Fast (scan), minutes (full verify) | Very fast (<10s/GB) |

---

## When to Use Bandit vs Nightjar

**Use Bandit when:**
- You need fast security pattern scanning in under 30 seconds
- You want to block known-dangerous patterns (hardcoded secrets, insecure crypto, SQL injection vectors)
- You're onboarding a new codebase and need a first-pass security baseline
- You want the lowest possible barrier to entry for security linting

**Use Nightjar when:**
- You need to prove behavioral correctness, not just catch known patterns
- You're using AI coding tools (Cursor, Copilot, Claude Code) and want a mathematical proof the generated code meets your spec
- You have business-critical invariants that a linter cannot verify (funds never go negative, user roles never escalate, tokens always expire)
- You need a compliance audit trail (EU CRA, SOC 2)

**Use both:**
Bandit runs first — fast, catches known patterns. Nightjar runs second — proves behavioral correctness. Together they cover two separate and non-overlapping risk layers.

---

## Can They Work Together?

Yes — and this is the recommended setup.

Bandit and Nightjar guard different layers. Run them in sequence in CI:

```yaml
# .github/workflows/verify.yml
- name: Security patterns (Bandit)
  run: bandit -r src/ -ll

- name: Behavioral proof (Nightjar)
  run: nightjar verify
```

Or as pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ["-ll"]
  - repo: local
    hooks:
      - id: nightjar-verify
        name: Nightjar verification
        entry: nightjar verify --fast
        language: system
```

Bandit's Apache 2.0 license is compatible with any usage. Nightjar's AGPL-3.0 core requires a commercial license for embedded proprietary use.

**The two tools are complementary, not competing.** Bandit answers "does this code contain dangerous patterns?" Nightjar answers "does this code satisfy its behavioral contracts?" Both questions deserve an answer.

---

## Get Started with Nightjar

```bash
pip install nightjar-verify
nightjar scan app.py           # extract contracts from your existing code
nightjar verify                # prove they hold
nightjar audit <package>       # A-F report card for any PyPI package
```

[Quickstart →](../docs/quickstart) · [Spec format →](../docs/spec-format) · [All comparisons →](../compare)
