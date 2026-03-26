"""Shared types for the CARD immune system.

Data classes for traces, invariant candidates, and verified invariants
that flow through the immune pipeline.

References:
- [REF-C05] Dynamic Invariant Mining — trace/invariant data model
- [REF-T12] MonkeyType — type trace format
- [REF-T15] OpenTelemetry — API trace format
- [REF-P17] MINES — API invariant format
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _utcnow() -> datetime:
    """UTC-aware now(), avoids deprecated datetime.utcnow()."""
    return datetime.now(tz=timezone.utc)


class TraceKind(str, Enum):
    """Classification of trace data sources."""
    TYPE = "type"          # MonkeyType type signatures [REF-T12]
    VALUE = "value"        # Daikon value observations [REF-T13]
    API = "api"            # OpenTelemetry HTTP spans [REF-T15]
    ERROR = "error"        # Sentry-style error capture


class InvariantStatus(str, Enum):
    """Lifecycle status of a mined invariant."""
    CANDIDATE = "candidate"    # Mined but not yet verified
    VERIFIED = "verified"      # Passed CrossHair + Hypothesis
    REJECTED = "rejected"      # Failed verification
    APPLIED = "applied"        # Written to .card.md


@dataclass
class TypeTrace:
    """A runtime type observation from MonkeyType [REF-T12].

    Attributes:
        module: Python module name.
        function: Function name.
        arg_name: Argument name (or 'return' for return type).
        observed_type: The type observed at runtime.
        timestamp: When the trace was recorded.
    """
    module: str
    function: str
    arg_name: str
    observed_type: str
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None


@dataclass
class ValueTrace:
    """A runtime value observation from Daikon mining [REF-C05].

    Attributes:
        function: Function name.
        variable: Variable name.
        value_repr: String representation of the observed value.
        value_type: Type name of the value.
        timestamp: When the trace was recorded.
    """
    function: str
    variable: str
    value_repr: str
    value_type: str
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None


@dataclass
class ApiTrace:
    """An API request/response trace from OpenTelemetry [REF-T15, REF-P17].

    Attributes:
        method: HTTP method (GET, POST, etc.).
        url: Request URL path.
        status_code: HTTP response status code.
        request_shape: JSON schema-like shape of request body.
        response_shape: JSON schema-like shape of response body.
        duration_ms: Request duration in milliseconds.
        trace_id: OpenTelemetry trace ID.
        timestamp: When the trace was recorded.
    """
    method: str
    url: str
    status_code: int
    request_shape: str = ""
    response_shape: str = ""
    duration_ms: int = 0
    trace_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None


@dataclass
class ErrorTrace:
    """A captured error with semantic fingerprint.

    Attributes:
        exception_class: Exception class name.
        message_template: PII-stripped error message template.
        stack_fingerprint: Semantic fingerprint for grouping.
        function: Function where error occurred.
        module: Module where error occurred.
        input_shape: Type shape of inputs at crash point.
        timestamp: When the error was captured.
    """
    exception_class: str
    message_template: str
    stack_fingerprint: str
    function: str = ""
    module: str = ""
    input_shape: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None


@dataclass
class InvariantCandidate:
    """A candidate invariant mined from traces [REF-C05].

    Attributes:
        function: Function this invariant applies to.
        expression: The invariant expression.
        kind: Type of invariant (type, bound, nullness, etc.).
        source: Which trace source produced this (daikon, monkeytype, otel).
        confidence: Confidence score (0.0-1.0) based on observation count.
        observation_count: Number of observations supporting this invariant.
        status: Lifecycle status.
        timestamp: When the candidate was created.
    """
    function: str
    expression: str
    kind: str
    source: str
    confidence: float = 0.0
    observation_count: int = 0
    status: InvariantStatus = InvariantStatus.CANDIDATE
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None


@dataclass
class VerifiedInvariant:
    """An invariant that passed verification [REF-T09, REF-T03].

    Attributes:
        function: Function this invariant applies to.
        expression: The invariant expression.
        kind: Type of invariant.
        verification_method: How it was verified (crosshair, hypothesis, both).
        card_spec_id: Which .card.md spec it was appended to (if any).
        timestamp: When it was verified.
    """
    function: str
    expression: str
    kind: str
    verification_method: str
    card_spec_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    id: Optional[int] = None
