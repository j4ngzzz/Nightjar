---
name: nightjar-verify
description: Formally verify AI-generated code after every generation. Catches bugs that tests miss — with mathematical proof, not pattern matching.
---

# Nightjar Verify

Formally verify AI-generated code. Not tested — proved.

AI-generated code has a 2.74x higher vulnerability rate. Nightjar runs a 5-stage verification pipeline (preflight, deps, schema, property-tests, formal-proof) to catch bugs before they ship.

## When to use

- After generating or modifying any Python code
- When the user mentions "verify", "prove", "check", "safe", "correct"
- Before committing AI-generated code

## What to do

1. Check if a `.card.md` spec exists for the module:
   ```bash
   ls .card/*.card.md
   ```

2. If no spec, create one:
   No spec found. Use the nightjar-spec skill to create one interactively (reads your code, suggests invariants, asks a few questions), or run `nightjar scan <file>` for auto-generation from type hints and guard clauses.
   ```bash
   # Option A: interactive skill — no YAML knowledge required
   # Invoke the nightjar-spec skill in Claude Code

   # Option B: auto-generate from existing code
   nightjar scan <file>

   # Option C: start from a blank template
   nightjar init <module_name>
   # Then edit .card/<module_name>.card.md to add invariants
   ```

3. Run verification:
   ```bash
   nightjar verify --spec .card/<module_name>.card.md
   ```

4. Report results. If a stage FAILs, show the counterexample and suggest a fix.

5. After fixing, re-run to confirm the fix holds.

## Install

```bash
pip install nightjarzzz
```

## Why

- OpenClaw had 280,000 GitHub stars and 60+ CVEs
- Moltbook leaked 1.5M API tokens from fully vibe-coded code
- 35 new CVEs from AI-generated code in March 2026 alone
- The UK NCSC called for "vibe coding safeguards" on March 24, 2026

Nightjar is the safeguard.
