"""Public scanner endpoint for Nightjar Verification Canvas.

Provides POST /api/scan — accepts a GitHub URL, creates a run record,
spawns ``nightjar verify --fast`` as an async subprocess (scoped to max
10 files), and returns immediately with the run_id.

Rate limiting: 5 scans per IP per day, tracked in the same SQLite DB used
by web_db.  A ``scan_rate_limits`` table is created by :func:`init_scanner_db`.

All LLM calls in the downstream pipeline go through litellm; this module
itself makes no LLM calls.

Registration
------------
Import and include the router in ``web_server.create_app``::

    from nightjar.web_scanner import scanner_router
    app.include_router(scanner_router, prefix="/api")

Or mount alongside the existing router::

    app.include_router(scanner_router, prefix="/api")
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nightjar import web_db
from nightjar.config import load_config

scanner_router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCANS_PER_IP_PER_DAY: int = 5
MAX_FILES_FREE_SCAN: int = 10

_GITHUB_URL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:/.*)?$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Rate-limit DB helpers
# ---------------------------------------------------------------------------

_DDL_RATE_LIMIT = """
CREATE TABLE IF NOT EXISTS scanner_rate_limits (
    ip          TEXT    NOT NULL,
    day_key     TEXT    NOT NULL,   -- YYYY-MM-DD UTC
    scan_count  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ip, day_key)
);
"""

# Cached DB path — resolved once
_rl_db_path_cache: Optional[str] = None


def _resolve_rl_db() -> str:
    """Return the path to the rate-limit SQLite database, initialising it once."""
    global _rl_db_path_cache
    if _rl_db_path_cache is None:
        cfg = load_config()
        specs_dir = cfg.get("paths", {}).get("specs", ".card/")
        _rl_db_path_cache = str(Path(specs_dir) / "tracking.db")
        Path(_rl_db_path_cache).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_rl_db_path_cache)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_DDL_RATE_LIMIT)
            conn.commit()
        finally:
            conn.close()
    return _rl_db_path_cache


def _day_key() -> str:
    """Return today's UTC date string: YYYY-MM-DD."""
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _increment_scan_count(ip: str) -> int:
    """Atomically increment today's scan count for *ip* and return the new total."""
    db = _resolve_rl_db()
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            INSERT INTO scanner_rate_limits (ip, day_key, scan_count)
            VALUES (?, ?, 1)
            ON CONFLICT(ip, day_key) DO UPDATE SET scan_count = scan_count + 1
            """,
            (ip, _day_key()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT scan_count FROM scanner_rate_limits WHERE ip = ? AND day_key = ?",
            (ip, _day_key()),
        ).fetchone()
        return row[0] if row else 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GitHub URL validation + normalisation
# ---------------------------------------------------------------------------


def validate_github_url(url: str) -> str:
    """Return a normalised ``https://github.com/...`` URL or raise ValueError.

    Args:
        url: Raw URL string from the request body.

    Returns:
        Normalised full GitHub HTTPS URL.

    Raises:
        ValueError: If *url* is empty, too long, or does not match GitHub
            URL format.
    """
    stripped = (url or "").strip()
    if not stripped:
        raise ValueError("github_url must not be empty")
    if len(stripped) > 512:
        raise ValueError("github_url is too long (max 512 chars)")

    # Accept bare "owner/repo" — normalise to full URL
    if re.match(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", stripped):
        stripped = f"https://github.com/{stripped}"

    if not _GITHUB_URL_RE.match(stripped):
        raise ValueError(
            f"Invalid GitHub URL: '{stripped}'. "
            "Expected format: https://github.com/owner/repo"
        )
    return stripped


def _extract_spec_id(github_url: str) -> str:
    """Extract ``owner/repo`` from a normalised GitHub URL.

    Args:
        github_url: Normalised GitHub HTTPS URL.

    Returns:
        ``"owner/repo"`` string.
    """
    # Strip scheme + host, split path
    path = re.sub(r"^https?://(?:www\.)?github\.com/", "", github_url)
    parts = path.rstrip("/").split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else path


# ---------------------------------------------------------------------------
# Background subprocess runner
# ---------------------------------------------------------------------------


async def _run_verification(
    run_id: str,
    github_url: str,
    db_path: str,
) -> None:
    """Spawn ``nightjar verify --fast`` as a subprocess and update the run record.

    The subprocess is scoped to at most ``MAX_FILES_FREE_SCAN`` Python files
    discovered in a shallow clone of the repository.  On completion the run
    status is updated to ``"complete"`` or ``"failed"``.

    Args:
        run_id: UUID4 run identifier (already inserted in ``canvas_runs``).
        github_url: Normalised GitHub HTTPS URL of the repository to verify.
        db_path: Path to the SQLite tracking database.
    """
    nightjar_bin = os.environ.get("NIGHTJAR_BIN", "nightjar")
    model = os.environ.get("NIGHTJAR_MODEL", "")

    cmd: list[str] = [
        nightjar_bin,
        "verify",
        "--fast",
        f"--github={github_url}",
        f"--max-files={MAX_FILES_FREE_SCAN}",
        f"--run-id={run_id}",
    ]
    if model:
        cmd += [f"--model={model}"]

    env = {**os.environ, "NIGHTJAR_RUN_ID": run_id}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        success = proc.returncode == 0
        trust = "SCHEMA_VERIFIED" if success else "UNVERIFIED"

        web_db.update_run_status(
            db_path=db_path,
            run_id=run_id,
            status="complete" if success else "failed",
            verified=success,
            trust_level=trust,
        )
    except asyncio.TimeoutError:
        web_db.update_run_status(
            db_path=db_path,
            run_id=run_id,
            status="failed",
            verified=False,
            trust_level="UNVERIFIED",
        )
    except Exception:
        # Subprocess could not be launched (nightjar not on PATH, etc.)
        web_db.update_run_status(
            db_path=db_path,
            run_id=run_id,
            status="failed",
            verified=False,
            trust_level="UNVERIFIED",
        )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Body for ``POST /api/scan``."""

    github_url: str


