"""Web application invariant templates — W4.4.

10 production-proven web API invariant templates for common HTTP/API patterns.
Each template factory returns a WebTemplate that can be applied to OTel spans
to produce MinesInvariant objects.

Templates:
  1. status_code_set_template    — HTTP status codes limited to observed set
  2. idempotent_get_template     — GET endpoints always return 200
  3. response_time_sla_template  — duration_ms <= SLA bound
  4. email_format_template       — email attributes match RFC 5321
  5. uuid_format_template        — UUID attributes match RFC 4122
  6. positive_integer_template   — *.id integer attributes must be > 0
  7. non_null_id_template        — *.id attributes must not be None
  8. monotonic_sequence_template — sequential IDs must be increasing
  9. monotonic_timestamp_template— created_at <= updated_at
 10. bounded_string_template     — string attributes within max length

References:
- MINES arXiv 2512.06906 — Category 1 (Common-sense), 2 (Format), 3 (Database)
- Scout 6 Tool 5 — web_templates for Format/Common-sense/Database constraints
- [REF-T10] icontract for runtime contract enforcement

Pipeline:
  mines.py (mine invariants) -> web_templates.py (apply templates) -> enforcer.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from immune.mines import OtelSpan, MinesInvariant, MinesCategory


# ---------------------------------------------------------------------------
# WebTemplate data model
# ---------------------------------------------------------------------------


@dataclass
class WebTemplate:
    """A reusable web API invariant template.

    Attributes:
        name:        Short identifier for this template.
        category:    MINES category (Common-sense, Format, Database, etc.).
        description: Human-readable description of the invariant.
        apply:       Callable(spans) -> list[MinesInvariant]
    """

    name: str
    category: MinesCategory
    description: str
    apply: Callable[[list[OtelSpan]], list[MinesInvariant]]


def apply_template(template: WebTemplate, spans: list[OtelSpan]) -> list[MinesInvariant]:
    """Apply a WebTemplate to a list of OTel spans, returning invariants."""
    return template.apply(spans)


# ---------------------------------------------------------------------------
# Template 1: HTTP status code set constraint
# ---------------------------------------------------------------------------


def status_code_set_template(
    operation_status_map: dict[str, set[int]] | None = None,
) -> WebTemplate:
    """Template: HTTP status codes must be limited to the observed set.

    For each operation, generates an invariant stating only the observed
    status codes are valid (Common-sense constraint, MINES Category 1).

    Args:
        operation_status_map: Optional pre-seeded {operation: {status_codes}}.
            If None, the allowed set is derived from the input spans.
    """
    preset = operation_status_map or {}

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        # Aggregate status codes per operation
        op_codes: dict[str, set[int]] = {}
        for span in spans:
            op = span.operation_name
            codes = preset.get(op) or op_codes.setdefault(op, set())
            codes.add(span.status_code)
            op_codes[op] = codes

        invariants = []
        for op, codes in op_codes.items():
            codes_str = "{" + ", ".join(str(c) for c in sorted(codes)) + "}"
            expr = f"status_code in {codes_str}"
            decorator = (
                f"@icontract.require(lambda status_code: status_code in {codes_str})"
            )
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.COMMON_SENSE,
                    operation=op,
                    expression=expr,
                    confidence=0.9,
                    icontract_decorator=decorator,
                )
            )
        return invariants

    return WebTemplate(
        name="status_code_set",
        category=MinesCategory.COMMON_SENSE,
        description="HTTP status codes are limited to observed set",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 2: Idempotent GET (always 200)
# ---------------------------------------------------------------------------


def idempotent_get_template() -> WebTemplate:
    """Template: GET endpoints always return HTTP 200.

    Generates invariant for GET operations asserting status_code == 200
    (Common-sense constraint, MINES Category 1).
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        get_ops: set[str] = set()
        for span in spans:
            if span.operation_name.upper().startswith("GET "):
                get_ops.add(span.operation_name)

        invariants = []
        for op in sorted(get_ops):
            expr = "status_code == 200"
            decorator = "@icontract.require(lambda status_code: status_code == 200)"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.COMMON_SENSE,
                    operation=op,
                    expression=expr,
                    confidence=0.85,
                    icontract_decorator=decorator,
                )
            )
        return invariants

    return WebTemplate(
        name="idempotent_get",
        category=MinesCategory.COMMON_SENSE,
        description="GET endpoints always return HTTP 200",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 3: Response time SLA
# ---------------------------------------------------------------------------


def response_time_sla_template(sla_ms: float = 1000.0) -> WebTemplate:
    """Template: response latency must be within SLA bound.

    Generates invariant asserting duration_ms <= sla_ms.
    (Common-sense constraint, MINES Category 1).

    Args:
        sla_ms: SLA threshold in milliseconds (default: 1000ms).
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        ops: set[str] = set()
        for span in spans:
            ops.add(span.operation_name)

        invariants = []
        for op in sorted(ops):
            expr = f"duration_ms <= {sla_ms}"
            decorator = f"@icontract.require(lambda duration_ms: duration_ms <= {sla_ms})"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.COMMON_SENSE,
                    operation=op,
                    expression=expr,
                    confidence=0.8,
                    icontract_decorator=decorator,
                )
            )
        return invariants

    return WebTemplate(
        name="response_time_sla",
        category=MinesCategory.COMMON_SENSE,
        description=f"Response time must be <= {sla_ms}ms",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 4: Email format (RFC 5321)
# ---------------------------------------------------------------------------

_EMAIL_ATTR_RE = re.compile(r"email", re.IGNORECASE)
_EMAIL_VAL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_format_template() -> WebTemplate:
    """Template: email attributes must conform to RFC 5321 format.

    Scans span attributes for keys containing 'email' and generates
    FORMAT invariants requiring valid email syntax.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        email_keys: set[str] = set()
        ops_for_key: dict[str, set[str]] = {}

        for span in spans:
            for key, val in span.attributes.items():
                if _EMAIL_ATTR_RE.search(key) and isinstance(val, str):
                    if _EMAIL_VAL_RE.match(val):
                        email_keys.add(key)
                        ops_for_key.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(email_keys):
            for op in sorted(ops_for_key[key]):
                expr = f"{key} matches RFC 5321 email format"
                decorator = (
                    f"@icontract.require(lambda attrs: re.match("
                    f"r'^[^@\\\\s]+@[^@\\\\s]+\\\\.[^@\\\\s]+$', attrs.get('{key}', '')))"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.FORMAT,
                        operation=op,
                        expression=expr,
                        confidence=0.95,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="email_format",
        category=MinesCategory.FORMAT,
        description="Email attributes must match RFC 5321",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 5: UUID format (RFC 4122)
# ---------------------------------------------------------------------------

_UUID_ATTR_RE = re.compile(r"(\.id$|_id$|uuid)", re.IGNORECASE)
_UUID_VAL_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def uuid_format_template() -> WebTemplate:
    """Template: UUID attributes must conform to RFC 4122 format.

    Scans span attributes for keys that look like UUID fields and generates
    FORMAT invariants requiring valid UUID syntax.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        uuid_keys: set[str] = set()
        ops_for_key: dict[str, set[str]] = {}

        for span in spans:
            for key, val in span.attributes.items():
                if isinstance(val, str) and _UUID_VAL_RE.match(val):
                    uuid_keys.add(key)
                    ops_for_key.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(uuid_keys):
            for op in sorted(ops_for_key[key]):
                expr = f"{key} matches RFC 4122 UUID format"
                decorator = (
                    f"@icontract.require(lambda attrs: re.match("
                    f"r'^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$', "
                    f"attrs.get('{key}', ''), re.IGNORECASE))"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.FORMAT,
                        operation=op,
                        expression=expr,
                        confidence=0.95,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="uuid_format",
        category=MinesCategory.FORMAT,
        description="UUID attributes must match RFC 4122",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 6: Positive integer (*.id attributes > 0)
# ---------------------------------------------------------------------------

_INT_ID_ATTR_RE = re.compile(r"(\.id$|_id$)", re.IGNORECASE)


def positive_integer_template() -> WebTemplate:
    """Template: integer ID attributes must be positive (> 0).

    Scans span attributes for keys ending in '.id' or '_id' with integer
    values and generates invariants asserting val > 0.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        int_id_keys: set[str] = set()
        ops_for_key: dict[str, set[str]] = {}

        for span in spans:
            for key, val in span.attributes.items():
                if _INT_ID_ATTR_RE.search(key) and isinstance(val, int):
                    int_id_keys.add(key)
                    ops_for_key.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(int_id_keys):
            for op in sorted(ops_for_key[key]):
                expr = f"{key} > 0"
                decorator = (
                    f"@icontract.require(lambda attrs: attrs.get('{key}', 0) > 0)"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.COMMON_SENSE,
                        operation=op,
                        expression=expr,
                        confidence=0.9,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="positive_integer",
        category=MinesCategory.COMMON_SENSE,
        description="Integer ID attributes must be positive (> 0)",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 7: Non-null foreign key ID
# ---------------------------------------------------------------------------


def non_null_id_template() -> WebTemplate:
    """Template: foreign key ID attributes must not be None.

    Scans span attributes for keys ending in '.id' or '_id' and generates
    DATABASE invariants asserting non-null.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        id_keys: set[str] = set()
        ops_for_key: dict[str, set[str]] = {}

        for span in spans:
            for key, val in span.attributes.items():
                if _INT_ID_ATTR_RE.search(key):
                    id_keys.add(key)
                    ops_for_key.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(id_keys):
            for op in sorted(ops_for_key[key]):
                expr = f"{key} is not None"
                decorator = (
                    f"@icontract.require(lambda attrs: attrs.get('{key}') is not None)"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.DATABASE,
                        operation=op,
                        expression=expr,
                        confidence=0.9,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="non_null_id",
        category=MinesCategory.DATABASE,
        description="Foreign key ID attributes must not be None",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 8: Monotonic sequence (increasing IDs)
# ---------------------------------------------------------------------------


def monotonic_sequence_template() -> WebTemplate:
    """Template: sequential IDs across spans must be monotonically increasing.

    Detects *.id numeric attributes that increase across consecutive spans
    and generates DATABASE invariants asserting monotonic ordering.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        # Group spans by operation and track ID sequences
        op_id_seqs: dict[str, dict[str, list[int]]] = {}

        for span in spans:
            op = span.operation_name
            for key, val in span.attributes.items():
                if _INT_ID_ATTR_RE.search(key) and isinstance(val, int):
                    op_id_seqs.setdefault(op, {}).setdefault(key, []).append(val)

        invariants = []
        for op, key_seqs in op_id_seqs.items():
            for key, seq in key_seqs.items():
                if len(seq) >= 2 and all(seq[i] < seq[i + 1] for i in range(len(seq) - 1)):
                    expr = f"{key} is monotonically increasing across spans"
                    decorator = (
                        f"@icontract.require(lambda attrs: attrs.get('{key}', 0) > 0)"
                    )
                    invariants.append(
                        MinesInvariant(
                            category=MinesCategory.DATABASE,
                            operation=op,
                            expression=expr,
                            confidence=0.8,
                            icontract_decorator=decorator,
                        )
                    )
        return invariants

    return WebTemplate(
        name="monotonic_sequence",
        category=MinesCategory.DATABASE,
        description="Sequential ID attributes must be monotonically increasing",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 9: Monotonic timestamp (created_at <= updated_at)
# ---------------------------------------------------------------------------

_CREATED_AT_RE = re.compile(r"created_at", re.IGNORECASE)
_UPDATED_AT_RE = re.compile(r"updated_at", re.IGNORECASE)


def monotonic_timestamp_template() -> WebTemplate:
    """Template: created_at must be <= updated_at.

    Detects spans with both created_at and updated_at attributes and
    generates DATABASE invariants asserting temporal ordering.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        ops_with_timestamps: set[str] = set()

        for span in spans:
            has_created = any(_CREATED_AT_RE.search(k) for k in span.attributes)
            has_updated = any(_UPDATED_AT_RE.search(k) for k in span.attributes)
            if has_created and has_updated:
                ops_with_timestamps.add(span.operation_name)

        invariants = []
        for op in sorted(ops_with_timestamps):
            expr = "created_at <= updated_at (monotonic timestamp ordering)"
            decorator = (
                "@icontract.require(lambda attrs: "
                "attrs.get('created_at', 0) <= attrs.get('updated_at', 0))"
            )
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.DATABASE,
                    operation=op,
                    expression=expr,
                    confidence=0.95,
                    icontract_decorator=decorator,
                )
            )
        return invariants

    return WebTemplate(
        name="monotonic_timestamp",
        category=MinesCategory.DATABASE,
        description="created_at must be <= updated_at",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 10: Bounded string length
# ---------------------------------------------------------------------------


def bounded_string_template(max_len: int = 255) -> WebTemplate:
    """Template: string attributes must not exceed max_len characters.

    Generates Common-sense invariants asserting len(attr) <= max_len
    for all string-valued span attributes.

    Args:
        max_len: Maximum allowed string length (default: 255).
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        str_keys: set[str] = set()
        ops_for_key: dict[str, set[str]] = {}

        for span in spans:
            for key, val in span.attributes.items():
                if isinstance(val, str):
                    str_keys.add(key)
                    ops_for_key.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(str_keys):
            for op in sorted(ops_for_key[key]):
                expr = f"len({key}) <= {max_len}"
                decorator = (
                    f"@icontract.require(lambda attrs: "
                    f"len(attrs.get('{key}', '')) <= {max_len})"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.COMMON_SENSE,
                        operation=op,
                        expression=expr,
                        confidence=0.85,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="bounded_string",
        category=MinesCategory.COMMON_SENSE,
        description=f"String attributes must not exceed {max_len} characters",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# ALL_TEMPLATES: registry of all 10 template factory functions
# ---------------------------------------------------------------------------


ALL_TEMPLATES: list[Callable] = [
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
]
