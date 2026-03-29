"""Tests for nightjar.hook_installer — auto-configure verification hooks.

TDD: Tests written FIRST before implementation.

Covers: detect_available_agents, install_hook, remove_hook, list_hooks,
        _atomic_write, _merge_claude_code, _merge_cursor, _merge_mcp_server.

Safety invariants under test:
  1. Never delete keys Nightjar did not write.
  2. Never overwrite existing nightjar key without --force.
  3. Validate existing config parses as JSON before writing.
  4. Abort with warning if file has syntax error.
  5. All writes are atomic (.tmp → os.replace).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nightjar.hook_installer import (
    NIGHTJAR_HOOK_MARKER,
    SUPPORTED_TARGETS,
    HookStatus,
    InstallResult,
    RemoveResult,
    _atomic_write,
    _merge_claude_code,
    _merge_cursor,
    _merge_mcp_server,
    detect_available_agents,
    install_hook,
    list_hooks,
    remove_hook,
)


# ── Constants ────────────────────────────────────────────


class TestConstants:
    def test_supported_targets_contains_all_four(self):
        assert set(SUPPORTED_TARGETS) == {"claude-code", "cursor", "windsurf", "kiro"}

    def test_hook_marker_value(self):
        assert NIGHTJAR_HOOK_MARKER == "nightjar-verify"


# ── detect_available_agents ──────────────────────────────


class TestDetectAvailableAgents:
    def test_detect_claude_code_dir(self, tmp_path):
        """Presence of .claude/ signals Claude Code is in use."""
        (tmp_path / ".claude").mkdir()
        result = detect_available_agents(tmp_path)
        assert "claude-code" in result

    def test_detect_cursor_dir(self, tmp_path):
        """Presence of .cursor/ signals Cursor is in use."""
        (tmp_path / ".cursor").mkdir()
        result = detect_available_agents(tmp_path)
        assert "cursor" in result

    def test_detect_windsurf_dir(self, tmp_path):
        """Presence of .windsurf/ signals Windsurf is in use."""
        (tmp_path / ".windsurf").mkdir()
        result = detect_available_agents(tmp_path)
        assert "windsurf" in result

    def test_detect_kiro_dir(self, tmp_path):
        """Presence of .kiro/ signals Kiro is in use."""
        (tmp_path / ".kiro").mkdir()
        result = detect_available_agents(tmp_path)
        assert "kiro" in result

    def test_detect_returns_empty_no_agents(self, tmp_path):
        """Empty project dir returns empty list."""
        result = detect_available_agents(tmp_path)
        assert result == []

    def test_detect_returns_multiple_agents(self, tmp_path):
        """Multiple agent dirs all detected."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".cursor").mkdir()
        result = detect_available_agents(tmp_path)
        assert "claude-code" in result
        assert "cursor" in result

    def test_detect_returns_list(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        result = detect_available_agents(tmp_path)
        assert isinstance(result, list)


# ── _merge_claude_code ───────────────────────────────────


class TestMergeClaudeCode:
    def test_empty_settings_adds_hook(self):
        """Empty settings dict gets a PostToolUse hook appended."""
        new_settings, changed = _merge_claude_code({})
        assert changed is True
        hooks = new_settings["hooks"]["PostToolUse"]
        assert isinstance(hooks, list)
        assert len(hooks) == 1
        cmd = hooks[0]["hooks"][0]["command"]
        assert "nightjar" in cmd

    def test_existing_nightjar_hook_not_duplicated(self):
        """If nightjar already in PostToolUse, returns unchanged=False."""
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit", "hooks": [{"type": "command", "command": "nightjar verify --fast"}]}
                ]
            }
        }
        new_settings, changed = _merge_claude_code(existing)
        assert changed is False
        # Array length unchanged
        assert len(new_settings["hooks"]["PostToolUse"]) == 1

    def test_appends_to_existing_post_tool_use_array(self):
        """Pre-existing entries preserved; nightjar entry appended."""
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Read", "hooks": [{"type": "command", "command": "echo hi"}]}
                ]
            }
        }
        new_settings, changed = _merge_claude_code(existing)
        assert changed is True
        hooks = new_settings["hooks"]["PostToolUse"]
        assert len(hooks) == 2
        # Original entry preserved
        assert hooks[0]["hooks"][0]["command"] == "echo hi"

    def test_other_hook_types_preserved(self):
        """Non-PostToolUse hooks are not touched."""
        existing = {
            "hooks": {
                "PostToolUse": [],
                "PreToolUse": [{"matcher": "*", "hooks": []}],
            }
        }
        new_settings, _ = _merge_claude_code(existing)
        assert "PreToolUse" in new_settings["hooks"]

    def test_matcher_includes_write_edit_multiedit(self):
        """Hook matcher covers Write, Edit, and MultiEdit tool events."""
        new_settings, _ = _merge_claude_code({})
        matcher = new_settings["hooks"]["PostToolUse"][0]["matcher"]
        assert "Write" in matcher
        assert "Edit" in matcher
        assert "MultiEdit" in matcher


