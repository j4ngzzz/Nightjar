"""Tests for contractd Rich CLI output formatting.

Reference: [REF-T17] Click CLI framework — display integrates with Click commands
Architecture: docs/ARCHITECTURE.md Section 8 — CLI design

TDD: These tests were written FIRST, before the display module.
"""

import io
from unittest.mock import patch, MagicMock

import pytest

from contractd.types import VerifyResult, StageResult, VerifyStatus


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def passing_result() -> VerifyResult:
    """A fully passing verification result."""
    return VerifyResult(
        verified=True,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=12),
            StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=45),
            StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=110),
            StageResult(stage=3, name="pbt", status=VerifyStatus.PASS, duration_ms=820),
            StageResult(stage=4, name="formal", status=VerifyStatus.PASS, duration_ms=3200),
        ],
        total_duration_ms=4187,
        retry_count=0,
    )


@pytest.fixture
def failing_result() -> VerifyResult:
    """A result with a failing PBT stage and errors."""
    return VerifyResult(
        verified=False,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=10),
            StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=30),
            StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=90),
            StageResult(
                stage=3,
                name="pbt",
                status=VerifyStatus.FAIL,
                duration_ms=1500,
                errors=[
                    {"message": "Property violation: amount must be positive", "line": 42},
                    {"message": "Falsifying example found", "line": 55},
                ],
                counterexample={"amount": -1, "currency": "USD"},
            ),
            StageResult(stage=4, name="formal", status=VerifyStatus.SKIP, duration_ms=0),
        ],
        total_duration_ms=1630,
        retry_count=2,
    )


@pytest.fixture
def timeout_result() -> VerifyResult:
    """A result with a timed-out formal stage."""
    return VerifyResult(
        verified=False,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=15),
            StageResult(stage=4, name="formal", status=VerifyStatus.TIMEOUT, duration_ms=30000),
        ],
        total_duration_ms=30015,
        retry_count=0,
    )


@pytest.fixture
def explain_report() -> dict:
    """A verification report dict for explain formatting."""
    return {
        "verified": False,
        "stages": [
            {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
            {
                "stage": 3,
                "name": "pbt",
                "status": "fail",
                "errors": [
                    {"message": "Property violation: amount must be positive"},
                    {"message": "Falsifying example: amount=-1"},
                ],
            },
        ],
        "total_duration_ms": 1500,
    }


# ── Module-level import tests ──────────────────────────


class TestDisplayImport:
    """Test that display module imports correctly."""

    def test_module_imports(self):
        """display.py can be imported."""
        import contractd.display  # noqa: F401

    def test_has_format_verify_result(self):
        """Module exposes format_verify_result function."""
        from contractd.display import format_verify_result
        assert callable(format_verify_result)

    def test_has_format_stage_result(self):
        """Module exposes format_stage_result function."""
        from contractd.display import format_stage_result
        assert callable(format_stage_result)

    def test_has_create_progress(self):
        """Module exposes create_progress function."""
        from contractd.display import create_progress
        assert callable(create_progress)

    def test_has_format_explain(self):
        """Module exposes format_explain function."""
        from contractd.display import format_explain
        assert callable(format_explain)


# ── format_verify_result tests ──────────────────────────


class TestFormatVerifyResult:
    """Test format_verify_result — full pipeline output."""

    def test_passing_result_shows_verified(self, passing_result, capsys):
        """Passing result prints VERIFIED badge."""
        from contractd.display import format_verify_result
        format_verify_result(passing_result)
        captured = capsys.readouterr().out
        assert "VERIFIED" in captured.upper()

    def test_failing_result_shows_fail(self, failing_result, capsys):
        """Failing result prints FAIL badge."""
        from contractd.display import format_verify_result
        format_verify_result(failing_result)
        captured = capsys.readouterr().out
        assert "FAIL" in captured.upper()

    def test_shows_stage_names(self, passing_result, capsys):
        """Output includes all stage names."""
        from contractd.display import format_verify_result
        format_verify_result(passing_result)
        captured = capsys.readouterr().out
        assert "preflight" in captured.lower()
        assert "deps" in captured.lower()
        assert "schema" in captured.lower()
        assert "pbt" in captured.lower()
        assert "formal" in captured.lower()

    def test_shows_duration(self, passing_result, capsys):
        """Output includes total duration."""
        from contractd.display import format_verify_result
        format_verify_result(passing_result)
        captured = capsys.readouterr().out
        # Should show duration in some form (ms or seconds)
        assert "4187" in captured or "4.19" in captured or "4.2" in captured

    def test_shows_errors_for_failed_stages(self, failing_result, capsys):
        """Failing stages show error messages."""
        from contractd.display import format_verify_result
        format_verify_result(failing_result)
        captured = capsys.readouterr().out
        assert "amount must be positive" in captured

    def test_shows_counterexample(self, failing_result, capsys):
        """Failing stages with counterexamples show them."""
        from contractd.display import format_verify_result
        format_verify_result(failing_result)
        captured = capsys.readouterr().out
        assert "-1" in captured

    def test_shows_retry_count(self, failing_result, capsys):
        """Output shows retry count when > 0."""
        from contractd.display import format_verify_result
        format_verify_result(failing_result)
        captured = capsys.readouterr().out
        assert "2" in captured  # retry_count=2

    def test_timeout_stage_displayed(self, timeout_result, capsys):
        """Timeout stages show TIMEOUT status."""
        from contractd.display import format_verify_result
        format_verify_result(timeout_result)
        captured = capsys.readouterr().out
        assert "TIMEOUT" in captured.upper()

    def test_empty_stages(self, capsys):
        """Result with no stages still shows header."""
        from contractd.display import format_verify_result
        result = VerifyResult(verified=True, stages=[], total_duration_ms=0, retry_count=0)
        format_verify_result(result)
        captured = capsys.readouterr().out
        assert "VERIFIED" in captured.upper()


# ── format_stage_result tests ───────────────────────────


class TestFormatStageResult:
    """Test format_stage_result — single stage display."""

    def test_pass_stage_returns_string(self):
        """Passing stage returns a non-empty string."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=12)
        result = format_stage_result(stage)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_pass_stage_contains_name(self):
        """Formatted stage includes the stage name."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=100)
        result = format_stage_result(stage)
        assert "schema" in result.lower()

    def test_pass_stage_contains_status(self):
        """Formatted stage includes status text."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=12)
        result = format_stage_result(stage)
        assert "PASS" in result.upper()

    def test_fail_stage_contains_status(self):
        """Failing stage shows FAIL."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=3, name="pbt", status=VerifyStatus.FAIL, duration_ms=800)
        result = format_stage_result(stage)
        assert "FAIL" in result.upper()

    def test_skip_stage_contains_status(self):
        """Skipped stage shows SKIP."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=4, name="formal", status=VerifyStatus.SKIP, duration_ms=0)
        result = format_stage_result(stage)
        assert "SKIP" in result.upper()

    def test_timeout_stage_contains_status(self):
        """Timeout stage shows TIMEOUT."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=4, name="formal", status=VerifyStatus.TIMEOUT, duration_ms=30000)
        result = format_stage_result(stage)
        assert "TIMEOUT" in result.upper()

    def test_stage_contains_duration(self):
        """Formatted stage includes duration."""
        from contractd.display import format_stage_result
        stage = StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=250)
        result = format_stage_result(stage)
        assert "250" in result or "0.25" in result


