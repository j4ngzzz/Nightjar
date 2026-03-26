"""Tests for the verification tracking database.

Validates that every verification run is recorded in SQLite with
schema: runs(id, spec_id, model, timestamp, verified, stage_results_json,
retry_count, total_cost). Computes rolling pass rate per model, per spec.

References:
- ARCHITECTURE.md Section 6 — self-evolution pipeline
- [REF-C02] Closed-loop verification tracks outcomes for improvement
"""

import json
import os
import tempfile
import time

import pytest

from contractd.tracking import (
    TrackingDB,
    record_run,
    get_pass_rate,
    get_pass_rate_by_model,
    get_pass_rate_by_spec,
    get_recent_runs,
    get_run_count,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "tracking.db")


@pytest.fixture
def db(db_path):
    """Create a fresh TrackingDB instance."""
    return TrackingDB(db_path)


class TestTrackingDBInit:
    """Tests for database initialization."""

    def test_creates_database_file(self, db_path):
        """DB file should be created on init."""
        TrackingDB(db_path)
        assert os.path.exists(db_path)

    def test_creates_runs_table(self, db):
        """The runs table should exist after init."""
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent_init(self, db_path):
        """Creating DB twice on same path should not error."""
        TrackingDB(db_path)
        TrackingDB(db_path)  # Should not raise


class TestRecordRun:
    """Tests for recording verification runs."""

    def test_record_basic_run(self, db):
        """Should store a run and return its ID."""
        run_id = db.record_run(
            spec_id="payment",
            model="claude-sonnet-4-6",
            verified=True,
            stage_results=[{"stage": 0, "status": "pass"}],
            retry_count=0,
            total_cost=0.05,
        )
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_record_failed_run(self, db):
        """Should store failed runs too."""
        run_id = db.record_run(
            spec_id="auth",
            model="deepseek/deepseek-chat",
            verified=False,
            stage_results=[{"stage": 3, "status": "fail", "errors": ["pbt failed"]}],
            retry_count=3,
            total_cost=0.12,
        )
        assert run_id > 0

    def test_timestamp_is_set(self, db):
        """Timestamp should be auto-set on record."""
        before = time.time()
        db.record_run(
            spec_id="payment",
            model="claude-sonnet-4-6",
            verified=True,
            stage_results=[],
            retry_count=0,
            total_cost=0.0,
        )
        after = time.time()

        runs = db.get_recent_runs(limit=1)
        assert len(runs) == 1
        assert before <= runs[0]["timestamp"] <= after

    def test_stage_results_stored_as_json(self, db):
        """Stage results should be retrievable as structured data."""
        stages = [
            {"stage": 0, "name": "preflight", "status": "pass"},
            {"stage": 1, "name": "deps", "status": "pass"},
            {"stage": 3, "name": "pbt", "status": "fail", "errors": ["counterexample found"]},
        ]
        db.record_run(
            spec_id="payment",
            model="claude-sonnet-4-6",
            verified=False,
            stage_results=stages,
            retry_count=1,
            total_cost=0.08,
        )

        runs = db.get_recent_runs(limit=1)
        assert runs[0]["stage_results"] == stages

    def test_multiple_runs_sequential_ids(self, db):
        """Multiple runs should get sequential IDs."""
        id1 = db.record_run("spec1", "model1", True, [], 0, 0.0)
        id2 = db.record_run("spec2", "model2", False, [], 1, 0.1)
        assert id2 > id1


