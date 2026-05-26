"""
Native multithreaded segmented download engine for direct HTTP files.

This module provides IDM-style segmented downloading using HTTP range requests.
It serves as the secondary backend alongside yt-dlp — handling all non-YouTube
direct file downloads (.mp4, .mkv, .zip, .exe, generic HTTP).

Architecture:
    DirectDownloadTask  →  ChunkManager  →  N worker threads (ThreadPoolExecutor)
                                          →  .partN chunk files on disk
                                          →  .leafdl manifest for resume
                                          →  merge into final file

The DirectDownloadTask mirrors the existing DownloadTask interface so
DownloadCardWindow, DownloadManager, and history all work unchanged.
"""

import os
import json
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Callable
from gi.repository import GLib


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANIFEST_EXT = ".leafdl"
CHUNK_EXT = ".part"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
BUFFER_SIZE = 64 * 1024  # 64 KiB read buffer
MAX_SIMULTANEOUS_DOWNLOADS = 10

# Module-level semaphore to cap concurrent active direct downloads
_download_semaphore = threading.Semaphore(MAX_SIMULTANEOUS_DOWNLOADS)


# ---------------------------------------------------------------------------
# Download Manifest (resume persistence)
# ---------------------------------------------------------------------------

@dataclass
class ChunkState:
    """Persistent state for a single download chunk."""
    index: int
    start_byte: int
    end_byte: int
    bytes_downloaded: int = 0
    status: str = "pending"  # pending | downloading | complete | error

    @property
    def total_bytes(self) -> int:
        return self.end_byte - self.start_byte + 1

    @property
    def current_offset(self) -> int:
        """Byte position to resume from."""
        return self.start_byte + self.bytes_downloaded


