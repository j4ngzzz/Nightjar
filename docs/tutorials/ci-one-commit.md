# Add Nightjar to your CI in one commit

One YAML file. PR annotations on every violation. No configuration beyond this.

---

## Step 1 — Copy the workflow

Create `.github/workflows/nightjar.yml`:

```yaml
name: Nightjar Verification

on:
  push:
    branches: [main, master]
    paths: ["src/**", "**.py", ".card/**", "*.toml"]
  pull_request:
    paths: ["src/**", "**.py", ".card/**", "*.toml"]

permissions:
  contents: read
  security-events: write   # required for SARIF upload

jobs:
  # Fast check on every PR (Hypothesis only, no Dafny — ~5 seconds)
  verify-fast:
    name: Nightjar (fast)
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - name: Run Nightjar
        uses: j4ngzzz/Nightjar@v1
        with:
          fast: "true"
          upload-sarif: "true"
          fail-on-violation: "true"

  # Full proof on every push to main (includes Dafny — ~30 seconds)
  verify-full:
    name: Nightjar (full)
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - name: Run Nightjar
        uses: j4ngzzz/Nightjar@v1
        with:
          fast: "false"
          upload-sarif: "true"
          fail-on-violation: "true"
          dafny-version: "4.9.0"
```

That's the entire CI integration. Commit and push.

---

## Step 2 — What you see on a PR

When Nightjar finds a violation, GitHub Code Scanning adds inline annotations
to the "Files changed" tab — identical to CodeQL or Semgrep annotations.

```
payment.py · line 14                                           [Nightjar]
INV-001 · amount is always positive (> 0, not >= 0)
Counterexample: process_charge(amount=0.0, currency="USD") → success
This property violation was found by Nightjar / Stage 3 (Hypothesis).
```

The PR is blocked from merging until the violation is resolved (if `fail-on-violation: "true"`).
Violations also accumulate in Security > Code Scanning Alerts on your repository page.

**Note**: SARIF annotations are free for public repositories. Private repositories require
GitHub Advanced Security (included in GitHub Team and Enterprise plans).

---

## Step 3 — Pre-commit hook (optional)

Catch violations before they reach CI. Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/j4ngzzz/Nightjar
    rev: v1
    hooks:
      - id: nightjar-verify
        args: ["--fast"]
```

Install:

```bash
pip install pre-commit
pre-commit install
```

On every `git commit`, Nightjar runs `--fast` (Hypothesis only) against any changed
`.card.md` files. Full Dafny proof still runs in CI. Local hook catches the obvious
failures in ~5 seconds before the push.

---

## What the action outputs

```yaml
steps.nightjar.outputs.result          # "pass" or "fail"
steps.nightjar.outputs.violation-count # "0" or number of violations
steps.nightjar.outputs.sarif-file      # path to the uploaded SARIF file
```

Use these in downstream steps:

```yaml
- name: Comment on PR
  if: steps.nightjar.outputs.result == 'fail'
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `Nightjar found ${{ steps.nightjar.outputs.violation-count }} violation(s). See Security > Code Scanning for details.`
      })
```

---

## Done

Your next PR will have Nightjar annotations. Every violation will be pinned to the exact
line where the invariant fails, with the counterexample that triggered it.

"LLMs write the code. We write the proof."

[Verify your FastAPI endpoint contracts →](verify-fastapi.md)
