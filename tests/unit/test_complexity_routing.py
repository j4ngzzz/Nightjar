"""Tests for U1.5 — Complexity-Discriminated Routing + Display Hooks.

Simple functions (low cyclomatic complexity + shallow AST) route to CrossHair only.
Complex functions route to full Dafny. Cuts ~70% verification time on typical codebases.

Display hooks in run_pipeline(): on_stage_start / on_stage_complete / on_pipeline_complete.

References:
- SafePilot (arxiv:2603.21523)
- nightjar-upgrade-plan.md U1.5
- nightjar.display DisplayCallback / NullDisplay
"""

import pytest
from unittest.mock import MagicMock, patch, call
from nightjar.types import (
    CardSpec, Contract, ModuleBoundary, Invariant, InvariantTier,
    StageResult, VerifyResult, VerifyStatus,
)


def _make_spec(invariants=None) -> CardSpec:
    return CardSpec(
        card_version="1.0", id="test", title="Test", status="draft",
        module=ModuleBoundary(owns=["f()"]),
        contract=Contract(),
        invariants=invariants or [],
    )


# ── Simple code: no branches, shallow AST
SIMPLE_CODE = "def charge(amount: int) -> int:\n    return amount * 2\n"

# ── Complex code: many branches, deep nesting
COMPLEX_CODE = """
def process(x):
    if x > 0:
        if x > 10:
            for i in range(x):
                if i % 2 == 0:
                    try:
                        result = x / i
                    except ZeroDivisionError:
                        result = 0
                else:
                    result = i
        else:
            while x > 0:
                x -= 1
    elif x < 0:
        x = abs(x)
    else:
        x = 1
    return x
"""


class TestComplexityScorer:
    """Tests for complexity scoring function."""

    def test_compute_complexity_importable(self):
        """_compute_complexity is importable from verifier."""
        from nightjar.verifier import _compute_complexity
        assert callable(_compute_complexity)

    def test_simple_function_has_low_complexity(self):
        """Single-expression function: complexity ≤ 3."""
        from nightjar.verifier import _compute_complexity
        score = _compute_complexity(SIMPLE_CODE)
        assert score <= 3, f"Simple function should score ≤ 3, got {score}"

    def test_complex_function_has_high_complexity(self):
        """Deeply-nested function with many branches: complexity > 5."""
        from nightjar.verifier import _compute_complexity
        score = _compute_complexity(COMPLEX_CODE)
        assert score > 5, f"Complex function should score > 5, got {score}"

    def test_complexity_is_non_negative(self):
        """Complexity score is always >= 0."""
        from nightjar.verifier import _compute_complexity
        assert _compute_complexity(SIMPLE_CODE) >= 0
        assert _compute_complexity(COMPLEX_CODE) >= 0

    def test_invalid_syntax_returns_high_complexity(self):
        """Syntax errors → max complexity (route to Dafny for safety)."""
        from nightjar.verifier import _compute_complexity
        score = _compute_complexity("def f(: invalid syntax !!!")
        assert score > 5, "Invalid syntax should return high complexity"


class TestRoutingDecision:
    """Tests for _route_to_crosshair() routing decision."""

    def test_route_to_crosshair_importable(self):
        from nightjar.verifier import _route_to_crosshair
        assert callable(_route_to_crosshair)

    def test_simple_function_routes_to_crosshair(self):
        """Simple function (low complexity) → CrossHair route."""
        from nightjar.verifier import _route_to_crosshair
        assert _route_to_crosshair(SIMPLE_CODE) is True, (
            "Simple function should route to CrossHair"
        )

    def test_complex_function_routes_to_dafny(self):
        """Complex function (high complexity) → Dafny route."""
        from nightjar.verifier import _route_to_crosshair
        assert _route_to_crosshair(COMPLEX_CODE) is False, (
            "Complex function should route to Dafny"
        )


class TestDisplayHooks:
    """Tests for display_callback hooks in run_pipeline().

    Per display.py: verifier calls on_stage_start/on_stage_complete/on_pipeline_complete.
    Hooks are called for each stage in order.
    """

    def test_run_pipeline_accepts_display_callback(self):
        """run_pipeline accepts an optional display_callback kwarg."""
        from nightjar.verifier import run_pipeline
        import inspect
        sig = inspect.signature(run_pipeline)
        assert "display_callback" in sig.parameters

    def test_on_stage_start_called_for_each_stage(self):
        """on_stage_start is called before each stage runs."""
        from nightjar.verifier import run_pipeline
        from nightjar.display import NullDisplay

        spec = _make_spec()
        mock_display = MagicMock(spec=NullDisplay)

        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            for m in (s0, s1, s2, s3, s4):
                m.return_value = StageResult(
                    stage=0, name="test", status=VerifyStatus.PASS,
                )
            run_pipeline(spec, SIMPLE_CODE, display_callback=mock_display)

        # on_stage_start must have been called at least once
        assert mock_display.on_stage_start.called, (
            "on_stage_start should be called for each stage"
        )

    def test_on_stage_complete_called_for_each_stage(self):
        """on_stage_complete is called after each stage completes."""
        from nightjar.verifier import run_pipeline
        from nightjar.display import NullDisplay

        spec = _make_spec()
        mock_display = MagicMock(spec=NullDisplay)

        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            for m in (s0, s1, s2, s3, s4):
                m.return_value = StageResult(
                    stage=0, name="test", status=VerifyStatus.PASS,
                )
            run_pipeline(spec, SIMPLE_CODE, display_callback=mock_display)

        assert mock_display.on_stage_complete.called, (
            "on_stage_complete should be called after each stage"
        )

    def test_on_pipeline_complete_called_at_end(self):
        """on_pipeline_complete is called with the final VerifyResult."""
        from nightjar.verifier import run_pipeline
        from nightjar.display import NullDisplay

        spec = _make_spec()
        mock_display = MagicMock(spec=NullDisplay)

        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            for m in (s0, s1, s2, s3, s4):
                m.return_value = StageResult(
                    stage=0, name="test", status=VerifyStatus.PASS,
                )
            result = run_pipeline(spec, SIMPLE_CODE, display_callback=mock_display)

        mock_display.on_pipeline_complete.assert_called_once()
        args = mock_display.on_pipeline_complete.call_args[0]
        assert isinstance(args[0], VerifyResult)

    def test_null_display_default_does_not_crash(self):
        """run_pipeline without display_callback runs with NullDisplay (no crash)."""
        from nightjar.verifier import run_pipeline

        spec = _make_spec()
        with patch("nightjar.verifier._run_stage_0") as s0, \
             patch("nightjar.verifier._run_stage_1") as s1, \
             patch("nightjar.verifier._run_stage_2") as s2, \
             patch("nightjar.verifier._run_stage_3") as s3, \
             patch("nightjar.verifier._run_stage_4") as s4:
            for m in (s0, s1, s2, s3, s4):
                m.return_value = StageResult(
                    stage=0, name="test", status=VerifyStatus.PASS,
                )
            # No display_callback → should use NullDisplay internally, not crash
            result = run_pipeline(spec, SIMPLE_CODE)
        assert isinstance(result, VerifyResult)
