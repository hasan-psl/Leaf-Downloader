import gi
from gi.repository import Gtk, Adw, Gio

from leaf_downloader.ui.downloads_page import DownloadsPage
from leaf_downloader.ui.queue_page import QueuePage
from leaf_downloader.ui.history_page import HistoryPage
from leaf_downloader.ui.settings_page import SettingsPage

class LeafDownloaderWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Leaf-Downloader")
        self.set_default_size(900, 700)
        
        try:
            # Try Libadwaita 1.4+ NavigationSplitView
            self.split_view = Adw.NavigationSplitView()
            self.set_content(self.split_view)
            
            self.setup_split_view()
        except AttributeError:
            # Fallback for older Libadwaita versions (e.g., Ubuntu 22.04)
            self.setup_fallback_view()

    def setup_split_view(self):
        # Sidebar
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_title(False)
        sidebar_toolbar.add_top_bar(sidebar_header)
        
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("navigation-sidebar")
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        sidebar_toolbar.set_content(scroll)
        
        self.sidebar_page = Adw.NavigationPage.new(sidebar_toolbar, "Sidebar")
        self.sidebar_page.set_title("Menu")
        self.split_view.set_sidebar(self.sidebar_page)
        
        # Content
        self.content_toolbar = Adw.ToolbarView()
        self.content_header = Adw.HeaderBar()
        self.content_toolbar.add_top_bar(self.content_header)
        
        self.window_title = Adw.WindowTitle(title="Downloads")
        self.content_header.set_title_widget(self.window_title)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        
        self.content_toolbar.set_content(self.stack)
        
        self.content_page = Adw.NavigationPage.new(self.content_toolbar, "Content")
        self.split_view.set_content(self.content_page)
        
        self.setup_pages()
        
    def setup_fallback_view(self):
        # A simpler layout using Gtk.Box and Gtk.StackSidebar for older Libadwaita
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        
        self.content_header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="Downloads")
        self.content_header.set_title_widget(self.window_title)
        main_box.append(self.content_header)
        
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(250)
        main_box.append(paned)
        paned.set_vexpand(True)
        
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("navigation-sidebar")
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        scroll.set_size_request(200, -1)
        paned.set_start_child(scroll)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        paned.set_end_child(self.stack)
        
        self.setup_pages()

    def setup_pages(self):
        # Pages
        self.downloads_page = DownloadsPage()
        self.queue_page = QueuePage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage()
        
        self.stack.add_named(self.downloads_page, "downloads")
        self.stack.add_named(self.queue_page, "queue")
        self.stack.add_named(self.history_page, "history")
        self.stack.add_named(self.settings_page, "settings")
        
        # Sidebar rows
        self.add_sidebar_row("Downloads", "folder-download-symbolic", "downloads")
        self.add_sidebar_row("Queue", "view-list-symbolic", "queue")
        self.add_sidebar_row("History", "document-open-recent-symbolic", "history")
        self.add_sidebar_row("Settings", "preferences-system-symbolic", "settings")
        
        self.listbox.connect("row-activated", self.on_row_activated)
        self.listbox.select_row(self.listbox.get_row_at_index(0))
        
    def add_sidebar_row(self, title, icon_name, name):
        row = Gtk.ListBoxRow()
        row.set_name(name)
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        label = Gtk.Label(label=title)
        
        box.append(icon)
        box.append(label)
        row.set_child(box)
        
        self.listbox.append(row)
        
    def on_row_activated(self, listbox, row):
        page_name = row.get_name()
        self.stack.set_visible_child_name(page_name)
        
        titles = {
            "downloads": "Downloads",
            "queue": "Queue",
            "history": "History",
            "settings": "Settings"
        }
        self.window_title.set_title(titles.get(page_name, "Leaf-Downloader"))
        
        # Refresh history when navigating to it
        if page_name == "history" and hasattr(self, 'history_page'):
            self.history_page.refresh()
