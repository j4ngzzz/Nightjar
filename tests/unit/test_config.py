"""Tests for config loader module.

Reference: [REF-T16] litellm model-agnostic interface
Tests: .env loading, nightjar.toml loading, model resolution
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_load_config_returns_defaults_when_no_files(tmp_path, monkeypatch):
    """When no .env or nightjar.toml exist, return sensible defaults."""
    monkeypatch.chdir(tmp_path)
    from nightjar.config import load_config

    config = load_config(str(tmp_path))
    assert isinstance(config, dict)
    assert "card" in config
    assert config["card"]["default_target"] == "py"


def test_load_config_reads_toml(tmp_path, monkeypatch):
    """When nightjar.toml exists, load its values."""
    monkeypatch.chdir(tmp_path)
    toml_content = b'[card]\nversion = "1.0"\ndefault_target = "js"\nmax_retries = 3\n'
    (tmp_path / "nightjar.toml").write_bytes(toml_content)

    from nightjar.config import load_config

    config = load_config(str(tmp_path))
    assert config["card"]["default_target"] == "js"
    assert config["card"]["max_retries"] == 3


def test_load_config_loads_dotenv(tmp_path, monkeypatch):
    """When .env exists, its variables are loaded into os.environ."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("NIGHTJAR_MODEL=test-model-123\nCARD_SECRET=abc\n")
    # Clear any existing value
    monkeypatch.delenv("NIGHTJAR_MODEL", raising=False)
    monkeypatch.delenv("CARD_SECRET", raising=False)

    from nightjar.config import load_config

    load_config(str(tmp_path))
    assert os.environ.get("NIGHTJAR_MODEL") == "test-model-123"
    assert os.environ.get("CARD_SECRET") == "abc"


def test_get_model_cli_flag_takes_precedence():
    """CLI flag > env var > config default."""
    from nightjar.config import get_model

    config = {"card": {"default_model": "config-model"}}
    with patch.dict(os.environ, {"NIGHTJAR_MODEL": "env-model"}):
        assert get_model(cli_model="cli-model", config=config) == "cli-model"


def test_get_model_env_over_config():
    """NIGHTJAR_MODEL env var takes precedence over config."""
    from nightjar.config import get_model

    config = {"card": {"default_model": "config-model"}}
    with patch.dict(os.environ, {"NIGHTJAR_MODEL": "env-model"}):
        assert get_model(config=config) == "env-model"


def test_get_model_falls_back_to_config():
    """When no CLI flag or env var, use config default."""
    from nightjar.config import get_model

    config = {"card": {"default_model": "config-model"}}
    with patch.dict(os.environ, {}, clear=False):
        # Remove NIGHTJAR_MODEL if present
        os.environ.pop("NIGHTJAR_MODEL", None)
        assert get_model(config=config) == "config-model"


def test_get_model_ultimate_default():
    """When nothing is configured, use deepseek/deepseek-chat."""
    from nightjar.config import get_model

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("NIGHTJAR_MODEL", None)
        assert get_model(config={}) == "deepseek/deepseek-chat"


def test_get_specs_dir_from_config():
    """Get specs directory from config."""
    from nightjar.config import get_specs_dir

    config = {"paths": {"specs": "custom/.card/"}}
    assert get_specs_dir(config) == "custom/.card/"


def test_get_specs_dir_default():
    """Default specs directory is .card/."""
    from nightjar.config import get_specs_dir

    assert get_specs_dir({}) == ".card/"
