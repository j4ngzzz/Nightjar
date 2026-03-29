"""Benchmark runner for Nightjar's verification pipeline.

Executes Nightjar against academic benchmark tasks (vericoding, DafnyBench)
and produces scored reports enabling claims like:
  "Nightjar achieves X% on the BAIF vericoding benchmark."

Benchmark references:
- Vericoding paper: arxiv:2509.22908 (POPL 2026 Dafny workshop)
  - Individual model best: Claude Opus 4.1 at 67.5% pass@1
  - Model union (any of 5 attempts): 82.2%
- DafnyBench paper: arxiv:2406.08467 (Harvard/MIT Tegmark group)

Design notes:
- benchmark_adapter (BenchmarkTask, detect_cheating) is built by a separate
  agent; this module imports it at call time with graceful stubs for testing.
- All verification goes through the existing run_pipeline() from verifier.py.
- Workers > 1 uses ThreadPoolExecutor for parallel task execution.
- Cheating detection rejects outputs containing assume/axiom/{:verify false}
  even when Dafny considers them verified.

References:
- [REF-T01] Dafny 4.x formal verification
- [REF-C02] CEGIS closed-loop retry
- [REF-P06] DafnyPro structured error format
"""

from __future__ import annotations

import concurrent.futures
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from nightjar.types import CardSpec, Contract, Invariant, InvariantTier, ModuleBoundary
from nightjar.verifier import run_pipeline


# ── Known baselines from vericoding paper (arxiv:2509.22908 Table 3) ─────────
_BASELINE_CLAUDE_OPUS = 67.5   # Claude Opus 4.1, pass@1
_BASELINE_GPT5_MINI   = 66.9   # GPT-5 Mini, pass@1
_BASELINE_GPT5        = 66.1   # GPT-5, pass@1
_BASELINE_SONNET4     = 64.6   # Claude Sonnet 4, pass@1
_BASELINE_MODEL_UNION = 82.2   # Any of 9 models in ≤5 attempts


# ── Cheating patterns — per vericoding evaluation protocol ────────────────────
# DEGRADED FALLBACK: This list is only used when benchmark_adapter is unavailable.
# It uses simple substring matching and may miss context-sensitive cases (e.g.
# comments containing "assume", or {:axiom} in strings). The canonical, accurate
# implementation is benchmark_adapter.detect_cheating — always prefer that.
_CHEATING_PATTERNS = ["assume ", "assume(", "{:axiom}", "{:verify false}"]


# ── Lazy import helpers ───────────────────────────────────────────────────────

def _import_benchmark_adapter() -> Any:
    """Import benchmark_adapter; raises ImportError with helpful message if absent."""
    try:
        import nightjar.benchmark_adapter as adapter  # noqa: F401
        return adapter
    except ImportError as exc:
        raise ImportError(
            "nightjar.benchmark_adapter is not available — "
            "it is built by a separate agent. "
            "In tests, mock detect_cheating and _generate_code_for_task directly."
        ) from exc


def detect_cheating(code: str) -> list[str]:
    """Detect cheating patterns in generated Dafny code.

    Delegates to benchmark_adapter.detect_cheating when available;
    falls back to a built-in pattern scan so the runner works
    independently of the adapter module.

    Args:
        code: Generated Dafny source code string.

    Returns:
        List of cheating violation strings found (empty if clean).
    """
    try:
        adapter = _import_benchmark_adapter()
        return adapter.detect_cheating(code)  # type: ignore[no-any-return]
    except ImportError:
        pass
    # Built-in fallback — covers the standard vericoding cheating patterns
    violations: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        for pattern in _CHEATING_PATTERNS:
            if pattern in stripped:
                violations.append(stripped)
                break
    return violations


