import gi
from gi.repository import Gtk, Adw

from leaf_downloader.core.downloader import DownloadManager
from leaf_downloader.core.config import ConfigManager

class QueuePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.append(self.stack)
        
        # Empty State
        self.status_page = Adw.StatusPage()
        self.status_page.set_title("Queue Empty")
        self.status_page.set_description("Downloads queued for later will appear here.")
        self.status_page.set_icon_name("view-list-symbolic")
        self.stack.add_named(self.status_page, "empty")
        
        # List State
        self.scroll = Gtk.ScrolledWindow()
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_margin_start(24)
        self.listbox.set_margin_end(24)
        self.listbox.set_margin_top(24)
        self.listbox.set_margin_bottom(24)
        self.scroll.set_child(self.listbox)
        self.stack.add_named(self.scroll, "list")
        
        self.task_row_map = {}
        
        # Load persisted queue
        self.load_persisted_queue()
        
        # Subscribe to new queue additions
        DownloadManager().subscribe_queue(self.on_new_queued_task)
        
    def load_persisted_queue(self):
        config = ConfigManager()
        queue = config.get_queue()
        
        if not queue:
            return
            
        for entry in queue:
            from leaf_downloader.core.downloader import DownloadTask
            task = DownloadTask(
                url=entry.get("url", ""),
                title=entry.get("title", "Unknown"),
                format_id=entry.get("format_id", ""),
                audio_format_id=entry.get("audio_format_id"),
                dest_dir=entry.get("dest_dir", ""),
                ext=entry.get("ext", "mp4")
            )
            DownloadManager().queued_tasks.append(task)
            self._add_queue_row(task)
            
    def on_new_queued_task(self, task):
        self._add_queue_row(task)
        
    def _add_queue_row(self, task):
        row = Adw.ActionRow()
        row.set_title(task.title)
        row.set_subtitle(task.url)
        
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)
        
        # Start Now button
        start_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        start_btn.add_css_class("flat")
        start_btn.set_tooltip_text("Start Now")
        start_btn.connect("clicked", self.on_start_clicked, task, row)
        btn_box.append(start_btn)
        
        # Remove from Queue button
        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.set_tooltip_text("Remove from Queue")
        remove_btn.connect("clicked", self.on_remove_clicked, task, row)
        btn_box.append(remove_btn)
        
        row.add_suffix(btn_box)
        self.listbox.append(row)
        self.task_row_map[task] = row
        
        self.stack.set_visible_child_name("list")
        
    def on_start_clicked(self, btn, task, row):
        # Remove from queue in config
        config = ConfigManager()
        queue = config.get_queue()
        # Find matching entry
        for i, entry in enumerate(queue):
            if entry.get("url") == task.url and entry.get("format_id") == task.format_id:
                config.remove_queue(i)
                break
                
        self.listbox.remove(row)
        self.task_row_map.pop(task, None)
        
        # Start the download
        DownloadManager().start_queued(task)
        
        if not self.task_row_map:
            self.stack.set_visible_child_name("empty")
        
    def on_remove_clicked(self, btn, task, row):
        config = ConfigManager()
        queue = config.get_queue()
        for i, entry in enumerate(queue):
            if entry.get("url") == task.url and entry.get("format_id") == task.format_id:
                config.remove_queue(i)
                break
                
        if task in DownloadManager().queued_tasks:
            DownloadManager().queued_tasks.remove(task)
            
        self.listbox.remove(row)
        self.task_row_map.pop(task, None)
        
        if not self.task_row_map:
            self.stack.set_visible_child_name("empty")