# ── _merge_cursor ────────────────────────────────────────


class TestMergeCursor:
    def test_empty_settings_adds_nightjar_key(self):
        new_settings, changed = _merge_cursor({})
        assert changed is True
        assert "nightjar" in new_settings

    def test_nightjar_key_has_required_fields(self):
        new_settings, _ = _merge_cursor({})
        cfg = new_settings["nightjar"]["afterFileEdit"]
        assert "command" in cfg
        assert "nightjar" in cfg["command"]
        assert "fileFilter" in cfg
        assert "timeout" in cfg

    def test_existing_nightjar_key_not_overwritten(self):
        """Already installed → returns unchanged=False."""
        existing = {"nightjar": {"afterFileEdit": {"command": "nightjar verify"}}}
        new_settings, changed = _merge_cursor(existing)
        assert changed is False
        assert new_settings["nightjar"] == existing["nightjar"]

    def test_other_cursor_settings_preserved(self):
        existing = {"editor.fontSize": 14, "theme": "dark"}
        new_settings, _ = _merge_cursor(existing)
        assert new_settings["editor.fontSize"] == 14
        assert new_settings["theme"] == "dark"


# ── _merge_mcp_server ────────────────────────────────────


class TestMergeMcpServer:
    def test_empty_settings_adds_nightjar_server(self):
        new_settings, changed = _merge_mcp_server({})
        assert changed is True
        assert "nightjar" in new_settings["mcpServers"]

    def test_nightjar_server_has_required_fields(self):
        new_settings, _ = _merge_mcp_server({})
        server = new_settings["mcpServers"]["nightjar"]
        assert "command" in server
        assert "args" in server

    def test_existing_nightjar_server_not_overwritten(self):
        existing = {"mcpServers": {"nightjar": {"command": "nightjar", "args": ["mcp"]}}}
        new_settings, changed = _merge_mcp_server(existing)
        assert changed is False

    def test_other_mcp_servers_preserved(self):
        """Third-party MCP servers are never touched."""
        existing = {"mcpServers": {"other-tool": {"command": "other", "args": []}}}
        new_settings, _ = _merge_mcp_server(existing)
        assert "other-tool" in new_settings["mcpServers"]
        assert "nightjar" in new_settings["mcpServers"]


# ── _atomic_write ────────────────────────────────────────


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "settings.json"
        _atomic_write(target, '{"key": "value"}')
        assert target.exists()
        assert json.loads(target.read_text()) == {"key": "value"}

    def test_atomic_write_replaces_existing(self, tmp_path):
        target = tmp_path / "settings.json"
        target.write_text('{"old": true}')
        _atomic_write(target, '{"new": true}')
        assert json.loads(target.read_text()) == {"new": True}

    def test_atomic_write_no_tmp_file_left(self, tmp_path):
        """After successful write, no .tmp file remains."""
        target = tmp_path / "settings.json"
        _atomic_write(target, '{"x": 1}')
        tmp_file = Path(str(target) + ".tmp")
        assert not tmp_file.exists()

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        """Parent directories are created if they don't exist."""
        target = tmp_path / "nested" / "dir" / "settings.json"
        _atomic_write(target, '{}')
        assert target.exists()


# ── install_hook — claude-code ───────────────────────────


