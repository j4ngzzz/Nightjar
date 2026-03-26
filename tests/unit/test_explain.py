"""Tests for contractd explain module.

Reference: [REF-P06] DafnyPro structured errors — error formatting approach
Architecture: docs/ARCHITECTURE.md Section 8 (CLI Design)

TDD: These tests were written FIRST, before the implementation.
"""

import json
import os
from pathlib import Path

import pytest

from contractd.explain import ExplainOutput, load_report, explain_failure, format_explanation


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def tmp_card_dir(tmp_path):
    """Create a temporary .card/ directory with verify.json."""
    card_dir = tmp_path / ".card"
    card_dir.mkdir()
    return card_dir


@pytest.fixture
def failing_report() -> dict:
    """A verification report with a stage 3 (PBT) failure."""
    return {
        "verified": False,
        "stages": [
            {
                "stage": 0,
                "name": "preflight",
                "status": "pass",
                "duration_ms": 12,
                "errors": [],
            },
            {
                "stage": 1,
                "name": "deps",
                "status": "pass",
                "duration_ms": 45,
                "errors": [],
            },
            {
                "stage": 2,
                "name": "schema",
                "status": "pass",
                "duration_ms": 80,
                "errors": [],
            },
            {
                "stage": 3,
                "name": "pbt",
                "status": "fail",
                "duration_ms": 1500,
                "errors": [
                    {
                        "message": "Property violated: output >= 0",
                        "counterexample": {"input": -5, "output": -5},
                    }
                ],
            },
        ],
        "total_duration_ms": 2500,
    }


@pytest.fixture
def passing_report() -> dict:
    """A verification report where all stages pass."""
    return {
        "verified": True,
        "stages": [
            {
                "stage": 0,
                "name": "preflight",
                "status": "pass",
                "duration_ms": 10,
                "errors": [],
            },
            {
                "stage": 1,
                "name": "deps",
                "status": "pass",
                "duration_ms": 30,
                "errors": [],
            },
        ],
        "total_duration_ms": 40,
    }


@pytest.fixture
def formal_failure_report() -> dict:
    """A verification report with a stage 4 (formal/Dafny) failure."""
    return {
        "verified": False,
        "stages": [
            {
                "stage": 0,
                "name": "preflight",
                "status": "pass",
                "duration_ms": 10,
                "errors": [],
            },
            {
                "stage": 4,
                "name": "formal",
                "status": "fail",
                "duration_ms": 5000,
                "errors": [
                    {
                        "message": "Dafny postcondition might not hold",
                    },
                    {
                        "message": "Assertion violation at line 42",
                    },
                ],
            },
        ],
        "total_duration_ms": 5010,
    }


@pytest.fixture
def multi_failure_report() -> dict:
    """A verification report with multiple stage failures."""
    return {
        "verified": False,
        "stages": [
            {
                "stage": 0,
                "name": "preflight",
                "status": "fail",
                "duration_ms": 5,
                "errors": [
                    {"message": "Missing required field: contract.inputs"},
                ],
            },
            {
                "stage": 1,
                "name": "deps",
                "status": "skip",
                "duration_ms": 0,
                "errors": [],
            },
        ],
        "total_duration_ms": 5,
    }


@pytest.fixture
def schema_failure_report() -> dict:
    """A verification report with a stage 2 (schema) failure."""
    return {
        "verified": False,
        "stages": [
            {
                "stage": 2,
                "name": "schema",
                "status": "fail",
                "duration_ms": 100,
                "errors": [
                    {"message": "Schema validation failed: missing 'amount' field"},
                ],
            },
        ],
        "total_duration_ms": 100,
    }


@pytest.fixture
def timeout_failure_report() -> dict:
    """A verification report with a timeout."""
    return {
        "verified": False,
        "stages": [
            {
                "stage": 4,
                "name": "formal",
                "status": "timeout",
                "duration_ms": 30000,
                "errors": [
                    {"message": "Dafny verification timed out after 30s"},
                ],
            },
        ],
        "total_duration_ms": 30000,
    }