class TestPassRate:
    """Tests for pass rate computation."""

    def test_overall_pass_rate(self, db):
        """Pass rate across all runs."""
        db.record_run("spec1", "model1", True, [], 0, 0.0)
        db.record_run("spec1", "model1", True, [], 0, 0.0)
        db.record_run("spec1", "model1", False, [], 1, 0.1)

        rate = db.get_pass_rate()
        assert abs(rate - 2 / 3) < 0.01

    def test_pass_rate_empty_db(self, db):
        """Pass rate should be 0.0 with no runs."""
        assert db.get_pass_rate() == 0.0

    def test_pass_rate_by_model(self, db):
        """Pass rate filtered by model."""
        db.record_run("spec1", "claude-sonnet-4-6", True, [], 0, 0.0)
        db.record_run("spec1", "claude-sonnet-4-6", True, [], 0, 0.0)
        db.record_run("spec1", "deepseek/deepseek-chat", False, [], 2, 0.1)
        db.record_run("spec1", "deepseek/deepseek-chat", True, [], 0, 0.0)

        claude_rate = db.get_pass_rate_by_model("claude-sonnet-4-6")
        deepseek_rate = db.get_pass_rate_by_model("deepseek/deepseek-chat")

        assert claude_rate == 1.0
        assert abs(deepseek_rate - 0.5) < 0.01

    def test_pass_rate_by_spec(self, db):
        """Pass rate filtered by spec_id."""
        db.record_run("payment", "model1", True, [], 0, 0.0)
        db.record_run("payment", "model1", True, [], 0, 0.0)
        db.record_run("auth", "model1", False, [], 1, 0.0)

        assert db.get_pass_rate_by_spec("payment") == 1.0
        assert db.get_pass_rate_by_spec("auth") == 0.0

    def test_pass_rate_unknown_model(self, db):
        """Pass rate for unknown model should be 0.0."""
        assert db.get_pass_rate_by_model("nonexistent") == 0.0

    def test_pass_rate_unknown_spec(self, db):
        """Pass rate for unknown spec should be 0.0."""
        assert db.get_pass_rate_by_spec("nonexistent") == 0.0


class TestRecentRuns:
    """Tests for retrieving recent runs."""

    def test_get_recent_runs_limit(self, db):
        """Should respect limit parameter."""
        for i in range(10):
            db.record_run(f"spec{i}", "model1", True, [], 0, 0.0)

        runs = db.get_recent_runs(limit=3)
        assert len(runs) == 3

    def test_get_recent_runs_ordered_by_timestamp(self, db):
        """Most recent runs should come first."""
        db.record_run("first", "model1", True, [], 0, 0.0)
        db.record_run("second", "model1", True, [], 0, 0.0)

        runs = db.get_recent_runs(limit=2)
        assert runs[0]["spec_id"] == "second"
        assert runs[1]["spec_id"] == "first"

    def test_get_recent_runs_includes_all_fields(self, db):
        """Each run dict should have all expected fields."""
        db.record_run("payment", "claude-sonnet-4-6", True, [{"s": 0}], 2, 0.05)

        runs = db.get_recent_runs(limit=1)
        run = runs[0]
        assert "id" in run
        assert run["spec_id"] == "payment"
        assert run["model"] == "claude-sonnet-4-6"
        assert run["verified"] is True
        assert run["stage_results"] == [{"s": 0}]
        assert run["retry_count"] == 2
        assert run["total_cost"] == pytest.approx(0.05)
        assert "timestamp" in run


class TestRunCount:
    """Tests for run counting."""

    def test_count_all(self, db):
        """Count all runs."""
        db.record_run("s1", "m1", True, [], 0, 0.0)
        db.record_run("s2", "m1", False, [], 0, 0.0)
        assert db.get_run_count() == 2

    def test_count_empty(self, db):
        """Count with no runs."""
        assert db.get_run_count() == 0


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_record_run_function(self, db_path):
        """Module-level record_run should work with db_path."""
        run_id = record_run(
            db_path=db_path,
            spec_id="payment",
            model="claude-sonnet-4-6",
            verified=True,
            stage_results=[],
            retry_count=0,
            total_cost=0.0,
        )
        assert run_id > 0

    def test_get_pass_rate_function(self, db_path):
        """Module-level get_pass_rate should work with db_path."""
        record_run(db_path, "s1", "m1", True, [], 0, 0.0)
        record_run(db_path, "s1", "m1", False, [], 0, 0.0)
        assert abs(get_pass_rate(db_path) - 0.5) < 0.01

    def test_get_pass_rate_by_model_function(self, db_path):
        """Module-level get_pass_rate_by_model should work."""
        record_run(db_path, "s1", "claude", True, [], 0, 0.0)
        assert get_pass_rate_by_model(db_path, "claude") == 1.0

    def test_get_pass_rate_by_spec_function(self, db_path):
        """Module-level get_pass_rate_by_spec should work."""
        record_run(db_path, "payment", "m1", True, [], 0, 0.0)
        assert get_pass_rate_by_spec(db_path, "payment") == 1.0

    def test_get_recent_runs_function(self, db_path):
        """Module-level get_recent_runs should work."""
        record_run(db_path, "s1", "m1", True, [], 0, 0.0)
        runs = get_recent_runs(db_path, limit=1)
        assert len(runs) == 1

    def test_get_run_count_function(self, db_path):
        """Module-level get_run_count should work."""
        record_run(db_path, "s1", "m1", True, [], 0, 0.0)
        assert get_run_count(db_path) == 1
