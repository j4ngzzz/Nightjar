"""Rich CLI output formatting + streaming display_callback interface.

Provides colored, structured terminal output for verification results,
progress tracking, and failure explanation.

STREAMING INTERFACE (U3.3) [REF-NEW-11]:
  DisplayCallback  — runtime-checkable Protocol; verifier.py calls these hooks
  NullDisplay      — silent no-op (tests, --quiet mode, non-interactive)
  RichStreamingDisplay — Rich Live streaming table; one row per pipeline stage

  Usage in verifier.py (Builder-VerEngine wires this in U1.5)::

      display = RichStreamingDisplay()
      with display:
          for stage in stages:
              display.on_stage_start(stage.num, stage.name)
              result = run_stage(stage)
              display.on_stage_complete(result)
          display.on_pipeline_complete(verify_result)

References:
- [REF-T17] Click CLI framework -- display integrates with Click commands
- [REF-NEW-11] Rich streaming display (U3.3 nightjar-upgrade-plan.md)
- Rich Live docs: https://rich.readthedocs.io/en/stable/live.html
- ARCHITECTURE.md Section 8 -- CLI design
"""

from typing import Optional, TYPE_CHECKING

from nightjar.types import StageResult, TrustLevel, VerifyResult, VerifyStatus

# Graceful Rich import -- fall back to plain text if Rich is not installed.
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    HAS_RICH = True
    try:
        from rich.group import Group
        HAS_RICH_GROUP = True
    except ImportError:
        HAS_RICH_GROUP = False
        Group = None  # type: ignore[assignment,misc]
except ImportError:
    HAS_RICH = False
    HAS_RICH_GROUP = False
    Group = None  # type: ignore[assignment,misc]

# ── Streaming display_callback interface (U3.3) [REF-NEW-11] ─────────────
#
# These three classes form the observer interface between verifier.py and the
# display layer.  Builder-VerEngine wires the hooks into verifier.py (U1.5).
# Builder-DX provides the implementations here (U3.3) and in tui.py (U3.1).

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # Python < 3.8 fallback (not expected, but safe)
    from typing_extensions import Protocol, runtime_checkable  # type: ignore


@runtime_checkable
class DisplayCallback(Protocol):
    """Observer protocol for live pipeline progress events [REF-NEW-11].

    Verifier.py calls these hooks during pipeline execution so the display
    layer receives events without coupling to a specific output format.

    All implementations must define all three methods.
    """

    def on_stage_start(self, stage: int, name: str) -> None:
        """Called when a verification stage begins execution."""
        ...

    def on_stage_complete(self, result: StageResult) -> None:
        """Called when a stage finishes (pass, fail, or skip)."""
        ...

    def on_pipeline_complete(self, result: VerifyResult) -> None:
        """Called once when the full pipeline finishes."""
        ...


class NullDisplay:
    """Silent no-op display — for tests, --quiet mode, or non-interactive use.

    Satisfies the DisplayCallback protocol without producing any output.
    """

    def on_stage_start(self, stage: int, name: str) -> None:
        pass

    def on_stage_complete(self, result: StageResult) -> None:
        pass

    def on_pipeline_complete(self, result: VerifyResult) -> None:
        pass


