---
name: nightjar-verify
version: 1.0.0
description: >
  Formally verify AI-generated Python code with mathematical proof.
  Use when: agent wrote or modified Python code, user says "verify", "prove", "check correctness".
  NOT for: reading files, planning, non-Python code.
user-invocable: true
metadata:
  {
    "openclaw": {
      "emoji": "🔏",
      "requires": {
        "bins": ["nightjar", "python3"]
      },
      "install": [
        {
          "id": "pip-nightjar",
          "kind": "pip",
          "package": "nightjar-verify",
          "bins": ["nightjar"],
          "label": "Install Nightjar formal verification CLI"
        }
      ]
    }
  }
---

# Nightjar Verify — OpenClaw Skill

Formally verify AI-generated Python code with mathematical proof. This skill runs
Nightjar's 5-stage pipeline (preflight, deps, schema, property-based tests, Dafny
formal proof) against a `.card.md` spec file. It catches counterexamples that unit
tests miss and produces machine-checkable proofs.

This skill was built in the wake of the OpenClaw security incidents — CVE-2026-25593
(command injection), CVE-2026-26322 (path traversal), and the ClawHavoc campaign
(341 malicious skills, 9,000+ compromised installs). Those bugs all had one thing in
common: the code was never formally verified against its specification before shipping.

---

## When to Activate

Activate this skill automatically when:

- The agent has just written or modified a `.py` file
- The user says "verify", "prove", "check safety", "formal proof", or "run nightjar"
- A `.card.md` spec file exists in `.card/` for the module being edited
- The agent is writing an MCP tool handler, OpenClaw skill handler, or agent tool function
- The file contains security-sensitive code (auth, file I/O, network requests, subprocess calls)

Do NOT activate for:
- Reading files or exploring the codebase
- Planning or design discussions
- Non-Python files (JS, TS, Go, etc.)
- Files with no matching `.card.md` spec (offer to create one instead)

---

## Workflow — 4 Steps

### Step 1: Find or Create a Spec

Check whether a `.card.md` spec exists for the module:

```bash
ls .card/*.card.md
```

If a spec exists, proceed to Step 2.

If no spec exists, offer the user three options:

**Option A — Extract from existing code (fast, no LLM required):**
```bash
nightjar scan <file.py>
# Statically extracts invariants already present in the code.
# Good starting point. Produces .card/<module>.card.md.
```

**Option B — Infer via LLM + symbolic execution (richer, needs API key):**
```bash
nightjar infer <file.py>
# Combines LLM analysis with CrossHair symbolic execution.
# Generates contract candidates — review before trusting.
# Requires NIGHTJAR_MODEL env var (e.g. claude-sonnet-4-6).
```

**Option C — Scaffold an empty spec for manual editing:**
```bash
nightjar init <module_name>
# Creates .card/<module>.card.md with placeholder invariants.
# Edit the YAML blocks before running verify.
```

Recommend Option A first. If the scan produces fewer than 3 invariants, suggest Option B.

### Step 2: Run Verification

**Fast mode — PBT only, no Dafny required. Runs in seconds:**
```bash
nightjar verify --spec .card/<module>.card.md --fast
```

**Full formal proof — requires Dafny 4.x installed:**
```bash
nightjar verify --spec .card/<module>.card.md
```

**Scan an entire directory, security-critical files first:**
```bash
nightjar scan <dir/> --smart-sort
```

**Audit a PyPI package for contract coverage:**
```bash
nightjar audit <package-name>
# Produces a report card with letter grades (A–F) per module.
# Useful before adding a new dependency.
```

Use `--fast` by default unless the user explicitly asks for a full formal proof or
the module contains security-critical logic (auth, payments, file I/O).

### Step 3: Interpret and Report Results

Always present results in this format:

```
NIGHTJAR VERIFICATION
File: src/payment.py | Spec: .card/payment.card.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Stage 0 Preflight:  PASS
Stage 1 Deps:       PASS
Stage 2 Schema:     PASS
Stage 3 PBT:        FAIL — Counterexample: amount=-0.01
Stage 4 Formal:     SKIP (--fast mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESULT: FAIL — amount > 0 violated
FIX: Add guard `if amount <= 0: raise ValueError("amount must be positive")`
```

**Interpreting each outcome:**

