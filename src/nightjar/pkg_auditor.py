"""PyPI Package Auditor — scan any package for contract coverage and known CVEs.

Downloads any PyPI package (or scans a local directory), runs Nightjar's scanner
on every .py file, computes weighted scores, checks CVEs via OSV, and renders a
terminal report card with letter grades (A+ through F).

Think "Lighthouse score for Python packages."

References:
- [REF-T03] Hypothesis for PBT invariant patterns
- [REF-T08] Pydantic for schema validation
- [REF-T05] pip-audit for CVE checking pattern
"""

from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Generator, Optional

from nightjar.scanner import ScanCandidate, scan_file_from_string

# ── Version for User-Agent ─────────────────────────────────────────────────────

try:
    from importlib.metadata import version as _pkg_version
    _NIGHTJAR_VERSION = _pkg_version("nightjar-verify")
except Exception:
    _NIGHTJAR_VERSION = "0.1.0"

_USER_AGENT = f"nightjar/{_NIGHTJAR_VERSION} (+https://github.com/j4ngzzz/Nightjar)"

logger = logging.getLogger(__name__)

PYPI_API = "https://pypi.org/pypi/{name}/json"
PYPI_VERSION_API = "https://pypi.org/pypi/{name}/{version}/json"
OSV_API = "https://api.osv.dev/v1/query"


# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class AuditScores:
    """Weighted scores for a PyPI package audit."""

    contract_coverage: float = 0.0      # 0-100: % of functions with extractable invariants
    type_depth: float = 0.0             # 0-100: % of params + returns annotated
    guard_density: float = 0.0          # 0-100: % of non-trivial funcs with guard clauses
    docstring_completeness: float = 0.0  # 0-100: % of public funcs with docstrings
    cve_cleanliness: float = 100.0       # 0-100: 100 if 0 CVEs, scaled down per CVE
    overall: float = 0.0                 # 0-100: weighted sum
    letter_grade: str = "F"              # A+ through F


@dataclass
class PackageAuditResult:
    """Full result of a package audit."""

    name: str
    version: str
    files_scanned: int
    total_functions: int
    functions_with_invariants: int
    candidates: list[ScanCandidate]
    cves: list[dict]
    scores: AuditScores
    metadata: dict
    findings: list[str]


# ── Parse spec ────────────────────────────────────────────────────────────────


def parse_package_spec(spec: str) -> tuple[str, Optional[str], bool]:
    """Parse a package spec into (name, version_or_none, is_local_path).

    Handles:
    - "requests"           → ("requests", None, False)
    - "requests==2.31.0"   → ("requests", "2.31.0", False)
    - "./local-pkg"        → ("local-pkg", None, True)
    - "/absolute/path"     → (basename, None, True)

    Args:
        spec: Package spec string from the CLI.

    Returns:
        Tuple of (name, version, is_local).
    """
    # Local path: starts with ./ or / or points to an existing directory
    if spec.startswith("./") or spec.startswith("/") or spec.startswith(".\\"):
        name = Path(spec).name or spec.lstrip("./")
        return (name, None, True)

    # Windows drive letter paths (C:\foo, D:/bar)
    if len(spec) >= 2 and spec[1] == ':':
        return spec, None, True

    # Check if it's a path to an existing directory (absolute or relative)
    p = Path(spec)
    if p.exists() and p.is_dir():
        return (p.name, None, True)

    # PyPI spec: may contain == for pinned version
    if "==" in spec:
        parts = spec.split("==", 1)
        name = parts[0].strip()
        version = parts[1].strip() if len(parts) > 1 else None
        return (name, version, False)

    return (spec.strip(), None, False)


# ── Score helpers ─────────────────────────────────────────────────────────────


def score_to_letter_grade(score: float) -> str:
    """Convert a 0-100 numeric score to a letter grade.

    Boundaries:
        A+ >= 95, A 90-94, A- 87-89,
        B+ 83-86, B  80-82, B- 77-79,
        C+ 73-76, C  70-72, C- 67-69,
        D+ 63-66, D  60-62, F < 60

    Args:
        score: Numeric score 0-100.

    Returns:
        Letter grade string.
    """
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 87:
        return "A-"
    if score >= 83:
        return "B+"
    if score >= 80:
        return "B"
    if score >= 77:
        return "B-"
    if score >= 73:
        return "C+"
    if score >= 70:
        return "C"
    if score >= 67:
        return "C-"
    if score >= 63:
        return "D+"
    if score >= 60:
        return "D"
    return "F"


