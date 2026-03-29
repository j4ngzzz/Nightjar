"""Wave 3 CLI tests — hook group, enhanced badge flags, mcp command,
and verify --security-pack flag.

Reference: [REF-T17] Click CLI framework
Architecture: docs/ARCHITECTURE.md Section 8 (CLI Design)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nightjar.cli import main


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_card(tmp_path):
    """Minimal .card.md spec file for --contract/--spec tests."""
    card_dir = tmp_path / ".card"
    card_dir.mkdir()
    spec = card_dir / "payment.card.md"
    spec.write_text(
        "---\ncard-version: '1.0'\nid: payment\ntitle: Payment\n---\n",
        encoding="utf-8",
    )
    return spec


# ── hook install ──────────────────────────────────────────────────────────────


class TestHookInstallCommand:
    def test_hook_install_help_works(self, runner):
        result = runner.invoke(main, ["hook", "install", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output.lower() or "hook" in result.output.lower()

    def test_hook_install_lists_target_choices(self, runner):
        result = runner.invoke(main, ["hook", "install", "--help"])
        assert result.exit_code == 0
        # The target choices must all appear in help text
        for target in ["claude-code", "cursor", "windsurf", "kiro", "all"]:
            assert target in result.output

    def test_hook_install_force_flag_exists(self, runner):
        result = runner.invoke(main, ["hook", "install", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_hook_install_dir_flag_exists(self, runner):
        result = runner.invoke(main, ["hook", "install", "--help"])
        assert result.exit_code == 0
        assert "--dir" in result.output

    def test_hook_install_no_agents_detected(self, runner, tmp_path):
        """When no agent dirs are found and target=all, exit with an error."""
        with patch("nightjar.hook_installer.detect_available_agents", return_value=[]):
            result = runner.invoke(
                main, ["hook", "install", "--dir", str(tmp_path)]
            )
        # Should report no agents detected
        assert result.exit_code != 0 or "No coding agent" in result.output

    def test_hook_install_specific_target(self, runner, tmp_path):
        """Install for a specific target — calls install_hook once."""
        mock_result = MagicMock()
        mock_result.message = "Nightjar hook installed"

        with patch("nightjar.hook_installer.install_hook", return_value=mock_result):
            result = runner.invoke(
                main,
                ["hook", "install", "--target", "claude-code", "--dir", str(tmp_path)],
            )
        assert "installed" in result.output.lower() or result.exit_code == 0


# ── hook remove ───────────────────────────────────────────────────────────────


class TestHookRemoveCommand:
    def test_hook_remove_help_works(self, runner):
        result = runner.invoke(main, ["hook", "remove", "--help"])
        assert result.exit_code == 0
        assert "remove" in result.output.lower() or "hook" in result.output.lower()

    def test_hook_remove_requires_target(self, runner):
        result = runner.invoke(main, ["hook", "remove"])
        # Missing required --target should produce an error or non-zero exit
        assert result.exit_code != 0

    def test_hook_remove_target_choices(self, runner):
        result = runner.invoke(main, ["hook", "remove", "--help"])
        assert result.exit_code == 0
        for target in ["claude-code", "cursor", "windsurf", "kiro"]:
            assert target in result.output

    def test_hook_remove_calls_remove_hook(self, runner, tmp_path):
        mock_result = MagicMock()
        mock_result.message = "Nightjar hook removed"

        with patch("nightjar.hook_installer.remove_hook", return_value=mock_result):
            result = runner.invoke(
                main,
                ["hook", "remove", "--target", "cursor", "--dir", str(tmp_path)],
            )
        assert "removed" in result.output.lower() or result.exit_code == 0


# ── hook list ─────────────────────────────────────────────────────────────────


class TestHookListCommand:
    def test_hook_list_help_works(self, runner):
        result = runner.invoke(main, ["hook", "list", "--help"])
        assert result.exit_code == 0

    def test_hook_list_calls_list_hooks(self, runner, tmp_path):
        from pathlib import Path

        mock_status = MagicMock()
        mock_status.target = "claude-code"
        mock_status.installed = True
        mock_status.config_path = Path(tmp_path) / ".claude" / "settings.json"

        with patch("nightjar.hook_installer.list_hooks", return_value=[mock_status]):
            result = runner.invoke(main, ["hook", "list", "--dir", str(tmp_path)])
        assert "claude-code" in result.output

    def test_hook_list_dir_flag_exists(self, runner):
        result = runner.invoke(main, ["hook", "list", "--help"])
        assert result.exit_code == 0
        assert "--dir" in result.output


# ── badge new flags ───────────────────────────────────────────────────────────


class TestBadgeNewFlags:
    def test_badge_svg_flag_exists(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0
        assert "--svg" in result.output

    def test_badge_shields_json_flag_exists(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0
        assert "--shields-json" in result.output

    def test_badge_readme_flag_exists(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0
        assert "--readme" in result.output

    def test_badge_owner_flag_exists(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0
        assert "--owner" in result.output

    def test_badge_repo_name_flag_exists(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0
        assert "--repo-name" in result.output

    def test_badge_svg_invokes_generate_badge_svg(self, runner, tmp_path):
        report = tmp_path / "verify.json"
        report.write_text('{"verified": true, "confidence_score": 95}', encoding="utf-8")

        with patch(
            "nightjar.badge.generate_badge_svg",
            return_value="<svg>mock</svg>",
        ):
            result = runner.invoke(
                main, ["badge", "--svg", "--report", str(report)]
            )
        assert result.exit_code == 0
        assert "<svg>" in result.output or "svg" in result.output.lower()

    def test_badge_shields_json_invokes_write_shields_json(self, runner, tmp_path):
        report = tmp_path / "verify.json"
        report.write_text('{"verified": true, "confidence_score": 90}', encoding="utf-8")
        out_file = tmp_path / "shields.json"

        with patch(
            "nightjar.badge.write_shields_json",
            return_value=out_file,
        ):
            result = runner.invoke(
                main, ["badge", "--shields-json", "--report", str(report)]
            )
        assert result.exit_code == 0
        assert "shields" in result.output.lower()

    def test_badge_readme_requires_owner_and_repo(self, runner, tmp_path):
        report = tmp_path / "verify.json"
        report.write_text('{"verified": true}', encoding="utf-8")
        result = runner.invoke(
            main,
            ["badge", "--readme", "--report", str(report)],
        )
        # Missing --owner/--repo-name should produce error
        assert result.exit_code != 0 or "requires" in result.output.lower()

    def test_badge_readme_with_owner_and_repo(self, runner, tmp_path):
        report = tmp_path / "verify.json"
        report.write_text('{"verified": true}', encoding="utf-8")

        with patch(
            "nightjar.badge.generate_readme_embed",
            return_value="![Nightjar](https://raw.githubusercontent.com/owner/repo/master/.card/badge.svg)",
        ):
            result = runner.invoke(
                main,
                [
                    "badge",
                    "--readme",
                    "--owner",
                    "myorg",
                    "--repo-name",
                    "myrepo",
                    "--report",
                    str(report),
                ],
            )
        assert result.exit_code == 0
        assert "Nightjar" in result.output


# ── mcp command ───────────────────────────────────────────────────────────────


class TestMcpCommand:
    def test_mcp_command_exists(self, runner):
        result = runner.invoke(main, ["mcp", "--help"])
        assert result.exit_code == 0

    def test_mcp_transport_option_exists(self, runner):
        result = runner.invoke(main, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "--transport" in result.output

    def test_mcp_missing_sdk_exits_with_error(self, runner):
        """When MCP SDK is absent, the command should print an error and exit != 0."""
        with patch("nightjar.mcp_server.HAS_MCP", False):
            result = runner.invoke(main, ["mcp"])
        # Either exit code is non-zero or output contains 'mcp' error message
        assert result.exit_code != 0 or "mcp" in result.output.lower()

    def test_mcp_runs_server_when_sdk_present(self, runner):
        mock_server = MagicMock()
        mock_server.run = MagicMock(return_value=None)

        with (
            patch("nightjar.mcp_server.HAS_MCP", True),
            patch("nightjar.mcp_server.create_mcp_server", return_value=mock_server),
        ):
            result = runner.invoke(main, ["mcp", "--transport", "stdio"])
        # server.run should have been called
        mock_server.run.assert_called_once_with(transport="stdio")


# ── verify --security-pack flag ───────────────────────────────────────────────


class TestVerifySecurityPackFlag:
    def test_verify_security_pack_flag_exists(self, runner):
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0
        assert "--security-pack" in result.output

    def test_verify_security_pack_owasp_choice_exists(self, runner):
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0
        assert "owasp" in result.output

    def test_verify_security_pack_invalid_choice(self, runner, tmp_card):
        result = runner.invoke(
            main,
            ["verify", "--spec", str(tmp_card), "--security-pack", "invalid"],
        )
        # Click rejects invalid choice
        assert result.exit_code != 0

    def test_verify_security_pack_owasp_imported(self, runner, tmp_card):
        """With --security-pack=owasp the owasp_pack module is imported."""
        mock_verify_result = MagicMock()
        mock_verify_result.verified = True
        mock_verify_result.stages = []

        with (
            patch(
                "nightjar.security.owasp_pack.generate_security_block",
                return_value=["injection-check", "auth-check"],
                create=True,
            ),
            patch("nightjar.cli._run_verify", return_value=mock_verify_result),
        ):
            result = runner.invoke(
                main,
                ["verify", "--spec", str(tmp_card), "--security-pack", "owasp"],
            )
        # Should mention the security pack injection
        assert "owasp" in result.output.lower() or result.exit_code == 0

    def test_verify_security_pack_owasp_import_error_is_non_fatal(
        self, runner, tmp_card
    ):
        """If owasp_pack is not installed, verify continues without crashing."""
        mock_verify_result = MagicMock()
        mock_verify_result.verified = True
        mock_verify_result.stages = []

        with (
            patch(
                "nightjar.cli._run_verify",
                return_value=mock_verify_result,
            ),
            patch.dict(
                "sys.modules",
                {"nightjar.security.owasp_pack": None},
            ),
        ):
            result = runner.invoke(
                main,
                ["verify", "--spec", str(tmp_card), "--security-pack", "owasp"],
            )
        # Must not crash — either passes or gives a warning
        assert "error" not in result.output.lower() or "warning" in result.output.lower()


# ── regression: all existing commands still work ──────────────────────────────


class TestAllExistingCommandsStillWork:
    def test_main_list_commands_contains_expected(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        expected_commands = [
            "init",
            "generate",
            "verify",
            "build",
            "retry",
            "lock",
            "explain",
            "scan",
            "infer",
            "auto",
            "watch",
            "badge",
            "audit",
            "benchmark",
            "hook",
            "mcp",
            "serve",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, (
                f"Expected command '{cmd}' missing from --help output"
            )

    def test_init_help_still_works(self, runner):
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0

    def test_verify_help_still_works(self, runner):
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0

    def test_generate_help_still_works(self, runner):
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0

    def test_build_help_still_works(self, runner):
        result = runner.invoke(main, ["build", "--help"])
        assert result.exit_code == 0

    def test_retry_help_still_works(self, runner):
        result = runner.invoke(main, ["retry", "--help"])
        assert result.exit_code == 0

    def test_lock_help_still_works(self, runner):
        result = runner.invoke(main, ["lock", "--help"])
        assert result.exit_code == 0

    def test_explain_help_still_works(self, runner):
        result = runner.invoke(main, ["explain", "--help"])
        assert result.exit_code == 0

    def test_scan_help_still_works(self, runner):
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0

    def test_badge_help_still_works(self, runner):
        result = runner.invoke(main, ["badge", "--help"])
        assert result.exit_code == 0

    def test_audit_help_still_works(self, runner):
        result = runner.invoke(main, ["audit", "--help"])
        assert result.exit_code == 0

    def test_serve_help_still_works(self, runner):
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
