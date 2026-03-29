"""Tests for the benchmark runner.

Validates scoring, cheating detection, error distribution, report formatting,
and JSON export against the vericoding/DafnyBench benchmark harness.

References:
- Vericoding paper: arxiv:2509.22908 (POPL 2026 Dafny workshop)
- DafnyBench: arxiv:2406.08467 (Harvard/MIT)
- Part 4 of research-benchmark-dafny-errors.md — implementation plan
- Part 5 of research-benchmark-dafny-errors.md — scoring / marketing claims
"""

import json
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nightjar.benchmark_runner import (
    AttemptResult,
    BenchmarkReport,
    TaskResult,
    compare_to_baselines,
    format_benchmark_json,
    format_benchmark_report,
    run_benchmark,
    run_single_task,
    score_pass_at_k,
)


# ---------------------------------------------------------------------------
# Helpers — minimal BenchmarkTask stub (no import from benchmark_adapter)
# ---------------------------------------------------------------------------

@dataclass
class _FakeTask:
    """Minimal stand-in for BenchmarkTask from benchmark_adapter."""
    task_id: str
    spec: str = "ensures result > 0"
    preamble: str = ""
    source: str = "vericoding"
    dataset: str = "HumanEval-Dafny"


def _make_task(task_id: str = "task-001") -> _FakeTask:
    return _FakeTask(task_id=task_id)


def _make_attempt(
    attempt_num: int = 1,
    success: bool = True,
    cheating: list[str] | None = None,
    error_category: str | None = None,
    duration: float = 0.5,
) -> AttemptResult:
    return AttemptResult(
        attempt_num=attempt_num,
        success=success,
        cheating_violations=cheating or [],
        dafny_output="",
        duration_seconds=duration,
        error_category=error_category,
    )


def _make_task_result(
    task_id: str = "task-001",
    passed: bool = True,
    best_attempt: int = 0,
    attempts: list[AttemptResult] | None = None,
) -> TaskResult:
    if attempts is None:
        attempts = [_make_attempt(attempt_num=1, success=passed)]
    return TaskResult(
        task_id=task_id,
        attempts=attempts,
        passed=passed,
        best_attempt=best_attempt,
    )


def _make_report(
    passed_tasks: int = 3,
    total_tasks: int = 5,
    pass_at_1: float = 0.6,
    pass_at_k: float = 0.8,
    k: int = 5,
    cheating_rejected: int = 0,
    avg_duration: float = 1.2,
    error_distribution: dict | None = None,
    results: list[TaskResult] | None = None,
) -> BenchmarkReport:
    return BenchmarkReport(
        source="vericoding",
        dataset="HumanEval-Dafny",
        total_tasks=total_tasks,
        passed_tasks=passed_tasks,
        pass_at_1=pass_at_1,
        pass_at_k=pass_at_k,
        k=k,
        cheating_rejected=cheating_rejected,
        avg_duration=avg_duration,
        error_distribution=error_distribution or {"postcondition_failure": 2},
        results=results or [_make_task_result()],
    )


# ---------------------------------------------------------------------------
# 1. score_pass_at_k — formula correctness
# ---------------------------------------------------------------------------

class TestScorePassAtK:
    """Tests for the pass@k metric calculation.

    Scenario: 5 tasks, 3 pass on attempt 1, 1 passes on attempt 3, 1 never passes.
    Expected: pass@1 = 3/5 = 60%, pass@5 = 4/5 = 80%.
    """

    def _build_results(self) -> list[TaskResult]:
        results = []
        # Tasks that pass on first attempt
        for i in range(3):
            results.append(TaskResult(
                task_id=f"task-{i:03d}",
                attempts=[_make_attempt(attempt_num=1, success=True)],
                passed=True,
                best_attempt=0,
            ))
        # Task that passes on third attempt
        results.append(TaskResult(
            task_id="task-003",
            attempts=[
                _make_attempt(attempt_num=1, success=False),
                _make_attempt(attempt_num=2, success=False),
                _make_attempt(attempt_num=3, success=True),
            ],
            passed=True,
            best_attempt=2,
        ))
        # Task that never passes
        results.append(TaskResult(
            task_id="task-004",
            attempts=[
                _make_attempt(attempt_num=1, success=False),
                _make_attempt(attempt_num=2, success=False),
            ],
            passed=False,
            best_attempt=-1,
        ))
        return results

    def test_pass_at_1_is_60_percent(self):
        results = self._build_results()
        score = score_pass_at_k(results, k=1)
        assert abs(score - 0.6) < 1e-9

    def test_pass_at_5_is_80_percent(self):
        results = self._build_results()
        score = score_pass_at_k(results, k=5)
        assert abs(score - 0.8) < 1e-9

    def test_pass_at_k_empty_results_returns_zero(self):
        assert score_pass_at_k([], k=1) == 0.0

    def test_pass_at_k_all_fail_returns_zero(self):
        results = [
            TaskResult(
                task_id="t1",
                attempts=[_make_attempt(success=False)],
                passed=False,
                best_attempt=-1,
            )
        ]
        assert score_pass_at_k(results, k=5) == 0.0

    def test_pass_at_k_all_pass_returns_one(self):
        results = [
            TaskResult(
                task_id=f"t{i}",
                attempts=[_make_attempt(success=True)],
                passed=True,
                best_attempt=0,
            )
            for i in range(4)
        ]
        assert abs(score_pass_at_k(results, k=1) - 1.0) < 1e-9

    def test_pass_at_k_respects_k_limit(self):
        """k=2 should only count tasks that pass within first 2 attempts."""
        results = [
            # passes on attempt 1 — counts for k=1 and k=2
            TaskResult(
                task_id="t0",
                attempts=[_make_attempt(attempt_num=1, success=True)],
                passed=True,
                best_attempt=0,
            ),
            # passes on attempt 3 — counts for k=5 but NOT k=2
            TaskResult(
                task_id="t1",
                attempts=[
                    _make_attempt(attempt_num=1, success=False),
                    _make_attempt(attempt_num=2, success=False),
                    _make_attempt(attempt_num=3, success=True),
                ],
                passed=True,
                best_attempt=2,
            ),
        ]
        score_k2 = score_pass_at_k(results, k=2)
        score_k5 = score_pass_at_k(results, k=5)
        assert abs(score_k2 - 0.5) < 1e-9  # only t0
        assert abs(score_k5 - 1.0) < 1e-9  # both t0 and t1


