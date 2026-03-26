"""Tests for Dafny binary detection and setup helper.

Reference: [REF-T01] Dafny verification-aware programming language
"""

import os
from unittest.mock import patch

import pytest


def test_find_dafny_returns_path_when_on_path():
    """find_dafny() returns path string when Dafny is found."""
    from contractd.dafny_setup import find_dafny

    with patch("shutil.which", return_value="/usr/local/bin/dafny"):
        result = find_dafny()
        assert result == "/usr/local/bin/dafny"


def test_find_dafny_returns_none_when_not_found():
    """find_dafny() returns None when Dafny is not on PATH."""
    from contractd.dafny_setup import find_dafny

    with patch("shutil.which", return_value=None):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DAFNY_PATH", None)
            result = find_dafny()
            assert result is None


def test_find_dafny_checks_env_var():
    """find_dafny() checks DAFNY_PATH env var if shutil.which fails."""
    from contractd.dafny_setup import find_dafny

    with patch("shutil.which", return_value=None):
        with patch.dict(os.environ, {"DAFNY_PATH": "/opt/dafny/dafny"}):
            with patch("os.path.isfile", return_value=True):
                result = find_dafny()
                assert result == "/opt/dafny/dafny"


def test_ensure_dafny_returns_path_when_found():
    """ensure_dafny() returns the path when Dafny is available."""
    from contractd.dafny_setup import ensure_dafny

    with patch("contractd.dafny_setup.find_dafny", return_value="/usr/bin/dafny"):
        assert ensure_dafny() == "/usr/bin/dafny"


def test_ensure_dafny_raises_when_not_found():
    """ensure_dafny() raises RuntimeError with install instructions."""
    from contractd.dafny_setup import ensure_dafny

    with patch("contractd.dafny_setup.find_dafny", return_value=None):
        with pytest.raises(RuntimeError, match="Dafny not found"):
            ensure_dafny()


def test_ensure_dafny_error_message_has_install_url():
    """Error message includes the Dafny releases URL."""
    from contractd.dafny_setup import ensure_dafny

    with patch("contractd.dafny_setup.find_dafny", return_value=None):
        with pytest.raises(RuntimeError, match="github.com/dafny-lang/dafny/releases"):
            ensure_dafny()


def test_get_dafny_version_returns_string():
    """get_dafny_version() returns version string from dafny binary."""
    from contractd.dafny_setup import get_dafny_version

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Dafny 4.4.0\n"
        mock_run.return_value.returncode = 0
        version = get_dafny_version("/usr/bin/dafny")
        assert "4.4.0" in version
