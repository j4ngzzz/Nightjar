# Changelog

All notable changes to the `nightjar-verify` OpenClaw skill are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [1.0.0] - 2026-03-29

### Added

- Initial release of Nightjar Verify skill for OpenClaw
- `/nightjar-verify` slash command for on-demand formal verification of Python code
- 5-stage verification pipeline: preflight, deps, schema, PBT (Hypothesis), formal (Dafny)
- `--fast` mode for PBT-only verification — no Dafny required, runs in seconds
- `nightjar scan` integration — bootstrap a `.card.md` spec from existing code
- `nightjar infer` integration — LLM + CrossHair contract generation
- `nightjar audit` integration — PyPI package contract coverage report (letter grades)
- `nightjar explain` — Dafny error translation into Python-developer-friendly language
- `nightjar retry` — CEGIS repair loop for auto-fixing failing code via LLM
- PostToolUse auto-verify hook (`hooks/nightjar-auto-verify`) — opt-in via `NIGHTJAR_AUTO_VERIFY=1`
- Security-mode invariant set: 7 invariants mapped to OpenClaw CVE classes (CVE-2026-25593, CVE-2026-26322, CVE-2026-26319) and the ClawHavoc/Moltbook incidents
- Structured output format for verification results (machine-readable and human-readable)
- VSCode-compatible output format (`--format=vscode`) for inline problem annotations
- Smoke test script (`test/smoke_test.sh`) for verifying skill installation
- CI snippet for GitHub Actions integration
- Support for all 9 Nightjar CLI commands: `verify`, `scan`, `infer`, `init`, `audit`, `explain`, `retry`, `lock`, `build`

### Security Context

This skill was developed in response to the OpenClaw security incident cluster of
early 2026. The 8 CVEs filed against OpenClaw (including 3 RCE vectors), the
ClawHavoc malicious skill campaign, and the Moltbook breach collectively compromised
tens of thousands of agent deployments. All of these had a common root cause: tool
handler code was shipped without formal verification against a specification.

Nightjar addresses this at the source — by requiring mathematical proof before any
agent tool code reaches production.
