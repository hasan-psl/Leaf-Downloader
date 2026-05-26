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
        pass

    def _set_cors_headers(self):
        """Set CORS headers to allow requests from browser extensions."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status_code, data):
        """Send a JSON response."""
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected before we could respond (e.g. fast ping check).
            pass

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
        elif self.path == "/api/metadata":
            self._handle_metadata()
        elif self.path == "/api/quit":
            self._handle_quit()
        elif self.path == "/api/show":
            self._handle_show()
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_download(self):
        """Process a download request from the extension."""
        # Rate limiting
        now = time.time()
        if hasattr(self.server, '_last_request_time'):
            if now - self.server._last_request_time < 0.2:  # slightly lower limit for rapid direct clicks
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

        # Check if direct download payload is present
        format_id = data.get("format_id")
        
        # Dispatch to GTK app on the main thread
        app = Gio.Application.get_default()
        if app:
            if format_id:
                # Direct download: serialize the whole data payload to JSON string
                payload = json.dumps(data)
                GLib.idle_add(
                    app.activate_action,
                    "download-from-extension",
                    GLib.Variant.new_string(payload)
                )
                self._send_json(200, {"status": "started", "url": url, "direct": True})
                print(f"[API Server] Direct download dispatched: {url} ({format_id})")
            else:
                # Legacy metadata window fallback
                GLib.idle_add(
                    app.activate_action,
                    "download-from-extension",
                    GLib.Variant.new_string(url)
                )
                self._send_json(200, {"status": "queued", "url": url, "direct": False})
                print(f"[API Server] Legacy download dispatched: {url}")
        else:
            self._send_json(500, {"error": "Application not available"})

    def _handle_quit(self):
        """Quit the GTK Application."""
        app = Gio.Application.get_default()
        if app:
            GLib.idle_add(app.quit)
            self._send_json(200, {"status": "quitting"})
        else:
            self._send_json(500, {"error": "Application not available"})

    def _handle_show(self):
        """Show the GTK Window."""
        app = Gio.Application.get_default()
        if app:
            GLib.idle_add(app.activate)
            self._send_json(200, {"status": "showing"})
        else:
            self._send_json(500, {"error": "Application not available"})

    def _handle_metadata(self):
        """Fetch metadata for a URL using yt-dlp."""
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
        is_direct_fallback = data.get("is_direct_fallback", False)

        # Validate URL
        if not url or not re.match(r'^https?://[\w\-]+(\.[\w\-]+)+[/#?]?.*$', url):
            self._send_json(400, {"error": "Invalid URL"})
            return

        from urllib.parse import urlparse

        # ---------- Fast-path: detect direct media URLs before calling yt-dlp ----------
        DIRECT_EXTENSIONS = [
            ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv",
            ".mp3", ".m4a", ".m3u8", ".ts",
            ".zip", ".exe", ".tar", ".gz", ".7z", ".iso", ".dmg",
        ]

        def _detect_direct(target_url):
            """Return (is_direct, ext) for a URL that looks like a direct media/file link."""
            parsed = urlparse(target_url)
            path = parsed.path.lower()
            for ext in DIRECT_EXTENSIONS:
                # Match path ending or extension inside the path (before query string)
                if path.endswith(ext) or ("/" + ext.lstrip(".") + "?") in path or path.endswith(ext.lstrip(".")):
                    return True, ext.lstrip(".")
            # Also check the raw extension at the end of the path segment
            last_segment = path.rstrip("/").split("/")[-1]
            if "." in last_segment:
                file_ext = "." + last_segment.rsplit(".", 1)[-1].split("?")[0]
                if file_ext in DIRECT_EXTENSIONS:
                    return True, file_ext.lstrip(".")
            return False, "mp4"

        def _build_direct_metadata(target_url, ext, filename_hint=None):
            """Build the metadata response for a direct file download."""
            parsed = urlparse(target_url)
            path = parsed.path
            filename = filename_hint or path.split("/")[-1] or "download"
            # Strip extension and query params from display name
            if "." in filename:
                filename = filename.rsplit(".", 1)[0]
            filename = filename.split("?")[0].split("#")[0].strip()
            if not filename:
                filename = "Direct Download"
            return {
                "title": filename,
                "thumbnail": "",
                "uploader": "Direct Link",
                "duration": 0,
                "formats": [{
                    "type": "Muxed",
                    "format_id": "direct",
                    "audio_format_id": None,
                    "height": "Direct",
                    "fps": None,
                    "ext": ext,
                    "vcodec": "unknown",
                    "acodec": "unknown",
                    "size": 0,
                    "merged": False,
                }],
            }

        # Check if this is obviously a direct file URL
        is_direct, detected_ext = _detect_direct(url)

        if is_direct:
            # Skip yt-dlp entirely for direct file URLs
            self._send_json(200, _build_direct_metadata(url, detected_ext))
            return

        # ---------- yt-dlp path for platform URLs (YouTube, etc.) ----------
        import subprocess
        try:
            cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                # yt-dlp failed — last resort: check if it looks direct anyway
                is_direct_retry, ext_retry = _detect_direct(url)
                if is_direct_retry:
                    self._send_json(200, _build_direct_metadata(url, ext_retry))
                elif is_direct_fallback:
                    # Browser sent us this as a direct fallback, and yt-dlp failed
                    self._send_json(200, _build_direct_metadata(url, "mp4"))
                else:
                    self._send_json(500, {"error": stderr.strip() or "Failed to run yt-dlp"})
                return


            metadata = json.loads(stdout)
            
            # Extract fields
            title = metadata.get("title", "Unknown Title")
            thumbnail = metadata.get("thumbnail", "")
            duration_sec = metadata.get("duration") or 0
            uploader = metadata.get("uploader", "Unknown Uploader")
            formats = metadata.get("formats", [])
            
            # Categorize formats
            prog_formats = []
            dash_video_formats = []
            audio_formats = []
            
            for f in formats:
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                
                has_video = vcodec != 'none' and vcodec is not None
                has_audio = acodec != 'none' and acodec is not None
                
                if has_video and has_audio:
                    prog_formats.append(f)
                elif has_video and not has_audio:
                    dash_video_formats.append(f)
                elif not has_video and has_audio:
                    audio_formats.append(f)
                    
            # Find best audio formats (sort by audio bitrate or total bitrate)
            audio_formats.sort(key=lambda x: x.get('abr') or x.get('tbr') or 0, reverse=True)
            best_audio = audio_formats[0] if audio_formats else None
            
            def get_size(f_dict):
                if not f_dict: return 0
                return f_dict.get('filesize') or f_dict.get('filesize_approx') or 0
                
            display_formats = []
            
            # Process Muxed (Progressive)
            seen_prog = set()
            for f in sorted(prog_formats, key=lambda x: (x.get('height') or 0, x.get('fps') or 0), reverse=True):
                key = (f.get('height'), f.get('ext'), f.get('fps'))
                if key not in seen_prog:
                    seen_prog.add(key)
                    display_formats.append({
                        'type': 'Muxed',
                        'format_id': f.get('format_id'),
                        'audio_format_id': None,
                        'height': f.get('height'),
                        'fps': f.get('fps'),
                        'ext': f.get('ext'),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec'),
                        'size': get_size(f),
                        'merged': False
                    })
                    
            # Process DASH Video
            seen_dash = set()
            for f in sorted(dash_video_formats, key=lambda x: (x.get('height') or 0, x.get('fps') or 0), reverse=True):
                key = (f.get('height'), f.get('ext'), f.get('fps'))
                if key not in seen_dash:
                    seen_dash.add(key)
                    
                    vid_ext = f.get('ext')
                    comp_audio = best_audio
                    
                    if vid_ext == 'mp4':
                        m4a_audios = [a for a in audio_formats if a.get('ext') == 'm4a']
                        if m4a_audios: comp_audio = m4a_audios[0]
                    elif vid_ext == 'webm':
                        webm_audios = [a for a in audio_formats if a.get('ext') == 'webm' or a.get('acodec') == 'opus']
                        if webm_audios: comp_audio = webm_audios[0]
                    
                    total_size = get_size(f) + get_size(comp_audio)
                    
                    display_formats.append({
                        'type': 'DASH',
                        'format_id': f.get('format_id'),
                        'audio_format_id': comp_audio.get('format_id') if comp_audio else None,
                        'height': f.get('height'),
                        'fps': f.get('fps'),
                        'ext': f.get('ext'),
                        'vcodec': f.get('vcodec'),
                        'acodec': comp_audio.get('acodec') if comp_audio else 'none',
                        'size': total_size,
                        'merged': True
                    })
                    
            # Process Audio Only (Top 3)
            seen_audio = set()
            audio_count = 0
            for f in audio_formats:
                key = (f.get('ext'), f.get('acodec'))
                if key not in seen_audio and audio_count < 3:
                    seen_audio.add(key)
                    audio_count += 1
                    display_formats.append({
                        'type': 'Audio Only',
                        'format_id': f.get('format_id'),
                        'audio_format_id': None,
                        'height': None,
                        'fps': None,
                        'ext': f.get('ext'),
                        'vcodec': 'none',
                        'acodec': f.get('acodec'),
                        'size': get_size(f),
                        'abr': f.get('abr'),
                        'merged': False
                    })
                    
            def sort_key(x):
                order = {'Muxed': 1, 'DASH': 2, 'Audio Only': 3}
                group_val = order.get(x.get('type'), 4)
                return (group_val, -(x.get('height') or 0), -(x.get('fps') or 0))
                
            display_formats.sort(key=sort_key)
            
            self._send_json(200, {
                "title": title,
                "thumbnail": thumbnail,
                "uploader": uploader,
                "duration": duration_sec,
                "formats": display_formats
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})


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
