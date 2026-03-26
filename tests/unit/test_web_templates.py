"""Tests for web application invariant templates.

Validates W4.4: 10 web application invariant templates from Scout 6 Section 6.

Templates (priority-ranked):
  1. HTTP status code patterns
  2. Response schema consistency
  3. Authentication invariant
  4. Idempotency
  5. Non-negativity
  6. Format invariants (email, UUID)
  7. FK integrity
  8. Sequence ordering
  9. Monotonic timestamps
 10. Bounded string length

References:
- Scout 6 Section 6 — priority-ranked web app templates
- MINES arXiv 2512.06906 — web API invariant categories
- [REF-T10] icontract for runtime contract enforcement
"""

from __future__ import annotations

import pytest

from immune.web_templates import (
    WebTemplate,
    apply_template,
    ALL_TEMPLATES,
    status_code_set_template,
    response_schema_template,
    auth_invariant_template,
    idempotent_get_template,
    positive_integer_template,
    format_invariant_template,
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
        """ALL_TEMPLATES contains exactly 10 template factories (Scout 6 S6)."""
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
# Test: Template 2 — Response schema consistency
# ---------------------------------------------------------------------------


class TestResponseSchemaTemplate:
    def test_response_schema_detects_consistent_keys(self):
        """Schema consistency: attributes present in ALL spans are required."""
        spans = [
            make_span("GET /users", attrs={"user.id": 1, "user.name": "Alice"}),
            make_span("GET /users", attrs={"user.id": 2, "user.name": "Bob"}),
        ]
        template = response_schema_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("schema" in inv.expression.lower() or "always" in inv.expression.lower() for inv in invs)

    def test_response_schema_skips_inconsistent_keys(self):
        """Keys NOT present in ALL spans are not marked as required."""
        spans = [
            make_span("GET /items", attrs={"item.id": 1, "item.name": "Widget"}),
            make_span("GET /items", attrs={"item.id": 2}),  # item.name missing
        ]
        template = response_schema_template()
        invs = apply_template(template, spans)
        # item.name is only in 1/2 spans — not a schema requirement
        assert not any("item.name" in inv.expression for inv in invs)

    def test_response_schema_category_is_common_sense(self):
        """Schema consistency invariants are Common-sense constraints."""
        template = response_schema_template()
        assert template.category == MinesCategory.COMMON_SENSE


# ---------------------------------------------------------------------------
# Test: Template 3 — Authentication invariant
# ---------------------------------------------------------------------------


class TestAuthInvariantTemplate:
    def test_auth_invariant_detects_auth_attribute(self):
        """Auth invariant: auth attributes always present in authenticated spans."""
        spans = [
            make_span("POST /orders", attrs={"Authorization": "Bearer abc", "user.id": 1}),
            make_span("POST /orders", attrs={"Authorization": "Bearer xyz", "user.id": 2}),
        ]
        template = auth_invariant_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any(
            "auth" in inv.expression.lower() or "Authorization" in inv.expression
            for inv in invs
        )

    def test_auth_invariant_skips_non_auth_spans(self):
        """Auth invariant not generated for spans without auth attributes."""
        spans = [make_span("GET /health", attrs={"status": "ok"})]
        template = auth_invariant_template()
        invs = apply_template(template, spans)
        assert len(invs) == 0

    def test_auth_invariant_category_is_environment(self):
        """Auth invariants belong to ENVIRONMENT category."""
        template = auth_invariant_template()
        assert template.category == MinesCategory.ENVIRONMENT


# ---------------------------------------------------------------------------
# Test: Template 4 — Idempotent GET
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
        assert any("200" in inv.expression for inv in invs)

    def test_idempotent_get_skips_non_get(self):
        """Idempotent GET template only applies to GET operations."""
        spans = [make_span("POST /users", status=201)]
        template = idempotent_get_template()
        invs = apply_template(template, spans)
        assert len(invs) == 0


# ---------------------------------------------------------------------------
# Test: Template 5 — Non-negativity / positive integer
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
        assert len(invs) == 0


# ---------------------------------------------------------------------------
# Test: Template 6 — Format invariants (email + UUID)
# ---------------------------------------------------------------------------


class TestFormatInvariantTemplate:
    def test_format_invariant_detects_email_attribute(self):
        """Format invariant: email attributes must match RFC 5321."""
        spans = [
            make_span("POST /users", attrs={"user.email": "test@example.com"}),
            make_span("POST /users", attrs={"user.email": "jane@test.org"}),
        ]
        template = format_invariant_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("email" in inv.expression.lower() or "RFC" in inv.expression for inv in invs)

    def test_format_invariant_detects_uuid_attribute(self):
        """Format invariant: UUID attributes must match RFC 4122."""
        spans = [
            make_span("GET /orders/1", attrs={"order.id": "550e8400-e29b-41d4-a716-446655440000"}),
            make_span("GET /orders/2", attrs={"order.id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"}),
        ]
        template = format_invariant_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        assert any("uuid" in inv.expression.lower() or "UUID" in inv.expression or "RFC 4122" in inv.expression for inv in invs)

    def test_format_invariant_category_is_format(self):
        """Format invariants belong to FORMAT category."""
        template = format_invariant_template()
        assert template.category == MinesCategory.FORMAT


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

    def test_monotonic_timestamp_decorator_uses_inf_default(self):
        """Decorator uses float('inf') for missing updated_at to avoid false violations."""
        spans = [make_span("GET /r", attrs={"created_at": 1000, "updated_at": 2000})]
        template = monotonic_timestamp_template()
        invs = apply_template(template, spans)
        assert len(invs) > 0
        # Decorator must not default updated_at to 0 (which causes false positives)
        assert "float('inf')" in invs[0].icontract_decorator or "inf" in invs[0].icontract_decorator

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
        assert len(invs) == 0

    def test_bounded_string_category_is_common_sense(self):
        """Bounded string invariants are Common-sense constraints."""
        template = bounded_string_template(max_len=100)
        assert template.category == MinesCategory.COMMON_SENSE
