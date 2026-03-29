"""SARIF writer for Nightjar verification results.

Wraps the to_sarif() function from verifier.py and adds file I/O,
structural validation against SARIF 2.1.0, and multi-file merge
for `nightjar verify --all` use-cases.

Usage:
    from nightjar.sarif_writer import write_sarif

    result = run_pipeline(spec, code)
    path = write_sarif(result, "nightjar.sarif", spec_path=".card/payment.card.md")

GitHub Code Scanning upload:
    gh upload-sarif --sarif-file nightjar.sarif

References:
- SARIF 2.1.0 spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
- GitHub Code Scanning: https://docs.github.com/en/code-security/code-scanning
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nightjar.types import VerifyResult

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_SARIF_VERSION = "2.1.0"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_sarif(
    result: "VerifyResult",
    output_path: "str | Path",
    *,
    spec_path: str = "",
    tool_version: str = "0.1.0",
    pretty: bool = True,
) -> Path:
    """Write verification results as a SARIF 2.1.0 JSON file.

    Wraps nightjar.verifier.to_sarif() and persists the output to disk.
    The file is always written with UTF-8 encoding so that unicode characters
    in error messages are preserved.

    Args:
        result: The VerifyResult from run_pipeline() or run_pipeline_with_fallback().
        output_path: Destination path (str or Path). Parent directory must exist.
        spec_path: Optional URI for the .card.md spec file. When given, failing
            results include a physicalLocation pointing at the spec.
        tool_version: Nightjar version string embedded in the SARIF driver block.
        pretty: If True (default), write indented JSON (indent=2).
            If False, write compact single-line JSON.

    Returns:
        The resolved output Path that was written.

    References:
        SARIF 2.1.0: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
    """
    # Import here to avoid circular imports at module load time
    from nightjar.verifier import to_sarif  # noqa: PLC0415

    output_path = Path(output_path)
    sarif_dict = to_sarif(result, spec_path=spec_path, tool_version=tool_version)

    indent = 2 if pretty else None
    separators = None if pretty else (",", ":")

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(sarif_dict, fh, ensure_ascii=False, indent=indent, separators=separators)
        if pretty:
            fh.write("\n")  # trailing newline for POSIX compliance

    return output_path


def validate_sarif(sarif_dict: dict) -> list[str]:
    """Validate a SARIF dict against 2.1.0 required fields.

    Performs structural validation only — no external schema dependency
    (jsonschema is not required). Checks all mandatory fields in the
    SARIF 2.1.0 specification that are relevant to GitHub Code Scanning.

    Args:
        sarif_dict: A dict representing a SARIF document (e.g. from json.load()).

    Returns:
        A list of human-readable error strings.  Empty list means valid.

    Checks:
    - $schema present and contains "sarif"
    - version is "2.1.0"
    - runs array exists with at least one run
    - Each run has tool.driver with name and version
    - Each result has ruleId, message, level
    - Each result location (if present) has physicalLocation.artifactLocation
    """
    errors: list[str] = []

    # --- Top-level fields ---
    if "$schema" not in sarif_dict:
        errors.append("Missing required field: $schema")
    elif "sarif" not in sarif_dict["$schema"].lower():
        errors.append(
            f"$schema does not look like a SARIF schema URI: {sarif_dict['$schema']!r}"
        )

    version = sarif_dict.get("version")
    if version is None:
        errors.append("Missing required field: version")
    elif version != _SARIF_VERSION:
        errors.append(
            f"version must be {_SARIF_VERSION!r}, got {version!r}"
        )

    runs = sarif_dict.get("runs")
    if runs is None:
        errors.append("Missing required field: runs")
        # Can't validate individual runs without the array
        return errors
    if not isinstance(runs, list):
        errors.append("runs must be an array")
        return errors
    if len(runs) == 0:
        errors.append("runs array must contain at least one run")
        return errors

    # --- Per-run validation ---
    for run_idx, run in enumerate(runs):
        prefix = f"runs[{run_idx}]"

        tool = run.get("tool", {})
        driver = tool.get("driver")
        if driver is None:
            errors.append(f"{prefix}.tool.driver is missing")
        else:
            if "name" not in driver:
                errors.append(f"{prefix}.tool.driver.name is missing")
            if "version" not in driver:
                errors.append(f"{prefix}.tool.driver.version is missing")

        results = run.get("results", [])
        for res_idx, res in enumerate(results):
            res_prefix = f"{prefix}.results[{res_idx}]"

            if "ruleId" not in res:
                errors.append(f"{res_prefix}.ruleId is missing")
            if "message" not in res:
                errors.append(f"{res_prefix}.message is missing")
            if "level" not in res:
                errors.append(f"{res_prefix}.level is missing")

            # Validate locations if present
            locations = res.get("locations", [])
            for loc_idx, loc in enumerate(locations):
                loc_prefix = f"{res_prefix}.locations[{loc_idx}]"
                phys = loc.get("physicalLocation")
                if phys is None:
                    errors.append(
                        f"{loc_prefix}: physicalLocation is missing "
                        "(required when locations are provided)"
                    )
                else:
                    if "artifactLocation" not in phys:
                        errors.append(
                            f"{loc_prefix}.physicalLocation: artifactLocation is missing"
                        )

    return errors


def sarif_summary(sarif_dict: dict, *, filename: str = "") -> str:
    """Return a one-line human-readable summary of SARIF results.

    Suitable for direct CLI output after writing a SARIF file.

    Args:
        sarif_dict: A SARIF 2.1.0 dict (e.g. the return value of write_sarif
            when re-parsed, or the dict before writing).
        filename: Optional filename to include in the summary string.

    Returns:
        A string such as:
            "SARIF: 3 errors, 1 warning written to nightjar.sarif"
            "SARIF: 0 findings (pass)"

    Examples:
        >>> sarif_summary(sarif, filename="nightjar.sarif")
        'SARIF: 2 errors, 1 warning written to nightjar.sarif'
    """
    errors = 0
    warnings = 0

    for run in sarif_dict.get("runs", []):
        for result in run.get("results", []):
            level = result.get("level", "")
            if level == "error":
                errors += 1
            elif level == "warning":
                warnings += 1

    if errors == 0 and warnings == 0:
        parts = ["SARIF: 0 findings (pass)"]
    else:
        parts_inner: list[str] = []
        if errors > 0:
            parts_inner.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings > 0:
            parts_inner.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        parts = ["SARIF: " + ", ".join(parts_inner)]

    if filename:
        parts.append(f"written to {filename}")

    return " ".join(parts)


def merge_sarif_files(paths: "list[Path]") -> dict:
    """Merge multiple SARIF files into a single SARIF document.

    Used by `nightjar verify --all` which runs the pipeline over multiple
    .card.md specs and produces one combined SARIF report for upload.

    The first file's $schema and version are used for the merged document.
    All runs from every input file are concatenated into a single runs array.

    Args:
        paths: List of Paths to SARIF JSON files. May be empty (returns a
            valid empty SARIF document).

    Returns:
        A SARIF 2.1.0 dict with all runs combined.

    References:
        SARIF 2.1.0 §3.13: Multiple runs in one log file.
    """
    if not paths:
        return {
            "$schema": _SARIF_SCHEMA,
            "version": _SARIF_VERSION,
            "runs": [],
        }

    all_runs: list[dict] = []

    for path in paths:
        path = Path(path)
        sarif = json.loads(path.read_text(encoding="utf-8"))
        all_runs.extend(sarif.get("runs", []))

    # Always use the module-level canonical schema and version constants,
    # regardless of what individual input files declare.
    return {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": all_runs,
    }
