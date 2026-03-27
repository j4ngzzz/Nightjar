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
from nightjar.stages.deps import run_deps_check, parse_deps_lock, detect_drift
from nightjar.types import StageResult, VerifyStatus


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


# ── W2-1: sbomlyze drift detection [rezmoss/sbomlyze] ───────────────────────


def _pkg(version: str, hash_val: str = "abc123") -> dict:
    """Build a minimal package dict as returned by parse_deps_lock."""
    return {"version": version, "hash": hash_val, "algorithm": "sha256"}


class TestDetectDrift:
    """detect_drift() classifies dependency changes into 3 categories.

    Priority: integrity > version > metadata (sbomlyze ClassifyDrift order).
    Integrity drift (hash change without version bump) = supply chain signal.

    Source: rezmoss/sbomlyze internal/analysis/drift.go
    """

    def test_no_changes_returns_empty(self):
        """Identical snapshots produce no drift events."""
        lock = {"click": _pkg("8.1.7", "aaa"), "pydantic": _pkg("2.0.0", "bbb")}
        assert detect_drift(lock, lock) == []

    def test_version_drift_detected(self):
        """Version change is classified as version drift, info severity."""
        current = {"click": _pkg("8.2.0", "newhash")}
        baseline = {"click": _pkg("8.1.7", "oldhash")}
        events = detect_drift(current, baseline)
        assert len(events) == 1
        assert events[0]["drift_type"] == "version"
        assert events[0]["severity"] == "info"
        assert events[0]["version_from"] == "8.1.7"
        assert events[0]["version_to"] == "8.2.0"

    def test_integrity_drift_detected(self):
        """Hash change WITHOUT version bump = integrity drift, HIGH severity."""
        current = {"click": _pkg("8.1.7", "tampered_hash")}
        baseline = {"click": _pkg("8.1.7", "original_hash")}
        events = detect_drift(current, baseline)
        assert len(events) == 1
        assert events[0]["drift_type"] == "integrity"
        assert events[0]["severity"] == "high"
        assert events[0]["version"] == "8.1.7"

    def test_integrity_priority_over_version(self):
        """When both hash and version change, version drift is reported (not integrity).

        sbomlyze reserves integrity for the anomalous case only (same version).
        """
        current = {"click": _pkg("8.2.0", "newhash")}
        baseline = {"click": _pkg("8.1.7", "oldhash")}
        events = detect_drift(current, baseline)
        assert events[0]["drift_type"] == "version"

    def test_added_package_detected(self):
        """Package only in current → drift_type 'added', info severity."""
        current = {"click": _pkg("8.1.7"), "requests": _pkg("2.31.0")}
        baseline = {"click": _pkg("8.1.7")}
        events = detect_drift(current, baseline)
        added = [e for e in events if e["drift_type"] == "added"]
        assert len(added) == 1
        assert added[0]["package"] == "requests"
        assert added[0]["severity"] == "info"

    def test_removed_package_detected(self):
        """Package only in baseline → drift_type 'removed', info severity."""
        current = {"click": _pkg("8.1.7")}
        baseline = {"click": _pkg("8.1.7"), "requests": _pkg("2.31.0")}
        events = detect_drift(current, baseline)
        removed = [e for e in events if e["drift_type"] == "removed"]
        assert len(removed) == 1
        assert removed[0]["package"] == "requests"

    def test_empty_hash_not_flagged_as_integrity(self):
        """Missing hash in either snapshot is not treated as integrity drift."""
        current = {"click": {"version": "8.1.7", "hash": "", "algorithm": ""}}
        baseline = {"click": {"version": "8.1.7", "hash": "abc", "algorithm": "sha256"}}
        events = detect_drift(current, baseline)
        # hash_changed requires both sides to have non-empty hashes
        assert not any(e["drift_type"] == "integrity" for e in events)

    def test_run_deps_check_fails_on_integrity_drift(self, tmp_path):
        """run_deps_check with baseline_lock_path fails when integrity drift found."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import click\n")

        # Use valid hex hashes (regex: [a-f0-9]+)
        current_lock = tmp_path / "current.lock"
        current_lock.write_text("click==8.1.7 --hash=sha256:deadbeef\n")

        baseline_lock = tmp_path / "baseline.lock"
        baseline_lock.write_text("click==8.1.7 --hash=sha256:cafebabe\n")

        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path=str(current_lock),
            baseline_lock_path=str(baseline_lock),
        )
        assert result.status == VerifyStatus.FAIL
        assert any(e.get("drift_type") == "integrity" for e in result.errors)

    def test_run_deps_check_passes_on_version_drift_only(self, tmp_path):
        """run_deps_check passes when only version drift (no integrity risk)."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import click\n")

        # Same hash prefix, different versions → version drift only
        current_lock = tmp_path / "current.lock"
        current_lock.write_text("click==8.2.0 --hash=sha256:aabbcc\n")

        baseline_lock = tmp_path / "baseline.lock"
        baseline_lock.write_text("click==8.1.7 --hash=sha256:ddeeff\n")

        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path=str(current_lock),
            baseline_lock_path=str(baseline_lock),
        )
        assert result.status == VerifyStatus.PASS

    def test_run_deps_check_no_baseline_ignores_drift(self, tmp_path):
        """Without baseline_lock_path, drift check is skipped entirely."""
        code_file = tmp_path / "module.py"
        code_file.write_text("import click\n")
        result = run_deps_check(
            code_path=str(code_file),
            deps_lock_path="tests/fixtures/deps.lock",
        )
        assert result.status == VerifyStatus.PASS
