"""Textual TUI dashboard for nightjar verify [REF-NEW-11, REF-NEW-13].

Implements the DisplayCallback protocol so verifier.py can drive it:

    tui = NightjarTUI()
    with tui.run_display():          # starts Textual event loop
        verifier.run_pipeline(spec, display=tui)

The TUI renders 5 collapsible stage panels (Moulti pattern) that
transition from waiting → running → PASS/FAIL as the pipeline executes.
A confidence bar and pass/fail banner appear at the bottom.

References:
- [REF-NEW-11] Rich/Textual streaming display (U3.1, U3.3)
- [REF-NEW-13] Moulti step-display pattern (MIT)
- Textual docs: https://textual.textualize.io
- nightjar-upgrade-plan.md Task U3.1
"""

from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widgets import Footer, Header, ProgressBar, Static
    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover
    HAS_TEXTUAL = False
    App = object  # type: ignore[misc,assignment]
    ComposeResult = object  # type: ignore[misc,assignment]
    Vertical = object  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]
    reactive = object  # type: ignore[misc,assignment]
    Footer = object  # type: ignore[misc,assignment]
    Header = object  # type: ignore[misc,assignment]
    ProgressBar = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]

from nightjar.types import StageResult, VerifyResult, VerifyStatus


# ── Stage panel widget ─────────────────────────────────────────────────────


class StagePanel(Static):
    """One row in the verification dashboard — one per pipeline stage.

    Reactive attributes auto-rerender the widget whenever they change,
    giving a live "terminal dashboard" feel with zero manual refresh calls.

    Moulti inspiration: each step is its own independent row that updates
    in place as the pipeline progresses.
    """

    # Status string: "waiting" | "running" | "pass" | "fail" | "skip"
    stage_status_val: reactive[str] = reactive("waiting")
    stage_name_str: reactive[str] = reactive("")
    duration_ms: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    StagePanel {
        height: 1;
        padding: 0 2;
    }
    """

    # Nightjar color palette — icons for render(), colors for styles.color (CSS only)
    _STATUS_ICONS = {
        "waiting": "○",
        "running": "▶",
        "pass":    "✓",
        "fail":    "✗",
        "skip":    "–",
        "timeout": "⏱",
    }
    _STATUS_COLORS = {
        "waiting": "#888888",
        "running": "#F59E0B",
        "pass":    "#00FF88",
        "fail":    "red",
        "skip":    "yellow",
        "timeout": "magenta",
    }

    def __init__(self, stage_num: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._stage_num = stage_num
        self.stage_name_str = f"stage{stage_num}"

    def render(self) -> str:
        icon = self._STATUS_ICONS.get(self.stage_status_val, "?")
        name = self.stage_name_str
        status = self.stage_status_val.upper()
        dur = f"[{self.duration_ms}ms]" if self.duration_ms else ""
        return f"{icon} Stage {self._stage_num}: {name:<16} {dur:<12} {status}"

    def watch_stage_status_val(self, value: str) -> None:
        """Apply CSS color when status changes."""
        color = self._STATUS_COLORS.get(value)
        self.styles.color = color  # None resets to default


# ── Custom messages (thread-safe post_message pattern) ────────────────────


class _StageStarted(Message):
    """Posted when a pipeline stage begins — thread-safe [Textual docs]."""
    def __init__(self, stage: int, name: str) -> None:
        super().__init__()
        self.stage = stage
        self.name = name


class _StageFinished(Message):
    """Posted when a pipeline stage completes — thread-safe."""
    def __init__(self, result: StageResult) -> None:
        super().__init__()
        self.result = result


class _PipelineFinished(Message):
    """Posted when the full pipeline completes — thread-safe."""
    def __init__(self, result: VerifyResult) -> None:
        super().__init__()
        self.result = result


# ── Main TUI App ──────────────────────────────────────────────────────────


class NightjarTUI(App[None]):
    """Textual TUI dashboard for live verification progress.

    Implements the DisplayCallback protocol so it can be passed directly
    to verifier.run_pipeline(spec, display=tui).

    Builder-VerEngine (U1.5) wires the call sites in verifier.py.
    """

    TITLE = "Nightjar Verify"
    CSS = """
    Screen {
        background: #1e1e2e;
    }
    #stages {
        height: auto;
        padding: 1 0;
        border: solid #313244;
    }
    #confidence {
        height: 3;
        margin: 0 2;
    }
    #banner {
        height: 3;
        content-align: center middle;
        text-align: center;
    }
    """

    # ── Layout ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="stages"):
            for i in range(5):
                yield StagePanel(i, id=f"stage-{i}")
        yield ProgressBar(total=100, id="confidence", show_eta=False)
        yield Static("", id="banner")
        yield Footer()

    # ── DisplayCallback protocol ──────────────────────────────────────────

    def on_stage_start(self, stage: int, name: str) -> None:
        """Called by verifier when a stage begins.

        Uses post_message (thread-safe) so this can be called from any
        thread — including a background verification worker.
        """
        self.post_message(_StageStarted(stage, name))

    def on_stage_complete(self, result: StageResult) -> None:
        """Called by verifier when a stage finishes (pass/fail/skip)."""
        self.post_message(_StageFinished(result))

    def on_pipeline_complete(self, result: VerifyResult) -> None:
        """Called by verifier when all stages have run."""
        self.post_message(_PipelineFinished(result))

    # ── Message handlers (main thread — safe to touch widgets) ────────────

    def on__stage_started(self, event: _StageStarted) -> None:
        panel = self.query_one(f"#stage-{event.stage}", StagePanel)
        panel.stage_name_str = event.name
        panel.stage_status_val = "running"

    def on__stage_finished(self, event: _StageFinished) -> None:
        r = event.result
        panel = self.query_one(f"#stage-{r.stage}", StagePanel)
        panel.stage_name_str = r.name
        panel.stage_status_val = r.status.value  # "pass" / "fail" / "skip"
        panel.duration_ms = r.duration_ms

    def on__pipeline_finished(self, event: _PipelineFinished) -> None:
        banner = self.query_one("#banner", Static)
        if event.result.verified:
            banner.update("✓  VERIFIED")
            banner.styles.color = "#00FF88"
        else:
            banner.update("✗  FAIL")
            banner.styles.color = "red"

        # Update confidence bar if a ConfidenceScore is attached
        if event.result.confidence is not None:
            try:
                score = int(event.result.confidence.score)  # type: ignore[union-attr]
                self.query_one("#confidence", ProgressBar).update(progress=score)
            except (AttributeError, TypeError, ValueError):
                pass
