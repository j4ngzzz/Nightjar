"""Tests for new CLI commands and options added to nightjar CLI.

Tests the following additions:
- nightjar audit — scan PyPI package for contract coverage / CVEs
- nightjar scan <dir> — directory scanning with --workers/--min-signal/--smart-sort
- nightjar scan <file> — existing single-file behaviour still works (no regression)
- nightjar verify --format=vscode
- nightjar verify --output-sarif
- nightjar benchmark — run Nightjar against an academic benchmark
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nightjar.cli import main


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_card(tmp_path):
    """Minimal .card.md spec file for --contract/--spec tests."""
    card_dir = tmp_path / ".card"
    card_dir.mkdir()
    spec = card_dir / "payment.card.md"
    spec.write_text(
        "---\ncard-version: '1.0'\nid: payment\ntitle: Payment\n---\n",
        encoding="utf-8",
    )
    return spec


def _make_scan_result(module_id: str = "payment", n_candidates: int = 3):
    """Return a minimal mock ScanResult."""
    r = MagicMock()
    r.module_id = module_id
    r.candidates = [MagicMock() for _ in range(n_candidates)]
    r.signal_strength = "high"
    return r


def _make_verify_result(verified: bool = True):
    mock = MagicMock()
    mock.verified = verified
    mock.stages = []
    mock.total_duration_ms = 100
    return mock


# ── nightjar audit ────────────────────────────────────────────────────────────


class TestAuditCommand:
    """Tests for 'nightjar audit <package_spec>'."""

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_basic_invocation(self, mock_render, mock_audit, runner):
        """audit runs audit_package and prints render_report_card output."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=85.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render.return_value = "REPORT CARD OUTPUT"

        result = runner.invoke(main, ["audit", "requests"])

        assert result.exit_code == 0, result.output
        mock_audit.assert_called_once_with(
            "requests",
            with_deps=False,
            check_cves=True,
            use_cache=True,
        )
        assert "REPORT CARD OUTPUT" in result.output

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_json")
    def test_audit_json_flag(self, mock_render_json, mock_audit, runner):
        """--json flag uses render_json instead of render_report_card."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=90.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render_json.return_value = '{"score": 90}'

        result = runner.invoke(main, ["audit", "requests", "--json"])

        assert result.exit_code == 0, result.output
        mock_render_json.assert_called_once_with(mock_result)
        assert '{"score": 90}' in result.output

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_with_deps_flag(self, mock_render, mock_audit, runner):
        """--with-deps passes with_deps=True to audit_package."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=75.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render.return_value = "OK"

        runner.invoke(main, ["audit", "flask", "--with-deps"])

        mock_audit.assert_called_once_with(
            "flask",
            with_deps=True,
            check_cves=True,
            use_cache=True,
        )

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_no_cve_flag(self, mock_render, mock_audit, runner):
        """--no-cve passes check_cves=False (offline mode)."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=80.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render.return_value = "OK"

        runner.invoke(main, ["audit", "flask", "--no-cve"])

        mock_audit.assert_called_once_with(
            "flask",
            with_deps=False,
            check_cves=False,
            use_cache=True,
        )

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_no_cache_flag(self, mock_render, mock_audit, runner):
        """--no-cache passes use_cache=False."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=80.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render.return_value = "OK"

        runner.invoke(main, ["audit", "flask", "--no-cache"])

        mock_audit.assert_called_once_with(
            "flask",
            with_deps=False,
            check_cves=True,
            use_cache=False,
        )

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_low_score_exits_1(self, mock_render, mock_audit, runner):
        """Exit code 1 when overall score < 70."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=50.0)
        mock_result.cves = []
        mock_audit.return_value = mock_result
        mock_render.return_value = "LOW SCORE"

        result = runner.invoke(main, ["audit", "bad-pkg"])

        assert result.exit_code == 1

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_cves_present_exits_1(self, mock_render, mock_audit, runner):
        """Exit code 1 when CVEs are found, even if score >= 70."""
        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=80.0)
        mock_result.cves = [{"id": "CVE-2024-0001"}]
        mock_audit.return_value = mock_result
        mock_render.return_value = "HAS CVE"

        result = runner.invoke(main, ["audit", "vuln-pkg"])

        assert result.exit_code == 1

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_network_error_exits_2(self, mock_render, mock_audit, runner):
        """Network / not-found errors produce exit code 2."""
        mock_audit.side_effect = Exception("Package 'nonexistent' not found on PyPI")

        result = runner.invoke(main, ["audit", "nonexistent"])

        assert result.exit_code == 2

    @patch("nightjar.pkg_auditor.audit_package")
    @patch("nightjar.pkg_auditor.render_report_card")
    def test_audit_output_flag_writes_card(self, mock_render, mock_audit, runner, tmp_path):
        """--output writes candidates as a .card.md file."""
        candidate = MagicMock()
        candidate.statement = "param x must be int"
        candidate.tier = "schema"
        candidate.confidence = 0.9

        mock_result = MagicMock()
        mock_result.scores = MagicMock(overall=80.0)
        mock_result.cves = []
        mock_result.name = "requests"
        mock_result.version = "2.31.0"
        mock_result.candidates = [candidate]
        mock_audit.return_value = mock_result
        mock_render.return_value = "REPORT"

        out_path = tmp_path / "requests.card.md"
        result = runner.invoke(main, ["audit", "requests", "--output", str(out_path)])

        assert result.exit_code == 0, result.output
        assert out_path.exists()


# ── nightjar scan (directory mode) ────────────────────────────────────────────


class TestScanDirectoryCommand:
    """Tests for 'nightjar scan <directory>'."""

    @patch("nightjar.scanner.scan_directory")
    def test_scan_directory_invokes_scan_directory(self, mock_scan_dir, runner, tmp_path):
        """scan_directory() is called when path is a directory."""
        (tmp_path / "dummy.py").write_text("x = 1\n", encoding="utf-8")
        mock_scan_dir.return_value = [
            _make_scan_result("payment", 3),
            _make_scan_result("auth", 1),
        ]

        result = runner.invoke(main, ["scan", str(tmp_path), "--approve-all"])

        mock_scan_dir.assert_called_once()
        assert result.exit_code == 0, result.output
        assert "Scan complete" in result.output

    @patch("nightjar.scanner.scan_directory")
    def test_scan_directory_workers_option(self, mock_scan_dir, runner, tmp_path):
        """--workers N is forwarded to scan_directory."""
        mock_scan_dir.return_value = [_make_scan_result("mod", 2)]

        runner.invoke(main, ["scan", str(tmp_path), "--workers", "4", "--approve-all"])

        call_kwargs = mock_scan_dir.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("workers") == 4

    @patch("nightjar.scanner.scan_directory")
    def test_scan_directory_min_signal_option(self, mock_scan_dir, runner, tmp_path):
        """--min-signal medium is forwarded to scan_directory."""
        mock_scan_dir.return_value = [_make_scan_result("mod", 5)]

        runner.invoke(main, ["scan", str(tmp_path), "--min-signal", "medium", "--approve-all"])

        call_kwargs = mock_scan_dir.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("min_signal") == "medium"

    @patch("nightjar.scanner.scan_directory")
    def test_scan_directory_smart_sort_flag(self, mock_scan_dir, runner, tmp_path):
        """--smart-sort is forwarded to scan_directory."""
        mock_scan_dir.return_value = [_make_scan_result("mod", 2)]

        runner.invoke(main, ["scan", str(tmp_path), "--smart-sort", "--approve-all"])

        call_kwargs = mock_scan_dir.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("smart_sort") is True

    @patch("nightjar.scanner.scan_file")
    @patch("nightjar.scanner.write_scan_card_md")
    def test_scan_file_still_works(self, mock_write, mock_scan, runner, tmp_path):
        """Existing single-file scan behaviour is unchanged (no regression)."""
        py_file = tmp_path / "payment.py"
        py_file.write_text("def pay(amount): pass\n", encoding="utf-8")

        mock_scan.return_value = _make_scan_result("payment", 2)
        mock_write.return_value = str(tmp_path / ".card" / "payment.card.md")

        result = runner.invoke(main, ["scan", str(py_file), "--approve-all"])

        mock_scan.assert_called_once()
        assert result.exit_code == 0, result.output


# ── nightjar verify --format=vscode ───────────────────────────────────────────


class TestVerifyVscodeFormat:
    """Tests for 'nightjar verify --format vscode'."""

    @patch("nightjar.cli._run_verify")
    @patch("nightjar.formatters.vscode.format_vscode_output")
    def test_verify_format_vscode_calls_formatter(
        self, mock_fmt, mock_verify, runner, tmp_card
    ):
        """--format vscode calls format_vscode_output and echoes its result."""
        mock_verify.return_value = _make_verify_result(verified=True)
        mock_fmt.return_value = ""

        result = runner.invoke(main, [
            "verify",
            "--spec", str(tmp_card),
            "--format", "vscode",
        ])

        mock_fmt.assert_called_once()
        assert result.exit_code == 0, result.output

    @patch("nightjar.cli._run_verify")
    @patch("nightjar.formatters.vscode.format_vscode_output")
    def test_verify_format_vscode_fail_exits_1(
        self, mock_fmt, mock_verify, runner, tmp_card
    ):
        """--format vscode exits 1 when result is not verified."""
        mock_verify.return_value = _make_verify_result(verified=False)
        mock_fmt.return_value = "payment.card.md:1:1: error: Stage 3 pbt"

        result = runner.invoke(main, [
            "verify",
            "--spec", str(tmp_card),
            "--format", "vscode",
        ])

        assert result.exit_code == 1

    @patch("nightjar.cli._run_verify")
    @patch("nightjar.formatters.vscode.format_vscode_output")
    def test_verify_format_vscode_output_shown(
        self, mock_fmt, mock_verify, runner, tmp_card
    ):
        """format_vscode_output result is echoed to stdout."""
        mock_verify.return_value = _make_verify_result(verified=False)
        mock_fmt.return_value = "payment.card.md:1:1: error: Stage 3"

        result = runner.invoke(main, [
            "verify",
            "--spec", str(tmp_card),
            "--format", "vscode",
        ])

        assert "payment.card.md:1:1: error:" in result.output


# ── nightjar verify --output-sarif ────────────────────────────────────────────


class TestVerifyOutputSarif:
    """Tests for 'nightjar verify --output-sarif <path>'."""

    @patch("nightjar.cli._run_verify")
    @patch("nightjar.sarif_writer.write_sarif")
    @patch("nightjar.sarif_writer.sarif_summary")
    @patch("nightjar.verifier.to_sarif")
    def test_verify_output_sarif_writes_file(
        self, mock_to_sarif, mock_summary, mock_write, mock_verify, runner, tmp_card, tmp_path
    ):
        """--output-sarif causes write_sarif to be called."""
        mock_verify.return_value = _make_verify_result(verified=True)
        sarif_path = tmp_path / "nightjar.sarif"
        mock_write.return_value = sarif_path
        mock_to_sarif.return_value = {"version": "2.1.0", "runs": []}
        mock_summary.return_value = "SARIF: 0 findings (pass)"

        result = runner.invoke(main, [
            "verify",
            "--spec", str(tmp_card),
            "--output-sarif", str(sarif_path),
        ])

        mock_write.assert_called_once()
        assert result.exit_code == 0, result.output

    @patch("nightjar.cli._run_verify")
    @patch("nightjar.sarif_writer.write_sarif")
    @patch("nightjar.sarif_writer.sarif_summary")
    @patch("nightjar.verifier.to_sarif")
    def test_verify_output_sarif_summary_shown(
        self, mock_to_sarif, mock_summary, mock_write, mock_verify, runner, tmp_card, tmp_path
    ):
        """sarif_summary output is echoed after writing."""
        mock_verify.return_value = _make_verify_result(verified=False)
        sarif_path = tmp_path / "nightjar.sarif"
        mock_write.return_value = sarif_path
        mock_to_sarif.return_value = {"version": "2.1.0", "runs": []}
        mock_summary.return_value = "SARIF: 2 errors written to nightjar.sarif"

        result = runner.invoke(main, [
            "verify",
            "--spec", str(tmp_card),
            "--output-sarif", str(sarif_path),
        ])

        assert "SARIF" in result.output


# ── nightjar benchmark ────────────────────────────────────────────────────────


class TestBenchmarkCommand:
    """Tests for 'nightjar benchmark <benchmark_path>'."""

    @patch("nightjar.benchmark_adapter.load_benchmark_suite")
    @patch("nightjar.benchmark_runner.run_benchmark")
    @patch("nightjar.benchmark_runner.format_benchmark_report")
    def test_benchmark_basic(
        self, mock_fmt, mock_run, mock_load, runner, tmp_path
    ):
        """benchmark loads tasks, runs, and formats the report."""
        bench_file = tmp_path / "tasks.jsonl"
        bench_file.write_text('{"id":"t1"}\n', encoding="utf-8")

        mock_load.return_value = [MagicMock()]
        mock_report = MagicMock()
        mock_report.passed_tasks = 1
        mock_run.return_value = mock_report
        mock_fmt.return_value = "BENCHMARK REPORT"

        result = runner.invoke(main, ["benchmark", str(bench_file)])

        assert result.exit_code == 0, result.output
        mock_load.assert_called_once()
        mock_run.assert_called_once()
        assert "BENCHMARK REPORT" in result.output

    @patch("nightjar.benchmark_adapter.load_benchmark_suite")
    @patch("nightjar.benchmark_runner.run_benchmark")
    @patch("nightjar.benchmark_runner.format_benchmark_json")
    def test_benchmark_json_flag(
        self, mock_fmt_json, mock_run, mock_load, runner, tmp_path
    ):
        """--json flag uses format_benchmark_json instead of format_benchmark_report."""
        bench_file = tmp_path / "tasks.jsonl"
        bench_file.write_text('{"id":"t1"}\n', encoding="utf-8")

        mock_load.return_value = [MagicMock()]
        mock_report = MagicMock()
        mock_report.passed_tasks = 1
        mock_run.return_value = mock_report
        mock_fmt_json.return_value = '{"pass_at_1": 0.75}'

        result = runner.invoke(main, ["benchmark", str(bench_file), "--json"])

        assert result.exit_code == 0, result.output
        mock_fmt_json.assert_called_once_with(mock_report)
        assert '{"pass_at_1": 0.75}' in result.output

    @patch("nightjar.benchmark_adapter.load_benchmark_suite")
    @patch("nightjar.benchmark_runner.run_benchmark")
    @patch("nightjar.benchmark_runner.format_benchmark_report")
    def test_benchmark_max_attempts_option(
        self, mock_fmt, mock_run, mock_load, runner, tmp_path
    ):
        """--max-attempts is forwarded to run_benchmark."""
        bench_file = tmp_path / "tasks.jsonl"
        bench_file.write_text('{"id":"t1"}\n', encoding="utf-8")

        mock_load.return_value = [MagicMock()]
        mock_run.return_value = MagicMock()
        mock_fmt.return_value = "OK"

        runner.invoke(main, ["benchmark", str(bench_file), "--max-attempts", "3"])

        _, kwargs = mock_run.call_args
        assert kwargs.get("max_attempts") == 3

    @patch("nightjar.benchmark_adapter.load_benchmark_suite")
    @patch("nightjar.benchmark_runner.run_benchmark")
    @patch("nightjar.benchmark_runner.format_benchmark_report")
    def test_benchmark_workers_option(
        self, mock_fmt, mock_run, mock_load, runner, tmp_path
    ):
        """--workers N is forwarded to run_benchmark."""
        bench_file = tmp_path / "tasks.jsonl"
        bench_file.write_text('{"id":"t1"}\n', encoding="utf-8")

        mock_load.return_value = [MagicMock()]
        mock_run.return_value = MagicMock()
        mock_fmt.return_value = "OK"

        runner.invoke(main, ["benchmark", str(bench_file), "--workers", "4"])

        _, kwargs = mock_run.call_args
        assert kwargs.get("workers") == 4

    @patch("nightjar.benchmark_adapter.load_benchmark_suite")
    @patch("nightjar.benchmark_runner.run_benchmark")
    @patch("nightjar.benchmark_runner.format_benchmark_report")
    def test_benchmark_source_option(
        self, mock_fmt, mock_run, mock_load, runner, tmp_path
    ):
        """--source vericoding is forwarded to load_benchmark_suite."""
        bench_file = tmp_path / "tasks.jsonl"
        bench_file.write_text('{"id":"t1"}\n', encoding="utf-8")

        mock_load.return_value = [MagicMock()]
        mock_run.return_value = MagicMock()
        mock_fmt.return_value = "OK"

        runner.invoke(main, ["benchmark", str(bench_file), "--source", "vericoding"])

        _, kwargs = mock_load.call_args
        assert kwargs.get("source") == "vericoding"
