import gi
from gi.repository import Gtk, Adw, GLib, Gio, Pango
import cairo
import re
import os
import subprocess
from leaf_downloader.core.config import ConfigManager

def parse_speed_to_bytes(speed_str):
    if not speed_str:
        return 0
    match = re.match(r'([\d\.]+)(Ki?B/s|Mi?B/s|Gi?B/s|B/s)', speed_str)
    if not match:
        return 0
    val = float(match.group(1))
    unit = match.group(2)
    multiplier = 1
    if unit.startswith('K'):
        multiplier = 1024
    elif unit.startswith('M'):
        multiplier = 1024 ** 2
    elif unit.startswith('G'):
        multiplier = 1024 ** 3
    return val * multiplier

def format_bytes(size):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PiB"

class DownloadCardWindow(Adw.Window):
    def __init__(self, task, **kwargs):
        super().__init__(**kwargs)
        self.task = task
        self.set_title("Download Progress")
        self.set_default_size(550, 320)
        self.set_resizable(False)
        self.add_css_class("dialog")
        
        self.speed_history = [0] * 60  # 60 points of history
        self.max_speed = 1024 # start with 1KB/s min for scale
        self.config = ConfigManager()
        self.fragments = self.config.get_setting("fragments", 4)
        if self.fragments < 1:
            self.fragments = 1
            
        # Animation state
        self.target_percent = 0.0
        self.current_percent = 0.0
        
        # Build UI
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)
        
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_show_end_title_buttons(True)
        self.header_bar.set_show_start_title_buttons(True)
        self.toolbar_view.add_top_bar(self.header_bar)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(24)
        self.toolbar_view.set_content(main_box)
        
        # Header (Title & Status)
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.title_label = Gtk.Label(label=self.task.title)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.add_css_class("title-1")
        header_box.append(self.title_label)
        
        self.status_label = Gtk.Label(label="Starting...")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("dim-label")
        header_box.append(self.status_label)
        main_box.append(header_box)
        
        # Graph Area for Speed
        self.graph_area = Gtk.DrawingArea()
        self.graph_area.set_size_request(-1, 100)
        self.graph_area.set_draw_func(self.draw_graph, None)
        main_box.append(self.graph_area)
        
        # Info Box (Speed, ETA, Size, Downloaded)
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        # Left side
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_box.set_halign(Gtk.Align.START)
        left_box.set_hexpand(True)
        self.eta_label = Gtk.Label(label="ETA: --:--")
        self.eta_label.set_halign(Gtk.Align.START)
        self.downloaded_label = Gtk.Label(label="Downloaded: 0.00%")
        self.downloaded_label.set_halign(Gtk.Align.START)
        self.downloaded_label.add_css_class("dim-label")
        left_box.append(self.eta_label)
        left_box.append(self.downloaded_label)
        
        # Right side
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_box.set_halign(Gtk.Align.END)
        self.size_label = Gtk.Label(label="Total Size: 0 MB")
        self.size_label.set_halign(Gtk.Align.END)
        self.speed_label = Gtk.Label(label="Speed: 0 B/s")
        self.speed_label.set_halign(Gtk.Align.END)
        self.speed_label.add_css_class("dim-label")
        right_box.append(self.size_label)
        right_box.append(self.speed_label)
        
        info_box.append(left_box)
        info_box.append(right_box)
        main_box.append(info_box)
        
        # Segmented Progress
        self.progress_area = Gtk.DrawingArea()
        self.progress_area.set_size_request(-1, 24)
        self.progress_area.set_draw_func(self.draw_progress, None)
        main_box.append(self.progress_area)
        
        # Stack for Controls (Downloading vs Finished)
        self.controls_stack = Gtk.Stack()
        self.controls_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        
        # Downloading Controls
        self.dl_controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.dl_controls_box.set_halign(Gtk.Align.END)
        
        self.pause_btn = Gtk.Button(label="Pause")
        self.pause_btn.connect("clicked", self.on_pause_clicked)
        self.pause_btn.add_css_class("suggested-action")
        
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.connect("clicked", self.on_cancel_clicked)
        self.cancel_btn.add_css_class("destructive-action")
        
        self.dl_controls_box.append(self.pause_btn)
        self.dl_controls_box.append(self.cancel_btn)
        self.controls_stack.add_named(self.dl_controls_box, "downloading")
        
        # Finished Controls
        self.finished_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.finished_box.set_halign(Gtk.Align.END)
        
        self.open_file_btn = Gtk.Button(label="Open File")
        self.open_file_btn.connect("clicked", self.on_open_file_clicked)
        self.open_file_btn.add_css_class("suggested-action")
        
        self.open_folder_btn = Gtk.Button(label="Open Folder")
        self.open_folder_btn.connect("clicked", self.on_open_folder_clicked)
        
        self.close_btn = Gtk.Button(label="Close")
        self.close_btn.connect("clicked", lambda x: self.close())
        
        self.finished_box.append(self.open_file_btn)
        self.finished_box.append(self.open_folder_btn)
        self.finished_box.append(self.close_btn)
        self.controls_stack.add_named(self.finished_box, "finished")
        
        main_box.append(self.controls_stack)
        
        self.task.add_callback(self.on_task_update)
        
        # Set animation and graph update timer
        self.anim_source = GLib.timeout_add(16, self.animate_progress)
        self.graph_source = GLib.timeout_add(1000, self.update_graph_data)
        
        self.connect("close-request", self.on_close_request)
        self.on_task_update(self.task)
        
    def on_close_request(self, window):
        if self.anim_source:
            GLib.source_remove(self.anim_source)
            self.anim_source = None
        if self.graph_source:
            GLib.source_remove(self.graph_source)
            self.graph_source = None
        return False

    def on_pause_clicked(self, btn):
        if self.task.status == "Downloading":
            self.task.pause()
        elif self.task.status == "Paused":
            self.task.resume()
            
    def on_cancel_clicked(self, btn):
        self.task.cancel()
        
    def on_open_file_clicked(self, btn):
        if self.task.final_filepath and os.path.exists(self.task.final_filepath):
            subprocess.Popen(["xdg-open", self.task.final_filepath])
            
    def on_open_folder_clicked(self, btn):
        if self.task.final_filepath and os.path.exists(self.task.final_filepath):
            subprocess.Popen(["xdg-open", os.path.dirname(self.task.final_filepath)])
            
    def on_task_update(self, task):
        self.target_percent = task.percent
        self.status_label.set_label(task.status)
        
        if task.status == "Downloading":
            self.speed_label.set_label(f"Speed: {task.speed}")
            self.eta_label.set_label(f"ETA: {task.eta}")
            self.size_label.set_label(f"Total Size: {task.filesize}")
            self.downloaded_label.set_label(f"Downloaded: {task.percent:.2f}%")
            self.pause_btn.set_label("Pause")
            self.pause_btn.set_sensitive(True)
            self.cancel_btn.set_sensitive(True)
            self.controls_stack.set_visible_child_name("downloading")
            
        elif task.status == "Paused":
            if task.filesize:
                self.size_label.set_label(f"Total Size: {task.filesize}")
            self.downloaded_label.set_label(f"Downloaded: {task.percent:.2f}%")
            self.speed_label.set_label("Speed: 0 B/s")
            self.eta_label.set_label("ETA: Paused")
            self.pause_btn.set_label("Resume")
            self.pause_btn.set_sensitive(True)
            self.cancel_btn.set_sensitive(True)
            self.controls_stack.set_visible_child_name("downloading")
            
        elif task.status in ["Completed", "Error", "Cancelled"]:
            self.speed_label.set_label("")
            self.eta_label.set_label("")
            
            if task.status == "Error":
                self.size_label.set_label("Total Size: Error")
                self.downloaded_label.set_label("Downloaded: Error")
                # Show close button if error
                self.controls_stack.set_visible_child_name("finished")
                self.open_file_btn.set_visible(False)
                self.open_folder_btn.set_visible(False)
            elif task.status == "Completed":
                if task.final_filepath and os.path.exists(task.final_filepath):
                    final_size_bytes = os.path.getsize(task.final_filepath)
                    self.size_label.set_label(f"Total Size: {format_bytes(final_size_bytes)}")
                else:
                    self.size_label.set_label(f"Total Size: {task.filesize}")
                self.downloaded_label.set_label("Downloaded: 100%")
                self.controls_stack.set_visible_child_name("finished")
                self.open_file_btn.set_visible(True)
                self.open_folder_btn.set_visible(True)
            elif task.status == "Cancelled":
                self.size_label.set_label("Total Size: Cancelled")
                self.downloaded_label.set_label(f"Downloaded: {task.percent:.2f}%")
                self.controls_stack.set_visible_child_name("finished")
                self.open_file_btn.set_visible(False)
                self.open_folder_btn.set_visible(False)
                
        elif task.status == "Merging":
            self.speed_label.set_label("")
            self.eta_label.set_label("")
            self.size_label.set_label("Merging formats...")
            self.downloaded_label.set_label("Downloaded: 100%")
            self.pause_btn.set_sensitive(False)
            self.controls_stack.set_visible_child_name("downloading")

    def animate_progress(self):
        diff = self.target_percent - self.current_percent
        if abs(diff) > 0.01:
            # Smooth interpolation
            self.current_percent += diff * 0.1
            self.progress_area.queue_draw()
        elif self.current_percent != self.target_percent:
            self.current_percent = self.target_percent
            self.progress_area.queue_draw()
        return True
        
    def update_graph_data(self):
        if self.task.status == "Downloading":
            speed_bytes = parse_speed_to_bytes(self.task.speed)
            self.speed_history.pop(0)
            self.speed_history.append(speed_bytes)
            
            local_max = max(self.speed_history)
            if local_max > self.max_speed:
                self.max_speed = local_max
            elif local_max < self.max_speed * 0.5 and self.max_speed > 1024:
                # decay max speed gracefully if real speed drops
                self.max_speed = max(local_max * 1.5, 1024)
                
            self.graph_area.queue_draw()
        elif self.task.status in ["Paused", "Completed", "Cancelled", "Error"]:
            self.speed_history.pop(0)
            self.speed_history.append(0)
            self.graph_area.queue_draw()
            
        return True

    def draw_graph(self, area, cr, width, height, user_data=None):
        # Draw background
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.05)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        # Grid lines
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
        cr.set_line_width(1.0)
        for i in range(1, 4):
            y = height * (i / 4.0)
            cr.move_to(0, y)
            cr.line_to(width, y)
            cr.stroke()
            
        points = len(self.speed_history)
        if points < 2:
            return
            
        dx = width / (points - 1)
        
        # Draw filled area
        cr.move_to(0, height)
        for i, val in enumerate(self.speed_history):
            x = i * dx
            # scale value to height
            y = height - (val / self.max_speed) * height if self.max_speed > 0 else height
            # clip to height
            y = max(0, min(height, y))
            cr.line_to(x, y)
            
        cr.line_to(width, height)
        cr.close_path()
        
        # Accent color (Adwaita blue-ish)
        cr.set_source_rgba(0.2, 0.5, 0.9, 0.2)
        cr.fill_preserve()
        
        cr.set_source_rgba(0.2, 0.5, 0.9, 0.8)
        cr.set_line_width(2.0)
        cr.stroke()
        
    def draw_progress(self, area, cr, width, height, user_data=None):
        # Draw IDM style segmented progress bar
        segment_count = self.fragments
        segment_width = (width - (segment_count - 1) * 2) / segment_count
        
        fraction = self.current_percent / 100.0
        filled_width = width * fraction
        
        for i in range(segment_count):
            x = i * (segment_width + 2)
            y = 0
            
            # Segment Background
            cr.set_source_rgba(0.2, 0.2, 0.2, 0.1)
            cr.rectangle(x, y, segment_width, height)
            cr.fill()
            
            # Segment Foreground
            if filled_width > x:
                fill_w = min(segment_width, filled_width - x)
                cr.set_source_rgba(0.1, 0.8, 0.3, 0.8) # Greenish accent
                cr.rectangle(x, y, fill_w, height)
                cr.fill()
                
                # Glossy highlight
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.15)
                cr.rectangle(x, y, fill_w, height / 2)
                cr.fill()
