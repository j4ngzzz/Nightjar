"""Tests for Stage 1: Dependency check.

Stage 1 validates generated code imports against a sealed dependency
manifest (deps.lock). Prevents hallucinated packages [REF-P27] and
ensures all dependencies are pinned with hashes [REF-C08].

References:
- [REF-C08] Sealed Dependency Manifest
- [REF-P27] Package Hallucinations (slopsquatting)
- [REF-T05] uv — hash verification
- [REF-T06] pip-audit — CVE scanning
"""

import pytest
from contractd.stages.deps import run_deps_check, parse_deps_lock
from contractd.types import StageResult, VerifyStatus


class TestDepsLockParsing:
    """Parse deps.lock sealed manifest."""

    def test_parse_valid_deps_lock(self):
        """Parse the test deps.lock fixture."""
        packages = parse_deps_lock("tests/fixtures/deps.lock")
        assert isinstance(packages, dict)
        assert "click" in packages
        assert "pydantic" in packages
        assert "pyyaml" in packages
        assert packages["click"]["version"] == "8.1.7"
        assert "hash" in packages["click"]

    def test_parse_nonexistent_deps_lock(self):
        """Missing deps.lock should return empty dict."""
        packages = parse_deps_lock("nonexistent/deps.lock")
        assert packages == {}


class TestDepsCheckAllowed:
    """Stage 1 should PASS when all imports are in deps.lock."""

    def test_allowed_imports_pass(self, tmp_path):
        """Code importing only allowed packages should pass."""
        code_file = tmp_path / "module.py"
        code_file.write_text(
            "import click\nimport pydantic\nimport yaml\n"
        )
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert isinstance(result, StageResult)
        assert result.stage == 1
        assert result.name == "deps"
        assert result.status == VerifyStatus.PASS

    def test_stdlib_imports_always_pass(self, tmp_path):
        """Standard library imports should always be allowed."""
        code_file = tmp_path / "module.py"
        code_file.write_text(
            "import os\nimport sys\nimport json\nimport pathlib\n"
            "from collections import defaultdict\n"
        )
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.PASS

    def test_from_imports_pass(self, tmp_path):
        """'from X import Y' should check the root package."""
        code_file = tmp_path / "module.py"
        code_file.write_text(
            "from pydantic import BaseModel\nfrom click import command\n"
        )
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.PASS


class TestDepsCheckDisallowed:
    """Stage 1 should FAIL when imports are NOT in deps.lock."""

    def test_unknown_package_fails(self, tmp_path):
        """Importing a package not in deps.lock should fail [REF-P27]."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import requests\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("requests" in str(e) for e in result.errors)

    def test_hallucinated_package_fails(self, tmp_path):
        """A completely fake package should fail — slopsquatting defense."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import totally_fake_pkg_12345\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.FAIL

    def test_multiple_disallowed_reports_all(self, tmp_path):
        """Multiple disallowed imports should all be reported."""
        code_file = tmp_path / "module.py"
        code_file.write_text(
            "import requests\nimport flask\nimport numpy\n"
        )
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.FAIL
        # Should report all three
        error_text = str(result.errors)
        assert "requests" in error_text
        assert "flask" in error_text
        assert "numpy" in error_text


class TestDepsCheckEdgeCases:
    """Edge cases for dependency checking."""

    def test_missing_code_file_fails(self):
        """Missing code file should fail."""
        result = run_deps_check(
            code_path="nonexistent.py",
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.FAIL

    def test_missing_deps_lock_fails(self, tmp_path):
        """Missing deps.lock should fail — sealed manifest is mandatory."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import click\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="nonexistent/deps.lock",
        )
        assert result.status == VerifyStatus.FAIL

    def test_empty_code_passes(self, tmp_path):
        """Code with no imports should pass."""
        code_file = tmp_path / "module.py"
        code_file.write_text("x = 42\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.PASS

    def test_duration_is_recorded(self, tmp_path):
        """Stage should record duration."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import click\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.duration_ms >= 0
