"""Configuration loader for Nightjar.

Loads .env for API keys (via python-dotenv) and nightjar.toml for
project settings. Provides model resolution with precedence:
CLI flag > NIGHTJAR_MODEL env var > nightjar.toml > hardcoded default.

Reference: [REF-T16] litellm — all LLM calls are model-agnostic
Architecture: docs/ARCHITECTURE.md Section 5 (Model Selection)
"""

import os
from pathlib import Path
from typing import Optional

# Default model — used as the final fallback when no env var or config is present
DEFAULT_MODEL = "claude-sonnet-4-6"

# Default config matching nightjar.toml schema
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
    """Load .env + nightjar.toml. Returns merged config dict.

    1. Loads .env file (if present) into os.environ for API keys
    2. Loads nightjar.toml (if present) for project settings
    3. Falls back to DEFAULT_CONFIG if no toml file found
    """
    root = Path(project_root)

    # Load .env for API keys (NIGHTJAR_MODEL, provider keys, etc.)
    env_path = root / ".env"
    if env_path.exists():
        _load_dotenv_simple(env_path)

    # Load nightjar.toml for project settings
    toml_path = root / "nightjar.toml"
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

    Priority: cli_model > NIGHTJAR_MODEL env var > config default > hardcoded default.
    All LLM calls go through litellm [REF-T16] — never call provider APIs directly.
    """
    if cli_model:
        return cli_model

    env_model = os.environ.get("NIGHTJAR_MODEL")
    if env_model:
        return env_model

    if config:
        return config.get("card", {}).get("default_model", DEFAULT_MODEL)

    return DEFAULT_MODEL


def get_specs_dir(config: dict) -> str:
    """Get the specs directory from config."""
    return config.get("paths", {}).get("specs", ".card/")


# Ordered list of env vars that litellm accepts as provider API keys.
# Checked in priority order: whichever is set first wins.
# Source: litellm/utils.py get_api_key() + validate_environment().
_KNOWN_API_KEY_VARS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "COHERE_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "REPLICATE_API_KEY",
    "HUGGINGFACE_API_KEY",
    "AZURE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "BEDROCK_ACCESS_KEY_ID",
    "VERTEX_PROJECT",
)


def require_llm_api_key() -> None:
    """Raise a clean error if no LLM provider API key is configured.

    Must be called before the first litellm.completion() call in any
    command that requires LLM access.  Prevents litellm from hanging
    indefinitely when no key is present (observed on Python 3.14).

    Raises:
        SystemExit(4): EXIT_LLM_ERROR — with a human-readable message
            listing the env vars that can be set to fix the problem.
    """
    # Also honour a .env file that load_config() may not have loaded yet
    # (e.g. when called early from a module-level guard).
    _maybe_load_dotenv()

    for var in _KNOWN_API_KEY_VARS:
        if os.environ.get(var, "").strip():
            return  # At least one key is present — proceed.

    import sys

    print(
        "Error: no LLM API key found.\n"
        "Set one of the following environment variables before running:\n"
        "  ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, "
        "GEMINI_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, …\n"
        "Or add it to a .env file in the project root.\n"
        "See: https://nightjar.dev/docs/models",
        file=sys.stderr,
    )
    sys.exit(4)  # EXIT_LLM_ERROR


def _maybe_load_dotenv() -> None:
    """Load .env from the current working directory if it exists."""
    env_path = Path(".env")
    if env_path.exists():
        _load_dotenv_simple(env_path)