class TestInstallHookClaudeCode:
    def test_install_claude_code_creates_settings(self, tmp_path):
        """No existing .claude/settings.json → creates it with correct JSON."""
        result = install_hook("claude-code", tmp_path)
        assert isinstance(result, InstallResult)
        assert result.installed is True
        assert result.target == "claude-code"
        config_path = tmp_path / ".claude" / "settings.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        hooks = data["hooks"]["PostToolUse"]
        assert any("nightjar" in h["hooks"][0]["command"] for h in hooks)

    def test_install_claude_code_merges_existing(self, tmp_path):
        """Existing settings.json preserved; nightjar hook appended."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        settings_path = config_dir / "settings.json"
        existing = {
            "editor": {"wordWrap": "on"},
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Read", "hooks": [{"type": "command", "command": "echo test"}]}
                ]
            }
        }
        settings_path.write_text(json.dumps(existing))
        result = install_hook("claude-code", tmp_path)
        assert result.installed is True
        data = json.loads(settings_path.read_text())
        # Original entry preserved
        assert data["editor"]["wordWrap"] == "on"
        # Nightjar appended
        commands = [h["hooks"][0]["command"] for h in data["hooks"]["PostToolUse"]]
        assert any("nightjar" in cmd for cmd in commands)
        # Original entry not removed
        assert any("echo test" in cmd for cmd in commands)

    def test_install_claude_code_idempotent(self, tmp_path):
        """Second install call returns installed=False (already installed)."""
        install_hook("claude-code", tmp_path)
        result2 = install_hook("claude-code", tmp_path)
        assert result2.installed is False
        assert "already" in result2.message.lower()

    def test_install_claude_code_config_path_in_result(self, tmp_path):
        result = install_hook("claude-code", tmp_path)
        assert result.config_path == tmp_path / ".claude" / "settings.json"

    def test_install_claude_code_force_overwrites(self, tmp_path):
        """--force flag re-installs even if already present."""
        install_hook("claude-code", tmp_path)
        result2 = install_hook("claude-code", tmp_path, force=True)
        assert result2.installed is True


# ── install_hook — cursor ────────────────────────────────


class TestInstallHookCursor:
    def test_install_cursor_creates_file(self, tmp_path):
        """No existing .cursor/settings.json → creates it."""
        result = install_hook("cursor", tmp_path)
        assert result.installed is True
        config_path = tmp_path / ".cursor" / "settings.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "nightjar" in data

    def test_install_cursor_idempotent(self, tmp_path):
        """Second install → installed=False, message says already installed."""
        install_hook("cursor", tmp_path)
        result2 = install_hook("cursor", tmp_path)
        assert result2.installed is False
        assert "already" in result2.message.lower()

    def test_install_cursor_preserves_existing_keys(self, tmp_path):
        config_dir = tmp_path / ".cursor"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        config_path.write_text(json.dumps({"theme": "solarized"}))
        install_hook("cursor", tmp_path)
        data = json.loads(config_path.read_text())
        assert data["theme"] == "solarized"
        assert "nightjar" in data


# ── install_hook — windsurf ──────────────────────────────


class TestInstallHookWindsurf:
    def test_install_windsurf_writes_to_global_path(self, tmp_path):
        """Windsurf config is written to ~/.codeium/windsurf/mcp_config.json."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        with patch.dict(os.environ, {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}):
            with patch("pathlib.Path.home", return_value=fake_home):
                result = install_hook("windsurf", tmp_path)
        assert result.installed is True
        expected = fake_home / ".codeium" / "windsurf" / "mcp_config.json"
        assert expected.exists()

    def test_install_windsurf_idempotent(self, tmp_path):
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            install_hook("windsurf", tmp_path)
            result2 = install_hook("windsurf", tmp_path)
        assert result2.installed is False


# ── install_hook — kiro ──────────────────────────────────


class TestInstallHookKiro:
    def test_install_kiro_creates_file_with_parent_dirs(self, tmp_path):
        """Kiro config at .kiro/settings/mcp.json; parent dirs created."""
        result = install_hook("kiro", tmp_path)
        assert result.installed is True
        config_path = tmp_path / ".kiro" / "settings" / "mcp.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "nightjar" in data["mcpServers"]

    def test_install_kiro_idempotent(self, tmp_path):
        install_hook("kiro", tmp_path)
        result2 = install_hook("kiro", tmp_path)
        assert result2.installed is False


