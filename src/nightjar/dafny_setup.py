"""Dafny binary detection and setup helper.

Detects the Dafny verification engine on the system PATH or via
DAFNY_PATH environment variable. Provides clear installation
instructions when Dafny is not found.

Reference: [REF-T01] Dafny — verification-aware programming language
Install: https://github.com/dafny-lang/dafny/releases
"""

import os
import shutil
import subprocess
from typing import Optional


def find_dafny() -> Optional[str]:
    """Find Dafny binary on PATH or in known locations.

    Checks (in order):
    1. shutil.which("dafny") — standard PATH lookup
    2. DAFNY_PATH environment variable — user-configured path

    Returns the path to the Dafny binary, or None if not found.
    Reference: [REF-T01] Dafny
    """
    # Check PATH first
    path = shutil.which("dafny")
    if path:
        return path

    # Check DAFNY_PATH env var
    env_path = os.environ.get("DAFNY_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    return None


def ensure_dafny() -> str:
    """Find Dafny or raise with installation instructions.

    Returns the path to the Dafny binary.
    Raises RuntimeError with install URL if not found.
    Reference: [REF-T01] Dafny
    """
    path = find_dafny()
    if path:
        return path
    raise RuntimeError(
        "Dafny not found. Install from: https://github.com/dafny-lang/dafny/releases\n"
        "Add to PATH, or set DAFNY_PATH environment variable."
    )


def get_dafny_version(dafny_path: str) -> str:
    """Get the Dafny version string from the binary.

    Reference: [REF-T01] Dafny
    """
    result = subprocess.run(
        [dafny_path, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()