def _generate_code_for_task(task: Any) -> str:
    """Generate Dafny code for a benchmark task.

    Delegates to benchmark_adapter.generate_code_for_task when available;
    otherwise returns a minimal stub that Dafny will verify as trivially
    failing (so the pipeline produces a real failure rather than crashing).

    Args:
        task: A BenchmarkTask object (or compatible duck-type).

    Returns:
        Generated Dafny source code string.
    """
    try:
        adapter = _import_benchmark_adapter()
        return adapter.generate_code_for_task(task)  # type: ignore[no-any-return]
    except ImportError:
        pass
    # Minimal stub — used when adapter is unavailable (e.g. isolated unit tests)
    task_id = getattr(task, "task_id", "unknown")
    spec = getattr(task, "spec", "")
    return (
        f"// Benchmark task: {task_id}\n"
        f"// Spec: {spec}\n"
        "method Placeholder() {}\n"
    )


def _task_to_card_spec(task: Any) -> CardSpec:
    """Convert a BenchmarkTask to a minimal CardSpec for the pipeline.

    The benchmark task carries a formal spec in the spec field. We create a
    CardSpec with one FORMAL invariant so that Stage 4 (Dafny) runs.

    Args:
        task: A BenchmarkTask object.

    Returns:
        CardSpec suitable for run_pipeline().
    """
    task_id = getattr(task, "task_id", "benchmark_task")
    spec_text = getattr(task, "spec", "")

    return CardSpec(
        card_version="1.0",
        id=task_id,
        title=f"Benchmark task {task_id}",
        status="benchmark",
        module=ModuleBoundary(owns=[task_id]),
        contract=Contract(),
        invariants=[
            Invariant(
                id="BENCH-INV-001",
                tier=InvariantTier.FORMAL,
                statement=spec_text or "true",
                rationale="Benchmark task formal specification",
            )
        ],
    )


def _classify_dafny_error_from_output(dafny_output: str) -> str | None:
    """Classify a Dafny error from raw verifier output text.

    Extended classification per Part 3 of research-benchmark-dafny-errors.md,
    covering the top-20 Dafny errors plus additional patterns.

    Args:
        dafny_output: Raw text from Dafny CLI.

    Returns:
        Error category string, or None if output indicates success/no errors.
    """
    if not dafny_output:
        return None
    lower = dafny_output.lower()
    if "postcondition" in lower:
        return "postcondition_failure"
    if "precondition" in lower:
        return "precondition_failure"
    if "loop invariant" in lower or ("invariant" in lower and "loop" in lower):
        return "loop_invariant_failure"
    if "assertion" in lower or "assert" in lower:
        return "assertion_failure"
    if "decreases" in lower or "termination" in lower or "cannot prove termination" in lower:
        return "decreases_failure"
    if "index out of range" in lower:
        return "array_bounds_failure"
    if "null" in lower or "target object" in lower:
        return "null_dereference_failure"
    if "reads" in lower and "insufficient" in lower:
        return "reads_frame_failure"
    if "modifies" in lower:
        return "modifies_frame_failure"
    if "trigger" in lower:
        return "quantifier_trigger_failure"
    if "subset" in lower and "constraint" in lower:
        return "subset_type_failure"
    if "fuel" in lower:
        return "fuel_failure"
    if "timeout" in lower:
        return "timeout"
    if "error" in lower:
        return "other"
    return None


# ── Core dataclasses ──────────────────────────────────────────────────────────

@dataclass
class AttemptResult:
    """Result from a single attempt to solve a benchmark task."""
    attempt_num: int
    success: bool
    cheating_violations: list[str]
    dafny_output: str
    duration_seconds: float
    error_category: str | None  # from _classify_dafny_error_from_output


@dataclass
class TaskResult:
    """Result from running all attempts on a single benchmark task."""
    task_id: str
    attempts: list[AttemptResult]
    passed: bool          # True if any attempt succeeded without cheating
    best_attempt: int     # 0-indexed attempt number of first success (-1 if none)
    # Note: best_attempt is 0-indexed (0 = first attempt), while
    # AttemptResult.attempt_num is 1-indexed (1 = first attempt).


@dataclass
class BenchmarkReport:
    """Aggregated result for an entire benchmark run."""
    source: str                      # "vericoding" or "dafnybench"
    dataset: str                     # e.g. "HumanEval-Dafny"
    total_tasks: int
    passed_tasks: int
    pass_at_1: float                 # % of tasks passing on first attempt
    pass_at_k: float                 # % of tasks passing in any of k attempts
    k: int                           # number of attempts per task
    cheating_rejected: int           # tasks that passed Dafny but used assume/axiom
    avg_duration: float              # average seconds per task
    error_distribution: dict[str, int]   # error_category → count
    results: list[TaskResult] = field(default_factory=list)


