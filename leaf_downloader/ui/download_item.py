import gi
from gi.repository import Gtk, GLib
import gi as _gi
_gi.require_version('Pango', '1.0')
from gi.repository import Pango

class DownloadItemWidget(Gtk.Box):
    def __init__(self, task, on_completed=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        
        self.task = task
        self.on_completed = on_completed
        self.task.add_callback(self.update_ui)
        
        # Top line: Title and Status
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        self.title_label = Gtk.Label(label=self.task.title)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_hexpand(True)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.add_css_class("heading")
        top_box.append(self.title_label)
        
        self.status_label = Gtk.Label(label=self.task.status)
        self.status_label.add_css_class("dim-label")
        top_box.append(self.status_label)
        
        self.append(top_box)
        
        # Progress Bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.append(self.progress_bar)
        
        # Bottom line: Stats and Controls
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        self.stats_label = Gtk.Label(label="")
        self.stats_label.set_halign(Gtk.Align.START)
        self.stats_label.set_hexpand(True)
        self.stats_label.add_css_class("dim-label")
        bottom_box.append(self.stats_label)
        
        # Controls
        self.pause_btn = Gtk.Button()
        self.pause_btn.set_icon_name("media-playback-pause-symbolic")
        self.pause_btn.add_css_class("flat")
        self.pause_btn.connect("clicked", self.on_pause_clicked)
        bottom_box.append(self.pause_btn)
        
        self.cancel_btn = Gtk.Button()
        self.cancel_btn.set_icon_name("process-stop-symbolic")
        self.cancel_btn.add_css_class("flat")
        self.cancel_btn.add_css_class("error")
        self.cancel_btn.connect("clicked", self.on_cancel_clicked)
        bottom_box.append(self.cancel_btn)
        
        self.append(bottom_box)
        
        # Initial UI update
        self.update_ui(self.task)
        
    def on_pause_clicked(self, btn):
        if self.task.status == "Downloading":
            self.task.pause()
        elif self.task.status == "Paused":
            self.task.resume()
            
    def on_cancel_clicked(self, btn):
        self.task.cancel()
        
    def update_ui(self, task):
        self.status_label.set_label(task.status)
        self.progress_bar.set_fraction(task.percent / 100.0)
        
        if task.status == "Downloading":
            self.stats_label.set_label(f"{task.filesize} • {task.speed} • ETA: {task.eta}")
            self.pause_btn.set_icon_name("media-playback-pause-symbolic")
            self.pause_btn.set_sensitive(True)
            self.cancel_btn.set_sensitive(True)
            
        elif task.status == "Paused":
            if task.filesize:
                self.stats_label.set_label(f"{task.filesize} • Paused")
            else:
                self.stats_label.set_label("Paused")
            self.pause_btn.set_icon_name("media-playback-start-symbolic")
            self.pause_btn.set_sensitive(True)
            self.cancel_btn.set_sensitive(True)
            
        elif task.status in ["Completed", "Error", "Cancelled"]:
            if task.status == "Error":
                self.stats_label.set_label(task.error_msg)
            elif task.status == "Completed":
                self.stats_label.set_label("Download finished successfully.")
            elif task.status == "Cancelled":
                self.stats_label.set_label("Download was cancelled.")
                
            self.pause_btn.set_sensitive(False)
            self.cancel_btn.set_sensitive(False)
            
            # Remove from active list after a short delay
            if self.on_completed and task.status in ["Completed", "Cancelled"]:
                GLib.timeout_add(2000, self._fire_completed)
            
        elif task.status == "Merging":
            self.stats_label.set_label("Merging streams with ffmpeg...")
            self.pause_btn.set_sensitive(False)
            self.progress_bar.set_fraction(1.0)
            
    def _fire_completed(self):
        if self.on_completed:
            self.on_completed(self.task)
        return False
