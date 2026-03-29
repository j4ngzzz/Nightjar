# Nightjar CI Examples

Copy-paste GitHub Actions workflows for five common Python project types.
Every file is complete — no placeholders, no `<YOUR_VALUE>` tokens.

---

## Files

| File | Project type | Key CI features |
|------|-------------|-----------------|
| `flask-app.yml` | Flask web app | Postgres service, pytest-flask, PR violation comment |
| `fastapi-app.yml` | FastAPI app | ruff + mypy lint, pytest-asyncio, async Postgres, PR comment |
| `django-app.yml` | Django app | manage.py check, migration guard, pytest-django, Postgres |
| `cli-tool.yml` | Click/Typer CLI tool | Cross-platform matrix (ubuntu/macos/windows), wheel build artifact |
| `library.yml` | Python library | Multi-version matrix (3.11/3.12/3.13), PyPI publish on release |

Each workflow contains two Nightjar jobs:

- **`verify-fast`** — triggers on pull_request. Runs Hypothesis only (~5 seconds). Blocks merge on violation.
- **`verify-full`** — triggers on push to main. Runs Hypothesis + Dafny formal proof (~30 seconds). Uploads SARIF.

---

## Action versions (verified current)

| Action | Version | Confirmed in |
|--------|---------|-------------|
| `actions/checkout` | `@v4` | `.github/workflows/verify.yml` |
| `actions/setup-python` | `@v5` | `.github/workflows/verify.yml` |
| `j4ngzzz/Nightjar` | `@v1` | `.github/workflows/nightjar-example.yml` |
| `actions/github-script` | `@v7` | `docs/tutorials/ci-one-commit.md` |
| `actions/upload-artifact` | `@v4` | current stable |
| `pypa/gh-action-pypi-publish` | `@release/v1` | current stable |

---

## Required permissions

Every workflow declares the minimum permissions needed:

```yaml
permissions:
  contents: read
  security-events: write   # SARIF upload to GitHub Code Scanning
  pull-requests: write     # PR violation comment (github-script)
```

The `publish` job in `library.yml` additionally declares `id-token: write`
at the job level for OIDC trusted publishing.

---

## SARIF and Code Scanning

When `upload-sarif: "true"` is set on the Nightjar action, violations appear
as inline annotations on the PR "Files changed" tab — identical to CodeQL
or Semgrep annotations. Counterexamples are shown directly on the offending line.

**Public repositories**: SARIF upload is free with no additional setup.

**Private repositories**: GitHub Advanced Security is required (included in
GitHub Team and Enterprise plans, and available as a paid add-on).

To disable SARIF upload (e.g. for a private repo on the Free plan), set
`upload-sarif: "false"`. Nightjar still runs and fails the job on violations;
you lose the inline PR annotations but keep the build gate.

---

## Nightjar action inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `fast` | string | `"false"` | `"true"` skips Dafny, runs Hypothesis only (~5s) |
| `upload-sarif` | string | `"false"` | Upload SARIF file to GitHub Code Scanning |
| `fail-on-violation` | string | `"true"` | Exit non-zero if any contract is violated |
| `dafny-version` | string | `"4.9.0"` | Dafny version to install for Stage 4 |

## Nightjar action outputs

| Output | Values | Description |
|--------|--------|-------------|
| `result` | `"pass"` / `"fail"` | Overall verification result |
| `violation-count` | `"0"` or a number | Number of violated invariants |
| `sarif-file` | file path | Path to the uploaded SARIF file |

---

## Adapting the workflows

**Change the Python version**: update the `python-version` field in the
`actions/setup-python` step. Nightjar itself requires Python 3.11+.

**Change the Dafny version**: update `dafny-version` on the `verify-full` job.
Current stable is `4.9.0`. See https://github.com/dafny-lang/dafny/releases.

**Use a specific model for generation**: set `NIGHTJAR_MODEL` in the job `env`
block. Example:

```yaml
env:
  NIGHTJAR_MODEL: claude-sonnet-4-6
```

**Skip verification on docs-only PRs**: add a path filter to the trigger:

```yaml
on:
  pull_request:
    paths:
      - "src/**"
      - "**.py"
      - ".card/**"
      - "*.toml"
    paths-ignore:
      - "docs/**"
      - "**.md"
```

---

## Pre-commit hook

To catch violations before they reach CI, add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/j4ngzzz/Nightjar
    rev: v1
    hooks:
      - id: nightjar-verify
        args: ["--fast"]
```

The hook runs `--fast` (Hypothesis only, ~5 seconds) on every `git commit`.
Full Dafny proof still runs in CI. Local hook catches obvious failures early.

---

See also:

- [Add Nightjar to CI in one commit](../../tutorials/ci-one-commit.md)
- [Verify your FastAPI endpoint contracts](../../tutorials/verify-fastapi.md)
- [Nightjar action reference](https://github.com/j4ngzzz/Nightjar)
