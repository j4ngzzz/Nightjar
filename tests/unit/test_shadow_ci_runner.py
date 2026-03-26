"""Tests for nightjar.shadow_ci_runner module.

TDD: Tests written for Reviewer 9 fixes.

Reviewer 9 (CRITICAL):
1. nightjar.shadow_ci_runner module was missing — action.yml referenced it
2. Script injection vulnerability: inputs interpolated directly in shell run block

References:
- Scout 7 Feature 2 — Shadow CI GitHub Action
- OWASP A03:2021 — Injection (script injection prevention)
- GitHub Actions security: use env vars, not direct input interpolation
"""
import json
import os
import sys
import pytest
from unittest.mock import patch


class TestShadowCIRunnerModule:
    """Tests that nightjar.shadow_ci_runner is a valid importable module."""

    def test_module_is_importable(self):
        """nightjar.shadow_ci_runner can be imported (was missing before fix)."""
        import nightjar.shadow_ci_runner
        assert nightjar.shadow_ci_runner is not None

    def test_module_has_main_function(self):
        """shadow_ci_runner has a main() entry point."""
        from nightjar.shadow_ci_runner import main
        assert callable(main)

    def test_module_can_be_invoked_as_main(self, tmp_path):
        """python -m nightjar.shadow_ci_runner runs without error."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "nightjar.shadow_ci_runner"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "NIGHTJAR_CI_MODE": "shadow", "PYTHONIOENCODING": "utf-8"},
        )
        # Should exit 0 in shadow mode even with no report file
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_main_reads_mode_from_env_not_shell(self, tmp_path):
        """main() reads NIGHTJAR_CI_MODE from env var (script injection fix)."""
        from nightjar.shadow_ci_runner import main

        report = {"verified": True, "confidence_score": 90, "stages": []}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        with patch.dict(os.environ, {
            "NIGHTJAR_CI_MODE": "shadow",
            "NIGHTJAR_CI_VERIFY_JSON": str(report_path),
        }), patch("sys.argv", ["shadow_ci_runner"]):
            exit_code = main()

        assert exit_code == 0  # shadow mode always 0

    def test_main_shadow_mode_always_exits_zero(self, tmp_path):
        """main() in shadow mode exits 0 even with failing verification."""
        from nightjar.shadow_ci_runner import main

        report = {"verified": False, "confidence_score": 10, "stages": [
            {"stage": 0, "name": "preflight", "status": "fail",
             "errors": [{"message": "SQL injection detected"}]},
        ]}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        with patch.dict(os.environ, {
            "NIGHTJAR_CI_MODE": "shadow",
            "NIGHTJAR_CI_VERIFY_JSON": str(report_path),
        }), patch("sys.argv", ["shadow_ci_runner"]):
            exit_code = main()

        assert exit_code == 0

    def test_main_strict_mode_exits_nonzero_on_failure(self, tmp_path):
        """main() in strict mode exits non-zero on verification failure."""
        from nightjar.shadow_ci_runner import main

        report = {"verified": False, "confidence_score": 30, "stages": [
            {"stage": 0, "name": "preflight", "status": "fail",
             "errors": [{"message": "Invariant violated"}]},
        ]}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        with patch.dict(os.environ, {
            "NIGHTJAR_CI_MODE": "strict",
            "NIGHTJAR_CI_VERIFY_JSON": str(report_path),
        }), patch("sys.argv", ["shadow_ci_runner"]):
            exit_code = main()

        assert exit_code != 0


class TestScriptInjectionFix:
    """Tests that verify the script injection vulnerability is fixed."""

    def test_action_yml_uses_env_vars_not_input_interpolation(self):
        """action.yml passes inputs via env vars, not direct shell interpolation.

        Before fix: run: python -m ... --mode "${{ inputs.mode }}"
                    (dangerous: inputs.mode could contain shell metacharacters)
        After fix:  env: NIGHTJAR_CI_MODE: ${{ inputs.mode }}
                    run: python -m nightjar.shadow_ci_runner
                    (safe: env vars are not shell-interpreted)
        """
        from pathlib import Path

        action_yml = Path(".github/nightjar-action/action.yml").read_text(encoding="utf-8")

        # Must NOT have ${{ inputs.* }} in the run: block (only in env: block)
        lines = action_yml.split("\n")
        in_run_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("run:"):
                in_run_block = True
                continue
            if in_run_block:
                # A new key at the same indentation level ends the run block
                if stripped and not stripped.startswith("#") and ":" in stripped and not stripped.startswith("-"):
                    in_run_block = False
                # No ${{ inputs.* }} should appear in the run block
                if "${{" in line and "inputs." in line:
                    pytest.fail(
                        f"Script injection vulnerability: inputs interpolated in run block: {line!r}"
                    )
