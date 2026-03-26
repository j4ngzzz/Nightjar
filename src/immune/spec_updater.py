"""Auto-append verified invariants to .card.md spec files.

Takes a verified invariant (confirmed by CrossHair/Hypothesis) and appends
it to the appropriate .card.md file's invariants: block with auto-generated
ID, tier: property, and origin metadata (failure_id, timestamp,
verification_method).

This closes the immune system loop: production failure → mine invariant →
enrich → verify → append to spec → next build incorporates the new invariant.

References:
- [REF-C09] Immune System / Acquired Immunity — append-only invariant history
- [REF-C01] Tiered invariants — auto-generated go to 'property' tier
- [REF-T24] Agent Skills Open Standard — YAML frontmatter format
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SpecUpdateResult:
    """Result of appending an invariant to a .card.md file.

    Attributes:
        success: Whether the append succeeded.
        invariant_id: The auto-generated ID of the new invariant.
        error: Error message if the append failed.
    """
    success: bool
    invariant_id: str = ""
    error: Optional[str] = None


def build_invariant_entry(
    expression: str,
    explanation: str,
    origin_failure_id: Optional[str] = None,
    verification_method: Optional[str] = None,
) -> dict:
    """Build a YAML-compatible invariant entry dict.

    Auto-generates a unique ID with INV-AUTO- prefix to distinguish
    immune-system-generated invariants from human-written ones. [REF-C01]

    Args:
        expression: The invariant expression (e.g., 'result >= 0').
        explanation: Human-readable explanation of the invariant.
        origin_failure_id: ID of the production failure that triggered this.
        verification_method: How the invariant was verified (e.g., 'crosshair+hypothesis').

    Returns:
        Dict suitable for YAML serialization into the invariants: block.
    """
    inv_id = f"INV-AUTO-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    entry: dict = {
        "id": inv_id,
        "tier": "property",  # [REF-C01] Auto-mined invariants go to property tier
        "statement": expression,
        "rationale": explanation,
    }

    # Origin metadata for audit trail [REF-C09]
    origin: dict = {"timestamp": timestamp}
    if origin_failure_id:
        origin["failure_id"] = origin_failure_id
    if verification_method:
        origin["verification_method"] = verification_method
    entry["origin"] = origin

    return entry


def _split_card_md(content: str) -> tuple[str, str, str]:
    """Split a .card.md file into (before-frontmatter, frontmatter, body).

    Returns the opening '---', the YAML frontmatter content, and the
    markdown body (everything after the closing '---').
    """
    parts = content.split("---", 2)
    if len(parts) < 3:
        # No proper frontmatter delimiters
        return "", content, ""

    # parts[0] is text before first ---, parts[1] is YAML, parts[2] is body
    return parts[0], parts[1], parts[2]


def append_invariant(
    card_path: str,
    expression: str,
    explanation: str,
    origin_failure_id: Optional[str] = None,
    verification_method: Optional[str] = None,
) -> SpecUpdateResult:
    """Append a verified invariant to a .card.md file.

    Reads the file, parses the YAML frontmatter, appends the new invariant
    to the invariants: list, and writes the file back — preserving the
    markdown body unchanged. [REF-C09]

    Args:
        card_path: Path to the .card.md file.
        expression: Invariant expression (e.g., 'result >= 0').
        explanation: Human-readable explanation.
        origin_failure_id: ID of the triggering failure.
        verification_method: How the invariant was verified.

    Returns:
        SpecUpdateResult with success status and the new invariant's ID.
    """
    path = Path(card_path)
    if not path.exists():
        return SpecUpdateResult(
            success=False,
            error=f"File not found: {card_path}",
        )

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return SpecUpdateResult(
            success=False,
            error=f"Failed to read file: {e}",
        )

    # Build the new invariant entry
    entry = build_invariant_entry(
        expression=expression,
        explanation=explanation,
        origin_failure_id=origin_failure_id,
        verification_method=verification_method,
    )

    # Parse the frontmatter
    prefix, frontmatter_str, body = _split_card_md(content)

    try:
        data = yaml.safe_load(frontmatter_str)
        if data is None:
            data = {}
    except yaml.YAMLError as e:
        return SpecUpdateResult(
            success=False,
            error=f"Failed to parse YAML frontmatter: {e}",
        )

    # Append to invariants list (create if not present)
    if "invariants" not in data or data["invariants"] is None:
        data["invariants"] = []
    data["invariants"].append(entry)

    # Serialize back to YAML, preserving key order
    try:
        new_frontmatter = yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    except yaml.YAMLError as e:
        return SpecUpdateResult(
            success=False,
            error=f"Failed to serialize YAML: {e}",
        )

    # Reconstruct the file
    new_content = f"{prefix}---\n{new_frontmatter}---{body}"

    try:
        path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return SpecUpdateResult(
            success=False,
            error=f"Failed to write file: {e}",
        )

    return SpecUpdateResult(
        success=True,
        invariant_id=entry["id"],
    )
