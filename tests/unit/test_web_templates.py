"""Tests for web application invariant templates.

Validates CR-06 / W4.4: 10 web application invariant templates for common
HTTP/API patterns discovered in production traces.

Templates cover:
  1. HTTP status code set constraint
  2. Idempotent GET (status code 200 always)
  3. Response time SLA (bounded latency)
  4. Email format in attributes
  5. UUID format in attributes
  6. Positive integer (e.g., user.id > 0)
  7. Foreign key referential integrity (non-null linked ID)
  8. Sequence ordering (monotonic IDs)
  9. Monotonic timestamps (created_at <= updated_at)
 10. Bounded string length

References:
- MINES arXiv 2512.06906 — web API invariant categories
- Scout 6 Tool 5 — web_templates for Format/Common-sense/Database constraints
- [REF-T10] icontract for runtime contract enforcement
"""

from __future__ import annotations

import pytest

from immune.web_templates import (
    WebTemplate,
    apply_template,
    ALL_TEMPLATES,
    # Individual template factory functions
    status_code_set_template,
    idempotent_get_template,
    response_time_sla_template,
    email_format_template,
    uuid_format_template,
    positive_integer_template,
    non_null_id_template,
    monotonic_sequence_template,
    monotonic_timestamp_template,
    bounded_string_template,
)
from immune.mines import OtelSpan, MinesInvariant, MinesCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_span(
    op: str,
    status: int = 200,
    duration_ms: float = 50.0,
    attrs: dict | None = None,
) -> OtelSpan:
    return OtelSpan(
        operation_name=op,
        attributes=attrs or {},
        status_code=status,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Test: WebTemplate data model
# ---------------------------------------------------------------------------


class TestWebTemplate:
    def test_web_template_construction(self):
        """WebTemplate has name, category, and description."""
        t = status_code_set_template({"GET /health": {200}})
        assert isinstance(t, WebTemplate)
        assert t.name != ""
        assert t.category in MinesCategory.__members__.values()
        assert t.description != ""

    def test_all_templates_list_has_10_entries(self):
        """ALL_TEMPLATES contains all 10 web template factories."""
        assert len(ALL_TEMPLATES) == 10, (
            f"Expected 10 templates, got {len(ALL_TEMPLATES)}: "
            f"{[t.__name__ for t in ALL_TEMPLATES]}"
        )


# ---------------------------------------------------------------------------
# Test: Template 1 — HTTP status code set constraint
# ---------------------------------------------------------------------------


class TestStatusCodeSetTemplate:
    def test_status_code_set_matches_observed(self):
        """Status code set invariant: only observed codes are valid."""
        spans = [
            make_span("POST /login", status=200),
            make_span("POST /login", status=401),
            make_span("POST /login", status=200),
        ]
        template = status_code_set_template({"POST /login": {200, 401}})
        invs = apply_template(template, spans)

        assert len(invs) > 0
        for inv in invs:
            assert isinstance(inv, MinesInvariant)
            assert "200" in inv.expression or "401" in inv.expression or "status" in inv.expression.lower()

    def test_status_code_set_icontract_format(self):
        """Status set invariant produces valid @icontract decorator."""
        template = status_code_set_template({"GET /items": {200, 404}})
        spans = [make_span("GET /items", status=200)]
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("@icontract" in inv.icontract_decorator for inv in invs)


# ---------------------------------------------------------------------------
# Test: Template 2 — Idempotent GET
# ---------------------------------------------------------------------------


class TestIdempotentGetTemplate:
    def test_idempotent_get_always_200(self):
        """GET endpoints should always return 200."""
        spans = [
            make_span("GET /users/1", status=200),
            make_span("GET /users/2", status=200),
        ]
        template = idempotent_get_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        # Should produce invariant asserting status_code == 200 for GET
        assert any("200" in inv.expression for inv in invs)

    def test_idempotent_get_skips_non_get(self):
        """Idempotent GET template only applies to GET operations."""
        spans = [make_span("POST /users", status=201)]
        template = idempotent_get_template()
        invs = apply_template(template, spans)
        # POST spans: no GET-idempotency invariants generated
        assert len(invs) == 0


# ---------------------------------------------------------------------------
# Test: Template 3 — Response time SLA
# ---------------------------------------------------------------------------


class TestResponseTimeSlaTemplate:
    def test_response_time_sla_produces_bound(self):
        """Response time SLA: duration_ms should be bounded."""
        spans = [
            make_span("GET /health", duration_ms=10.0),
            make_span("GET /health", duration_ms=25.0),
            make_span("GET /health", duration_ms=15.0),
        ]
        template = response_time_sla_template(sla_ms=1000.0)
        invs = apply_template(template, spans)
        assert len(invs) > 0
        # Invariant expression should reference duration
        assert any("duration" in inv.expression.lower() for inv in invs)

    def test_response_time_sla_category_is_common_sense(self):
        """SLA invariants are Common-sense constraints."""
        template = response_time_sla_template(sla_ms=500.0)
        assert template.category == MinesCategory.COMMON_SENSE


# ---------------------------------------------------------------------------
# Test: Template 4 — Email format
# ---------------------------------------------------------------------------


class TestEmailFormatTemplate:
    def test_email_format_detects_email_attribute(self):
        """Email format: attribute matching email pattern must be RFC 5321."""
        spans = [
            make_span("POST /users", attrs={"user.email": "test@example.com"}),
            make_span("POST /users", attrs={"user.email": "jane@test.org"}),
        ]
        template = email_format_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("email" in inv.expression.lower() or "RFC" in inv.expression for inv in invs)

    def test_email_format_category_is_format(self):
        """Email format invariants belong to FORMAT category."""
        template = email_format_template()
        assert template.category == MinesCategory.FORMAT


# ---------------------------------------------------------------------------
# Test: Template 5 — UUID format
# ---------------------------------------------------------------------------


class TestUuidFormatTemplate:
    def test_uuid_format_detects_uuid_attribute(self):
        """UUID format: attribute matching UUID pattern must be RFC 4122."""
        spans = [
            make_span("GET /orders/1", attrs={"order.id": "550e8400-e29b-41d4-a716-446655440000"}),
            make_span("GET /orders/2", attrs={"order.id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"}),
        ]
        template = uuid_format_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("uuid" in inv.expression.lower() or "UUID" in inv.expression for inv in invs)

    def test_uuid_format_category_is_format(self):
        """UUID format invariants belong to FORMAT category."""
        template = uuid_format_template()
        assert template.category == MinesCategory.FORMAT


# ---------------------------------------------------------------------------
# Test: Template 6 — Positive integer
# ---------------------------------------------------------------------------


class TestPositiveIntegerTemplate:
    def test_positive_integer_detects_id_attribute(self):
        """Positive integer: attributes with numeric IDs must be > 0."""
        spans = [
            make_span("GET /users", attrs={"user.id": 5}),
            make_span("GET /users", attrs={"user.id": 12}),
        ]
        template = positive_integer_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("> 0" in inv.expression or ">= 1" in inv.expression or "positive" in inv.expression.lower() for inv in invs)

    def test_positive_integer_skips_non_id_attrs(self):
        """Positive integer template should not apply to non-numeric attributes."""
        spans = [
            make_span("GET /health", attrs={"status": "ok"}),
        ]
        template = positive_integer_template()
        invs = apply_template(template, spans)
        # "status": "ok" is a string — no positive integer invariant
        assert len(invs) == 0


# ---------------------------------------------------------------------------
# Test: Template 7 — Non-null foreign key ID
# ---------------------------------------------------------------------------


class TestNonNullIdTemplate:
    def test_non_null_id_detects_null_violation(self):
        """Non-null ID: linked IDs (*.id attributes) must be non-null."""
        spans = [
            make_span("POST /orders", attrs={"customer.id": 1, "product.id": 42}),
            make_span("POST /orders", attrs={"customer.id": 2, "product.id": 7}),
        ]
        template = non_null_id_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("None" in inv.expression or "null" in inv.expression.lower() or "not None" in inv.expression for inv in invs)

    def test_non_null_id_category_is_database(self):
        """Non-null ID invariants belong to DATABASE category."""
        template = non_null_id_template()
        assert template.category == MinesCategory.DATABASE


# ---------------------------------------------------------------------------
# Test: Template 8 — Monotonic sequence
# ---------------------------------------------------------------------------


class TestMonotonicSequenceTemplate:
    def test_monotonic_sequence_detects_increasing_ids(self):
        """Monotonic sequence: sequential IDs must be strictly increasing."""
        spans = [
            make_span("GET /events", attrs={"event.id": 1}),
            make_span("GET /events", attrs={"event.id": 2}),
            make_span("GET /events", attrs={"event.id": 3}),
        ]
        template = monotonic_sequence_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("monoton" in inv.expression.lower() or "increasing" in inv.expression.lower() or ">" in inv.expression for inv in invs)

    def test_monotonic_sequence_category_is_database(self):
        """Monotonic sequence invariants are DATABASE constraints."""
        template = monotonic_sequence_template()
        assert template.category == MinesCategory.DATABASE


# ---------------------------------------------------------------------------
# Test: Template 9 — Monotonic timestamp
# ---------------------------------------------------------------------------


class TestMonotonicTimestampTemplate:
    def test_monotonic_timestamp_detects_created_updated(self):
        """Monotonic timestamp: created_at <= updated_at."""
        spans = [
            make_span("GET /resource", attrs={"created_at": 1000, "updated_at": 2000}),
            make_span("GET /resource", attrs={"created_at": 1500, "updated_at": 1500}),
        ]
        template = monotonic_timestamp_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any(
            "created" in inv.expression.lower() or "updated" in inv.expression.lower() or "timestamp" in inv.expression.lower()
            for inv in invs
        )

    def test_monotonic_timestamp_category_is_database(self):
        """Monotonic timestamp invariants are DATABASE constraints."""
        template = monotonic_timestamp_template()
        assert template.category == MinesCategory.DATABASE


# ---------------------------------------------------------------------------
# Test: Template 10 — Bounded string length
# ---------------------------------------------------------------------------


class TestBoundedStringTemplate:
    def test_bounded_string_detects_string_attribute(self):
        """Bounded string: string attributes must not exceed max length."""
        spans = [
            make_span("POST /users", attrs={"user.name": "Alice"}),
            make_span("POST /users", attrs={"user.name": "Bob"}),
        ]
        template = bounded_string_template(max_len=255)
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("len" in inv.expression.lower() or "255" in inv.expression or "length" in inv.expression.lower() for inv in invs)

    def test_bounded_string_skips_non_string(self):
        """Bounded string template skips non-string attributes."""
        spans = [make_span("GET /users", attrs={"user.id": 42})]
        template = bounded_string_template(max_len=255)
        invs = apply_template(template, spans)
        # Integer attribute: no bounded-string invariant
        assert len(invs) == 0

    def test_bounded_string_category_is_common_sense(self):
        """Bounded string invariants are Common-sense constraints."""
        template = bounded_string_template(max_len=100)
        assert template.category == MinesCategory.COMMON_SENSE