class RichStreamingDisplay:
    """Live streaming pipeline output using Rich Live [REF-NEW-11].

    Renders a live-updating table in the terminal — one row per stage.
    Stage rows transition: (waiting) → running... → PASS / FAIL.
    A confidence bar appears once the pipeline completes.

    Usage::

        with RichStreamingDisplay() as display:
            display.on_stage_start(0, "preflight")
            display.on_stage_complete(stage_result)
            ...
            display.on_pipeline_complete(verify_result)

    The ``console`` parameter is injectable for tests (pass a Console backed
    by ``io.StringIO`` to capture output without a real terminal).
    """

    # Color constants — nightjar palette
    _COLOR_PASS = "bold green"
    _COLOR_FAIL = "bold red"
    _COLOR_RUNNING = "bold yellow"
    _COLOR_WAITING = "dim"

    def __init__(self, console: Optional["Console"] = None) -> None:
        self._injected_console = console
        self.stage_status: dict[int, "str | VerifyStatus"] = {}
        self.stage_names: dict[int, str] = {}
        self.stage_durations: dict[int, int] = {}
        self.stage_coverage_notes: dict[int, str] = {}
        self.pipeline_done: bool = False
        self.pipeline_verified: bool = False
        self.pipeline_trust_level: Optional[TrustLevel] = None
        self.pipeline_confidence_val: float = 0.0
        self._live: Optional["Live"] = None

    # ── Context manager ──────────────────────────────────────────────────

    def __enter__(self) -> "RichStreamingDisplay":
        if HAS_RICH:
            con = self._injected_console or Console(
                force_terminal=True, highlight=False
            )
            self._live = Live(
                self._build_renderable(),
                console=con,
                refresh_per_second=10,
                transient=False,
            )
            self._live.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._live is not None:
            # Final refresh with terminal state before exiting
            self._live.update(self._build_renderable(), refresh=True)
            self._live.__exit__(*args)

    # ── DisplayCallback implementation ───────────────────────────────────

    def on_stage_start(self, stage: int, name: str) -> None:
        """Mark stage as running and refresh the live display."""
        self.stage_status[stage] = "running"
        self.stage_names[stage] = name
        self._refresh()

    def on_stage_complete(self, result: StageResult) -> None:
        """Update stage row with final status/duration and refresh."""
        self.stage_status[result.stage] = result.status
        self.stage_names[result.stage] = result.name
        self.stage_durations[result.stage] = result.duration_ms
        if result.coverage_note:
            self.stage_coverage_notes[result.stage] = result.coverage_note
        self._refresh()

    def on_pipeline_complete(self, result: VerifyResult) -> None:
        """Render the final pass/fail banner and freeze the display."""
        self.pipeline_done = True
        self.pipeline_verified = result.verified
        self.pipeline_trust_level = result.trust_level
        if result.confidence is not None:
            self.pipeline_confidence_val = result.confidence.total / 100.0
        self._refresh()

    # ── Internal rendering ───────────────────────────────────────────────

    def _refresh(self) -> None:
        """Push an updated renderable to the Live display."""
        if self._live is not None and HAS_RICH:
            self._live.update(self._build_renderable(), refresh=True)

    def _build_renderable(self) -> object:
        """Build the Rich renderable for the current pipeline state.

        Returns a Group containing the stage table and (when done) a
        pass/fail banner.  Falls back to a plain string when Rich is absent.
        """
        if not HAS_RICH:
            return self._build_plain()

        table = Table(
            title="Nightjar Verify",
            show_header=True,
            show_lines=False,
            expand=True,
        )
        table.add_column("Stage", justify="center", style="cyan", width=7)
        table.add_column("Name", style="bold", width=14)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Duration", justify="right", width=10)

        for stage_num in range(_STAGE_COUNT):
            status = self.stage_status.get(stage_num)
            name = self.stage_names.get(stage_num, _STAGE_NAMES.get(stage_num, f"stage{stage_num}"))
            ms = self.stage_durations.get(stage_num)
            duration_str = _format_duration_ms(ms) if ms is not None else "—"

            if status is None:
                status_cell = Text("waiting", style=self._COLOR_WAITING)
            elif status == "running":
                status_cell = Text("running…", style=self._COLOR_RUNNING)
            elif status == VerifyStatus.PASS:
                status_cell = Text("PASS", style=self._COLOR_PASS)
            elif status == VerifyStatus.FAIL:
                status_cell = Text("FAIL", style=self._COLOR_FAIL)
            elif status == VerifyStatus.SKIP:
                status_cell = Text("SKIP", style="bold yellow")
            else:
                status_cell = Text(str(status), style="dim")

            table.add_row(str(stage_num), name, status_cell, duration_str)

        if self.pipeline_done:
            if self.pipeline_verified:
                banner_text = Text(" ✓ VERIFIED ", style="bold white on green", justify="center")
                border = "green"
            else:
                banner_text = Text(" ✗ FAIL ", style="bold white on red", justify="center")
                border = "red"

            if self.pipeline_trust_level is not None:
                style = _TRUST_LEVEL_STYLES.get(self.pipeline_trust_level, "")
                if self.pipeline_done and self.pipeline_confidence_val != 0.0:
                    confidence_str = f" ({self.pipeline_confidence_val:.2f})"
                else:
                    confidence_str = ""
                coverage_parts = [
                    note for note in self.stage_coverage_notes.values() if note
                ]
                coverage_detail = (" — " + " | ".join(coverage_parts)) if coverage_parts else ""
                trust_text = Text(
                    f"Trust: {self.pipeline_trust_level.value}{confidence_str}{coverage_detail}",
                    style=style,
                    justify="center",
                )
                if HAS_RICH_GROUP:
                    banner_content = Group(banner_text, trust_text)
                else:
                    banner_content = banner_text
            else:
                banner_content = banner_text

            banner = Panel(banner_content, border_style=border)
            if HAS_RICH_GROUP:
                return Group(table, banner)
            return table

        return table

    def _build_plain(self) -> str:
        """Plain-text fallback when Rich is not installed."""
        lines = ["=== Nightjar Verify ==="]
        for stage_num in range(_STAGE_COUNT):
            status = self.stage_status.get(stage_num, "waiting")
            name = self.stage_names.get(stage_num, _STAGE_NAMES.get(stage_num, f"stage{stage_num}"))
            status_str = status.value if hasattr(status, "value") else status
            lines.append(f"  Stage {stage_num} ({name}): {status_str}")
        if self.pipeline_done:
            result_str = "VERIFIED" if self.pipeline_verified else "FAIL"
            lines.append(f"\n>>> {result_str}")
            if self.pipeline_trust_level is not None:
                if self.pipeline_confidence_val != 0.0:
                    confidence_str = f" ({self.pipeline_confidence_val:.2f})"
                else:
                    confidence_str = ""
                coverage_parts = [
                    note for note in self.stage_coverage_notes.values() if note
                ]
                coverage_detail = (" — " + " | ".join(coverage_parts)) if coverage_parts else ""
                lines.append(
                    f"Trust: {self.pipeline_trust_level.value}{confidence_str}{coverage_detail}"
                )
        return "\n".join(lines)


