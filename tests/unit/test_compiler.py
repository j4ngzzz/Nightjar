"""Tests for Dafny compile-to-target-language wrapper.

Validates that compiler.py correctly invokes ``dafny build`` with the
right ``--target`` flag and handles success/failure cases.

References:
- [REF-T01] Dafny CLI: ``dafny build module.dfy --target py``
  Supported targets: py, js, go, java, cs
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from nightjar.compiler import (
    SUPPORTED_TARGETS,
    CompileResult,
    compile_dafny,
    validate_target,
    UnsupportedTargetError,
)


class TestSupportedTargets:
    """Test target language validation."""

    def test_all_targets_present(self):
        """All five Dafny compilation targets should be supported."""
        assert "py" in SUPPORTED_TARGETS
        assert "js" in SUPPORTED_TARGETS
        assert "go" in SUPPORTED_TARGETS
        assert "java" in SUPPORTED_TARGETS
        assert "cs" in SUPPORTED_TARGETS

    def test_validate_valid_target(self):
        """Valid targets should pass validation."""
        for target in SUPPORTED_TARGETS:
            validate_target(target)  # should not raise

    def test_validate_invalid_target_raises(self):
        """Invalid target should raise UnsupportedTargetError."""
        with pytest.raises(UnsupportedTargetError) as exc_info:
            validate_target("ruby")
        assert "ruby" in str(exc_info.value)
        assert "py" in str(exc_info.value)  # should mention valid targets


class TestCompileResult:
    """Test the CompileResult dataclass."""

    def test_success_result(self):
        result = CompileResult(
            success=True,
            target="py",
            output_path="dist/module.py",
            stdout="Compilation succeeded",
            stderr="",
        )
        assert result.success
        assert result.target == "py"

    def test_failure_result(self):
        result = CompileResult(
            success=False,
            target="js",
            output_path="",
            stdout="",
            stderr="Error: type mismatch",
        )
        assert not result.success
        assert "type mismatch" in result.stderr


class TestCompileDafny:
    """Test the compile_dafny function with mocked subprocess."""

    @patch("nightjar.compiler.subprocess.run")
    def test_successful_compilation(self, mock_run):
        """Successful compile should return success=True with output path."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Dafny program verifier did not attempt verification\n"
                   "Compiled assembly into dist/module.py",
            stderr="",
        )
        result = compile_dafny("module.dfy", target="py", output_dir="dist")
        assert result.success
        assert result.target == "py"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "dafny" in cmd[0] or cmd[0] == "dafny"
        assert "build" in cmd
        assert "--target:py" in cmd or "--target" in cmd

    @patch("nightjar.compiler.subprocess.run")
    def test_compilation_failure(self, mock_run):
        """Failed compile should return success=False with error."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: type mismatch at line 42",
        )
        result = compile_dafny("module.dfy", target="py", output_dir="dist")
        assert not result.success
        assert "type mismatch" in result.stderr

    @patch("nightjar.compiler.subprocess.run")
    def test_compile_to_javascript(self, mock_run):
        """JS target should use --target:js."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Compiled", stderr=""
        )
        compile_dafny("module.dfy", target="js", output_dir="dist")
        cmd = mock_run.call_args[0][0]
        assert "--target:js" in cmd

    @patch("nightjar.compiler.subprocess.run")
    def test_compile_to_go(self, mock_run):
        """Go target should use --target:go."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Compiled", stderr=""
        )
        compile_dafny("module.dfy", target="go", output_dir="dist")
        cmd = mock_run.call_args[0][0]
        assert "--target:go" in cmd

    def test_invalid_target_raises(self):
        """Invalid target should raise before subprocess call."""
        with pytest.raises(UnsupportedTargetError):
            compile_dafny("module.dfy", target="ruby", output_dir="dist")

    @patch("nightjar.compiler.subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Subprocess timeout should result in failure."""
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="dafny", timeout=60)
        result = compile_dafny("module.dfy", target="py", output_dir="dist")
        assert not result.success
        assert "timeout" in result.stderr.lower()

    @patch("nightjar.compiler.subprocess.run")
    def test_dafny_binary_env_var(self, mock_run):
        """DAFNY_PATH env var should override default 'dafny' binary."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Compiled", stderr=""
        )
        with patch.dict("os.environ", {"DAFNY_PATH": "/custom/dafny"}):
            compile_dafny("module.dfy", target="py", output_dir="dist")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/custom/dafny"

    @patch("nightjar.compiler.subprocess.run")
    def test_output_dir_created(self, mock_run):
        """Output directory should be passed to dafny build."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Compiled", stderr=""
        )
        compile_dafny("module.dfy", target="py", output_dir="dist/compiled")
        cmd = mock_run.call_args[0][0]
        # Check that output dir is referenced in the command (normalize separators)
        cmd_str = " ".join(cmd).replace("\\", "/")
        assert "dist/compiled" in cmd_str
