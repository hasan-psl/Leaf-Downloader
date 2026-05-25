import gi
import re
from gi.repository import Gtk, Gdk, Gio, GLib, Pango

from leaf_downloader.core.config import ConfigManager

class ClipboardPopup(Gtk.Window):
    def __init__(self, app, url, download_callback):
        super().__init__(application=app)
        self.set_title("Clipboard Monitor")
        self.set_default_size(400, 120)
        self.set_resizable(False)
        # Keep above other windows if possible
        self.add_css_class("dialog")
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        label = Gtk.Label(label="<b>Download detected media?</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        box.append(label)
        
        url_label = Gtk.Label(label=url)
        url_label.set_halign(Gtk.Align.START)
        url_label.add_css_class("dim-label")
        url_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(url_label)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(8)
        
        ignore_btn = Gtk.Button(label="Ignore")
        ignore_btn.connect("clicked", self.on_ignore)
        button_box.append(ignore_btn)
        
        download_btn = Gtk.Button(label="Download")
        download_btn.add_css_class("suggested-action")
        download_btn.connect("clicked", lambda x: self.on_download(url, download_callback))
        button_box.append(download_btn)
        
        box.append(button_box)
        self.set_child(box)
        
    def on_ignore(self, btn):
        self.close()
        
    def on_download(self, url, cb):
        self.close()
        cb(url)


class ClipboardMonitor:
    def __init__(self, app):
        self.app = app
        self.config = ConfigManager()
        
        display = Gdk.Display.get_default()
        if display:
            self.clipboard = display.get_clipboard()
            self.clipboard.connect("changed", self.on_clipboard_changed)
            
        self.last_url = None

    def on_clipboard_changed(self, clipboard):
        if not self.config.get_setting("monitor_clipboard", False):
            return
            
        clipboard.read_text_async(None, self.on_text_ready)

    def on_text_ready(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if not text:
                return
            text = text.strip()
            
            is_media = self.is_media_url(text)
            
            if is_media and text != self.last_url:
                self.last_url = text
                self.show_notification(text)
        except Exception as e:
            print(f"[Clipboard Monitor] Error reading clipboard text: {e}")

    def is_media_url(self, text):
        if not text:
            return False
            
        # YouTube
        if re.match(r'^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/.*', text):
            return True
            
        # Reddit
        if re.match(r'^https?://(www\.)?reddit\.com/.*', text):
            return True
            
        # Direct media
        if re.match(r'^https?://.*\.(mp4|webm|mkv|mp3|m4a|avi|ogg|wav)$', text, re.IGNORECASE):
            return True
            
        return False

    def show_notification(self, url):
        # Use a custom popup window to ensure it appears reliably on screen
        popup = ClipboardPopup(self.app, url, self._trigger_download)
        popup.present()

    def _trigger_download(self, url):
        # We can directly trigger the app action
        self.app.activate_action("download-clipboard", GLib.Variant.new_string(url))
