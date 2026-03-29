"""Tests for AutoResearch hill climbing optimization.

Karpathy's AutoResearch pattern: each run tries ONE variation
(prompt tweak, temperature change, different few-shot selection).
Measures verification pass rate. Keeps if improved, discards if not.

References:
- [REF-P04] AlphaVerus — self-improving loop
- [REF-T26] DSPy — prompt variation strategies (inspiration)
"""

import os
import time
from unittest.mock import patch, MagicMock

import pytest

from nightjar.hill_climb import (
    HillClimbConfig,
    Variation,
    HillClimbResult,
    HillClimber,
    run_hill_climb,
    generate_variation,
)
from nightjar.tracking import TrackingDB
from nightjar.prompts import PromptTemplate, PromptRegistry


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def tracking_db(tmp_dir):
    db = TrackingDB(str(tmp_dir / "tracking.db"))
    db.record_run("payment", "claude-sonnet-4-6", True, [], 0, 0.05)
    db.record_run("payment", "claude-sonnet-4-6", True, [], 0, 0.03)
    db.record_run("auth", "claude-sonnet-4-6", False, [], 2, 0.15)
    return db


@pytest.fixture
def prompt_registry(tmp_dir):
    reg = PromptRegistry(str(tmp_dir / "prompts"))
    reg.register(PromptTemplate(
        name="analyst",
        version=1,
        system_prompt="You are a requirements analyst.",
        user_prompt_template="Analyze: {spec_context}",
        pass_rate=0.67,
        last_optimized=time.time(),
    ))
    return reg


@pytest.fixture
def config(tmp_dir):
    return HillClimbConfig(
        tracking_db_path=str(tmp_dir / "tracking.db"),
        prompt_registry_path=str(tmp_dir / "prompts"),
        target_prompt="analyst",
    )


class TestVariation:
    """Tests for the Variation data class."""

    def test_create_prompt_variation(self):
        v = Variation(
            kind="prompt_tweak",
            description="Added emphasis on edge cases",
            parameter_name="system_prompt",
            original_value="Old prompt",
            new_value="New prompt with edge cases",
        )
        assert v.kind == "prompt_tweak"

    def test_create_temperature_variation(self):
        v = Variation(
            kind="temperature",
            description="Lowered temperature from 0.2 to 0.1",
            parameter_name="temperature",
            original_value="0.2",
            new_value="0.1",
        )
        assert v.kind == "temperature"


class TestHillClimbConfig:
    """Tests for hill climb configuration."""

    def test_create_config(self, tmp_dir):
        config = HillClimbConfig(
            tracking_db_path=str(tmp_dir / "t.db"),
            prompt_registry_path=str(tmp_dir / "p"),
            target_prompt="analyst",
        )
        assert config.target_prompt == "analyst"


class TestHillClimber:
    """Tests for the hill climber."""

    def test_create_climber(self, config):
        climber = HillClimber(config)
        assert climber.config == config

    def test_generate_variation_returns_variation(self, config, prompt_registry):
        climber = HillClimber(config)
        tpl = prompt_registry.get("analyst", version=1)
        variation = climber.generate_variation(tpl)
        assert isinstance(variation, Variation)
        assert variation.kind in ("prompt_tweak", "temperature", "few_shot")

    def test_evaluate_returns_score(self, config, tracking_db, prompt_registry):
        climber = HillClimber(config)
        tpl = prompt_registry.get("analyst", version=1)
        score = climber.evaluate(tpl)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_step_returns_result(self, config, tracking_db, prompt_registry):
        climber = HillClimber(config)
        result = climber.step()
        assert isinstance(result, HillClimbResult)
        assert isinstance(result.accepted, bool)
        assert result.variation is not None

    def test_step_tracks_history(self, config, tracking_db, prompt_registry):
        climber = HillClimber(config)
        climber.step()
        assert len(climber.history) == 1

    def test_multiple_steps(self, config, tracking_db, prompt_registry):
        climber = HillClimber(config)
        for _ in range(3):
            climber.step()
        assert len(climber.history) == 3


class TestRunHillClimb:
    """Tests for the module-level run function."""

    def test_run_hill_climb(self, config, tracking_db, prompt_registry):
        results = run_hill_climb(config, steps=2)
        assert len(results) == 2
        assert all(isinstance(r, HillClimbResult) for r in results)


class TestGenerateVariation:
    """Tests for the generate_variation function."""

    def test_generate_variation_function(self, config, prompt_registry):
        tpl = prompt_registry.get("analyst", version=1)
        variation = generate_variation(config, tpl)
        assert isinstance(variation, Variation)