| Result | Meaning | What to say |
|--------|---------|-------------|
| All PASS | All invariants hold | "Verified. All invariants hold mathematically." |
| Stage 3 FAIL | PBT found a counterexample | "Property test found a counterexample: [input] violates [invariant ID]." |
| Stage 4 FAIL | Dafny could not construct a proof | "Dafny could not prove [invariant]. Consider adding a loop invariant or a guard clause." |
| Stage 4 SKIP | Dafny not installed | "PBT passed. Install Dafny for full formal proofs: `brew install dafny`." |
| Exit code 3 | Verification timed out | "Verification timed out. Try `--fast` mode or reduce the number of PBT examples with `--max-examples 50`." |
| Exit code 4 | LLM API error | "LLM call failed. Check NIGHTJAR_MODEL and your API key." |
| Exit code 5 | Max retries exhausted | "CEGIS repair loop exhausted. Human review required — Nightjar cannot auto-fix this." |

**For Dafny errors**, translate them into plain Python terms. Do not surface raw
Dafny syntax to the user unless they ask. Instead say:
- "Dafny cannot prove the loop terminates" → "Add a decreasing loop counter as a loop invariant."
- "Postcondition might not hold" → "The function might return a value that violates [invariant]. Add an assertion before the return."

For human-readable explanations of the last failure:
```bash
nightjar explain
```

### Step 4: Fix and Re-Verify

When verification fails:

1. Show the exact counterexample input and the invariant it violates
2. Explain WHY it violated — what assumption the spec makes that the code breaks
3. Propose a minimal fix (prefer guard clause over restructuring)
4. Apply the fix
5. Re-run `nightjar verify --spec .card/<module>.card.md --fast`
6. Repeat until all stages PASS

Example fix cycle for a payment amount bug:

```
Invariant violated: INV-03 — amount > 0
Counterexample: process_payment(amount=-0.01, currency="USD")

The spec requires amount to be strictly positive, but the function
accepts negative values silently.

Fix: add at the top of process_payment():
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")

Re-running verification...
```

Do not stop at one fix. Re-verify. Only report success after `nightjar verify` exits 0.

---

## Security-Specific Workflow (for Agent/MCP Code)

When verifying MCP tool handlers, OpenClaw skill handlers, or any agent tool function,
run the security-focused verification path. These file patterns trigger it automatically:
- Files containing `@mcp.tool`, `FastMCP`, `@tool`, or `function_call`
- Files named `handler.py`, `tools.py`, `skills.py`, `agent.py`
- Files in directories named `tools/`, `skills/`, `handlers/`

For security-critical code, always use full verification (not `--fast`) and reference
these invariant classes that map to known OpenClaw CVEs:

| Invariant Class | CVE Reference | What it checks |
|----------------|---------------|----------------|
| SEC-INV-01 | CVE-2026-25593 | No shell execution with user-controlled input |
| SEC-INV-02 | (general) | All tool params validated against strict schema |
| SEC-INV-03 | CVE-2026-26322 | No file access outside allowed_paths |
| SEC-INV-04 | Moltbook breach | No secrets/tokens in tool output |
| SEC-INV-05 | CVE-2026-26319 | Network requests validated against allowlist |
| SEC-INV-07 | ClawHavoc | No dynamic tool registration from external input |
| SEC-INV-08 | (formal tier) | Proof that validation gate is never bypassed |

If any of these invariants are absent from the `.card.md` spec for an agent tool file,
warn the user and offer to add them via `nightjar scan --security-mode`.

---

## Additional Commands Reference

```bash
# Explain the last verification failure in plain English
nightjar explain

# Retry with CEGIS repair loop (LLM auto-fix)
nightjar retry --spec .card/<module>.card.md

# Lock dependencies with hashes (security boundary)
nightjar lock

# Full pipeline: generate + verify + compile
nightjar build --target py

# Scan entire directory, security-critical files first
nightjar scan <dir/> --smart-sort

# Audit a PyPI dependency before adding it
nightjar audit <package-name>
```

---

## Installation

```bash
pip install nightjar-verify
```

Requires Python 3.11+.

For full formal proofs (Stage 4), also install Dafny 4.x:
```bash
# macOS
brew install dafny

# Ubuntu/Debian
sudo apt-get install dafny

# Windows
winget install Microsoft.Dafny
```

Set the LLM model for `infer` and `retry` commands:
```bash
export NIGHTJAR_MODEL=claude-sonnet-4-6
# Or any litellm-compatible model string
```

Enable auto-verify on every file write (opt-in):
```bash
export NIGHTJAR_AUTO_VERIFY=1
```

---

## CI Integration

Add to `.github/workflows/verify.yml`:

```yaml
- name: Nightjar formal verification
  run: |
    pip install nightjar-verify
    nightjar verify --fast
  env:
    NIGHTJAR_MODEL: ${{ secrets.NIGHTJAR_MODEL }}
```

This runs PBT verification on every PR. Add Dafny to the runner image for full
formal proofs in CI.
