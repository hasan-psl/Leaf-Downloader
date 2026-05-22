"""
Lightweight localhost HTTP API server for browser extension communication.

Runs on 127.0.0.1 (localhost only) to receive download URLs from the
Leaf-Downloader Firefox extension. Uses Python's built-in http.server
to avoid any additional dependencies.
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from gi.repository import GLib, Gio
import re


class ApiRequestHandler(BaseHTTPRequestHandler):
    """Handles incoming HTTP requests from the browser extension."""

    # Suppress default stderr logging for each request
    def log_message(self, format, *args):
        print(f"[API Server] {format % args}")

    def _set_cors_headers(self):
        """Set CORS headers to allow requests from browser extensions."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status_code, data):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/api/ping":
            self._send_json(200, {
                "status": "running",
                "app": "Leaf-Downloader",
                "version": "1.0"
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/api/download":
            self._handle_download()
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_download(self):
        """Process a download request from the extension."""
        # Rate limiting
        now = time.time()
        if hasattr(self.server, '_last_request_time'):
            if now - self.server._last_request_time < 1.0:
                self._send_json(429, {"error": "Too many requests. Please wait."})
                return
        self.server._last_request_time = now

        # Read request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0 or content_length > 4096:
                self._send_json(400, {"error": "Invalid request body"})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON"})
            return

        url = data.get("url", "").strip()

        # Validate URL
        if not url or not re.match(r'^https?://[\w\-]+(\.[\w\-]+)+[/#?]?.*$', url):
            self._send_json(400, {"error": "Invalid URL"})
            return

        # Dispatch to GTK app on the main thread
        app = Gio.Application.get_default()
        if app:
            GLib.idle_add(
                app.activate_action,
                "download-from-extension",
                GLib.Variant.new_string(url)
            )
            self._send_json(200, {"status": "queued", "url": url})
            print(f"[API Server] Download dispatched: {url}")
        else:
            self._send_json(500, {"error": "Application not available"})


class ApiServer:
    """
    Manages the localhost HTTP server lifecycle.
    
    Runs in a daemon thread so it doesn't block the GTK main loop.
    Binds exclusively to 127.0.0.1 for security.
    """

    def __init__(self, port=9549):
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """Start the API server in a background daemon thread."""
        if self.running:
            return

        try:
            self.server = HTTPServer(("127.0.0.1", self.port), ApiRequestHandler)
            self.server._last_request_time = 0
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            self.running = True
            print(f"[API Server] Listening on http://127.0.0.1:{self.port}")
        except OSError as e:
            print(f"[API Server] Failed to start: {e}")
            self.running = False

    def _serve(self):
        """Server loop running in background thread."""
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"[API Server] Error: {e}")
        finally:
            self.running = False

    def stop(self):
        """Gracefully shut down the server."""
        if self.server and self.running:
            self.server.shutdown()
            self.running = False
            print("[API Server] Stopped")

    def is_running(self):
        """Check if the server is currently active."""
        return self.running
