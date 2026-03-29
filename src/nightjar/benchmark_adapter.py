"""Benchmark adapter for vericoding (POPL 2026) and DafnyBench task files.

Loads formal verification benchmark tasks and converts them to Nightjar's
internal CardSpec format, enabling credible performance claims against
academic benchmarks.

References:
- Vericoding paper: https://arxiv.org/abs/2509.22908
  "A benchmark for vericoding: formally verified program synthesis"
  Accepted at Dafny 2026 workshop co-located with POPL 2026.
- DafnyBench paper: https://arxiv.org/abs/2406.08467
  782 Dafny programs, hints-removed evaluation format.
- [REF-T01] Dafny 4.x verification engine
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nightjar.types import (
    CardSpec,
    Contract,
    Invariant,
    InvariantTier,
    ModuleBoundary,
)

logger = logging.getLogger(__name__)

# Placeholder tokens used by the vericoding benchmark format
_VC_CODE = "<vc-code>"
_VC_HELPERS = "<vc-helpers>"

# Cheating patterns: generated Dafny must not contain these
# Per vericoding benchmark evaluation protocol (arxiv:2509.22908 §3)
# Note: comment stripping in detect_cheating() handles false positives from
# "// assume ..." style comments before these patterns are applied.
_CHEATING_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("assume", re.compile(r"\bassume\b", re.MULTILINE)),
    ("axiom", re.compile(r"\{:axiom\}", re.IGNORECASE)),
    ("verify false", re.compile(r"\{:verify\s+false\}", re.IGNORECASE)),
]

# Regex to extract requires/ensures clauses from Dafny spec text
_REQUIRES_RE = re.compile(r"^\s*requires\s+(.+)", re.MULTILINE)
_ENSURES_RE = re.compile(r"^\s*ensures\s+(.+)", re.MULTILINE)


@dataclass
class BenchmarkTask:
    """A single benchmark task (formal spec → generate implementation).

    Represents one task from either the vericoding or DafnyBench benchmark.
    The LLM must fill in the code_placeholder (and optionally helpers_placeholder)
    so that ``dafny verify`` succeeds on the full_template.
    """

    task_id: str
    source: str                # "vericoding" or "dafnybench"
    dataset: str               # "HumanEval-Dafny", "DafnyBench", "APPS", etc.
    preamble: str              # Dafny code before the spec (imports, datatypes)
    spec: str                  # The formal specification (pre/postconditions)
    code_placeholder: str      # Token marking where generated code goes
    helpers_placeholder: str   # Token marking where helper lemmas go
    full_template: str         # Complete .dfy file with placeholder tokens
    difficulty: str            # "easy", "medium", "hard" if available, else ""
    metadata: dict = field(default_factory=dict)  # Extra fields from source


# ── Vericoding JSONL loader ────────────────────────────────────────────────────


def load_vericoding_tasks(jsonl_path: Path) -> list[BenchmarkTask]:
    """Parse a vericoding dafny_tasks.jsonl file into BenchmarkTask objects.

    Each line is a JSON object with fields including: task_id, dataset,
    preamble, spec, full_template, and optionally difficulty and metadata.
    The spec and full_template contain ``<vc-code>`` and possibly
    ``<vc-helpers>`` placeholder tokens.

    Malformed JSON lines and tasks missing the required ``spec`` field are
    silently skipped with a logged warning so a single bad line never aborts
    a large benchmark run.

    Args:
        jsonl_path: Path to the .jsonl file (one JSON object per line).

    Returns:
        List of BenchmarkTask objects, one per valid line.
    """
    tasks: list[BenchmarkTask] = []
    text = jsonl_path.read_text(encoding="utf-8")
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("vericoding JSONL line %d: JSON parse error — %s", lineno, exc)
            continue

        # Required field: spec
        spec = obj.get("spec") or obj.get("body") or ""
        if not spec:
            logger.warning(
                "vericoding JSONL line %d: skipped — missing 'spec' field (task_id=%r)",
                lineno,
                obj.get("task_id", "<unknown>"),
            )
            continue

        task_id = str(obj.get("task_id", f"task_{lineno}"))
        dataset = str(obj.get("dataset", "vericoding"))
        preamble = str(obj.get("preamble", ""))
        full_template = str(obj.get("full_template", spec))
        difficulty = str(obj.get("difficulty", ""))

        # Detect which placeholders are present in the template/spec
        code_placeholder = _VC_CODE if _VC_CODE in (full_template + spec) else ""
        helpers_placeholder = _VC_HELPERS if _VC_HELPERS in (full_template + spec) else ""

        # Collect any extra fields as metadata.
        # If the JSON object has a "metadata" sub-dict, hoist its contents
        # to the top level so callers can do metadata.get("source") directly.
        known_keys = {
            "task_id", "dataset", "preamble", "spec", "full_template",
            "difficulty", "helpers_template", "body", "metadata",
        }
        metadata: dict[str, Any] = {}
        if isinstance(obj.get("metadata"), dict):
            metadata.update(obj["metadata"])
        metadata.update({k: v for k, v in obj.items() if k not in known_keys})

        tasks.append(
            BenchmarkTask(
                task_id=task_id,
                source="vericoding",
                dataset=dataset,
                preamble=preamble,
                spec=spec,
                code_placeholder=code_placeholder,
                helpers_placeholder=helpers_placeholder,
                full_template=full_template,
                difficulty=difficulty,
                metadata=metadata,
            )
        )

    return tasks


# ── DafnyBench directory loader ────────────────────────────────────────────────


def load_dafnybench_tasks(directory: Path) -> list[BenchmarkTask]:
    """Load DafnyBench tasks from a benchmark root directory.

    DafnyBench has two subdirectories inside the benchmark root:
    - ``hints_included/`` — programs with loop invariants/assertions intact
    - ``hints_removed/`` — programs with hints stripped (the challenge)

    This loader reads from ``hints_removed/`` (the evaluation challenge).
    Each .dfy file becomes one BenchmarkTask.

    Args:
        directory: Path to the DafnyBench benchmark root (containing
            ``hints_removed/`` as a subdirectory).

    Returns:
        List of BenchmarkTask objects, one per .dfy file.

    Raises:
        ValueError: If the ``hints_removed/`` subdirectory does not exist.
    """
    hints_removed = directory / "hints_removed"
    if not hints_removed.exists() or not hints_removed.is_dir():
        raise ValueError(
            f"DafnyBench hints_removed/ directory not found at {hints_removed}. "
            "Expected directory structure: <root>/hints_removed/*.dfy"
        )

    tasks: list[BenchmarkTask] = []
    for dfy_file in sorted(hints_removed.glob("*.dfy")):
        content = dfy_file.read_text(encoding="utf-8")
        task_id = dfy_file.stem  # filename without .dfy extension

        tasks.append(
            BenchmarkTask(
                task_id=task_id,
                source="dafnybench",
                dataset="DafnyBench",
                preamble="",          # DafnyBench files are self-contained
                spec=content,         # Full file content is the challenge
                code_placeholder="",  # DafnyBench fills hints, not code body
                helpers_placeholder="",
                full_template=content,
                difficulty="",        # DafnyBench doesn't label difficulty
                metadata={"file": str(dfy_file)},
            )
        )

    return tasks


# ── CardSpec conversion ────────────────────────────────────────────────────────


def task_to_card_spec(task: BenchmarkTask) -> CardSpec:
    """Convert a BenchmarkTask to Nightjar's CardSpec format.

    Extracts ``requires`` and ``ensures`` clauses from the Dafny spec text
    and maps them to Invariant objects with tier=FORMAL. This allows the
    Nightjar pipeline to treat each benchmark task as a standard card.

    Args:
        task: The benchmark task to convert.

    Returns:
        A CardSpec with invariants derived from the Dafny preconditions and
        postconditions found in the task's spec text.
    """
    invariants: list[Invariant] = []

    # Extract requires clauses → precondition invariants
    for match in _REQUIRES_RE.finditer(task.spec):
        clause = match.group(1).strip().rstrip("{")
        if clause:
            inv_id = f"{task.task_id}_requires_{len(invariants)}"
            invariants.append(
                Invariant(
                    id=inv_id,
                    tier=InvariantTier.FORMAL,
                    statement=f"requires {clause}",
                    rationale=f"Dafny precondition from {task.source} task {task.task_id}",
                )
            )

    # Extract ensures clauses → postcondition invariants
    for match in _ENSURES_RE.finditer(task.spec):
        clause = match.group(1).strip().rstrip("{")
        if clause:
            inv_id = f"{task.task_id}_ensures_{len(invariants)}"
            invariants.append(
                Invariant(
                    id=inv_id,
                    tier=InvariantTier.FORMAL,
                    statement=f"ensures {clause}",
                    rationale=f"Dafny postcondition from {task.source} task {task.task_id}",
                )
            )

    # Derive a human-readable title from the task_id
    title = task.task_id.replace("_", " ").replace("-", " ")

    return CardSpec(
        card_version="1.0",
        id=task.task_id,
        title=title,
        status="benchmark",
        module=ModuleBoundary(owns=[task.task_id]),
        contract=Contract(),
        invariants=invariants,
        constraints={
            "source": task.source,
            "dataset": task.dataset,
            "difficulty": task.difficulty,
        },
        intent=(
            f"Benchmark task from {task.source} dataset {task.dataset}. "
            f"Generate a Dafny implementation that satisfies the formal specification."
        ),
        acceptance_criteria=(
            f"`dafny verify` passes without assume, {{:axiom}}, or {{:verify false}}."
        ),
    )


# ── Cheating detection ─────────────────────────────────────────────────────────


def detect_cheating(dafny_output: str) -> list[str]:
    """Check generated Dafny code for patterns that bypass verification.

    The vericoding benchmark (arxiv:2509.22908 §3) explicitly prohibits:
    - ``assume`` statements (shortcut past proof obligations)
    - ``{:axiom}`` attribute (marks lemmas as assumed true)
    - ``{:verify false}`` attribute (disables verification for a method)

    Comments are excluded from the search so that explanatory comments
    mentioning these keywords do not trigger false positives.

    Args:
        dafny_output: The generated Dafny code string to inspect.

    Returns:
        A list of human-readable violation descriptions. Empty list means
        the code is clean.
    """
    # Strip single-line comments before searching to avoid false positives
    # on comment text like "// we could assume x > 0 here"
    stripped = re.sub(r"//[^\n]*", "", dafny_output)

    violations: list[str] = []
    for label, pattern in _CHEATING_PATTERNS:
        matches = pattern.findall(stripped)
        if matches:
            violations.append(
                f"Cheating pattern '{label}' found ({len(matches)} occurrence(s))"
            )

    return violations


# ── Template filling ───────────────────────────────────────────────────────────


def fill_template(
    task: BenchmarkTask,
    generated_code: str,
    generated_helpers: str = "",
) -> str:
    """Replace placeholder tokens in the task template with generated code.

    The vericoding benchmark uses ``<vc-code>`` and ``<vc-helpers>`` as
    placeholder tokens in the full_template. This function substitutes them
    with the LLM-generated implementation and helper lemmas respectively.

    If no ``<vc-helpers>`` placeholder is present, the generated_helpers
    argument is ignored. If ``<vc-helpers>`` is present but generated_helpers
    is empty, the placeholder is removed (replaced with empty string).

    Args:
        task: The benchmark task whose full_template to fill.
        generated_code: The generated implementation code to insert at
            ``<vc-code>``.
        generated_helpers: Optional helper lemmas to insert at
            ``<vc-helpers>``. Defaults to empty string.

    Returns:
        The completed .dfy file contents with placeholders replaced.
    """
    result = task.full_template
    result = result.replace(_VC_CODE, generated_code)
    result = result.replace(_VC_HELPERS, generated_helpers)
    return result


# ── Auto-detecting suite loader ────────────────────────────────────────────────


def load_benchmark_suite(
    path: Path,
    source: str = "auto",
) -> list[BenchmarkTask]:
    """Load a benchmark suite from a file or directory, auto-detecting format.

    Supported formats and auto-detection rules:
    - ``source="vericoding"`` or path ends with ``.jsonl`` → vericoding JSONL
    - ``source="dafnybench"`` or path is a directory → DafnyBench
    - ``source="auto"`` applies the above rules automatically

    Args:
        path: Path to the benchmark file (.jsonl) or directory (DafnyBench root).
        source: One of ``"auto"``, ``"vericoding"``, or ``"dafnybench"``.

    Returns:
        List of BenchmarkTask objects.

    Raises:
        ValueError: If source is unknown or auto-detection fails to match.
    """
    _VALID_SOURCES = {"auto", "vericoding", "dafnybench"}
    if source not in _VALID_SOURCES:
        raise ValueError(
            f"Unknown benchmark source {source!r}. "
            f"Must be one of: {sorted(_VALID_SOURCES)}"
        )

    resolved = source
    if resolved == "auto":
        if path.is_file() and path.suffix == ".jsonl":
            resolved = "vericoding"
        elif path.is_dir():
            resolved = "dafnybench"
        else:
            raise ValueError(
                f"Cannot auto-detect benchmark format for {path}. "
                "Use source='vericoding' or source='dafnybench' explicitly."
            )

    if resolved == "vericoding":
        return load_vericoding_tasks(path)
    else:  # dafnybench
        return load_dafnybench_tasks(path)