# ── Metrics ───────────────────────────────────────────────────────────────────

def score_pass_at_k(results: list[TaskResult], k: int) -> float:
    """Calculate pass@k metric over a list of task results.

    pass@1 = fraction of tasks that succeeded on their first attempt.
    pass@k = fraction of tasks that succeeded within their first k attempts.

    A task "succeeds within k attempts" when TaskResult.passed is True AND
    TaskResult.best_attempt < k (0-indexed: best_attempt=0 means attempt 1).

    Args:
        results: List of TaskResult objects.
        k: Number of allowed attempts (1 = first-attempt only, 5 = any of 5).

    Returns:
        Float in [0.0, 1.0]; 0.0 if results is empty.
    """
    if not results:
        return 0.0
    successes = sum(
        1
        for r in results
        if r.passed and r.best_attempt >= 0 and r.best_attempt < k
    )
    return successes / len(results)


# ── Task execution ────────────────────────────────────────────────────────────

def run_single_task(
    task: Any,
    *,
    max_attempts: int = 5,
    timeout: float = 120,
) -> TaskResult:
    """Run one benchmark task through the Nightjar pipeline with retries.

    For each attempt (up to max_attempts):
    1. Generate Dafny code for the task.
    2. Check for cheating patterns — reject if found.
    3. Run run_pipeline() with a CardSpec derived from the task.
    4. If verified and no cheating → mark passed, stop retrying.
    5. Otherwise record the failure and try again.

    Exceptions from run_pipeline (including TimeoutError) are caught per
    attempt and recorded as failures; other attempts still proceed.

    Args:
        task: A BenchmarkTask-compatible object with task_id and spec.
        max_attempts: Maximum number of generation+verify cycles.
        timeout: Per-attempt timeout in seconds. Currently NOT enforced —
                 the value is accepted for API compatibility but has no effect.
                 TODO: enforce via concurrent.futures.wait(timeout=...) by
                 submitting run_pipeline to a ThreadPoolExecutor per attempt.

    Returns:
        TaskResult with all attempts recorded and passed/best_attempt set.
    """
    spec = _task_to_card_spec(task)
    attempts: list[AttemptResult] = []
    passed = False
    best_attempt = -1

    for attempt_num in range(max_attempts):
        start = time.monotonic()
        dafny_output = ""
        error_category: str | None = None
        cheating_violations: list[str] = []
        success = False

        try:
            code = _generate_code_for_task(task)
            cheating_violations = detect_cheating(code)

            if cheating_violations:
                # Cheating detected — skip pipeline, record as failure
                dafny_output = f"CHEATING REJECTED: {cheating_violations}"
                error_category = "cheating_rejected"
            else:
                verify_result = run_pipeline(spec, code)
                dafny_output = _extract_dafny_output(verify_result)
                if verify_result.verified:
                    success = True
                else:
                    error_category = _classify_dafny_error_from_output(dafny_output)

        except concurrent.futures.TimeoutError:
            dafny_output = "TIMEOUT"
            error_category = "timeout"
        except Exception as exc:  # noqa: BLE001 — catch all per-attempt errors
            dafny_output = f"ERROR: {exc}"
            error_category = "runner_error"

        duration = time.monotonic() - start
        attempt = AttemptResult(
            attempt_num=attempt_num + 1,
            success=success,
            cheating_violations=cheating_violations,
            dafny_output=dafny_output,
            duration_seconds=duration,
            error_category=error_category,
        )
        attempts.append(attempt)

        if success:
            passed = True
            best_attempt = attempt_num
            break  # Stop retrying once we have a success

    return TaskResult(
        task_id=getattr(task, "task_id", "unknown"),
        attempts=attempts,
        passed=passed,
        best_attempt=best_attempt,
    )


