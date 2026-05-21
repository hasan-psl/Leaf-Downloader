import gi
from gi.repository import Gtk, Adw

from leaf_downloader.ui.new_download_dialog import NewDownloadDialog
from leaf_downloader.core.downloader import DownloadManager
from leaf_downloader.ui.download_item import DownloadItemWidget

class DownloadsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        # Persistent + Add Download button at top
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top_bar.set_margin_start(24)
        top_bar.set_margin_end(24)
        top_bar.set_margin_top(12)
        top_bar.set_margin_bottom(0)
        
        add_btn = Gtk.Button()
        add_btn.set_icon_name("list-add-symbolic")
        add_btn.set_label("Add Download")
        add_btn.add_css_class("suggested-action")
        add_btn.add_css_class("pill")
        add_btn.connect("clicked", self.on_new_download)
        top_bar.append(add_btn)
        
        self.append(top_bar)
        
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.append(self.stack)
        
        # Empty State using Adw.StatusPage
        self.status_page = Adw.StatusPage()
        self.status_page.set_title("No Active Downloads")
        self.status_page.set_description("Click '+ Add Download' to start.")
        self.status_page.set_icon_name("folder-download-symbolic")
        self.stack.add_named(self.status_page, "empty")
        
        # List State
        self.scroll = Gtk.ScrolledWindow()
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_margin_start(24)
        self.listbox.set_margin_end(24)
        self.listbox.set_margin_top(12)
        self.listbox.set_margin_bottom(24)
        self.scroll.set_child(self.listbox)
        
        self.stack.add_named(self.scroll, "list")
        
        self.row_map = {}
        DownloadManager().subscribe(self.on_new_download_task)
        
    def on_new_download_task(self, task):
        item = DownloadItemWidget(task, on_completed=self.on_task_completed)
        row = Gtk.ListBoxRow()
        row.set_child(item)
        self.listbox.append(row)
        self.row_map[task] = row
        
        self.stack.set_visible_child_name("list")
        
    def on_task_completed(self, task):
        """Remove completed/cancelled task rows from active list after a delay."""
        row = self.row_map.pop(task, None)
        if row:
            self.listbox.remove(row)
        # If no more active downloads, show empty state
        if not self.row_map:
            self.stack.set_visible_child_name("empty")
        
    def on_new_download(self, btn):
        window = self.get_root()
        if window:
            dialog = NewDownloadDialog(parent_window=window)
            dialog.present(window)
