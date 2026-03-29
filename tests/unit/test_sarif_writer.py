"""Tests for SARIF writer module.

Validates write_sarif, validate_sarif, sarif_summary, and merge_sarif_files
against the SARIF 2.1.0 structure used by GitHub Code Scanning.

References:
- SARIF 2.1.0 spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
- GitHub Code Scanning: https://docs.github.com/en/code-security/code-scanning
"""

import json
import tempfile
from pathlib import Path

import pytest

from nightjar.types import StageResult, VerifyResult, VerifyStatus
from nightjar.sarif_writer import (
    merge_sarif_files,
    sarif_summary,
    validate_sarif,
    write_sarif,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fail_stage(stage: int = 0, name: str = "Preflight") -> StageResult:
    return StageResult(
        stage=stage,
        name=name,
        status=VerifyStatus.FAIL,
        duration_ms=50,
        errors=[{"message": f"Stage {stage} failed: something went wrong"}],
    )


def _pass_stage(stage: int = 2, name: str = "Schema") -> StageResult:
    return StageResult(
        stage=stage,
        name=name,
        status=VerifyStatus.PASS,
        duration_ms=30,
    )


def _timeout_stage(stage: int = 3, name: str = "PropertyTests") -> StageResult:
    return StageResult(
        stage=stage,
        name=name,
        status=VerifyStatus.TIMEOUT,
        duration_ms=5000,
        errors=[{"error": "Timed out after 5000 ms"}],
    )


def _make_result(
    *,
    verified: bool = False,
    stages: list[StageResult] | None = None,
) -> VerifyResult:
    if stages is None:
        stages = [_fail_stage(0, "Preflight"), _pass_stage(2, "Schema")]
    return VerifyResult(verified=verified, stages=stages, total_duration_ms=100)


def _minimal_sarif(n_results: int = 1) -> dict:
    """Return a structurally valid minimal SARIF 2.1.0 dict."""
    results = [
        {
            "ruleId": f"NJ00{i}",
            "message": {"text": f"Error {i}"},
            "level": "error",
        }
        for i in range(n_results)
    ]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Nightjar",
                        "version": "0.1.0",
                    }
                },
                "results": results,
            }
        ],
    }


# ---------------------------------------------------------------------------
# write_sarif tests
# ---------------------------------------------------------------------------

def test_write_sarif_creates_file():
    """write_sarif must create the file at the given path."""
    result = _make_result(verified=False, stages=[_fail_stage(0, "Preflight")])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "results.sarif"
        returned = write_sarif(result, out)
        assert out.exists(), "SARIF file was not created"
        assert returned == out


def test_write_sarif_returns_path_object():
    """write_sarif must return a Path (even if a str was passed in)."""
    result = _make_result()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = str(Path(tmpdir) / "results.sarif")
        returned = write_sarif(result, out)
        assert isinstance(returned, Path)