class ScanResponse(BaseModel):
    """Immediate response for ``POST /api/scan``."""

    run_id: str
    url: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@scanner_router.post("/scan", response_model=ScanResponse, status_code=202)
async def create_scan(body: ScanRequest, request: Request) -> ScanResponse:
    """Accept a GitHub URL, create a run, and start verification asynchronously.

    Rate-limited to ``MAX_SCANS_PER_IP_PER_DAY`` scans per client IP per day.
    Returns immediately with ``run_id`` and a canonical ``/run/{run_id}`` URL.
    Verification runs in the background.

    Args:
        body: JSON body with ``github_url``.
        request: FastAPI request (used to extract client IP).

    Returns:
        ``{"run_id": "<uuid4>", "url": "/run/<uuid4>"}``

    Raises:
        HTTPException 400: If ``github_url`` is invalid.
        HTTPException 429: If rate limit exceeded.
    """
    # --- Validate URL ---
    try:
        github_url = validate_github_url(body.github_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- Rate limiting ---
    # Increment-first strategy: atomically increment, then reject if over limit.
    # This prevents TOCTOU races where concurrent requests both read the same
    # count and both slip through at the boundary.
    client_ip = _client_ip(request)
    new_count = _increment_scan_count(client_ip)
    if new_count > MAX_SCANS_PER_IP_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: {MAX_SCANS_PER_IP_PER_DAY} scans per IP per day. "
                "Try again tomorrow."
            ),
        )

    # --- Create run record ---
    spec_id = _extract_spec_id(github_url)
    cfg = load_config()
    db_path = web_db.init_db(config=cfg)
    run_id = web_db.create_run(
        db_path=db_path,
        spec_id=spec_id,
        model=os.environ.get("NIGHTJAR_MODEL", ""),
        meta={
            "github_url": github_url,
            "source": "public_scanner",
            "max_files": MAX_FILES_FREE_SCAN,
            "client_ip_hash": _hash_ip(client_ip),
        },
    )

    # --- Spawn background verification ---
    asyncio.create_task(
        _run_verification(run_id=run_id, github_url=github_url, db_path=db_path)
    )

    return ScanResponse(run_id=run_id, url=f"/run/{run_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    """Extract the real client IP, honouring X-Forwarded-For if present."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _hash_ip(ip: str) -> str:
    """Return a one-way hash of *ip* for storing in meta without raw IP.

    Uses SHA-256 truncated to 16 hex chars — enough to correlate without
    storing identifiable data in the run record.
    """
    import hashlib
    return hashlib.sha256(ip.encode()).hexdigest()[:16]
