"""FastAPI server for Nightjar Verification Canvas.

Serves verification run data, SSE streams, and the public scanner API.

Usage (development):
    python -m nightjar.web_server
    uvicorn nightjar.web_server:app --reload --port 8000

The ``app`` module-level instance is imported by uvicorn and by the
``nightjar serve`` CLI command.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        A fully wired :class:`fastapi.FastAPI` instance with CORS middleware
        and the canvas router mounted at ``/api``.
    """
    app = FastAPI(
        title="Nightjar Canvas",
        version="0.1.0",
        description=(
            "Verification Canvas API — real-time SSE streams, run storage, "
            "and trust-score badges for Nightjar-verified modules."
        ),
    )

    # Allow all origins for development; tighten in production via env var.
    # Note: allow_credentials=True is intentionally omitted — the CORS spec
    # forbids credentials with a wildcard origin. Set explicit origins via
    # NIGHTJAR_ALLOWED_ORIGINS env var for credentialed requests.
    import os

    raw_origins = os.environ.get("NIGHTJAR_ALLOWED_ORIGINS", "*")
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from nightjar.web_router import router
    from nightjar.web_scanner import scanner_router

    app.include_router(router, prefix="/api")
    app.include_router(scanner_router, prefix="/api")

    return app


# Module-level application instance consumed by uvicorn / gunicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
