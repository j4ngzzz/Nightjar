"""hook_installer — auto-configure verification hooks for coding agents.

Installs Nightjar verification hooks into Claude Code, Cursor, Windsurf,
and Kiro without touching any config key that Nightjar did not write.

Public API:
    detect_available_agents(project_dir) -> list[str]
    install_hook(target, cwd, *, force=False) -> InstallResult
    remove_hook(target, cwd) -> RemoveResult
    list_hooks(cwd) -> list[HookStatus]

Internal helpers:
    _atomic_write(path, data) -> None
    _merge_claude_code(existing) -> tuple[dict, bool]
    _merge_cursor(existing) -> tuple[dict, bool]
    _merge_mcp_server(existing) -> tuple[dict, bool]

Safety invariants (enforced throughout):
  1. Never delete any key in a config that Nightjar did not write.
  2. Never overwrite an existing nightjar key without force=True.
  3. Always validate existing config parses as JSON before writing.
  4. If the file has a syntax error, abort with warning — never overwrite.
  5. All file writes are atomic: write to .tmp then os.replace().

Config paths:
  - claude-code  : {cwd}/.claude/settings.json  (project-scoped)
  - cursor       : {cwd}/.cursor/settings.json
  - windsurf     : ~/.codeium/windsurf/mcp_config.json  (global — Windsurf
                   MCP config is always global, not project-local)
  - kiro         : {cwd}/.kiro/settings/mcp.json

Open task: Windsurf MCP config path (~/.codeium/windsurf/mcp_config.json) is
the documented path as of Windsurf 1.x. If Windsurf changes this path in a
future release, update _config_path_for("windsurf", cwd). Detection uses the
presence of .windsurf/ in the project dir as a proxy for Windsurf usage.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path

# ── Public constants ─────────────────────────────────────────────────────────

SUPPORTED_TARGETS: list[str] = ["claude-code", "cursor", "windsurf", "kiro"]

# Sentinel string used to detect existing Nightjar installations.
# Searched as a substring in command strings (claude-code) and as a dict key.
NIGHTJAR_HOOK_MARKER: str = "nightjar-verify"

# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class InstallResult:
    """Result returned by install_hook()."""
    target: str
    config_path: Path
    installed: bool   # True = we wrote to the file; False = no-op or error
    message: str


@dataclass
class RemoveResult:
    """Result returned by remove_hook()."""
    target: str
    removed: bool     # True = we removed nightjar's entry; False = wasn't there
    message: str


@dataclass
class HookStatus:
    """One row in the output of list_hooks()."""
    target: str
    config_path: Path
    installed: bool   # True = nightjar hook/key is present in config


# ── Hook payload definitions ─────────────────────────────────────────────────

# PostToolUse entry appended to .claude/settings.json
_CLAUDE_HOOK_ENTRY: dict = {
    "matcher": "Write|Edit|MultiEdit",
    "hooks": [
        {
            "type": "command",
            "command": "nightjar verify --fast --format=json 2>/dev/null || true",
        }
    ],
}

# Cursor extension namespace block
_CURSOR_CONFIG: dict = {
    "afterFileEdit": {
        "command": "nightjar verify --fast --format=json",
        "fileFilter": "**/*.py",
        "timeout": 60,
    }
}

# MCP server entry shared by Windsurf and Kiro
_MCP_SERVER_ENTRY: dict = {
    "command": "nightjar",
    "args": ["mcp"],
    "description": "Nightjar formal verification — verify_contract, get_violations, suggest_fix",
}


# ── Config path resolution ────────────────────────────────────────────────────


def _config_path_for(target: str, cwd: Path) -> Path:
    """Return the canonical config file path for *target*."""
    if target == "claude-code":
        return cwd / ".claude" / "settings.json"
    if target == "cursor":
        return cwd / ".cursor" / "settings.json"
    if target == "windsurf":
        # Windsurf stores MCP config globally, not per-project.
        return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    if target == "kiro":
        return cwd / ".kiro" / "settings" / "mcp.json"
    raise ValueError(f"Unsupported target: {target!r}. Choose from {SUPPORTED_TARGETS}")


# ── Atomic write ──────────────────────────────────────────────────────────────


def _atomic_write(path: Path, data: str) -> None:
    """Write *data* to *path* atomically via a .tmp intermediary.

    Creates parent directories if they do not exist. On POSIX, os.replace()
    is atomic. On Windows it is not guaranteed atomic but is still safer than
    a plain write because the original file is only replaced after the new
    content has been fully flushed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # Clean up the .tmp file if anything went wrong before replace.
        if tmp.exists():
            tmp.unlink(missing_errors=True)
        raise


