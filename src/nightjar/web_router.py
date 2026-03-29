"""FastAPI router for Nightjar Verification Canvas.

Endpoints
---------
GET  /api/health                  — liveness probe
POST /api/runs                    — create a new run record
GET  /api/runs/{run_id}           — full run snapshot
GET  /api/runs/{run_id}/stream    — SSE stream of live events
GET  /api/runs/{run_id}/events    — stored event log
GET  /api/badge/{owner}/{name}    — trust-score JSON for badge rendering
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from nightjar import web_db, web_events
from nightjar.badge import BadgeStatus, generate_badge_url
from nightjar.config import load_config

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VERSION = "0.1.2"

# In-memory SSE subscriber queues: run_id → list[asyncio.Queue]
# Each active SSE connection for a run gets its own queue.
_sse_queues: dict[str, list[asyncio.Queue]] = {}

# Cached DB path — resolved once at first request to avoid filesystem
# reads on every call.
_db_path_cache: Optional[str] = None


def _get_db_path(config: Optional[dict[str, Any]] = None) -> str:
    """Resolve the tracking DB path from config, initialising it if needed."""
    cfg = config or load_config()
    return web_db.init_db(config=cfg)


def _resolve_db() -> str:
    """Return an initialised DB path, cached after the first call."""
    global _db_path_cache
    if _db_path_cache is None:
        _db_path_cache = _get_db_path()
    return _db_path_cache


async def _event_generator(
    run_id: str, request: Request
) -> AsyncGenerator[str, None]:
    """Yield SSE frames for *run_id*, relayed from the in-memory queue.

    Yields a ``ping`` comment every 15 s so proxies keep the connection alive.
    The generator exits when the client disconnects or a ``run_complete``
    event is received.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(run_id, []).append(queue)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event: web_events.CanvasEvent = await asyncio.wait_for(
                    queue.get(), timeout=15.0
                )
                yield event.to_sse()
                if event.event_type == web_events.EventType.RUN_COMPLETE:
                    break
            except asyncio.TimeoutError:
                # Send a keep-alive comment
                yield ": ping\n\n"
    finally:
        queues = _sse_queues.get(run_id, [])
        if queue in queues:
            queues.remove(queue)


async def _broadcast(run_id: str, event: web_events.CanvasEvent) -> None:
    """Push *event* to all active SSE queues for *run_id*."""
    for q in _sse_queues.get(run_id, []):
        await q.put(event)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    """Body for ``POST /api/runs``."""

    spec_id: str = ""
    model: str = ""
    meta: dict[str, Any] = {}


class CreateRunResponse(BaseModel):
    """Response for ``POST /api/runs``."""

    run_id: str


class PublishEventRequest(BaseModel):
    """Internal helper — allows tests to push events programmatically."""

    event_type: str
    payload: dict[str, Any] = {}
    seq: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe.

    Returns:
        ``{"status": "ok", "version": "0.1.0"}``
    """
    return {"status": "ok", "version": _VERSION}


@router.get("/runs")
async def list_runs(
    public: Optional[bool] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return a list of recent verification runs.

    Args:
        public: If ``True``, return only public-scanner runs
            (``meta.source == "public_scanner"``).  If omitted or ``False``,
            returns all runs.
        limit: Maximum number of runs to return (capped at 100).

    Returns:
        List of run summary dicts ordered by ``created_at`` descending.
        Each item includes: ``run_id``, ``spec_id``, ``status``,
        ``verified``, ``trust_level``, ``created_at``.
    """
    import sqlite3
    import json

    effective_limit = max(1, min(limit, 100))
    db = _resolve_db()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT run_id, spec_id, status, verified, trust_level,
                   created_at, meta_json
            FROM canvas_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (effective_limit,),
        ).fetchall()
    finally:
        conn.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(row["meta_json"] or "{}")
        except (ValueError, KeyError):
            pass

        if public and meta.get("source") != "public_scanner":
            continue

        result.append(
            {
                "run_id": row["run_id"],
                "spec_id": row["spec_id"],
                "status": row["status"],
                "verified": bool(row["verified"]),
                "trust_level": row["trust_level"],
                "created_at": row["created_at"],
            }
        )

    return result