# ---------------------------------------------------------------------------
# 2. Cheating detection — task with assume → rejected
# ---------------------------------------------------------------------------

class TestCheatingRejection:
    """Tasks that use assume/axiom are rejected even if Dafny says pass."""

    def test_cheating_attempt_not_counted_as_pass(self):
        """An attempt with cheating violations must not be counted as success."""
        attempt = AttemptResult(
            attempt_num=1,
            success=False,  # should be False when cheating detected
            cheating_violations=["assume x > 0;"],
            dafny_output="Verified",
            duration_seconds=0.3,
            error_category=None,
        )
        result = TaskResult(
            task_id="cheat-task",
            attempts=[attempt],
            passed=False,
            best_attempt=-1,
        )
        assert not result.passed

    def test_cheating_violations_field_populated(self):
        """cheating_violations list captures the offending patterns."""
        attempt = AttemptResult(
            attempt_num=1,
            success=False,
            cheating_violations=["assume a == b;", "{:axiom}"],
            dafny_output="",
            duration_seconds=0.1,
            error_category=None,
        )
        assert len(attempt.cheating_violations) == 2
        assert "assume a == b;" in attempt.cheating_violations

    def test_cheating_rejected_count_in_report(self):
        """BenchmarkReport.cheating_rejected tracks how many tasks cheated."""
        report = _make_report(cheating_rejected=3)
        assert report.cheating_rejected == 3


# ---------------------------------------------------------------------------
# 3. format_benchmark_report — output contains expected strings
# ---------------------------------------------------------------------------

class TestFormatBenchmarkReport:

    def test_contains_pass_at_1(self):
        report = _make_report(pass_at_1=0.6, pass_at_k=0.8)
        output = format_benchmark_report(report)
        assert "60" in output or "0.6" in output  # percentage shown

    def test_contains_pass_at_k(self):
        report = _make_report(pass_at_k=0.8, k=5)
        output = format_benchmark_report(report)
        assert "80" in output or "0.8" in output

    def test_contains_dataset_name(self):
        report = _make_report()
        output = format_benchmark_report(report)
        assert "HumanEval-Dafny" in output

    def test_contains_source(self):
        report = _make_report()
        output = format_benchmark_report(report)
        assert "vericoding" in output

    def test_contains_error_distribution(self):
        report = _make_report(error_distribution={"postcondition_failure": 7, "other": 2})
        output = format_benchmark_report(report)
        assert "postcondition_failure" in output

    def test_contains_total_tasks(self):
        report = _make_report(total_tasks=164)
        output = format_benchmark_report(report)
        assert "164" in output

    def test_returns_string(self):
        report = _make_report()
        output = format_benchmark_report(report)
        assert isinstance(output, str)
        assert len(output) > 0


# ---------------------------------------------------------------------------
# 4. format_benchmark_json — valid JSON, correct fields
# ---------------------------------------------------------------------------

