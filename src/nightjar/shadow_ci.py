"""Shadow CI mode for Nightjar.

Runs verification in non-blocking mode — NEVER fails the CI check.
Produces a structured report and PR comment-ready markdown.

The key insight (Scout 7 Feature 2):
  '50% of devs don't verify AI code. Shadow mode removes friction entirely.'
  Developers won't disable a tool that never blocks their PR.

The viral moment:
  'PR #442: Nightjar caught SQL injection that passed all tests.'

References:
- Scout 7 Feature 2 — Shadow CI mode design
- Scout 7 Section 10 — Nightjar Security Mode bundle (F1 + F2 + F3)
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ShadowCIResult:
    """Result of a Shadow CI run.

    Attributes:
        exit_code: Always 0 in shadow mode. Non-zero in strict mode on failure.
        report: Structured dict with verification summary.
        pr_comment: Optional markdown string for PR comment.
    """

    exit_code: int
    report: dict
    pr_comment: Optional[str] = None


def _load_report(report_path: str) -> Optional[dict]:
    """Load a verify.json report from disk.

    Args:
        report_path: Path to verify.json.

    Returns:
        Parsed dict or None if missing/unreadable.
    """
    try:
        with open(report_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _summarize_report(raw_report: Optional[dict]) -> dict:
    """Build a compact summary dict from the raw verification report.

    Args:
        raw_report: Raw verify.json dict, or None if not found.

    Returns:
        Summary dict with status, score, and stage list.
    """
    if raw_report is None:
        return {
            "status": "no_report",
            "confidence_score": 0,
            "verified": False,
            "stages": [],
        }

    verified: bool = raw_report.get("verified", False)
    score: int = int(raw_report.get("confidence_score", 0))
    stages_raw: list = raw_report.get("stages", [])

    stages_summary = [
        {
            "stage": s.get("stage", -1),
            "name": s.get("name", "unknown"),
            "status": s.get("status", "unknown"),
            "violations": len(s.get("errors", [])),
        }
        for s in stages_raw
    ]

    # Collect all violations across stages
    violations = []
    for s in stages_raw:
        for err in s.get("errors", []):
            violations.append(
                {
                    "stage": s.get("name", "unknown"),
                    "message": err.get("message", ""),
                    "counterexample": err.get("counterexample"),
                }
            )

    return {
        "status": "verified" if verified else "violations_found",
        "verified": verified,
        "confidence_score": score,
        "stages": stages_summary,
        "violations": violations,
        "violation_count": len(violations),
    }


def format_pr_comment(report: dict) -> str:
    """Format a verification report as a PR comment-ready markdown string.

    Produces the "viral moment" — a readable PR comment that shows what
    Nightjar found even when passing all existing tests.

    Args:
        report: Raw verify.json dict (from verify pipeline).

    Returns:
        Markdown string for a GitHub PR comment.

    References:
        Scout 7 Feature 2 — 'PR #442: Nightjar caught SQL injection that passed all tests.'
    """
    summary = _summarize_report(report)
    verified = summary["verified"]
    score = summary["confidence_score"]
    violation_count = summary["violation_count"]

    icon = "✅" if verified else "⚠️"
    status_text = "All invariants verified" if verified else f"{violation_count} violation(s) found"

    lines = [
        f"## {icon} Nightjar Shadow CI Report",
        "",
        f"**Status:** {status_text}",
        f"**Confidence Score:** {score}/100",
        "",
    ]

    if not verified and summary["violations"]:
        lines.append("### Violations Detected")
        lines.append("")
        lines.append(
            "> These violations were caught by Nightjar formal verification. "
            "Your existing tests did not catch them."
        )
        lines.append("")
        for v in summary["violations"][:5]:  # cap at 5 for readability
            stage = v["stage"]
            msg = v["message"]
            lines.append(f"- **[{stage}]** {msg}")
            if v.get("counterexample"):
                lines.append(f"  - Counterexample: `{v['counterexample']}`")
        lines.append("")

    # Stage table
    if summary["stages"]:
        lines.append("### Stage Summary")
        lines.append("")
        lines.append("| Stage | Name | Status | Violations |")
        lines.append("|-------|------|--------|-----------|")
        for s in summary["stages"]:
            status_icon = "✅" if s["status"] == "pass" else "❌" if s["status"] == "fail" else "⏭️"
            lines.append(
                f"| {s['stage']} | {s['name']} | {status_icon} {s['status']} | {s['violations']} |"
            )
        lines.append("")

    lines.append(
        "_This is a non-blocking Shadow CI report. "
        "Run `nightjar verify` locally for full details._"
    )

    return "\n".join(lines)


def run_shadow_ci(
    report_path: str,
    mode: str = "shadow",
) -> ShadowCIResult:
    """Run Nightjar in Shadow CI mode.

    In shadow mode, ALWAYS exits 0 regardless of verification outcome.
    In strict mode, exits non-zero on verification failure.

    Args:
        report_path: Path to verify.json from a nightjar verify run.
        mode: 'shadow' (default) — never block. 'strict' — fail on violations.

    Returns:
        ShadowCIResult with exit_code, structured report, and PR comment.

    References:
        Scout 7 Feature 2 — Shadow CI mode.
    """
    raw_report = _load_report(report_path)
    summary = _summarize_report(raw_report)

    # Generate PR comment from raw report (or empty dict if missing)
    pr_comment = format_pr_comment(raw_report or {})

    # Determine exit code
    if mode == "shadow":
        # NEVER block in shadow mode — this is the whole point
        exit_code = 0
    else:
        # strict mode: fail if verification failed
        exit_code = 0 if summary["verified"] else 1

    return ShadowCIResult(
        exit_code=exit_code,
        report=summary,
        pr_comment=pr_comment,
    )
