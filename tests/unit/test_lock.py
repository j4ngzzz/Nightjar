"""Tests for nightjar lock — Sealed Dependency Manifest generation.

The lock module scans project imports, resolves installed versions,
computes SHA-256 hashes of distribution files, and writes a deps.lock
manifest to prevent hallucinated package attacks.

References:
- [REF-C08] Sealed Dependency Manifest
- [REF-P27] Package Hallucinations (slopsquatting) — 19.7% of AI deps are fake
- [REF-T05] uv — hash verification
- [REF-T06] pip-audit — CVE scanning
"""

import hashlib
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from nightjar.lock import (
    scan_project_imports,
    resolve_package_versions,
    compute_package_hash,
    generate_lock_file,
    parse_lock_entry,
    LockEntry,
)


# ── scan_project_imports ─────────────────────────────────


class TestScanProjectImports:
    """Scan Python source files to extract third-party imports."""

    def test_finds_imports_in_single_file(self, tmp_path):
        """Single .py file with imports should be detected."""
        src = tmp_path / "main.py"
        src.write_text("import click\nimport pydantic\nimport os\n")
        result = scan_project_imports(str(tmp_path))
        # os is stdlib, should be excluded
        assert "click" in result
        assert "pydantic" in result
        assert "os" not in result

    def test_finds_imports_in_nested_dirs(self, tmp_path):
        """Imports in subdirectories should be found."""
        pkg = tmp_path / "src" / "mymod"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("import yaml\n")
        (pkg / "core.py").write_text("from hypothesis import given\n")
        result = scan_project_imports(str(tmp_path))
        assert "yaml" in result
        assert "hypothesis" in result

    def test_skips_stdlib_imports(self, tmp_path):
        """Standard library imports should not appear in results."""
        src = tmp_path / "main.py"
        src.write_text("import os\nimport sys\nimport json\nimport pathlib\n")
        result = scan_project_imports(str(tmp_path))
        assert len(result) == 0

    def test_handles_from_imports(self, tmp_path):
        """from X import Y should capture X as the package."""
        src = tmp_path / "main.py"
        src.write_text("from click import command\nfrom pydantic import BaseModel\n")
        result = scan_project_imports(str(tmp_path))
        assert "click" in result
        assert "pydantic" in result

    def test_deduplicates_imports(self, tmp_path):
        """Same import from multiple files should appear only once."""
        (tmp_path / "a.py").write_text("import click\n")
        (tmp_path / "b.py").write_text("import click\nfrom click import group\n")
        result = scan_project_imports(str(tmp_path))
        assert result.count("click") == 1 if isinstance(result, list) else True
        # Should be a set or deduplicated list
        assert "click" in result

    def test_skips_non_python_files(self, tmp_path):
        """Non-.py files should be ignored."""
        (tmp_path / "readme.md").write_text("import click\n")
        (tmp_path / "data.json").write_text('{"import": "click"}')
        result = scan_project_imports(str(tmp_path))
        assert len(result) == 0

    def test_handles_syntax_errors_gracefully(self, tmp_path):
        """Files with syntax errors should be skipped, not crash."""
        (tmp_path / "bad.py").write_text("def foo(\n")  # syntax error
        (tmp_path / "good.py").write_text("import click\n")
        result = scan_project_imports(str(tmp_path))
        assert "click" in result

    def test_empty_project(self, tmp_path):
        """Empty directory should return empty set."""
        result = scan_project_imports(str(tmp_path))
        assert len(result) == 0

    def test_excludes_venv_and_hidden_dirs(self, tmp_path):
        """Virtual environments and hidden directories should be skipped."""
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "module.py").write_text("import flask\n")
        hidden = tmp_path / ".git" / "hooks"
        hidden.mkdir(parents=True)
        (hidden / "pre-commit.py").write_text("import black\n")
        (tmp_path / "main.py").write_text("import click\n")
        result = scan_project_imports(str(tmp_path))
        assert "click" in result
        assert "flask" not in result
        assert "black" not in result


# ── resolve_package_versions ─────────────────────────────


class TestResolvePackageVersions:
    """Map import names to installed package versions."""

    def test_resolves_installed_package(self):
        """Should find version for an installed package like click."""
        versions = resolve_package_versions({"click"})
        assert "click" in versions
        assert versions["click"]  # non-empty version string

    def test_handles_import_to_package_mapping(self):
        """yaml import should map to pyyaml package."""
        versions = resolve_package_versions({"yaml"})
        assert "pyyaml" in versions

    def test_skips_uninstalled_packages(self):
        """Packages not installed should not appear in result."""
        versions = resolve_package_versions({"nonexistent_fake_pkg_xyz"})
        assert "nonexistent_fake_pkg_xyz" not in versions
        assert len(versions) == 0


