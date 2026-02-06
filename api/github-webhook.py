"""GitHub App webhook handler for swarm-ai-bot."""

import hashlib
import hmac
import os
from http.server import BaseHTTPRequestHandler


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_POST(self):
        """Handle incoming webhook POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

        if webhook_secret and not verify_signature(payload, signature, webhook_secret):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid signature"}')
            return

        # Get event type
        event_type = self.headers.get("X-GitHub-Event", "")

        # Handle ping event (sent when webhook is first configured)
        if event_type == "ping":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"message": "pong"}')
            return

        # For now, just acknowledge other events
        # TODO: Add handlers for issues, issue_comment, etc.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(f'{{"event": "{event_type}", "status": "received"}}'.encode())

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "swarm-ai-bot webhook"}')
