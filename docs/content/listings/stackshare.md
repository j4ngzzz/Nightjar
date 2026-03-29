# StackShare Listing — Nightjar

**Submission URL:** https://stackshare.io/tool-add
**Platform:** StackShare
**Status:** Draft — ready to submit post-launch

---

## One-Liner

This is the main copy field ("What is this tool?"). Hard limit: one sentence, ~20 words. Must be scannable in a stack card.

---

**Primary (recommended):**

> Formal verification pipeline for Python — coordinates Hypothesis, CrossHair, and Dafny to prove code satisfies its spec for all inputs.

---

**Alternate (if the primary reads as too long):**

> Python verification pipeline: property-based testing + symbolic execution + formal proof in a single `nightjar verify` command.

---

**Alternate (lead with the outcome):**

> Found 74 real bugs in 34 Python packages. Nightjar verifies Python code against behavioral specs using Hypothesis, CrossHair, and Dafny.

---

## Category

**Primary category:** Testing
**Secondary category:** Code Review / Static Analysis

StackShare's taxonomy closest matches:
- Testing Frameworks
- Static Analysis
- Security

Select the one the form forces you to pick first: **Testing Frameworks** (most accurate — it wraps Hypothesis and runs a test pipeline).

---

## Pricing / License

- **Free tier:** Full CLI, open-source, AGPL-3.0
- **Teams:** $2,400/year (removes AGPL obligations, adds support)
- **Enterprise:** $12,000/year (on-premise, compliance reporting, SSO)

---

## Website

https://nightjarcode.dev

---

## GitHub

https://github.com/j4ngzzz/Nightjar

---

## Integrations

List these in the "What does this tool integrate with?" section. All confirmed from the README integrations table.

| Integration | How |
|-------------|-----|
| **GitHub Actions** | `j4ngzzz/Nightjar@v1` action — posts SARIF annotations on PRs |
| **pytest** | `pytest --nightjar` flag adds verification as a test phase |
| **pre-commit** | `nightjar-verify` and `nightjar-scan` hooks block unverified commits |
| **VS Code** | `nightjar verify --format=vscode` outputs diagnostics to the Problems panel |
| **Claude Code** | `nightjar-verify` MCP skill — auto-verifies after AI generates code |
| **Docker** | Official Dockerfile bundles Dafny — zero local install required |
| **Dafny** | Formal proof backend (Stage 4) |
| **Hypothesis** | Property-based testing backend (Stage 3) |
| **CrossHair** | SMT symbolic execution backend (Stages 2.5 and 4) |
| **pip-audit** | Dependency CVE scanning backend (Stage 1) |
| **Pydantic** | Schema validation backend (Stage 2) |
| **MCP** | 3 MCP tools: `verify_contract`, `get_violations`, `suggest_fix` |

---

## "What is Nightjar used for?" — StackShare Decisions Section

If the platform has a free-text "Decisions" or "Why we use it" section, use this:

> We run `nightjar verify` in CI after every AI-assisted code change. It catches the class of bugs that unit tests miss — invariant violations that only appear at edge-case inputs. The `--fast` mode (skip Dafny) takes under 10 minutes on a 1,000-function codebase and fits comfortably in a pre-merge check.

---

## Submission Notes

- StackShare sometimes takes 1–3 business days to approve new tool listings.
- After approval, post Nightjar to the "Tech Stack" on your personal profile to seed visibility.
- The "Integrations" section drives a lot of discovery — getting listed as an integration on GitHub Actions' StackShare page (if possible) is high-value.
- Tag "nightjar-verify" as the PyPI package name when asked for package identifiers.
