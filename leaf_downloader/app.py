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
            
            # Initialize clipboard monitoring only once per window creation
            self.clipboard_monitor = ClipboardMonitor(self)
            
            # Start API server for browser extension communication
            self._start_api_server()
        
        # Enable modern dark mode natively
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        
        win.present()

    def _start_api_server(self):
        """Start the localhost API server if enabled in settings."""
        config = ConfigManager()
        if config.get_setting("api_server_enabled", True):
            port = config.get_setting("api_server_port", 9549)
            self.api_server = ApiServer(port=port)
            self.api_server.start()

    def on_download_clipboard(self, action, param):
        url = param.get_string()
        # Withdraw the notification
        self.withdraw_notification("clipboard-url")
        
        self._open_download_dialog(url)

    def on_download_from_extension(self, action, param):
        url = param.get_string()
        print(f"[Browser Extension] Download request: {url}")
        
        # Bring the window to front
        win = self.props.active_window
        if win:
            win.present()
        
        self._open_download_dialog(url)

    def _open_download_dialog(self, url):
        """Open the New Download Dialog and auto-fetch metadata for a URL."""
        win = self.props.active_window
        if win:
            dialog = NewDownloadDialog(win)
            dialog.present(win)
            dialog.set_url_and_fetch(url)

