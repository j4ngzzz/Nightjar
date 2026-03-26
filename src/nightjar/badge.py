"""Nightjar Verified badge module.

Generates shields.io badge URLs from the last verification result.
Produces markdown snippets for README.md and PR comments.

References:
- Scout 7 N8 — "Nightjar Verified" badge for GitHub/npm
- Codecov badge model: https://docs.codecov.com/docs/status-badges
"""
import json
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import quote


class BadgeStatus(str, Enum):
    """Verification outcome status for the badge."""

    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


# shields.io badge colour per status
_STATUS_COLOR: dict[BadgeStatus, str] = {
    BadgeStatus.PASSED: "brightgreen",
    BadgeStatus.FAILED: "red",
    BadgeStatus.UNKNOWN: "lightgrey",
}

_BADGE_LABEL = "nightjar"


def generate_badge_url(status: BadgeStatus, score: int) -> str:
    """Generate a shields.io badge URL for the given verification status and score.

    Args:
        status: The verification outcome (PASSED, FAILED, or UNKNOWN).
        score: Verification confidence score 0-100.

    Returns:
        A shields.io badge URL string (https://…).

    References:
        Scout 7 N8 — badge shows security level + spec coverage + last verified date.
    """
    color = _STATUS_COLOR[status]

    if status == BadgeStatus.UNKNOWN:
        message = "unknown"
    elif status == BadgeStatus.PASSED:
        message = f"verified%20{score}%25"
    else:
        # failed — still show the score
        message = f"failed%20{score}%25"

    label = quote(_BADGE_LABEL, safe="")
    return f"https://img.shields.io/badge/{label}-{message}-{color}"


def generate_badge_url_from_report(report_path: str) -> str:
    """Read a verify.json report and return the appropriate badge URL.

    Args:
        report_path: Path to verify.json.

    Returns:
        shields.io badge URL. Returns an UNKNOWN badge if the report is
        missing or unreadable.
    """
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return generate_badge_url(BadgeStatus.UNKNOWN, 0)

    verified: bool = report.get("verified", False)
    score: int = int(report.get("confidence_score", 0))

    status = BadgeStatus.PASSED if verified else BadgeStatus.FAILED
    return generate_badge_url(status, score)


def generate_badge_markdown(status: BadgeStatus, score: int) -> str:
    """Generate a markdown image snippet for embedding in README.md.

    Args:
        status: The verification outcome.
        score: Verification confidence score 0-100.

    Returns:
        A markdown image link string, e.g. ``![nightjar verified](https://…)``.

    References:
        Scout 7 N8 — viral GitHub badge; Codecov badge model.
    """
    url = generate_badge_url(status, score)
    alt = f"nightjar {status.value} {score}%"
    return f"![{alt}]({url})"
