"""Tests for the shared invariant pattern library.

Append-only library of abstracted invariant patterns. Each entry:
pattern_id, abstract_form, abstract_invariant, tenant_confidence
(DP-protected), verification_method, proof_artifact_hash.

References:
- [REF-C09] Immune system acquired immunity
- [REF-C10] Herd immunity via differential privacy
"""

import os
import time

import pytest

from immune.pattern_library import (
    InvariantPattern,
    PatternLibrary,
    add_pattern,
    get_pattern,
    search_patterns,
    get_pattern_count,
    update_confidence,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "patterns.db")


@pytest.fixture
def library(db_path):
    return PatternLibrary(db_path)


SAMPLE_PATTERN = InvariantPattern(
    pattern_id="",  # Auto-generated
    fingerprint="abc123def456",
    abstract_form="AttributeError on (arg0: ObjectType{f0: NullType})",
    abstract_invariant="assert arg0.f0 is not None",
    tenant_count_dp=52.3,
    confidence_dp=0.95,
    verification_method="crosshair",
    proof_hash="sha256:deadbeef",
    is_universal=False,
)


class TestPatternLibraryInit:
    """Tests for library initialization."""

    def test_creates_db(self, db_path):
        PatternLibrary(db_path)
        assert os.path.exists(db_path)

    def test_creates_patterns_table(self, library):
        import sqlite3
        conn = sqlite3.connect(library.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent(self, db_path):
        PatternLibrary(db_path)
        PatternLibrary(db_path)


class TestAddPattern:
    """Tests for adding patterns."""

    def test_add_returns_pattern_id(self, library):
        pid = library.add_pattern(SAMPLE_PATTERN)
        assert isinstance(pid, str)
        assert len(pid) > 0

    def test_add_multiple(self, library):
        id1 = library.add_pattern(SAMPLE_PATTERN)
        p2 = InvariantPattern(
            pattern_id="",
            fingerprint="xyz789",
            abstract_form="TypeError on (arg0: StringType)",
            abstract_invariant="assert isinstance(arg0, int)",
            tenant_count_dp=10.0,
            confidence_dp=0.6,
            verification_method="hypothesis",
            proof_hash="sha256:cafebabe",
            is_universal=False,
        )
        id2 = library.add_pattern(p2)
        assert id1 != id2

    def test_count_after_add(self, library):
        library.add_pattern(SAMPLE_PATTERN)
        assert library.get_count() == 1


class TestGetPattern:
    """Tests for retrieving patterns."""

    def test_get_by_id(self, library):
        pid = library.add_pattern(SAMPLE_PATTERN)
        pattern = library.get_pattern(pid)
        assert pattern is not None
        assert pattern.fingerprint == "abc123def456"
        assert pattern.abstract_invariant == "assert arg0.f0 is not None"

    def test_get_nonexistent(self, library):
        assert library.get_pattern("nonexistent") is None

    def test_get_by_fingerprint(self, library):
        library.add_pattern(SAMPLE_PATTERN)
        patterns = library.get_by_fingerprint("abc123def456")
        assert len(patterns) == 1
        assert patterns[0].fingerprint == "abc123def456"

    def test_get_by_fingerprint_empty(self, library):
        assert library.get_by_fingerprint("nonexistent") == []


class TestSearchPatterns:
    """Tests for searching the library."""

    def test_search_returns_list(self, library):
        library.add_pattern(SAMPLE_PATTERN)
        results = library.search("AttributeError")
        assert isinstance(results, list)
        assert len(results) == 1

    def test_search_no_match(self, library):
        library.add_pattern(SAMPLE_PATTERN)
        results = library.search("ZeroDivisionError")
        assert results == []

    def test_search_universal_only(self, library):
        library.add_pattern(SAMPLE_PATTERN)
        p2 = InvariantPattern(
            pattern_id="",
            fingerprint="xyz",
            abstract_form="Universal pattern",
            abstract_invariant="assert True",
            tenant_count_dp=100.0,
            confidence_dp=0.99,
            verification_method="crosshair",
            proof_hash="sha256:aaa",
            is_universal=True,
        )
        library.add_pattern(p2)

        universals = library.get_universal_patterns()
        assert len(universals) == 1
        assert universals[0].is_universal is True


class TestUpdateConfidence:
    """Tests for updating DP-protected confidence."""

    def test_update_confidence(self, library):
        pid = library.add_pattern(SAMPLE_PATTERN)
        library.update_confidence(pid, tenant_count_dp=60.0, confidence_dp=0.98)

        updated = library.get_pattern(pid)
        assert updated.tenant_count_dp == 60.0
        assert updated.confidence_dp == 0.98

    def test_promote_to_universal(self, library):
        pid = library.add_pattern(SAMPLE_PATTERN)
        library.promote_to_universal(pid)

        pattern = library.get_pattern(pid)
        assert pattern.is_universal is True


class TestModuleLevelFunctions:
    """Tests for convenience functions."""

    def test_add_and_get(self, db_path):
        pid = add_pattern(db_path, SAMPLE_PATTERN)
        pattern = get_pattern(db_path, pid)
        assert pattern is not None

    def test_search(self, db_path):
        add_pattern(db_path, SAMPLE_PATTERN)
        results = search_patterns(db_path, "AttributeError")
        assert len(results) == 1

    def test_count(self, db_path):
        add_pattern(db_path, SAMPLE_PATTERN)
        assert get_pattern_count(db_path) == 1

    def test_update_confidence_func(self, db_path):
        pid = add_pattern(db_path, SAMPLE_PATTERN)
        update_confidence(db_path, pid, 75.0, 0.97)
        pattern = get_pattern(db_path, pid)
        assert pattern.confidence_dp == 0.97
