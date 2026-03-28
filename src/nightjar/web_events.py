"""SSE event types for Nightjar Verification Canvas.

Defines the event taxonomy that flows from verification pipeline
stages to the frontend canvas over Server-Sent Events.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Verification canvas SSE event types."""

    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    STAGE_FAIL = "stage_fail"
    INVARIANT_FOUND = "invariant_found"
    RUN_COMPLETE = "run_complete"


@dataclass
class CanvasEvent:
    """A single SSE event payload.

    Attributes:
        event_type: Classification of this event.
        run_id: The verification run this event belongs to.
        payload: Arbitrary JSON-serialisable data for the event.
        ts: Unix timestamp (seconds) when this event was created.
        seq: Monotonically increasing sequence number within a run.
    """

    event_type: EventType
    run_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    seq: int = 0

    def to_sse(self) -> str:
        """Serialise to Server-Sent Events wire format.

        Returns a string with ``event:`` and ``data:`` fields terminated
        by the required double newline.
        """
        data = {
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "payload": self.payload,
            "ts": self.ts,
            "seq": self.seq,
        }
        return f"event: {self.event_type.value}\ndata: {json.dumps(data)}\n\n"

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation for database storage."""
        return {
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "payload": self.payload,
            "ts": self.ts,
            "seq": self.seq,
        }


def make_stage_start(
    run_id: str,
    stage: int,
    name: str,
    seq: int = 0,
) -> CanvasEvent:
    """Create a STAGE_START event."""
    return CanvasEvent(
        event_type=EventType.STAGE_START,
        run_id=run_id,
        payload={"stage": stage, "name": name},
        seq=seq,
    )


def make_stage_complete(
    run_id: str,
    stage: int,
    name: str,
    duration_ms: int = 0,
    seq: int = 0,
) -> CanvasEvent:
    """Create a STAGE_COMPLETE event."""
    return CanvasEvent(
        event_type=EventType.STAGE_COMPLETE,
        run_id=run_id,
        payload={"stage": stage, "name": name, "duration_ms": duration_ms},
        seq=seq,
    )


def make_stage_fail(
    run_id: str,
    stage: int,
    name: str,
    errors: Optional[list[dict[str, Any]]] = None,
    seq: int = 0,
) -> CanvasEvent:
    """Create a STAGE_FAIL event."""
    return CanvasEvent(
        event_type=EventType.STAGE_FAIL,
        run_id=run_id,
        payload={"stage": stage, "name": name, "errors": errors or []},
        seq=seq,
    )


def make_invariant_found(
    run_id: str,
    invariant_id: str,
    statement: str,
    tier: str,
    seq: int = 0,
) -> CanvasEvent:
    """Create an INVARIANT_FOUND event."""
    return CanvasEvent(
        event_type=EventType.INVARIANT_FOUND,
        run_id=run_id,
        payload={
            "invariant_id": invariant_id,
            "statement": statement,
            "tier": tier,
        },
        seq=seq,
    )


def make_run_complete(
    run_id: str,
    verified: bool,
    trust_level: str,
    total_duration_ms: int = 0,
    seq: int = 0,
) -> CanvasEvent:
    """Create a RUN_COMPLETE event."""
    return CanvasEvent(
        event_type=EventType.RUN_COMPLETE,
        run_id=run_id,
        payload={
            "verified": verified,
            "trust_level": trust_level,
            "total_duration_ms": total_duration_ms,
        },
        seq=seq,
    )