def _extract_dafny_output(verify_result: Any) -> str:
    """Extract Dafny error text from a VerifyResult for error classification.

    Looks through stage results for Stage 4 (formal) errors.

    Args:
        verify_result: VerifyResult from run_pipeline().

    Returns:
        Concatenated error messages from formal stage, or empty string.
    """
    lines: list[str] = []
    for stage in getattr(verify_result, "stages", []):
        if getattr(stage, "stage", None) == 4:
            for err in getattr(stage, "errors", []):
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                if msg:
                    lines.append(msg)
    return "\n".join(lines)


# ── Benchmark runner ──────────────────────────────────────────────────────────

def run_benchmark(
    tasks: list[Any],
    *,
    max_attempts: int = 5,
    timeout_per_task: float = 120,
    workers: int = 1,
) -> BenchmarkReport:
    """Run all benchmark tasks through the Nightjar pipeline and produce a report.

    Tasks are executed sequentially (workers=1) or in parallel threads
    (workers > 1). Results are aggregated into a BenchmarkReport with
    pass@1, pass@k, error distribution, and cheating statistics.

    Args:
        tasks: List of BenchmarkTask-compatible objects.
        max_attempts: Maximum verification attempts per task.
        timeout_per_task: Per-task timeout in seconds.
        workers: Number of parallel worker threads (1 = sequential).

    Returns:
        BenchmarkReport with full results.
    """
    if not tasks:
        # Return an empty report for zero tasks
        return BenchmarkReport(
            source="unknown",
            dataset="unknown",
            total_tasks=0,
            passed_tasks=0,
            pass_at_1=0.0,
            pass_at_k=0.0,
            k=max_attempts,
            cheating_rejected=0,
            avg_duration=0.0,
            error_distribution={},
            results=[],
        )

    # Derive source/dataset from the first task's attributes
    first = tasks[0]
    source = getattr(first, "source", "unknown")
    dataset = getattr(first, "dataset", "unknown")

    def _run(task: Any) -> TaskResult:
        return run_single_task(task, max_attempts=max_attempts, timeout=timeout_per_task)

    results: list[TaskResult]
    if workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_run, tasks))
    else:
        results = [_run(t) for t in tasks]

    # Aggregate statistics
    passed_tasks = sum(1 for r in results if r.passed)
    pass_at_1 = score_pass_at_k(results, k=1)
    pass_at_k_val = score_pass_at_k(results, k=max_attempts)

    # Cheating count — tasks where any attempt had cheating violations
    cheating_rejected = sum(
        1 for r in results
        if any(a.cheating_violations for a in r.attempts)
    )

    # Average duration per task (sum of all attempt durations / task count)
    total_duration = sum(
        sum(a.duration_seconds for a in r.attempts)
        for r in results
    )
    avg_duration = total_duration / len(results) if results else 0.0

    # Error distribution — count across all failed attempts
    error_distribution: dict[str, int] = {}
    for r in results:
        for a in r.attempts:
            if a.error_category and not a.success:
                error_distribution[a.error_category] = (
                    error_distribution.get(a.error_category, 0) + 1
                )

    return BenchmarkReport(
        source=source,
        dataset=dataset,
        total_tasks=len(tasks),
        passed_tasks=passed_tasks,
        pass_at_1=pass_at_1,
        pass_at_k=pass_at_k_val,
        k=max_attempts,
        cheating_rejected=cheating_rejected,
        avg_duration=avg_duration,
        error_distribution=error_distribution,
        results=results,
    )


# ── Report formatting ─────────────────────────────────────────────────────────

