"""
.card.md parser — reads YAML frontmatter + Markdown body.

Format based on:
- [REF-T24] Agent Skills Open Standard (YAML frontmatter + Markdown body)
- [REF-T25] GitHub Spec Kit (Given/When/Then acceptance criteria)
- [REF-C01] Tiered invariants (CARD's invention)

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 2.
"""

import re
from pathlib import Path

import yaml

from .types import (
    CardSpec,
    Contract,
    ContractInput,
    ContractOutput,
    Invariant,
    InvariantTier,
    ModuleBoundary,
)

# Required top-level frontmatter fields per ARCHITECTURE.md Section 2
_REQUIRED_FIELDS = ("card-version", "id")


def parse_card_spec(path: str) -> CardSpec:
    """Parse a .card.md file into a CardSpec object.

    The .card.md format uses YAML frontmatter (between ``---`` delimiters)
    plus a Markdown body, following [REF-T24] Agent Skills Open Standard.

    Args:
        path: Filesystem path to the .card.md file.

    Returns:
        A fully populated CardSpec dataclass.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If YAML is malformed or required fields are missing.
    """
    content = Path(path).read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(content)
    data = _parse_yaml(frontmatter)
    _validate_required(data)

    return CardSpec(
        card_version=str(data["card-version"]),
        id=data["id"],
        title=data.get("title", ""),
        status=data.get("status", "draft"),
        module=_parse_module(data.get("module", {})),
        contract=_parse_contract(data.get("contract", {})),
        invariants=_parse_invariants(data.get("invariants", [])),
        constraints=data.get("constraints", {}),
        intent=_extract_section(body, "Intent"),
        acceptance_criteria=_extract_section(body, "Acceptance Criteria"),
        functional_requirements=_extract_section(body, "Functional Requirements"),
    )


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Split content into YAML frontmatter and Markdown body.

    Expects the file to start with ``---``, followed by YAML, then another
    ``---``, then the Markdown body.  This follows [REF-T24] convention.
    """
    # Match: starts with ---, then content, then --- on its own line
    match = re.match(r"\A---\n(.*?)---\n?(.*)\Z", content, re.DOTALL)
    if not match:
        raise ValueError(
            "Invalid .card.md: file must contain YAML frontmatter "
            "between --- delimiters"
        )
    return match.group(1), match.group(2)


def _parse_yaml(raw: str) -> dict:
    """Parse YAML string, raising ValueError on malformed input."""
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid .card.md: malformed YAML frontmatter — {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(
            "Invalid .card.md: frontmatter must be a YAML mapping, "
            f"got {type(data).__name__}"
        )
    return data


def _validate_required(data: dict) -> None:
    """Ensure all required top-level fields are present."""
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"Invalid .card.md: required fields missing: {', '.join(missing)}"
        )


def _parse_module(raw: dict | None) -> ModuleBoundary:
    """Map the ``module:`` block to a ModuleBoundary dataclass."""
    if not raw:
        return ModuleBoundary()
    # depends-on uses hyphenated key in YAML; map to dict
    depends_on_raw = raw.get("depends-on", {})
    depends_on = {}
    if isinstance(depends_on_raw, dict):
        depends_on = {str(k): str(v) for k, v in depends_on_raw.items()}
    elif isinstance(depends_on_raw, list):
        depends_on = {str(item): "" for item in depends_on_raw}
    return ModuleBoundary(
        owns=raw.get("owns", []),
        depends_on=depends_on,
        excludes=raw.get("excludes", []),
    )


def _parse_contract(raw: dict | None) -> Contract:
    """Map the ``contract:`` block to a Contract dataclass."""
    if not raw:
        return Contract()
    return Contract(
        inputs=[_parse_input(i) for i in (raw.get("inputs") or [])],
        outputs=[_parse_output(o) for o in (raw.get("outputs") or [])],
        errors=raw.get("errors", []),
        events_emitted=raw.get("events-emitted", []),
    )


def _parse_input(raw: dict) -> ContractInput:
    """Map a single contract input entry."""
    return ContractInput(
        name=raw["name"],
        type=raw["type"],
        constraints=raw.get("constraints", ""),
    )


def _parse_output(raw: dict) -> ContractOutput:
    """Map a single contract output entry."""
    return ContractOutput(
        name=raw["name"],
        type=raw["type"],
        schema=raw.get("schema", {}),
    )


def _parse_invariants(raw: list | None) -> list[Invariant]:
    """Map the ``invariants:`` list to Invariant dataclasses.

    Each invariant has a tier from [REF-C01]: example, property, or formal.
    """
    if not raw:
        return []
    result = []
    for item in raw:
        tier_str = item.get("tier", "example")
        try:
            tier = InvariantTier(tier_str)
        except ValueError:
            tier = InvariantTier.EXAMPLE
        result.append(
            Invariant(
                id=item["id"],
                tier=tier,
                statement=item.get("statement", ""),
                rationale=item.get("rationale", ""),
            )
        )
    return result


def _extract_section(body: str, heading: str) -> str:
    """Extract the content under a Markdown ``## heading`` section.

    Returns the text between ``## heading`` and the next ``##`` heading
    (or end of file), stripped of leading/trailing whitespace.
    """
    # Match ## Heading (possibly with sub-level ### inside)
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()
