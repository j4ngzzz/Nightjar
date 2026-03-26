"""GitHub Action runner script for Nightjar Shadow CI.

This script is the entrypoint for the nightjar/verify@v1 GitHub Action.
It reads a verify.json report, generates a structured report and PR comment,
then posts the comment to the PR if a GitHub token is available.

Usage (from action.yml):
    python -m nightjar.shadow_ci_runner --mode shadow --report full ...

References:
- Scout 7 Feature 2 — Shadow CI Mode GitHub Action
- action.yml — action inputs/outputs
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from the action directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from nightjar.shadow_ci import run_shadow_ci, format_pr_comment
from nightjar.badge import generate_badge_url_from_report, BadgeStatus, generate_badge_url


def _post_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT for action outputs."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    else:
        # Fallback: print for debugging
        print(f"::set-output name={key}::{value}")


def _post_pr_comment(comment: str) -> None:
    """Post a PR comment via GitHub API if token is available.

    Uses GITHUB_TOKEN, GITHUB_REPOSITORY, and PR_NUMBER env vars.
    Silently skips if any are missing (non-PR contexts).
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER", "")

    if not all([token, repo, pr_number]):
        # Not in a PR context — print comment to stdout for debugging
        print("--- Nightjar PR Comment (preview) ---")
        print(comment)
        print("--- End PR Comment ---")
        return

    try:
        import urllib.request
        import urllib.error

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
        with urllib.request.urlopen(req) as resp:
            if resp.status not in (200, 201):
                print(f"Warning: Failed to post PR comment (HTTP {resp.status})")
    except Exception as exc:  # noqa: BLE001
        # Never block CI due to comment posting failure
        print(f"Warning: Could not post PR comment: {exc}")


def main() -> int:
    """Main entrypoint for the GitHub Action runner."""
    parser = argparse.ArgumentParser(description="Nightjar Shadow CI runner")
    parser.add_argument("--mode", default="shadow", choices=["shadow", "strict"])
    parser.add_argument("--report", default="full", choices=["full", "summary"])
    parser.add_argument("--verify-json", default=".card/verify.json")
    parser.add_argument("--security-pack", default="none")
    args = parser.parse_args()

    print(f"Nightjar Shadow CI — mode={args.mode}, report={args.report}")
    print(f"Reading: {args.verify_json}")

    result = run_shadow_ci(report_path=args.verify_json, mode=args.mode)

    # Print the report summary
    print(json.dumps(result.report, indent=2))

    # Set action outputs
    _post_github_output("verified", str(result.report.get("verified", False)).lower())
    _post_github_output("confidence-score", str(result.report.get("confidence_score", 0)))
    _post_github_output("violation-count", str(result.report.get("violation_count", 0)))

    # Generate badge URL
    badge_url = generate_badge_url_from_report(args.verify_json)
    _post_github_output("badge-url", badge_url)

    # Post PR comment
    if result.pr_comment:
        _post_pr_comment(result.pr_comment)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
