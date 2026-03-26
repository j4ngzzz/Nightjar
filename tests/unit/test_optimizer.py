"""Tests for DSPy SIMBA prompt optimization.

Uses DSPy SIMBA to optimize the Analyst/Formalizer/Coder prompts.
Metric: verification pass rate on a held-out set of specs.

References:
- [REF-T26] DSPy — SIMBA optimizer for prompt optimization
- [REF-C03] Analyst → Formalizer → Coder pipeline prompts
- [REF-P04] AlphaVerus — self-improving loop
"""

import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

from nightjar.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    PromptOptimizer,
    run_optimization,
    evaluate_prompt,
)
from nightjar.tracking import TrackingDB
from nightjar.prompts import PromptTemplate, PromptRegistry


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def tracking_db(tmp_dir):
    db = TrackingDB(str(tmp_dir / "tracking.db"))
    # Seed with some runs
    db.record_run("payment", "claude-sonnet-4-6", True, [], 0, 0.05)
    db.record_run("payment", "claude-sonnet-4-6", False, [], 2, 0.15)
    db.record_run("auth", "claude-sonnet-4-6", True, [], 0, 0.03)
    return db


@pytest.fixture
def prompt_registry(tmp_dir):
    reg = PromptRegistry(str(tmp_dir / "prompts"))
    for name in ["analyst", "formalizer", "coder"]:
        reg.register(PromptTemplate(
            name=name,
            version=1,
            system_prompt=f"You are a {name}.",
            user_prompt_template=f"Do {name} work on: {{spec_context}}",
            pass_rate=0.67,
            last_optimized=time.time(),
        ))
    return reg


@pytest.fixture
def config(tmp_dir, tracking_db, prompt_registry):
    return OptimizationConfig(
        tracking_db_path=str(tmp_dir / "tracking.db"),
        prompt_registry_path=str(tmp_dir / "prompts"),
        target_prompt="analyst",
        max_iterations=3,
        improvement_threshold=0.01,
    )


class TestOptimizationConfig:
    """Tests for optimization configuration."""

    def test_create_config(self, tmp_dir):
        config = OptimizationConfig(
            tracking_db_path=str(tmp_dir / "t.db"),
            prompt_registry_path=str(tmp_dir / "p"),
            target_prompt="analyst",
            max_iterations=5,
            improvement_threshold=0.02,
        )
        assert config.target_prompt == "analyst"
        assert config.max_iterations == 5

    def test_default_values(self, tmp_dir):
        config = OptimizationConfig(
            tracking_db_path=str(tmp_dir / "t.db"),
            prompt_registry_path=str(tmp_dir / "p"),
            target_prompt="analyst",
        )
        assert config.max_iterations == 10
        assert config.improvement_threshold == 0.01


class TestPromptOptimizer:
    """Tests for the prompt optimizer."""

    def test_create_optimizer(self, config):
        optimizer = PromptOptimizer(config)
        assert optimizer.config == config

    def test_evaluate_prompt_returns_score(self, config, prompt_registry):
        optimizer = PromptOptimizer(config)
        tpl = prompt_registry.get("analyst", version=1)
        # evaluate_prompt uses tracking DB pass rate as proxy metric
        score = optimizer.evaluate_prompt(tpl)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @patch("nightjar.optimizer._call_llm_for_variation")
    def test_optimize_creates_new_version(self, mock_llm, config, prompt_registry):
        """Optimization should create a new version of the template."""
        mock_llm.return_value = "You are an improved analyst. Be more precise."
        optimizer = PromptOptimizer(config)
        result = optimizer.optimize()

        assert isinstance(result, OptimizationResult)
        assert result.original_version == 1
        assert result.iterations_run >= 0

    @patch("nightjar.optimizer._call_llm_for_variation")
    def test_optimize_returns_result_with_scores(self, mock_llm, config):
        mock_llm.return_value = "Improved system prompt."
        optimizer = PromptOptimizer(config)
        result = optimizer.optimize()

        assert hasattr(result, "original_score")
        assert hasattr(result, "best_score")
        assert isinstance(result.original_score, float)
        assert isinstance(result.best_score, float)

    @patch("nightjar.optimizer._call_llm_for_variation")
    def test_optimize_respects_max_iterations(self, mock_llm, config):
        mock_llm.return_value = "Try this."
        config.max_iterations = 2
        optimizer = PromptOptimizer(config)
        result = optimizer.optimize()
        assert result.iterations_run <= 2


class TestEvaluatePrompt:
    """Tests for the evaluate_prompt function."""

    def test_evaluate_uses_tracking_db(self, config, prompt_registry):
        tpl = prompt_registry.get("analyst", version=1)
        score = evaluate_prompt(config, tpl)
        # With 2 pass out of 3 runs, base rate is ~0.67
        assert 0.0 <= score <= 1.0


class TestRunOptimization:
    """Tests for the module-level run_optimization function."""

    @patch("nightjar.optimizer._call_llm_for_variation")
    def test_run_optimization_function(self, mock_llm, config):
        mock_llm.return_value = "Better prompt."
        result = run_optimization(config)
        assert isinstance(result, OptimizationResult)
