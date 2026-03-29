"""Sentry webhook payload parser — processes Sentry-format JSON payloads into
invariant candidates. Does not connect to Sentry directly (no sentry_sdk dependency).

Pipeline:
    Sentry production error
    → sentry_event_to_candidate() (convert to candidate invariant)
    → sentry_feed() (batch, filter, deduplicate)
    → immune/pipeline.py Tier 2 entry point

References:
- nightjar-upgrade-plan.md U5.1 (lines 616-638)
- Sentry Python SDK event structure: https://develop.sentry.dev/sdk/event-payloads/
- immune/enricher.py — CandidateInvariant dataclass
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SentryCandidate:
    """A candidate invariant derived from a Sentry production error.

    Compatible with immune/enricher.py CandidateInvariant (has `expression`).

    Attributes:
        expression: Python invariant expression, e.g. ``amount > 0``.
        explanation: Human-readable description of the proposed invariant.
        confidence: Score 0.0–1.0 (production errors start at 0.7).
        function_name: Name of the crashing function extracted from the frame.
        module: Python module containing the crashing function.
        exc_type: Exception class name, e.g. ``ValueError``.
    """

    expression: str
    explanation: str = ""
    confidence: float = 0.7
    function_name: str = ""
    module: str = ""
    exc_type: str = ""


# ---------------------------------------------------------------------------
# Expression inference
# ---------------------------------------------------------------------------

_NEGATIVE_NUMBER_RE = re.compile(r"^-\d")


def _none_vars(vars_dict: dict) -> list[str]:
    """Return variable names whose runtime value was None/null."""
    return [k for k, v in vars_dict.items() if v in ("None", "null", "NoneType")]


def _negative_vars(vars_dict: dict) -> list[str]:
    """Return variable names whose runtime value was a negative number."""
    result = []
    for k, v in vars_dict.items():
        if isinstance(v, str) and _NEGATIVE_NUMBER_RE.match(v.strip()):
            result.append(k)
        else:
            try:
                if float(v) < 0:
                    result.append(k)
            except (ValueError, TypeError):
                pass
    return result


def _infer_expression(
    exc_type: str,
    exc_value: str,
    vars_dict: dict,
    function_name: str,
) -> str:
    """Infer a Python precondition expression from a Sentry exception frame.

    Heuristic rules (in priority order):
    1. None-related errors → ``<var> is not None``
    2. Negative-value errors → ``<var> > 0``
    3. Fallback → ``<function>: <exc_type> precondition violated``
    """
    # Rule 1: None-related (AttributeError on NoneType, TypeError with None arg)
    none_check = (
        exc_type in ("AttributeError", "TypeError")
        and ("NoneType" in exc_value or "None" in exc_value)
    )
    if not none_check and vars_dict:
        # Detected None in frame vars regardless of exc_type
        nv = _none_vars(vars_dict)
        if nv:
            return f"{nv[0]} is not None"

    if none_check:
        nv = _none_vars(vars_dict)
        if nv:
            return f"{nv[0]} is not None"
        return "arg is not None"

    # Rule 2: ValueError / numeric constraint violation
    if exc_type == "ValueError":
        neg = _negative_vars(vars_dict)
        if neg:
            return f"{neg[0]} > 0"
        # Message contains "positive" hint
        if "positive" in exc_value.lower():
            first_var = next(iter(vars_dict), None)
            if first_var:
                return f"{first_var} > 0"
            return f"{function_name}: input must be positive"
        return f"{function_name}: ValueError precondition violated"

    # Rule 3: generic fallback
    return f"{function_name}: {exc_type} precondition violated"


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def _extract_last_frame(exception_value: dict) -> Optional[dict]:
    """Return the innermost stacktrace frame, or None if absent."""
    stacktrace = exception_value.get("stacktrace") or {}
    frames = stacktrace.get("frames") or []
    return frames[-1] if frames else None


def sentry_event_to_candidate(event: dict) -> Optional[SentryCandidate]:
    """Convert a Sentry event dict to a SentryCandidate invariant proposal.

    Args:
        event: Sentry event payload dict (subset sufficient — only
               ``exception.values[*]`` and ``level`` are inspected).

    Returns:
        A :class:`SentryCandidate` if a meaningful invariant can be inferred,
        ``None`` if the event has no usable stacktrace frame.
    """
    exception = event.get("exception") or {}
    values = exception.get("values") or []
    if not values:
        return None

    exc_info = values[-1]  # innermost exception
    exc_type = exc_info.get("type", "Exception")
    exc_value = exc_info.get("value", "")

    frame = _extract_last_frame(exc_info)
    if frame is None:
        return None

    function_name = frame.get("function", "")
    module = frame.get("module", "")
    vars_dict: dict = frame.get("vars") or {}

    expression = _infer_expression(exc_type, exc_value, vars_dict, function_name)
    explanation = (
        f"Production {exc_type} in {module}.{function_name}: {exc_value!r}"
    )

    return SentryCandidate(
        expression=expression,
        explanation=explanation,
        confidence=0.7,
        function_name=function_name,
        module=module,
        exc_type=exc_type,
    )


# ---------------------------------------------------------------------------
# Batch feed (filter + deduplicate)
# ---------------------------------------------------------------------------

def _dedup_key(candidate: SentryCandidate) -> tuple:
    """Stable key for deduplication: (function_name, expression)."""
    return (candidate.function_name, candidate.expression)


def sentry_feed(events: list[dict]) -> list[SentryCandidate]:
    """Process a batch of Sentry events into deduplicated candidate invariants.

    Rules applied:
    - Only ``level == "error"`` events are processed.
    - Identical (function_name, expression) pairs are deduplicated to one entry.

    Args:
        events: List of Sentry event dicts.

    Returns:
        Deduplicated list of :class:`SentryCandidate` objects.
    """
    seen: set[tuple] = set()
    candidates: list[SentryCandidate] = []

    for event in events:
        if event.get("level") != "error":
            continue

        candidate = sentry_event_to_candidate(event)
        if candidate is None:
            continue

        key = _dedup_key(candidate)
        if key in seen:
            continue

        seen.add(key)
        candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------------
# Webhook integration
# ---------------------------------------------------------------------------

def process_webhook_payload(payload: str) -> Optional[dict]:
    """Parse a raw Sentry webhook JSON payload string.

    Sentry webhooks wrap the event under ``data.error``.  This function
    unwraps it and returns the event dict, or ``None`` on parse failure.

    Args:
        payload: Raw JSON string from the Sentry webhook endpoint.

    Returns:
        The Sentry event dict, or ``None`` if the payload is invalid JSON.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None

    # Sentry webhook structure: {"action": ..., "data": {"error": <event>}}
    event = data.get("data", {}).get("error")
    if event and isinstance(event, dict):
        return event

    # Fallback: payload is already an event dict (e.g. direct API send)
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# DSN configuration
# ---------------------------------------------------------------------------

def get_sentry_dsn() -> Optional[str]:
    """Read the Sentry DSN from the ``SENTRY_DSN`` environment variable.

    Returns:
        The DSN string, or ``None`` if the variable is not set.
    """
    return os.environ.get("SENTRY_DSN") or None
