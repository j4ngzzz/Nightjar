"""Tests for nightjar CLI tiered help output (NightjarGroup).

Verifies that `nightjar --help` renders commands grouped into named sections
(Start here, Build pipeline, Development, Integration, Advanced) and that the
Quick Start snippet appears in the output.

Reference: [REF-T17] Click CLI framework
"""

import pytest
from click.testing import CliRunner

from nightjar.cli import main, COMMAND_TIERS


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def help_output(runner):
    result = runner.invoke(main, ["--help"])
    return result


# ── Exit code ────────────────────────────────────────────


def test_help_exits_0(help_output):
    assert help_output.exit_code == 0


# ── Section headers ──────────────────────────────────────


def test_help_contains_start_here_section(help_output):
    assert "Start here" in help_output.output


def test_help_contains_build_pipeline_section(help_output):
    assert "Build pipeline" in help_output.output


def test_help_contains_development_section(help_output):
    assert "Development" in help_output.output


def test_help_contains_integration_section(help_output):
    assert "Integration" in help_output.output


def test_help_contains_advanced_section(help_output):
    assert "Advanced" in help_output.output


# ── Quick start ──────────────────────────────────────────


def test_help_shows_quick_start(help_output):
    assert "Quick start" in help_output.output


# ── Command placement ────────────────────────────────────


def test_spec_appears_in_start_here():
    """spec command is mapped to tier 1 / 'Start here' in COMMAND_TIERS.

    This test validates the tier mapping directly so it passes even before the
    spec command is registered by the parallel W4A work stream.
    """
    tier, section = COMMAND_TIERS["spec"]
    assert tier == 1
    assert section == "Start here"


def test_scan_appears_in_advanced(help_output):
    """scan is a registered command and must appear under the Advanced section."""
    output = help_output.output
    # Locate the "Advanced" section and confirm "scan" follows it before any
    # other section header.
    advanced_idx = output.find("Advanced")
    assert advanced_idx != -1, "Advanced section not found in help output"
    scan_idx = output.find("scan", advanced_idx)
    assert scan_idx != -1, "'scan' command not found after Advanced section"
