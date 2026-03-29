"""Sealed dependency manifest generation — nightjar lock.

Scans project Python files for third-party imports, resolves installed
versions via importlib.metadata, computes SHA-256 hashes of installed
distribution files, and writes a deps.lock manifest.

This prevents hallucinated package attacks [REF-P27] where 19.7% of
AI-generated dependencies are fabricated. The sealed manifest [REF-C08]
ensures only verified, human-approved packages enter the build.

References:
- [REF-C08] Sealed Dependency Manifest — locked with SHA hashes
- [REF-P27] Package Hallucinations (slopsquatting) — USENIX
- [REF-T05] uv — hash verification pattern
- [REF-T06] pip-audit — CVE scanning integration point
"""

import ast
import hashlib
import importlib.metadata
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# Known import-name → package-name mappings where they differ.
# Public — imported by stages/deps.py to avoid duplication.
IMPORT_TO_PACKAGE: dict[str, str] = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "attr": "attrs",
    "dateutil": "python-dateutil",
    "gi": "pygobject",
    "Crypto": "pycryptodome",
}

# Directories to skip when scanning for imports
_SKIP_DIRS: set[str] = {
    ".venv", "venv", ".env", "env", ".git", ".hg", ".svn",
    "__pycache__", "node_modules", ".tox", ".nox", ".mypy_cache",
    ".pytest_cache", ".eggs", "dist", "build", ".card",
}

# deps.lock line format: package==version --hash=sha256:HASH
_LOCK_LINE_RE = re.compile(
    r"^(?P<package>[\w\-\.]+)==(?P<version>[\w\.\-]+)"
    r"(?:\s+--hash=(?P<algorithm>\w+):(?P<hash>[a-f0-9]+))?$"
)


@dataclass
class LockEntry:
    """A single entry in the deps.lock manifest.

    Format: package==version --hash=sha256:HASH
    Matches the format parsed by stages/deps.py [REF-C08].
    """

    package: str
    version: str
    hash: str

    def format_line(self) -> str:
        """Format as a deps.lock line."""
        return f"{self.package}=={self.version} --hash=sha256:{self.hash}"


def parse_lock_entry(line: str) -> LockEntry | None:
    """Parse a single deps.lock line into a LockEntry.

    Returns None if the line doesn't match the expected format.
    """
    line = line.strip()
    match = _LOCK_LINE_RE.match(line)
    if not match:
        return None
    return LockEntry(
        package=match.group("package"),
        version=match.group("version"),
        hash=match.group("hash") or "",
    )


def scan_project_imports(project_root: str) -> set[str]:
    """Scan all Python files under project_root for third-party imports.

    Walks the directory tree, parses each .py file's AST, extracts
    import statements, filters out stdlib modules, and returns the
    set of unique third-party root package names.

    Skips virtual environments, hidden directories, and __pycache__.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Set of third-party import names (root packages only).
    """
    root = Path(project_root)
    imports: set[str] = set()

    for py_file in _walk_python_files(root):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if not _is_stdlib(root_pkg):
                        imports.add(root_pkg)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if not _is_stdlib(root_pkg):
                        imports.add(root_pkg)

    return imports


def resolve_package_versions(import_names: set[str]) -> dict[str, str]:
    """Map import names to installed package names and versions.

    Handles import-name → package-name mismatches (e.g., yaml → pyyaml).
    Uses importlib.metadata to look up installed distributions.

    Args:
        import_names: Set of root import names.

    Returns:
        Dict mapping package name (not import name) → version string.
        Only includes packages that are actually installed.
    """
    resolved: dict[str, str] = {}

    for import_name in import_names:
        # Try the known mapping first
        pkg_name = IMPORT_TO_PACKAGE.get(import_name, import_name)
        version = _get_installed_version(pkg_name)
        if version:
            resolved[pkg_name] = version
            continue

        # Try the import name directly if mapping didn't work
        if pkg_name != import_name:
            version = _get_installed_version(import_name)
            if version:
                resolved[import_name] = version

    return resolved


def compute_package_hash(package_name: str) -> str:
    """Compute SHA-256 hash of a package's installed distribution metadata.

    Hashes the METADATA file from the installed distribution as a
    reproducible fingerprint for the exact installed version.

    Args:
        package_name: The package name (e.g., 'click').

    Returns:
        Hex-encoded SHA-256 hash string, or empty string if not found.
    """
    try:
        dist = importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""

    # Hash the METADATA file content as a stable fingerprint
    hasher = hashlib.sha256()
    try:
        metadata_text = dist.read_text("METADATA") or dist.read_text("PKG-INFO") or ""
        hasher.update(metadata_text.encode("utf-8"))
    except (FileNotFoundError, TypeError):
        # Fallback: hash the name + version
        hasher.update(f"{package_name}=={dist.version}".encode("utf-8"))

    return hasher.hexdigest()


def generate_lock_file(project_root: str, output_path: str) -> bool:
    """Generate a deps.lock sealed manifest from project imports.

    Full pipeline: scan imports → resolve versions → compute hashes → write file.

    The generated file format is compatible with stages/deps.py parsing,
    which validates generated code imports against this manifest [REF-C08].

    Args:
        project_root: Path to the project root to scan.
        output_path: Path where deps.lock will be written.

    Returns:
        True if lock file was generated successfully.
    """
    # Step 1: Scan project for third-party imports
    imports = scan_project_imports(project_root)

    # Step 2: Resolve to installed package versions
    packages = resolve_package_versions(imports)

    # Step 3: Build lock entries with hashes
    entries: list[LockEntry] = []
    for pkg_name, version in sorted(packages.items()):
        pkg_hash = compute_package_hash(pkg_name)
        if pkg_hash:
            entries.append(LockEntry(package=pkg_name, version=version, hash=pkg_hash))

    # Step 4: Write deps.lock
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# deps.lock — Sealed Dependency Manifest [REF-C08]",
        "# Generated by: nightjar lock",
        "# DO NOT manually edit. Run `nightjar lock` to update.",
        "#",
        "# Format: package==version --hash=sha256:HASH",
    ]
    for entry in entries:
        lines.append(entry.format_line())

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


# ── Private helpers ──────────────────────────────────────


def _walk_python_files(root: Path):
    """Yield .py files under root, skipping excluded directories."""
    if not root.is_dir():
        return

    for item in root.iterdir():
        if item.is_dir():
            if item.name in _SKIP_DIRS or item.name.startswith("."):
                continue
            yield from _walk_python_files(item)
        elif item.is_file() and item.suffix == ".py":
            yield item


def _is_stdlib(module_name: str) -> bool:
    """Check if a module is part of the Python standard library."""
    return module_name in sys.stdlib_module_names


def _get_installed_version(package_name: str) -> str:
    """Get the installed version of a package, or empty string if not installed."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""