def test_write_sarif_valid_json():
    """The written file must be parseable JSON."""
    result = _make_result(verified=False, stages=[_fail_stage()])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "results.sarif"
        write_sarif(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_write_sarif_utf8_encoding():
    """The file must be written with UTF-8 encoding (handles unicode messages)."""
    unicode_error = {"message": "Échec: \u00e9\u00e0\u00fc — invalid input \u4e2d\u6587"}
    stage = StageResult(
        stage=0,
        name="Preflight",
        status=VerifyStatus.FAIL,
        duration_ms=10,
        errors=[unicode_error],
    )
    result = VerifyResult(verified=False, stages=[stage])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "unicode.sarif"
        write_sarif(result, out)
        raw = out.read_bytes()
        decoded = raw.decode("utf-8")
        assert "\u00e9" in decoded or "Échec" in decoded


def test_write_sarif_pretty_true_has_indentation():
    """pretty=True (the default) must produce indented JSON."""
    result = _make_result()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "pretty.sarif"
        write_sarif(result, out, pretty=True)
        content = out.read_text(encoding="utf-8")
        # Indented JSON has newlines after opening braces
        assert "\n" in content
        assert "  " in content


def test_write_sarif_pretty_false_is_compact():
    """pretty=False must produce single-line compact JSON."""
    result = _make_result()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "compact.sarif"
        write_sarif(result, out, pretty=False)
        content = out.read_text(encoding="utf-8")
        lines = [ln for ln in content.splitlines() if ln.strip()]
        assert len(lines) == 1, "Compact SARIF should be a single line"


def test_write_sarif_schema_and_version_present():
    """Written SARIF must contain $schema and version 2.1.0."""
    result = _make_result(verified=False, stages=[_fail_stage()])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "results.sarif"
        write_sarif(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["version"] == "2.1.0"
        assert "sarif" in data["$schema"].lower()


def test_write_sarif_passes_spec_path_to_locations():
    """When spec_path is given, failing results must have a physicalLocation."""
    stage = _fail_stage(0, "Preflight")
    result = VerifyResult(verified=False, stages=[stage])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "results.sarif"
        write_sarif(result, out, spec_path=".card/payment.card.md")
        data = json.loads(out.read_text(encoding="utf-8"))
        results = data["runs"][0]["results"]
        assert len(results) >= 1
        loc = results[0].get("locations", [])
        assert len(loc) >= 1
        assert "physicalLocation" in loc[0]


def test_write_sarif_pass_only_result_has_no_sarif_results():
    """A fully passing VerifyResult must produce zero SARIF result entries."""
    result = VerifyResult(
        verified=True,
        stages=[_pass_stage(0, "Preflight"), _pass_stage(2, "Schema")],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "pass.sarif"
        write_sarif(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["runs"][0]["results"] == []


def test_write_sarif_timeout_stage_produces_warning():
    """A TIMEOUT stage must produce a SARIF result with level=warning."""
    result = VerifyResult(verified=False, stages=[_timeout_stage(3, "PropertyTests")])
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "timeout.sarif"
        write_sarif(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        results = data["runs"][0]["results"]
        assert any(r["level"] == "warning" for r in results)


# ---------------------------------------------------------------------------
# validate_sarif tests
# ---------------------------------------------------------------------------

def test_validate_sarif_passes_for_well_formed():
    """validate_sarif must return empty list for a valid SARIF 2.1.0 dict."""
    sarif = _minimal_sarif()
    errors = validate_sarif(sarif)
    assert errors == [], f"Expected no errors but got: {errors}"


def test_validate_sarif_catches_missing_schema():
    """validate_sarif must catch a missing $schema field."""
    sarif = _minimal_sarif()
    del sarif["$schema"]
    errors = validate_sarif(sarif)
    assert any("schema" in e.lower() for e in errors)


def test_validate_sarif_catches_wrong_version():
    """validate_sarif must catch version != '2.1.0'."""
    sarif = _minimal_sarif()
    sarif["version"] = "2.0.0"
    errors = validate_sarif(sarif)
    assert any("version" in e.lower() for e in errors)


def test_validate_sarif_catches_missing_runs():
    """validate_sarif must catch missing or empty runs array."""
    sarif = _minimal_sarif()
    del sarif["runs"]
    errors = validate_sarif(sarif)
    assert any("runs" in e.lower() for e in errors)


def test_validate_sarif_catches_empty_runs():
    """validate_sarif must flag an empty runs list."""
    sarif = _minimal_sarif()
    sarif["runs"] = []
    errors = validate_sarif(sarif)
    assert any("run" in e.lower() for e in errors)


def test_validate_sarif_catches_missing_tool_driver():
    """validate_sarif must catch a run missing tool.driver."""
    sarif = _minimal_sarif()
    del sarif["runs"][0]["tool"]["driver"]
    errors = validate_sarif(sarif)
    assert any("driver" in e.lower() for e in errors)


def test_validate_sarif_catches_driver_missing_name():
    """validate_sarif must catch driver missing the name field."""
    sarif = _minimal_sarif()
    del sarif["runs"][0]["tool"]["driver"]["name"]
    errors = validate_sarif(sarif)
    assert any("name" in e.lower() for e in errors)


def test_validate_sarif_catches_driver_missing_version():
    """validate_sarif must catch driver missing the version field."""
    sarif = _minimal_sarif()
    del sarif["runs"][0]["tool"]["driver"]["version"]
    errors = validate_sarif(sarif)
    assert any("version" in e.lower() for e in errors)


def test_validate_sarif_catches_result_missing_rule_id():
    """validate_sarif must catch a result entry missing ruleId."""
    sarif = _minimal_sarif(n_results=1)
    del sarif["runs"][0]["results"][0]["ruleId"]
    errors = validate_sarif(sarif)
    assert any("ruleid" in e.lower() for e in errors)


def test_validate_sarif_catches_result_missing_message():
    """validate_sarif must catch a result entry missing message."""
    sarif = _minimal_sarif(n_results=1)
    del sarif["runs"][0]["results"][0]["message"]
    errors = validate_sarif(sarif)
    assert any("message" in e.lower() for e in errors)


def test_validate_sarif_catches_result_missing_level():
    """validate_sarif must catch a result entry missing level."""
    sarif = _minimal_sarif(n_results=1)
    del sarif["runs"][0]["results"][0]["level"]
    errors = validate_sarif(sarif)
    assert any("level" in e.lower() for e in errors)


def test_validate_sarif_catches_result_location_missing_physical():
    """validate_sarif must flag a location entry without physicalLocation."""
    sarif = _minimal_sarif(n_results=1)
    # Add a location that is missing physicalLocation
    sarif["runs"][0]["results"][0]["locations"] = [{"logicalLocations": []}]
    errors = validate_sarif(sarif)
    assert any("physicallocation" in e.lower() for e in errors)


def test_validate_sarif_catches_physical_location_missing_artifact():
    """validate_sarif must flag physicalLocation without artifactLocation."""
    sarif = _minimal_sarif(n_results=1)
    sarif["runs"][0]["results"][0]["locations"] = [
        {"physicalLocation": {"region": {"startLine": 1}}}
    ]
    errors = validate_sarif(sarif)
    assert any("artifactlocation" in e.lower() for e in errors)


def test_validate_sarif_multiple_errors_reported():
    """validate_sarif must report all errors, not just the first."""
    sarif = {}  # missing everything
    errors = validate_sarif(sarif)
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# sarif_summary tests
# ---------------------------------------------------------------------------

def test_sarif_summary_counts_errors():
    """sarif_summary must count error-level results correctly."""
    sarif = _minimal_sarif(n_results=3)
    summary = sarif_summary(sarif)
    assert "3" in summary
    assert "error" in summary.lower()


def test_sarif_summary_counts_warnings():
    """sarif_summary must count warning-level results correctly."""
    sarif = _minimal_sarif(n_results=0)
    sarif["runs"][0]["results"] = [
        {"ruleId": "NJ003", "message": {"text": "timeout"}, "level": "warning"}
    ]
    summary = sarif_summary(sarif)
    assert "1" in summary
    assert "warning" in summary.lower()


def test_sarif_summary_mixed_levels():
    """sarif_summary must correctly count a mix of errors and warnings."""
    sarif = _minimal_sarif(n_results=0)
    sarif["runs"][0]["results"] = [
        {"ruleId": "NJ000", "message": {"text": "e1"}, "level": "error"},
        {"ruleId": "NJ001", "message": {"text": "e2"}, "level": "error"},
        {"ruleId": "NJ003", "message": {"text": "w1"}, "level": "warning"},
    ]
    summary = sarif_summary(sarif)
    assert "2" in summary
    assert "1" in summary
    assert "error" in summary.lower()
    assert "warning" in summary.lower()


def test_sarif_summary_zero_findings():
    """sarif_summary must handle zero results gracefully."""
    sarif = _minimal_sarif(n_results=0)
    summary = sarif_summary(sarif)
    assert "0" in summary or "no" in summary.lower() or "pass" in summary.lower()


def test_sarif_summary_includes_filename_when_provided():
    """sarif_summary must include the filename when passed as kwarg."""
    sarif = _minimal_sarif(n_results=2)
    summary = sarif_summary(sarif, filename="nightjar.sarif")
    assert "nightjar.sarif" in summary


# ---------------------------------------------------------------------------
# merge_sarif_files tests
# ---------------------------------------------------------------------------

def test_merge_sarif_files_combines_runs():
    """merge_sarif_files must combine runs from multiple files into one document."""
    sarif_a = _minimal_sarif(n_results=1)
    sarif_b = _minimal_sarif(n_results=2)
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = Path(tmpdir) / "a.sarif"
        path_b = Path(tmpdir) / "b.sarif"
        path_a.write_text(json.dumps(sarif_a), encoding="utf-8")
        path_b.write_text(json.dumps(sarif_b), encoding="utf-8")

        merged = merge_sarif_files([path_a, path_b])

        assert "runs" in merged
        assert len(merged["runs"]) == 2


def test_merge_sarif_files_preserves_schema_and_version():
    """Merged SARIF must have correct $schema and version 2.1.0."""
    sarif_a = _minimal_sarif()
    sarif_b = _minimal_sarif()
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = Path(tmpdir) / "a.sarif"
        path_b = Path(tmpdir) / "b.sarif"
        path_a.write_text(json.dumps(sarif_a), encoding="utf-8")
        path_b.write_text(json.dumps(sarif_b), encoding="utf-8")

        merged = merge_sarif_files([path_a, path_b])

        assert merged["version"] == "2.1.0"
        assert "$schema" in merged


def test_merge_sarif_files_single_file():
    """merge_sarif_files with one file must return a valid SARIF with one run."""
    sarif_a = _minimal_sarif(n_results=2)
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = Path(tmpdir) / "a.sarif"
        path_a.write_text(json.dumps(sarif_a), encoding="utf-8")

        merged = merge_sarif_files([path_a])

        assert len(merged["runs"]) == 1
        assert len(merged["runs"][0]["results"]) == 2


def test_merge_sarif_files_empty_list():
    """merge_sarif_files with an empty list must return a valid empty SARIF."""
    merged = merge_sarif_files([])
    assert merged["version"] == "2.1.0"
    assert merged["runs"] == []


def test_merge_sarif_files_result_is_valid_sarif():
    """The merged output must pass validate_sarif (non-empty case)."""
    sarif_a = _minimal_sarif(n_results=1)
    sarif_b = _minimal_sarif(n_results=1)
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = Path(tmpdir) / "a.sarif"
        path_b = Path(tmpdir) / "b.sarif"
        path_a.write_text(json.dumps(sarif_a), encoding="utf-8")
        path_b.write_text(json.dumps(sarif_b), encoding="utf-8")

        merged = merge_sarif_files([path_a, path_b])
        errors = validate_sarif(merged)

        assert errors == [], f"Merged SARIF failed validation: {errors}"


# ---------------------------------------------------------------------------
# Integration: write_sarif output passes validate_sarif
# ---------------------------------------------------------------------------

def test_write_sarif_output_is_valid():
    """The SARIF produced by write_sarif must pass validate_sarif."""
    stages = [
        _fail_stage(0, "Preflight"),
        _pass_stage(2, "Schema"),
        _timeout_stage(3, "PropertyTests"),
    ]
    result = VerifyResult(verified=False, stages=stages)
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "results.sarif"
        write_sarif(result, out, spec_path=".card/test.card.md")
        data = json.loads(out.read_text(encoding="utf-8"))
        errors = validate_sarif(data)
        assert errors == [], f"write_sarif produced invalid SARIF: {errors}"
