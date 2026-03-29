"""Unit tests for pkg_auditor module.

Tests cover:
- parse_package_spec
- score computation
- letter grade boundaries
- render_report_card
- render_json
- collect_py_files filtering
- install_to_temp (mocked)
- fetch_pypi_metadata (mocked)
- check_cves_osv (mocked)
- local directory mode
- cache read/write
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass

import pytest

# Adjust sys.path so we can import from src/
SRC_DIR = Path(__file__).parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nightjar.pkg_auditor import (
    AuditScores,
    PackageAuditResult,
    parse_package_spec,
    score_to_letter_grade,
    compute_scores,
    collect_py_files,
    render_report_card,
    render_json,
    fetch_pypi_metadata,
    check_cves_osv,
    install_to_temp,
    count_functions_and_annotations,
    scan_package_files,
    get_cache_path,
    load_cached_result,
    save_cached_result,
    temp_package_env,
    audit_package,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_scores(
    contract_coverage: float = 80.0,
    type_depth: float = 70.0,
    guard_density: float = 60.0,
    docstring_completeness: float = 50.0,
    cve_cleanliness: float = 100.0,
    overall: float = 74.0,
    letter_grade: str = "C",
) -> AuditScores:
    return AuditScores(
        contract_coverage=contract_coverage,
        type_depth=type_depth,
        guard_density=guard_density,
        docstring_completeness=docstring_completeness,
        cve_cleanliness=cve_cleanliness,
        overall=overall,
        letter_grade=letter_grade,
    )


def make_result(
    name: str = "mypackage",
    version: str = "1.2.3",
    files_scanned: int = 5,
    total_functions: int = 20,
    functions_with_invariants: int = 10,
    candidates: list | None = None,
    cves: list | None = None,
    scores: AuditScores | None = None,
    metadata: dict | None = None,
    findings: list[str] | None = None,
) -> PackageAuditResult:
    if candidates is None:
        candidates = []
    if cves is None:
        cves = []
    if scores is None:
        scores = make_scores()
    if metadata is None:
        metadata = {"summary": "A test package", "author": "Test Author", "license": "MIT"}
    if findings is None:
        findings = ["All checks passed"]
    return PackageAuditResult(
        name=name,
        version=version,
        files_scanned=files_scanned,
        total_functions=total_functions,
        functions_with_invariants=functions_with_invariants,
        candidates=candidates,
        cves=cves,
        scores=scores,
        metadata=metadata,
        findings=findings,
    )


# ── Tests: parse_package_spec ─────────────────────────────────────────────────


class TestParsePackageSpec:
    def test_simple_package_name(self):
        name, version, is_local = parse_package_spec("requests")
        assert name == "requests"
        assert version is None
        assert is_local is False

    def test_pinned_version(self):
        name, version, is_local = parse_package_spec("requests==2.31.0")
        assert name == "requests"
        assert version == "2.31.0"
        assert is_local is False

    def test_local_path_dotslash(self):
        name, version, is_local = parse_package_spec("./my-package")
        assert is_local is True
        assert version is None

    def test_local_path_absolute(self, tmp_path):
        path_str = str(tmp_path)
        name, version, is_local = parse_package_spec(path_str)
        assert is_local is True

    def test_package_with_underscore(self):
        name, version, is_local = parse_package_spec("my_package==0.1.0")
        assert name == "my_package"
        assert version == "0.1.0"
        assert is_local is False

    def test_package_with_hyphen(self):
        name, version, is_local = parse_package_spec("some-package")
        assert name == "some-package"
        assert version is None
        assert is_local is False

    def test_local_path_slash(self):
        name, version, is_local = parse_package_spec("/absolute/path/to/pkg")
        assert is_local is True


# ── Tests: score_to_letter_grade ─────────────────────────────────────────────


class TestScoreToLetterGrade:
    def test_a_plus(self):
        assert score_to_letter_grade(95) == "A+"
        assert score_to_letter_grade(100) == "A+"

    def test_a(self):
        assert score_to_letter_grade(90) == "A"
        assert score_to_letter_grade(94) == "A"

    def test_a_minus(self):
        assert score_to_letter_grade(87) == "A-"
        assert score_to_letter_grade(89) == "A-"

    def test_b_plus(self):
        assert score_to_letter_grade(83) == "B+"
        assert score_to_letter_grade(86) == "B+"

    def test_b(self):
        assert score_to_letter_grade(80) == "B"
        assert score_to_letter_grade(82) == "B"

    def test_b_minus(self):
        assert score_to_letter_grade(77) == "B-"
        assert score_to_letter_grade(79) == "B-"

    def test_c_plus(self):
        assert score_to_letter_grade(73) == "C+"
        assert score_to_letter_grade(76) == "C+"

    def test_c(self):
        assert score_to_letter_grade(70) == "C"
        assert score_to_letter_grade(72) == "C"

    def test_c_minus(self):
        assert score_to_letter_grade(67) == "C-"
        assert score_to_letter_grade(69) == "C-"

    def test_d_plus(self):
        assert score_to_letter_grade(63) == "D+"
        assert score_to_letter_grade(66) == "D+"

    def test_d(self):
        assert score_to_letter_grade(60) == "D"
        assert score_to_letter_grade(62) == "D"

    def test_f(self):
        assert score_to_letter_grade(59) == "F"
        assert score_to_letter_grade(0) == "F"


# ── Tests: compute_scores ─────────────────────────────────────────────────────


class TestComputeScores:
    def test_perfect_scores(self):
        scan_results = {}
        func_stats = (10, 20, 20, 10)  # total_funcs, annotated_params, total_params, with_docstrings
        cves: list = []
        scores = compute_scores(scan_results, func_stats, cves)
        # No functions with invariants → contract_coverage = 0
        # All params annotated → type_depth = 100
        # No guard clauses found → guard_density = 0 (no candidates)
        # All docstrings → docstring_completeness = 100
        # No CVEs → cve_cleanliness = 100
        assert scores.cve_cleanliness == 100.0
        assert scores.docstring_completeness == 100.0
        assert isinstance(scores.overall, float)
        assert isinstance(scores.letter_grade, str)

    def test_cve_penalty(self):
        scan_results = {}
        func_stats = (10, 0, 0, 0)
        cves = [{"id": "CVE-2023-0001"}, {"id": "CVE-2023-0002"}]
        scores = compute_scores(scan_results, func_stats, cves)
        assert scores.cve_cleanliness < 100.0

    def test_no_functions_zero_coverage(self):
        scan_results = {}
        func_stats = (0, 0, 0, 0)
        scores = compute_scores(scan_results, func_stats, [])
        assert scores.contract_coverage == 0.0

    def test_weighted_overall(self):
        """Overall must be weighted sum: 30% cov + 20% type + 20% guard + 15% doc + 15% cve."""
        scan_results = {}
        func_stats = (10, 10, 10, 10)  # all annotated and docstrings
        scores = compute_scores(scan_results, func_stats, [])
        # contract_coverage=0, type_depth=100, guard_density=0, docstring=100, cve=100
        expected = 0 * 0.30 + 100 * 0.20 + 0 * 0.20 + 100 * 0.15 + 100 * 0.15
        assert abs(scores.overall - expected) < 1.0

    def test_scores_are_clamped_0_to_100(self):
        scan_results = {}
        func_stats = (5, 50, 10, 5)  # annotated_params > total_params (edge case)
        scores = compute_scores(scan_results, func_stats, [])
        assert 0.0 <= scores.type_depth <= 100.0
        assert 0.0 <= scores.overall <= 100.0


# ── Tests: collect_py_files ────────────────────────────────────────────────────


class TestCollectPyFiles:
    def test_collects_py_files(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "helper.py").write_text("y = 2", encoding="utf-8")
        files = collect_py_files(tmp_path, "testpkg")
        assert len(files) == 2

    def test_excludes_pycache(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1", encoding="utf-8")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("cached", encoding="utf-8")
        files = collect_py_files(tmp_path, "testpkg")
        assert all("__pycache__" not in str(f) for f in files)

    def test_excludes_dist_info(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1", encoding="utf-8")
        dist = tmp_path / "mypkg-1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text("metadata", encoding="utf-8")
        (dist / "top_level.py").write_text("# dist", encoding="utf-8")
        files = collect_py_files(tmp_path, "testpkg")
        assert all(".dist-info" not in str(f) for f in files)

    def test_excludes_test_files(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("def test_x(): pass", encoding="utf-8")
        files = collect_py_files(tmp_path, "testpkg")
        names = [f.name for f in files]
        assert "test_module.py" not in names

    def test_returns_paths(self, tmp_path):
        (tmp_path / "a.py").write_text("pass", encoding="utf-8")
        files = collect_py_files(tmp_path, "testpkg")
        assert all(isinstance(f, Path) for f in files)


# ── Tests: count_functions_and_annotations ───────────────────────────────────


class TestCountFunctionsAndAnnotations:
    def test_counts_functions(self, tmp_path):
        source = """\
