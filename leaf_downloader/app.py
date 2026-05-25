import gi
from gi.repository import Gtk, Adw, Gio, GLib

from leaf_downloader.window import LeafDownloaderWindow
from leaf_downloader.core.clipboard_monitor import ClipboardMonitor
from leaf_downloader.core.api_server import ApiServer
from leaf_downloader.core.config import ConfigManager
from leaf_downloader.ui.new_download_dialog import NewDownloadDialog

class LeafDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.LeafDownloader',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.api_server = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        
        # Keep application running in the background (background-capable)
        self.hold()
        
        # Action for handling download from clipboard
        action = Gio.SimpleAction.new("download-clipboard", GLib.VariantType.new("s"))
        action.connect("activate", self.on_download_clipboard)
        self.add_action(action)
        
        # Action for handling download from browser extension
        ext_action = Gio.SimpleAction.new("download-from-extension", GLib.VariantType.new("s"))
        ext_action.connect("activate", self.on_download_from_extension)
        self.add_action(ext_action)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LeafDownloaderWindow(application=self)
            
            # Initialize clipboard monitoring only once per process
            if not hasattr(self, 'clipboard_monitor') or not self.clipboard_monitor:
                self.clipboard_monitor = ClipboardMonitor(self)
            
            # Start API server for browser extension communication only once per process
            self._start_api_server()
        
        # Enable modern dark mode natively
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        
        win.present()

    def _start_api_server(self):
        """Start the localhost API server if enabled in settings."""
        if hasattr(self, 'api_server') and self.api_server and self.api_server.is_running():
            return
        config = ConfigManager()
        if config.get_setting("api_server_enabled", True):
            port = config.get_setting("api_server_port", 9549)
            self.api_server = ApiServer(port=port)
            self.api_server.start()
            self._start_tray_helper()

    def _start_tray_helper(self):
        """Spawns the system tray icon helper process."""
        if hasattr(self, 'tray_process') and self.tray_process:
            return
            
        import subprocess
        import sys
        import os
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tray_script = os.path.join(current_dir, "core", "tray_helper.py")
        
        try:
            self.tray_process = subprocess.Popen(
                [sys.executable, tray_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("[App] System tray helper process started.")
        except Exception as e:
            print(f"[App] Failed to start system tray helper: {e}")

    def on_download_clipboard(self, action, param):
        url = param.get_string()
        # Withdraw the notification
        self.withdraw_notification("clipboard-url")
        
        self._open_download_dialog(url)

    def on_download_from_extension(self, action, param):
        param_str = param.get_string()
        print(f"[Browser Extension] Download request parameter: {param_str}")
        
        import json
        is_direct = False
        try:
            data = json.loads(param_str)
            if isinstance(data, dict) and "format_id" in data:
                is_direct = True
        except Exception:
            pass

        if is_direct:
            # Start download immediately in background without opening main window!
            from leaf_downloader.core.downloader import DownloadManager
            from leaf_downloader.core.config import ConfigManager
            import os
            
            url = data.get("url")
            title = data.get("title", "Unknown Title")
            format_id = data.get("format_id")
            audio_format_id = data.get("audio_format_id")
            ext = data.get("ext", "mp4")
            resolution = data.get("resolution", "")
            
            default_dir = ConfigManager().get_setting("download_dir", os.path.expanduser("~/Downloads/Leaf"))
            
            DownloadManager().add_download(
                url=url,
                title=title,
                format_id=format_id,
                audio_format_id=audio_format_id,
                dest_dir=default_dir,
                ext=ext,
                start_immediately=True,
                resolution=resolution
            )
            print(f"[Browser Extension] Direct download started for: {title} ({resolution})")
        else:
            # Fallback to legacy behavior: bring the main window to front and open metadata dialog
            win = self.props.active_window
            if not win:
                win = LeafDownloaderWindow(application=self)
            
            win.present()
            self._open_download_dialog(param_str)

    def _open_download_dialog(self, url):
        """Open the New Download Dialog and auto-fetch metadata for a URL."""
        win = self.props.active_window
        if win:
            dialog = NewDownloadDialog(win)
            dialog.present(win)
            dialog.set_url_and_fetch(url)

    def do_shutdown(self):
        """Clean up background processes on application shutdown."""
        if hasattr(self, 'tray_process') and self.tray_process:
            print("[App] Terminating system tray helper process...")
            self.tray_process.terminate()
            self.tray_process = None
            
        if hasattr(self, 'api_server') and self.api_server:
            self.api_server.stop()
            
        Adw.Application.do_shutdown(self)

