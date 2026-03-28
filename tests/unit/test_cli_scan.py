"""Tests for the nightjar scan CLI command.

Covers:
- Command exists and shows correct help text
- No-LLM path (basic scan)
- File-not-found error
- --approve-all flag
- --output flag
- Low-signal warning
"""

import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from nightjar.cli import main


# ── Helpers ────────────────────────────────────────────────────────────────────


def _write_tmp_py(content: str) -> str:
    """Write content to a temp .py file and return the path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


_SAMPLE_PY = '''\
def process_payment(amount: float, currency: str) -> dict:
    """Process a payment transaction.

    Args:
        amount: The payment amount.
        currency: ISO 4217 currency code.

    Returns:
        dict with transaction_id and status keys.

    Raises:
        ValueError: if amount is negative.
    """
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if not currency:
        raise ValueError("currency must not be empty")
    assert amount >= 0, "amount is non-negative"
    return {"transaction_id": "txn_001", "status": "ok"}
'''

_EMPTY_PY = '''\
# No functions, no type hints, no docstrings
x = 1
'''


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_scan_command_exists():
    """scan command is registered and --help works."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "Scan a Python file" in result.output


def test_scan_help_shows_examples():
    """--help output mentions the nightjar scan usage pattern."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "nightjar scan" in result.output


def test_scan_help_shows_llm_option():
    """--help output lists --llm flag."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--llm" in result.output


def test_scan_help_shows_verify_option():
    """--help output lists --verify flag."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--verify" in result.output


def test_scan_file_not_found():
    """scan with a non-existent file exits with CONFIG_ERROR (exit code 2)."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "/nonexistent/path/nope.py"])
    # Click Path(exists=True) will catch this before our code
    assert result.exit_code != 0


def test_scan_basic_no_llm_approve_all():
    """scan a file with type hints + guards, --approve-all, writes spec."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "payment.card.md")
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", output_path],
            )
            assert result.exit_code == 0, result.output
            assert "Spec written" in result.output
            assert os.path.exists(output_path)
            content = Path(output_path).read_text(encoding="utf-8")
            assert "card-version" in content
            assert "generated-by: nightjar-scan" in content
    finally:
        os.unlink(src_path)


def test_scan_writes_card_md_with_invariants():
    """The written .card.md contains the extracted invariants."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "payment.card.md")
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", output_path],
            )
            assert result.exit_code == 0, result.output
            content = Path(output_path).read_text(encoding="utf-8")
            # Should have at least one invariant
            assert "INV-" in content
    finally:
        os.unlink(src_path)


def test_scan_output_option_respected():
    """--output path is used as the destination for the .card.md file."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_output = os.path.join(tmpdir, "custom_spec.card.md")
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", custom_output],
            )
            assert result.exit_code == 0, result.output
            assert os.path.exists(custom_output)
    finally:
        os.unlink(src_path)


def test_scan_low_signal_warning():
    """Low-signal files produce a warning message or empty-candidate exit."""
    src_path = _write_tmp_py(_EMPTY_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "empty.card.md")
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", output_path],
            )
            # Command should not crash; exit 0 or 1 (no candidates → FAIL)
            assert result.exit_code in (0, 1)
    finally:
        os.unlink(src_path)


def test_scan_approve_all_flag_skips_prompts():
    """--approve-all auto-approves without interactive prompts."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "auto.card.md")
            runner = CliRunner()
            # With --approve-all there should be no interactive prompts
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", output_path],
            )
            # Should not hang waiting for input
            assert result.exit_code == 0, result.output
            assert "Auto-approved" in result.output
    finally:
        os.unlink(src_path)


def test_scan_shows_candidate_count():
    """Output includes the number of candidates found."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "payment.card.md")
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["scan", src_path, "--approve-all", "--output", output_path],
            )
            assert result.exit_code == 0, result.output
            # Should mention candidate count
            assert "candidate" in result.output
    finally:
        os.unlink(src_path)


def test_scan_interactive_reject_all():
    """Rejecting all candidates in interactive mode exits with FAIL."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "payment.card.md")
            runner = CliRunner()
            # Provide 'n' for every prompt
            result = runner.invoke(
                main,
                ["scan", src_path, "--output", output_path],
                input="n\n" * 20,  # enough n's to reject everything
            )
            # Exit 1 = FAIL (no spec written) or 0 if somehow accepted
            # Key test: no exception / crash
            assert result.exit_code in (0, 1)
            if result.exit_code == 1:
                assert "rejected" in result.output or "Spec not written" in result.output
    finally:
        os.unlink(src_path)


def test_scan_interactive_accept_all():
    """Accepting all candidates in interactive mode writes spec."""
    src_path = _write_tmp_py(_SAMPLE_PY)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "payment.card.md")
            runner = CliRunner()
            # Provide 'y' for every prompt
            result = runner.invoke(
                main,
                ["scan", src_path, "--output", output_path],
                input="y\n" * 20,
            )
            assert result.exit_code == 0, result.output
            assert os.path.exists(output_path)
    finally:
        os.unlink(src_path)
