import os
import sys
import time
import urllib.request
import urllib.error
import threading
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import AyatanaAppIndicator3 as appindicator

API_BASE = "http://127.0.0.1:9549"

class LeafTrayIcon:
    def __init__(self):
        # Locate icon
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(os.path.dirname(current_dir))
        icon_path = os.path.join(project_dir, "browser_extension", "icons", "icon-48.png")
        if not os.path.exists(icon_path):
            # Fallback icon name
            icon_path = "emblem-downloads"

        # Initialize indicator
        self.indicator = appindicator.Indicator.new(
            "leaf-downloader-indicator",
            icon_path,
            appindicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        
        # Build menu
        self.menu = Gtk.Menu()
        
        show_item = Gtk.MenuItem(label="Show Leaf Downloader")
        show_item.connect("activate", self.on_show)
        self.menu.append(show_item)
        
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)
        
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        
        # Start background ping checker
        self.running = True
        self.ping_thread = threading.Thread(target=self.ping_loop, daemon=True)
        self.ping_thread.start()

    def on_show(self, _):
        threading.Thread(target=self._send_post, args=("/api/show",), daemon=True).start()

    def on_quit(self, _):
        threading.Thread(target=self._send_post, args=("/api/quit",), daemon=True).start()
        # Exit tray itself
        GLib.idle_add(Gtk.main_quit)

    def _send_post(self, path):
        try:
            req = urllib.request.Request(f"{API_BASE}{path}", method="POST")
            urllib.request.urlopen(req, timeout=2)
        except Exception as e:
            print(f"[Tray Helper] Error sending command: {e}")

    def ping_loop(self):
        # Sleep initially to let API server start
        time.sleep(2)
        while self.running:
            try:
                urllib.request.urlopen(f"{API_BASE}/api/ping", timeout=2)
            except urllib.error.URLError:
                # API is offline, main app probably closed
                print("[Tray Helper] Main app offline. Exiting tray...")
                GLib.idle_add(Gtk.main_quit)
                break
            except Exception:
                pass
            time.sleep(3)

def main():
    tray = LeafTrayIcon()
    Gtk.main()

if __name__ == "__main__":
    main()
