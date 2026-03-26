"""Tests for MINES web API invariant mining pipeline.

Validates CR-06: clean-room implementation based on:
  MINES: Mining API Invariants from Execution Logs.
  arXiv:2512.06906 (ICSE 2026).
  https://arxiv.org/abs/2512.06906

MINES mines invariants from OpenTelemetry (OTel) spans across 5 categories:
  1. Common-sense constraints
  2. Format constraints
  3. Database constraints
  4. Environment constraints
  5. Related API constraints

Pipeline: OTel spans -> LLM hypothesizes -> validate -> @icontract decorators

References:
- Scout 6 Tool 5 — MINES (arXiv 2512.06906, ICSE 2026)
- [REF-T10] icontract for runtime contract enforcement
- [REF-T16] litellm for model-agnostic LLM calls
"""

from __future__ import annotations

import pytest

from immune.mines import (
    OtelSpan,
    MinesInvariant,
    MinesCategory,
    mine_from_otel_spans,
    validate_invariants_against_spans,
    format_as_icontract,
)


# ---------------------------------------------------------------------------
# Helper: build OTel spans for testing
# ---------------------------------------------------------------------------


def make_span(
    operation: str,
    status_code: int = 200,
    duration_ms: float = 50.0,
    attrs: dict | None = None,
) -> OtelSpan:
    return OtelSpan(
        operation_name=operation,
        attributes=attrs or {},
        status_code=status_code,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Test: OtelSpan data model
# ---------------------------------------------------------------------------


class TestOtelSpan:
    def test_otel_span_construction(self):
        """OtelSpan can be constructed with required fields."""
        span = OtelSpan(
            operation_name="POST /login",
            attributes={"user.id": "123", "content-type": "application/json"},
            status_code=200,
            duration_ms=45.2,
        )
        assert span.operation_name == "POST /login"
        assert span.attributes["user.id"] == "123"
        assert span.status_code == 200
        assert span.duration_ms == 45.2

    def test_otel_span_minimal(self):
        """OtelSpan can be constructed with minimal attributes."""
        span = OtelSpan(
            operation_name="GET /health",
            attributes={},
            status_code=200,
            duration_ms=1.0,
        )
        assert span.operation_name == "GET /health"


# ---------------------------------------------------------------------------
# Test: MinesInvariant and MinesCategory
# ---------------------------------------------------------------------------


class TestMinesInvariant:
    def test_mines_invariant_construction(self):
        """MinesInvariant can be constructed with required fields."""
        inv = MinesInvariant(
            category=MinesCategory.COMMON_SENSE,
            operation="POST /login",
            expression="status_code in {200, 401}",
            confidence=0.95,
            icontract_decorator="@icontract.require(lambda status_code: status_code in {200, 401})",
        )
        assert inv.category == MinesCategory.COMMON_SENSE
        assert inv.operation == "POST /login"
        assert inv.confidence == 0.95

    def test_mines_category_enum(self):
        """MinesCategory enum has all 5 MINES categories."""
        assert hasattr(MinesCategory, "COMMON_SENSE")
        assert hasattr(MinesCategory, "FORMAT")
        assert hasattr(MinesCategory, "DATABASE")
        assert hasattr(MinesCategory, "ENVIRONMENT")
        assert hasattr(MinesCategory, "RELATED_API")


# ---------------------------------------------------------------------------
# Test: mine_from_otel_spans
# ---------------------------------------------------------------------------


class TestMineFromOtelSpans:
    """Core MINES pipeline: OTel spans -> invariant hypotheses."""

    def test_mines_generates_invariants_from_otel_spans(self):
        """mine_from_otel_spans produces MinesInvariant objects from span data.

        Reference: MINES arXiv 2512.06906 -- mining from execution logs.
        """
        spans = [
            make_span("POST /login", status_code=200),
            make_span("POST /login", status_code=401),
            make_span("POST /login", status_code=200),
            make_span("POST /login", status_code=401),
            make_span("POST /login", status_code=200),
        ]
        # Note: LLM is mocked via dry_run=True to avoid real API calls in tests
        invariants = mine_from_otel_spans(spans, dry_run=True)

        assert len(invariants) > 0, (
            "Expected at least one invariant mined from login endpoint spans"
        )
        # Each invariant must have required fields
        for inv in invariants:
            assert isinstance(inv, MinesInvariant)
            assert inv.category in MinesCategory.__members__.values()
            assert inv.operation != ""
            assert inv.expression != ""
            assert 0.0 <= inv.confidence <= 1.0

    def test_mines_empty_spans_returns_empty(self):
        """No spans -> no invariants."""
        invariants = mine_from_otel_spans([], dry_run=True)
        assert invariants == []

    def test_mines_generates_status_code_invariant(self):
        """MINES should detect common-sense HTTP status code patterns.

        POST /login only returning 200 or 401 is a common-sense constraint.
        Reference: MINES ICSE 2026 -- Category 1: Common-sense constraints.
        """
        spans = [
            make_span("POST /login", status_code=200),
            make_span("POST /login", status_code=401),
            make_span("POST /login", status_code=200),
            make_span("POST /login", status_code=200),
        ]
        invariants = mine_from_otel_spans(spans, dry_run=True)

        # Should detect that status_code is limited to {200, 401}
        status_invs = [
            i for i in invariants
            if "status" in i.expression.lower() or "200" in i.expression
        ]
        assert len(status_invs) > 0, (
            f"Expected status code invariant, got: {[i.expression for i in invariants]}"
        )


# ---------------------------------------------------------------------------
# Test: validate_invariants_against_spans
# ---------------------------------------------------------------------------


class TestValidateInvariants:
    """Validate mined invariants against healthy trace spans."""

    def test_mines_validates_against_healthy_traces(self):
        """Validation confirms invariants hold on the healthy trace set.

        Reference: MINES arXiv 2512.06906 -- validation step.
        """
        spans = [
            make_span("GET /items", status_code=200),
            make_span("GET /items", status_code=200),
            make_span("GET /items", status_code=200),
        ]
        # Manually create an invariant to validate
        inv = MinesInvariant(
            category=MinesCategory.COMMON_SENSE,
            operation="GET /items",
            expression="status_code == 200",
            confidence=0.9,
            icontract_decorator="@icontract.require(lambda status_code: status_code == 200)",
        )

        # Invariant should PASS validation (all spans have status 200)
        valid = validate_invariants_against_spans([inv], spans)
        assert len(valid) > 0, "Expected invariant to pass validation"

    def test_mines_rejects_violated_invariant(self):
        """Invariant that fails on validation spans should be rejected."""
        spans = [
            make_span("GET /items", status_code=200),
            make_span("GET /items", status_code=404),  # violates status_code==200
        ]
        inv = MinesInvariant(
            category=MinesCategory.COMMON_SENSE,
            operation="GET /items",
            expression="status_code == 200",
            confidence=0.9,
            icontract_decorator="@icontract.require(lambda status_code: status_code == 200)",
        )
        valid = validate_invariants_against_spans([inv], spans)
        assert len(valid) == 0, (
            "Expected invariant rejected (404 violates status_code==200)"
        )


# ---------------------------------------------------------------------------
# Test: format_as_icontract
# ---------------------------------------------------------------------------


class TestFormatAsIcontract:
    """Generated invariants must produce valid @icontract decorator strings."""

    def test_format_as_icontract_produces_decorator(self):
        """format_as_icontract returns a valid @icontract.require string."""
        inv = MinesInvariant(
            category=MinesCategory.FORMAT,
            operation="POST /users",
            expression="email matches RFC 5321",
            confidence=0.8,
            icontract_decorator="",
        )
        decorated = format_as_icontract(inv)
        assert "@icontract" in decorated, (
            f"Expected @icontract in decorator, got: {decorated}"
        )
        assert "require" in decorated or "ensure" in decorated, (
            f"Expected require or ensure in decorator, got: {decorated}"
        )
