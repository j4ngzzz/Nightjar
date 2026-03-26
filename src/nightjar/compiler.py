"""Dafny compile-to-target-language wrapper.

After verification passes, runs ``dafny build module.dfy --target {lang}``
to compile verified Dafny code to Python, JavaScript, Go, Java, or C#.

References:
- [REF-T01] Dafny CLI: ``dafny build module.dfy --target py``
  Supported targets: py, js, go, java, cs
  Amazon uses Dafny for auth services at 1 billion calls/second.

BEFORE MODIFYING: Read [REF-T01] Dafny docs on compilation targets.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


# [REF-T01] Dafny supports these compilation targets
SUPPORTED_TARGETS: frozenset[str] = frozenset({"py", "js", "go", "java", "cs"})

# Default timeout for dafny build (seconds)
_DEFAULT_TIMEOUT: int = 120


class UnsupportedTargetError(ValueError):
    """Raised when an unsupported compilation target is requested."""


@dataclass
class CompileResult:
    """Result from a Dafny compilation attempt."""
    success: bool
    target: str
    output_path: str
    stdout: str
    stderr: str


def validate_target(target: str) -> None:
    """Validate that target is a supported Dafny compilation target.

    Args:
        target: Language target string (py, js, go, java, cs).

    Raises:
        UnsupportedTargetError: If target is not in SUPPORTED_TARGETS.
    """
    if target not in SUPPORTED_TARGETS:
        raise UnsupportedTargetError(
            f"Unsupported target '{target}'. "
            f"Valid targets: {', '.join(sorted(SUPPORTED_TARGETS))}"
        )


def compile_dafny(
    dfy_path: str,
    target: str,
    output_dir: str,
    timeout: int = _DEFAULT_TIMEOUT,
) -> CompileResult:
    """Compile a Dafny file to the specified target language.

    Runs ``dafny build <dfy_path> --target:<target> --output:<output_dir/module>``.
    Respects DAFNY_PATH environment variable for custom binary location.

    Args:
        dfy_path: Path to the .dfy file to compile.
        target: Target language (py, js, go, java, cs).
        output_dir: Directory to write compiled output.
        timeout: Subprocess timeout in seconds.

    Returns:
        CompileResult with success status, stdout, stderr.

    Raises:
        UnsupportedTargetError: If target is not supported.
    """
    validate_target(target)

    dafny_bin = os.environ.get("DAFNY_PATH", "dafny")
    dfy_name = Path(dfy_path).stem
    output_path = str(Path(output_dir) / dfy_name)

    cmd = [
        dafny_bin,
        "build",
        dfy_path,
        f"--target:{target}",
        f"--output:{output_path}",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CompileResult(
            success=proc.returncode == 0,
            target=target,
            output_path=output_path if proc.returncode == 0 else "",
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False,
            target=target,
            output_path="",
            stdout="",
            stderr=f"Timeout: dafny build exceeded {timeout}s limit",
        )
