"""Tests for auto-appending verified invariants to .card.md files.

References:
- [REF-C09] Immune System / Acquired Immunity
- [REF-C01] Tiered invariants — CARD's invention
"""

import os
import tempfile
import pytest

from immune.spec_updater import (
    append_invariant,
    SpecUpdateResult,
    build_invariant_entry,
)


SAMPLE_CARD_MD = """\
---
card-version: "1.0"
id: payment-processing
title: Payment Processing Module
status: draft
invariants:
  - id: INV-001
    tier: example
    statement: "Processing a $10 USD payment returns a valid transaction_id"
    rationale: "Basic smoke test"
  - id: INV-002
    tier: property
    statement: "amount_charged + fee equals total deducted"
    rationale: "Financial integrity"
---

## Intent

Process payments securely.
"""


class TestBuildInvariantEntry:
    """Test YAML invariant entry construction."""

    def test_basic_entry(self):
        entry = build_invariant_entry(
            expression="result >= 0",
            explanation="Return value is always non-negative",
            origin_failure_id="ERR-2026-001",
        )
        assert entry["tier"] == "property"
        assert entry["statement"] == "result >= 0"
        assert entry["rationale"] == "Return value is always non-negative"
        assert entry["id"].startswith("INV-AUTO-")

    def test_entry_has_origin_metadata(self):
        entry = build_invariant_entry(
            expression="x > 0",
            explanation="Input must be positive",
            origin_failure_id="ERR-123",
            verification_method="crosshair+hypothesis",
        )
        assert "origin" in entry
        assert entry["origin"]["failure_id"] == "ERR-123"
        assert entry["origin"]["verification_method"] == "crosshair+hypothesis"
        assert "timestamp" in entry["origin"]

    def test_auto_id_is_unique(self):
        entry1 = build_invariant_entry("a > 0", "pos")
        entry2 = build_invariant_entry("b > 0", "pos")
        assert entry1["id"] != entry2["id"]


class TestAppendInvariant:
    """Test appending invariants to .card.md files."""

    def test_appends_to_invariants_block(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CARD_MD)
            tmp_path = f.name

        try:
            result = append_invariant(
                card_path=tmp_path,
                expression="result >= 0",
                explanation="Non-negative return",
            )
            assert isinstance(result, SpecUpdateResult)
            assert result.success is True
            assert result.invariant_id.startswith("INV-AUTO-")

            # Verify the file was updated
            content = open(tmp_path, encoding="utf-8").read()
            assert "result >= 0" in content
            assert "Non-negative return" in content
        finally:
            os.unlink(tmp_path)

    def test_preserves_existing_invariants(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CARD_MD)
            tmp_path = f.name

        try:
            append_invariant(
                card_path=tmp_path,
                expression="new_invariant > 0",
                explanation="New invariant",
            )
            content = open(tmp_path, encoding="utf-8").read()
            # Original invariants still present
            assert "INV-001" in content
            assert "INV-002" in content
            assert "new_invariant > 0" in content
        finally:
            os.unlink(tmp_path)

    def test_preserves_markdown_body(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CARD_MD)
            tmp_path = f.name

        try:
            append_invariant(
                card_path=tmp_path,
                expression="z > 0",
                explanation="test",
            )
            content = open(tmp_path, encoding="utf-8").read()
            assert "## Intent" in content
            assert "Process payments securely." in content
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file_returns_error(self):
        result = append_invariant(
            card_path="/nonexistent/file.card.md",
            expression="x > 0",
            explanation="test",
        )
        assert result.success is False
        assert result.error is not None

    def test_includes_origin_metadata(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CARD_MD)
            tmp_path = f.name

        try:
            result = append_invariant(
                card_path=tmp_path,
                expression="result != None",
                explanation="Never returns None",
                origin_failure_id="ERR-042",
                verification_method="hypothesis",
            )
            assert result.success is True
            content = open(tmp_path, encoding="utf-8").read()
            assert "ERR-042" in content
        finally:
            os.unlink(tmp_path)

    def test_card_md_with_no_invariants_block(self):
        """Should handle a .card.md that has no invariants yet."""
        card_no_inv = """\
---
card-version: "1.0"
id: minimal
title: Minimal Module
status: draft
---

## Intent

Minimal test.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(card_no_inv)
            tmp_path = f.name

        try:
            result = append_invariant(
                card_path=tmp_path,
                expression="result > 0",
                explanation="Positive result",
            )
            assert result.success is True
            content = open(tmp_path, encoding="utf-8").read()
            assert "result > 0" in content
            assert "invariants:" in content
        finally:
            os.unlink(tmp_path)
