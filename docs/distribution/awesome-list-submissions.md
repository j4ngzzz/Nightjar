# Awesome List Submissions

Submission drafts for the three primary awesome lists. Each section includes the list's actual requirements (verified from CONTRIBUTING.md), an honest eligibility assessment, and the exact PR text to use.

---

## 1. awesome-python (vinta/awesome-python)

**Repo:** https://github.com/vinta/awesome-python
**Requirement source:** CONTRIBUTING.md (verified March 28, 2026)

### Eligibility Assessment

| Requirement | Status | Notes |
|-------------|--------|-------|
| Python-first (>50% codebase) | PASS | Nightjar is pure Python |
| Active (commits within 12 months) | PASS | Active development |
| Stable (production-ready, not alpha) | **FAIL** | Currently alpha/v0.x |
| Documented (clear README with examples) | PASS | README with terminal demos |
| Unique (distinct value) | PASS | No other formal verification pipeline in the list |
| Established (repo at least 1 month old) | **FAIL** | Launched March 2026 |
| Stars: Hidden Gem path requires 100+ stars with justification | **PENDING** | Zero stars at launch |

**Honest assessment:** Do not submit to awesome-python now. The CONTRIBUTING.md explicitly requires "production-ready, not alpha/beta/experimental" and "at least 3 months old" for the Hidden Gem path. Submitting now will be closed. Target: submit at 3 months old (late June 2026) if the tool has 100+ stars and has reached a stable release (v1.0 or removal of alpha tag).

### Correct Category

The correct section in awesome-python is **Testing > Code Analysis**. The current entries there include: flake8, pylint, prospector, vulture, wemake-python-styleguide. Nightjar belongs in this section.

### Entry Format (when ready)

```markdown
- [nightjar](https://github.com/j4ngzzz/Nightjar) - 5-stage formal verification pipeline for AI-generated Python code: syntax checking, dependency CVE scanning, schema validation, property-based testing (Hypothesis), and formal proof (CrossHair + Dafny).
```

### PR Description (when ready)

```
## Summary

Adding nightjar to the Code Analysis subcategory under Testing.

Nightjar is a formal verification pipeline for Python code. It runs 5 stages: syntax/preflight, dependency CVE scanning (pip-audit), schema validation (Pydantic), property-based testing (Hypothesis), and formal verification (CrossHair + Dafny). It found 48 confirmed bugs across 20 popular Python packages in a public scan campaign (nightjarcode.dev/scan/2026-q1/).

## Why it's a Hidden Gem

- Solves a niche problem (formal verification for AI-generated Python code) that no other tool in the list addresses
- Has a documented track record: 48 confirmed bugs across 20 scanned codebases, 0 false positives in verified set
- Active development with consistent commits
- Real-world impact: fastmcp JWT bypass (CVSS 9.1), python-jose algorithm bypass, passlib bcrypt breakage all found via Nightjar's pipeline

## Category placement

Testing > Code Analysis — sits alongside flake8, pylint, vulture. Nightjar's differentiation is formal proof rather than pattern matching or linting.
```

---

## 2. awesome-static-analysis (analysis-tools-dev/static-analysis)

**Repo:** https://github.com/analysis-tools-dev/static-analysis
**Requirement source:** CONTRIBUTING.md (verified March 28, 2026)

### Eligibility Assessment

| Requirement | Status | Notes |
|-------------|--------|-------|
| Actively maintained (>1 contributor) | PASS | Open source, active |
| Actively used (>20 stars on GitHub) | **PENDING** | Zero stars at launch |
| Relatively mature (exists >3 months) | **PENDING** | Launched March 2026 |

**Honest assessment:** The bar here is much lower than awesome-python (20 stars, 3 months old). Submit when Nightjar has cleared 20 stars and is 3 months old — approximately late June 2026 if the HN launch goes well. This is the most realistic near-term submission.

**Format note:** This list uses YAML files in `data/tools/`, NOT direct README edits. Create a file at `data/tools/nightjar.yml`.

### YAML File to Submit

**File:** `data/tools/nightjar.yml`

