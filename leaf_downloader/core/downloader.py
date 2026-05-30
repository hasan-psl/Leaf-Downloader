import threading
import subprocess
import os
import signal
import re
import glob
import time
from gi.repository import GLib

class DownloadTask:
    def __init__(self, url, title, format_id, audio_format_id, dest_dir, ext='mp4', resolution=""):
        self.url = url
        self.title = title
        self.format_id = format_id
        self.audio_format_id = audio_format_id
        self.resolution = resolution
        self.dest_dir = dest_dir
        self.ext = ext
        
        self.status = "Queued" # Queued, Downloading, Paused, Merging, Completed, Error, Cancelled
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.filesize = ""
        self.error_msg = ""
        self.final_filepath = ""
        
        self._raw_speed_history = []
        
        self.process = None
        self.thread = None
        self.on_update_callbacks = []
        
    def add_callback(self, callback):
        if callback not in self.on_update_callbacks:
            self.on_update_callbacks.append(callback)
            
    def set_callback(self, callback):
        # For backward compatibility, clear and add
        self.on_update_callbacks = [callback]
        
    def _notify(self):
        for cb in self.on_update_callbacks:
            GLib.idle_add(cb, self)
            
    def start(self):
        self.status = "Downloading"
        self._notify()
        self.thread = threading.Thread(target=self._worker)
        self.thread.daemon = True
        self.thread.start()
        
    def pause(self):
        if self.process and self.status == "Downloading":
            try:
                os.kill(self.process.pid, signal.SIGSTOP)
                self.status = "Paused"
                self._notify()
            except Exception as e:
                print(f"Failed to pause: {e}")
            
    def resume(self):
        if self.process and self.status == "Paused":
            try:
                os.kill(self.process.pid, signal.SIGCONT)
                self.status = "Downloading"
                self._notify()
            except Exception as e:
                print(f"Failed to resume: {e}")
            
    def cancel(self):
        if self.status in ["Downloading", "Paused", "Merging"]:
            if self.status == "Paused":
                try:
                    os.kill(self.process.pid, signal.SIGCONT)
                except:
                    pass
            try:
                os.kill(self.process.pid, signal.SIGTERM)
            except:
                pass
            self.status = "Cancelled"
            self._notify()
            
    def _parse_speed_bytes(self, speed_str):
        if not speed_str: return 0
        match = re.match(r'([\d\.]+)([KMGT]?i?B/s|B/s)', speed_str)
        if not match: return 0
        val = float(match.group(1))
        unit = match.group(2)
        multiplier = 1
        if unit.startswith('K'): multiplier = 1024
        elif unit.startswith('M'): multiplier = 1024**2
        elif unit.startswith('G'): multiplier = 1024**3
        return val * multiplier
        
    def _format_speed(self, speed_bytes):
        if speed_bytes >= 1024**3: return f"{speed_bytes/(1024**3):.2f}GiB/s"
        elif speed_bytes >= 1024**2: return f"{speed_bytes/(1024**2):.2f}MiB/s"
        elif speed_bytes >= 1024: return f"{speed_bytes/1024:.2f}KiB/s"
        return f"{speed_bytes:.2f}B/s"
            
    def _worker(self):
        from leaf_downloader.core.config import ConfigManager
        config = ConfigManager()
        
        formats = self.format_id
        # Build output template: user-edited name with static ext
        out_template = f"{self.title}.%(ext)s"
            
        import sys
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--newline",
            "-P", self.dest_dir,
            "-o", out_template
        ]
        
        if formats and formats != "direct":
            formats_str = formats
            if self.audio_format_id:
                formats_str += f"+{self.audio_format_id}"
            cmd.extend(["-f", formats_str])
            
        cmd.append(self.url)
        
        # Add multithreading if enabled
        if config.get_setting("multithread", False):
            fragments = config.get_setting("fragments", 4)
            cmd.insert(-1, "--concurrent-fragments")
            cmd.insert(-1, str(fragments))
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            prog_regex = re.compile(r'\[download\]\s+(?P<percent>[\d\.]+)%\s+of\s+(?:~?\s*)(?P<size>\S+)\s+at\s+(?:~?\s*)(?P<speed>\S+)\s+ETA\s+(?P<eta>[\d:]+)')
            merge_regex = re.compile(r'Merging formats into')
            already_downloaded_regex = re.compile(r'has already been downloaded')
            destination_regex = re.compile(r'\[(?:download|Merger)\]\s+(?:Destination:\s+)?(.+)')
            
            for line in self.process.stdout:
                if self.status == "Cancelled":
                    break
                    
                match = prog_regex.search(line)
                if match:
                    self.percent = float(match.group('percent'))
                    self.filesize = match.group('size')
                    
                    raw_speed = match.group('speed')
                    speed_bytes = self._parse_speed_bytes(raw_speed)
                    
                    now = time.time()
                    self._raw_speed_history.append((now, speed_bytes))
                    # filter last 1 second
                    self._raw_speed_history = [(t, s) for t, s in self._raw_speed_history if now - t <= 1.0]
                    
                    if self._raw_speed_history:
                        avg_speed = sum(s for t, s in self._raw_speed_history) / len(self._raw_speed_history)
                        self.speed = self._format_speed(avg_speed)
                    else:
                        self.speed = raw_speed
                        
                    self.eta = match.group('eta')
                    self._notify()
                elif merge_regex.search(line):
                    self.status = "Merging"
                    self.percent = 100.0
                    self._notify()
                elif already_downloaded_regex.search(line):
                    self.percent = 100.0
                    
                # Try to capture final file path
                dest_match = destination_regex.search(line)
                if dest_match:
                    self.final_filepath = dest_match.group(1).strip().strip('"').strip("'")
                    
            self.process.wait()
            
            if self.status == "Cancelled":
                return
                
            if self.process.returncode == 0:
                self.status = "Completed"
                self.percent = 100.0
                self.speed = ""
                self.eta = ""
                
                # Try to find the final file if we didn't capture it
                if not self.final_filepath or not os.path.exists(self.final_filepath):
                    escaped_title = glob.escape(self.title)
                    pattern = os.path.join(glob.escape(self.dest_dir), f"{escaped_title}.*")
                    matches = glob.glob(pattern)
                    if matches:
                        self.final_filepath = matches[0]
                
                # Push to history
                self._push_to_history()
                self._send_notification()
            else:
                self.status = "Error"
                self.error_msg = f"yt-dlp exited with code {self.process.returncode}"
                
            self._notify()
            
        except Exception as e:
            if self.status != "Cancelled":
                self.status = "Error"
                self.error_msg = str(e)
                self._notify()
                
    def _send_notification(self):
        try:
            from gi.repository import Gio
            notification = Gio.Notification.new("Download Completed")
            notification.set_body(f"{self.title} has finished downloading.")
            notification.set_icon(Gio.ThemedIcon.new("folder-download-symbolic"))
            
            # Get the application instance
            app = Gio.Application.get_default()
            if app:
                app.send_notification(f"download-complete-{id(self)}", notification)
        except Exception as e:
            print(f"Failed to send notification: {e}")
                
    def _push_to_history(self):
        from leaf_downloader.core.config import ConfigManager
        config = ConfigManager()
        entry = {
            "url": self.url,
            "title": self.title,
            "format_id": self.format_id,
            "audio_format_id": self.audio_format_id,
            "resolution": self.resolution,
            "dest_dir": self.dest_dir,
            "ext": self.ext,
            "filepath": self.final_filepath
        }
        config.add_history(entry)

class DownloadManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tasks = []
            cls._instance.queued_tasks = []
            cls._instance.callbacks = []
            cls._instance.history_callbacks = []
            cls._instance.queue_callbacks = []
            cls._instance.active_windows = []
        return cls._instance
        
    def add_download(self, url, title, format_id, audio_format_id, dest_dir, ext='mp4', start_immediately=True, resolution=""):
        # Route direct HTTP downloads to the native segmented engine,
        # everything else (YouTube, etc.) goes through yt-dlp
        if format_id == "direct":
            from leaf_downloader.core.direct_downloader import DirectDownloadTask
            task = DirectDownloadTask(url, title, dest_dir, ext, resolution)
        else:
            task = DownloadTask(url, title, format_id, audio_format_id, dest_dir, ext, resolution)
        
        if start_immediately:
            self.tasks.append(task)
            for cb in self.callbacks:
                GLib.idle_add(cb, task)
            self._spawn_download_window(task)
            task.start()
        else:
            # Queue it
            self.queued_tasks.append(task)
            from leaf_downloader.core.config import ConfigManager
            ConfigManager().add_queue({
                "url": url,
                "title": title,
                "format_id": format_id,
                "audio_format_id": audio_format_id,
                "resolution": resolution,
                "dest_dir": dest_dir,
                "ext": ext
            })
            for cb in self.queue_callbacks:
                GLib.idle_add(cb, task)
                
    def start_queued(self, task):
        if task in self.queued_tasks:
            self.queued_tasks.remove(task)
            self.tasks.append(task)
            for cb in self.callbacks:
                GLib.idle_add(cb, task)
            self._spawn_download_window(task)
            task.start()
            
    def _spawn_download_window(self, task):
        try:
            from leaf_downloader.ui.download_card_window import DownloadCardWindow
            from gi.repository import Gio
            
            app = Gio.Application.get_default()
            win = DownloadCardWindow(task, application=app)
            self.active_windows.append(win)
            
            # Remove window from list when it closes
            win.connect("close-request", lambda w: self.active_windows.remove(w) if w in self.active_windows else False)
            win.present()
        except Exception as e:
            print(f"Failed to spawn download card window: {e}")
        
    def subscribe(self, callback):
        self.callbacks.append(callback)
        # Notify about existing tasks
        for task in self.tasks:
            callback(task)
            
    def subscribe_history(self, callback):
        self.history_callbacks.append(callback)
        
    def subscribe_queue(self, callback):
        self.queue_callbacks.append(callback)
        for task in self.queued_tasks:
            callback(task)