# ── Compute scores ────────────────────────────────────────────────────────────


def compute_scores(
    scan_results: dict[str, list[ScanCandidate]],
    func_stats: tuple[int, int, int, int],
    cves: list[dict],
) -> AuditScores:
    """Compute weighted audit scores from scan data.

    Weights:
        30% contract coverage (funcs_with_invariants / total_funcs)
        20% type annotation depth (annotated_params / total_params)
        20% guard clause density (funcs_with_guards / total_funcs)
        15% docstring completeness (funcs_with_docstrings / total_funcs)
        15% CVE cleanliness (100 if 0 CVEs, -20 per CVE, floor 0)

    Args:
        scan_results: Mapping of file path → list[ScanCandidate].
        func_stats: (total_funcs, annotated_params, total_params, with_docstrings)
        cves: List of CVE dicts from OSV API.

    Returns:
        Populated AuditScores instance.
    """
    total_funcs, annotated_params, total_params, with_docstrings = func_stats

    # 1. Contract coverage: % of functions that appear in scan results
    all_candidates = [c for cands in scan_results.values() for c in cands]
    func_names_with_invariants: set[str] = {
        c.function_name for c in all_candidates if c.function_name
    }
    if total_funcs > 0:
        contract_coverage = min(100.0, (len(func_names_with_invariants) / total_funcs) * 100)
    else:
        contract_coverage = 0.0

    # 2. Type annotation depth: % of params annotated
    if total_params > 0:
        type_depth = min(100.0, (annotated_params / total_params) * 100)
    else:
        type_depth = 0.0

    # 3. Guard clause density: % of functions that have at least one guard clause candidate
    guard_funcs: set[str] = {
        c.function_name
        for cands in scan_results.values()
        for c in cands
        if c.source == "guard_clause" and c.function_name
    }
    if total_funcs > 0:
        guard_density = min(100.0, (len(guard_funcs) / total_funcs) * 100)
    else:
        guard_density = 0.0

    # 4. Docstring completeness
    if total_funcs > 0:
        docstring_completeness = min(100.0, (with_docstrings / total_funcs) * 100)
    else:
        docstring_completeness = 0.0

    # 5. CVE cleanliness: 100 for 0 CVEs, -20 per CVE, floor 0
    cve_cleanliness = max(0.0, 100.0 - len(cves) * 20.0)

    # Weighted overall
    overall = (
        contract_coverage * 0.30
        + type_depth * 0.20
        + guard_density * 0.20
        + docstring_completeness * 0.15
        + cve_cleanliness * 0.15
    )
    overall = min(100.0, max(0.0, overall))

    return AuditScores(
        contract_coverage=round(contract_coverage, 1),
        type_depth=round(type_depth, 1),
        guard_density=round(guard_density, 1),
        docstring_completeness=round(docstring_completeness, 1),
        cve_cleanliness=round(cve_cleanliness, 1),
        overall=round(overall, 1),
        letter_grade=score_to_letter_grade(overall),
    )


# ── File collection ───────────────────────────────────────────────────────────


def collect_py_files(install_dir: Path | str, package_name: str) -> list[Path]:
    """Find all .py source files in an installed package directory.

    Excludes: __pycache__, *.dist-info, test directories.

    Args:
        install_dir: Root directory to walk.
        package_name: Package name (used for logging, not filtering).

    Returns:
        List of Path objects pointing to .py source files.
    """
    root = Path(install_dir)
    all_py = list(root.rglob("*.py"))

    def is_source(p: Path) -> bool:
        parts = p.parts
        for seg in parts:
            if seg.endswith(".dist-info") or seg == "__pycache__":
                return False
            # Exclude test directories: "tests", "test", "test_*" as directory name
            # but only when the segment is a directory component, not a file name
            if seg in ("tests", "test"):
                return False
        # Also exclude test files by name pattern (test_*.py or *_test.py)
        stem = p.stem
        if stem.startswith("test_") or stem.endswith("_test"):
            return False
        return True

    return [p for p in all_py if is_source(p)]


# ── AST function/annotation counting ─────────────────────────────────────────


