"""Tests for nightjar.gitnexus_hooks — blast radius warnings before regeneration.

TDD: Tests written FIRST before implementation.

Pipeline:
    nightjar build <spec>
    → gitnexus_hooks.check_blast_radius(symbol_name)
    → BlastRadiusResult (dependents_count, is_high_risk, affected_modules)
    → warn_before_regeneration() returns True/False

References:
- nightjar-upgrade-plan.md U5.2 (lines 640-659)
- GitNexus CLI: `npx gitnexus impact <target> --direction upstream`
- CLAUDE.md: "MUST run impact analysis before editing any symbol"
"""
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_impact_json(
    symbol: str,
    impacted_count: int,
    risk: str,
    direct: int = 0,
    affected_modules: list | None = None,
) -> str:
    return json.dumps({
        "target": {"id": f"Function:src/{symbol}", "name": symbol.split(".")[-1]},
        "direction": "upstream",
        "impactedCount": impacted_count,
        "risk": risk,
        "summary": {
            "direct": direct,
            "processes_affected": 0,
            "modules_affected": len(affected_modules or []),
        },
        "affected_processes": [],
        "affected_modules": affected_modules or [],
        "byDepth": {},
    })


def _make_mock_proc(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = ""
    return proc


# ---------------------------------------------------------------------------
# check_blast_radius()
# ---------------------------------------------------------------------------

class TestBlastRadiusCheck:
    """Tests for check_blast_radius(symbol_name) → BlastRadiusResult."""

    def test_gitnexus_hook_warns_on_high_blast_radius(self):
        """HIGH risk symbols trigger is_high_risk=True on default threshold."""
        from nightjar.gitnexus_hooks import check_blast_radius

        affected = ["billing", "refund", "audit"]
        stdout = _make_impact_json(
            "payment.deduct",
            impacted_count=5,
            risk="HIGH",
            direct=3,
            affected_modules=affected,
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            result = check_blast_radius("payment.deduct")

        assert result.is_high_risk is True
        assert result.dependents_count >= 3

    def test_gitnexus_hook_allows_low_blast_radius(self):
        """LOW risk symbols do not trigger a warning."""
        from nightjar.gitnexus_hooks import check_blast_radius

        stdout = _make_impact_json(
            "utils.helper",
            impacted_count=1,
            risk="LOW",
            direct=1,
            affected_modules=["tests"],
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            result = check_blast_radius("utils.helper")

        assert result.is_high_risk is False

    def test_blast_radius_result_has_dependents_list(self):
        """BlastRadiusResult.affected_modules lists module names."""
        from nightjar.gitnexus_hooks import check_blast_radius

        affected = ["billing", "refund"]
        stdout = _make_impact_json(
            "payment.process",
            impacted_count=2,
            risk="MEDIUM",
            direct=2,
            affected_modules=affected,
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            result = check_blast_radius("payment.process")

        assert "billing" in result.affected_modules
        assert "refund" in result.affected_modules

    def test_symbol_not_found_returns_no_risk(self):
        """Symbol not in GitNexus index → is_high_risk=False, dependents=0."""
        from nightjar.gitnexus_hooks import check_blast_radius

        error_json = json.dumps({"error": "Target 'unknown.func' not found"})
        with patch("subprocess.run", return_value=_make_mock_proc(error_json)):
            result = check_blast_radius("unknown.func")

        assert result.is_high_risk is False
        assert result.dependents_count == 0

    def test_gitnexus_unavailable_returns_no_risk(self):
        """If gitnexus CLI is not available, return safe default (no warning)."""
        from nightjar.gitnexus_hooks import check_blast_radius

        with patch("subprocess.run", side_effect=FileNotFoundError("npx not found")):
            result = check_blast_radius("payment.deduct")

        assert result.is_high_risk is False  # safe default — don't block on tool absence

    def test_custom_threshold_respected(self):
        """dependents_count > threshold → is_high_risk=True even for MEDIUM risk."""
        from nightjar.gitnexus_hooks import check_blast_radius

        stdout = _make_impact_json(
            "core.process",
            impacted_count=2,
            risk="MEDIUM",
            direct=2,
            affected_modules=["alpha", "beta"],
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            # threshold=1: 2 dependents > 1 → high risk
            result_hi = check_blast_radius("core.process", threshold=1)
            # threshold=5: 2 dependents < 5 → not high risk
            result_lo = check_blast_radius("core.process", threshold=5)

        assert result_hi.is_high_risk is True
        assert result_lo.is_high_risk is False


# ---------------------------------------------------------------------------
# warn_before_regeneration()
# ---------------------------------------------------------------------------

class TestWarnBeforeRegeneration:
    """Tests for warn_before_regeneration(symbol_name) → bool."""

    def test_high_blast_radius_returns_true(self):
        """warn_before_regeneration() returns True when blast radius is high."""
        from nightjar.gitnexus_hooks import warn_before_regeneration

        affected = ["billing", "refund", "audit"]
        stdout = _make_impact_json(
            "payment.deduct", impacted_count=5, risk="HIGH",
            direct=3, affected_modules=affected,
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            should_warn = warn_before_regeneration("payment.deduct")

        assert should_warn is True

    def test_low_blast_radius_returns_false(self):
        """warn_before_regeneration() returns False when blast radius is low."""
        from nightjar.gitnexus_hooks import warn_before_regeneration

        stdout = _make_impact_json(
            "helper.parse", impacted_count=0, risk="LOW",
        )
        with patch("subprocess.run", return_value=_make_mock_proc(stdout)):
            should_warn = warn_before_regeneration("helper.parse")

        assert should_warn is False

    def test_format_warning_message_contains_symbol_and_dependents(self):
        """format_blast_radius_warning() includes symbol name and dependent modules."""
        from nightjar.gitnexus_hooks import format_blast_radius_warning, BlastRadiusResult

        result = BlastRadiusResult(
            symbol_name="payment.deduct",
            dependents_count=3,
            affected_modules=["billing", "refund", "audit"],
            risk="HIGH",
            is_high_risk=True,
        )
        warning = format_blast_radius_warning(result)

        assert "payment.deduct" in warning
        assert "billing" in warning or "3" in warning