def format_benchmark_report(report: BenchmarkReport) -> str:
    """Pretty-print a BenchmarkReport with Rich-style tables.

    Falls back to plain-text ASCII tables when Rich is not installed.

    Args:
        report: BenchmarkReport to format.

    Returns:
        Human-readable string report.
    """
    pass_at_1_pct = report.pass_at_1 * 100
    pass_at_k_pct = report.pass_at_k * 100

    lines: list[str] = [
        "",
        f"  Nightjar Benchmark Results — {report.source} / {report.dataset}",
        "  " + "─" * 56,
        f"  Total tasks:        {report.total_tasks}",
        f"  Passed tasks:       {report.passed_tasks}",
        f"  pass@1:             {pass_at_1_pct:.1f}%",
        f"  {'pass@' + str(report.k) + ':':<20}{pass_at_k_pct:.1f}%",
        f"  Cheating rejected:  {report.cheating_rejected}",
        f"  Avg duration/task:  {report.avg_duration:.2f}s",
        "",
    ]

    if report.error_distribution:
        lines.append("  Error distribution:")
        # Sort by count descending
        for category, count in sorted(
            report.error_distribution.items(), key=lambda x: -x[1]
        ):
            bar = "█" * min(count, 40)
            lines.append(f"    {category:<35s} {count:>4d}  {bar}")
        lines.append("")

    return "\n".join(lines)


def format_benchmark_json(report: BenchmarkReport) -> str:
    """Export a BenchmarkReport as a JSON string.

    TaskResult and AttemptResult objects are serialized recursively.

    Args:
        report: BenchmarkReport to export.

    Returns:
        JSON string (pretty-printed with 2-space indent).
    """
    def _serialize(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _serialize(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [_serialize(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        return obj

    data = _serialize(report)
    return json.dumps(data, indent=2)


def compare_to_baselines(report: BenchmarkReport) -> str:
    """Compare Nightjar's benchmark results to published baselines.

    Baselines from vericoding paper (arxiv:2509.22908 Table 3):
    - Claude Opus 4.1: 67.5% pass@1 (best individual model)
    - GPT-5: 66.1% pass@1
    - Model union (any of 9 models in ≤5 attempts): 82.2%

    The comparison uses pass@1 for individual model comparisons and
    pass@k for model-union comparison.

    Args:
        report: BenchmarkReport to compare.

    Returns:
        Formatted comparison string.
    """
    nightjar_p1 = report.pass_at_1 * 100
    nightjar_pk = report.pass_at_k * 100

    delta_vs_best = nightjar_p1 - _BASELINE_CLAUDE_OPUS
    delta_vs_union = nightjar_pk - _BASELINE_MODEL_UNION

    lines: list[str] = [
        "",
        "  Comparison to vericoding baselines (arxiv:2509.22908)",
        "  " + "─" * 52,
        f"  {'Model':<35s} {'pass@1':>7s}   {'vs Nightjar':>10s}",
        "  " + "─" * 52,
        f"  {'Claude Opus 4.1 (best individual)':<35s} {_BASELINE_CLAUDE_OPUS:>6.1f}%"
        f"   {'+' if delta_vs_best >= 0 else ''}{delta_vs_best:+.1f}pp",
        f"  {'GPT-5':<35s} {_BASELINE_GPT5:>6.1f}%   {nightjar_p1 - _BASELINE_GPT5:+.1f}pp",
        f"  {'Claude Sonnet 4':<35s} {_BASELINE_SONNET4:>6.1f}%"
        f"   {nightjar_p1 - _BASELINE_SONNET4:+.1f}pp",
        f"  {'Nightjar (this run)':<35s} {nightjar_p1:>6.1f}%",
        "  " + "─" * 52,
    ]

    if delta_vs_best > 0:
        lines.append(
            f"  Nightjar exceeds best individual model by +{delta_vs_best:.1f} percentage points."
        )
    else:
        lines.append(
            f"  Nightjar is {abs(delta_vs_best):.1f}pp below best individual model baseline."
            f" Target: >{_BASELINE_CLAUDE_OPUS:.1f}%"
        )

    lines += [
        "",
        f"  Model union (any of 9 models, ≤5 attempts): {_BASELINE_MODEL_UNION:.1f}%",
        f"  Nightjar pass@{report.k}:                        {nightjar_pk:.1f}%",
    ]

    if delta_vs_union > 0:
        lines.append(
            f"  Nightjar exceeds the model union by +{delta_vs_union:.1f}pp — "
            f"a strong result."
        )
    else:
        lines.append(
            f"  Nightjar is {abs(delta_vs_union):.1f}pp below the model union score."
        )

    lines.append("")
    return "\n".join(lines)
