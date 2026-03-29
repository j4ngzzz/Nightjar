"""Nightjar pytest plugin.

Registers the --nightjar flag and the @pytest.mark.nightjar marker.
When --nightjar is passed, runs the Nightjar verification pipeline against all
.card.md specs before the test session starts. Marked tests are skipped if
verification fails.

Plugin is OPTIONAL — importing without pytest installed must not crash.
All nightjar internals are imported lazily (inside functions) to keep
pytest startup fast and to avoid loading the full nightjar stack unless
the --nightjar flag is actually used.

References:
- Research: .bridgespace/swarms/pane1774/inbox/wave4/pipeline-integrations-research.md
- Hypothesis plugin pattern: https://github.com/HypothesisWorks/hypothesis/blob/master/hypothesis-python/src/_hypothesis_pytestplugin.py
- pytest writing plugins: https://docs.pytest.org/en/stable/how-to/writing_plugins.html
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, Optional

# Guard: this module must be importable even without pytest installed.
try:
    import pytest
    _PYTEST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYTEST_AVAILABLE = False

if TYPE_CHECKING:
    # Only used for type annotations — never at runtime here.
    from pytest import Config, Item, Parser, Session, Terminal


# ---------------------------------------------------------------------------
# Internal state key stored on pytest.Config
# ---------------------------------------------------------------------------

_RESULT_ATTR = "_nightjar_verification_failed"
_SUMMARY_ATTR = "_nightjar_summary"


# ---------------------------------------------------------------------------
# 1. CLI option registration
# ---------------------------------------------------------------------------

def pytest_addoption(parser: "Parser") -> None:
    """Register Nightjar CLI options."""
    try:
        group = parser.getgroup("nightjar", "Nightjar Formal Verification")
        group.addoption(
            "--nightjar",
            action="store_true",
            default=False,
            help="Run Nightjar verification pipeline before the test session.",
        )
        group.addoption(
            "--nightjar-fast",
            action="store_true",
            default=False,
            help="Run Nightjar in fast mode (skip Dafny + negation-proof stages).",
        )
        group.addoption(
            "--nightjar-spec",
            action="store",
            default=".card",
            metavar="PATH",
            help="Path to .card/ spec directory (default: .card).",
        )
    except Exception:
        # Never crash pytest even if option registration fails.
        pass


# ---------------------------------------------------------------------------
# 2. Marker registration
# ---------------------------------------------------------------------------

def pytest_configure(config: "Config") -> None:
    """Register the 'nightjar' marker so pytest --markers shows it."""
    try:
        config.addinivalue_line(
            "markers",
            "nightjar: Mark a test as requiring Nightjar-verified code. "
            "Skipped automatically if --nightjar verification fails.",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 3. Session start — run verification pipeline
# ---------------------------------------------------------------------------

def pytest_sessionstart(session: "Session") -> None:
    """Run the Nightjar pipeline before the test session if --nightjar is set."""
    try:
        config = session.config
        if not config.getoption("--nightjar", default=False):
            return

        fast: bool = config.getoption("--nightjar-fast", default=False)
        spec_path: str = config.getoption("--nightjar-spec", default=".card")

        cmd = [sys.executable, "-m", "nightjar", "verify", "--spec", spec_path]
        if fast:
            cmd.append("--fast")

        # Try the entry-point executable first; fall back to python -m nightjar.
        try:
            import shutil
            nightjar_bin = shutil.which("nightjar")
            if nightjar_bin:
                cmd = [nightjar_bin, "verify", "--spec", spec_path]
                if fast:
                    cmd.append("--fast")
        except Exception:
            pass

        # Print header via terminal reporter if available.
        _write_sep(config, "Nightjar Verification")

        result = subprocess.run(cmd, capture_output=False)

        setattr(config, _RESULT_ATTR, result.returncode != 0)
        setattr(config, _SUMMARY_ATTR, {
            "returncode": result.returncode,
            "fast": fast,
            "spec_path": spec_path,
        })

    except Exception as exc:
        # Plugin failure must NEVER crash pytest — set state conservatively.
        try:
            setattr(session.config, _RESULT_ATTR, False)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 4. Collection: skip @pytest.mark.nightjar tests if verification failed
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config: "Config", items: list["Item"]) -> None:
    """Skip tests marked @pytest.mark.nightjar when verification failed."""
    try:
        failed: bool = getattr(config, _RESULT_ATTR, False)
        if not failed:
            return

        skip_marker = pytest.mark.skip(
            reason="Nightjar verification failed — fix contract violations first"
        )
        for item in items:
            if item.get_closest_marker("nightjar"):
                item.add_marker(skip_marker)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 5. Terminal summary — print Nightjar result block
# ---------------------------------------------------------------------------

def pytest_terminal_summary(terminalreporter: "Terminal", exitstatus: int, config: "Config") -> None:
    """Print Nightjar verification summary at the bottom of the pytest report."""
    try:
        if not config.getoption("--nightjar", default=False):
            return

        summary = getattr(config, _SUMMARY_ATTR, None)
        if summary is None:
            return

        terminalreporter.write_sep("=", "Nightjar Summary")
        returncode = summary.get("returncode", -1)
        fast = summary.get("fast", False)
        spec_path = summary.get("spec_path", ".card")

        status = "PASSED" if returncode == 0 else "FAILED"
        mode = "fast" if fast else "full"

        terminalreporter.write_line(f"  verification : {status}")
        terminalreporter.write_line(f"  mode         : {mode}")
        terminalreporter.write_line(f"  spec-path    : {spec_path}")
        terminalreporter.write_line(f"  exit-code    : {returncode}")

    except Exception:
        pass


# ---------------------------------------------------------------------------
# 6. Report header — single line shown above test output
# ---------------------------------------------------------------------------

def pytest_report_header(config: "Config") -> Optional[str]:
    """Show Nightjar mode in the pytest header section."""
    try:
        if not config.getoption("--nightjar", default=False):
            return None
        spec = config.getoption("--nightjar-spec", default=".card")
        fast = config.getoption("--nightjar-fast", default=False)
        mode = "fast" if fast else "full"
        return f"nightjar: spec={spec!r}  mode={mode}"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_sep(config: "Config", title: str) -> None:
    """Write a separator line via the terminal reporter, if present."""
    try:
        reporter = config.pluginmanager.getplugin("terminalreporter")
        if reporter is not None:
            reporter.write_sep("=", title, bold=True)
    except Exception:
        pass
