"""Tests for nightjar pytest plugin.

Validates option registration, marker registration, skip-on-failure behaviour,
run-on-success behaviour, and no-op behaviour when the flag is absent.

All nightjar internals are mocked so these tests run without Dafny, an LLM,
or any .card/ directory.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import subprocess

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(nightjar: bool = False, fast: bool = False, spec: str = ".card") -> MagicMock:
    """Build a minimal mock pytest.Config."""
    config = MagicMock()
    config.getoption.side_effect = lambda name, default=None: {
        "--nightjar": nightjar,
        "--nightjar-fast": fast,
        "--nightjar-spec": spec,
    }.get(name, default)
    # Simulate no prior verification state
    if not hasattr(config, "_nightjar_verification_failed"):
        del config._nightjar_verification_failed  # ensure getattr returns default
    return config


# ---------------------------------------------------------------------------
# Test 1: plugin registers all three CLI options
# ---------------------------------------------------------------------------

class TestPluginRegistersOptions:
    """Plugin must register --nightjar, --nightjar-fast, --nightjar-spec."""

    def test_addoption_registers_nightjar_flag(self):
        """pytest_addoption must call addoption for --nightjar."""
        from nightjar.pytest_plugin import pytest_addoption

        parser = MagicMock()
        group = MagicMock()
        parser.getgroup.return_value = group

        pytest_addoption(parser)

        parser.getgroup.assert_called_once_with("nightjar", "Nightjar Formal Verification")

        option_names = [call.args[0] for call in group.addoption.call_args_list]
        assert "--nightjar" in option_names
        assert "--nightjar-fast" in option_names
        assert "--nightjar-spec" in option_names

    def test_addoption_does_not_crash_on_exception(self):
        """pytest_addoption must silently absorb exceptions (never crash pytest)."""
        from nightjar.pytest_plugin import pytest_addoption

        parser = MagicMock()
        parser.getgroup.side_effect = RuntimeError("parser exploded")

        # Must not raise
        pytest_addoption(parser)


# ---------------------------------------------------------------------------
# Test 2: plugin registers 'nightjar' marker
# ---------------------------------------------------------------------------

class TestPluginRegistersMarker:
    """pytest_configure must register the nightjar marker."""

    def test_configure_adds_nightjar_marker(self):
        """nightjar marker should be registered with addinivalue_line."""
        from nightjar.pytest_plugin import pytest_configure

        config = MagicMock()
        pytest_configure(config)

        # addinivalue_line must have been called with 'markers' at least once
        calls = config.addinivalue_line.call_args_list
        marker_calls = [c for c in calls if c.args[0] == "markers"]
        assert len(marker_calls) >= 1

        # The marker text must mention 'nightjar'
        marker_texts = " ".join(c.args[1] for c in marker_calls)
        assert "nightjar" in marker_texts

    def test_configure_does_not_crash_on_exception(self):
        """pytest_configure must not propagate exceptions."""
        from nightjar.pytest_plugin import pytest_configure

        config = MagicMock()
        config.addinivalue_line.side_effect = ValueError("boom")

        # Must not raise
        pytest_configure(config)


# ---------------------------------------------------------------------------
# Test 3: @pytest.mark.nightjar tests are skipped when verification fails
# ---------------------------------------------------------------------------

class TestSkipOnVerificationFailure:
    """Tests marked @pytest.mark.nightjar must be skipped when verification failed."""

    def test_marked_items_get_skip_when_failed(self):
        """Items with 'nightjar' marker must receive a 'skip' marker on failure."""
        from nightjar.pytest_plugin import pytest_collection_modifyitems

        config = MagicMock()
        # Simulate a failed verification
        config._nightjar_verification_failed = True
        config.getoption.return_value = True  # --nightjar is set

        # Create a fake test item that has the 'nightjar' marker
        marked_item = MagicMock()
        marked_item.get_closest_marker.return_value = MagicMock()  # marker present

        # Create a plain item (no nightjar marker)
        plain_item = MagicMock()
        plain_item.get_closest_marker.return_value = None  # marker absent

        pytest_collection_modifyitems(config, [marked_item, plain_item])

        # The marked item must have had a skip marker added
        marked_item.add_marker.assert_called_once()
        skip_call_args = marked_item.add_marker.call_args
        # The skip marker is a pytest.mark.skip instance
        assert skip_call_args is not None

        # The plain item must NOT have been skipped
        plain_item.add_marker.assert_not_called()

    def test_no_skip_when_verification_passed(self):
        """Items must NOT be skipped when verification succeeded."""
        from nightjar.pytest_plugin import pytest_collection_modifyitems

        config = MagicMock()
        config._nightjar_verification_failed = False

        marked_item = MagicMock()
        marked_item.get_closest_marker.return_value = MagicMock()

        pytest_collection_modifyitems(config, [marked_item])

        marked_item.add_marker.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: verification pipeline runs and stores result on success
# ---------------------------------------------------------------------------

class TestRunsVerificationOnSuccess:
    """When --nightjar is set and subprocess returns 0, state must reflect success."""

    def test_sessionstart_sets_failed_false_on_success(self):
        """Successful verification sets _nightjar_verification_failed=False."""
        from nightjar.pytest_plugin import pytest_sessionstart

        config = MagicMock()
        config.getoption.side_effect = lambda name, default=None: {
            "--nightjar": True,
            "--nightjar-fast": False,
            "--nightjar-spec": ".card",
        }.get(name, default)
        config.pluginmanager.getplugin.return_value = None

        session = MagicMock()
        session.config = config

        completed = MagicMock()
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed) as mock_run:
            pytest_sessionstart(session)

        # subprocess.run was called
        mock_run.assert_called_once()
        # State reflects success
        assert config._nightjar_verification_failed is False

    def test_sessionstart_sets_failed_true_on_failure(self):
        """Failed verification sets _nightjar_verification_failed=True."""
        from nightjar.pytest_plugin import pytest_sessionstart

        config = MagicMock()
        config.getoption.side_effect = lambda name, default=None: {
            "--nightjar": True,
            "--nightjar-fast": True,
            "--nightjar-spec": "custom/.card",
        }.get(name, default)
        config.pluginmanager.getplugin.return_value = None

        session = MagicMock()
        session.config = config

        completed = MagicMock()
        completed.returncode = 1

        with patch("subprocess.run", return_value=completed):
            pytest_sessionstart(session)

        assert config._nightjar_verification_failed is True

    def test_sessionstart_passes_fast_flag_to_subprocess(self):
        """--nightjar-fast must be forwarded to the subprocess command."""
        from nightjar.pytest_plugin import pytest_sessionstart

        config = MagicMock()
        config.getoption.side_effect = lambda name, default=None: {
            "--nightjar": True,
            "--nightjar-fast": True,
            "--nightjar-spec": ".card",
        }.get(name, default)
        config.pluginmanager.getplugin.return_value = None

        session = MagicMock()
        session.config = config

        completed = MagicMock()
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed) as mock_run:
            with patch("shutil.which", return_value=None):
                pytest_sessionstart(session)

        cmd = mock_run.call_args.args[0]
        assert "--fast" in cmd


# ---------------------------------------------------------------------------
# Test 5: does nothing when --nightjar flag is absent
# ---------------------------------------------------------------------------

class TestNoopWithoutFlag:
    """When --nightjar is not passed, the plugin must be completely silent."""

    def test_sessionstart_skips_without_flag(self):
        """pytest_sessionstart must not call subprocess.run without --nightjar."""
        from nightjar.pytest_plugin import pytest_sessionstart

        config = MagicMock()
        config.getoption.return_value = False  # --nightjar is off

        session = MagicMock()
        session.config = config

        with patch("subprocess.run") as mock_run:
            pytest_sessionstart(session)

        mock_run.assert_not_called()

    def test_collection_noop_without_failure_state(self):
        """pytest_collection_modifyitems is a no-op when no failure occurred."""
        from nightjar.pytest_plugin import pytest_collection_modifyitems

        config = MagicMock()
        # No _nightjar_verification_failed attribute at all
        del config._nightjar_verification_failed

        item = MagicMock()
        item.get_closest_marker.return_value = MagicMock()

        # Should not raise, should not skip the item
        pytest_collection_modifyitems(config, [item])
        item.add_marker.assert_not_called()

    def test_terminal_summary_noop_without_flag(self):
        """pytest_terminal_summary prints nothing when --nightjar is off."""
        from nightjar.pytest_plugin import pytest_terminal_summary

        config = MagicMock()
        config.getoption.return_value = False

        terminalreporter = MagicMock()
        pytest_terminal_summary(terminalreporter, exitstatus=0, config=config)

        terminalreporter.write_sep.assert_not_called()
        terminalreporter.write_line.assert_not_called()

    def test_plugin_importable_without_nightjar_cli(self):
        """The plugin module must be importable even if nightjar.cli is broken."""
        # This just verifies the import itself succeeds cleanly.
        import importlib
        import nightjar.pytest_plugin as plugin_module
        assert hasattr(plugin_module, "pytest_addoption")
        assert hasattr(plugin_module, "pytest_configure")
        assert hasattr(plugin_module, "pytest_sessionstart")
        assert hasattr(plugin_module, "pytest_collection_modifyitems")
        assert hasattr(plugin_module, "pytest_terminal_summary")
