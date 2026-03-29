"""Tests for nightjar EU CRA Compliance Certificate module.

TDD: Tests written FIRST before implementation.

Reference: Scout 7 S2 — EU Cyber Resilience Act
TIME-SENSITIVE: EU CRA reporting obligations begin September 11, 2026 (5 months).
SBOM requirements, 24-hour vulnerability reporting.
"""
import json
import pytest
from datetime import datetime, timezone


class TestComplianceCertificate:
    """Tests for generate_compliance_cert()."""

    def test_compliance_cert_includes_sbom_verification_timestamp(self, tmp_path):
        """Compliance certificate includes SBOM and verification timestamp.

        Scout 7 S2: SBOM requirements + verification timestamp for EU CRA.
        """
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 90,
            "module": "payment",
            "stages": [
                {"stage": 0, "name": "preflight", "status": "pass", "errors": []},
                {"stage": 1, "name": "deps", "status": "pass", "errors": [],
                 "sbom": {"dependencies": [{"name": "requests", "version": "2.31.0"}]}},
            ],
            "timestamp": "2026-03-26T10:00:00Z",
        }

        cert = generate_compliance_cert(report)

        # Must include SBOM reference
        assert "sbom" in json.dumps(cert).lower() or "dependencies" in json.dumps(cert).lower()
        # Must include verification timestamp
        cert_str = json.dumps(cert)
        assert "timestamp" in cert_str or "verified_at" in cert_str

    def test_compliance_cert_is_dict(self, tmp_path):
        """Compliance certificate is a structured dict."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 85,
            "module": "auth",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        assert isinstance(cert, dict)

    def test_compliance_cert_includes_eu_cra_fields(self):
        """Compliance certificate includes EU CRA required fields."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 100,
            "module": "payment",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        cert_str = json.dumps(cert).lower()

        # EU CRA compliance fields
        assert "nightjar" in cert_str or "tool" in cert_str
        assert "verified" in cert_str

    def test_compliance_cert_failed_verification(self):
        """Compliance certificate reflects unverified status for failing checks."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": False,
            "confidence_score": 30,
            "module": "payment",
            "stages": [
                {"stage": 0, "name": "preflight", "status": "fail",
                 "errors": [{"message": "SQL injection detected"}]},
            ],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)

        # Must NOT claim compliance for failed verification
        cert_str = json.dumps(cert).lower()
        assert "not_verified" in cert_str or "unverified" in cert_str or \
               (cert.get("verified") is False) or \
               (cert.get("compliance_status") not in (None, "compliant"))

    def test_compliance_cert_to_json(self):
        """Compliance certificate serializes to valid JSON."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 95,
            "module": "auth",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        # Must be JSON-serializable
        json_str = json.dumps(cert)
        assert isinstance(json_str, str)
        assert len(json_str) > 10

    def test_compliance_cert_includes_tool_version(self):
        """Compliance certificate identifies the verification tool and version."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 90,
            "module": "payment",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        cert_str = json.dumps(cert).lower()
        assert "nightjar" in cert_str or "version" in cert_str

    def test_compliance_cert_vulnerability_reporting_24h(self):
        """Compliance cert includes 24-hour vulnerability reporting contact field."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": False,
            "confidence_score": 40,
            "module": "payment",
            "stages": [
                {"stage": 3, "name": "pbt", "status": "fail",
                 "errors": [{"message": "Vulnerability: SQL injection"}]},
            ],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        # EU CRA requires 24h vulnerability reporting
        cert_str = json.dumps(cert).lower()
        assert "vulnerabilit" in cert_str or "incident" in cert_str or "report" in cert_str


class TestComplianceExport:
    """Tests for compliance certificate export functions."""

    def test_export_compliance_cert_to_file(self, tmp_path):
        """export_compliance_cert writes JSON file to disk."""
        from nightjar.compliance import generate_compliance_cert, export_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 95,
            "module": "auth",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        output_path = tmp_path / "compliance.json"
        export_compliance_cert(cert, str(output_path))

        assert output_path.exists()
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)


class TestComplianceReviewerFixes:
    """Tests for Reviewer 9 fixes to compliance module."""

    def test_version_uses_nightjar_package_version(self):
        """Compliance cert uses nightjar.__version__, not hardcoded string."""
        import nightjar
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 90,
            "module": "auth",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        # Must match package version — NOT the old hardcoded "0.3.0"
        assert cert["tool"]["version"] == nightjar.__version__
        assert cert["tool"]["version"] == "0.1.1"
        assert cert["tool"]["version"] != "0.3.0"

    def test_owasp_results_integrated_when_provided(self):
        """Compliance cert includes OWASP results when provided (F3 integration)."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 90,
            "module": "payment",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        owasp_results = {
            "categories_checked": ["sql_injection", "xss"],
            "passed": True,
            "violations": [],
        }
        cert = generate_compliance_cert(report, owasp_results=owasp_results)

        assert cert["owasp_security"]["enabled"] is True
        assert "sql_injection" in cert["owasp_security"]["categories_checked"]
        assert cert["owasp_security"]["passed"] is True
        assert cert["owasp_security"]["violation_count"] == 0

    def test_owasp_violations_override_compliance_status(self):
        """OWASP violations downgrade compliance_status from compliant."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,  # formally verified
            "confidence_score": 95,
            "module": "login",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        owasp_results = {
            "categories_checked": ["sql_injection"],
            "passed": False,
            "violations": [{"category": "sql_injection", "input": "' OR 1=1--"}],
        }
        cert = generate_compliance_cert(report, owasp_results=owasp_results)

        # Even though formally verified, OWASP violations make it non_compliant
        assert cert["compliance_status"] == "non_compliant"
        assert cert["owasp_security"]["violation_count"] == 1

    def test_owasp_section_disabled_when_not_provided(self):
        """OWASP section shows disabled when no results provided."""
        from nightjar.compliance import generate_compliance_cert

        report = {
            "verified": True,
            "confidence_score": 85,
            "module": "auth",
            "stages": [],
            "timestamp": "2026-03-26T10:00:00Z",
        }
        cert = generate_compliance_cert(report)
        assert cert["owasp_security"]["enabled"] is False
