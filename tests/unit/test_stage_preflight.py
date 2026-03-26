"""Tests for Stage 0: Pre-flight verification.

Stage 0 validates:
1. .card.md YAML frontmatter is well-formed and parseable
2. Required fields exist (card-version, id, title, status)
3. Invariant tiers are valid values
4. If generated code is provided, Python AST parses successfully

Reference: docs/ARCHITECTURE.md Section 3 (Stage 0)
"""

import pytest
from contractd.stages.preflight import run_preflight
from contractd.types import StageResult, VerifyStatus


class TestPreflightValidSpec:
    """Pre-flight should PASS for well-formed .card.md specs."""

    def test_minimal_spec_passes(self):
        """Minimal valid spec should pass preflight."""
        result = run_preflight("tests/fixtures/minimal.card.md")
        assert isinstance(result, StageResult)
        assert result.stage == 0
        assert result.name == "preflight"
        assert result.status == VerifyStatus.PASS

    def test_full_spec_passes(self):
        """Full payment spec should pass preflight."""
        result = run_preflight("tests/fixtures/payment.card.md")
        assert result.status == VerifyStatus.PASS

    def test_duration_is_recorded(self):
        """Preflight should record duration in milliseconds."""
        result = run_preflight("tests/fixtures/minimal.card.md")
        assert result.duration_ms >= 0


class TestPreflightInvalidSpec:
    """Pre-flight should FAIL for malformed specs."""

    def test_malformed_yaml_fails(self):
        """Malformed YAML frontmatter should fail with error details."""
        result = run_preflight("tests/fixtures/invalid.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("yaml" in str(e).lower() or "parse" in str(e).lower()
                    for e in result.errors)

    def test_nonexistent_file_fails(self):
        """Missing file should fail with clear error."""
        result = run_preflight("tests/fixtures/nonexistent.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0

    def test_missing_required_fields_fails(self):
        """Spec missing card-version or id should fail."""
        result = run_preflight("tests/fixtures/missing_fields.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("required" in str(e).lower() or "missing" in str(e).lower()
                    for e in result.errors)


class TestPreflightCodeValidation:
    """Pre-flight should validate generated Python code AST if provided."""

    def test_valid_python_code_passes(self, tmp_path):
        """Valid Python code should pass AST check."""
        code_file = tmp_path / "valid.py"
        code_file.write_text("def hello():\n    return 'world'\n")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.PASS

    def test_invalid_python_code_fails(self, tmp_path):
        """Syntactically invalid Python should fail AST check."""
        code_file = tmp_path / "broken.py"
        code_file.write_text("def hello(\n    return 'world'\n")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("syntax" in str(e).lower() or "ast" in str(e).lower()
                    for e in result.errors)

    def test_empty_python_code_passes(self, tmp_path):
        """Empty Python file should pass AST check (valid empty module)."""
        code_file = tmp_path / "empty.py"
        code_file.write_text("")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.PASS