```yaml
name: nightjar
categories:
  - python
tags:
  - formal-verification
  - property-based-testing
  - security
  - hypothesis
  - dafny
  - ai-generated-code
homepage: https://nightjarcode.dev
source: https://github.com/j4ngzzz/Nightjar
description: >
  5-stage formal verification pipeline for Python code: preflight, dependency
  CVE scanning (pip-audit), schema validation (Pydantic), property-based testing
  (Hypothesis), and formal proof (CrossHair + Dafny). Designed for AI-generated
  code verification with CEGIS retry loop and spec-driven .card.md contracts.
  Found 48 confirmed bugs across 20 popular Python packages.
license: AGPL-3.0
```

### PR Title and Description

**Title:** `Add nightjar — formal verification pipeline for Python (PBT + Dafny)`

**Body:**
```
Adding nightjar to the Python section.

Nightjar is a 5-stage static/formal analysis pipeline specifically designed for AI-generated Python code. It is differentiated from other Python SAST tools in the list (bandit, semgrep, prospector) by including formal proof via CrossHair (SMT-based symbolic execution) and Dafny verification in addition to traditional linting and property-based testing.

Track record: 48 confirmed bugs found across 20 popular Python packages including authentication bypasses in fastmcp and python-jose.

YAML file added at data/tools/nightjar.yml per CONTRIBUTING.md instructions.
```

---

## 3. awesome-python-security (guardrailsio/awesome-python-security)

**Repo:** https://github.com/guardrailsio/awesome-python-security
**Requirement source:** README-implied (no formal CONTRIBUTING.md — standard awesome-list conventions apply)

### Eligibility Assessment

| Requirement | Status | Notes |
|-------------|--------|-------|
| Python security focus | PASS | CVE scanning + security invariant verification |
| Active project | PASS | Active development |
| Documented | PASS | README with examples |
| No explicit star/age minimum in guidelines | PASS | More permissive list |

**Honest assessment:** This is the best near-term submission target. The list has no explicit star floor and is focused on the Python security tool ecosystem. Nightjar's bug-finding track record (fastmcp JWT bypass, python-jose algorithm bypass) is directly relevant. Submit within 2 weeks of launch.

### Correct Section

The `Tools` section of awesome-python-security. Current entries include: bandit, safety, semgrep, pip-audit. Nightjar belongs here.

### Entry Format

```markdown
- [nightjar](https://github.com/j4ngzzz/Nightjar) - Formal verification pipeline for Python: CVE dependency scanning, property-based testing (Hypothesis), and formal proof (CrossHair + Dafny). Found authentication bypasses in fastmcp and python-jose via invariant verification. AGPL-3.0 / commercial.
```

### PR Title and Description

**Title:** `Add nightjar — formal verification + CVE pipeline for Python security`

**Body:**
```
Adding nightjar to the Tools section.

Nightjar is a formal verification pipeline with a direct security application: it checks Python code against invariant specifications and finds security-relevant edge cases that traditional SAST misses.

Recent findings from a public scan campaign:
- fastmcp 2.14.5: JWT expiry bypass via Python truthiness (`if exp` passes on `exp=None` and `exp=0`); OAuth redirect URI bypass via fnmatch wildcard
- python-jose 3.5.0: `jwt.decode(algorithms=None)` skips algorithm validation entirely
- passlib 1.7.4: authentication completely broken against bcrypt 4.x/5.x

These were found by the pipeline's property-based testing and spec-verification stages, not by pattern-matching SAST rules.

Repo: https://github.com/j4ngzzz/Nightjar
PyPI: nightjar-verify
```

---

## Submission Checklist

| List | Submit now? | Target date | Blocker |
|------|-------------|-------------|---------|
| awesome-python-security | Yes | Immediately after launch | None — most permissive list |
| awesome-static-analysis | No | Late June 2026 | Need 20 stars + 3 months old |
| awesome-python | No | Late June 2026 | Need 100+ stars + stable release + 3 months old |

**One PR per list — never batch multiple tool submissions into one PR, as all three lists' CONTRIBUTING.md guidelines explicitly reject this.**
