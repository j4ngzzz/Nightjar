"""VS Code problem matcher output formatter.

Converts Nightjar VerifyResult objects into lines that match the VS Code
problem matcher pattern defined in .vscode/tasks.json:

    ^(.+):(\\d+):(\\d+):\\s+(error|warning):\\s+(.+)$

Each output line is:

    file_path:line:column: severity: message

Where:
- file_path  — the spec file path (or "nightjar" if not provided)
- line       — line number from the error dict if present, else 1
- column     — column number from the error dict if present, else 1
- severity   — "error" for FAIL stages, "warning" for TIMEOUT stages
- message    — stage name + error message

PASS and SKIP stages produce no output.

References:
- VS Code Tasks documentation: https://code.visualstudio.com/docs/editor/tasks
- VS Code Problem Matchers: https://code.visualstudio.com/docs/editor/tasks#_processing-task-output-with-problem-matchers
"""

from nightjar.types import StageResult, VerifyResult, VerifyStatus

_FALLBACK_FILE = "nightjar"


def _stage_severity(status: VerifyStatus) -> str | None:
    """Return the VS Code severity string for a stage status, or None to skip."""
    if status == VerifyStatus.FAIL:
        return "error"
    if status == VerifyStatus.TIMEOUT:
        return "warning"
    return None  # PASS and SKIP produce no output


def _format_stage_lines(
    stage: StageResult,
    file_path: str,
) -> list[str]:
    """Produce one or more output lines for a single stage result.

    For stages with structured errors, each error becomes one line.
    For stages with no errors, a single generic line is emitted.

    Args:
        stage:     The StageResult to format.
        file_path: The file reference to use (e.g. ".card/payment.card.md").

    Returns:
        A list of formatted "file:line:col: severity: message" strings.
    """
    severity = _stage_severity(stage.status)
    if severity is None:
        return []

    lines: list[str] = []

    if stage.errors:
        for err in stage.errors:
            msg = err.get("message", "unknown error")
            line = int(err.get("line", 1))
            col = int(err.get("column", 1))
            # Sanitise: VS Code regex requires at least 1 for line/col
            line = max(1, line)
            col = max(1, col)
            # Compose a message that includes the stage name for context
            full_msg = f"Stage {stage.stage} {stage.name} — {msg}"
            lines.append(f"{file_path}:{line}:{col}: {severity}: {full_msg}")
    else:
        # No structured errors — emit one generic line so the stage is visible
        lines.append(
            f"{file_path}:1:1: {severity}: "
            f"Stage {stage.stage} {stage.name} — verification {stage.status.value}"
        )

    return lines


def format_vscode_output(result: VerifyResult, spec_path: str = "") -> str:
    """Format verification results for VS Code problem matcher.

    Output format per line:
        file_path:line:column: severity: message

    Where severity is 'error' for FAIL, 'warning' for TIMEOUT.
    Each stage failure becomes one or more output lines.  PASS and SKIP
    stages produce no output.

    Example output::

        .card/payment.card.md:1:1: error: Stage 3 pbt — Counterexample found: amount=-0.01
        .card/payment.card.md:1:1: warning: Stage 4 formal — verification timeout

    Args:
        result:    The VerifyResult from the pipeline.
        spec_path: Path to the .card.md file being verified.  Used as the
                   file reference in each output line.  Defaults to the
                   string "nightjar" if empty or not provided.

    Returns:
        A newline-joined string of zero or more problem matcher lines.
        Returns an empty string when all stages pass.
    """
    file_ref = spec_path.strip() if spec_path and spec_path.strip() else _FALLBACK_FILE

    all_lines: list[str] = []
    for stage in result.stages:
        all_lines.extend(_format_stage_lines(stage, file_ref))

    return "\n".join(all_lines)
