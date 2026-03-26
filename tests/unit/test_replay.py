"""Tests for the experience replay store.

When generation + verification succeeds, store the (spec, prompt,
generated_code, verification_result) tuple. On future generation for
similar specs, retrieve top-K successful examples as few-shot context.

References:
- [REF-C06] LLM-driven invariant enrichment — few-shot from past successes
- [REF-P04] AlphaVerus — self-improving loop uses replay of successful runs
"""

import os

import pytest

from contractd.replay import (
    ReplayStore,
    store_success,
    retrieve_similar,
    get_replay_count,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "replay.db")


@pytest.fixture
def store(db_path):
    return ReplayStore(db_path)


SAMPLE_SPEC = "module: payment\ninvariants:\n  - amount > 0"
SAMPLE_PROMPT = "Generate a payment processor that validates amounts."
SAMPLE_CODE = "def process_payment(amount: float) -> bool:\n    return amount > 0"
SAMPLE_RESULT = {"verified": True, "stages": [{"stage": 0, "status": "pass"}]}


class TestReplayStoreInit:
    """Tests for store initialization."""

    def test_creates_db_file(self, db_path):
        ReplayStore(db_path)
        assert os.path.exists(db_path)

    def test_creates_successes_table(self, store):
        import sqlite3
        conn = sqlite3.connect(store.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='successes'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent_init(self, db_path):
        ReplayStore(db_path)
        ReplayStore(db_path)


class TestStoreSuccess:
    """Tests for storing successful generation+verification tuples."""

    def test_store_returns_id(self, store):
        entry_id = store.store_success(
            spec_id="payment",
            spec_text=SAMPLE_SPEC,
            prompt=SAMPLE_PROMPT,
            generated_code=SAMPLE_CODE,
            verification_result=SAMPLE_RESULT,
        )
        assert isinstance(entry_id, int)
        assert entry_id > 0

    def test_store_multiple(self, store):
        id1 = store.store_success("s1", "spec1", "prompt1", "code1", {"verified": True})
        id2 = store.store_success("s2", "spec2", "prompt2", "code2", {"verified": True})
        assert id2 > id1

    def test_count_after_store(self, store):
        store.store_success("s1", "spec1", "p1", "c1", {"verified": True})
        store.store_success("s2", "spec2", "p2", "c2", {"verified": True})
        assert store.get_count() == 2


class TestRetrieveSimilar:
    """Tests for TF-IDF similarity retrieval."""

    def test_retrieve_returns_list(self, store):
        store.store_success("payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT)
        results = store.retrieve_similar("payment processor with amount validation", k=3)
        assert isinstance(results, list)

    def test_retrieve_returns_matching_entries(self, store):
        store.store_success("payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT)
        store.store_success(
            "auth",
            "module: auth\ninvariants:\n  - token is not None",
            "Generate auth token validator",
            "def validate_token(token): return token is not None",
            {"verified": True},
        )

        results = store.retrieve_similar("payment amount validation", k=1)
        assert len(results) == 1
        assert results[0]["spec_id"] == "payment"

    def test_retrieve_respects_k_limit(self, store):
        for i in range(10):
            store.store_success(
                f"spec{i}", f"module: spec{i}", f"prompt{i}", f"code{i}", {"verified": True}
            )
        results = store.retrieve_similar("some query", k=3)
        assert len(results) <= 3

    def test_retrieve_empty_store(self, store):
        results = store.retrieve_similar("anything", k=5)
        assert results == []

    def test_retrieve_entry_has_expected_fields(self, store):
        store.store_success("payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT)
        results = store.retrieve_similar("payment", k=1)
        assert len(results) == 1
        entry = results[0]
        assert "spec_id" in entry
        assert "spec_text" in entry
        assert "prompt" in entry
        assert "generated_code" in entry
        assert "verification_result" in entry
        assert "similarity" in entry

    def test_similarity_score_range(self, store):
        store.store_success("payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT)
        results = store.retrieve_similar("payment", k=1)
        assert 0.0 <= results[0]["similarity"] <= 1.0

    def test_more_similar_spec_ranks_higher(self, store):
        store.store_success(
            "payment",
            "module: payment\nprocess payments with amount validation",
            "Generate payment processor",
            "def process(amount): pass",
            {"verified": True},
        )
        store.store_success(
            "logging",
            "module: logging\nconfigure structured log output with levels",
            "Generate a logger",
            "def log(msg): pass",
            {"verified": True},
        )

        results = store.retrieve_similar(
            "payment processing amount", k=2
        )
        # Payment should rank higher than logging for a payment query
        assert results[0]["spec_id"] == "payment"


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_store_success_function(self, db_path):
        entry_id = store_success(
            db_path, "payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT
        )
        assert entry_id > 0

    def test_retrieve_similar_function(self, db_path):
        store_success(db_path, "payment", SAMPLE_SPEC, SAMPLE_PROMPT, SAMPLE_CODE, SAMPLE_RESULT)
        results = retrieve_similar(db_path, "payment", k=1)
        assert len(results) == 1

    def test_get_replay_count_function(self, db_path):
        store_success(db_path, "s1", "spec", "prompt", "code", {"verified": True})
        assert get_replay_count(db_path) == 1
