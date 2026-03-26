"""Tests for audit branch system.

After a successful build, generated code is copied to .card/audit/
as read-only files for compliance and git-trackable auditing.
The audit directory preserves a snapshot of every verified generation.

References:
- [REF-C07] Don't Round-Trip — generated code is NEVER manually edited
"""

import os
import stat
from pathlib import Path

import pytest

from contractd.audit import (
    archive_artifact,
    list_audited_modules,
    get_audit_path,
    is_audit_current,
)


# ── archive_artifact ─────────────────────────────────────


class TestArchiveArtifact:
    """Copy generated code to .card/audit/ as read-only."""

    def test_copies_file_to_audit_dir(self, tmp_path):
        """Generated file should be copied to audit directory."""
        source = tmp_path / "generated" / "payment.py"
        source.parent.mkdir(parents=True)
        source.write_text("# generated code\ndef pay(): pass\n")
        audit_dir = tmp_path / ".card" / "audit"

        result = archive_artifact(
            source_path=str(source),
            module_id="payment",
            target="py",
            audit_dir=str(audit_dir),
        )
        assert result is True
        dest = audit_dir / "payment.py"
        assert dest.exists()
        content = dest.read_text()
        # Source content should be present (with header prepended)
        assert "def pay(): pass" in content
        assert "# generated code" in content

    def test_creates_audit_dir_if_missing(self, tmp_path):
        """Should create the audit directory if it doesn't exist."""
        source = tmp_path / "module.py"
        source.write_text("x = 1\n")
        audit_dir = tmp_path / "deep" / "audit"

        archive_artifact(str(source), "module", "py", str(audit_dir))
        assert audit_dir.exists()

    def test_marks_file_as_read_only(self, tmp_path):
        """Archived files should be read-only [REF-C07]."""
        source = tmp_path / "module.py"
        source.write_text("x = 1\n")
        audit_dir = tmp_path / ".card" / "audit"

        archive_artifact(str(source), "module", "py", str(audit_dir))
        dest = audit_dir / "module.py"
        # Check that write bits are cleared
        mode = dest.stat().st_mode
        assert not (mode & stat.S_IWUSR)
        assert not (mode & stat.S_IWGRP)
        assert not (mode & stat.S_IWOTH)

    def test_overwrites_existing_audit_file(self, tmp_path):
        """Re-archiving should overwrite the previous version."""
        source = tmp_path / "module.py"
        audit_dir = tmp_path / ".card" / "audit"
        audit_dir.mkdir(parents=True)

        source.write_text("v1\n")
        archive_artifact(str(source), "module", "py", str(audit_dir))

        source.write_text("v2\n")
        archive_artifact(str(source), "module", "py", str(audit_dir))

        dest = audit_dir / "module.py"
        content = dest.read_text()
        assert "v2" in content
        assert "v1" not in content

    def test_adds_header_comment(self, tmp_path):
        """Archived file should have a header indicating it's generated."""
        source = tmp_path / "module.py"
        source.write_text("def foo(): pass\n")
        audit_dir = tmp_path / ".card" / "audit"

        archive_artifact(str(source), "module", "py", str(audit_dir))
        content = (audit_dir / "module.py").read_text()
        assert "GENERATED FROM SPEC" in content or "DO NOT EDIT" in content

    def test_handles_dafny_target(self, tmp_path):
        """Should work with .dfy extension for Dafny files."""
        source = tmp_path / "module.dfy"
        source.write_text("method Main() {}\n")
        audit_dir = tmp_path / ".card" / "audit"

        archive_artifact(str(source), "module", "dfy", str(audit_dir))
        dest = audit_dir / "module.dfy"
        assert dest.exists()

    def test_returns_false_for_missing_source(self, tmp_path):
        """Should return False if source file doesn't exist."""
        audit_dir = tmp_path / ".card" / "audit"
        result = archive_artifact(
            str(tmp_path / "missing.py"), "module", "py", str(audit_dir)
        )
        assert result is False


# ── list_audited_modules ─────────────────────────────────


class TestListAuditedModules:
    """List modules that have been archived."""

    def test_lists_archived_modules(self, tmp_path):
        """Should return list of archived module names."""
        audit_dir = tmp_path / ".card" / "audit"
        audit_dir.mkdir(parents=True)
        (audit_dir / "payment.py").write_text("# payment\n")
        (audit_dir / "auth.py").write_text("# auth\n")

        modules = list_audited_modules(str(audit_dir))
        assert "payment" in modules
        assert "auth" in modules

    def test_empty_audit_dir(self, tmp_path):
        """Empty audit dir should return empty list."""
        audit_dir = tmp_path / ".card" / "audit"
        audit_dir.mkdir(parents=True)
        modules = list_audited_modules(str(audit_dir))
        assert modules == []

    def test_missing_audit_dir(self, tmp_path):
        """Missing audit dir should return empty list."""
        modules = list_audited_modules(str(tmp_path / "nonexistent"))
        assert modules == []


# ── get_audit_path ───────────────────────────────────────


class TestGetAuditPath:
    """Get the expected path for a module's audit file."""

    def test_returns_correct_path(self, tmp_path):
        """Should return audit_dir/module.ext."""
        audit_dir = str(tmp_path / ".card" / "audit")
        path = get_audit_path("payment", "py", audit_dir)
        assert path.endswith("payment.py")
        assert ".card" in path

    def test_dafny_extension(self, tmp_path):
        """Should use .dfy for Dafny target."""
        audit_dir = str(tmp_path / ".card" / "audit")
        path = get_audit_path("module", "dfy", audit_dir)
        assert path.endswith("module.dfy")

    def test_js_extension(self, tmp_path):
        """Should use .js for JS target."""
        audit_dir = str(tmp_path / ".card" / "audit")
        path = get_audit_path("module", "js", audit_dir)
        assert path.endswith("module.js")


# ── is_audit_current ─────────────────────────────────────


class TestIsAuditCurrent:
    """Check if the audit file matches the current generated artifact."""

    def test_current_when_same_content(self, tmp_path):
        """Should return True when audit matches source."""
        source = tmp_path / "module.py"
        source.write_text("x = 1\n")
        audit_dir = tmp_path / ".card" / "audit"

        archive_artifact(str(source), "module", "py", str(audit_dir))
        assert is_audit_current(str(source), "module", "py", str(audit_dir)) is True

    def test_not_current_when_source_changed(self, tmp_path):
        """Should return False when source differs from audit."""
        source = tmp_path / "module.py"
        source.write_text("v1\n")
        audit_dir = tmp_path / ".card" / "audit"

        archive_artifact(str(source), "module", "py", str(audit_dir))
        source.write_text("v2\n")
        assert is_audit_current(str(source), "module", "py", str(audit_dir)) is False

    def test_not_current_when_no_audit(self, tmp_path):
        """Should return False when no audit file exists."""
        source = tmp_path / "module.py"
        source.write_text("x = 1\n")
        assert is_audit_current(
            str(source), "module", "py", str(tmp_path / "audit")
        ) is False
