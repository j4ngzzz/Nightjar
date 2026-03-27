---
card-version: "1.0"
id: shadow_ci
title: Shadow CI Mode and GitHub Action Runner
status: draft
invariants:
  - id: INV-01
    tier: formal
    statement: "run_shadow_ci with mode='shadow' always returns ShadowCIResult.exit_code == 0 regardless of verification outcome"
    rationale: "Shadow mode never blocks CI — this is the core product contract; developers won't disable a tool that never blocks their PR"
  - id: INV-02
    tier: property
    statement: "run_shadow_ci with mode='strict' returns exit_code == 0 if and only if the report's verified field is True"
    rationale: "Strict mode is opt-in gate behavior; exit code must match verification outcome precisely"
  - id: INV-03
    tier: property
    statement: "run_shadow_ci returns exit_code == 0 and a valid ShadowCIResult when report_path points to a missing or unreadable file"
    rationale: "_load_report returns None on any IO/parse error; the pipeline must degrade gracefully — missing report is not a blocker"
  - id: INV-04
    tier: property
    statement: "format_pr_comment output contains the violation count and at most 5 individual violation entries"
    rationale: "PR comments cap violations at 5 for readability; the count is always accurate regardless of the display cap"
  - id: INV-05
    tier: example
    statement: "_post_github_output writes 'key=value\\n' to the GITHUB_OUTPUT file path when the env var is set"
    rationale: "GitHub Actions output protocol requires this exact format; the runner must produce action outputs for downstream steps"
  - id: INV-06
    tier: property
    statement: "_post_pr_comment never raises an exception — all failures are caught and printed as warnings"
    rationale: "PR comment failure must never block CI; the comment is informational, not gating"
  - id: INV-07
    tier: example
    statement: "shadow_ci_runner.main reads all inputs from environment variables (NIGHTJAR_CI_MODE, NIGHTJAR_CI_REPORT, NIGHTJAR_CI_VERIFY_JSON) — never from raw shell argument interpolation"
    rationale: "Script injection prevention (OWASP A03:2021 Injection); env vars are sanitized, direct ${{ inputs.* }} interpolation is not"
---

## Intent

Two-module implementation of non-blocking CI verification for GitHub Actions.

`shadow_ci.py` contains the core logic:
- Loads and summarizes verify.json reports
- Formats PR comment markdown with violation details
- Enforces the shadow/strict mode contract (shadow always exits 0)

`shadow_ci_runner.py` is the GitHub Action entry point:
- Reads all inputs from environment variables to prevent script injection
- Posts GitHub Action outputs (verified, confidence-score, violation-count, badge-url)
- Posts PR comments via GitHub API using stdlib urllib only

The "viral moment" design: when Nightjar catches a bug that all existing tests missed,
the PR comment makes it visible and attributable — creating organic adoption.

References:
- Scout 7 Feature 2 — Shadow CI mode design
- Scout 7 Section 10 — Nightjar Security Mode bundle
- OWASP Top 10 A03:2021 — Injection (script injection prevention)
- GitHub Actions security hardening

## Acceptance Criteria

- [ ] `run_shadow_ci(mode='shadow')` always returns `exit_code == 0`
- [ ] `run_shadow_ci(mode='strict')` returns `exit_code == 1` when `verified == False`
- [ ] Missing/unreadable report_path degrades gracefully (exit_code 0, status "no_report")
- [ ] `format_pr_comment` caps displayed violations at 5; always shows accurate total count
- [ ] `shadow_ci_runner.main` reads mode/report/verify-json from env vars with argparse fallback
- [ ] `_post_pr_comment` never raises; failures are printed as warnings
- [ ] GitHub Action outputs include: verified, confidence-score, violation-count, badge-url

## Functional Requirements

**shadow_ci.py:**
1. **ShadowCIResult** — dataclass with (exit_code: int, report: dict, pr_comment: Optional[str])
2. **_load_report(report_path) -> Optional[dict]** — opens and JSON-parses the path; returns None on FileNotFoundError, JSONDecodeError, or OSError
3. **_summarize_report(raw_report) -> dict** — normalizes raw verify.json into summary with keys: status, verified, confidence_score, stages (list with stage/name/status/violations per entry), violations (list with stage/message/counterexample per entry), violation_count; returns "no_report" summary when raw_report is None
4. **format_pr_comment(report) -> str** — produces GitHub-flavored markdown PR comment; includes status icon, confidence score, violation table (capped at 5), stage summary table, and footer with "nightjar verify" call-to-action
5. **run_shadow_ci(report_path, mode='shadow') -> ShadowCIResult** — loads report, summarizes, formats PR comment, sets exit_code=0 in shadow mode or (0 if verified else 1) in strict mode

**shadow_ci_runner.py:**
6. **_post_github_output(key, value)** — appends "key=value\n" to the file at GITHUB_OUTPUT env var path; silently ignores OSError
7. **_post_pr_comment(comment)** — if GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER are all set, posts comment via GitHub API using urllib.request; if any missing, prints preview to stdout; catches all exceptions and prints warnings
8. **main() -> int** — argparse with defaults from NIGHTJAR_CI_MODE/NIGHTJAR_CI_REPORT/NIGHTJAR_CI_VERIFY_JSON env vars; calls run_shadow_ci; posts outputs (verified, confidence-score, violation-count, badge-url); posts PR comment; returns exit_code
