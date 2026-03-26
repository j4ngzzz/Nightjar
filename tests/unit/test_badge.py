"""Tests for nightjar badge module.

TDD: Tests written FIRST before implementation.

Reference: Scout 7 N8 — "Nightjar Verified" badge via shields.io
"""
import pytest

from nightjar.badge import generate_badge_url, BadgeStatus


class TestBadgeStatus:
    """Tests for BadgeStatus enum."""

    def test_badge_status_values(self):
        """BadgeStatus has expected values."""
        assert BadgeStatus.PASSED
        assert BadgeStatus.FAILED
        assert BadgeStatus.UNKNOWN


class TestGenerateBadgeUrl:
    """Tests for generate_badge_url()."""

    def test_badge_url_includes_status_passed(self):
        """Badge URL contains 'passed' status for verified code."""
        url = generate_badge_url(status=BadgeStatus.PASSED, score=100)
        assert "passed" in url.lower() or "verified" in url.lower()

    def test_badge_url_includes_status_and_coverage(self):
        """Badge URL includes both status and coverage score."""
        url = generate_badge_url(status=BadgeStatus.PASSED, score=85)
        assert "85" in url

    def test_badge_url_is_shields_io(self):
        """Badge URL points to shields.io."""
        url = generate_badge_url(status=BadgeStatus.PASSED, score=100)
        assert "shields.io" in url

    def test_badge_url_failed_status(self):
        """Badge URL reflects failed status."""
        url = generate_badge_url(status=BadgeStatus.FAILED, score=45)
        assert "failed" in url.lower() or "red" in url.lower()

    def test_badge_url_unknown_status(self):
        """Badge URL reflects unknown status when no verification run."""
        url = generate_badge_url(status=BadgeStatus.UNKNOWN, score=0)
        assert "unknown" in url.lower() or "lightgrey" in url.lower()

    def test_badge_url_is_string(self):
        """generate_badge_url returns a string."""
        url = generate_badge_url(status=BadgeStatus.PASSED, score=100)
        assert isinstance(url, str)

    def test_badge_url_returns_valid_url_format(self):
        """Badge URL starts with https://."""
        url = generate_badge_url(status=BadgeStatus.PASSED, score=100)
        assert url.startswith("https://")

    def test_badge_url_score_zero(self):
        """Badge URL handles score of 0."""
        url = generate_badge_url(status=BadgeStatus.FAILED, score=0)
        assert isinstance(url, str)
        assert len(url) > 0

    def test_badge_url_from_verify_json(self, tmp_path):
        """generate_badge_url_from_report reads verify.json and returns badge URL."""
        import json
        from nightjar.badge import generate_badge_url_from_report

        report = {
            "verified": True,
            "confidence_score": 85,
            "stages": [{"stage": 0, "name": "preflight", "status": "pass", "errors": []}],
        }
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        url = generate_badge_url_from_report(str(report_path))
        assert "shields.io" in url
        assert "85" in url

    def test_badge_url_from_missing_report(self, tmp_path):
        """generate_badge_url_from_report returns unknown badge if no report."""
        from nightjar.badge import generate_badge_url_from_report

        url = generate_badge_url_from_report(str(tmp_path / "missing.json"))
        assert "shields.io" in url
        assert "unknown" in url.lower() or "lightgrey" in url.lower()

    def test_badge_markdown_snippet(self):
        """generate_badge_markdown returns markdown image link."""
        from nightjar.badge import generate_badge_markdown

        md = generate_badge_markdown(status=BadgeStatus.PASSED, score=100)
        assert md.startswith("![")
        assert "shields.io" in md
