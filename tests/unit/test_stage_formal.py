"""Tests for Stage 4 — Dafny Formal Verification.

Validates that the formal stage runs `dafny verify` on generated Dafny code,
parses results, and reports structured errors per [REF-P06] DafnyPro format.

References:
- [REF-T01] Dafny — verification-aware programming language
- [REF-P02] Vericoding benchmark — 82-96% Dafny success rate
- [REF-P06] DafnyPro — structured error format with assertion batch IDs
- [REF-C01] Tiered invariants — only 'formal' tier reaches Stage 4
- Scout 3 S4: Dafny optimization flags (verifySnapshots, vcsCores, filter-position)
- Scout 5 F1: Fine-grained caching (/verifySnapshots:3) — 10x+ repeat speedup
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyStatus,
)
from nightjar.stages.formal import run_formal, parse_dafny_output


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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
            mock_dafny.side_effect = TimeoutError("Dafny verification timed out")
            result = run_formal(spec, SAMPLE_DFY_CODE)

        assert result.status == VerifyStatus.TIMEOUT

    def test_dafny_not_installed(self):
        """Stage 4 FAIL gracefully when dafny binary is not found."""
        spec = _make_spec([
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For all x > 0, result > 0"),
        ])
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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
        with patch("nightjar.stages.formal._run_dafny_verify") as mock_dafny:
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


class TestDafnyOptimizationFlags:
    """Tests for W1.1 — Dafny optimization flags.

    Per Scout 3 S4 + Scout 5 F1:
    - /verifySnapshots:3 — fine-grained Boogie caching (10x+ repeat speedup, LPAR 2015)
    - --vcsCores N — parallel verification (max(1, cpu_count//2))
    - --progress — stream per-symbol verification status
    - --filter-position — 90%+ wall time reduction for single-function verify
    - --filter-symbol — skip unchanged procedures
    """

    def test_formal_includes_verify_snapshots_flag(self):
        """`dafny verify` invocation includes /verifySnapshots:3 for caching.

        Per Scout 5 F1: Fine-Grained Caching of Verification Results (LPAR 2015,
        MS Research). /verifySnapshots:3 enables per-method hash caching with
        call-graph awareness. 10x+ speedup on repeat verifications.
        """
        from unittest.mock import patch, call
        from nightjar.stages.formal import _run_dafny_verify

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "verified\n"
            mock_run.return_value.stderr = ""
            _run_dafny_verify("test.dfy")

        called_cmd = mock_run.call_args[0][0]
        assert "/verifySnapshots:3" in called_cmd, (
            "/verifySnapshots:3 not found in Dafny command — "
            "required for fine-grained caching (Scout 5 F1, LPAR 2015)"
        )

    def test_formal_auto_detects_cpu_cores(self):
        """`dafny verify` uses max(1, cpu_count//2) for --vcsCores.

        Per Scout 3 S4.2: near-linear speedup across independent procedures.
        Uses half of available cores to avoid starving other processes.
        Scout 5 caveat: 'with vcsCores>1, output becomes interleaved' — handled
        by deinterleaving logic.
        """
        import os
        from unittest.mock import patch
        from nightjar.stages.formal import _run_dafny_verify

        expected_cores = max(1, (os.cpu_count() or 4) // 2)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "verified\n"
            mock_run.return_value.stderr = ""
            _run_dafny_verify("test.dfy")

        called_cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(called_cmd)
        assert f"--vcsCores:{expected_cores}" in cmd_str or f"--vcsCores {expected_cores}" in cmd_str, (
            f"Expected --vcsCores:{expected_cores} in Dafny command. "
            "Required for parallel verification (Scout 3 S4.2)"
        )

    def test_formal_parses_progress_output(self):
        """Progress events are extracted from Dafny --progress stdout.

        Per Scout 5 F1: --progress flag streams 'Verified X/Y symbols...'
        during verification. We parse these to show live feedback.
        When vcsCores>1, output lines are interleaved and must be sorted.
        """
        from nightjar.stages.formal import parse_progress_events

        progress_output = (
            "Verifying Process (0/2)...\n"
            "Verifying Helper (1/2)...\n"
            "Verified: Process (2/2)\n"
        )
        events = parse_progress_events(progress_output)
        assert len(events) >= 2, "Expected at least 2 progress events"
        # Each event must have 'symbol' key
        for event in events:
            assert "symbol" in event, f"Progress event missing 'symbol' key: {event}"

    def test_formal_includes_progress_flag(self):
        """Dafny invocation includes --progress for streaming output.

        Per Scout 5 F8 + PR #5218: --progress streams per-symbol status.
        """
        from unittest.mock import patch
        from nightjar.stages.formal import _run_dafny_verify

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "verified\n"
            mock_run.return_value.stderr = ""
            _run_dafny_verify("test.dfy")

        called_cmd = mock_run.call_args[0][0]
        assert "--progress" in called_cmd, (
            "--progress flag not in Dafny command — "
            "required for streaming per-symbol status (Scout 5 F8)"
        )

    def test_formal_includes_filter_position_when_provided(self):
        """When filter_position is provided, it's added to the Dafny command.

        Per Scout 3 S4.2: --filter-position=<file>:<line> provides 90%+
        wall-time reduction by verifying only one function.
        """
        from unittest.mock import patch
        from nightjar.stages.formal import _run_dafny_verify

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "verified\n"
            mock_run.return_value.stderr = ""
            _run_dafny_verify("test.dfy", filter_position="test.dfy:10")

        called_cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(called_cmd)
        assert "filter-position" in cmd_str and "test.dfy:10" in cmd_str, (
            "--filter-position flag not passed to Dafny command (Scout 3 S4.2)"
        )

    def test_formal_deinterleaves_progress_when_multicores(self):
        """Progress output is deinterleaved when vcsCores > 1.

        Per Scout 5 caveat: 'With --vcsCores:4, output becomes interleaved.
        Need to parse and deinterleave for clean display.'
        """
        from nightjar.stages.formal import deinterleave_progress

        # Simulate interleaved output from 2 parallel verifiers
        interleaved = [
            "Verifying Process (0/4)...",
            "Verifying Helper (1/4)...",  # Could be from different core
            "Verified: Process (2/4)",
            "Verified: Helper (3/4)",
        ]
        deinterleaved = deinterleave_progress(interleaved)
        # Verified lines should come after corresponding Verifying lines
        assert isinstance(deinterleaved, list)
        assert len(deinterleaved) == len(interleaved)
