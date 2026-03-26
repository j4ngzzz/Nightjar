"""Nightjar Shadow CI runner — importable module entry point.

This module is invoked by the GitHub Action via:
    python -m nightjar.shadow_ci_runner

It bridges the GitHub Action YAML to the shadow_ci.py Python logic.
Environment variables (not shell arguments) carry the action inputs to
avoid GitHub Actions script injection vulnerabilities.

Security design:
    Inputs are passed via environment variables set in action.yml:
        NIGHTJAR_CI_MODE, NIGHTJAR_CI_REPORT, NIGHTJAR_CI_VERIFY_JSON,
        NIGHTJAR_SECURITY_PACK
    The shell `run:` block in action.yml uses ONLY these env vars —
    never interpolates ${{ inputs.* }} directly into shell commands.

References:
- Scout 7 Feature 2 — Shadow CI Mode GitHub Action
- OWASP Top 10 A03:2021 — Injection (script injection prevention)
- GitHub Actions security hardening: use env vars, not direct input interpolation
"""
import argparse
import json
import os
import sys

from nightjar.shadow_ci import run_shadow_ci, format_pr_comment
from nightjar.badge import generate_badge_url_from_report


def _post_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT for action outputs.

    Args:
        key: Output variable name.
        value: Output value string.
    """
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        try:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"{key}={value}\n")
        except OSError:
            # Non-fatal — output not available in all contexts
            pass


def _post_pr_comment(comment: str) -> None:
    """Post a PR comment via GitHub API if token is available.

    Uses GITHUB_TOKEN, GITHUB_REPOSITORY, and PR_NUMBER env vars.
    Silently skips if any are missing (non-PR contexts).

    Security: uses urllib (stdlib only), no shell subprocess.

    Args:
        comment: Markdown string for the PR comment body.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER", "")

    if not all([token, repo, pr_number]):
        # Not in a PR context — print for local debugging
        # Use errors='replace' to handle emoji/non-ASCII on Windows consoles
        safe_comment = comment[:500].encode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ).decode(sys.stdout.encoding or "utf-8", errors="replace")
        print("--- Nightjar Shadow CI Report (preview) ---")
        print(safe_comment)
        print("--- End Report ---")
        return

    try:
        import urllib.request

        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        payload = json.dumps({"body": comment}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            if resp.status not in (200, 201):
                print(f"Warning: Failed to post PR comment (HTTP {resp.status})")
    except Exception as exc:  # noqa: BLE001
        # NEVER block CI due to comment posting failure
        print(f"Warning: Could not post PR comment: {exc}")


def main() -> int:
    """Main entrypoint for the GitHub Action runner.

    Reads inputs from ENVIRONMENT VARIABLES (not shell args interpolation)
    to prevent GitHub Actions script injection.

    Returns:
        Exit code: 0 always in shadow mode; non-zero on failure in strict mode.
    """
    parser = argparse.ArgumentParser(description="Nightjar Shadow CI runner")
    # All string args are read from env vars in action.yml — these are defaults only
    parser.add_argument(
        "--mode",
        default=os.environ.get("NIGHTJAR_CI_MODE", "shadow"),
        choices=["shadow", "strict"],
    )
    parser.add_argument(
        "--report",
        default=os.environ.get("NIGHTJAR_CI_REPORT", "full"),
        choices=["full", "summary"],
    )
    parser.add_argument(
        "--verify-json",
        default=os.environ.get("NIGHTJAR_CI_VERIFY_JSON", ".card/verify.json"),
    )
    parser.add_argument(
        "--security-pack",
        default=os.environ.get("NIGHTJAR_SECURITY_PACK", "none"),
    )
    # parse_known_args so unit tests can pass pytest args without breaking
    args, _ = parser.parse_known_args()

    print(f"Nightjar Shadow CI — mode={args.mode}, report={args.report}")
    print(f"Reading: {args.verify_json}")

    result = run_shadow_ci(report_path=args.verify_json, mode=args.mode)

    # Print the report summary
    print(json.dumps(result.report, indent=2))

    # Set GitHub Action outputs
    _post_github_output("verified", str(result.report.get("verified", False)).lower())
    _post_github_output("confidence-score", str(result.report.get("confidence_score", 0)))
    _post_github_output("violation-count", str(result.report.get("violation_count", 0)))
    badge_url = generate_badge_url_from_report(args.verify_json)
    _post_github_output("badge-url", badge_url)

    # Post PR comment
    if result.pr_comment:
        _post_pr_comment(result.pr_comment)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
