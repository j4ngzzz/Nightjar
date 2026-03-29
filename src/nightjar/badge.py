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
from urllib.parse import quote
from xml.sax.saxutils import escape as _xml_escape


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


# ─── shields.io endpoint JSON ────────────────────────────────────────────────

# Hex values for the local SVG generator (no shields.io dependency).
_SVG_COLOR_HEX: dict[str, str] = {
    "brightgreen": "#4c1",
    "green": "#97ca00",
    "yellow": "#dfb317",
    "red": "#e05d44",
    "lightgrey": "#9f9f9f",
}


def _resolve_shields_color(verified: bool, confidence_score: int) -> str:
    """Return the shields.io colour name for a verification result.

    Args:
        verified: Whether the verification passed.
        confidence_score: Integer confidence score 0–100.

    Returns:
        One of: "brightgreen", "green", "yellow", "red".
    """
    if not verified:
        return "red"
    if confidence_score >= 90:
        return "brightgreen"
    if confidence_score >= 70:
        return "green"
    return "yellow"


def generate_shields_json(report_path: str = ".card/verify.json") -> dict:
    """Generate a shields.io endpoint JSON payload from the last verify report.

    Returns a dict compatible with the shields.io endpoint badge spec:
    https://shields.io/endpoint

    Args:
        report_path: Path to the ``verify.json`` verification report.

    Returns:
        Dict with keys ``schemaVersion``, ``label``, ``message``, ``color``.
        If the report is missing or unreadable the dict uses ``"lightgrey"``
        and the message ``"not verified"``.

    References:
        Scout 7 N8 — "Nightjar Verified" badge for GitHub/npm.
    """
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {
            "schemaVersion": 1,
            "label": _BADGE_LABEL,
            "message": "not verified",
            "color": "lightgrey",
        }

    verified: bool = report.get("verified", False)
    score: int = int(report.get("confidence_score", 0))
    color = _resolve_shields_color(verified, score)

    if verified:
        message = f"verified {score}%"
    else:
        message = f"failed {score}%"

    return {
        "schemaVersion": 1,
        "label": _BADGE_LABEL,
        "message": message,
        "color": color,
    }


def write_shields_json(
    report_path: str = ".card/verify.json",
    output_path: str = ".card/shields.json",
) -> Path:
    """Write the shields.io endpoint JSON to disk.

    Args:
        report_path: Path to the ``verify.json`` verification report.
        output_path: Destination path for the generated ``shields.json``.

    Returns:
        The resolved ``Path`` of the written file.

    References:
        Scout 7 N8 — auto-update badge artefact in CI.
    """
    payload = generate_shields_json(report_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


# ─── standalone SVG badge ─────────────────────────────────────────────────────

# Approximate per-character pixel width for the DejaVu Sans / Verdana font used
# by shields.io (11px font-size).  Good enough for badge layout without a real
# font-metrics library.
_CHAR_WIDTH_PX: float = 6.5


def _text_width(text: str) -> int:
    """Estimate rendered pixel width of *text* in the badge font."""
    return int(len(text) * _CHAR_WIDTH_PX)


def generate_badge_svg(report_path: str = ".card/verify.json") -> str:
    """Generate a self-contained SVG badge (no external requests).

    The badge mirrors the two-part shields.io flat style: a dark-grey left
    panel labelled ``"nightjar"`` and a coloured right panel showing the
    verification result message.

    Args:
        report_path: Path to the ``verify.json`` verification report.

    Returns:
        A complete SVG document as a string.  Can be saved directly to
        ``.card/badge.svg`` and served from a CDN or committed to the repo.

    References:
        Scout 7 N8 — Nightjar Verified badge; shields.io badge anatomy.
    """
    payload = generate_shields_json(report_path)
    label: str = _xml_escape(payload["label"])
    message: str = _xml_escape(payload["message"])
    color_name: str = payload["color"]
    right_color = _SVG_COLOR_HEX.get(color_name, _SVG_COLOR_HEX["lightgrey"])

    h = 20  # total badge height (px)
    padding = 10  # horizontal padding per side (px)

    left_text_w = _text_width(label)
    right_text_w = _text_width(message)

    left_w = left_text_w + padding
    right_w = right_text_w + padding
    total_w = left_w + right_w

    left_cx = left_w // 2
    right_cx = left_w + right_w // 2

    # Both the background rectangles and the text groups share the rounded
    # clip-path so text cannot overflow the badge corners.
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{h}">\n'
        f'  <clipPath id="r">\n'
        f'    <rect width="{total_w}" height="{h}" rx="3" fill="#fff"/>\n'
        f'  </clipPath>\n'
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{left_w}" height="{h}" fill="#555"/>\n'
        f'    <rect x="{left_w}" width="{right_w}" height="{h}" fill="{right_color}"/>\n'
        f'    <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">\n'
        f'      <text x="{left_cx}" y="15" fill="#010101" fill-opacity=".3">{label}</text>\n'
        f'      <text x="{left_cx}" y="14">{label}</text>\n'
        f'      <text x="{right_cx}" y="15" fill="#010101" fill-opacity=".3">{message}</text>\n'
        f'      <text x="{right_cx}" y="14">{message}</text>\n'
        f'    </g>\n'
        f'  </g>\n'
        f'</svg>'
    )
    return svg


# ─── README embed helper ──────────────────────────────────────────────────────


def generate_readme_embed(
    repo_owner: str,
    repo_name: str,
    branch: str = "master",
) -> str:
    """Generate the markdown badge embed line for a repository's README.

    The embed points to the raw ``.card/badge.svg`` committed in the repo,
    so the badge updates automatically whenever CI regenerates it.

    Args:
        repo_owner: GitHub username or organisation name.
        repo_name: Repository name.
        branch: Branch where ``.card/badge.svg`` lives (default ``"master"``).

    Returns:
        A markdown image string, e.g.::

            ![Nightjar](https://raw.githubusercontent.com/owner/repo/master/.card/badge.svg)

    References:
        Scout 7 N8 — viral GitHub badge; README embed pattern.
    """
    safe_owner = quote(repo_owner, safe="")
    safe_repo = quote(repo_name, safe="")
    url = (
        f"https://raw.githubusercontent.com/{safe_owner}/{safe_repo}"
        f"/{branch}/.card/badge.svg"
    )
    return f"![Nightjar]({url})"
