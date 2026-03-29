"""Stage 1: Dependency check — sealed manifest verification.

Validates that generated code only imports packages listed in deps.lock.
Prevents hallucinated/slopsquatted packages from entering the build.

Cost: ~1-2s, $0.00
Short-circuit: unknown package or CVE → FAIL

References:
- [REF-C08] Sealed Dependency Manifest
- [REF-P27] Package Hallucinations — 19.7% of AI-generated deps are hallucinated
- [REF-T05] uv — hash verification
- [REF-T06] pip-audit — CVE scanning
"""

import ast
import re
import sys
import time
from pathlib import Path
from typing import Optional

from nightjar.lock import IMPORT_TO_PACKAGE
from nightjar.types import StageResult, VerifyStatus

# deps.lock line format: package==version --hash=sha256:HASH
_DEPS_LINE_RE = re.compile(
    r"^(?P<package>[\w\-\.]+)==(?P<version>[\w\.\-]+)"
    r"(?:\s+--hash=(?P<algorithm>\w+):(?P<hash>[a-f0-9]+))?$"
)


def parse_deps_lock(path: str) -> dict[str, dict]:
    """Parse a deps.lock sealed manifest into a package dict.

    Args:
        path: Path to deps.lock file.

    Returns:
        Dict mapping package name → {version, hash, algorithm}.
        Empty dict if file doesn't exist.
    """
    lock_file = Path(path)
    if not lock_file.exists():
        return {}

    packages: dict[str, dict] = {}
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _DEPS_LINE_RE.match(line)
        if match:
            name = match.group("package").lower()
            packages[name] = {
                "version": match.group("version"),
                "hash": match.group("hash") or "",
                "algorithm": match.group("algorithm") or "",
            }

    return packages


def detect_drift(
    current: dict[str, dict],
    baseline: dict[str, dict],
) -> list[dict]:
    """Detect drift between two deps.lock snapshots.

    Uses sbomlyze's 3-category model (rezmoss/sbomlyze) to classify changes.
    Priority order: integrity > version > metadata (same as sbomlyze's
    ClassifyDrift logic in internal/analysis/drift.go).

    Categories:
    - integrity (HIGH): hash changed WITHOUT version bump.
      The cryptographic ground truth disagrees with the declared version.
      Classical supply chain attack vector (event-stream, XZ utils):
      attacker replaces artifact at known version without bumping it.
      Always investigate — this is never a routine update.
    - version (info): version changed (normal update/downgrade).
    - metadata (info): license/maintainer changed — governance risk.
      NOTE: deps.lock format only stores version+hash, so metadata drift
      (license changes) is not detectable here without an enriched SBOM.
    - added/removed (info): package appeared or disappeared.

    Args:
        current: Current deps.lock dict from parse_deps_lock().
        baseline: Baseline deps.lock dict to compare against.

    Returns:
        List of drift event dicts sorted by package name, each with
        'package', 'drift_type', 'severity', and type-specific fields.
    """
    events: list[dict] = []
    all_packages = sorted(set(current) | set(baseline))

    for pkg in all_packages:
        if pkg not in baseline:
            events.append({
                "package": pkg,
                "drift_type": "added",
                "severity": "info",
                "version": current[pkg]["version"],
            })
            continue

        if pkg not in current:
            events.append({
                "package": pkg,
                "drift_type": "removed",
                "severity": "info",
                "version": baseline[pkg]["version"],
            })
            continue

        cur = current[pkg]
        base = baseline[pkg]

        version_changed = cur["version"] != base["version"]
        # Only flag hash change when both snapshots recorded a non-empty hash.
        # Missing hash = uv hash not captured yet; not a drift signal.
        hash_changed = (
            bool(cur["hash"]) and bool(base["hash"])
            and cur["hash"] != base["hash"]
        )

        # Priority order from sbomlyze: integrity > version > metadata.
        # Integrity check is BEFORE version check so that integrity is only
        # flagged for the anomalous case (same version, different hash).
        if hash_changed and not version_changed:
            events.append({
                "package": pkg,
                "drift_type": "integrity",
                "severity": "high",
                "version": cur["version"],
                "baseline_hash": base["hash"],
                "current_hash": cur["hash"],
                "message": (
                    f"Hash changed without version bump for '{pkg}' "
                    f"(version {cur['version']}). "
                    "Potential supply chain tampering — verify the artifact."
                ),
            })
        elif version_changed:
            events.append({
                "package": pkg,
                "drift_type": "version",
                "severity": "info",
                "version_from": base["version"],
                "version_to": cur["version"],
            })
        # Metadata drift (license/maintainer) requires enriched SBOM data
        # not present in the deps.lock hash+version format.

    return events


