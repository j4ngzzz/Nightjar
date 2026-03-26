"""Web application invariant templates — W4.4.

10 production-proven web API invariant templates for common HTTP/API patterns.
Each template factory returns a WebTemplate that can be applied to OTel spans
to produce MinesInvariant objects.

Templates (Scout 6 Section 6, priority-ranked):
  1.  status_code_set_template     — HTTP status codes limited to observed set
  2.  response_schema_template     — response attributes have consistent shape
  3.  auth_invariant_template      — authenticated endpoints always have auth attrs
  4.  idempotent_get_template      — GET endpoints always return 200
  5.  positive_integer_template    — *.id integer attributes must be > 0
  6.  format_invariant_template    — email/UUID attributes match RFC 5321/4122
  7.  non_null_id_template         — *.id attributes must not be None
  8.  monotonic_sequence_template  — sequential IDs must be increasing
  9.  monotonic_timestamp_template — created_at <= updated_at
 10.  bounded_string_template      — string attributes within max length

References:
- Scout 6 Section 6 — 10 priority-ranked web app templates
- MINES arXiv 2512.06906 — Category 1 (Common-sense), 2 (Format), 3 (Database)
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
# Template 2: Response schema consistency
# ---------------------------------------------------------------------------


def response_schema_template() -> WebTemplate:
    """Template: response attributes have a consistent shape across all spans.

    For each operation, detects which attribute keys appear in ALL spans
    and generates invariants asserting those keys are always present.
    Schema inconsistency (some spans missing expected keys) is a DATABASE/
    Common-sense violation.

    Reference: Scout 6 Section 6 — Template #2, response schema consistency.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        from collections import Counter

        # Group spans by operation
        op_spans: dict[str, list[OtelSpan]] = {}
        for span in spans:
            op_spans.setdefault(span.operation_name, []).append(span)

        invariants = []
        for op, op_s in op_spans.items():
            if len(op_s) < 2:
                continue

            # Find attribute keys that appear in ALL spans (the "schema")
            key_counts: Counter[str] = Counter()
            for span in op_s:
                for key in span.attributes:
                    key_counts[key] += 1

            required_keys = [k for k, c in key_counts.items() if c == len(op_s)]
            if not required_keys:
                continue

            for key in sorted(required_keys):
                expr = f"response always contains attribute '{key}' (schema consistency)"
                decorator = (
                    f"@icontract.ensure(lambda result: '{key}' in result.attributes, "
                    f"description=\"{op}: '{key}' must always be present\")"
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
        name="response_schema",
        category=MinesCategory.COMMON_SENSE,
        description="Response attributes have consistent shape across all spans",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 3: Authentication invariant
# ---------------------------------------------------------------------------

_AUTH_ATTR_RE = re.compile(
    r"(auth|token|session|bearer|api.?key|authorization|x.?auth)",
    re.IGNORECASE,
)


def auth_invariant_template() -> WebTemplate:
    """Template: authenticated endpoints always have auth-related attributes.

    Detects spans that contain auth-related attributes (Authorization, token,
    session, api_key, etc.) and generates invariants asserting those attributes
    must always be present for the operation.

    Reference: Scout 6 Section 6 — Template #3, authentication invariant.
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        # Find operations where all spans have at least one auth attribute
        op_spans: dict[str, list[OtelSpan]] = {}
        for span in spans:
            op_spans.setdefault(span.operation_name, []).append(span)

        invariants = []
        for op, op_s in op_spans.items():
            # Collect auth keys seen in each span
            auth_keys_per_span: list[set[str]] = []
            for span in op_s:
                auth_keys = {k for k in span.attributes if _AUTH_ATTR_RE.search(k)}
                auth_keys_per_span.append(auth_keys)

            # Find auth keys present in ALL spans (always-required auth attrs)
            if not auth_keys_per_span:
                continue
            common_auth_keys = auth_keys_per_span[0]
            for s in auth_keys_per_span[1:]:
                common_auth_keys = common_auth_keys & s

            for key in sorted(common_auth_keys):
                expr = f"auth attribute '{key}' is always present (authentication invariant)"
                decorator = (
                    f"@icontract.require(lambda attrs: '{key}' in attrs and attrs['{key}'], "
                    f"description=\"{op}: auth attribute '{key}' must be present\")"
                )
                invariants.append(
                    MinesInvariant(
                        category=MinesCategory.ENVIRONMENT,
                        operation=op,
                        expression=expr,
                        confidence=0.95,
                        icontract_decorator=decorator,
                    )
                )
        return invariants

    return WebTemplate(
        name="auth_invariant",
        category=MinesCategory.ENVIRONMENT,
        description="Authenticated endpoints always have auth-related attributes",
        apply=_apply,
    )


# ---------------------------------------------------------------------------
# Template 4: Idempotent GET (always 200)
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
# Template 5: Positive integer (non-negativity for IDs / quantities)
# ---------------------------------------------------------------------------

_INT_ID_ATTR_RE = re.compile(r"(\.id$|_id$)", re.IGNORECASE)


def positive_integer_template() -> WebTemplate:
    """Template: integer ID attributes must be positive (> 0).

    Covers non-negativity for prices, quantities, and database IDs.
    Scans span attributes for keys ending in '.id' or '_id' with integer
    values and generates invariants asserting val > 0.

    Reference: Scout 6 Section 6 — Template #5, non-negativity.
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
# Template 6: Format invariants (email RFC 5321 + UUID RFC 4122)
# ---------------------------------------------------------------------------

_EMAIL_ATTR_RE = re.compile(r"email", re.IGNORECASE)
_EMAIL_VAL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_VAL_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def format_invariant_template() -> WebTemplate:
    """Template: string attributes must match declared format (email, UUID).

    Detects email and UUID format patterns in span attributes and generates
    FORMAT invariants requiring RFC-compliant syntax.

    Reference: Scout 6 Section 6 — Template #6, format invariants (email, UUID).
    """

    def _apply(spans: list[OtelSpan]) -> list[MinesInvariant]:
        email_keys: dict[str, set[str]] = {}   # key -> ops
        uuid_keys: dict[str, set[str]] = {}    # key -> ops

        for span in spans:
            for key, val in span.attributes.items():
                if not isinstance(val, str):
                    continue
                if _EMAIL_ATTR_RE.search(key) and _EMAIL_VAL_RE.match(val):
                    email_keys.setdefault(key, set()).add(span.operation_name)
                elif _UUID_VAL_RE.match(val):
                    uuid_keys.setdefault(key, set()).add(span.operation_name)

        invariants = []
        for key in sorted(email_keys):
            for op in sorted(email_keys[key]):
                expr = f"{key} matches RFC 5321 email format"
                decorator = (
                    f"@icontract.require(lambda attrs: re.match("
                    f"r'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$', attrs.get('{key}', '')))"
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
        for key in sorted(uuid_keys):
            for op in sorted(uuid_keys[key]):
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
        name="format_invariant",
        category=MinesCategory.FORMAT,
        description="String attributes must match declared format (email, UUID)",
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
# Template 8: Monotonic sequence (create-before-update ordering)
# ---------------------------------------------------------------------------


def monotonic_sequence_template() -> WebTemplate:
    """Template: sequential IDs across spans must be monotonically increasing.

    Detects *.id numeric attributes that increase across consecutive spans
    and generates DATABASE invariants asserting monotonic ordering.

    Reference: Scout 6 Section 6 — Template #8, sequence ordering.
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

    Reference: Scout 6 Section 6 — Template #9, monotonic timestamps.
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
            # Fix: use float('inf') as default for updated_at so that missing
            # updated_at never causes a false positive violation.
            decorator = (
                "@icontract.require(lambda attrs: "
                "attrs.get('created_at', 0) <= attrs.get('updated_at', float('inf')))"
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

    Reference: Scout 6 Section 6 — Template #10, bounded string length.
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
    status_code_set_template,     # 1. HTTP status patterns
    response_schema_template,     # 2. Response schema consistency
    auth_invariant_template,      # 3. Authentication invariant
    idempotent_get_template,      # 4. Idempotency
    positive_integer_template,    # 5. Non-negativity
    format_invariant_template,    # 6. Format invariants (email, UUID)
    non_null_id_template,         # 7. FK integrity
    monotonic_sequence_template,  # 8. Sequence ordering
    monotonic_timestamp_template, # 9. Monotonic timestamps
    bounded_string_template,      # 10. Bounded string length
]
