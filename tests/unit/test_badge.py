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


class TestGenerateShieldsJson:
    """Tests for generate_shields_json()."""

    def test_generate_shields_json_verified_high_confidence(self, tmp_path):
        """High-confidence verified report → brightgreen."""
        import json
        from nightjar.badge import generate_shields_json

        report = {"verified": True, "confidence_score": 95}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = generate_shields_json(str(report_path))

        assert result["schemaVersion"] == 1
        assert result["label"] == "nightjar"
        assert "95" in result["message"]
        assert "verified" in result["message"]
        assert result["color"] == "brightgreen"

    def test_generate_shields_json_verified_medium_confidence(self, tmp_path):
        """Medium-confidence (70-89) verified report → green."""
        import json
        from nightjar.badge import generate_shields_json

        report = {"verified": True, "confidence_score": 75}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = generate_shields_json(str(report_path))

        assert result["color"] == "green"
        assert "75" in result["message"]

    def test_generate_shields_json_verified_low_confidence(self, tmp_path):
        """Low-confidence (< 70) verified report → yellow."""
        import json
        from nightjar.badge import generate_shields_json

        report = {"verified": True, "confidence_score": 55}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = generate_shields_json(str(report_path))

        assert result["color"] == "yellow"
        assert "55" in result["message"]

    def test_generate_shields_json_failed(self, tmp_path):
        """Failed verification → red badge with 'failed' message."""
        import json
        from nightjar.badge import generate_shields_json

        report = {"verified": False, "confidence_score": 40}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = generate_shields_json(str(report_path))

        assert result["color"] == "red"
        assert "failed" in result["message"]
        assert "40" in result["message"]

    def test_generate_shields_json_no_report(self, tmp_path):
        """Missing report file → lightgrey with 'not verified' message."""
        from nightjar.badge import generate_shields_json

        result = generate_shields_json(str(tmp_path / "nonexistent.json"))

        assert result["schemaVersion"] == 1
        assert result["label"] == "nightjar"
        assert result["message"] == "not verified"
        assert result["color"] == "lightgrey"


class TestGenerateBadgeSvg:
    """Tests for generate_badge_svg()."""

    def test_generate_badge_svg_contains_nightjar(self, tmp_path):
        """SVG badge contains the label 'nightjar'."""
        import json
        from nightjar.badge import generate_badge_svg

        report = {"verified": True, "confidence_score": 90}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        svg = generate_badge_svg(str(report_path))

        assert "<svg" in svg
        assert "nightjar" in svg
        assert "verified" in svg

    def test_generate_badge_svg_color_scale(self, tmp_path):
        """SVG badge reflects the correct hex colour for each status."""
        import json
        from nightjar.badge import generate_badge_svg

        cases = [
            ({"verified": True, "confidence_score": 95}, "#4c1"),    # brightgreen
            ({"verified": True, "confidence_score": 80}, "#97ca00"),  # green
            ({"verified": True, "confidence_score": 60}, "#dfb317"),  # yellow
            ({"verified": False, "confidence_score": 30}, "#e05d44"), # red
        ]
        for report_data, expected_hex in cases:
            report_path = tmp_path / "verify.json"
            report_path.write_text(json.dumps(report_data), encoding="utf-8")
            svg = generate_badge_svg(str(report_path))
            assert expected_hex in svg, (
                f"Expected {expected_hex} in SVG for report {report_data}"
            )

    def test_generate_badge_svg_no_report_lightgrey(self, tmp_path):
        """SVG badge is lightgrey when no report is present."""
        from nightjar.badge import generate_badge_svg

        svg = generate_badge_svg(str(tmp_path / "missing.json"))

        assert "#9f9f9f" in svg  # lightgrey hex
        assert "not verified" in svg


class TestGenerateReadmeEmbed:
    """Tests for generate_readme_embed()."""

    def test_generate_readme_embed_format(self):
        """Embed returns correct raw.githubusercontent.com markdown link."""
        from nightjar.badge import generate_readme_embed

        md = generate_readme_embed("acme-org", "my-repo")

        assert md.startswith("![Nightjar]")
        assert "raw.githubusercontent.com" in md
        assert "acme-org" in md
        assert "my-repo" in md
        assert "master" in md
        assert ".card/badge.svg" in md

    def test_generate_readme_embed_custom_branch(self):
        """Embed uses the supplied branch name."""
        from nightjar.badge import generate_readme_embed

        md = generate_readme_embed("acme-org", "my-repo", branch="main")

        assert "main" in md
        assert "master" not in md


class TestWriteShieldsJson:
    """Tests for write_shields_json()."""

    def test_write_shields_json_creates_file(self, tmp_path):
        """write_shields_json creates the output file with valid JSON."""
        import json
        from nightjar.badge import write_shields_json

        report = {"verified": True, "confidence_score": 88}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        output_path = tmp_path / "shields.json"
        result = write_shields_json(str(report_path), str(output_path))

        assert result == output_path
        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["schemaVersion"] == 1
        assert data["label"] == "nightjar"
        assert data["color"] == "green"  # 88 → green

    def test_write_shields_json_creates_parent_dirs(self, tmp_path):
        """write_shields_json creates missing parent directories."""
        import json
        from nightjar.badge import write_shields_json

        report = {"verified": False, "confidence_score": 10}
        report_path = tmp_path / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        output_path = tmp_path / "deep" / "nested" / "shields.json"
        result = write_shields_json(str(report_path), str(output_path))

        assert result == output_path
        assert output_path.exists()