# ── Stage count constant ─────────────────────────────────────────────────

# Pipeline stages 0-4 plus stage 5 (negation-proof / Stage 2.5).
# Stage 5 (STAGE_NEGPROOF) is inserted between stages 3 and 4 in the
# execution order but uses ID=5 to avoid renumbering the formal stage.
_STAGE_COUNT = 6  # stages 0, 1, 2, 3, 4, 5 (negation-proof)

_STAGE_NAMES: dict[int, str] = {
    0: "preflight",
    1: "deps",
    2: "schema",
    3: "pbt",
    4: "formal",
    5: "neg-proof",
}

# ── Module-level console ──────────────────────────────────────────────────

# Module-level console; force_terminal=True so Rich always emits ANSI
# (pytest capsys captures the underlying write calls).
_console: Optional["Console"] = None


def _get_console() -> "Console | None":
    """Return (and lazily create) the module-level Rich Console.

    Returns None when Rich is not installed.

    References:
    - [REF-T17] Click CLI framework -- shared console for all output
    """
    global _console
    if _console is None:
        if HAS_RICH:
            _console = Console(force_terminal=True, highlight=False)
        else:
            _console = None
    return _console


# ── Status helpers ──────────────────────────────────────


_STATUS_STYLES = {
    VerifyStatus.PASS: ("PASS", "bold green"),
    VerifyStatus.FAIL: ("FAIL", "bold red"),
    VerifyStatus.SKIP: ("SKIP", "bold yellow"),
    VerifyStatus.TIMEOUT: ("TIMEOUT", "bold magenta"),
}

# SkillFortify trust level color coding [Scout 9 W2-2]
_TRUST_LEVEL_STYLES: dict[TrustLevel, str] = {
    TrustLevel.FORMALLY_VERIFIED: "bold green",
    TrustLevel.PROPERTY_VERIFIED: "bold blue",
    TrustLevel.SCHEMA_VERIFIED:   "bold yellow",
    TrustLevel.UNVERIFIED:        "bold red",
}


def _status_text(status: VerifyStatus) -> "Text":
    """Return a Rich Text object for a VerifyStatus value.

    References:
    - [REF-T17] Click CLI framework -- colored status indicators
    """
    label, style = _STATUS_STYLES.get(status, (str(status), ""))
    if HAS_RICH:
        return Text(label, style=style)
    return label  # type: ignore[return-value]


def _format_duration_ms(ms: int) -> str:
    """Format milliseconds into a human-readable duration string.

    References:
    - ARCHITECTURE.md Section 8 -- duration display convention
    """
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms / 1000
    return f"{seconds:.2f}s"


# ── Public API ─────────────────────────────────────────


