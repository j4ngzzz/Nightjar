---
title: Nightjar vs Semgrep — Pattern-Based SAST vs Behavioral Proof
description: Semgrep catches code that looks wrong. Nightjar proves code that behaves wrong — for every possible input, not just the patterns someone wrote a rule for.
slug: vs-semgrep
competitor: Semgrep
competitor_version: "Community Edition + AppSec Platform (2025)"
version_checked: "2026-03-29"
---

# Nightjar vs Semgrep

## Rules tell you what code looks like. Proofs tell you what code does.

Semgrep is one of the most capable static analysis tools available. With 30+ supported languages, 20,000+ rules in the AppSec Platform, and a rule syntax that looks like actual code, it occupies a uniquely powerful position in the SAST market. Teams use Semgrep to enforce security policies, catch bug patterns, maintain style consistency, and block known-bad code at CI time.

Nightjar operates at a different level of abstraction. Where Semgrep asks "does this code match a known pattern?", Nightjar asks "does this code satisfy the behavioral spec you wrote, for all inputs?" These are orthogonal questions.

> **The gap:** Semgrep can tell you that a function calls `subprocess.run` with untrusted input. Nightjar can tell you that a function with perfect subprocess hygiene still violates the invariant that `transfer_amount > 0` when called with `amount = -1.0`.

---

## What Semgrep Does Well

Semgrep (Community Edition + AppSec Platform, 2025) is state-of-the-art in pattern-based analysis.

- **Semantic pattern matching**: Rules match code structure, not just text. A rule for `foo.bar()` matches regardless of how `foo` was imported. This eliminates many false positives that plague regex-based linters.
- **Language breadth**: 30+ languages including Python, JavaScript, TypeScript, Go, Java, Ruby, Rust, and more. One rule format across your whole stack.
- **20,000+ rules**: The AppSec Platform includes proprietary SAST, SCA (software composition analysis), and secrets detection rules. The open registry has 2,500+ community rules.
- **Custom rules in minutes**: Rule syntax looks like the code you're scanning. Writing `foo(...)` matches any call to `foo` with any arguments. No regex, no AST traversal.
- **AI-assisted analysis (2025)**: Semgrep Code now uses AI to detect complex flaws like IDOR and business-logic vulnerabilities alongside deterministic SAST.
- **Cross-file analysis**: Pro version traces data flow across files and function boundaries — taint analysis that Bandit cannot do.
- **IDE integration**: VS Code and IntelliJ extensions in Community Edition.
- **Broad CI support**: GitHub Actions, GitLab CI, CircleCI, Jenkins — first-class support everywhere.

---

## Where Semgrep Hits Its Limits

Semgrep's power is fundamentally bounded by what someone has written a rule for. Even with 20,000+ rules and AI augmentation, Semgrep cannot:

**Prove correctness for all inputs.** Semgrep flags code that matches patterns. It cannot verify that your `calculate_interest_rate()` function never returns a negative value across all possible floating-point inputs. You'd need to write a rule for every specific violation — which is impossible for behavioral properties.

**Verify invariants that aren't expressible as code patterns.** "The list of recipients must never include the sender" is a behavioral invariant. There is no code pattern that always violates it — only code that sometimes does, depending on runtime values. Semgrep operates pre-runtime; it sees structure, not values.

**Close the AI-generated code gap.** LLMs write structurally clean code that passes all pattern checks. The bugs Nightjar finds in production packages — budget windows that never reset, ENS names that resolve to the wrong address, JWT tokens from 1970 accepted as valid — have no pattern fingerprint. They are logic errors, not pattern violations.

**Provide a mathematical guarantee.** Semgrep finding zero violations means "no matching patterns found." Nightjar proving stage 4 means "no counterexample exists." These are qualitatively different claims. In regulated environments (EU CRA, SOC 2 audits), the mathematical proof is what auditors want to see.

**Generate code from specs.** Semgrep is an analysis tool. It does not generate or regenerate code to satisfy a contract.

---

## Feature Comparison

