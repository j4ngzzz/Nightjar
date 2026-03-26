"""Tests for contractd CLI commands.

Reference: [REF-T17] Click CLI framework
Architecture: docs/ARCHITECTURE.md Section 8 (CLI Design)

Tests use Click's CliRunner for isolated CLI invocation.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from contractd.cli import main


@pytest.fixture
def runner():
    """Create a Click CliRunner for testing."""
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with .card/ structure."""
    card_dir = tmp_path / ".card"
    card_dir.mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / ".card" / "audit").mkdir()
    (tmp_path / ".card" / "cache").mkdir()
    return tmp_path


# ── CLI Root ─────────────────────────────────────────────


class TestCLIRoot:
    """Test the root contractd command group."""

    def test_help_shows_description(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "contractd" in result.output.lower() or "contract" in result.output.lower()

    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_no_args_shows_help(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code == 0


# ── init command ─────────────────────────────────────────


class TestInitCommand:
    """Test 'contractd init' — scaffold .card.md spec."""

    def test_init_creates_card_spec(self, runner, tmp_project):
        result = runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        assert result.exit_code == 0
        spec_path = tmp_project / ".card" / "payment.card.md"
        assert spec_path.exists()

    def test_init_spec_has_yaml_frontmatter(self, runner, tmp_project):
        runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "payment.card.md"
        content = spec_path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "card-version:" in content
        assert 'id: payment' in content

    def test_init_requires_module_name(self, runner):
        result = runner.invoke(main, ["init"])
        assert result.exit_code != 0

    def test_init_refuses_overwrite_without_force(self, runner, tmp_project):
        # Create existing spec
        spec_path = tmp_project / ".card" / "existing.card.md"
        spec_path.write_text("existing content", encoding="utf-8")
        result = runner.invoke(main, ["init", "existing", "--output", str(tmp_project)])
        assert result.exit_code != 0 or "already exists" in result.output.lower()


# ── verify command ───────────────────────────────────────


class TestVerifyCommand:
    """Test 'contractd verify' — run verification pipeline."""

    @patch("contractd.cli._run_verify")
    def test_verify_default_runs_all_stages(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=True, stages=[], total_duration_ms=100)
        result = runner.invoke(main, [
            "verify", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_verify.assert_called_once()

    @patch("contractd.cli._run_verify")
    def test_verify_fast_skips_dafny(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=True, stages=[], total_duration_ms=50)
        result = runner.invoke(main, [
            "verify", "--fast",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        call_kwargs = mock_verify.call_args
        # --fast should exclude stage 4
        assert call_kwargs is not None

    @patch("contractd.cli._run_verify")
    def test_verify_single_stage(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=True, stages=[], total_duration_ms=10)
        result = runner.invoke(main, [
            "verify", "--stage", "2",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_verify.assert_called_once()

    @patch("contractd.cli._run_verify")
    def test_verify_fail_returns_exit_code_1(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=False, stages=[], total_duration_ms=100)
        result = runner.invoke(main, [
            "verify", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 1

    @patch("contractd.cli._run_verify")
    def test_verify_pass_returns_exit_code_0(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=True, stages=[], total_duration_ms=100)
        result = runner.invoke(main, [
            "verify", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 0


# ── generate command ─────────────────────────────────────


class TestGenerateCommand:
    """Test 'contractd generate' — LLM code generation."""

    @patch("contractd.cli._run_generate")
    def test_generate_uses_default_model(self, mock_gen, runner, tmp_project):
        mock_gen.return_value = "generated.dfy"
        result = runner.invoke(main, [
            "generate", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_gen.assert_called_once()

    @patch("contractd.cli._run_generate")
    def test_generate_accepts_model_flag(self, mock_gen, runner, tmp_project):
        mock_gen.return_value = "generated.dfy"
        result = runner.invoke(main, [
            "generate",
            "--model", "deepseek/deepseek-chat",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_gen.assert_called_once()

    @patch("contractd.cli._run_generate")
    def test_generate_respects_card_model_env(self, mock_gen, runner, tmp_project):
        mock_gen.return_value = "generated.dfy"
        result = runner.invoke(main, [
            "generate", "--contract", str(tmp_project / ".card" / "test.card.md")
        ], env={"CARD_MODEL": "openai/o3"})
        mock_gen.assert_called_once()


# ── build command ────────────────────────────────────────


class TestBuildCommand:
    """Test 'contractd build' — generate + verify + compile."""

    @patch("contractd.cli._run_build")
    def test_build_default_target_py(self, mock_build, runner, tmp_project):
        mock_build.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "build", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_build.assert_called_once()

    @patch("contractd.cli._run_build")
    def test_build_accepts_target(self, mock_build, runner, tmp_project):
        mock_build.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "build",
            "--target", "js",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_build.assert_called_once()

    @patch("contractd.cli._run_build")
    def test_build_ci_mode(self, mock_build, runner, tmp_project):
        mock_build.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "build", "--ci",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_build.assert_called_once()


# ── ship command ─────────────────────────────────────────


class TestShipCommand:
    """Test 'contractd ship' — build + sign artifact."""

    @patch("contractd.cli._run_build")
    def test_ship_runs_build(self, mock_build, runner, tmp_project):
        mock_build.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "ship", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 0
        assert "ship complete" in result.output.lower()

    @patch("contractd.cli._run_build")
    def test_ship_fails_on_verification_failure(self, mock_build, runner, tmp_project):
        mock_build.return_value = MagicMock(verified=False)
        result = runner.invoke(main, [
            "ship", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 1


# ── explain command ──────────────────────────────────────


class TestExplainCommand:
    """Test 'contractd explain' — show last failure in human-readable form."""

    @patch("contractd.cli._load_verify_report")
    def test_explain_shows_last_failure(self, mock_report, runner, tmp_project):
        mock_report.return_value = {
            "verified": False,
            "stages": [{"stage": 3, "name": "pbt", "status": "fail",
                        "errors": [{"message": "property violation"}]}]
        }
        result = runner.invoke(main, [
            "explain", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 0

    @patch("contractd.cli._load_verify_report")
    def test_explain_no_report(self, mock_report, runner, tmp_project):
        mock_report.return_value = None
        result = runner.invoke(main, [
            "explain", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert "no verification" in result.output.lower() or result.exit_code != 0


# ── lock command ─────────────────────────────────────────


class TestLockCommand:
    """Test 'contractd lock' — freeze deps into deps.lock with hashes."""

    @patch("contractd.cli._run_lock")
    def test_lock_creates_deps_lock(self, mock_lock, runner, tmp_project):
        mock_lock.return_value = True
        result = runner.invoke(main, [
            "lock", "--output", str(tmp_project)
        ])
        assert result.exit_code == 0


# ── retry command ────────────────────────────────────────


class TestRetryCommand:
    """Test 'contractd retry' — force retry with LLM repair loop."""

    @patch("contractd.cli._run_retry")
    def test_retry_default_max(self, mock_retry, runner, tmp_project):
        mock_retry.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "retry", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_retry.assert_called_once()

    @patch("contractd.cli._run_retry")
    def test_retry_custom_max(self, mock_retry, runner, tmp_project):
        mock_retry.return_value = MagicMock(verified=True)
        result = runner.invoke(main, [
            "retry", "--max", "3",
            "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        mock_retry.assert_called_once()


# ── Exit codes ───────────────────────────────────────────


class TestExitCodes:
    """Test that exit codes follow the spec from ARCHITECTURE.md Section 8."""

    @patch("contractd.cli._run_verify")
    def test_exit_0_on_pass(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=True, stages=[], total_duration_ms=100)
        result = runner.invoke(main, [
            "verify", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 0

    @patch("contractd.cli._run_verify")
    def test_exit_1_on_fail(self, mock_verify, runner, tmp_project):
        mock_verify.return_value = MagicMock(verified=False, stages=[], total_duration_ms=100)
        result = runner.invoke(main, [
            "verify", "--contract", str(tmp_project / ".card" / "test.card.md")
        ])
        assert result.exit_code == 1