def format_verify_result(result: VerifyResult) -> None:
    """Print the full verification result with Rich formatting.

    Displays:
    - Green "VERIFIED" badge or red "FAIL" badge
    - Table of stages with status (colored), duration, error count
    - For failed stages: show errors with counterexamples
    - Total duration and retry count

    References:
    - [REF-T17] Click CLI framework -- primary output function
    - ARCHITECTURE.md Section 8 -- CLI display spec
    """
    console = _get_console()

    if not HAS_RICH or console is None:
        _format_verify_result_plain(result)
        return

    # ── Header badge ────────────────────────────────────
    if result.verified:
        badge = Text(" VERIFIED ", style="bold white on green")
    else:
        badge = Text(" FAIL ", style="bold white on red")

    console.print()
    console.print(badge)

    # ── Trust level (SkillFortify graduated trust) [Scout 9 W2-2] ───────
    if result.trust_level is not None:
        style = _TRUST_LEVEL_STYLES.get(result.trust_level, "")
        if result.confidence is not None:
            confidence_str = f" ({result.confidence.total / 100.0:.2f})"
        else:
            confidence_str = ""
        coverage_parts = [s.coverage_note for s in result.stages if s.coverage_note]
        coverage_detail = (" — " + " | ".join(coverage_parts)) if coverage_parts else ""
        trust_line = Text(
            f"Trust: {result.trust_level.value}{confidence_str}{coverage_detail}",
            style=style,
        )
        console.print(trust_line)

    console.print()

    # ── Stage table ─────────────────────────────────────
    table = Table(title="Verification Stages", show_lines=False)
    table.add_column("Stage", justify="center", style="cyan", width=6)
    table.add_column("Name", style="bold", width=12)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Errors", justify="center", width=8)

    for stage in result.stages:
        status_txt = _status_text(stage.status)
        error_count = str(len(stage.errors)) if stage.errors else "0"
        table.add_row(
            str(stage.stage),
            stage.name,
            status_txt,
            _format_duration_ms(stage.duration_ms),
            error_count,
        )

    console.print(table)

    # ── Error details for failed stages ─────────────────
    for stage in result.stages:
        if stage.status == VerifyStatus.FAIL and stage.errors:
            console.print()
            error_lines = []
            for err in stage.errors:
                msg = err.get("message", "unknown error")
                line = err.get("line", "")
                line_str = f" (line {line})" if line else ""
                error_lines.append(f"  - {msg}{line_str}")
                # Dafny error translation — Python-friendly explanation
                try:
                    from nightjar.stages.formal import translate_dafny_error
                    translation = translate_dafny_error(msg)
                    if translation["category"] != "other":
                        error_lines.append(f"    Python meaning: {translation['summary']}")
                        error_lines.append(f"    Fix hint: {translation['fix_hint']}")
                except Exception:
                    pass

            error_text = "\n".join(error_lines)

            if stage.counterexample:
                error_text += f"\n\n  Counterexample: {stage.counterexample}"

            panel = Panel(
                error_text,
                title=f"Stage {stage.stage} ({stage.name}) -- Errors",
                border_style="red",
            )
            console.print(panel)

    # ── Footer summary ──────────────────────────────────
    console.print()
    summary_parts = [f"Total duration: {_format_duration_ms(result.total_duration_ms)}"]
    if result.retry_count > 0:
        summary_parts.append(f"Retries: {result.retry_count}")

    console.print(" | ".join(summary_parts))
    console.print()


def _format_verify_result_plain(result: VerifyResult) -> None:
    """Plain-text fallback when Rich is not available.

    References:
    - [REF-T17] Click CLI framework -- graceful degradation
    """
    if result.verified:
        print("VERIFIED -- all stages passed")
    else:
        print("FAIL -- verification did not pass")

    if result.trust_level is not None:
        if result.confidence is not None:
            confidence_str = f" ({result.confidence.total / 100.0:.2f})"
        else:
            confidence_str = ""
        coverage_parts = [s.coverage_note for s in result.stages if s.coverage_note]
        coverage_detail = (" — " + " | ".join(coverage_parts)) if coverage_parts else ""
        print(f"Trust: {result.trust_level.value}{confidence_str}{coverage_detail}")

    for stage in result.stages:
        print(format_stage_result(stage))

    for stage in result.stages:
        if stage.status == VerifyStatus.FAIL and stage.errors:
            print(f"\nStage {stage.stage} ({stage.name}) -- Errors:")
            for err in stage.errors:
                msg = err.get("message", "unknown error")
                print(f"  - {msg}")
                # Dafny error translation — Python-friendly explanation
                try:
                    from nightjar.stages.formal import translate_dafny_error
                    translation = translate_dafny_error(msg)
                    if translation["category"] != "other":
                        print(f"    Python meaning: {translation['summary']}")
                        print(f"    Fix hint: {translation['fix_hint']}")
                except Exception:
                    pass
            if stage.counterexample:
                print(f"  Counterexample: {stage.counterexample}")

    print(f"\nTotal duration: {_format_duration_ms(result.total_duration_ms)}")
    if result.retry_count > 0:
        print(f"Retries: {result.retry_count}")


