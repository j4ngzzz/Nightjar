"""Playwright e2e tests for the Nightjar badge server.

These tests verify that:
1. The badge HTML page serves the correct shields.io URL with the right status.
2. The inline SVG badge renders with the correct colour and score text.
3. The generated badge URL format matches the shields.io spec.

Skipped automatically when playwright is not installed.

References:
- nightjar-upgrade-plan.md U5.3 (lines 661-676)
- nightjar/badge.py — badge URL generation
- shields.io badge URL spec: https://shields.io/badges/static-badge
"""
from __future__ import annotations

import pytest

# conftest.py already calls pytest.importorskip("playwright") at module level,
# so any import error is caught before the tests run.
from playwright.sync_api import sync_playwright


class TestBadgeRendersVerifiedStatus:
    """Badge server serves correct SVG and HTML badge content."""

    def test_badge_renders_verified_status(self, badge_server: str):
        """Playwright: badge HTML page contains img with shields.io verified URL."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            # Block outbound network to shields.io — we only test our markup
            page.route("**/*", lambda route: (
                route.abort() if "shields.io" in route.request.url else route.continue_()
            ))

            page.goto(f"{badge_server}/badge")

            # The img#badge element must have src pointing to shields.io with
            # the correct label and status message for a PASSED 95% badge.
            img = page.locator("#badge")
            img.wait_for(state="attached")
            src = img.get_attribute("src")

            assert src is not None, "Badge img element has no src attribute"
            assert "shields.io" in src, f"Expected shields.io URL, got: {src}"
            assert "nightjar" in src, f"Expected 'nightjar' label in URL: {src}"
            assert "verified" in src or "95" in src, (
                f"Expected 'verified' or '95' in badge URL: {src}"
            )
            browser.close()

    def test_badge_svg_contains_score_text(self, badge_server: str):
        """Playwright: inline SVG badge at /badge.svg contains score text."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{badge_server}/badge.svg")

            # SVG content should contain the score value
            content = page.content()
            assert "95" in content, f"Expected '95' score in SVG badge content: {content[:200]}"
            assert "nightjar" in content.lower(), (
                f"Expected 'nightjar' label in SVG content: {content[:200]}"
            )
            browser.close()

    def test_badge_url_format_matches_shields_io_spec(self):
        """generate_badge_url() produces a valid shields.io static badge URL."""
        from nightjar.badge import BadgeStatus, generate_badge_url

        url = generate_badge_url(BadgeStatus.PASSED, 95)

        # Static badge format: https://img.shields.io/badge/{label}-{message}-{color}
        assert url.startswith("https://img.shields.io/badge/"), (
            f"Badge URL must start with shields.io prefix: {url}"
        )
        assert "brightgreen" in url, f"PASSED badge must be brightgreen: {url}"
        assert "95" in url, f"Score must appear in URL: {url}"

    def test_badge_url_failed_status_uses_red(self):
        """FAILED badge uses red colour per spec."""
        from nightjar.badge import BadgeStatus, generate_badge_url

        url = generate_badge_url(BadgeStatus.FAILED, 30)
        assert "red" in url, f"FAILED badge must use red: {url}"
        assert "30" in url, f"Score must appear in URL: {url}"

    def test_badge_url_unknown_status(self):
        """UNKNOWN badge uses lightgrey and shows 'unknown'."""
        from nightjar.badge import BadgeStatus, generate_badge_url

        url = generate_badge_url(BadgeStatus.UNKNOWN, 0)
        assert "lightgrey" in url, f"UNKNOWN badge must use lightgrey: {url}"
        assert "unknown" in url, f"UNKNOWN badge must show 'unknown': {url}"