@dataclass
class DownloadManifest:
    """
    Persistent manifest file (.leafdl) that tracks the state of a segmented
    download. Enables resume after pause, crash, or app restart.
    """
    url: str
    filename: str
    dest_dir: str
    total_size: int
    chunk_count: int
    supports_ranges: bool
    chunks: List[ChunkState] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    @property
    def manifest_path(self) -> str:
        return os.path.join(self.dest_dir, f"{self.filename}{MANIFEST_EXT}")

    def chunk_path(self, index: int) -> str:
        return os.path.join(self.dest_dir, f"{self.filename}{CHUNK_EXT}{index}")

    def save(self):
        """Persist manifest to disk as JSON."""
        data = {
            "url": self.url,
            "filename": self.filename,
            "dest_dir": self.dest_dir,
            "total_size": self.total_size,
            "chunk_count": self.chunk_count,
            "supports_ranges": self.supports_ranges,
            "created_at": self.created_at,
            "chunks": [asdict(c) for c in self.chunks],
        }
        try:
            with open(self.manifest_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"[DirectDL] Failed to save manifest: {e}")

    @classmethod
    def load(cls, path: str) -> Optional["DownloadManifest"]:
        """Load a manifest from disk. Returns None on failure."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            manifest = cls(
                url=data["url"],
                filename=data["filename"],
                dest_dir=data["dest_dir"],
                total_size=data["total_size"],
                chunk_count=data["chunk_count"],
                supports_ranges=data["supports_ranges"],
                created_at=data.get("created_at", 0),
                chunks=[ChunkState(**c) for c in data["chunks"]],
            )
            return manifest
        except Exception as e:
            print(f"[DirectDL] Failed to load manifest: {e}")
            return None

    def cleanup(self):
        """Remove manifest and all chunk part files from disk."""
        for chunk in self.chunks:
            path = self.chunk_path(chunk.index)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        try:
            if os.path.exists(self.manifest_path):
                os.remove(self.manifest_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Chunk Manager
# ---------------------------------------------------------------------------

class ChunkManager:
    """
    Manages the full lifecycle of a segmented download:
      1. Probe server (HEAD) for size and range support
      2. Split into N chunks with byte ranges
      3. Spawn worker threads to download each chunk
      4. Track progress, handle retries, support pause/resume/cancel
      5. Merge chunks into final output file
    """

    def __init__(self, url: str, dest_dir: str, filename: str, ext: str,
                 chunk_count: int = 4, max_retries: int = 3,
                 timeout: int = 30, on_progress: Callable = None,
                 on_status_change: Callable = None):
        self.url = url
        self.dest_dir = dest_dir
        self.filename = filename
        self.ext = ext
        self.chunk_count = max(1, chunk_count)
        self.max_retries = max_retries
        self.timeout = timeout

        # Callbacks
        self.on_progress = on_progress          # (percent, speed_bytes, eta_str, downloaded, total)
        self.on_status_change = on_status_change  # (status, error_msg)

        # State
        self.manifest: Optional[DownloadManifest] = None
        self.total_size = 0
        self.supports_ranges = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()

        # Speed tracking
        self._speed_samples: List[tuple] = []  # (timestamp, bytes_in_interval)
        self._last_downloaded = 0

        # Ensure dest dir exists
        os.makedirs(self.dest_dir, exist_ok=True)

    def probe_server(self) -> bool:
        """
        Send a HEAD request to determine file size and range support.
        Returns True if probe succeeds.
        """
        try:
            req = urllib.request.Request(self.url, method="HEAD")
            req.add_header("User-Agent", USER_AGENT)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.total_size = int(resp.headers.get("Content-Length", 0))
                accept_ranges = resp.headers.get("Accept-Ranges", "none")
                self.supports_ranges = (accept_ranges.lower() != "none" and self.total_size > 0)
            return True
        except Exception as e:
            # Fallback: try a GET with Range header to test support
            try:
                req = urllib.request.Request(self.url)
                req.add_header("User-Agent", USER_AGENT)
                req.add_header("Range", "bytes=0-0")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 206:
                        self.supports_ranges = True
                        content_range = resp.headers.get("Content-Range", "")
                        if "/" in content_range:
                            try:
                                self.total_size = int(content_range.split("/")[-1])
                            except ValueError:
                                pass
                    else:
                        cl = resp.headers.get("Content-Length")
                        if cl:
                            self.total_size = int(cl)
                return True
            except Exception as e2:
                print(f"[DirectDL] Probe failed: {e2}")
                return False

    def _build_chunks(self):
        """Split file into N byte-range chunks and create manifest."""
        if not self.supports_ranges or self.total_size == 0:
            # Single connection fallback
            self.chunk_count = 1
            chunks = [ChunkState(index=0, start_byte=0, end_byte=max(self.total_size - 1, 0))]
        else:
            chunk_size = self.total_size // self.chunk_count
            chunks = []
            for i in range(self.chunk_count):
                start = i * chunk_size
                end = (start + chunk_size - 1) if i < self.chunk_count - 1 else (self.total_size - 1)
                chunks.append(ChunkState(index=i, start_byte=start, end_byte=end))

        self.manifest = DownloadManifest(
            url=self.url,
            filename=self.filename,
            dest_dir=self.dest_dir,
            total_size=self.total_size,
            chunk_count=self.chunk_count,
            supports_ranges=self.supports_ranges,
            chunks=chunks,
        )
        self.manifest.save()

    def _try_resume(self) -> bool:
        """Check for an existing manifest and resume if possible."""
        manifest_path = os.path.join(self.dest_dir, f"{self.filename}{MANIFEST_EXT}")
        if os.path.exists(manifest_path):
            loaded = DownloadManifest.load(manifest_path)
            if loaded and loaded.url == self.url:
                # Verify chunk files exist for completed chunks
                valid = True
                for chunk in loaded.chunks:
                    if chunk.status == "complete":
                        chunk_path = loaded.chunk_path(chunk.index)
                        if not os.path.exists(chunk_path):
                            valid = False
                            break
                if valid:
                    self.manifest = loaded
                    self.total_size = loaded.total_size
                    self.supports_ranges = loaded.supports_ranges
                    self.chunk_count = loaded.chunk_count
                    # Reset non-complete chunks to pending
                    for chunk in self.manifest.chunks:
                        if chunk.status != "complete":
                            chunk.status = "pending"
                    print(f"[DirectDL] Resuming download: {self.filename}")
                    return True
        return False

    def start(self):
        """Begin or resume the download. Blocks until complete or cancelled."""
        # Try resume first
        if not self._try_resume():
            # Fresh download — probe and build chunks
            if not self.probe_server():
                if self.on_status_change:
                    self.on_status_change("Error", "Failed to connect to server")
                return

            self._build_chunks()

        if self.on_status_change:
            self.on_status_change("Downloading", "")

        # Download all chunks
        success = self._download_all_chunks()

        if self._cancel_flag.is_set():
            return

        if success:
            # Merge chunks into final file
            if self.on_status_change:
                self.on_status_change("Merging", "")

            final_path = self._merge_chunks()
            if final_path:
                self.manifest.cleanup()
                if self.on_status_change:
                    self.on_status_change("Completed", final_path)
            else:
                if self.on_status_change:
                    self.on_status_change("Error", "Failed to merge chunks")
        else:
            # Find which chunks failed
            failed = [c for c in self.manifest.chunks if c.status == "error"]
            msg = f"{len(failed)} chunk(s) failed after {self.max_retries} retries"
            if self.on_status_change:
                self.on_status_change("Error", msg)

    def _download_all_chunks(self) -> bool:
        """Download all pending/error chunks using a thread pool. Returns True if all succeed."""
        pending = [c for c in self.manifest.chunks if c.status != "complete"]
        if not pending:
            return True

        workers = min(len(pending), self.chunk_count)
        all_ok = True

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for chunk in pending:
                future = pool.submit(self._download_chunk, chunk)
                futures[future] = chunk

            # Speed reporting timer
            speed_timer = threading.Thread(target=self._speed_reporter, daemon=True)
            speed_timer.start()

            for future in futures:
                try:
                    result = future.result()
                    if not result:
                        all_ok = False
                except Exception:
                    all_ok = False

        return all_ok

    def _download_chunk(self, chunk: ChunkState) -> bool:
        """Download a single chunk with retry logic. Returns True on success."""
        for attempt in range(self.max_retries + 1):
            if self._cancel_flag.is_set():
                return False

            try:
                chunk.status = "downloading"
                self.manifest.save()

                req = urllib.request.Request(self.url)
                req.add_header("User-Agent", USER_AGENT)

                # Use range header if supported
                if self.supports_ranges and self.total_size > 0:
                    start = chunk.current_offset
                    end = chunk.end_byte
                    if start > end:
                        # Already complete
                        chunk.status = "complete"
                        self.manifest.save()
                        return True
                    req.add_header("Range", f"bytes={start}-{end}")

                chunk_path = self.manifest.chunk_path(chunk.index)
                mode = "ab" if chunk.bytes_downloaded > 0 else "wb"

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    with open(chunk_path, mode) as f:
                        while True:
                            # Check cancel
                            if self._cancel_flag.is_set():
                                chunk.status = "pending"
                                self.manifest.save()
                                return False

                            # Check pause — blocks here while paused
                            self._pause_event.wait()

                            data = resp.read(BUFFER_SIZE)
                            if not data:
                                break

                            f.write(data)
                            with self._lock:
                                chunk.bytes_downloaded += len(data)

                chunk.status = "complete"
                self.manifest.save()
                return True

            except Exception as e:
                print(f"[DirectDL] Chunk {chunk.index} attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                else:
                    chunk.status = "error"
                    self.manifest.save()
                    return False

        return False

    def _speed_reporter(self):
        """Background thread that calculates speed and reports progress every 500ms."""
        while not self._cancel_flag.is_set():
            time.sleep(0.5)

            if self._cancel_flag.is_set():
                break

            # Calculate total downloaded bytes
            with self._lock:
                total_downloaded = sum(c.bytes_downloaded for c in self.manifest.chunks)

            # Speed calculation (3-second rolling window)
            now = time.time()
            bytes_since_last = total_downloaded - self._last_downloaded
            self._last_downloaded = total_downloaded

            self._speed_samples.append((now, bytes_since_last))
            # Keep only last 3 seconds of samples
            self._speed_samples = [(t, b) for t, b in self._speed_samples if now - t <= 3.0]

            total_bytes_in_window = sum(b for _, b in self._speed_samples)
            window_duration = max(now - self._speed_samples[0][0], 0.5) if self._speed_samples else 1.0
            speed_bps = total_bytes_in_window / window_duration if window_duration > 0 else 0

            # Progress
            if self.total_size > 0:
                percent = (total_downloaded / self.total_size) * 100.0
            else:
                percent = 0.0

            # ETA
            remaining = max(self.total_size - total_downloaded, 0)
            if speed_bps > 0:
                eta_secs = remaining / speed_bps
                mins, secs = divmod(int(eta_secs), 60)
                hours, mins = divmod(mins, 60)
                eta_str = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
            else:
                eta_str = "--:--"

            if self.on_progress:
                self.on_progress(percent, speed_bps, eta_str, total_downloaded, self.total_size)

            # Check if all chunks are done
            all_done = all(c.status in ("complete", "error") for c in self.manifest.chunks)
            if all_done:
                break

    def _merge_chunks(self) -> Optional[str]:
        """Merge all chunk files into the final output file. Returns the final path."""
        # Build final filename with extension
        final_name = f"{self.filename}.{self.ext}" if self.ext else self.filename
        final_path = os.path.join(self.dest_dir, final_name)

        # Handle filename collisions
        if os.path.exists(final_path):
            base, ext_part = os.path.splitext(final_path)
            counter = 1
            while os.path.exists(final_path):
                final_path = f"{base} ({counter}){ext_part}"
                counter += 1

        try:
            with open(final_path, "wb") as outfile:
                for chunk in sorted(self.manifest.chunks, key=lambda c: c.index):
                    chunk_path = self.manifest.chunk_path(chunk.index)
                    if not os.path.exists(chunk_path):
                        print(f"[DirectDL] Missing chunk file: {chunk_path}")
                        return None
                    with open(chunk_path, "rb") as infile:
                        while True:
                            data = infile.read(BUFFER_SIZE)
                            if not data:
                                break
                            outfile.write(data)
            return final_path
        except Exception as e:
            print(f"[DirectDL] Merge failed: {e}")
            return None

    def pause(self):
        """Pause all chunk downloads (threads block on the pause event)."""
        self._pause_event.clear()

    def resume(self):
        """Resume paused chunk downloads."""
        self._pause_event.set()

    def cancel(self):
        """Cancel all chunk downloads and clean up."""
        self._cancel_flag.set()
        self._pause_event.set()  # Unblock any paused threads so they can exit

    def get_chunk_progress(self) -> List[float]:
        """Return per-chunk progress as fractions [0.0 - 1.0] for UI rendering."""
        if not self.manifest:
            return []
        result = []
        for chunk in self.manifest.chunks:
            total = chunk.total_bytes
            if total > 0:
                result.append(min(chunk.bytes_downloaded / total, 1.0))
            else:
                result.append(1.0 if chunk.status == "complete" else 0.0)
        return result


# ---------------------------------------------------------------------------
# DirectDownloadTask — drop-in replacement for DownloadTask
# ---------------------------------------------------------------------------

class DirectDownloadTask:
    """
    Download task for direct HTTP files using the segmented engine.

    Implements the same interface as DownloadTask (status, percent, speed,
    pause/resume/cancel, callbacks) so DownloadManager and DownloadCardWindow
    can use it interchangeably.
    """

    def __init__(self, url, title, dest_dir, ext="mp4", resolution=""):
        self.url = url
        self.title = title
        self.dest_dir = dest_dir
        self.ext = ext
        self.resolution = resolution

        # Fields matching DownloadTask interface
        self.format_id = "direct"
        self.audio_format_id = None
        self.status = "Queued"
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.filesize = ""
        self.error_msg = ""
        self.final_filepath = ""

        # Per-chunk progress for the download card UI
        self.chunk_progress: List[float] = []

        self.process = None  # Not used, but keeps interface compat
        self.thread = None
        self.on_update_callbacks = []
        self._chunk_manager: Optional[ChunkManager] = None

    def add_callback(self, callback):
        if callback not in self.on_update_callbacks:
            self.on_update_callbacks.append(callback)

    def set_callback(self, callback):
        self.on_update_callbacks = [callback]

    def _notify(self):
        for cb in self.on_update_callbacks:
            GLib.idle_add(cb, self)

    def start(self):
        self.status = "Downloading"
        self._notify()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def pause(self):
        if self._chunk_manager and self.status == "Downloading":
            self._chunk_manager.pause()
            self.status = "Paused"
            self._notify()

    def resume(self):
        if self._chunk_manager and self.status == "Paused":
            self._chunk_manager.resume()
            self.status = "Downloading"
            self._notify()

    def cancel(self):
        if self.status in ["Downloading", "Paused", "Merging"]:
            if self._chunk_manager:
                self._chunk_manager.cancel()
            self.status = "Cancelled"
            self._notify()

    @staticmethod
    def _format_speed(speed_bytes):
        if speed_bytes >= 1024 ** 3:
            return f"{speed_bytes / (1024 ** 3):.2f}GiB/s"
        elif speed_bytes >= 1024 ** 2:
            return f"{speed_bytes / (1024 ** 2):.2f}MiB/s"
        elif speed_bytes >= 1024:
            return f"{speed_bytes / 1024:.2f}KiB/s"
        return f"{speed_bytes:.2f}B/s"

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.2f} GiB"
        elif size_bytes >= 1024 ** 2:
            return f"{size_bytes / (1024 ** 2):.2f} MiB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KiB"
        return f"{size_bytes} B"

    def _on_progress(self, percent, speed_bps, eta_str, downloaded, total):
        """Callback from ChunkManager — runs in worker thread."""
        self.percent = min(percent, 100.0)
        self.speed = self._format_speed(speed_bps)
        self.eta = eta_str
        self.filesize = self._format_size(total) if total > 0 else "Unknown"

        # Update per-chunk progress for UI
        if self._chunk_manager:
            self.chunk_progress = self._chunk_manager.get_chunk_progress()

        self._notify()

    def _on_status_change(self, status, detail):
        """Callback from ChunkManager — runs in worker thread."""
        if status == "Completed":
            self.status = "Completed"
            self.percent = 100.0
            self.speed = ""
            self.eta = ""
            self.final_filepath = detail  # detail is the final file path
            self._push_to_history()
            self._send_notification()
        elif status == "Error":
            if self.status != "Cancelled":
                self.status = "Error"
                self.error_msg = detail
        elif status == "Merging":
            self.status = "Merging"
            self.percent = 100.0
        elif status == "Downloading":
            self.status = "Downloading"

        self._notify()

    def _worker(self):
        """Main worker thread — acquires semaphore, runs ChunkManager."""
        acquired = _download_semaphore.acquire(timeout=0)
        if not acquired:
            # Wait in queue status
            self.status = "Queued"
            self.error_msg = "Waiting for download slot..."
            self._notify()
            _download_semaphore.acquire()  # Block until a slot opens

        try:
            from leaf_downloader.core.config import ConfigManager
            config = ConfigManager()

            chunk_count = config.get_setting("fragments", 4)
            if not config.get_setting("multithread", False):
                chunk_count = 1
            max_retries = config.get_setting("direct_download_max_retries", 3)
            timeout = config.get_setting("direct_download_timeout", 30)

            self._chunk_manager = ChunkManager(
                url=self.url,
                dest_dir=self.dest_dir,
                filename=self.title,
                ext=self.ext,
                chunk_count=chunk_count,
                max_retries=max_retries,
                timeout=timeout,
                on_progress=self._on_progress,
                on_status_change=self._on_status_change,
            )

            # This blocks until download completes, fails, or is cancelled
            self._chunk_manager.start()

        except Exception as e:
            if self.status != "Cancelled":
                self.status = "Error"
                self.error_msg = str(e)
                self._notify()
        finally:
            _download_semaphore.release()

    def _send_notification(self):
        """Send a desktop notification on download completion."""
        try:
            from gi.repository import Gio
            notification = Gio.Notification.new("Download Completed")
            notification.set_body(f"{self.title} has finished downloading.")
            notification.set_icon(Gio.ThemedIcon.new("folder-download-symbolic"))

            app = Gio.Application.get_default()
            if app:
                app.send_notification(f"download-complete-{id(self)}", notification)
        except Exception as e:
            print(f"[DirectDL] Failed to send notification: {e}")

    def _push_to_history(self):
        """Save completed download to persistent history."""
        from leaf_downloader.core.config import ConfigManager
        config = ConfigManager()
        entry = {
            "url": self.url,
            "title": self.title,
            "format_id": "direct",
            "audio_format_id": None,
            "resolution": self.resolution,
            "dest_dir": self.dest_dir,
            "ext": self.ext,
            "filepath": self.final_filepath,
        }
        config.add_history(entry)