# ── Merge helpers (each returns (new_dict, was_changed)) ─────────────────────


def _merge_claude_code(existing: dict) -> tuple[dict, bool]:
    """Merge the Nightjar PostToolUse hook into Claude Code settings.

    Idempotent: if any entry under hooks.PostToolUse already contains the
    string "nightjar" in its command, returns (existing, False).

    Invariant: all pre-existing entries are preserved; the nightjar entry is
    appended at the end of the PostToolUse array.
    """
    settings = copy.deepcopy(existing)

    hooks_section = settings.setdefault("hooks", {})
    post_tool_use = hooks_section.setdefault("PostToolUse", [])

    # Check for existing installation — search all command strings.
    for entry in post_tool_use:
        for hook in entry.get("hooks", []):
            if "nightjar" in hook.get("command", ""):
                return settings, False  # already installed — invariant 2

    # Not installed — append a deep copy so the module-level constant is
    # never mutated through the returned dict.
    post_tool_use.append(copy.deepcopy(_CLAUDE_HOOK_ENTRY))
    return settings, True


def _merge_cursor(existing: dict) -> tuple[dict, bool]:
    """Merge the Nightjar afterFileEdit hook into Cursor settings.

    Uses the top-level "nightjar" key as the Nightjar namespace. Idempotent:
    if the key already exists, returns (existing, False).
    """
    settings = copy.deepcopy(existing)

    if "nightjar" in settings:
        return settings, False  # already installed — invariant 2

    # Deep copy so the module-level constant cannot be mutated by callers.
    settings["nightjar"] = copy.deepcopy(_CURSOR_CONFIG)
    return settings, True


def _merge_mcp_server(existing: dict) -> tuple[dict, bool]:
    """Merge the Nightjar MCP server entry into a mcpServers config dict.

    Used for both Windsurf (~/.codeium/windsurf/mcp_config.json) and Kiro
    (.kiro/settings/mcp.json). Idempotent: if mcpServers.nightjar already
    exists, returns (existing, False).

    All other mcpServers keys are never touched — invariant 1.
    """
    settings = copy.deepcopy(existing)

    mcp_servers = settings.setdefault("mcpServers", {})

    if "nightjar" in mcp_servers:
        return settings, False  # already installed — invariant 2

    # Deep copy so the module-level constant cannot be mutated by callers.
    mcp_servers["nightjar"] = copy.deepcopy(_MCP_SERVER_ENTRY)
    return settings, True


# ── Installation detection ────────────────────────────────────────────────────


def _is_installed(target: str, config_path: Path) -> bool:
    """Return True if Nightjar's hook/key is present in the config at *path*."""
    if not config_path.exists():
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if target == "claude-code":
        for entry in data.get("hooks", {}).get("PostToolUse", []):
            for hook in entry.get("hooks", []):
                if "nightjar" in hook.get("command", ""):
                    return True
        return False

    if target == "cursor":
        return "nightjar" in data

    if target in ("windsurf", "kiro"):
        return "nightjar" in data.get("mcpServers", {})

    return False


# ── Public API ────────────────────────────────────────────────────────────────


def detect_available_agents(project_dir: Path) -> list[str]:
    """Return the subset of SUPPORTED_TARGETS whose agent dir exists in *project_dir*.

    Detection uses the presence of the agent's project-local config directory:
      - claude-code → .claude/
      - cursor      → .cursor/
      - windsurf    → .windsurf/   (NOTE: actual MCP config is global)
      - kiro        → .kiro/

    This is a heuristic — the directory existing means the user has already
    configured that agent for this project.
    """
    agent_dirs = {
        "claude-code": ".claude",
        "cursor": ".cursor",
        "windsurf": ".windsurf",
        "kiro": ".kiro",
    }
    return [
        target
        for target, dirname in agent_dirs.items()
        if (project_dir / dirname).is_dir()
    ]


