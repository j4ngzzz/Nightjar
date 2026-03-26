"""Rich CLI output formatting.

Provides colored, structured terminal output for verification results,
progress tracking, and failure explanation.

References:
- [REF-T17] Click CLI framework -- display integrates with Click commands
- ARCHITECTURE.md Section 8 -- CLI design
"""

from typing import Optional

from contractd.types import StageResult, VerifyResult, VerifyStatus

# Graceful Rich import -- fall back to plain text if Rich is not installed.
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Module-level console; force_terminal=True so Rich always emits ANSI
# (pytest capsys captures the underlying write calls).
_console: Optional["Console"] = None


def _get_console() -> "Console":
    """Return (and lazily create) the module-level Rich Console.

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

    for stage in result.stages:
        print(format_stage_result(stage))

    for stage in result.stages:
        if stage.status == VerifyStatus.FAIL and stage.errors:
            print(f"\nStage {stage.stage} ({stage.name}) -- Errors:")
            for err in stage.errors:
                msg = err.get("message", "unknown error")
                print(f"  - {msg}")
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