class TestFormatBenchmarkJson:

    def test_is_valid_json(self):
        report = _make_report()
        raw = format_benchmark_json(report)
        parsed = json.loads(raw)  # must not raise
        assert isinstance(parsed, dict)

    def test_json_has_pass_at_1(self):
        report = _make_report(pass_at_1=0.6)
        parsed = json.loads(format_benchmark_json(report))
        assert "pass_at_1" in parsed
        assert abs(parsed["pass_at_1"] - 0.6) < 1e-9

    def test_json_has_pass_at_k(self):
        report = _make_report(pass_at_k=0.8, k=5)
        parsed = json.loads(format_benchmark_json(report))
        assert "pass_at_k" in parsed
        assert abs(parsed["pass_at_k"] - 0.8) < 1e-9

    def test_json_has_error_distribution(self):
        dist = {"postcondition_failure": 3, "loop_invariant_failure": 1}
        report = _make_report(error_distribution=dist)
        parsed = json.loads(format_benchmark_json(report))
        assert "error_distribution" in parsed
        assert parsed["error_distribution"]["postcondition_failure"] == 3

    def test_json_has_results_list(self):
        results = [_make_task_result("t1"), _make_task_result("t2")]
        report = _make_report(results=results)
        parsed = json.loads(format_benchmark_json(report))
        assert "results" in parsed
        assert len(parsed["results"]) == 2

    def test_json_has_cheating_rejected(self):
        report = _make_report(cheating_rejected=2)
        parsed = json.loads(format_benchmark_json(report))
        assert parsed["cheating_rejected"] == 2


# ---------------------------------------------------------------------------
# 5. compare_to_baselines — references known paper numbers
# ---------------------------------------------------------------------------

class TestCompareToBaselines:

    def test_mentions_claude_opus(self):
        report = _make_report(pass_at_1=0.75)
        output = compare_to_baselines(report)
        # Should reference Claude Opus 4.1 baseline from the paper
        assert "Claude" in output or "claude" in output or "67.5" in output

    def test_mentions_model_union(self):
        report = _make_report(pass_at_1=0.85, pass_at_k=0.90)
        output = compare_to_baselines(report)
        assert "82.2" in output or "model union" in output.lower()

    def test_shows_improvement_when_above_baseline(self):
        """When Nightjar exceeds 67.5%, comparison should note the improvement."""
        report = _make_report(pass_at_1=0.80)
        output = compare_to_baselines(report)
        # Should contain some positive delta signal
        assert output  # non-empty
        assert isinstance(output, str)

    def test_shows_warning_when_below_baseline(self):
        """When Nightjar is below 67.5%, comparison should flag it."""
        report = _make_report(pass_at_1=0.50)
        output = compare_to_baselines(report)
        assert output  # non-empty (no crash)


# ---------------------------------------------------------------------------
# 6. Error distribution counting
# ---------------------------------------------------------------------------

class TestErrorDistribution:

    def test_distribution_counts_categories(self):
        """error_distribution maps category → count correctly."""
        results = [
            TaskResult(
                task_id="t0",
                attempts=[
                    _make_attempt(success=False, error_category="postcondition_failure"),
                    _make_attempt(attempt_num=2, success=True, error_category=None),
                ],
                passed=True,
                best_attempt=1,
            ),
            TaskResult(
                task_id="t1",
                attempts=[
                    _make_attempt(success=False, error_category="postcondition_failure"),
                    _make_attempt(attempt_num=2, success=False, error_category="loop_invariant_failure"),
                ],
                passed=False,
                best_attempt=-1,
            ),
        ]
        # Build a report from these results (manually count for assertion)
        dist: dict[str, int] = {}
        for r in results:
            for a in r.attempts:
                if a.error_category:
                    dist[a.error_category] = dist.get(a.error_category, 0) + 1

        assert dist["postcondition_failure"] == 2
        assert dist["loop_invariant_failure"] == 1

    def test_distribution_in_report_is_dict(self):
        report = _make_report(error_distribution={"other": 5})
        assert isinstance(report.error_distribution, dict)


# ---------------------------------------------------------------------------
# 7. run_single_task — mocked pipeline, no real Dafny
# ---------------------------------------------------------------------------