def install_hook(
    target: str,
    cwd: Path,
    *,
    force: bool = False,
) -> InstallResult:
    """Install the Nightjar verification hook for *target* in *cwd*.

    Args:
        target: One of SUPPORTED_TARGETS ("claude-code", "cursor",
                "windsurf", "kiro").
        cwd:    Project root directory. Config paths are resolved relative
                to this (except windsurf, which is always global).
        force:  If True, overwrite an existing Nightjar installation.
                Without force, an already-installed hook is a no-op.

    Returns:
        InstallResult with installed=True if the config was written,
        installed=False if the hook was already present (idempotent) or
        if the operation was aborted due to a config error.

    Safety invariants:
        - Aborts (installed=False) if the existing config is invalid JSON.
        - Never overwrites without force=True when Nightjar is already present.
        - All writes are atomic (.tmp → os.replace).
    """
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target: {target!r}. Choose from {SUPPORTED_TARGETS}")

    config_path = _config_path_for(target, cwd)

    # ── Read existing config (or start from empty dict) ──────────────────────
    existing: dict = {}
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        try:
            existing = json.loads(raw)
        except json.JSONDecodeError:
            # Invariant 4: abort without writing if JSON is invalid.
            return InstallResult(
                target=target,
                config_path=config_path,
                installed=False,
                message=(
                    f"Aborted: {config_path} contains invalid JSON. "
                    "Fix the file manually before installing the Nightjar hook."
                ),
            )

    # ── Idempotency check (invariant 2) ──────────────────────────────────────
    if not force and _is_installed(target, config_path):
        return InstallResult(
            target=target,
            config_path=config_path,
            installed=False,
            message=f"Nightjar hook already installed in {config_path}",
        )

    # ── Merge ─────────────────────────────────────────────────────────────────
    if target == "claude-code":
        if force:
            # Remove existing nightjar entries first so merge adds a fresh one.
            existing = _remove_nightjar_from_claude_code(existing)
        new_settings, changed = _merge_claude_code(existing)
    elif target == "cursor":
        if force:
            existing.pop("nightjar", None)
        new_settings, changed = _merge_cursor(existing)
    elif target in ("windsurf", "kiro"):
        if force:
            existing.get("mcpServers", {}).pop("nightjar", None)
        new_settings, changed = _merge_mcp_server(existing)
    else:
        raise ValueError(f"Unsupported target: {target!r}")

    if not changed:
        # Merge function determined already installed (shouldn't normally reach
        # here after the _is_installed check, but be defensive).
        return InstallResult(
            target=target,
            config_path=config_path,
            installed=False,
            message=f"Nightjar hook already installed in {config_path}",
        )

    # ── Atomic write (invariant 5) ────────────────────────────────────────────
    _atomic_write(config_path, json.dumps(new_settings, indent=2))

    return InstallResult(
        target=target,
        config_path=config_path,
        installed=True,
        message=f"Nightjar hook installed → {config_path}",
    )


def remove_hook(target: str, cwd: Path) -> RemoveResult:
    """Remove only Nightjar's entries from the config for *target*.

    Only removes keys/entries that Nightjar itself wrote. All other config
    content is preserved (invariant 1).

    Returns:
        RemoveResult with removed=True if an entry was found and removed,
        removed=False if nothing was found to remove.
    """
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target: {target!r}. Choose from {SUPPORTED_TARGETS}")

    config_path = _config_path_for(target, cwd)

    if not config_path.exists() or not _is_installed(target, config_path):
        return RemoveResult(
            target=target,
            removed=False,
            message=f"Nightjar hook not found in {config_path}",
        )

    raw = config_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return RemoveResult(
            target=target,
            removed=False,
            message=(
                f"Aborted: {config_path} contains invalid JSON. "
                "Fix the file manually."
            ),
        )

    if target == "claude-code":
        data = _remove_nightjar_from_claude_code(data)
    elif target == "cursor":
        data.pop("nightjar", None)
    elif target in ("windsurf", "kiro"):
        data.get("mcpServers", {}).pop("nightjar", None)

    _atomic_write(config_path, json.dumps(data, indent=2))

    return RemoveResult(
        target=target,
        removed=True,
        message=f"Nightjar hook removed from {config_path}",
    )


def list_hooks(cwd: Path) -> list[HookStatus]:
    """Return the installation status of the Nightjar hook for all targets.

    Checks the config file for each supported target and reports whether
    Nightjar's hook/key is present. Does not modify any file.

    The config_path in each HookStatus is the canonical path for that target,
    regardless of whether the file exists.
    """
    results: list[HookStatus] = []
    for target in SUPPORTED_TARGETS:
        config_path = _config_path_for(target, cwd)
        results.append(
            HookStatus(
                target=target,
                config_path=config_path,
                installed=_is_installed(target, config_path),
            )
        )
    return results


# ── Private removal helpers ───────────────────────────────────────────────────


def _remove_nightjar_from_claude_code(data: dict) -> dict:
    """Return *data* with all Nightjar PostToolUse entries removed.

    Preserves all other hooks and config keys untouched (invariant 1).
    """
    data = copy.deepcopy(data)
    post_tool_use = data.get("hooks", {}).get("PostToolUse", [])
    filtered = [
        entry for entry in post_tool_use
        if not any("nightjar" in h.get("command", "") for h in entry.get("hooks", []))
    ]
    if "hooks" in data and "PostToolUse" in data["hooks"]:
        data["hooks"]["PostToolUse"] = filtered
    return data
