"""Tests for nightjar Shadow CI mode.

TDD: Tests written FIRST before implementation.

Reference: Scout 7 Feature 2 — Shadow CI Mode (non-blocking, always exit 0)
The viral moment: PR comment showing Nightjar caught SQL injection that passed all tests.
"""
import json
import pytest
from unittest.mock import MagicMock, patch


class TestShadowCIReport:
    """Tests for shadow_ci.py structured report output."""

    def test_shadow_ci_always_exits_zero(self, tmp_path):
        """Shadow CI NEVER fails the check — always exits 0.

        Scout 7: '50% of devs don't verify AI code. Shadow mode removes friction entirely.'
        The key: developers won't disable it if it never blocks them.
        """
        from nightjar.shadow_ci import run_shadow_ci

        # Even with a failing verification report, shadow CI exits 0
        failing_report = {
            "verified": False,
            "confidence_score": 30,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "fail",
                 "errors": [{"message": "SQL injection vulnerability detected"}]},
            ],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(failing_report), encoding="utf-8")

        result = run_shadow_ci(report_path=str(report_path), mode="shadow")
        assert result.exit_code == 0  # ALWAYS zero in shadow mode

    def test_shadow_ci_outputs_structured_report(self, tmp_path):
        """Shadow CI outputs a structured report dict with required fields."""
        from nightjar.shadow_ci import run_shadow_ci

        report = {
            "verified": True,
            "confidence_score": 95,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
                {"stage": 4, "name": "formal", "status": "pass", "errors": []},
            ],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = run_shadow_ci(report_path=str(report_path), mode="shadow")

        # Structured report must contain these fields
        assert hasattr(result, "exit_code")
        assert hasattr(result, "report")
        assert "verified" in result.report or "status" in result.report
        assert "confidence_score" in result.report or "score" in result.report

    def test_shadow_ci_captures_security_violations(self, tmp_path):
        """Shadow CI captures and reports security violations without blocking."""
        from nightjar.shadow_ci import run_shadow_ci

        report = {
            "verified": False,
            "confidence_score": 40,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
                {
                    "stage": 3,
                    "name": "pbt",
                    "status": "fail",
                    "errors": [
                        {
                            "message": "SQL injection: unsanitized input reaches query",
                            "counterexample": {"user_input": "' OR 1=1--"},
                        }
                    ],
                },
            ],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = run_shadow_ci(report_path=str(report_path), mode="shadow")

        # Does not block (exit 0)
        assert result.exit_code == 0
        # Reports the violation
        assert result.report is not None
        report_str = json.dumps(result.report)
        assert "sql" in report_str.lower() or "injection" in report_str.lower() or "fail" in report_str.lower()

    def test_shadow_ci_generates_pr_comment(self, tmp_path):
        """Shadow CI generates a PR comment-ready markdown string."""
        from nightjar.shadow_ci import run_shadow_ci, format_pr_comment

        report = {
            "verified": False,
            "confidence_score": 55,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
                {
                    "stage": 3,
                    "name": "pbt",
                    "status": "fail",
                    "errors": [{"message": "Property violated: output >= 0"}],
                },
            ],
        }

        comment = format_pr_comment(report)
        # Must be markdown
        assert isinstance(comment, str)
        assert len(comment) > 0
        # Must mention Nightjar
        assert "nightjar" in comment.lower() or "Nightjar" in comment

    def test_shadow_ci_report_includes_stage_summary(self, tmp_path):
        """Shadow CI report lists all stages and their status."""
        from nightjar.shadow_ci import run_shadow_ci

        report = {
            "verified": True,
            "confidence_score": 100,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
                {"stage": 1, "name": "deps", "status": "pass", "errors": []},
                {"stage": 2, "name": "schema", "status": "pass", "errors": []},
                {"stage": 3, "name": "pbt", "status": "pass", "errors": []},
                {"stage": 4, "name": "formal", "status": "pass", "errors": []},
            ],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = run_shadow_ci(report_path=str(report_path), mode="shadow")
        assert result.exit_code == 0
        # Report should summarize all 5 stages
        report_str = json.dumps(result.report)
        assert "preflight" in report_str or "stages" in report_str

    def test_shadow_ci_missing_report_still_exits_zero(self, tmp_path):
        """Shadow CI exits 0 even if no verify.json exists."""
        from nightjar.shadow_ci import run_shadow_ci

        result = run_shadow_ci(
            report_path=str(tmp_path / "nonexistent.json"),
            mode="shadow",
        )
        assert result.exit_code == 0

    def test_shadow_ci_strict_mode_fails_on_violations(self, tmp_path):
        """In strict (non-shadow) mode, violations cause non-zero exit."""
        from nightjar.shadow_ci import run_shadow_ci

        report = {
            "verified": False,
            "confidence_score": 30,
            "stages": [
                {"stage": 0, "name": "preflight", "status": "fail",
                 "errors": [{"message": "Invariant violated"}]},
            ],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = run_shadow_ci(report_path=str(report_path), mode="strict")
        assert result.exit_code != 0  # strict mode DOES fail