def count_functions_and_annotations(
    py_files: list[Path],
) -> tuple[int, int, int, int]:
    """Count functions, annotated params, total params, and docstrings across files.

    Args:
        py_files: List of .py file paths to analyze.

    Returns:
        Tuple of (total_funcs, annotated_params, total_params, with_docstrings).
    """
    total_funcs = 0
    annotated_params = 0
    total_params = 0
    with_docstrings = 0

    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            if not source.strip():
                continue
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            total_funcs += 1

            # Count docstring
            if ast.get_docstring(node):
                with_docstrings += 1

            # Count params (skip self, cls)
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                total_params += 1
                if arg.annotation is not None:
                    annotated_params += 1

            # Count *args annotation
            if node.args.vararg and node.args.vararg.annotation is not None:
                total_params += 1
                annotated_params += 1
            elif node.args.vararg:
                total_params += 1

            # Count **kwargs annotation
            if node.args.kwarg and node.args.kwarg.annotation is not None:
                total_params += 1
                annotated_params += 1
            elif node.args.kwarg:
                total_params += 1

            # Count return annotation
            if node.returns is not None:
                total_params += 1
                annotated_params += 1
            else:
                total_params += 1

    return total_funcs, annotated_params, total_params, with_docstrings


# ── Scan files ────────────────────────────────────────────────────────────────


def scan_package_files(py_files: list[Path]) -> dict[str, list[ScanCandidate]]:
    """Run nightjar scanner on each .py file in the package.

    Args:
        py_files: List of .py file paths.

    Returns:
        Dict mapping file path string → list of ScanCandidate (only files with results).
    """
    results: dict[str, list[ScanCandidate]] = {}
    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            candidates = scan_file_from_string(source)
            if candidates:
                results[str(f)] = candidates
        except Exception as exc:
            logger.debug("scan skipped %s: %s", f, exc)
    return results


# ── PyPI API calls ────────────────────────────────────────────────────────────