| Feature | Nightjar | Semgrep |
|---------|----------|---------|
| **Analysis approach** | Formal proof + PBT + symbolic execution | Semantic pattern matching + dataflow |
| **Languages supported** | Python (primary) | 30+ languages |
| **Behavioral invariant proving** | Yes — all inputs, Stage 3 + 4 | No |
| **Property-based testing** | Yes — Hypothesis, Stage 3 | No |
| **Symbolic execution** | Yes — CrossHair, Stage 2.5 | No |
| **Formal proof (Dafny)** | Yes — Stage 4 | No |
| **Custom rules / specs** | Yes — `.card.md` format | Yes — rule YAML/pattern syntax |
| **Security pattern detection** | Partial (dep audit, Stage 1) | Yes — primary purpose |
| **Cross-file dataflow / taint** | Partial (spec-scoped) | Yes (Pro/AppSec Platform) |
| **SCA (dependency scanning)** | Yes — Stage 1, pip-audit | Yes (AppSec Platform) |
| **Secrets detection** | No | Yes (AppSec Platform) |
| **AI-assisted detection** | LLM generates verified code | AI-assisted rule matching (2025) |
| **Spec-as-source / code generation** | Yes — core feature | No |
| **CEGIS repair loop** | Yes | No |
| **False positive rate** | Zero on confirmed findings | ~12% on dynamic code (community) |
| **Open source** | AGPL-3.0 | OSS (CE) + commercial (Platform) |
| **Pricing** | Free (AGPL) / Commercial license | Free (CE) / Team/Enterprise tiers |
| **CI integration** | GitHub Actions, pre-commit, pytest | Broad first-class support |

---

## When to Use Semgrep vs Nightjar

**Use Semgrep when:**
- You need multi-language analysis across Python, JS, Go, Java in a single tool
- You want to enforce security policies and style rules via custom rules
- You need taint/dataflow analysis to trace untrusted data across files
- You need secrets detection integrated with SAST in one platform
- You want coverage across all the vulnerability classes OWASP defines

**Use Nightjar when:**
- You need mathematical proof that behavioral invariants hold — not pattern matching
- Your team uses AI coding tools and needs verification, not just linting
- You have business-critical contracts that a rule cannot capture (financial invariants, access control guarantees, data integrity proofs)
- You need a compliance-grade audit trail with cryptographic provenance
- You want to prove properties that emerge from combinations of inputs, not from single-line patterns

**Use both:**
Semgrep enforces security patterns and style across your whole stack. Nightjar proves behavioral correctness for your Python modules. They operate at different layers and complement each other without overlap.

---

## Can They Work Together?

Yes. The integration is straightforward.

**In CI, run Semgrep first (faster), Nightjar second (deeper):**

```yaml
# .github/workflows/verify.yml
- name: Semgrep SAST
  uses: semgrep/semgrep-action@v1
  with:
    config: auto

- name: Nightjar behavioral proof
  run: nightjar verify
```

**As pre-commit hooks:**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/returntocorp/semgrep
    hooks:
      - id: semgrep
        args: ["--config=auto", "--error"]
  - repo: local
    hooks:
      - id: nightjar
        entry: nightjar verify --fast
        language: system
```

Semgrep scans all languages in your repo. Nightjar focuses on the Python modules that have `.card.md` specs. Neither tool steps on the other's territory.

**A practical note on Semgrep's AI features (2025):** Semgrep Code's AI-assisted analysis can detect some logic-level bugs. But this is probabilistic — the same model-based uncertainty that creates AI-generated bugs in the first place. Nightjar's formal proof is deterministic: a Dafny-verified function either satisfies the spec for all inputs or it doesn't. There is no "maybe."

---

## Get Started with Nightjar

```bash
pip install nightjar-verify
nightjar scan app.py           # bootstrap specs from your existing code
nightjar verify                # run all six verification stages
nightjar audit semgrep         # see Nightjar's verdict on Semgrep itself
```

[Quickstart →](../docs/quickstart) · [Spec format →](../docs/spec-format) · [All comparisons →](../compare)
