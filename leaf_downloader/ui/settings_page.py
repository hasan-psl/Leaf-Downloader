import gi
from gi.repository import Gtk, Adw

from leaf_downloader.core.config import ConfigManager

class SettingsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.config = ConfigManager()
        
        self.preferences = Adw.PreferencesPage()
        
        # General Settings Group
        general_group = Adw.PreferencesGroup()
        general_group.set_title("General")
        
        # Download Directory row
        self.row_dir = Adw.EntryRow(title="Download Directory")
        import os
        default_dir = self.config.get_setting("download_dir", os.path.expanduser("~/Downloads/Leaf"))
        self.row_dir.set_text(default_dir)
        self.row_dir.connect("changed", self.on_dir_changed)
        
        # Select folder button
        select_btn = Gtk.Button(icon_name="folder-open-symbolic")
        select_btn.set_valign(Gtk.Align.CENTER)
        select_btn.add_css_class("flat")
        select_btn.connect("clicked", self.on_select_dir_clicked)
        self.row_dir.add_suffix(select_btn)
        
        general_group.add(self.row_dir)
        
        # Monitor Clipboard row
        self.clipboard_row = Adw.SwitchRow()
        self.clipboard_row.set_title("Monitor Clipboard")
        self.clipboard_row.set_subtitle("Automatically detect media URLs copied to clipboard.")
        self.clipboard_row.set_active(self.config.get_setting("monitor_clipboard", False))
        self.clipboard_row.connect("notify::active", self.on_clipboard_toggled)
        general_group.add(self.clipboard_row)
        
        self.preferences.add(general_group)
        
        # Performance Group
        perf_group = Adw.PreferencesGroup()
        perf_group.set_title("Performance")
        perf_group.set_description("Configure download performance options.")
        
        # Multithread Toggle
        self.multithread_row = Adw.SwitchRow()
        self.multithread_row.set_title("Multithread Mode")
        self.multithread_row.set_subtitle("Download multiple fragments concurrently for faster speeds.")
        self.multithread_row.set_active(self.config.get_setting("multithread", False))
        self.multithread_row.connect("notify::active", self.on_multithread_toggled)
        perf_group.add(self.multithread_row)
        
        # Fragment Count Row (visible when multithread is on)
        self.fragment_row = Adw.ActionRow()
        self.fragment_row.set_title("Concurrent Fragments")
        self.fragment_row.set_subtitle("Number of fragments to download simultaneously.")
        
        frag_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        frag_box.set_valign(Gtk.Align.CENTER)
        
        self.fragment_spin = Gtk.SpinButton()
        adjustment = Gtk.Adjustment(value=self.config.get_setting("fragments", 4),
                                    lower=2, upper=32, step_increment=1,
                                    page_increment=4)
        self.fragment_spin.set_adjustment(adjustment)
        self.fragment_spin.set_valign(Gtk.Align.CENTER)
        frag_box.append(self.fragment_spin)
        
        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self.on_apply_fragments)
        frag_box.append(apply_btn)
        
        self.fragment_row.add_suffix(frag_box)
        perf_group.add(self.fragment_row)
        
        # Set initial visibility
        self.fragment_row.set_visible(self.config.get_setting("multithread", False))
        
        self.preferences.add(perf_group)
        
        # Browser Integration Group
        browser_group = Adw.PreferencesGroup()
        browser_group.set_title("Browser Integration")
        browser_group.set_description("Receive download URLs from the Leaf Firefox extension.")
        
        # API Server Toggle
        self.api_server_row = Adw.SwitchRow()
        self.api_server_row.set_title("Extension Server")
        self.api_server_row.set_active(self.config.get_setting("api_server_enabled", True))
        self.api_server_row.connect("notify::active", self.on_api_server_toggled)
        browser_group.add(self.api_server_row)
        
        # Update subtitle based on state
        self._update_api_server_subtitle()
        
        self.preferences.add(browser_group)
        
        self.append(self.preferences)
        
    def _update_api_server_subtitle(self):
        """Update the API server row subtitle to show current status."""
        enabled = self.config.get_setting("api_server_enabled", True)
        port = self.config.get_setting("api_server_port", 9549)
        if enabled:
            self.api_server_row.set_subtitle(f"Listening on 127.0.0.1:{port}")
        else:
            self.api_server_row.set_subtitle("Server disabled. Extension cannot connect.")
        
    def on_multithread_toggled(self, switch, *args):
        active = switch.get_active()
        self.config.set_setting("multithread", active)
        self.fragment_row.set_visible(active)
        
    def on_clipboard_toggled(self, switch, *args):
        active = switch.get_active()
        self.config.set_setting("monitor_clipboard", active)
        
    def on_api_server_toggled(self, switch, *args):
        active = switch.get_active()
        self.config.set_setting("api_server_enabled", active)
        self._update_api_server_subtitle()
        
        # Start or stop the server live
        from gi.repository import Gio
        app = Gio.Application.get_default()
        if app and hasattr(app, 'api_server'):
            if active:
                if not app.api_server or not app.api_server.is_running():
                    from leaf_downloader.core.api_server import ApiServer
                    port = self.config.get_setting("api_server_port", 9549)
                    app.api_server = ApiServer(port=port)
                    app.api_server.start()
            else:
                if app.api_server and app.api_server.is_running():
                    app.api_server.stop()
        
    def on_apply_fragments(self, btn):
        value = int(self.fragment_spin.get_value())
        self.config.set_setting("fragments", value)
        
    def on_dir_changed(self, entry):
        self.config.set_setting("download_dir", entry.get_text().strip())

    def on_select_dir_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Download Directory")
        try:
            from gi.repository import Gio
            initial_folder = Gio.File.new_for_path(self.row_dir.get_text())
            dialog.set_initial_folder(initial_folder)
        except:
            pass
            
        def on_folder_selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    path = folder.get_path()
                    self.row_dir.set_text(path)
                    self.config.set_setting("download_dir", path)
            except Exception:
                pass
                
        window = self.get_root()
        if window:
            dialog.select_folder(window, None, on_folder_selected)

