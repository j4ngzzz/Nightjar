"""MINES web API invariant mining pipeline — clean-room implementation.

Implements the MINES approach from:
  MINES: Mining API Invariants from Execution Logs (ICSE 2026).
  arXiv:2512.06906. https://arxiv.org/abs/2512.06906

Scout 6 Tool 5 summary: "High recall, near-zero false positives" on 5 benchmarks.
5 invariant categories for web APIs:
  1. Common-sense constraints  -- e.g., POST /login returns 200 or 401
  2. Format constraints        -- e.g., email matches RFC 5321 pattern
  3. Database constraints      -- e.g., user_id is always a positive integer
  4. Environment constraints   -- e.g., response time < 500ms during business hours
  5. Related API constraints   -- e.g., DELETE /resource always follows POST /resource

Pipeline:
  OTel spans -> pattern detection -> LLM hypothesis -> validate -> @icontract decorators

LLM hypothesis step uses litellm (model-agnostic, NIGHTJAR_MODEL env var).
In dry_run mode, skips LLM and uses deterministic pattern detection only.

Clean-room CR-06: Implements from arXiv 2512.06906 MINES paper. No existing
MINES code consulted.

References:
- MINES arXiv 2512.06906 (ICSE 2026) -- algorithm and 5 categories
- Scout 6 Tool 5 -- MINES recommendation
- [REF-T10] icontract -- runtime contract enforcement target
- [REF-T16] litellm -- model-agnostic LLM calls
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nightjar.config import DEFAULT_MODEL

try:
    import litellm  # type: ignore[import]
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OtelSpan:
    """An OpenTelemetry span representing one API call observation.

    Attributes:
        operation_name: e.g. "POST /login", "GET /items/42"
        attributes:     Key-value pairs from span attributes (headers, params, etc.)
        status_code:    HTTP response status code
        duration_ms:    Request duration in milliseconds
    """

    operation_name: str
    attributes: dict[str, Any]
    status_code: int
    duration_ms: float


class MinesCategory(str, Enum):
    """The 5 MINES invariant categories (arXiv 2512.06906 Section 3.2).

    Each category captures a different aspect of API behavior patterns.
    """

    COMMON_SENSE = "common_sense"     # HTTP status codes, response shapes
    FORMAT = "format"                  # email, UUID, date format patterns
    DATABASE = "database"              # FK integrity, uniqueness, non-null
    ENVIRONMENT = "environment"        # latency, rate limits, time-based patterns
    RELATED_API = "related_api"        # sequencing: create before use before delete


@dataclass
class MinesInvariant:
    """A single invariant mined by MINES from OTel spans.

    Attributes:
        category:            MINES invariant category
        operation:           API operation this invariant applies to
        expression:          Human-readable invariant expression
        confidence:          Confidence score [0.0, 1.0] from validation
        icontract_decorator: Ready-to-use @icontract decorator string
    """

    category: MinesCategory
    operation: str
    expression: str
    confidence: float
    icontract_decorator: str


# ---------------------------------------------------------------------------
# Core MINES pipeline
# ---------------------------------------------------------------------------


def mine_from_otel_spans(
    spans: list[OtelSpan],
    dry_run: bool = False,
    model: Optional[str] = None,
    confidence_threshold: float = 0.7,
) -> list[MinesInvariant]:
    """Mine invariants from OpenTelemetry spans (MINES algorithm, ICSE 2026).

    Pipeline:
    1. Pattern detection: group spans by operation, detect candidate patterns
    2. LLM hypothesis (if not dry_run): use litellm to hypothesize invariants
    3. Validation: check each hypothesis against all spans for that operation
    4. Filter by confidence_threshold

    In dry_run mode, uses deterministic pattern detection only (no LLM).
    This is used in tests to avoid real API calls.

    Args:
        spans:               OTel spans to mine from.
        dry_run:             If True, skip LLM, use deterministic mining only.
        model:               litellm model name. Defaults to NIGHTJAR_MODEL env var.
        confidence_threshold: Minimum confidence to include in output [0.0, 1.0].

    Returns:
        List of MinesInvariant objects that passed validation.

    Reference: MINES arXiv 2512.06906 -- Algorithm 1 (span-based mining).
    """
    if not spans:
        return []

    # Group spans by operation
    by_operation: dict[str, list[OtelSpan]] = defaultdict(list)
    for span in spans:
        by_operation[span.operation_name].append(span)

    all_invariants: list[MinesInvariant] = []

    for operation, op_spans in by_operation.items():
        if len(op_spans) < 2:
            # Need at least 2 observations to mine invariants
            continue

        # Step 1: Deterministic pattern detection (always runs)
        candidates = _detect_patterns(operation, op_spans)

        # Step 2: LLM hypothesis (if enabled)
        if not dry_run and _LITELLM_AVAILABLE:
            llm_candidates = _llm_hypothesize(operation, op_spans, model=model)
            candidates.extend(llm_candidates)

        # Step 3: Validate candidates against all spans
        validated = validate_invariants_against_spans(candidates, op_spans)

        # Step 4: Filter by confidence
        above_threshold = [
            inv for inv in validated if inv.confidence >= confidence_threshold
        ]
        all_invariants.extend(above_threshold)

    return all_invariants


def _detect_patterns(
    operation: str, spans: list[OtelSpan]
) -> list[MinesInvariant]:
    """Deterministic pattern detection for common invariant shapes.

    Covers MINES Categories 1 (Common-sense) and 2 (Format) without LLM.
    Reference: MINES arXiv 2512.06906 Section 3.2 -- pattern templates.
    """
    invariants: list[MinesInvariant] = []

    # --- Category 1: Common-sense — HTTP status code patterns ---
    status_codes = [s.status_code for s in spans]
    unique_statuses = set(status_codes)

    if len(unique_statuses) <= 5:
        # Status code is restricted to a small set
        sorted_statuses = sorted(unique_statuses)
        status_set = "{" + ", ".join(str(s) for s in sorted_statuses) + "}"
        expr = f"status_code in {status_set}"
        confidence = _count_support(status_codes, unique_statuses) / len(status_codes)
        invariants.append(
            MinesInvariant(
                category=MinesCategory.COMMON_SENSE,
                operation=operation,
                expression=expr,
                confidence=confidence,
                icontract_decorator=_format_status_code_decorator(operation, sorted_statuses),
            )
        )

    # --- Category 1: Common-sense — response time bounds ---
    durations = [s.duration_ms for s in spans]
    if durations:
        max_dur = max(durations)
        # p95 as upper bound (exclude top 5%)
        sorted_dur = sorted(durations)
        p95_idx = int(len(sorted_dur) * 0.95)
        p95 = sorted_dur[min(p95_idx, len(sorted_dur) - 1)]
        if p95 < max_dur * 0.9:  # There are outliers
            expr = f"duration_ms <= {p95:.1f}"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.ENVIRONMENT,
                    operation=operation,
                    expression=expr,
                    confidence=0.95,  # p95 by definition
                    icontract_decorator=_format_duration_decorator(operation, p95),
                )
            )

    # --- Category 2: Format — attribute patterns ---
    for attr_name in _get_common_attributes(spans):
        attr_values = [
            s.attributes.get(attr_name)
            for s in spans
            if attr_name in s.attributes
        ]
        if not attr_values:
            continue

        # Email format detection
        if _all_match_email(attr_values):
            expr = f"{attr_name} matches email pattern (RFC 5321)"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.FORMAT,
                    operation=operation,
                    expression=expr,
                    confidence=1.0,
                    icontract_decorator=_format_email_decorator(operation, attr_name),
                )
            )

        # UUID format detection
        elif _all_match_uuid(attr_values):
            expr = f"{attr_name} matches UUID pattern"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.FORMAT,
                    operation=operation,
                    expression=expr,
                    confidence=1.0,
                    icontract_decorator=_format_uuid_decorator(operation, attr_name),
                )
            )

        # Non-negative integer (database ID pattern)
        elif _all_positive_int(attr_values):
            expr = f"{attr_name} >= 1 (positive integer, likely DB ID)"
            invariants.append(
                MinesInvariant(
                    category=MinesCategory.DATABASE,
                    operation=operation,
                    expression=expr,
                    confidence=1.0,
                    icontract_decorator=_format_positive_int_decorator(operation, attr_name),
                )
            )

    return invariants


def _llm_hypothesize(
    operation: str,
    spans: list[OtelSpan],
    model: Optional[str] = None,
) -> list[MinesInvariant]:
    """Use LLM to hypothesize invariants from span patterns.

    Formats a representative sample of spans as context and asks the LLM
    to identify likely API invariants across all 5 MINES categories.

    All LLM calls go through litellm [REF-T16] for model-agnosticism.
    Model resolved from NIGHTJAR_MODEL env var or function argument.

    Reference: MINES arXiv 2512.06906 -- LLM-based hypothesis generation.
    """
    if not _LITELLM_AVAILABLE:
        return []
    import litellm  # re-import is a no-op but satisfies type checker

    resolved_model = model or os.environ.get("NIGHTJAR_MODEL") or DEFAULT_MODEL

    # Format a representative sample (max 10 spans) as context
    sample = spans[:10]
    span_summaries = []
    for s in sample:
        summary = {
            "operation": s.operation_name,
            "status": s.status_code,
            "duration_ms": round(s.duration_ms, 1),
        }
        if s.attributes:
            summary["attrs"] = {k: v for k, v in list(s.attributes.items())[:5]}
        span_summaries.append(str(summary))

    prompt = (
        f"You are analyzing API traces for operation: {operation!r}\n\n"
        f"Sample spans:\n" + "\n".join(span_summaries) + "\n\n"
        "Identify likely API invariants from these 5 categories:\n"
        "1. Common-sense: HTTP status codes, response shapes\n"
        "2. Format: email, UUID, date pattern\n"
        "3. Database: FK, uniqueness, non-null\n"
        "4. Environment: latency, rate limits\n"
        "5. Related API: sequencing between endpoints\n\n"
        "Return ONLY a JSON array of objects with keys: "
        "category (string), expression (string), confidence (float 0-1).\n"
        "Keep it brief. Return [] if no clear invariants."
    )

    try:
        response = litellm.completion(
            model=resolved_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.0,
        )
        content = response.choices[0].message.content or ""
        return _parse_llm_response(operation, content)
    except Exception:
        # LLM failure is non-fatal — return empty, let deterministic patterns fill in
        return []


def _parse_llm_response(operation: str, content: str) -> list[MinesInvariant]:
    """Parse LLM JSON response into MinesInvariant objects."""
    import json

    # Extract JSON array from response (may be wrapped in markdown)
    json_match = re.search(r"\[.*\]", content, re.DOTALL)
    if not json_match:
        return []

    try:
        items = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return []

    invariants: list[MinesInvariant] = []
    category_map = {
        "common_sense": MinesCategory.COMMON_SENSE,
        "format": MinesCategory.FORMAT,
        "database": MinesCategory.DATABASE,
        "environment": MinesCategory.ENVIRONMENT,
        "related_api": MinesCategory.RELATED_API,
        # Also accept integer labels
        "1": MinesCategory.COMMON_SENSE,
        "2": MinesCategory.FORMAT,
        "3": MinesCategory.DATABASE,
        "4": MinesCategory.ENVIRONMENT,
        "5": MinesCategory.RELATED_API,
    }

    for item in items:
        if not isinstance(item, dict):
            continue
        cat_str = str(item.get("category", "")).lower().replace("-", "_")
        category = category_map.get(cat_str, MinesCategory.COMMON_SENSE)
        expression = str(item.get("expression", "")).strip()
        confidence = float(item.get("confidence", 0.7))

        if not expression:
            continue

        invariants.append(
            MinesInvariant(
                category=category,
                operation=operation,
                expression=expression,
                confidence=min(max(confidence, 0.0), 1.0),
                icontract_decorator=_format_generic_decorator(operation, expression),
            )
        )

    return invariants


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_invariants_against_spans(
    candidates: list[MinesInvariant],
    spans: list[OtelSpan],
) -> list[MinesInvariant]:
    """Validate candidate invariants against a set of spans.

    For each candidate, checks if the expressed constraint holds for ALL
    spans belonging to the same operation. Invariants that fail are rejected.

    This is the "validate" step in the MINES pipeline (arXiv 2512.06906).

    Args:
        candidates: Candidate invariants to validate.
        spans:      Healthy trace spans (the validation set).

    Returns:
        Subset of candidates that hold for all matching spans.
    """
    validated: list[MinesInvariant] = []

    for inv in candidates:
        # Find spans for this operation
        op_spans = [s for s in spans if s.operation_name == inv.operation]
        if not op_spans:
            # No spans for this operation -- can't validate, skip
            continue

        if _check_holds_for_all(inv, op_spans):
            validated.append(inv)

    return validated


def _check_holds_for_all(inv: MinesInvariant, spans: list[OtelSpan]) -> bool:
    """Check if invariant holds for all spans in the list.

    Parses simple status_code and attribute expressions to validate
    against span data. Returns True if invariant holds for all spans.
    """
    expr = inv.expression

    # --- status_code in {set} ---
    status_set_match = re.match(r"status_code in \{([0-9, ]+)\}", expr)
    if status_set_match:
        allowed = set(int(s.strip()) for s in status_set_match.group(1).split(","))
        return all(s.status_code in allowed for s in spans)

    # --- status_code == N ---
    status_eq_match = re.match(r"status_code == (\d+)", expr)
    if status_eq_match:
        required = int(status_eq_match.group(1))
        return all(s.status_code == required for s in spans)

    # --- duration_ms <= N ---
    duration_match = re.match(r"duration_ms <= ([0-9.]+)", expr)
    if duration_match:
        limit = float(duration_match.group(1))
        return all(s.duration_ms <= limit for s in spans)

    # --- Attribute-based invariants: attr >= 1, email, UUID patterns ---
    attr_pos_match = re.match(r"(\w+) >= 1 \(positive integer", expr)
    if attr_pos_match:
        attr_name = attr_pos_match.group(1)
        for span in spans:
            if attr_name in span.attributes:
                try:
                    val = int(span.attributes[attr_name])
                    if val < 1:
                        return False
                except (ValueError, TypeError):
                    return False
        return True

    email_match = re.match(r"(\w+) matches email pattern", expr)
    if email_match:
        attr_name = email_match.group(1)
        for span in spans:
            if attr_name in span.attributes:
                if not re.match(r"[^@]+@[^@]+\.[^@]+", str(span.attributes[attr_name])):
                    return False
        return True

    uuid_match = re.match(r"(\w+) matches UUID pattern", expr)
    if uuid_match:
        attr_name = uuid_match.group(1)
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        for span in spans:
            if attr_name in span.attributes:
                if not uuid_re.match(str(span.attributes[attr_name])):
                    return False
        return True

    # Unknown expression format: cannot validate — reject conservatively
    # (MINES validation must confirm holds; if we can't check, we don't confirm)
    return False


# ---------------------------------------------------------------------------
# icontract decorator formatter
# ---------------------------------------------------------------------------


def format_as_icontract(inv: MinesInvariant) -> str:
    """Format a MinesInvariant as an @icontract decorator string.

    Generates Python @icontract.require or @icontract.ensure decorator code
    that can be applied to API endpoint functions.

    Args:
        inv: The MinesInvariant to format.

    Returns:
        @icontract decorator string.

    Reference: [REF-T10] icontract runtime enforcement.
    """
    if inv.icontract_decorator:
        return inv.icontract_decorator

    return _format_generic_decorator(inv.operation, inv.expression)


# ---------------------------------------------------------------------------
# Helper formatters
# ---------------------------------------------------------------------------


def _format_status_code_decorator(operation: str, statuses: list[int]) -> str:
    status_set = "{" + ", ".join(str(s) for s in statuses) + "}"
    return (
        f"@icontract.ensure(lambda result: result.status_code in {status_set},\n"
        f"                  description=\"{operation}: status must be in {status_set}\")"
    )


def _format_duration_decorator(operation: str, p95: float) -> str:
    return (
        f"@icontract.ensure(lambda result: result.duration_ms <= {p95:.1f},\n"
        f"                  description=\"{operation}: p95 latency <= {p95:.1f}ms\")"
    )


def _format_email_decorator(operation: str, attr_name: str) -> str:
    return (
        f"@icontract.require(\n"
        f"    lambda {attr_name}: re.match(r'[^@]+@[^@]+\\.[^@]+', str({attr_name})),\n"
        f"    description=\"{operation}: {attr_name} must match email format (RFC 5321)\")"
    )


def _format_uuid_decorator(operation: str, attr_name: str) -> str:
    return (
        f"@icontract.require(\n"
        f"    lambda {attr_name}: re.match(\n"
        f"        r'^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$',\n"
        f"        str({attr_name}), re.IGNORECASE),\n"
        f"    description=\"{operation}: {attr_name} must be a valid UUID\")"
    )


def _format_positive_int_decorator(operation: str, attr_name: str) -> str:
    return (
        f"@icontract.require(lambda {attr_name}: int({attr_name}) >= 1,\n"
        f"                   description=\"{operation}: {attr_name} must be a positive integer\")"
    )


def _format_generic_decorator(operation: str, expression: str) -> str:
    """Generic decorator for expressions we can't parse into specific lambda."""
    safe_expr = expression.replace('"', "'")
    return (
        f"# MINES invariant: {safe_expr}\n"
        f"@icontract.require(lambda: True,  # TODO: implement check for: {safe_expr}\n"
        f"                   description=\"{operation}: {safe_expr}\")"
    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _get_common_attributes(spans: list[OtelSpan]) -> list[str]:
    """Return attribute names that appear in at least half the spans."""
    if not spans:
        return []
    counts: Counter[str] = Counter()
    for span in spans:
        for key in span.attributes:
            counts[key] += 1
    threshold = len(spans) // 2
    return [key for key, count in counts.items() if count >= threshold]


def _count_support(values: list[Any], unique: set[Any]) -> int:
    """Count how many values are in the unique set (always all of them here)."""
    return len(values)  # All observed values are in the set by construction


def _all_match_email(values: list[Any]) -> bool:
    """Return True if all values look like email addresses."""
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    return bool(values) and all(
        isinstance(v, str) and email_re.match(v) for v in values
    )


def _all_match_uuid(values: list[Any]) -> bool:
    """Return True if all values look like UUIDs."""
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(values) and all(
        isinstance(v, str) and uuid_re.match(v) for v in values
    )


def _all_positive_int(values: list[Any]) -> bool:
    """Return True if all values are positive integers."""
    for v in values:
        try:
            if int(v) < 1:
                return False
        except (ValueError, TypeError):
            return False
    return bool(values)
