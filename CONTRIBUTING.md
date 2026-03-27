# Contributing to Nightjar

Nightjar is AGPL-3.0. By contributing, you agree your changes are released under AGPL-3.0.

## Quick Start

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/ -v -m "not integration"  # skip tests requiring Dafny/LLM API
```

## Writing a .card.md Spec

Each `.card.md` file describes one module. The format is YAML frontmatter between `---` delimiters followed by a Markdown body.

Required YAML frontmatter fields:

```yaml
---
card-version: "1.0"
id: payment
title: Payment Processing Module
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "amount > 0"
    rationale: "Payments must have a positive amount"
---
```

Required Markdown body sections:

- `## Intent` — one paragraph describing what this module does and why
- `## Acceptance Criteria` — bulleted list of observable outcomes
- `## Functional Requirements` — numbered list of implementation requirements

## Commit Convention

- `feat:` new feature
- `fix:` bug fix
- `ref:` reference implementation (cite [REF-XXX])
- `test:` test only
- `docs:` documentation

When implementing a pattern from a paper or reference, use:

```
ref: implement CEGIS retry loop [REF-NEW-02]
```

This makes the git history traceable back to academic sources.

## Code Style

- Python 3.11+, PEP 8, type hints everywhere
- All LLM calls go through litellm — never call provider APIs directly
- Never hardcode model names — use `NIGHTJAR_MODEL` environment variable
- No classes unless state management requires it (prefer functions)

## Running the Test Suite

```bash
pytest tests/ -v                          # full suite
pytest tests/ -v -m "not integration"    # skip external dependencies
pytest tests/test_parser.py -v           # specific module
```

Integration tests require a Dafny binary on `$PATH` and a valid LLM API key in
`NIGHTJAR_MODEL` / the provider's environment variable (e.g. `ANTHROPIC_API_KEY`).

## Commercial Licensing

Nightjar is AGPL-3.0. If your organization cannot comply with AGPL (for example
when embedding Nightjar in a proprietary product), a commercial license is available.

Pricing: $2,400/yr (teams), $12,000/yr (enterprise). Contact: nightjar-license@proton.me

## Dependency Governance Note

Nightjar uses `uv` and `ruff` as development tools. On March 19, 2026, OpenAI acquired Astral (the company behind both tools). They remain open-source under MIT/Apache-2.0 and continue to function normally.

If future changes to uv/Ruff introduce OpenAI-platform-specific behavior, Nightjar will evaluate alternatives (pip + black/ruff-fork). Contributions that add fallback paths or reduce hard dependency on Astral tooling are welcome.