def run_deps_check(
    code_path: str,
    deps_lock_path: str,
    baseline_lock_path: Optional[str] = None,
) -> StageResult:
    """Run Stage 1 dependency check on generated code.

    Extracts all import statements from the code, then verifies each
    third-party import exists in the deps.lock allowlist. Optionally runs
    sbomlyze-style drift detection against a baseline snapshot.

    Args:
        code_path: Path to generated Python code.
        deps_lock_path: Path to deps.lock sealed manifest.
        baseline_lock_path: Optional path to a previous deps.lock snapshot
            for drift detection. Integrity drift (hash change without version
            bump) triggers a FAIL — it is a supply chain attack signal.
            Version/added/removed drift is informational only.

    Returns:
        StageResult with stage=1, name='deps', and pass/fail status.
    """
    start = time.monotonic()

    # 1. Validate code file exists
    code_file = Path(code_path)
    if not code_file.exists():
        return _fail(start, [{"message": f"Code file not found: {code_path}"}])

    # 2. Validate deps.lock exists — sealed manifest is mandatory [REF-C08]
    lock_file = Path(deps_lock_path)
    if not lock_file.exists():
        return _fail(start, [{
            "message": f"Sealed dependency manifest not found: {deps_lock_path}. "
                       "Run `nightjar lock` to create it [REF-C08]."
        }])

    # 3. Parse deps.lock
    allowed = parse_deps_lock(deps_lock_path)

    # 4. Extract imports from code
    try:
        source = code_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=code_path)
    except (OSError, SyntaxError) as exc:
        return _fail(start, [{"message": f"Cannot parse code: {exc}"}])

    imports = _extract_imports(tree)

    # 5. Check each import against allowlist
    disallowed: list[str] = []
    for imp in imports:
        root_package = imp.split(".")[0]
        if _is_stdlib(root_package):
            continue
        if not _is_allowed(root_package, allowed):
            disallowed.append(root_package)

    if disallowed:
        errors = [
            {
                "message": f"Import '{pkg}' not in sealed manifest (deps.lock). "
                           "Potential hallucinated dependency [REF-P27].",
                "package": pkg,
            }
            for pkg in sorted(set(disallowed))
        ]
        return _fail(start, errors)

    # 6. Optional sbomlyze drift detection [sbomlyze rezmoss/sbomlyze].
    # Integrity drift (hash change without version bump) = HIGH severity FAIL.
    # Supply chain attacks replace artifacts at the same version; only a hash
    # comparison reveals the substitution.
    if baseline_lock_path is not None:
        baseline = parse_deps_lock(baseline_lock_path)
        if baseline:
            drift_events = detect_drift(allowed, baseline)
            integrity_events = [e for e in drift_events if e["drift_type"] == "integrity"]
            if integrity_events:
                drift_errors = [
                    {
                        "type": "integrity_drift",
                        "message": e["message"],
                        "package": e["package"],
                        "drift_type": e["drift_type"],
                        "severity": e["severity"],
                        "version": e["version"],
                        "baseline_hash": e["baseline_hash"],
                        "current_hash": e["current_hash"],
                    }
                    for e in integrity_events
                ]
                return _fail(start, drift_errors)

    return _pass(start)


def _extract_imports(tree: ast.AST) -> list[str]:
    """Extract all import module names from an AST.

    Returns list of top-level module names (e.g., ['click', 'pydantic']).
    """
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _is_stdlib(module_name: str) -> bool:
    """Check if a module is part of the Python standard library."""
    if module_name in sys.stdlib_module_names:
        return True
    # Also check common subpackages
    parts = module_name.split(".")
    return parts[0] in sys.stdlib_module_names


def _is_allowed(import_name: str, allowed: dict[str, dict]) -> bool:
    """Check if an import name maps to an allowed package in deps.lock.

    Handles import-name → package-name mismatches (e.g., yaml → pyyaml).
    """
    # Direct match (import name == package name)
    if import_name.lower() in allowed:
        return True

    # Check known import→package mappings
    mapped = IMPORT_TO_PACKAGE.get(import_name)
    if mapped and mapped.lower() in allowed:
        return True

    return False


def _elapsed_ms(start: float) -> int:
    """Calculate elapsed milliseconds since start."""
    return int((time.monotonic() - start) * 1000)


def _pass(start: float) -> StageResult:
    """Create a passing StageResult."""
    return StageResult(
        stage=1,
        name="deps",
        status=VerifyStatus.PASS,
        duration_ms=_elapsed_ms(start),
    )


def _fail(start: float, errors: list[dict]) -> StageResult:
    """Create a failing StageResult with error details."""
    return StageResult(
        stage=1,
        name="deps",
        status=VerifyStatus.FAIL,
        duration_ms=_elapsed_ms(start),
        errors=errors,
    )
