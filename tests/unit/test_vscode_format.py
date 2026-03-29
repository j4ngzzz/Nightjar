"""Tests for the VS Code problem matcher output formatter.

Tests verify that format_vscode_output produces lines that:
  - Match the regex pattern used in .vscode/tasks.json
  - Use 'error' severity for FAIL stages
  - Use 'warning' severity for TIMEOUT stages
  - Produce no output for PASS or SKIP stages
  - Include spec_path as the file reference
  - Fall back to 'nightjar' when spec_path is not provided

TDD: these tests were written before the implementation.
"""

import re
import pytest

from nightjar.types import StageResult, VerifyResult, VerifyStatus
from nightjar.formatters.vscode import format_vscode_output


# The same regex pattern used in .vscode/tasks.json
VSCODE_PATTERN = re.compile(
    r"^(.+):(\d+):(\d+):\s+(error|warning|info):\s+(.+)$"
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_result(stages: list[StageResult], verified: bool = False) -> VerifyResult:
    return VerifyResult(verified=verified, stages=stages)


def _parse_line(line: str) -> re.Match:
    """Assert a line matches the VS Code problem matcher pattern and return the match."""
    m = VSCODE_PATTERN.match(line)
    assert m is not None, f"Line does not match VS Code pattern: {line!r}"
    return m


# ── Test 1: PASS stage produces no output ────────────────────────────────────


def test_pass_stage_produces_no_output():
    stage = StageResult(stage=0, name="preflight", status=VerifyStatus.PASS)
    result = _make_result([stage], verified=True)
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    assert output.strip() == "", f"Expected empty output for PASS, got: {output!r}"


# ── Test 2: SKIP stage produces no output ────────────────────────────────────


def test_skip_stage_produces_no_output():
    stage = StageResult(stage=4, name="formal", status=VerifyStatus.SKIP)
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/auth.card.md")
    assert output.strip() == "", f"Expected empty output for SKIP, got: {output!r}"


# ── Test 3: FAIL stage emits 'error' severity ────────────────────────────────


def test_fail_stage_emits_error_severity():
    stage = StageResult(
        stage=3,
        name="pbt",
        status=VerifyStatus.FAIL,
        errors=[{"message": "Counterexample found: amount=-0.01"}],
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) >= 1
    m = _parse_line(lines[0])
    assert m.group(4) == "error", f"Expected severity 'error', got {m.group(4)!r}"


# ── Test 4: TIMEOUT stage emits 'warning' severity ───────────────────────────


def test_timeout_stage_emits_warning_severity():
    stage = StageResult(
        stage=4,
        name="formal",
        status=VerifyStatus.TIMEOUT,
        errors=[{"message": "Timeout after 60s"}],
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) >= 1
    m = _parse_line(lines[0])
    assert m.group(4) == "warning", f"Expected severity 'warning', got {m.group(4)!r}"


# ── Test 5: spec_path appears as the file reference ──────────────────────────


def test_spec_path_used_as_file_reference():
    stage = StageResult(
        stage=2,
        name="schema",
        status=VerifyStatus.FAIL,
        errors=[{"message": "Schema validation failed"}],
    )
    result = _make_result([stage])
    spec = ".card/my_module.card.md"
    output = format_vscode_output(result, spec_path=spec)
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) >= 1
    m = _parse_line(lines[0])
    assert m.group(1) == spec, f"Expected file {spec!r}, got {m.group(1)!r}"


# ── Test 6: fallback to 'nightjar' when spec_path not provided ───────────────


def test_fallback_file_when_no_spec_path():
    stage = StageResult(
        stage=1,
        name="deps",
        status=VerifyStatus.FAIL,
        errors=[{"message": "Dependency audit failed"}],
    )
    result = _make_result([stage])
    output = format_vscode_output(result)  # no spec_path
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) >= 1
    m = _parse_line(lines[0])
    assert m.group(1) == "nightjar", f"Expected fallback file 'nightjar', got {m.group(1)!r}"