def format_stage_result(stage: StageResult) -> str:
    """Format a single stage result as a one-line summary string.

    Returns a string like: "Stage 0 (preflight): PASS [12ms]"

    References:
    - [REF-T17] Click CLI framework -- stage line format
    - ARCHITECTURE.md Section 8 -- stage display convention
    """
    status_label = stage.status.value.upper()
    duration = _format_duration_ms(stage.duration_ms)
    error_count = len(stage.errors) if stage.errors else 0
    parts = [f"Stage {stage.stage} ({stage.name}): {status_label} [{duration}]"]
    if error_count > 0:
        parts.append(f"({error_count} error{'s' if error_count != 1 else ''})")
    return " ".join(parts)


def create_progress() -> "Progress":
    """Create a Rich Progress bar for tracking pipeline stages.

    Usage::

        progress = create_progress()
        with progress:
            task = progress.add_task("Verifying...", total=5)
            for stage in stages:
                run_stage(stage)
                progress.advance(task)

    References:
    - [REF-T17] Click CLI framework -- progress display
    - ARCHITECTURE.md Section 8 -- pipeline progress
    """
    if HAS_RICH:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=_get_console(),
        )

    # Fallback: a minimal context manager that mimics Progress interface
    return _FallbackProgress()


class _FallbackProgress:
    """Minimal Progress-compatible fallback when Rich is not installed.

    References:
    - [REF-T17] Click CLI framework -- graceful degradation
    """

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def add_task(self, description: str, total: float = 100.0, **kwargs) -> int:
        """Add a task. Returns a task ID (always 0)."""
        print(f"[progress] {description} (total={total})")
        return 0

    def advance(self, task_id: int, advance: float = 1.0) -> None:
        """Advance the progress bar (no-op in fallback)."""
        pass

    def update(self, task_id: int, **kwargs) -> None:
        """Update task metadata (no-op in fallback)."""
        pass


def format_explain(report: dict) -> None:
    """Format a verification failure report with Rich panels and syntax highlighting.

    Reads the report dict (from .card/verify.json) and prints a
    human-readable explanation of each failure.

    References:
    - [REF-T17] Click CLI framework -- explain command output
    - ARCHITECTURE.md Section 8 -- explain display format
    """
    console = _get_console()

    if not HAS_RICH or console is None:
        _format_explain_plain(report)
        return

    verified = report.get("verified", False)

    if verified:
        console.print(Panel(
            "All stages passed -- no failures to explain.",
            title="Verification Passed",
            border_style="green",
        ))
        return

    # ── Header ──────────────────────────────────────────
    console.print()
    console.print(Text(" VERIFICATION FAILURE ", style="bold white on red"))
    console.print()

    stages = report.get("stages", [])
    duration = report.get("total_duration_ms", 0)

    failed_stages = [s for s in stages if s.get("status") == "fail"]

    if not failed_stages:
        console.print("No failed stages found in report.")
        console.print()
        return

    for stage_data in failed_stages:
        stage_num = stage_data.get("stage", "?")
        name = stage_data.get("name", "unknown")
        errors = stage_data.get("errors", [])

        # Build error content
        lines = []
        for err in errors:
            msg = err.get("message", "unknown error")
            lines.append(f"  - {msg}")
            if "counterexample" in err:
                ce = err["counterexample"]
                lines.append(f"    Counterexample: {ce}")

        content = "\n".join(lines) if lines else "  (no error details)"

        panel = Panel(
            content,
            title=f"Stage {stage_num} -- {name}",
            border_style="red",
        )
        console.print(panel)
        console.print()

    if duration:
        console.print(f"Total duration: {_format_duration_ms(duration)}")
        console.print()


def _format_explain_plain(report: dict) -> None:
    """Plain-text fallback for format_explain when Rich is not available.

    References:
    - [REF-T17] Click CLI framework -- graceful degradation
    """
    verified = report.get("verified", False)

    if verified:
        print("Verification Passed -- no failures to explain.")
        return

    print("=== VERIFICATION FAILURE ===\n")

    stages = report.get("stages", [])
    failed_stages = [s for s in stages if s.get("status") == "fail"]

    if not failed_stages:
        print("No failed stages found in report.")
        return

    for stage_data in failed_stages:
        stage_num = stage_data.get("stage", "?")
        name = stage_data.get("name", "unknown")
        errors = stage_data.get("errors", [])

        print(f"Stage {stage_num} ({name}): FAIL")
        for err in errors:
            msg = err.get("message", "unknown error")
            print(f"  - {msg}")
            if "counterexample" in err:
                print(f"    Counterexample: {err['counterexample']}")
        print()

    duration = report.get("total_duration_ms", 0)
    if duration:
        print(f"Total duration: {_format_duration_ms(duration)}")
