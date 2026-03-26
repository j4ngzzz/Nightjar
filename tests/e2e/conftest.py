"""Shared fixtures for Nightjar e2e (Playwright) tests.

All e2e tests skip automatically when playwright is not installed,
so the test suite remains green in lean CI environments.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Generator

import pytest

# Skip entire e2e module when playwright is unavailable.
playwright = pytest.importorskip(
    "playwright",
    reason="playwright not installed — install with: pip install playwright && playwright install chromium",
)


@pytest.fixture(scope="session")
def browser_context_args():
    """Force headless Chromium for all e2e tests."""
    return {"headless": True}


# ---------------------------------------------------------------------------
# Local badge HTTP server fixture
# ---------------------------------------------------------------------------

class _BadgeHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that serves badge HTML and SVG."""

    def do_GET(self):  # noqa: N802
        if self.path == "/badge":
            # Serve an HTML page embedding the nightjar badge
            from nightjar.badge import BadgeStatus, generate_badge_url
            badge_url = generate_badge_url(BadgeStatus.PASSED, 95)
            html = (
                "<!DOCTYPE html><html><body>"
                f'<img id="badge" src="{badge_url}" alt="nightjar verified 95%">'
                "</body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/badge.svg":
            # Serve a minimal inline SVG badge (no external dependency)
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">'
                '<rect width="70" height="20" fill="#555"/>'
                '<rect x="70" width="50" height="20" fill="#4c1"/>'
                '<text x="35" y="14" fill="#fff" font-size="11">nightjar</text>'
                '<text x="95" y="14" fill="#fff" font-size="11">95%</text>'
                '</svg>'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg)))
            self.end_headers()
            self.wfile.write(svg)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # silence server log spam during tests
        pass


@pytest.fixture(scope="session")
def badge_server() -> Generator[str, None, None]:
    """Spin up a local badge HTTP server; yield its base URL; tear down."""
    server = HTTPServer(("127.0.0.1", 0), _BadgeHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