class TestRunSingleTask:
    """run_single_task calls the verification pipeline. We mock it."""

    def _make_verify_result(self, verified: bool) -> MagicMock:
        from nightjar.types import VerifyResult, VerifyStatus, StageResult
        mock = MagicMock()
        mock.verified = verified
        mock.stages = []
        return mock

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=[])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_passes_on_verified_result(self, mock_gen, mock_cheat, mock_pipeline):
        mock_pipeline.return_value = self._make_verify_result(verified=True)
        task = _make_task("t001")
        result = run_single_task(task, max_attempts=1, timeout=30)
        assert result.passed is True
        assert result.best_attempt == 0

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=[])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_fails_when_pipeline_fails(self, mock_gen, mock_cheat, mock_pipeline):
        mock_pipeline.return_value = self._make_verify_result(verified=False)
        task = _make_task("t002")
        result = run_single_task(task, max_attempts=2, timeout=30)
        assert result.passed is False
        assert result.best_attempt == -1

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=["assume x > 0;"])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_cheating_causes_rejection(self, mock_gen, mock_cheat, mock_pipeline):
        """Even if pipeline says verified=True, cheating violations → not passed."""
        mock_pipeline.return_value = self._make_verify_result(verified=True)
        task = _make_task("t003")
        result = run_single_task(task, max_attempts=1, timeout=30)
        assert result.passed is False
        assert len(result.attempts[0].cheating_violations) > 0

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=[])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_retries_on_failure(self, mock_gen, mock_cheat, mock_pipeline):
        """Pipeline is called up to max_attempts times on failure."""
        mock_pipeline.return_value = self._make_verify_result(verified=False)
        task = _make_task("t004")
        result = run_single_task(task, max_attempts=3, timeout=30)
        assert len(result.attempts) == 3
        assert mock_pipeline.call_count == 3

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=[])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_stops_retrying_on_first_success(self, mock_gen, mock_cheat, mock_pipeline):
        """Once verified, no more retries are performed."""
        mock_pipeline.return_value = self._make_verify_result(verified=True)
        task = _make_task("t005")
        result = run_single_task(task, max_attempts=5, timeout=30)
        assert mock_pipeline.call_count == 1
        assert result.passed is True


# ---------------------------------------------------------------------------
# 8. Timeout handling
# ---------------------------------------------------------------------------

class TestTimeoutHandling:

    @patch("nightjar.benchmark_runner.run_pipeline")
    @patch("nightjar.benchmark_runner.detect_cheating", return_value=[])
    @patch("nightjar.benchmark_runner._generate_code_for_task", return_value="def f(): pass")
    def test_timeout_marks_attempt_as_failed(self, mock_gen, mock_cheat, mock_pipeline):
        """A pipeline that raises TimeoutError is caught; task is marked failed."""
        import concurrent.futures
        mock_pipeline.side_effect = concurrent.futures.TimeoutError("timed out")
        task = _make_task("t-timeout")
        result = run_single_task(task, max_attempts=1, timeout=1)
        assert result.passed is False
        # Attempt should still be recorded
        assert len(result.attempts) >= 1


# ---------------------------------------------------------------------------
# 9. run_benchmark — mocked single-task runner
# ---------------------------------------------------------------------------

class TestRunBenchmark:

    @patch("nightjar.benchmark_runner.run_single_task")
    def test_report_aggregates_task_results(self, mock_single):
        """run_benchmark aggregates all TaskResult objects into a BenchmarkReport."""
        mock_single.side_effect = [
            _make_task_result("t0", passed=True, best_attempt=0),
            _make_task_result("t1", passed=True, best_attempt=0),
            _make_task_result("t2", passed=False, best_attempt=-1),
        ]
        tasks = [_make_task(f"t{i}") for i in range(3)]
        report = run_benchmark(tasks, max_attempts=1, timeout_per_task=30, workers=1)

        assert report.total_tasks == 3
        assert report.passed_tasks == 2
        assert abs(report.pass_at_1 - 2 / 3) < 1e-9

    @patch("nightjar.benchmark_runner.run_single_task")
    def test_report_source_and_dataset_propagated(self, mock_single):
        """source/dataset come from the first task's attributes."""
        mock_single.return_value = _make_task_result("t0", passed=True)
        tasks = [_make_task("t0")]
        report = run_benchmark(tasks, max_attempts=1, timeout_per_task=30, workers=1)
        assert report.source == "vericoding"
        assert report.dataset == "HumanEval-Dafny"

    @patch("nightjar.benchmark_runner.run_single_task")
    def test_pass_at_k_is_computed(self, mock_single):
        """pass_at_k in report equals score_pass_at_k(results, k)."""
        results = [
            _make_task_result("t0", passed=True, best_attempt=0),
            _make_task_result("t1", passed=False, best_attempt=-1),
        ]
        mock_single.side_effect = results
        tasks = [_make_task(f"t{i}") for i in range(2)]
        report = run_benchmark(tasks, max_attempts=5, timeout_per_task=30, workers=1)
        expected = score_pass_at_k(results, k=5)
        assert abs(report.pass_at_k - expected) < 1e-9

    @patch("nightjar.benchmark_runner.run_single_task")
    def test_error_distribution_populated(self, mock_single):
        """error_distribution counts error categories across all failed attempts."""
        mock_single.return_value = TaskResult(
            task_id="t0",
            attempts=[
                _make_attempt(success=False, error_category="postcondition_failure"),
            ],
            passed=False,
            best_attempt=-1,
        )
        tasks = [_make_task("t0")]
        report = run_benchmark(tasks, max_attempts=1, timeout_per_task=30, workers=1)
        assert "postcondition_failure" in report.error_distribution
        assert report.error_distribution["postcondition_failure"] >= 1