# ── load_report tests ───────────────────────────────────


class TestLoadReport:
    """Tests for load_report(): loading .card/verify.json."""

    def test_loads_existing_report(self, tmp_card_dir, failing_report):
        """load_report returns parsed dict when verify.json exists."""
        report_path = tmp_card_dir / "verify.json"
        report_path.write_text(json.dumps(failing_report), encoding="utf-8")

        # Pass a path to a .card.md file in the .card/ directory
        contract_path = str(tmp_card_dir / "test.card.md")
        result = load_report(contract_path)

        assert result is not None
        assert result["verified"] is False
        assert len(result["stages"]) == 4

    def test_returns_none_when_no_report(self, tmp_path):
        """load_report returns None when verify.json does not exist."""
        contract_path = str(tmp_path / ".card" / "test.card.md")
        result = load_report(contract_path)
        assert result is None

    def test_loads_from_default_card_dir(self, tmp_path, failing_report):
        """load_report falls back to .card/verify.json in CWD."""
        card_dir = tmp_path / ".card"
        card_dir.mkdir()
        report_path = card_dir / "verify.json"
        report_path.write_text(json.dumps(failing_report), encoding="utf-8")

        # Use the .card dir's parent as working context
        contract_path = str(card_dir / "test.card.md")
        result = load_report(contract_path)
        assert result is not None
        assert result["verified"] is False


# ── explain_failure tests ────────────────────────────────


class TestExplainFailure:
    """Tests for explain_failure(): analyzing failure reports."""

    def test_returns_explain_output_dataclass(self, failing_report):
        """explain_failure returns an ExplainOutput dataclass."""
        result = explain_failure(failing_report)
        assert isinstance(result, ExplainOutput)

    def test_identifies_failed_stage(self, failing_report):
        """explain_failure correctly identifies which stage failed."""
        result = explain_failure(failing_report)
        assert result.failed_stage == 3
        assert result.stage_name == "pbt"

    def test_extracts_error_messages(self, failing_report):
        """explain_failure extracts error messages from the failed stage."""
        result = explain_failure(failing_report)
        assert len(result.error_messages) == 1
        assert "Property violated: output >= 0" in result.error_messages[0]

    def test_extracts_counterexamples(self, failing_report):
        """explain_failure extracts counterexamples from PBT failures."""
        result = explain_failure(failing_report)
        assert len(result.counterexamples) == 1
        assert result.counterexamples[0] == {"input": -5, "output": -5}

    def test_identifies_invariant_violated(self, failing_report):
        """explain_failure extracts the violated invariant."""
        result = explain_failure(failing_report)
        assert "output >= 0" in result.invariant_violated

    def test_suggests_fix_for_pbt_failure(self, failing_report):
        """explain_failure provides a suggested fix for PBT failures."""
        result = explain_failure(failing_report)
        assert result.suggested_fix != ""
        assert len(result.suggested_fix) > 10  # Non-trivial suggestion

    def test_formal_failure_stage(self, formal_failure_report):
        """explain_failure handles stage 4 (Dafny formal) failures."""
        result = explain_failure(formal_failure_report)
        assert result.failed_stage == 4
        assert result.stage_name == "formal"
        assert len(result.error_messages) == 2

    def test_formal_failure_suggested_fix(self, formal_failure_report):
        """explain_failure suggests Dafny-related fix for formal failures."""
        result = explain_failure(formal_failure_report)
        assert result.suggested_fix != ""

    def test_preflight_failure(self, multi_failure_report):
        """explain_failure handles preflight (stage 0) failure."""
        result = explain_failure(multi_failure_report)
        assert result.failed_stage == 0
        assert result.stage_name == "preflight"

    def test_schema_failure(self, schema_failure_report):
        """explain_failure handles schema (stage 2) failure."""
        result = explain_failure(schema_failure_report)
        assert result.failed_stage == 2
        assert result.stage_name == "schema"

    def test_timeout_failure(self, timeout_failure_report):
        """explain_failure handles timeout status."""
        result = explain_failure(timeout_failure_report)
        assert result.failed_stage == 4
        assert result.stage_name == "formal"

    def test_all_stages_summary(self, failing_report):
        """explain_failure includes a summary of all stages."""
        result = explain_failure(failing_report)
        assert len(result.all_stages_summary) == 4
        # Each summary entry should have stage, name, and status
        for entry in result.all_stages_summary:
            assert "stage" in entry
            assert "name" in entry
            assert "status" in entry

    def test_passing_report_returns_no_failure(self, passing_report):
        """explain_failure on a passing report returns stage -1 (no failure)."""
        result = explain_failure(passing_report)
        assert result.failed_stage == -1
        assert result.stage_name == ""
        assert result.error_messages == []
        assert result.suggested_fix == ""