# ── install_hook — invalid JSON ──────────────────────────


class TestInstallHookInvalidJson:
    def test_invalid_json_aborts_claude_code(self, tmp_path):
        """Corrupt settings.json → abort without writing, return installed=False."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text("{this is not json!!!}")
        result = install_hook("claude-code", tmp_path)
        assert result.installed is False
        assert "invalid" in result.message.lower() or "syntax" in result.message.lower() or "json" in result.message.lower()
        # File should NOT be overwritten
        assert (config_dir / "settings.json").read_text() == "{this is not json!!!}"

    def test_invalid_json_aborts_cursor(self, tmp_path):
        config_dir = tmp_path / ".cursor"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text("not json at all")
        result = install_hook("cursor", tmp_path)
        assert result.installed is False

    def test_invalid_json_no_tmp_file_left(self, tmp_path):
        """On invalid JSON abort, no .tmp file is left on disk."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        config_path.write_text("{bad json")
        install_hook("claude-code", tmp_path)
        tmp_file = Path(str(config_path) + ".tmp")
        assert not tmp_file.exists()


# ── install_hook — force flag ────────────────────────────


class TestForceFlag:
    def test_force_flag_overwrites_existing_nightjar_entry(self, tmp_path):
        """force=True re-installs even if nightjar hook already present."""
        install_hook("claude-code", tmp_path)
        result = install_hook("claude-code", tmp_path, force=True)
        assert result.installed is True

    def test_force_flag_cursor(self, tmp_path):
        install_hook("cursor", tmp_path)
        result = install_hook("cursor", tmp_path, force=True)
        assert result.installed is True

    def test_without_force_idempotent_returns_false(self, tmp_path):
        install_hook("claude-code", tmp_path)
        result = install_hook("claude-code", tmp_path, force=False)
        assert result.installed is False


# ── remove_hook ──────────────────────────────────────────


class TestRemoveHook:
    def test_remove_claude_code(self, tmp_path):
        """Install then remove → nightjar entry gone, other entries preserved."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        existing = {
            "editor": {"wordWrap": "on"},
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Read", "hooks": [{"type": "command", "command": "echo keep"}]}
                ]
            }
        }
        config_path.write_text(json.dumps(existing))
        install_hook("claude-code", tmp_path)
        result = remove_hook("claude-code", tmp_path)
        assert isinstance(result, RemoveResult)
        assert result.removed is True
        data = json.loads(config_path.read_text())
        # Nightjar entry gone
        commands = [
            h["hooks"][0]["command"]
            for h in data.get("hooks", {}).get("PostToolUse", [])
        ]
        assert not any("nightjar" in cmd for cmd in commands)
        # Other entry preserved
        assert any("echo keep" in cmd for cmd in commands)

    def test_remove_cursor(self, tmp_path):
        install_hook("cursor", tmp_path)
        result = remove_hook("cursor", tmp_path)
        assert result.removed is True
        config_path = tmp_path / ".cursor" / "settings.json"
        data = json.loads(config_path.read_text())
        assert "nightjar" not in data

    def test_remove_cursor_preserves_other_keys(self, tmp_path):
        config_dir = tmp_path / ".cursor"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(json.dumps({"theme": "dark"}))
        install_hook("cursor", tmp_path)
        remove_hook("cursor", tmp_path)
        data = json.loads((config_dir / "settings.json").read_text())
        assert data.get("theme") == "dark"

    def test_remove_when_not_installed_returns_removed_false(self, tmp_path):
        result = remove_hook("claude-code", tmp_path)
        assert result.removed is False
        assert "not installed" in result.message.lower() or "not found" in result.message.lower()

    def test_remove_kiro(self, tmp_path):
        install_hook("kiro", tmp_path)
        result = remove_hook("kiro", tmp_path)
        assert result.removed is True
        config_path = tmp_path / ".kiro" / "settings" / "mcp.json"
        data = json.loads(config_path.read_text())
        assert "nightjar" not in data.get("mcpServers", {})

    def test_remove_kiro_preserves_other_mcp_servers(self, tmp_path):
        """Other MCP servers in kiro config are never touched."""
        config_dir = tmp_path / ".kiro" / "settings"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "mcp.json"
        config_path.write_text(json.dumps({
            "mcpServers": {"other-tool": {"command": "other", "args": []}}
        }))
        install_hook("kiro", tmp_path)
        remove_hook("kiro", tmp_path)
        data = json.loads(config_path.read_text())
        assert "other-tool" in data["mcpServers"]


# ── list_hooks ───────────────────────────────────────────


class TestListHooks:
    def test_list_hooks_returns_list_of_hook_status(self, tmp_path):
        result = list_hooks(tmp_path)
        assert isinstance(result, list)
        assert all(isinstance(h, HookStatus) for h in result)

    def test_list_hooks_shows_installed(self, tmp_path):
        """After install, list_hooks shows INSTALLED for that target."""
        install_hook("claude-code", tmp_path)
        hooks = list_hooks(tmp_path)
        claude_status = next(h for h in hooks if h.target == "claude-code")
        assert claude_status.installed is True

    def test_list_hooks_shows_not_installed(self, tmp_path):
        hooks = list_hooks(tmp_path)
        for hook in hooks:
            assert hook.installed is False

    def test_list_hooks_shows_all_four_targets(self, tmp_path):
        hooks = list_hooks(tmp_path)
        targets = {h.target for h in hooks}
        assert targets == set(SUPPORTED_TARGETS)

    def test_list_hooks_cursor_installed(self, tmp_path):
        install_hook("cursor", tmp_path)
        hooks = list_hooks(tmp_path)
        cursor_status = next(h for h in hooks if h.target == "cursor")
        assert cursor_status.installed is True

    def test_list_hooks_installed_then_removed(self, tmp_path):
        install_hook("cursor", tmp_path)
        remove_hook("cursor", tmp_path)
        hooks = list_hooks(tmp_path)
        cursor_status = next(h for h in hooks if h.target == "cursor")
        assert cursor_status.installed is False

    def test_list_hooks_config_path_populated(self, tmp_path):
        hooks = list_hooks(tmp_path)
        for h in hooks:
            assert h.config_path is not None
            assert isinstance(h.config_path, Path)


# ── Module-level constant mutation protection ────────────


class TestConstantMutationProtection:
    """Merge helpers must not mutate module-level hook payload constants."""

    def test_merge_claude_code_does_not_mutate_hook_entry(self):
        """Returned settings dict is independent of _CLAUDE_HOOK_ENTRY."""
        from nightjar.hook_installer import _CLAUDE_HOOK_ENTRY
        original_keys = set(_CLAUDE_HOOK_ENTRY.keys())
        new_settings, _ = _merge_claude_code({})
        # Mutate the returned dict
        new_settings["hooks"]["PostToolUse"][0]["POISON"] = True
        # Constant must be unaffected
        assert "POISON" not in _CLAUDE_HOOK_ENTRY
        assert set(_CLAUDE_HOOK_ENTRY.keys()) == original_keys

    def test_merge_cursor_does_not_mutate_cursor_config(self):
        """Returned settings dict is independent of _CURSOR_CONFIG."""
        from nightjar.hook_installer import _CURSOR_CONFIG
        original_keys = set(_CURSOR_CONFIG.keys())
        new_settings, _ = _merge_cursor({})
        new_settings["nightjar"]["POISON"] = True
        assert "POISON" not in _CURSOR_CONFIG
        assert set(_CURSOR_CONFIG.keys()) == original_keys

    def test_merge_mcp_server_does_not_mutate_mcp_entry(self):
        """Returned settings dict is independent of _MCP_SERVER_ENTRY."""
        from nightjar.hook_installer import _MCP_SERVER_ENTRY
        original_keys = set(_MCP_SERVER_ENTRY.keys())
        new_settings, _ = _merge_mcp_server({})
        new_settings["mcpServers"]["nightjar"]["POISON"] = True
        assert "POISON" not in _MCP_SERVER_ENTRY
        assert set(_MCP_SERVER_ENTRY.keys()) == original_keys


# ── install_hook — unsupported target ────────────────────


class TestUnsupportedTarget:
    def test_unsupported_target_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported target"):
            install_hook("vscode", tmp_path)

    def test_remove_unsupported_target_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported target"):
            remove_hook("vscode", tmp_path)
