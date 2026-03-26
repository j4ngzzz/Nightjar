"""EU CRA Compliance Certificate module for Nightjar.

Generates structured compliance artifacts from verification results.
Covers EU Cyber Resilience Act (EU CRA) requirements including:
- SBOM (Software Bill of Materials) verification
- Verification timestamp
- Vulnerability reporting fields (24-hour requirement)
- Tool attestation

TIME-SENSITIVE: EU CRA reporting obligations begin September 11, 2026.
(5 months from plan date of 2026-03-26)

References:
- Scout 7 S2 — EU CRA Compliance features
- Scout 7 N5 — Enterprise compliance packs (EU AI Act, SOC2, HIPAA)
- EU Cyber Resilience Act: https://www.aigovernancetoday.com/news/iso-42001-redefining-ai-governance-2026
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Nightjar tool metadata for attestation
_NIGHTJAR_VERSION = "0.3.0"  # Matches pyproject.toml
_TOOL_NAME = "Nightjar"
_TOOL_URL = "https://github.com/nightjar-dev/nightjar"


def _extract_sbom(report: dict) -> Optional[dict]:
    """Extract SBOM data from the verification report if available.

    Looks for SBOM data in the deps stage of the verification report.

    Args:
        report: Raw verify.json dict.

    Returns:
        SBOM dict if found, None otherwise.
    """
    for stage in report.get("stages", []):
        if stage.get("name") == "deps":
            sbom_data = stage.get("sbom")
            if sbom_data:
                return sbom_data
    return None


def _collect_vulnerabilities(report: dict) -> list[dict]:
    """Extract all violations/vulnerabilities from verification stages.

    Args:
        report: Raw verify.json dict.

    Returns:
        List of vulnerability dicts with stage, message, and severity.
    """
    vulnerabilities = []
    for stage in report.get("stages", []):
        stage_name = stage.get("name", "unknown")
        for error in stage.get("errors", []):
            msg = error.get("message", "")
            vulnerabilities.append(
                {
                    "stage": stage_name,
                    "message": msg,
                    # EU CRA requires classifying severity
                    "severity": _classify_severity(msg),
                    "counterexample": error.get("counterexample"),
                }
            )
    return vulnerabilities


def _classify_severity(message: str) -> str:
    """Classify a violation message as CRITICAL, HIGH, MEDIUM, or LOW.

    Simple heuristic classification based on message content.
    For EU CRA 24-hour reporting, CRITICAL and HIGH must be reported within 24h.

    Args:
        message: Violation error message.

    Returns:
        Severity string: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.
    """
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in ("sql injection", "xss", "command injection", "rce")):
        return "CRITICAL"
    if any(kw in msg_lower for kw in ("vulnerability", "injection", "overflow", "auth")):
        return "HIGH"
    if any(kw in msg_lower for kw in ("validation", "assertion", "postcondition")):
        return "MEDIUM"
    return "LOW"


def generate_compliance_cert(report: dict) -> dict:
    """Generate a structured EU CRA compliance certificate from a verification report.

    Produces a JSON-serializable dict containing:
    - Tool attestation (Nightjar version, verification method)
    - Verification result and confidence score
    - SBOM reference (extracted from deps stage if available)
    - Vulnerability report list (for 24-hour reporting requirement)
    - Compliance status

    Args:
        report: Raw verify.json dict from a nightjar verify run.

    Returns:
        Compliance certificate dict (JSON-serializable).

    References:
        Scout 7 S2 — EU CRA: SBOM requirements + 24h vulnerability reporting.
        EU CRA general application: September 11, 2026.
    """
    verified: bool = report.get("verified", False)
    score: int = int(report.get("confidence_score", 0))
    module: str = report.get("module", "unknown")
    timestamp: str = report.get("timestamp", datetime.now(timezone.utc).isoformat())

    sbom = _extract_sbom(report)
    vulnerabilities = _collect_vulnerabilities(report)
    high_severity = [v for v in vulnerabilities if v["severity"] in ("CRITICAL", "HIGH")]

    # EU CRA compliance status
    if verified:
        compliance_status = "compliant"
    elif not vulnerabilities:
        compliance_status = "not_verified"  # ran but couldn't determine
    else:
        compliance_status = "non_compliant"

    return {
        # Tool attestation
        "tool": {
            "name": _TOOL_NAME,
            "version": _NIGHTJAR_VERSION,
            "url": _TOOL_URL,
            "method": "formal_verification",
            "stages": [
                "preflight", "deps", "schema", "pbt", "formal"
            ],
        },
        # Verification result
        "verified": verified,
        "confidence_score": score,
        "module": module,
        "verified_at": timestamp,
        "compliance_status": compliance_status,
        # SBOM (EU CRA requirement)
        "sbom": sbom or {"note": "SBOM not available — run 'nightjar lock' to generate"},
        # Vulnerabilities (EU CRA 24-hour reporting requirement)
        "vulnerability_report": {
            "total_count": len(vulnerabilities),
            "critical_high_count": len(high_severity),
            "eu_cra_24h_reporting_required": len(high_severity) > 0,
            "incident_response": (
                "Report critical/high vulnerabilities within 24 hours "
                "per EU CRA Article 14 (effective September 11, 2026)."
            ) if high_severity else "No critical/high vulnerabilities detected.",
            "vulnerabilities": vulnerabilities,
        },
        # Regulatory context
        "regulatory": {
            "framework": "EU Cyber Resilience Act (EU CRA)",
            "effective_date": "2026-09-11",
            "article_14": "24-hour vulnerability reporting obligation",
            "note": (
                "This certificate attests to the formal verification status "
                "of AI-generated code at the time of generation. "
                "Re-verify after any code changes."
            ),
        },
    }


def export_compliance_cert(cert: dict, output_path: str) -> None:
    """Write a compliance certificate to a JSON file.

    Args:
        cert: Compliance certificate dict from generate_compliance_cert().
        output_path: File path to write the JSON certificate.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cert, f, indent=2, ensure_ascii=False)