# ── compute_package_hash ─────────────────────────────────


class TestComputePackageHash:
    """Compute SHA-256 hash for package integrity verification."""

    def test_returns_hex_string(self):
        """Hash should be a 64-char hex string (SHA-256)."""
        hash_val = compute_package_hash("click")
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        # Valid hex
        int(hash_val, 16)

    def test_returns_empty_for_missing_package(self):
        """Missing package should return empty string."""
        hash_val = compute_package_hash("nonexistent_fake_pkg_xyz")
        assert hash_val == ""

    def test_deterministic(self):
        """Same package should produce same hash."""
        h1 = compute_package_hash("click")
        h2 = compute_package_hash("click")
        assert h1 == h2


# ── LockEntry ────────────────────────────────────────────


class TestLockEntry:
    """LockEntry dataclass for deps.lock entries."""

    def test_format_line(self):
        """Lock entry should format as package==version --hash=sha256:HASH."""
        entry = LockEntry(package="click", version="8.1.7", hash="abc123def456")
        line = entry.format_line()
        assert line == "click==8.1.7 --hash=sha256:abc123def456"

    def test_parse_roundtrip(self):
        """Parsing a formatted line should produce the same entry."""
        entry = LockEntry(package="click", version="8.1.7", hash="abc123def456")
        line = entry.format_line()
        parsed = parse_lock_entry(line)
        assert parsed is not None
        assert parsed.package == entry.package
        assert parsed.version == entry.version
        assert parsed.hash == entry.hash


# ── generate_lock_file ───────────────────────────────────


class TestGenerateLockFile:
    """Full lock file generation pipeline."""

    def test_creates_deps_lock_file(self, tmp_path):
        """generate_lock_file should create a deps.lock file."""
        src = tmp_path / "main.py"
        src.write_text("import click\n")
        output = tmp_path / "deps.lock"
        result = generate_lock_file(str(tmp_path), str(output))
        assert result is True
        assert output.exists()

    def test_deps_lock_has_header(self, tmp_path):
        """Generated deps.lock should have a header comment."""
        src = tmp_path / "main.py"
        src.write_text("import click\n")
        output = tmp_path / "deps.lock"
        generate_lock_file(str(tmp_path), str(output))
        content = output.read_text()
        assert content.startswith("# deps.lock")
        assert "[REF-C08]" in content

    def test_deps_lock_contains_packages(self, tmp_path):
        """Generated deps.lock should list detected packages."""
        src = tmp_path / "main.py"
        src.write_text("import click\n")
        output = tmp_path / "deps.lock"
        generate_lock_file(str(tmp_path), str(output))
        content = output.read_text()
        assert "click==" in content
        assert "--hash=sha256:" in content

    def test_deps_lock_format_matches_fixture(self, tmp_path):
        """Each non-comment line should match the format: pkg==ver --hash=sha256:hex."""
        src = tmp_path / "main.py"
        src.write_text("import click\nimport pytest\n")
        output = tmp_path / "deps.lock"
        generate_lock_file(str(tmp_path), str(output))
        content = output.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parsed = parse_lock_entry(line)
            assert parsed is not None, f"Failed to parse line: {line}"
            assert parsed.package
            assert parsed.version
            assert parsed.hash

    def test_returns_false_on_no_imports(self, tmp_path):
        """If no third-party imports found, should still succeed with empty lock."""
        src = tmp_path / "main.py"
        src.write_text("import os\nimport sys\n")
        output = tmp_path / "deps.lock"
        result = generate_lock_file(str(tmp_path), str(output))
        assert result is True
        assert output.exists()

    def test_sorted_output(self, tmp_path):
        """Packages in deps.lock should be sorted alphabetically."""
        src = tmp_path / "main.py"
        src.write_text("import pytest\nimport click\nimport hypothesis\n")
        output = tmp_path / "deps.lock"
        generate_lock_file(str(tmp_path), str(output))
        content = output.read_text()
        packages = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parsed = parse_lock_entry(line)
                if parsed:
                    packages.append(parsed.package)
        assert packages == sorted(packages)
