"""Tests for U3.3 — Rich streaming display_callback interface.

The DisplayCallback protocol defines the hooks that verifier.py will call during
pipeline execution so the display layer (Rich Live or Textual TUI) receives
live progress events without coupling to the output format.

References:
- [REF-NEW-11] Rich streaming display (U3.3)
- nightjar-upgrade-plan.md Task U3.3
"""

import io

import pytest

from nightjar.types import StageResult, VerifyResult, VerifyStatus
from nightjar.display import (
    DisplayCallback,
    NullDisplay,
    RichStreamingDisplay,
)

# ── helpers ────────────────────────────────────────────────────────────────


def _stage(stage: int, name: str, status: VerifyStatus, ms: int = 100) -> StageResult:
    return StageResult(stage=stage, name=name, status=status, duration_ms=ms)


# ── DisplayCallback protocol ───────────────────────────────────────────────


class TestDisplayCallbackProtocol:
    """DisplayCallback is a runtime-checkable Protocol."""

    def test_null_display_satisfies_protocol(self):
        """NullDisplay must pass isinstance(x, DisplayCallback)."""
        assert isinstance(NullDisplay(), DisplayCallback)

    def test_rich_streaming_display_satisfies_protocol(self):
        """RichStreamingDisplay must pass isinstance(x, DisplayCallback)."""
        assert isinstance(RichStreamingDisplay(), DisplayCallback)

    def test_arbitrary_object_without_methods_fails(self):
        """Plain object without the callback methods is not a DisplayCallback."""
        assert not isinstance(object(), DisplayCallback)

    def test_partial_implementation_fails(self):
        """Object missing one method is not a valid DisplayCallback."""

        class Partial:
            def on_stage_start(self, stage: int, name: str) -> None: ...
            def on_stage_complete(self, result) -> None: ...
            # missing on_pipeline_complete

        assert not isinstance(Partial(), DisplayCallback)


# ── NullDisplay ────────────────────────────────────────────────────────────


class TestNullDisplay:
    """NullDisplay is a silent no-op — suitable for tests and --quiet mode."""

    def test_on_stage_start_does_not_raise(self):
        NullDisplay().on_stage_start(0, "preflight")

    def test_on_stage_complete_does_not_raise(self):
        NullDisplay().on_stage_complete(_stage(0, "preflight", VerifyStatus.PASS))

    def test_on_pipeline_complete_does_not_raise(self):
        NullDisplay().on_pipeline_complete(VerifyResult(verified=True))

    def test_multiple_calls_do_not_raise(self):
        d = NullDisplay()
        for i in range(5):
            d.on_stage_start(i, f"stage{i}")
            d.on_stage_complete(_stage(i, f"stage{i}", VerifyStatus.PASS))
        d.on_pipeline_complete(VerifyResult(verified=True))


# ── RichStreamingDisplay state tracking ───────────────────────────────────


class TestRichStreamingDisplayState:
    """RichStreamingDisplay tracks pipeline state regardless of terminal output."""

    def test_context_manager_enter_exit(self):
        """RichStreamingDisplay is a context manager that doesn't raise."""
        with RichStreamingDisplay():
            pass

    def test_on_stage_start_marks_running(self):
        """on_stage_start records the stage as 'running'."""
        d = RichStreamingDisplay()
        with d:
            d.on_stage_start(0, "preflight")
        assert d.stage_status[0] == "running"

    def test_on_stage_start_records_name(self):
        """on_stage_start records the stage name."""
        d = RichStreamingDisplay()
        with d:
            d.on_stage_start(2, "schema")
        assert d.stage_names[2] == "schema"

    def test_on_stage_complete_updates_status_pass(self):
        """on_stage_complete records PASS status."""
        d = RichStreamingDisplay()
        with d:
            d.on_stage_start(0, "preflight")
            d.on_stage_complete(_stage(0, "preflight", VerifyStatus.PASS, ms=50))
        assert d.stage_status[0] == VerifyStatus.PASS

    def test_on_stage_complete_updates_status_fail(self):
        """on_stage_complete records FAIL status."""
        d = RichStreamingDisplay()
        with d:
            d.on_stage_start(3, "pbt")
            d.on_stage_complete(_stage(3, "pbt", VerifyStatus.FAIL, ms=800))
        assert d.stage_status[3] == VerifyStatus.FAIL

    def test_on_stage_complete_records_duration(self):
        """on_stage_complete records the stage duration."""
        d = RichStreamingDisplay()
        with d:
            d.on_stage_start(1, "deps")
            d.on_stage_complete(_stage(1, "deps", VerifyStatus.PASS, ms=320))
        assert d.stage_durations[1] == 320

    def test_on_pipeline_complete_marks_done(self):
        """on_pipeline_complete sets pipeline_done = True."""
        d = RichStreamingDisplay()
        with d:
            d.on_pipeline_complete(VerifyResult(verified=True))
        assert d.pipeline_done is True

    def test_on_pipeline_complete_records_verified(self):
        """on_pipeline_complete stores the verified flag."""
        d = RichStreamingDisplay()
        with d:
            d.on_pipeline_complete(VerifyResult(verified=False))
        assert d.pipeline_verified is False

    def test_full_pipeline_sequence(self):
        """All 5 stages start + complete + pipeline done."""
        stages = [
            (0, "preflight", VerifyStatus.PASS, 50),
            (1, "deps", VerifyStatus.PASS, 200),
            (2, "schema", VerifyStatus.PASS, 150),
            (3, "pbt", VerifyStatus.PASS, 400),
            (4, "formal", VerifyStatus.PASS, 3000),
        ]
        results = [
            StageResult(stage=s, name=n, status=st, duration_ms=ms)
            for s, n, st, ms in stages
        ]
        verify_result = VerifyResult(verified=True, stages=results)

        d = RichStreamingDisplay()
        with d:
            for s, n, st, ms in stages:
                d.on_stage_start(s, n)
                d.on_stage_complete(StageResult(stage=s, name=n, status=st, duration_ms=ms))
            d.on_pipeline_complete(verify_result)

        assert all(d.stage_status[i] == VerifyStatus.PASS for i in range(5))
        assert d.pipeline_done is True
        assert d.pipeline_verified is True


# ── RichStreamingDisplay with injected console ────────────────────────────


class TestRichStreamingDisplayOutput:
    """RichStreamingDisplay renderable contains expected content."""

    def _render(self, d: "RichStreamingDisplay") -> str:
        """Render the current display state to a plain-text string."""
        try:
            from rich.console import Console
            buf = io.StringIO()
            con = Console(file=buf, highlight=False, no_color=True)
            con.print(d._build_renderable())
            return buf.getvalue()
        except ImportError:
            pytest.skip("Rich not installed")

    def test_stage_name_appears_in_renderable(self):
        """Stage name 'preflight' must appear in the rendered table."""
        d = RichStreamingDisplay()
        d.on_stage_start(0, "preflight")
        output = self._render(d)
        assert "preflight" in output

    def test_pass_status_appears_in_renderable(self):
        """PASS must appear in rendered output after a passing stage."""
        d = RichStreamingDisplay()
        d.on_stage_start(0, "preflight")
        d.on_stage_complete(_stage(0, "preflight", VerifyStatus.PASS))
        output = self._render(d)
        assert "PASS" in output or "pass" in output.lower()
