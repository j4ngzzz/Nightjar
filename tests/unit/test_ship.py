"""Tests for nightjar ship — Artifact signing with provenance.

The ship module runs the full build pipeline (generate + verify + compile),
then hashes the resulting artifact and writes provenance metadata to
.card/verify.json including model used, timestamp, verification results,
and artifact SHA-256 hash.

References:
- [REF-C07] Don't Round-Trip — generated code is read-only
- [REF-C08] Sealed Dependency Manifest — deps.lock integrity
"""

import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from nightjar.ship import (
    hash_artifact,
    build_provenance,
    write_provenance,
    Provenance,
)


# ── hash_artifact ────────────────────────────────────────


class TestHashArtifact:
    """Compute SHA-256 hash of build artifacts."""

    def test_hashes_single_file(self, tmp_path):
        """Should hash a single artifact file."""
        artifact = tmp_path / "module.py"
        artifact.write_text("def hello(): return 42\n")
        result = hash_artifact(str(artifact))
        assert isinstance(result, str)
        assert len(result) == 64
        int(result, 16)  # valid hex

    def test_deterministic_hash(self, tmp_path):
        """Same content should produce same hash."""
        artifact = tmp_path / "module.py"
        artifact.write_text("x = 1\n")
        h1 = hash_artifact(str(artifact))
        h2 = hash_artifact(str(artifact))
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path):
        """Different content should produce different hashes."""
        a1 = tmp_path / "a.py"
        a2 = tmp_path / "b.py"
        a1.write_text("x = 1\n")
        a2.write_text("x = 2\n")
        assert hash_artifact(str(a1)) != hash_artifact(str(a2))

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Missing file should return empty string."""
        result = hash_artifact(str(tmp_path / "missing.py"))
        assert result == ""

    def test_hashes_directory_of_artifacts(self, tmp_path):
        """Should hash all files in a directory deterministically."""
        (tmp_path / "a.py").write_text("a = 1\n")
        (tmp_path / "b.py").write_text("b = 2\n")
        h1 = hash_artifact(str(tmp_path))
        h2 = hash_artifact(str(tmp_path))
        assert h1 == h2
        assert len(h1) == 64


# ── Provenance ───────────────────────────────────────────


class TestProvenance:
    """Provenance metadata for shipped artifacts."""

    def test_provenance_fields(self):
        """Provenance should have required fields."""
        p = Provenance(
            artifact_hash="abc123",
            model="claude-sonnet-4-6",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        assert p.artifact_hash == "abc123"
        assert p.model == "claude-sonnet-4-6"
        assert p.verified is True
        assert p.stages_passed == 5
        assert p.target == "py"

    def test_provenance_has_timestamp(self):
        """Provenance should have a timestamp."""
        p = Provenance(
            artifact_hash="abc",
            model="test",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        assert p.timestamp  # auto-generated
        assert isinstance(p.timestamp, str)

    def test_provenance_to_dict(self):
        """Provenance should serialize to dict for JSON."""
        p = Provenance(
            artifact_hash="abc",
            model="test",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        d = p.to_dict()
        assert d["artifact_hash"] == "abc"
        assert d["model"] == "test"
        assert d["verified"] is True
        assert "timestamp" in d
        assert d["target"] == "py"


# ── build_provenance ─────────────────────────────────────


class TestBuildProvenance:
    """Build provenance from verification results and artifact."""

    def test_builds_from_verify_result(self, tmp_path):
        """Should create provenance from verify result + artifact path."""
        artifact = tmp_path / "module.py"
        artifact.write_text("x = 42\n")

        provenance = build_provenance(
            artifact_path=str(artifact),
            model="claude-sonnet-4-6",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        assert provenance.verified is True
        assert provenance.model == "claude-sonnet-4-6"
        assert provenance.artifact_hash
        assert len(provenance.artifact_hash) == 64

    def test_provenance_captures_failure(self, tmp_path):
        """Failed verification should set verified=False."""
        artifact = tmp_path / "module.py"
        artifact.write_text("x = 42\n")

        provenance = build_provenance(
            artifact_path=str(artifact),
            model="test-model",
            verified=False,
            stages_passed=3,
            stages_total=5,
            target="py",
        )
        assert provenance.verified is False
        assert provenance.stages_passed == 3


# ── write_provenance ─────────────────────────────────────


class TestWriteProvenance:
    """Write provenance to .card/verify.json."""

    def test_writes_json_file(self, tmp_path):
        """Should write provenance to the specified path."""
        output = tmp_path / ".card" / "verify.json"
        p = Provenance(
            artifact_hash="abc",
            model="test",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        write_provenance(p, str(output))
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["artifact_hash"] == "abc"
        assert data["verified"] is True

    def test_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if they don't exist."""
        output = tmp_path / "deep" / "nested" / "verify.json"
        p = Provenance(
            artifact_hash="abc",
            model="test",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        write_provenance(p, str(output))
        assert output.exists()

    def test_json_is_readable(self, tmp_path):
        """Written JSON should be valid and human-readable (indented)."""
        output = tmp_path / "verify.json"
        p = Provenance(
            artifact_hash="abc123",
            model="claude-sonnet-4-6",
            verified=True,
            stages_passed=5,
            stages_total=5,
            target="py",
        )
        write_provenance(p, str(output))
        content = output.read_text()
        # Should be indented (pretty-printed)
        assert "\n" in content
        data = json.loads(content)
        assert data["model"] == "claude-sonnet-4-6"
