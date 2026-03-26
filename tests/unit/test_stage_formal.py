"""Tests for Stage 4 — Dafny Formal Verification.

Validates that the formal stage runs `dafny verify` on generated Dafny code,
parses results, and reports structured errors per [REF-P06] DafnyPro format.

References:
- [REF-T01] Dafny — verification-aware programming language
- [REF-P02] Vericoding benchmark — 82-96% Dafny success rate
- [REF-P06] DafnyPro — structured error format with assertion batch IDs
- [REF-C01] Tiered invariants — only 'formal' tier reaches Stage 4
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from contractd.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyStatus,
)
from contractd.stages.formal import run_formal, parse_dafny_output


def _make_spec(invariants: list[Invariant]) -> CardSpec:
    """Helper to build a minimal CardSpec with given invariants."""
    return CardSpec(
        card_version="1.0",
        id="test-module",
        title="Test Module",
        status="draft",
        module=ModuleBoundary(owns=["func_a()"]),
        contract=Contract(
            inputs=[ContractInput(name="x", type="integer", constraints="x > 0")],
            outputs=[ContractOutput(name="Result", type="integer")],
        ),
        invariants=invariants,
    )


SAMPLE_DFY_CODE = '''
method Process(x: int) returns (r: int)
  requires x > 0
  ensures r > 0
{
  r := x * 2;
}
'''


class TestRunFormal:
    """Tests for run_formal function."""

    def test_returns_stage_result(self):
        """run_formal returns StageResult with stage=4 and name='formal'."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.return_value = (0, "", "")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert isinstance(result, StageResult)
        assert result.stage == 4
        assert result.name == "formal"

    def test_pass_when_dafny_succeeds(self):
        """Stage 4 PASS when dafny verify exits 0."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.return_value = (0, "Dafny program verifier finished with 1 verified, 0 errors\n", "")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.PASS

    def test_fail_when_dafny_reports_errors(self):
        """Stage 4 FAIL when dafny verify reports verification errors."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        error_output = (
            "test.dfy(5,2): Error: a postcondition could not be proved on this return path\n"
            "test.dfy(3,10): Related location: this is the postcondition that could not be proved\n"
            "Dafny program verifier finished with 0 verified, 1 error\n"
        )
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.return_value = (4, error_output, "")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0

    def test_skip_when_no_formal_invariants(self):
        """Stage 4 SKIP when spec has no formal tier invariants."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.PROPERTY,
                      statement="Some property"),
        ])
        result = run_formal(spec, SAMPLE_DFY_CODE)
        assert result.status == VerifyStatus.SKIP

    def test_skip_when_only_example_invariants(self):
        """Stage 4 SKIP for example-tier invariants."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.EXAMPLE,
                      statement="process(5) returns 10"),
        ])
        result = run_formal(spec, SAMPLE_DFY_CODE)
        assert result.status == VerifyStatus.SKIP

    def test_timeout_handling(self):
        """Stage 4 reports TIMEOUT when dafny exceeds time limit."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.side_effect = TimeoutError("Dafny verification timed out")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.TIMEOUT

    def test_dafny_not_installed(self):
        """Stage 4 FAIL gracefully when dafny binary is not found."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.side_effect = FileNotFoundError("dafny not found")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.FAIL
        assert any("not found" in str(e.get("error", "")).lower() for e in result.errors)

    def test_duration_is_recorded(self):
        """run_formal records duration_ms >= 0."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.return_value = (0, "verified\n", "")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.duration_ms >= 0

    def test_error_contains_file_and_line(self):
        """Errors from Dafny include file and line information [REF-P06]."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        error_output = (
            "test.dfy(5,2): Error: a postcondition could not be proved on this return path\n"
            "Dafny program verifier finished with 0 verified, 1 error\n"
        )
        with patch("contractd.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.return_value = (4, error_output, "")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.FAIL
        error = result.errors[0]
        assert "line" in error or "file" in error or "message" in error

    def test_empty_spec_skips(self):
        """Empty invariants list → SKIP."""
        spec = _make_spec([])
        result = run_formal(spec, SAMPLE_DFY_CODE)
        assert result.status == VerifyStatus.SKIP


class TestParseDafnyOutput:
    """Tests for parse_dafny_output helper."""

    def test_parse_success_output(self):
        """Parse successful verification output."""
        output = "Dafny program verifier finished with 2 verified, 0 errors\n"
        errors = parse_dafny_output(output)
        assert errors == []

    def test_parse_error_output(self):
        """Parse verification failure output with line numbers."""
        output = (
            "module.dfy(10,4): Error: a postcondition could not be proved on this return path\n"
            "module.dfy(3,12): Related location: this is the postcondition that could not be proved\n"
            "Dafny program verifier finished with 0 verified, 1 error\n"
        )
        errors = parse_dafny_output(output)
        assert len(errors) >= 1
        assert errors[0]["line"] == 10
        assert "postcondition" in errors[0]["message"]

    def test_parse_multiple_errors(self):
        """Parse output with multiple verification errors."""
        output = (
            "module.dfy(10,4): Error: a postcondition could not be proved\n"
            "module.dfy(20,8): Error: assertion might not hold\n"
            "Dafny program verifier finished with 0 verified, 2 errors\n"
        )
        errors = parse_dafny_output(output)
        assert len(errors) == 2