# ── format_explanation tests ─────────────────────────────


class TestFormatExplanation:
    """Tests for format_explanation(): plain text formatting."""

    def test_format_contains_stage_info(self, failing_report):
        """Formatted output mentions the failed stage name and number."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert "Stage 3" in text
        assert "pbt" in text.lower()

    def test_format_contains_error_messages(self, failing_report):
        """Formatted output includes error messages."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert "Property violated: output >= 0" in text

    def test_format_contains_counterexample(self, failing_report):
        """Formatted output includes counterexample details."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert "counterexample" in text.lower() or "Counterexample" in text

    def test_format_contains_suggested_fix(self, failing_report):
        """Formatted output includes a suggested fix."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert "fix" in text.lower() or "suggestion" in text.lower() or "Fix" in text

    def test_format_contains_stages_summary(self, failing_report):
        """Formatted output includes a summary of all stages."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert "preflight" in text.lower()
        assert "pass" in text.lower()

    def test_format_passing_report(self, passing_report):
        """Formatted output for passing report indicates no failures."""
        explanation = explain_failure(passing_report)
        text = format_explanation(explanation)
        assert "no failure" in text.lower() or "passed" in text.lower()

    def test_format_is_string(self, failing_report):
        """format_explanation returns a string."""
        explanation = explain_failure(failing_report)
        text = format_explanation(explanation)
        assert isinstance(text, str)

    def test_format_formal_failure(self, formal_failure_report):
        """Formatted output for formal failure includes Dafny context."""
        explanation = explain_failure(formal_failure_report)
        text = format_explanation(explanation)
        assert "Stage 4" in text
        assert "formal" in text.lower()


# ── ExplainOutput dataclass tests ────────────────────────


class TestExplainOutput:
    """Tests for the ExplainOutput dataclass itself."""

    def test_create_explain_output(self):
        """ExplainOutput can be created with all required fields."""
        output = ExplainOutput(
            failed_stage=3,
            stage_name="pbt",
            invariant_violated="output >= 0",
            error_messages=["Property violated"],
            counterexamples=[{"input": -1}],
            suggested_fix="Add input validation",
            all_stages_summary=[{"stage": 0, "name": "preflight", "status": "pass"}],
        )
        assert output.failed_stage == 3
        assert output.stage_name == "pbt"
        assert output.invariant_violated == "output >= 0"
        assert len(output.error_messages) == 1
        assert len(output.counterexamples) == 1
        assert output.suggested_fix == "Add input validation"
        assert len(output.all_stages_summary) == 1

    def test_explain_output_defaults(self):
        """ExplainOutput fields work correctly with empty lists."""
        output = ExplainOutput(
            failed_stage=-1,
            stage_name="",
            invariant_violated="",
            error_messages=[],
            counterexamples=[],
            suggested_fix="",
            all_stages_summary=[],
        )
        assert output.failed_stage == -1
        assert output.error_messages == []
        assert output.counterexamples == []
