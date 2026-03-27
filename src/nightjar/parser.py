"""
.card.md parser — reads YAML frontmatter + Markdown body.

Format based on:
- [REF-T24] Agent Skills Open Standard (YAML frontmatter + Markdown body)
- [REF-T25] GitHub Spec Kit (Given/When/Then acceptance criteria)
- [REF-C01] Tiered invariants (CARD's invention)

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 2.
"""

import hashlib
import re
from dataclasses import dataclass, field
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


@dataclass
class SpecDiff:
    """Difference between two invariant hash maps (SpecLang incremental pattern).

    Per GitHub Next SpecLang: track spec changes incrementally — most edits
    touch 1-2 invariants. Only those need re-verification.

    Defined here (not types.py) as a parser-layer concern: it describes how
    a spec changed between two parses, not a verification artifact.
    """
    added: list[str] = field(default_factory=list)     # invariant IDs new in new_hashes
    removed: list[str] = field(default_factory=list)   # invariant IDs absent from new_hashes
    changed: list[str] = field(default_factory=list)   # IDs in both but hash differs
    unchanged: list[str] = field(default_factory=list) # IDs in both with same hash


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


# ─── SpecLang Incremental Recompilation (W2-5) ───────────────────────────────
# Per GitHub Next SpecLang: watch for spec changes and recompile only the
# affected sections. hash_invariants + diff_specs implement the change-tracking
# layer that verifier.run_pipeline_incremental() consumes.


def hash_invariants(spec: CardSpec) -> dict[str, str]:
    """Return {invariant_id: sha256_hash} for each invariant in the spec.

    Hash covers: invariant statement + tier + rationale. Changing any of these
    means the invariant's verification may produce a different result and must
    be re-run. Only the invariant ID is used as the key, not the index.

    Per SpecLang: identify which spec sections changed without re-running all
    verification. hash_invariants() is called before and after a spec edit;
    diff_specs() compares the two maps to find what actually changed.

    Uses stdlib hashlib only — no external dependencies.

    Args:
        spec: Parsed .card.md specification.

    Returns:
        Dict mapping each invariant's ID to its SHA-256 hex digest.
    """
    result: dict[str, str] = {}
    for inv in spec.invariants:
        content = f"{inv.statement}|{inv.tier.value}|{inv.rationale}"
        result[inv.id] = hashlib.sha256(content.encode()).hexdigest()
    return result


def diff_specs(
    old_hashes: dict[str, str],
    new_hashes: dict[str, str],
) -> SpecDiff:
    """Compare two invariant hash maps and return which invariants changed.

    Per GitHub Next SpecLang: most spec edits touch 1-2 invariants. This diff
    identifies exactly which invariant IDs need re-verification so the pipeline
    can skip unchanged ones.

    Args:
        old_hashes: Previous {invariant_id: sha256_hash} map (e.g., from cache).
        new_hashes: Current {invariant_id: sha256_hash} from hash_invariants().

    Returns:
        SpecDiff listing added/removed/changed/unchanged invariant IDs.
        All lists are sorted for stable, deterministic output.
    """
    old_ids = set(old_hashes.keys())
    new_ids = set(new_hashes.keys())

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    common = old_ids & new_ids
    changed = sorted(id_ for id_ in common if old_hashes[id_] != new_hashes[id_])
    unchanged = sorted(id_ for id_ in common if old_hashes[id_] == new_hashes[id_])

    return SpecDiff(added=added, removed=removed, changed=changed, unchanged=unchanged)