@router.post("/runs", response_model=CreateRunResponse, status_code=201)
async def create_run(body: CreateRunRequest) -> CreateRunResponse:
    """Create a new verification run record.

    Args:
        body: JSON body with optional ``spec_id``, ``model``, and ``meta``.

    Returns:
        ``{"run_id": "<uuid4>"}``
    """
    db = _resolve_db()
    run_id = web_db.create_run(
        db_path=db,
        spec_id=body.spec_id,
        model=body.model,
        meta=body.meta,
    )
    return CreateRunResponse(run_id=run_id)


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Return a full run snapshot including events and invariants.

    Args:
        run_id: UUID4 run identifier.

    Returns:
        Full run dict with ``events`` and ``invariants`` lists.

    Raises:
        HTTPException 404: if *run_id* is not found.
    """
    db = _resolve_db()
    run = web_db.get_run(db_path=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request) -> StreamingResponse:
    """SSE stream for live verification events.

    The response uses ``text/event-stream`` content type.  Each frame is a
    JSON-encoded :class:`web_events.CanvasEvent`.  The stream ends when the
    client disconnects or a ``run_complete`` event is received.

    Args:
        run_id: UUID4 run identifier.

    Returns:
        A ``StreamingResponse`` with ``Content-Type: text/event-stream``.

    Raises:
        HTTPException 404: if *run_id* is not found.
    """
    db = _resolve_db()
    run = web_db.get_run(db_path=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return StreamingResponse(
        _event_generator(run_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[dict[str, Any]]:
    """Return the stored event log for a run.

    Args:
        run_id: UUID4 run identifier.

    Returns:
        List of event dicts ordered by (seq, event_id).

    Raises:
        HTTPException 404: if *run_id* is not found.
    """
    db = _resolve_db()
    run = web_db.get_run(db_path=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return web_db.get_events(db_path=db, run_id=run_id)


@router.get("/badge/{owner}/{name}")
async def get_badge(owner: str, name: str) -> dict[str, Any]:
    """Return trust-score JSON for badge rendering.

    The *owner/name* pair maps to a ``spec_id`` by joining them with a
    slash (``"{owner}/{name}"``).  This mirrors the GitHub-style path used
    by Codecov and similar badge services.

    Args:
        owner: Repository owner / organisation slug.
        name: Repository or module name.

    Returns:
        JSON dict with ``spec_id``, ``pass_rate``, ``trust_level``,
        ``run_count``, ``badge_url``.
    """
    spec_id = f"{owner}/{name}"
    db = _resolve_db()
    score = web_db.get_trust_score(db_path=db, spec_id=spec_id)

    # Derive a shields.io badge URL from the trust score
    trust = score["trust_level"]
    if trust == "FORMALLY_VERIFIED":
        badge_status = BadgeStatus.PASSED
        pct = 100
    elif trust == "PROPERTY_VERIFIED":
        badge_status = BadgeStatus.PASSED
        pct = 75
    elif trust == "SCHEMA_VERIFIED":
        badge_status = BadgeStatus.PASSED
        pct = 50
    else:
        badge_status = BadgeStatus.UNKNOWN
        pct = 0

    badge_url = generate_badge_url(badge_status, pct)
    return {**score, "badge_url": badge_url}


# ---------------------------------------------------------------------------
# Internal helper used by the verification pipeline to push events
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/events", status_code=201)
async def publish_event(run_id: str, body: PublishEventRequest) -> dict[str, Any]:
    """Push a new event for a run (used by the verification pipeline).

    This endpoint is intended for internal use by the Nightjar pipeline
    and integration tests.  It stores the event in the database and
    broadcasts it to any active SSE listeners.

    Args:
        run_id: UUID4 run identifier.
        body: Event data (``event_type``, ``payload``, ``seq``).

    Returns:
        ``{"event_id": <int>, "run_id": "<uuid>"}``

    Raises:
        HTTPException 404: if *run_id* is not found.
        HTTPException 422: if ``event_type`` is not a valid
            :class:`web_events.EventType`.
    """
    db = _resolve_db()
    run = web_db.get_run(db_path=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        et = web_events.EventType(body.event_type)
    except ValueError:
        valid = [e.value for e in web_events.EventType]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type '{body.event_type}'. Valid: {valid}",
        )

    event_id = web_db.store_event(
        db_path=db,
        run_id=run_id,
        event_type=body.event_type,
        payload=body.payload,
        seq=body.seq,
    )

    # Broadcast to SSE subscribers
    canvas_event = web_events.CanvasEvent(
        event_type=et,
        run_id=run_id,
        payload=body.payload,
        seq=body.seq,
    )
    await _broadcast(run_id, canvas_event)

    # If the run is complete, update its status in the DB
    if et == web_events.EventType.RUN_COMPLETE:
        verified = bool(body.payload.get("verified", False))
        trust = body.payload.get("trust_level", "UNVERIFIED")
        web_db.update_run_status(
            db_path=db,
            run_id=run_id,
            status="complete",
            verified=verified,
            trust_level=trust,
        )

    return {"event_id": event_id, "run_id": run_id}
