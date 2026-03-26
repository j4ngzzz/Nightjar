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


def load_constitution(path: str) -> list[Invariant]:
    """Load global invariants from a constitution.card.md file.

    Constitution files define project-level invariants that inherit to all
    modules, per [REF-T25] GitHub Spec Kit constitution pattern.

    Args:
        path: Filesystem path to the constitution.card.md file.

    Returns:
        List of Invariant objects from the ``global-invariants`` block.
        Returns empty list if file does not exist.
    """
    constitution_path = Path(path)
    if not constitution_path.exists():
        return []

    content = constitution_path.read_text(encoding="utf-8")
    frontmatter, _body = _split_frontmatter(content)
    data = _parse_yaml(frontmatter)

    return _parse_invariants(data.get("global-invariants", []))


def parse_with_constitution(
    spec_path: str,
    constitution_path: str,
) -> CardSpec:
    """Parse a .card.md spec and merge constitution invariants.

    Module-specific invariants come first, followed by global invariants
    from the constitution. Duplicate IDs (if any) are deduplicated —
    module-level takes precedence.

    Per [REF-T25] Spec Kit: constitution.md defines project-level invariants
    inherited by all modules.

    Args:
        spec_path: Path to the module's .card.md file.
        constitution_path: Path to constitution.card.md (may not exist).

    Returns:
        CardSpec with merged invariants.
    """
    spec = parse_card_spec(spec_path)
    global_invariants = load_constitution(constitution_path)

    if not global_invariants:
        return spec

    # Deduplicate: module invariants take precedence over global
    existing_ids = {inv.id for inv in spec.invariants}
    merged = list(spec.invariants)
    for inv in global_invariants:
        if inv.id not in existing_ids:
            merged.append(inv)

    spec.invariants = merged
    return spec


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
