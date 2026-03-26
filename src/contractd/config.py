"""Configuration loader for CARD.

Loads .env for API keys (via python-dotenv) and contractd.toml for
project settings. Provides model resolution with precedence:
CLI flag > CARD_MODEL env var > contractd.toml > hardcoded default.

Reference: [REF-T16] litellm — all LLM calls are model-agnostic
Architecture: docs/ARCHITECTURE.md Section 5 (Model Selection)
"""

import os
from pathlib import Path
from typing import Optional


# Default config matching contractd.toml schema
DEFAULT_CONFIG: dict = {
    "card": {
        "version": "1.0",
        "default_target": "py",
        "default_model": "claude-sonnet-4-6",
        "max_retries": 5,
        "verification_timeout": 30,
    },
    "paths": {
        "specs": ".card/",
        "dist": "dist/",
        "audit": ".card/audit/",
        "cache": ".card/cache/",
    },
}


def load_config(project_root: str = ".") -> dict:
    """Load .env + contractd.toml. Returns merged config dict.

    1. Loads .env file (if present) into os.environ for API keys
    2. Loads contractd.toml (if present) for project settings
    3. Falls back to DEFAULT_CONFIG if no toml file found
    """
    root = Path(project_root)

    # Load .env for API keys (CARD_MODEL, provider keys, etc.)
    env_path = root / ".env"
    if env_path.exists():
        _load_dotenv_simple(env_path)

    # Load contractd.toml for project settings
    toml_path = root / "contractd.toml"
    if toml_path.exists():
        import tomllib

        with open(toml_path, "rb") as f:
            return tomllib.load(f)

    return DEFAULT_CONFIG.copy()


def _load_dotenv_simple(env_path: Path) -> None:
    """Load a .env file into os.environ. Minimal implementation.

    Handles KEY=VALUE lines, ignores comments and blank lines.
    Uses python-dotenv if available, falls back to manual parsing.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        # Fallback: manual .env parsing when python-dotenv not installed
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    os.environ[key] = value


def get_model(
    cli_model: Optional[str] = None,
    config: Optional[dict] = None,
) -> str:
    """Resolve LLM model name with precedence.

    Priority: cli_model > CARD_MODEL env var > config default > hardcoded default.
    All LLM calls go through litellm [REF-T16] — never call provider APIs directly.
    """
    if cli_model:
        return cli_model

    env_model = os.environ.get("CARD_MODEL")
    if env_model:
        return env_model

    if config:
        return config.get("card", {}).get("default_model", "deepseek/deepseek-chat")

    return "deepseek/deepseek-chat"


def get_specs_dir(config: dict) -> str:
    """Get the specs directory from config."""
    return config.get("paths", {}).get("specs", ".card/")