def foo(x: int) -> str:
    '''doc'''
    pass

def bar(y):
    pass
"""
        f = tmp_path / "mod.py"
        f.write_text(source, encoding="utf-8")
        total, annotated, total_params, with_docs = count_functions_and_annotations([f])
        assert total == 2
        assert annotated >= 1  # x: int is annotated
        assert total_params >= 2  # x and y

    def test_docstring_count(self, tmp_path):
        source = """\
def foo():
    '''Has docstring.'''
    pass

def bar():
    pass
"""
        f = tmp_path / "mod.py"
        f.write_text(source, encoding="utf-8")
        total, annotated, total_params, with_docs = count_functions_and_annotations([f])
        assert total == 2
        assert with_docs == 1

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        result = count_functions_and_annotations([f])
        assert result == (0, 0, 0, 0)


# ── Tests: render_report_card ─────────────────────────────────────────────────


class TestRenderReportCard:
    def test_contains_package_name(self):
        result = make_result(name="requests", version="2.31.0")
        output = render_report_card(result)
        assert "requests" in output

    def test_contains_version(self):
        result = make_result(name="requests", version="2.31.0")
        output = render_report_card(result)
        assert "2.31.0" in output

    def test_contains_overall_score(self):
        result = make_result(scores=make_scores(overall=74.0))
        output = render_report_card(result)
        # Should show score as number
        assert "74" in output

    def test_contains_letter_grade(self):
        result = make_result(scores=make_scores(letter_grade="B+", overall=83.0))
        output = render_report_card(result)
        assert "B+" in output

    def test_contains_files_scanned(self):
        result = make_result(files_scanned=23)
        output = render_report_card(result)
        assert "23" in output

    def test_contains_findings(self):
        result = make_result(findings=["Missing type annotations", "No CVEs found"])
        output = render_report_card(result)
        assert "Missing type annotations" in output

    def test_returns_string(self):
        result = make_result()
        output = render_report_card(result)
        assert isinstance(output, str)


# ── Tests: render_json ────────────────────────────────────────────────────────


class TestRenderJson:
    def test_valid_json(self):
        result = make_result()
        output = render_json(result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_name(self):
        result = make_result(name="flask")
        output = render_json(result)
        parsed = json.loads(output)
        assert parsed["name"] == "flask"

    def test_contains_version(self):
        result = make_result(version="3.0.0")
        output = render_json(result)
        parsed = json.loads(output)
        assert parsed["version"] == "3.0.0"

    def test_contains_scores(self):
        result = make_result()
        output = render_json(result)
        parsed = json.loads(output)
        assert "scores" in parsed
        assert "overall" in parsed["scores"]

    def test_contains_cves(self):
        cves = [{"id": "CVE-2023-0001", "details": "Remote code execution"}]
        result = make_result(cves=cves)
        output = render_json(result)
        parsed = json.loads(output)
        assert len(parsed["cves"]) == 1
        assert parsed["cves"][0]["id"] == "CVE-2023-0001"

    def test_contains_findings(self):
        result = make_result(findings=["Finding A", "Finding B"])
        output = render_json(result)
        parsed = json.loads(output)
        assert "Finding A" in parsed["findings"]


# ── Tests: install_to_temp (mocked) ──────────────────────────────────────────


class TestInstallToTemp:
    def test_success_returns_true(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = install_to_temp("requests", str(tmp_path))
            assert result is True

    def test_failure_returns_false(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Not found")
            result = install_to_temp("nonexistent-fake-package-xyz", str(tmp_path))
            assert result is False

    def test_calls_pip_with_target(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            install_to_temp("requests", str(tmp_path))
            args = mock_run.call_args[0][0]
            assert "--target" in args
            assert str(tmp_path) in args


# ── Tests: fetch_pypi_metadata (mocked) ──────────────────────────────────────


class TestFetchPypiMetadata:
    def test_returns_dict(self):
        fake_response = json.dumps({
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "summary": "HTTP library",
                "author": "Kenneth Reitz",
                "license": "Apache 2.0",
            },
            "vulnerabilities": [],
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = fake_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_pypi_metadata("requests")
        assert result["info"]["name"] == "requests"

    def test_uses_version_url_when_version_given(self):
        fake_response = json.dumps({
            "info": {"name": "requests", "version": "2.28.0"},
            "vulnerabilities": [],
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = fake_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        captured_url = []

        def fake_urlopen(url, timeout=10):
            captured_url.append(url if isinstance(url, str) else getattr(url, 'full_url', str(url)))
            return mock_response

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            fetch_pypi_metadata("requests", "2.28.0")

        assert any("2.28.0" in u for u in captured_url)


# ── Tests: check_cves_osv (mocked) ──────────────────────────────────────────


class TestCheckCvesOsv:
    def test_returns_empty_on_clean_package(self):
        fake_response = json.dumps({"vulns": []}).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = fake_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            cves = check_cves_osv("requests", "2.31.0")
        assert cves == []

    def test_returns_vulns_list(self):
        fake_response = json.dumps({
            "vulns": [
                {"id": "PYSEC-2021-001", "aliases": ["CVE-2021-12345"], "details": "XSS vulnerability"},
            ]
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = fake_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            cves = check_cves_osv("oldpackage", "0.1.0")
        assert len(cves) == 1
        assert cves[0]["id"] == "PYSEC-2021-001"

    def test_handles_network_error_gracefully(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            cves = check_cves_osv("requests", "2.31.0")
        # Should return empty list on error, not raise
        assert cves == []


# ── Tests: local directory mode ───────────────────────────────────────────────


class TestLocalDirectoryMode:
    def test_audit_local_directory(self, tmp_path):
        """audit_package should handle a local path without downloading."""
        # Create a small fake package
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'def hello(name: str) -> str:\n    """Say hello."""\n    return f"Hello {name}"\n',
            encoding="utf-8",
        )

        with patch("nightjar.pkg_auditor.check_cves_osv", return_value=[]):
            result = audit_package(str(pkg_dir))

        assert result.files_scanned >= 1
        assert result.total_functions >= 1
        assert isinstance(result.scores, AuditScores)

    def test_local_mode_skips_download(self, tmp_path):
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "mod.py").write_text("def foo(): pass", encoding="utf-8")

        with patch("nightjar.pkg_auditor.install_to_temp") as mock_install:
            with patch("nightjar.pkg_auditor.check_cves_osv", return_value=[]):
                audit_package(str(pkg_dir))
        # install_to_temp should NOT be called for local paths
        mock_install.assert_not_called()


# ── Tests: cache read/write ────────────────────────────────────────────────────


class TestCacheReadWrite:
    def test_cache_path_creation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = get_cache_path("requests", "2.31.0")
        assert "requests" in str(path)
        assert "2.31.0" in str(path)

    def test_save_and_load_result(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = make_result(name="requests", version="2.31.0")
        save_cached_result(result)
        loaded = load_cached_result("requests", "2.31.0")
        assert loaded is not None
        assert loaded.name == "requests"
        assert loaded.version == "2.31.0"

    def test_load_returns_none_when_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        loaded = load_cached_result("nonexistent", "9.9.9")
        assert loaded is None


# ── Tests: temp_package_env ───────────────────────────────────────────────────


class TestTempPackageEnv:
    def test_creates_temp_dir(self):
        with temp_package_env() as tmp:
            assert os.path.isdir(tmp)

    def test_cleans_up_on_exit(self):
        with temp_package_env() as tmp:
            tmp_path = tmp
        assert not os.path.exists(tmp_path)


# ── Tests: scan_package_files ─────────────────────────────────────────────────


class TestScanPackageFiles:
    def test_returns_dict(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text(
            'def foo(x: int) -> str:\n    if x < 0:\n        raise ValueError("neg")\n    return str(x)\n',
            encoding="utf-8",
        )
        results = scan_package_files([f])
        assert isinstance(results, dict)

    def test_skips_unparseable_files(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def (broken syntax!!!", encoding="utf-8")
        results = scan_package_files([f])
        # Should not raise; may return empty or the file with empty candidates
        assert isinstance(results, dict)

    def test_extracts_candidates_from_typed_code(self, tmp_path):
        f = tmp_path / "typed.py"
        f.write_text(
            'def add(a: int, b: int) -> int:\n    assert a >= 0\n    return a + b\n',
            encoding="utf-8",
        )
        results = scan_package_files([f])
        all_candidates = [c for cands in results.values() for c in cands]
        assert len(all_candidates) > 0
