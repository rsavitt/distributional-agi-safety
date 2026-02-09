"""Lightweight HTTP server for the agent interaction dashboard."""

import json
import mimetypes
import sys
import webbrowser
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from swarm.dashboard.session_parser import discover_sessions, parse_session

# Directory containing web assets (index.html, app.js, styles.css)
WEB_DIR = Path(__file__).parent / "web"


class DashboardHandler(SimpleHTTPRequestHandler):
    """Request handler for the dashboard API and static file serving."""

    base_dir: Path  # set by server factory

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        # API routes
        if path == "/api/sessions":
            self._handle_sessions_list()
        elif path.startswith("/api/sessions/"):
            # /api/sessions/<encoded_path>
            session_path = path[len("/api/sessions/"):]
            # URL-decode the path
            from urllib.parse import unquote
            session_path = unquote(session_path)
            self._handle_session_detail(session_path)
        elif path == "/api/health":
            self._json_response({"status": "ok"})
        else:
            # Serve static files from web directory
            self._serve_static(path)

    def _handle_sessions_list(self) -> None:
        """Return list of discovered sessions."""
        sessions = discover_sessions(self.base_dir)
        self._json_response({"sessions": sessions})

    def _handle_session_detail(self, session_path: str) -> None:
        """Return fully parsed session data."""
        # Validate the path exists
        p = Path(session_path)
        if not p.exists():
            # Try relative to base_dir
            p = self.base_dir / session_path
        if not p.exists():
            self._json_response({"error": "Session file not found"}, status=404)
            return

        data = parse_session(str(p))
        self._json_response(data)

    def _json_response(
        self, data: Any, status: int = 200
    ) -> None:
        """Send a JSON response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str) -> None:
        """Serve static files from the web/ directory."""
        if path == "/" or path == "":
            path = "/index.html"

        file_path = WEB_DIR / path.lstrip("/")

        if not file_path.exists() or not file_path.is_file():
            # Fall back to index.html for SPA routing
            file_path = WEB_DIR / "index.html"

        if not file_path.exists():
            self.send_error(404, "File not found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging to keep output clean."""
        pass


def run_dashboard(
    base_dir: Optional[str] = None,
    port: int = 3339,
    no_open: bool = False,
) -> None:
    """Launch the dashboard web server.

    Args:
        base_dir: Root directory to scan for sessions (default: cwd)
        port: Port to serve on (default: 3339)
        no_open: If True, don't auto-open browser
    """
    resolved_dir = Path(base_dir) if base_dir else Path.cwd()
    if not resolved_dir.is_dir():
        print(f"Error: directory not found: {resolved_dir}", file=sys.stderr)
        sys.exit(1)

    # Inject base_dir into handler class
    DashboardHandler.base_dir = resolved_dir

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"

    print("=" * 50)
    print("  SWARM Agent Dashboard")
    print("=" * 50)
    print(f"  Scanning:  {resolved_dir}")
    print(f"  Dashboard: {url}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 50)

    if not no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
        server.shutdown()