# ── Test 7: multiple errors in a single stage each become a line ─────────────


def test_multiple_errors_per_stage_each_get_a_line():
    stage = StageResult(
        stage=3,
        name="pbt",
        status=VerifyStatus.FAIL,
        errors=[
            {"message": "Counterexample: amount=-0.01"},
            {"message": "Counterexample: amount=0"},
            {"message": "Counterexample: currency=''"},
        ],
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) == 3, f"Expected 3 lines (one per error), got {len(lines)}: {lines}"
    for line in lines:
        m = _parse_line(line)
        assert m.group(4) == "error"


# ── Test 8: stage with no errors still emits one generic line for FAIL ───────


def test_fail_stage_with_no_errors_emits_generic_line():
    stage = StageResult(
        stage=0,
        name="preflight",
        status=VerifyStatus.FAIL,
        errors=[],  # no structured errors
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/test.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) == 1
    m = _parse_line(lines[0])
    assert m.group(4) == "error"
    # message should reference the stage name
    assert "preflight" in m.group(5).lower() or "stage" in m.group(5).lower()


# ── Test 9: TIMEOUT stage with no errors emits one generic warning line ──────


def test_timeout_stage_with_no_errors_emits_generic_warning():
    stage = StageResult(
        stage=4,
        name="formal",
        status=VerifyStatus.TIMEOUT,
        errors=[],
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/auth.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) == 1
    m = _parse_line(lines[0])
    assert m.group(4) == "warning"


# ── Test 10: line number from Dafny error is used when available ─────────────


def test_dafny_line_number_propagated():
    stage = StageResult(
        stage=4,
        name="formal",
        status=VerifyStatus.FAIL,
        errors=[{"message": "Postcondition might not hold", "line": 42, "column": 7}],
    )
    result = _make_result([stage])
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) == 1
    m = _parse_line(lines[0])
    assert m.group(2) == "42", f"Expected line 42, got {m.group(2)!r}"
    assert m.group(3) == "7", f"Expected column 7, got {m.group(3)!r}"


# ── Test 11: mixed stages — only FAIL/TIMEOUT produce output ─────────────────


def test_mixed_stages_only_fail_and_timeout_produce_output():
    stages = [
        StageResult(stage=0, name="preflight", status=VerifyStatus.PASS),
        StageResult(stage=1, name="deps", status=VerifyStatus.PASS),
        StageResult(
            stage=2,
            name="schema",
            status=VerifyStatus.FAIL,
            errors=[{"message": "Schema error"}],
        ),
        StageResult(stage=3, name="pbt", status=VerifyStatus.SKIP),
        StageResult(
            stage=4,
            name="formal",
            status=VerifyStatus.TIMEOUT,
            errors=[],
        ),
    ]
    result = _make_result(stages)
    output = format_vscode_output(result, spec_path=".card/test.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    # schema FAIL (1 error) + formal TIMEOUT (generic) = 2 lines
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"
    severities = [_parse_line(l).group(4) for l in lines]
    assert "error" in severities
    assert "warning" in severities


# ── Test 12: output lines all match the tasks.json regex ─────────────────────


def test_all_output_lines_match_tasks_json_regex():
    """Validate that every output line the formatter produces matches the
    exact regex defined in .vscode/tasks.json's problemMatcher."""
    stages = [
        StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.FAIL,
            errors=[
                {"message": "Counterexample: x=-1"},
                {"message": "Counterexample: x=0", "line": 10, "column": 1},
            ],
        ),
        StageResult(
            stage=4,
            name="formal",
            status=VerifyStatus.TIMEOUT,
        ),
    ]
    result = _make_result(stages)
    output = format_vscode_output(result, spec_path=".card/payment.card.md")
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) >= 1
    for line in lines:
        assert VSCODE_PATTERN.match(line), (
            f"Line does not match tasks.json regex pattern: {line!r}"
        )
