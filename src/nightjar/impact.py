"""Offline blast-radius analysis for Nightjar.

This module replaces any dependency on GitNexus for end-user blast-radius
analysis. It works entirely offline using the Python standard library (ast,
pathlib, os, collections). No external services or network calls are required.

The core idea: parse every .py file in the project with the ``ast`` module,
extract all import statements, build a forward import graph (module -> what it
imports), invert it to a reverse graph (module -> who imports it), then do a
breadth-first search to find every file that transitively depends on a changed
file.

Usage::

    from nightjar.impact import blast_radius, format_blast_radius

    affected = blast_radius("src/nightjar/parser.py", project_root=".")
    print(format_blast_radius(affected, changed="src/nightjar/parser.py"))
"""

import ast
import os
from collections import deque
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _iter_py_files(project_root: str) -> list[str]:
    """Return sorted list of all .py files under *project_root*."""
    root = Path(project_root).resolve()
    return sorted(str(p) for p in root.rglob("*.py"))


def _module_name_from_path(file_path: str, project_root: str) -> str:
    """Convert an absolute file path to a dotted module name relative to *project_root*.

    Examples
    --------
    ``/repo/src/nightjar/parser.py`` with root ``/repo`` ->
    ``src.nightjar.parser``
    """
    root = Path(project_root).resolve()
    path = Path(file_path).resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return str(path)
    parts = list(rel.parts)
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _extract_imports(file_path: str) -> set[str]:
    """Parse *file_path* with ``ast`` and return all imported module names.

    Both ``import foo`` and ``from foo import bar`` forms are handled.
    Relative imports (``from . import x``) are skipped — they cannot be
    resolved without knowing the package structure, and for blast-radius
    purposes the absolute imports are sufficient for cross-module tracking.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, OSError):
        return set()

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imported.add(node.module)
    return imported


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_import_graph(project_root: str) -> dict[str, set[str]]:
    """Walk all .py files under *project_root* and build a forward import graph.

    The graph maps each absolute file path to the set of module names (dotted
    strings) that file imports at the top level.

    Parameters
    ----------
    project_root:
        Root directory of the project to scan.

    Returns
    -------
    dict[str, set[str]]
        ``{"/abs/path/to/file.py": {"nightjar.parser", "os", ...}, ...}``
    """
    graph: dict[str, set[str]] = {}
    for py_file in _iter_py_files(project_root):
        graph[py_file] = _extract_imports(py_file)
    return graph


def blast_radius(changed_file: str, project_root: str = ".") -> list[str]:
    """Return all files that transitively import *changed_file*.

    Performs a breadth-first search on the *reverse* import graph starting
    from *changed_file*. A file A is included in the result if there exists a
    chain ``A imports B imports … imports changed_file``.

    Parameters
    ----------
    changed_file:
        Path to the file that was modified. Can be relative or absolute.
    project_root:
        Root directory of the project to scan (defaults to current directory).

    Returns
    -------
    list[str]
        Sorted list of absolute file paths that depend on *changed_file*.
        The changed file itself is not included.
    """
    root = Path(project_root).resolve()
    target = Path(changed_file).resolve()
    target_module = _module_name_from_path(str(target), str(root))

    forward_graph = build_import_graph(str(root))

    # Build reverse graph: module_name -> set of files that import it
    reverse: dict[str, set[str]] = {}
    for file_path, imports in forward_graph.items():
        for mod in imports:
            reverse.setdefault(mod, set()).add(file_path)

    # Also map by file path key so we can look up by path as well as by name
    # Keys in reverse are module names; we also want to handle path-based lookup.
    affected: set[str] = set()
    queue: deque[str] = deque()

    # Seed BFS with every file that directly imports the target module
    direct_importers = reverse.get(target_module, set())
    for importer in direct_importers:
        if importer != str(target) and importer not in affected:
            affected.add(importer)
            queue.append(importer)

    # BFS through transitive importers
    while queue:
        current = queue.popleft()
        current_module = _module_name_from_path(current, str(root))
        for importer in reverse.get(current_module, set()):
            if importer != str(target) and importer not in affected:
                affected.add(importer)
                queue.append(importer)

    return sorted(affected)


def spec_blast_radius(spec_id: str, project_root: str = ".") -> list[str]:
    """Find all .py files that reference *spec_id* as a string literal.

    Uses ``ast.walk`` to inspect every ``ast.Constant`` node in every .py
    file. This catches spec IDs embedded in decorators, docstrings, test
    parametrize calls, and similar patterns without relying on text search.

    Parameters
    ----------
    spec_id:
        The spec identifier string to search for (e.g. ``"payment"``).
    project_root:
        Root directory of the project to scan.

    Returns
    -------
    list[str]
        Sorted list of absolute file paths containing *spec_id* as a literal.
    """
    root = Path(project_root).resolve()
    matches: list[str] = []

    for py_file in _iter_py_files(str(root)):
        try:
            source = Path(py_file).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=py_file)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if spec_id in node.value:
                    matches.append(py_file)
                    break  # one match per file is enough

    return sorted(matches)


def format_blast_radius(files: list[str], changed: str = "") -> str:
    """Format a blast-radius result as a human-readable string.

    Parameters
    ----------
    files:
        List of affected file paths (as returned by :func:`blast_radius` or
        :func:`spec_blast_radius`).
    changed:
        The file that was changed (shown in the header when provided).

    Returns
    -------
    str
        A multi-line string suitable for printing to a terminal, e.g.::

            3 files affected by changes to src/nightjar/parser.py:
              src/nightjar/cli.py
              src/nightjar/verifier.py
              tests/test_parser.py
    """
    n = len(files)
    if changed:
        header = f"{n} file{'s' if n != 1 else ''} affected by changes to {changed}:"
    else:
        header = f"{n} file{'s' if n != 1 else ''} affected:"

    if not files:
        return header + " (none)"

    lines = [header]
    for f in files:
        lines.append(f"  {f}")
    return os.linesep.join(lines)
