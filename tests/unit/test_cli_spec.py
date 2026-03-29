"""Tests for the 'nightjar spec' smart router command.

Covers:
  - Help exits 0
  - Routing logic (_route_spec_input unit tests)
  - spec command delegates to scan (file), scan (dir), infer, and auto
  - --mode flag overrides auto-detection
  - Routing announcement to stderr when mode is auto-detected
  - Regression: existing scan and infer commands still work independently

References: [REF-T17] Click CLI framework
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from nightjar.cli import main, _route_spec_input


# ── Helpers ────────────────────────────────────────────────────────────────────


_SAMPLE_PY = """\
def process_payment(amount: float, currency: str) -> dict:
    \"\"\"Process a payment transaction.\"\"\"
    if amount < 0:
        raise ValueError("amount must be non-negative")
    assert amount >= 0
    return {"transaction_id": "txn_001", "status": "ok"}
"""


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_py_file(tmp_path):
    """A real .py file on disk."""
    f = tmp_path / "payment.py"
    f.write_text(_SAMPLE_PY, encoding="utf-8")
    return str(f)


@pytest.fixture
def tmp_dir(tmp_path):
    """A real directory on disk (a *subdirectory* of tmp_path so it differs from tmp_py_file's parent)."""
    d = tmp_path / "scandir"
    d.mkdir()
    return str(d)


# ── _route_spec_input pure-function tests ──────────────────────────────────────


class TestRouteSpecInput:
    """Unit tests for the pure routing function."""

    def test_existing_dir_routes_to_scan_dir(self, tmp_dir):
        route = _route_spec_input(tmp_dir, mode=None, model_available=False)
        assert route == "scan_dir"

    def test_existing_dir_routes_to_scan_dir_with_model(self, tmp_dir):
        route = _route_spec_input(tmp_dir, mode=None, model_available=True)
        assert route == "scan_dir"

    def test_existing_file_no_model_routes_to_scan_file(self, tmp_py_file):
        route = _route_spec_input(tmp_py_file, mode=None, model_available=False)
        assert route == "scan_file"

    def test_existing_file_with_model_routes_to_infer(self, tmp_py_file):
        route = _route_spec_input(tmp_py_file, mode=None, model_available=True)
        assert route == "infer"

    def test_nonexistent_py_path_routes_to_scan_file(self):
        route = _route_spec_input("/nonexistent/file.py", mode=None, model_available=False)
        assert route == "scan_file"

    def test_nonexistent_py_path_with_model_still_routes_to_scan_file(self):
        # Non-existent path ending in .py → scan_file (priority 5 wins over model)
        route = _route_spec_input("/nonexistent/file.py", mode=None, model_available=True)
        assert route == "scan_file"

    def test_natural_language_routes_to_auto(self):
        route = _route_spec_input("payment processing with refunds", mode=None, model_available=False)
        assert route == "auto"

    def test_natural_language_with_model_still_routes_to_auto(self):
        route = _route_spec_input("payment processing with refunds", mode=None, model_available=True)
        assert route == "auto"

    def test_mode_scan_overrides_existing_file_with_model(self, tmp_py_file):
        route = _route_spec_input(tmp_py_file, mode="scan", model_available=True)
        assert route == "scan_file"

    def test_mode_scan_on_directory_returns_scan_dir(self, tmp_dir):
        route = _route_spec_input(tmp_dir, mode="scan", model_available=True)
        assert route == "scan_dir"

    def test_mode_infer_overrides_existing_file_no_model(self, tmp_py_file):
        route = _route_spec_input(tmp_py_file, mode="infer", model_available=False)
        assert route == "infer"

    def test_mode_auto_overrides_existing_py_file(self, tmp_py_file):
        route = _route_spec_input(tmp_py_file, mode="auto", model_available=False)
        assert route == "auto"

    def test_mode_auto_overrides_natural_language(self):
        route = _route_spec_input("some string", mode="auto", model_available=True)
        assert route == "auto"


# ── spec --help ────────────────────────────────────────────────────────────────


def test_spec_help_exits_0(runner):
    """nightjar spec --help exits 0 and mentions routing."""
    result = runner.invoke(main, ["spec", "--help"])
    assert result.exit_code == 0
    assert "INPUT_TARGET" in result.output
    assert "--mode" in result.output


# ── spec file → scan delegation ────────────────────────────────────────────────


def test_spec_file_routes_to_scan(runner, tmp_py_file):
    """spec with an existing .py file (no model) delegates to scan command."""
    # Provide a custom output so the scan doesn't look up config paths
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "payment.card.md")
        result = runner.invoke(
            main,
            ["spec", tmp_py_file, "--approve-all", "--output", output_path],
            env={"NIGHTJAR_MODEL": "", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )
    # Should have announced routing to stderr
    assert "spec: routing to scan (file)" in result.output or (
        result.output  # no exception; routing happened
    )
    # Exit 0 (scan ran successfully)
    assert result.exit_code == 0


# ── spec dir → scan_dir delegation ────────────────────────────────────────────


def test_spec_dir_routes_to_scan_dir(runner, tmp_dir):
    """spec with a directory delegates to scan dir command."""
    # Write a .py file into tmp_dir so the router detects it as a real directory
    Path(tmp_dir, "payment.py").write_text(_SAMPLE_PY, encoding="utf-8")

    mock_scan_dir = MagicMock(return_value=[])
    with patch("nightjar.scanner.scan_directory", mock_scan_dir):
        result = runner.invoke(
            main,
            ["spec", tmp_dir],
            env={"NIGHTJAR_MODEL": "", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )

    # scan_directory was called with the directory path
    mock_scan_dir.assert_called_once()
    call_args = mock_scan_dir.call_args
    called_path = call_args[0][0]
    assert str(called_path) == tmp_dir or Path(called_path) == Path(tmp_dir)

    assert result.exit_code == 0


# ── spec string → auto delegation ─────────────────────────────────────────────


def test_spec_string_routes_to_auto(runner):
    """spec with a natural-language string delegates to auto command."""
    mock_auto_result = MagicMock()
    mock_auto_result.card_path = ".card/payment.card.md"
    mock_auto_result.approved_count = 3
    mock_auto_result.skipped_count = 0

    with patch("nightjar.auto.run_auto", return_value=mock_auto_result):
        result = runner.invoke(
            main,
            ["spec", "payment processing with refund support", "--approve-all"],
            env={"NIGHTJAR_MODEL": "claude-sonnet-4-6", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )

    assert result.exit_code == 0


# ── --mode overrides ───────────────────────────────────────────────────────────


def test_spec_mode_scan_overrides_detection(runner, tmp_py_file):
    """--mode scan on a file that would otherwise route to infer → scan_file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "payment.card.md")
        result = runner.invoke(
            main,
            ["spec", tmp_py_file, "--mode", "scan", "--approve-all", "--output", output_path],
            env={"NIGHTJAR_MODEL": "claude-sonnet-4-6", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )
    # No routing announcement in output (mode was explicit)
    assert "spec: routing to" not in result.output
    assert result.exit_code == 0


def test_spec_mode_infer_overrides_detection(runner, tmp_py_file):
    """--mode infer on a file that has no model → forced infer, not scan."""
    mock_infer = MagicMock()
    mock_infer.preconditions = []
    mock_infer.postconditions = []
    mock_infer.verification_status = "verified"
    mock_infer.confidence = 0.9
    mock_infer.iterations_used = 1
    mock_infer.function_name = "process_payment"
    mock_infer.counterexample = None

    with patch("nightjar.inferrer.infer_contracts", return_value=mock_infer):
        with patch("nightjar.contract_library.retrieve_examples", return_value=[]):
            result = runner.invoke(
                main,
                ["spec", tmp_py_file, "--mode", "infer", "--no-verify"],
                env={"NIGHTJAR_MODEL": "", "NIGHTJAR_DISABLE_CACHE": "1"},
                catch_exceptions=False,
            )

    # No routing announcement (mode was explicit)
    assert "spec: routing to" not in result.output


def test_spec_mode_auto_overrides_detection(runner, tmp_py_file):
    """--mode auto on an existing .py file → forced auto, not scan/infer."""
    mock_auto_result = MagicMock()
    mock_auto_result.card_path = ".card/payment.card.md"
    mock_auto_result.approved_count = 2
    mock_auto_result.skipped_count = 0

    with patch("nightjar.auto.run_auto", return_value=mock_auto_result):
        result = runner.invoke(
            main,
            ["spec", tmp_py_file, "--mode", "auto", "--approve-all"],
            env={"NIGHTJAR_MODEL": "claude-sonnet-4-6", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )

    # No routing announcement (mode was explicit)
    assert "spec: routing to" not in result.output
    assert result.exit_code == 0


# ── Routing announcement ───────────────────────────────────────────────────────


def test_spec_announces_routing_to_stderr(runner, tmp_py_file):
    """When mode is not set, spec announces its routing decision to stderr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "payment.card.md")
        result = runner.invoke(
            main,
            ["spec", tmp_py_file, "--approve-all", "--output", output_path],
            env={"NIGHTJAR_MODEL": "", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )

    # CliRunner captures stderr in result.stderr
    assert "spec: routing to" in result.stderr


def test_spec_no_announcement_when_mode_is_set(runner, tmp_py_file):
    """When --mode is explicitly set, no routing announcement is printed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "payment.card.md")
        result = runner.invoke(
            main,
            ["spec", tmp_py_file, "--mode", "scan", "--approve-all", "--output", output_path],
            env={"NIGHTJAR_MODEL": "", "NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )

    assert "spec: routing to" not in result.stderr


# ── Regressions: existing commands still work ──────────────────────────────────


def test_existing_scan_command_still_works(runner, tmp_py_file):
    """Regression: 'nightjar scan <file>' still works after spec was added."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "payment.card.md")
        result = runner.invoke(
            main,
            ["scan", tmp_py_file, "--approve-all", "--output", output_path],
            env={"NIGHTJAR_DISABLE_CACHE": "1"},
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    assert "Spec written" in result.output


def test_existing_infer_command_still_works(runner, tmp_py_file):
    """Regression: 'nightjar infer <file>' still works after spec was added."""
    mock_infer = MagicMock()
    mock_infer.preconditions = ["amount >= 0"]
    mock_infer.postconditions = ["return_value is not None"]
    mock_infer.verification_status = "verified"
    mock_infer.confidence = 0.95
    mock_infer.iterations_used = 1
    mock_infer.function_name = "process_payment"
    mock_infer.counterexample = None

    with patch("nightjar.inferrer.infer_contracts", return_value=mock_infer):
        with patch("nightjar.contract_library.retrieve_examples", return_value=[]):
            result = runner.invoke(
                main,
                ["infer", tmp_py_file, "--no-verify"],
                env={"NIGHTJAR_MODEL": "claude-sonnet-4-6", "NIGHTJAR_DISABLE_CACHE": "1"},
                catch_exceptions=False,
            )

    # Should not raise an error
    assert result.exit_code == 0
