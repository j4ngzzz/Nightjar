"""Multi-module dependency resolution with topological sort.

Scans .card.md specs, builds a dependency graph from ``module.depends-on``
fields, and produces a build order via Kahn's algorithm (topological sort).
Detects circular dependencies.

References:
- ARCHITECTURE.md Section 2 (module boundary with depends-on)
- [REF-T25] Spec Kit conventions for module dependencies

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 2.
"""

from __future__ import annotations

from pathlib import Path

from .parser import parse_card_spec
from .types import CardSpec


class CyclicDependencyError(Exception):
    """Raised when modules have circular dependencies."""


def build_dependency_graph(specs: list[CardSpec]) -> dict[str, set[str]]:
    """Build a dependency graph from a list of parsed CardSpec objects.

    Args:
        specs: List of parsed .card.md specifications.

    Returns:
        Dict mapping module ID to set of module IDs it depends on.
        Includes external dependencies (modules not in the spec set).
    """
    graph: dict[str, set[str]] = {}
    for spec in specs:
        graph[spec.id] = set(spec.module.depends_on.keys())
    return graph


def resolve_build_order(specs: list[CardSpec]) -> list[str]:
    """Determine build order for modules via topological sort.

    Uses Kahn's algorithm: repeatedly remove nodes with no unresolved
    in-module dependencies. External dependencies (not in the spec set)
    are assumed satisfied and excluded from the build order.

    Args:
        specs: List of parsed .card.md specifications.

    Returns:
        List of module IDs in dependency order (build first → last).

    Raises:
        CyclicDependencyError: If circular dependencies exist.
    """
    if not specs:
        return []

    graph = build_dependency_graph(specs)
    module_ids = {spec.id for spec in specs}

    # Filter graph to only in-set dependencies for sorting
    # (external deps like "postgres" are assumed satisfied)
    in_set_deps: dict[str, set[str]] = {}
    for mod_id in module_ids:
        in_set_deps[mod_id] = graph.get(mod_id, set()) & module_ids

    # Kahn's algorithm for topological sort
    in_degree: dict[str, int] = {mod_id: 0 for mod_id in module_ids}
    for mod_id, deps in in_set_deps.items():
        for dep in deps:
            # dep depends on nothing extra here; mod_id depends on dep
            pass
    # Compute in-degrees: for each module, count how many other modules
    # depend on it (i.e., it appears as a dependency)
    # Actually, in-degree for topological sort: count incoming edges
    # Edge: dep -> mod_id means "dep must be built before mod_id"
    # So in_degree[mod_id] = number of deps mod_id has (within the set)
    in_degree = {mod_id: len(deps) for mod_id, deps in in_set_deps.items()}

    # Start with modules that have no in-set dependencies
    queue = [mod_id for mod_id, deg in in_degree.items() if deg == 0]
    queue.sort()  # deterministic ordering for equal-priority modules

    result: list[str] = []
    while queue:
        current = queue.pop(0)
        result.append(current)
        # Remove current from all dependents' dependency sets
        for mod_id in module_ids:
            if current in in_set_deps[mod_id]:
                in_set_deps[mod_id].discard(current)
                in_degree[mod_id] -= 1
                if in_degree[mod_id] == 0:
                    queue.append(mod_id)
                    queue.sort()  # maintain deterministic order

    if len(result) != len(module_ids):
        # Modules remaining have unresolved deps → cycle
        remaining = module_ids - set(result)
        raise CyclicDependencyError(
            f"Circular dependency detected among modules: "
            f"{', '.join(sorted(remaining))}"
        )

    return result


def scan_and_resolve(card_dir: str) -> list[tuple[str, CardSpec]]:
    """Scan a directory for .card.md files and resolve build order.

    Args:
        card_dir: Path to .card/ directory containing .card.md files.

    Returns:
        List of (path, CardSpec) tuples in dependency-resolved build order.

    Raises:
        CyclicDependencyError: If circular dependencies exist.
    """
    card_path = Path(card_dir)
    if not card_path.exists():
        return []

    specs_by_id: dict[str, tuple[str, CardSpec]] = {}
    for card_file in card_path.glob("*.card.md"):
        if card_file.name == "constitution.card.md":
            continue  # Constitution is not a buildable module
        spec = parse_card_spec(str(card_file))
        specs_by_id[spec.id] = (str(card_file), spec)

    all_specs = [entry[1] for entry in specs_by_id.values()]
    order = resolve_build_order(all_specs)

    return [(specs_by_id[mod_id][0], specs_by_id[mod_id][1]) for mod_id in order]