# ── create_progress tests ──────────────────────────────


class TestCreateProgress:
    """Test create_progress — Rich progress bar creation."""

    def test_returns_progress_object(self):
        """create_progress returns a Rich Progress instance."""
        from contractd.display import create_progress
        progress = create_progress()
        # Should be a Rich Progress or a compatible fallback
        assert progress is not None
        assert hasattr(progress, "__enter__")  # context manager
        assert hasattr(progress, "__exit__")

    def test_progress_is_context_manager(self):
        """Progress can be used as context manager."""
        from contractd.display import create_progress
        progress = create_progress()
        with progress:
            pass  # Just test it doesn't crash

    def test_progress_has_add_task(self):
        """Progress object has add_task method."""
        from contractd.display import create_progress
        progress = create_progress()
        assert hasattr(progress, "add_task")


# ── format_explain tests ───────────────────────────────


class TestFormatExplain:
    """Test format_explain — failure report display."""

    def test_explain_shows_failure_title(self, explain_report, capsys):
        """Explain output has a clear failure header."""
        from contractd.display import format_explain
        format_explain(explain_report)
        captured = capsys.readouterr().out
        # Should have some kind of failure header
        assert "fail" in captured.lower()

    def test_explain_shows_error_messages(self, explain_report, capsys):
        """Explain output shows individual error messages."""
        from contractd.display import format_explain
        format_explain(explain_report)
        captured = capsys.readouterr().out
        assert "amount must be positive" in captured

    def test_explain_shows_stage_info(self, explain_report, capsys):
        """Explain output identifies which stage failed."""
        from contractd.display import format_explain
        format_explain(explain_report)
        captured = capsys.readouterr().out
        assert "pbt" in captured.lower() or "3" in captured

    def test_explain_verified_shows_no_failures(self, capsys):
        """Explain on a passing report shows success message."""
        from contractd.display import format_explain
        report = {"verified": True, "stages": [], "total_duration_ms": 100}
        format_explain(report)
        captured = capsys.readouterr().out
        assert "pass" in captured.lower() or "no failure" in captured.lower()

    def test_explain_empty_errors(self, capsys):
        """Explain handles stages with empty error lists."""
        from contractd.display import format_explain
        report = {
            "verified": False,
            "stages": [{"stage": 1, "name": "deps", "status": "fail", "errors": []}],
            "total_duration_ms": 50,
        }
        format_explain(report)
        captured = capsys.readouterr().out
        assert "fail" in captured.lower()

    def test_explain_with_counterexample(self, capsys):
        """Explain shows counterexample data when present."""
        from contractd.display import format_explain
        report = {
            "verified": False,
            "stages": [
                {
                    "stage": 3,
                    "name": "pbt",
                    "status": "fail",
                    "errors": [
                        {
                            "message": "falsifying example",
                            "counterexample": {"x": 0, "y": -5},
                        }
                    ],
                }
            ],
            "total_duration_ms": 200,
        }
        format_explain(report)
        captured = capsys.readouterr().out
        assert "-5" in captured


# ── Graceful fallback tests ────────────────────────────


class TestGracefulFallback:
    """Test that display works even if Rich is not installed."""

    def test_format_verify_result_no_crash(self, passing_result, capsys):
        """format_verify_result does not crash even without Rich console."""
        from contractd.display import format_verify_result
        # This should work regardless — function should not raise
        format_verify_result(passing_result)
        captured = capsys.readouterr().out
        assert len(captured) > 0

    def test_format_explain_no_crash(self, explain_report, capsys):
        """format_explain does not crash."""
        from contractd.display import format_explain
        format_explain(explain_report)
        captured = capsys.readouterr().out
        assert len(captured) > 0
