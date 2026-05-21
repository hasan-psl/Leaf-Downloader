import gi
from gi.repository import Gtk, Adw, Gio

from leaf_downloader.window import LeafDownloaderWindow

class LeafDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.LeafDownloader',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LeafDownloaderWindow(application=self)
        
        # Enable modern dark mode natively
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        
        win.present()
