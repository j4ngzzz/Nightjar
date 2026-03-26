"""Tests for multi-module dependency resolution.

Validates topological sort of .card.md modules based on depends-on
relationships, with circular dependency detection.

References:
- ARCHITECTURE.md Section 2 (module boundary with depends-on)
- [REF-T25] Spec Kit conventions for module dependencies
"""

import pytest
from pathlib import Path

from nightjar.resolver import (
    build_dependency_graph,
    resolve_build_order,
    CyclicDependencyError,
)
from nightjar.types import CardSpec, ModuleBoundary, Contract


def _make_spec(
    spec_id: str,
    depends_on: dict[str, str] | None = None,
) -> CardSpec:
    """Helper to create a minimal CardSpec for testing."""
    return CardSpec(
        card_version="1.0",
        id=spec_id,
        title=f"Module {spec_id}",
        status="draft",
        module=ModuleBoundary(
            owns=[],
            depends_on=depends_on or {},
            excludes=[],
        ),
        contract=Contract(),
        invariants=[],
    )


class TestBuildDependencyGraph:
    """Test dependency graph construction from specs."""

    def test_empty_specs(self):
        """No specs should produce empty graph."""
        graph = build_dependency_graph([])
        assert graph == {}

    def test_single_spec_no_deps(self):
        """Single spec with no deps should have empty adjacency list."""
        specs = [_make_spec("auth")]
        graph = build_dependency_graph(specs)
        assert "auth" in graph
        assert graph["auth"] == set()

    def test_single_dependency(self):
        """Spec depending on another should show in graph."""
        specs = [
            _make_spec("auth"),
            _make_spec("payment", depends_on={"auth": "approved"}),
        ]
        graph = build_dependency_graph(specs)
        assert "auth" in graph["payment"]

    def test_multiple_dependencies(self):
        """Spec with multiple deps should list all."""
        specs = [
            _make_spec("auth"),
            _make_spec("database"),
            _make_spec("payment", depends_on={"auth": "approved", "database": "^1.0"}),
        ]
        graph = build_dependency_graph(specs)
        assert graph["payment"] == {"auth", "database"}

    def test_unknown_dep_included(self):
        """Dependencies on external modules (not in spec set) are recorded."""
        specs = [
            _make_spec("payment", depends_on={"postgres": "approved"}),
        ]
        graph = build_dependency_graph(specs)
        # postgres is an external dep — it should still appear in the graph
        assert "postgres" in graph["payment"]


class TestResolveBuildOrder:
    """Test topological sort and cycle detection."""

    def test_single_module(self):
        """Single module should return just that module."""
        specs = [_make_spec("auth")]
        order = resolve_build_order(specs)
        assert order == ["auth"]

    def test_linear_chain(self):
        """A -> B -> C should build C first, then B, then A."""
        specs = [
            _make_spec("a", depends_on={"b": ""}),
            _make_spec("b", depends_on={"c": ""}),
            _make_spec("c"),
        ]
        order = resolve_build_order(specs)
        assert order.index("c") < order.index("b")
        assert order.index("b") < order.index("a")

    def test_diamond_dependency(self):
        """Diamond: A depends on B and C, both depend on D."""
        specs = [
            _make_spec("a", depends_on={"b": "", "c": ""}),
            _make_spec("b", depends_on={"d": ""}),
            _make_spec("c", depends_on={"d": ""}),
            _make_spec("d"),
        ]
        order = resolve_build_order(specs)
        assert order.index("d") < order.index("b")
        assert order.index("d") < order.index("c")
        assert order.index("b") < order.index("a")
        assert order.index("c") < order.index("a")

    def test_independent_modules(self):
        """Modules with no deps can appear in any order, all present."""
        specs = [
            _make_spec("auth"),
            _make_spec("payment"),
            _make_spec("notifications"),
        ]
        order = resolve_build_order(specs)
        assert set(order) == {"auth", "payment", "notifications"}
        assert len(order) == 3

    def test_cyclic_dependency_raises(self):
        """Circular dependency should raise CyclicDependencyError."""
        specs = [
            _make_spec("a", depends_on={"b": ""}),
            _make_spec("b", depends_on={"a": ""}),
        ]
        with pytest.raises(CyclicDependencyError) as exc_info:
            resolve_build_order(specs)
        assert "a" in str(exc_info.value) or "b" in str(exc_info.value)

    def test_three_way_cycle_raises(self):
        """A -> B -> C -> A should raise."""
        specs = [
            _make_spec("a", depends_on={"b": ""}),
            _make_spec("b", depends_on={"c": ""}),
            _make_spec("c", depends_on={"a": ""}),
        ]
        with pytest.raises(CyclicDependencyError):
            resolve_build_order(specs)

    def test_self_dependency_raises(self):
        """Module depending on itself should raise."""
        specs = [_make_spec("a", depends_on={"a": ""})]
        with pytest.raises(CyclicDependencyError):
            resolve_build_order(specs)

    def test_external_deps_excluded_from_order(self):
        """External deps (not in spec set) should not appear in build order."""
        specs = [
            _make_spec("payment", depends_on={"postgres": "approved"}),
        ]
        order = resolve_build_order(specs)
        # postgres is external, not a .card.md module — exclude from order
        assert "postgres" not in order
        assert order == ["payment"]

    def test_preserves_all_modules(self):
        """All modules in the spec set appear in the build order."""
        specs = [
            _make_spec("a", depends_on={"b": ""}),
            _make_spec("b", depends_on={"c": ""}),
            _make_spec("c"),
            _make_spec("d"),
        ]
        order = resolve_build_order(specs)
        assert set(order) == {"a", "b", "c", "d"}
