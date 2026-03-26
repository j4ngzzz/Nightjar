"""Tests for U3.1 — Textual TUI dashboard.

The TUI implements DisplayCallback so verifier.py can drive it via the
three on_* hooks.  Tests use Textual's App.run_test() async context manager
to verify widget state without requiring a real terminal.

References:
- [REF-NEW-11] Rich/Textual streaming display (U3.1)
- [REF-NEW-13] Moulti step-display pattern
- nightjar-upgrade-plan.md Task U3.1
"""

import pytest

from nightjar.types import StageResult, VerifyResult, VerifyStatus
from nightjar.display import DisplayCallback


# ── helpers ────────────────────────────────────────────────────────────────


def _stage(stage: int, name: str, status: VerifyStatus, ms: int = 100) -> StageResult:
    return StageResult(stage=stage, name=name, status=status, duration_ms=ms)


# ── import guard ───────────────────────────────────────────────────────────


try:
    from nightjar.tui import NightjarTUI, StagePanel
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

pytestmark = pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")


# ── Protocol conformance ───────────────────────────────────────────────────


class TestNightjarTUIProtocol:
    """NightjarTUI satisfies the DisplayCallback protocol."""

    def test_implements_display_callback(self):
        """NightjarTUI is a valid DisplayCallback."""
        app = NightjarTUI()
        assert isinstance(app, DisplayCallback)


# ── Widget composition ─────────────────────────────────────────────────────


class TestTUIRenders:
    """TUI composes the expected widget tree."""

    async def test_renders_five_stage_panels(self):
        """Five StagePanel widgets must be present at startup."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            panels = app.query(StagePanel)
            assert len(panels) == 5

    async def test_all_stages_start_as_waiting(self):
        """All five stages must have status 'waiting' on startup."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            for panel in app.query(StagePanel):
                assert panel.stage_status_val == "waiting"

    async def test_confidence_bar_present(self):
        """A ProgressBar widget with id='confidence' must exist."""
        from textual.widgets import ProgressBar
        app = NightjarTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#confidence", ProgressBar)
            assert bar is not None


# ── Live updates via DisplayCallback ──────────────────────────────────────


class TestTUILiveUpdates:
    """on_stage_start / on_stage_complete drive live panel updates."""

    async def test_on_stage_start_marks_running(self):
        """Calling on_stage_start transitions the panel to 'running'."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_stage_start(0, "preflight")
            await pilot.pause()
            panel = app.query_one("#stage-0", StagePanel)
            assert panel.stage_status_val == "running"

    async def test_on_stage_start_sets_name(self):
        """on_stage_start updates the stage panel's name."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_stage_start(2, "schema")
            await pilot.pause()
            panel = app.query_one("#stage-2", StagePanel)
            assert panel.stage_name_str == "schema"

    async def test_on_stage_complete_sets_pass(self):
        """on_stage_complete with PASS sets panel to 'pass'."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_stage_start(1, "deps")
            app.on_stage_complete(_stage(1, "deps", VerifyStatus.PASS, ms=200))
            await pilot.pause()
            panel = app.query_one("#stage-1", StagePanel)
            assert panel.stage_status_val == "pass"

    async def test_on_stage_complete_sets_fail(self):
        """on_stage_complete with FAIL sets panel to 'fail'."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_stage_start(3, "pbt")
            app.on_stage_complete(_stage(3, "pbt", VerifyStatus.FAIL, ms=800))
            await pilot.pause()
            panel = app.query_one("#stage-3", StagePanel)
            assert panel.stage_status_val == "fail"

    async def test_on_stage_complete_records_duration(self):
        """on_stage_complete stores the duration_ms on the panel."""
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_stage_complete(_stage(0, "preflight", VerifyStatus.PASS, ms=42))
            await pilot.pause()
            panel = app.query_one("#stage-0", StagePanel)
            assert panel.duration_ms == 42

    async def test_on_pipeline_complete_verified_shows_banner(self):
        """on_pipeline_complete(verified=True) updates banner to VERIFIED."""
        from textual.widgets import Static
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_pipeline_complete(VerifyResult(verified=True))
            await pilot.pause()
            banner = app.query_one("#banner", Static)
            content = str(banner.render())
            assert "VERIFIED" in content.upper()

    async def test_on_pipeline_complete_fail_shows_banner(self):
        """on_pipeline_complete(verified=False) updates banner to FAIL."""
        from textual.widgets import Static
        app = NightjarTUI()
        async with app.run_test() as pilot:
            app.on_pipeline_complete(VerifyResult(verified=False))
            await pilot.pause()
            banner = app.query_one("#banner", Static)
            content = str(banner.render())
            assert "FAIL" in content.upper()

    async def test_full_pipeline_all_pass(self):
        """All five stages PASS → pipeline_complete(verified=True)."""
        app = NightjarTUI()
        stages = [
            (0, "preflight", VerifyStatus.PASS, 50),
            (1, "deps",      VerifyStatus.PASS, 200),
            (2, "schema",    VerifyStatus.PASS, 150),
            (3, "pbt",       VerifyStatus.PASS, 400),
            (4, "formal",    VerifyStatus.PASS, 3000),
        ]
        results = [StageResult(stage=s, name=n, status=st, duration_ms=ms)
                   for s, n, st, ms in stages]
        verify_result = VerifyResult(verified=True, stages=results)

        async with app.run_test() as pilot:
            for s, n, st, ms in stages:
                app.on_stage_start(s, n)
                app.on_stage_complete(StageResult(stage=s, name=n, status=st, duration_ms=ms))
            app.on_pipeline_complete(verify_result)
            await pilot.pause()

            for i in range(5):
                panel = app.query_one(f"#stage-{i}", StagePanel)
                assert panel.stage_status_val == "pass"