def fetch_pypi_metadata(name: str, version: Optional[str] = None) -> dict:
    """Fetch package metadata from the PyPI JSON API.

    Args:
        name: Package name.
        version: Specific version, or None for latest.

    Returns:
        Full PyPI JSON response dict.

    Raises:
        urllib.error.URLError: On network errors.
        json.JSONDecodeError: On malformed responses.
    """
    if version:
        url = PYPI_VERSION_API.format(name=name, version=version)
    else:
        url = PYPI_API.format(name=name)

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def check_cves_osv(name: str, version: str) -> list[dict]:
    """Check for known vulnerabilities via the OSV API.

    Args:
        name: Package name.
        version: Package version string.

    Returns:
        List of vulnerability dicts. Empty list on error or no vulns.
    """
    payload = {
        "package": {"name": name, "ecosystem": "PyPI"},
        "version": version,
    }
    req = urllib.request.Request(
        OSV_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("vulns", [])
    except Exception as exc:
        logger.warning("OSV CVE check failed for %s==%s: %s", name, version, exc)
        return []


# ── Install ────────────────────────────────────────────────────────────────────


def install_to_temp(package_spec: str, temp_dir: str) -> bool:
    """Install a package to an isolated temp directory using pip --target.

    Does NOT install transitive dependencies (--no-deps) for focused scanning.

    Args:
        package_spec: Package spec, e.g. "requests==2.31.0".
        temp_dir: Directory to install into.

    Returns:
        True on success, False on failure.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            temp_dir,
            "--no-deps",
            "--quiet",
            package_spec,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0


# ── Temp dir context manager ──────────────────────────────────────────────────


@contextmanager
def temp_package_env() -> Generator[str, None, None]:
    """Context manager that creates and auto-destroys a temp directory.

    Yields:
        Path string of the temporary directory.
    """
    tmp = tempfile.mkdtemp(prefix="nightjar_audit_")
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Cache ─────────────────────────────────────────────────────────────────────


def get_cache_path(name: str, version: str) -> Path:
    """Return the cache directory for a specific package version.

    Note: The cache path ``.card/cache/pypi`` is CWD-relative by design.
    This matches how ``nightjar.toml`` and ``.card/`` are always resolved
    relative to the project root (the current working directory) when
    nightjar commands are run.

    Args:
        name: Package name.
        version: Package version string.

    Returns:
        Path to the cache directory (created if needed).
    """
    cache_root = Path(".card") / "cache" / "pypi" / name / version
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root


def save_cached_result(result: PackageAuditResult) -> None:
    """Persist an audit result to the local cache.

    Saves name, version, files_scanned, total_functions, functions_with_invariants,
    cves, scores, metadata, findings, and timestamp. ScanCandidates are excluded
    from cache (they are re-generated on load from raw scan).

    Args:
        result: The audit result to cache.
    """
    cache_dir = get_cache_path(result.name, result.version)
    payload = {
        "name": result.name,
        "version": result.version,
        "files_scanned": result.files_scanned,
        "total_functions": result.total_functions,
        "functions_with_invariants": result.functions_with_invariants,
        "cves": result.cves,
        "scores": {
            "contract_coverage": result.scores.contract_coverage,
            "type_depth": result.scores.type_depth,
            "guard_density": result.scores.guard_density,
            "docstring_completeness": result.scores.docstring_completeness,
            "cve_cleanliness": result.scores.cve_cleanliness,
            "overall": result.scores.overall,
            "letter_grade": result.scores.letter_grade,
        },
        "metadata": result.metadata,
        "findings": result.findings,
        "timestamp": time.time(),
    }
    (cache_dir / "score.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def load_cached_result(name: str, version: str) -> Optional[PackageAuditResult]:
    """Load a cached audit result if it exists.

    For pinned versions the cache is valid indefinitely.
    For latest-only queries it would be time-bounded (caller decides).

    Note: The cache path ``.card/cache/pypi`` is CWD-relative by design.
    This matches how ``nightjar.toml`` and ``.card/`` are always resolved
    relative to the project root (the current working directory) when
    nightjar commands are run.

    Args:
        name: Package name.
        version: Package version string.

    Returns:
        PackageAuditResult if cache hit, None otherwise.
    """
    cache_dir = Path(".card") / "cache" / "pypi" / name / version
    score_file = cache_dir / "score.json"
    if not score_file.exists():
        return None
    try:
        data = json.loads(score_file.read_text(encoding="utf-8"))
        scores_data = data.get("scores", {})
        scores = AuditScores(
            contract_coverage=scores_data.get("contract_coverage", 0.0),
            type_depth=scores_data.get("type_depth", 0.0),
            guard_density=scores_data.get("guard_density", 0.0),
            docstring_completeness=scores_data.get("docstring_completeness", 0.0),
            cve_cleanliness=scores_data.get("cve_cleanliness", 100.0),
            overall=scores_data.get("overall", 0.0),
            letter_grade=scores_data.get("letter_grade", "F"),
        )
        return PackageAuditResult(
            name=data.get("name", name),
            version=data.get("version", version),
            files_scanned=data.get("files_scanned", 0),
            total_functions=data.get("total_functions", 0),
            functions_with_invariants=data.get("functions_with_invariants", 0),
            candidates=[],  # Not cached
            cves=data.get("cves", []),
            scores=scores,
            metadata=data.get("metadata", {}),
            findings=data.get("findings", []),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


# ── Findings builder ──────────────────────────────────────────────────────────


def _build_findings(
    scan_results: dict[str, list[ScanCandidate]],
    func_stats: tuple[int, int, int, int],
    cves: list[dict],
    scores: AuditScores,
    total_candidates: int,
) -> list[str]:
    """Generate human-readable finding strings for the report card.

    Args:
        scan_results: Scanner results keyed by file path.
        func_stats: (total_funcs, annotated_params, total_params, with_docstrings)
        cves: CVE list from OSV.
        scores: Computed AuditScores.
        total_candidates: Total invariant candidates extracted.

    Returns:
        List of finding strings (positive and negative).
    """
    total_funcs, annotated_params, total_params, with_docstrings = func_stats
    findings: list[str] = []

    # CVE findings
    if not cves:
        findings.append("No known CVEs found (clean)")
    else:
        for cve in cves:
            cve_id = cve.get("id", "UNKNOWN")
            aliases = cve.get("aliases", [])
            alias_str = f" ({', '.join(aliases)})" if aliases else ""
            details = cve.get("details", "")[:80]
            findings.append(f"CVE: {cve_id}{alias_str} — {details}")

    # Annotation findings
    if total_params > 0:
        unannotated = total_params - annotated_params
        if unannotated > 0:
            findings.append(f"{unannotated} parameters missing type annotations")
        else:
            findings.append("All parameters have type annotations")

    # Docstring findings
    if total_funcs > 0:
        missing_docs = total_funcs - with_docstrings
        if missing_docs > 0:
            findings.append(f"{missing_docs} functions missing docstrings")
        else:
            findings.append("All functions have docstrings")

    # Invariant candidate count
    if total_candidates > 0:
        findings.append(f"{total_candidates} invariant candidates extracted")
    else:
        findings.append("No invariant candidates found")

    # Files with guard clauses
    guard_files = [
        Path(path).name
        for path, cands in scan_results.items()
        if any(c.source == "guard_clause" for c in cands)
    ]
    if guard_files:
        sample = guard_files[:3]
        findings.append(f"Guard clauses found in: {', '.join(sample)}")

    return findings


# ── Report rendering ──────────────────────────────────────────────────────────


def render_report_card(result: PackageAuditResult) -> str:
    """Render a Rich terminal report card as a plain string.

    Produces a screenshot-worthy terminal output with progress bars and
    letter grades for each scoring dimension.

    Args:
        result: The PackageAuditResult to render.

    Returns:
        The rendered report card as a string (with Rich markup stripped for plain text,
        or with markup if the caller wants Rich formatting).
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    buf = StringIO()
    console = Console(file=buf, force_terminal=False, highlight=False, width=72)

    def bar(score: float, width: int = 16) -> str:
        filled = int((score / 100) * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    # Title
    title_text = f"NIGHTJAR AUDIT — {result.name} {result.version}"
    console.print(f"\n{'═' * 68}")
    console.print(f"  {title_text}")
    console.print(f"{'═' * 68}")

    # Score rows
    s = result.scores
    rows = [
        ("Contract Coverage     ", s.contract_coverage, score_to_letter_grade(s.contract_coverage)),
        ("Type Annotation Depth ", s.type_depth, score_to_letter_grade(s.type_depth)),
        ("Guard Clause Density  ", s.guard_density, score_to_letter_grade(s.guard_density)),
        ("Docstring Completeness", s.docstring_completeness, score_to_letter_grade(s.docstring_completeness)),
        ("CVE Cleanliness       ", s.cve_cleanliness, score_to_letter_grade(s.cve_cleanliness)),
    ]
    for label, score, grade in rows:
        b = bar(score)
        console.print(f"  {label}  {b}  {score:5.1f}%   {grade}")

    console.print(f"{'─' * 68}")
    overall_bar = bar(s.overall)
    console.print(
        f"  OVERALL SCORE         "
        f"  {overall_bar}  {s.overall:5.1f}/100   {s.letter_grade}"
    )
    console.print(f"{'═' * 68}")

    # Stats row
    cve_count = len(result.cves)
    metadata_parts = []
    if result.metadata.get("license"):
        metadata_parts.append(f"License: {result.metadata['license']}")
    if result.metadata.get("author"):
        metadata_parts.append(f"Author: {result.metadata['author']}")
    meta_str = "   ".join(metadata_parts) if metadata_parts else ""

    console.print(
        f"  Files scanned: {result.files_scanned}"
        f"   Invariants: {len(result.candidates)}"
        f"   Functions: {result.total_functions}"
        f"   CVEs: {cve_count}"
    )
    if meta_str:
        console.print(f"  {meta_str}")
    console.print(f"{'═' * 68}\n")

    # Findings
    if result.findings:
        console.print("  Findings:")
        for finding in result.findings:
            if "CVE:" in finding or "missing" in finding.lower():
                console.print(f"  ✗  {finding}")
            else:
                console.print(f"  ✓  {finding}")
        console.print()

    return buf.getvalue()


def render_json(result: PackageAuditResult) -> str:
    """Render the audit result as a JSON string.

    ScanCandidate objects are serialized as dicts.

    Args:
        result: The PackageAuditResult to serialize.

    Returns:
        JSON string with full audit data.
    """
    candidates_json = [
        {
            "statement": c.statement,
            "tier": c.tier,
            "source": c.source,
            "source_line": c.source_line,
            "confidence": c.confidence,
            "function_name": c.function_name,
        }
        for c in result.candidates
    ]
    payload = {
        "name": result.name,
        "version": result.version,
        "files_scanned": result.files_scanned,
        "total_functions": result.total_functions,
        "functions_with_invariants": result.functions_with_invariants,
        "candidates": candidates_json,
        "cves": result.cves,
        "scores": {
            "contract_coverage": result.scores.contract_coverage,
            "type_depth": result.scores.type_depth,
            "guard_density": result.scores.guard_density,
            "docstring_completeness": result.scores.docstring_completeness,
            "cve_cleanliness": result.scores.cve_cleanliness,
            "overall": result.scores.overall,
            "letter_grade": result.scores.letter_grade,
        },
        "metadata": result.metadata,
        "findings": result.findings,
    }
    return json.dumps(payload, indent=2)


# ── Main pipeline ─────────────────────────────────────────────────────────────


def audit_package(
    package_spec: str,
    *,
    with_deps: bool = False,
    check_cves: bool = True,
    use_cache: bool = True,
) -> PackageAuditResult:
    """Full audit pipeline: resolve → download → scan → score → return result.

    Handles PyPI packages and local directories. For local paths, skips
    download and CVE check (no version info available).

    Args:
        package_spec: Package name, name==version, or local directory path.
        with_deps: If True, also install declared dependencies.
        check_cves: If False, skip OSV CVE lookup (offline mode).
        use_cache: If True, use cached results when available.

    Returns:
        PackageAuditResult with scores, candidates, and findings.
    """
    name, version, is_local = parse_package_spec(package_spec)

    # ── Local directory mode ──────────────────────────────────────────────────
    if is_local:
        local_path = Path(package_spec)
        py_files = collect_py_files(local_path, name)
        scan_results = scan_package_files(py_files)
        func_stats = count_functions_and_annotations(py_files)
        all_candidates = [c for cands in scan_results.values() for c in cands]
        funcs_with_inv = len({c.function_name for c in all_candidates if c.function_name})

        cves: list[dict] = []  # No version to check
        scores = compute_scores(scan_results, func_stats, cves)
        findings = _build_findings(scan_results, func_stats, cves, scores, len(all_candidates))

        return PackageAuditResult(
            name=name,
            version="local",
            files_scanned=len(py_files),
            total_functions=func_stats[0],
            functions_with_invariants=funcs_with_inv,
            candidates=all_candidates,
            cves=cves,
            scores=scores,
            metadata={},
            findings=findings,
        )

    # ── PyPI mode ─────────────────────────────────────────────────────────────

    # 1. Fetch metadata to resolve version
    metadata: dict = {}
    try:
        pypi_data = fetch_pypi_metadata(name, version)
        info = pypi_data.get("info", {})
        resolved_version = info.get("version", version or "unknown")
        metadata = {
            "summary": info.get("summary", ""),
            "author": info.get("author", ""),
            "license": info.get("license", ""),
            "home_page": info.get("home_page", ""),
            "requires_dist": info.get("requires_dist") or [],
        }
    except Exception as exc:
        logger.warning("PyPI metadata fetch failed for %s: %s", name, exc)
        resolved_version = version or "unknown"

    version = resolved_version

    # 2. Check cache
    if use_cache:
        cached = load_cached_result(name, version)
        if cached is not None:
            return cached

    # 3. CVE check
    cves = []
    if check_cves and version != "unknown":
        cves = check_cves_osv(name, version)

    # 4. Install and scan
    install_spec = f"{name}=={version}" if version and version != "unknown" else name

    # Handle with_deps flag
    no_deps_flag = [] if with_deps else ["--no-deps"]

    with temp_package_env() as tmp:
        result_subprocess = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--target", tmp, "--quiet"]
            + no_deps_flag
            + [install_spec],
            capture_output=True,
            text=True,
            timeout=120,
        )
        install_ok = result_subprocess.returncode == 0

        if not install_ok:
            # Return a failed result
            scores = AuditScores(
                contract_coverage=0,
                type_depth=0,
                guard_density=0,
                docstring_completeness=0,
                cve_cleanliness=100,
                overall=0,
                letter_grade="F",
            )
            return PackageAuditResult(
                name=name,
                version=version,
                files_scanned=0,
                total_functions=0,
                functions_with_invariants=0,
                candidates=[],
                cves=cves,
                scores=scores,
                metadata=metadata,
                findings=[f"Install failed: {result_subprocess.stderr[:200]}"],
            )

        py_files = collect_py_files(Path(tmp), name)
        scan_results = scan_package_files(py_files)
        func_stats = count_functions_and_annotations(py_files)
        all_candidates = [c for cands in scan_results.values() for c in cands]
        funcs_with_inv = len({c.function_name for c in all_candidates if c.function_name})

    scores = compute_scores(scan_results, func_stats, cves)
    findings = _build_findings(scan_results, func_stats, cves, scores, len(all_candidates))

    result = PackageAuditResult(
        name=name,
        version=version,
        files_scanned=len(py_files),
        total_functions=func_stats[0],
        functions_with_invariants=funcs_with_inv,
        candidates=all_candidates,
        cves=cves,
        scores=scores,
        metadata=metadata,
        findings=findings,
    )

    # 5. Cache result
    if use_cache and version != "unknown":
        try:
            save_cached_result(result)
        except Exception:
            pass  # Cache failure is non-fatal

    return result
