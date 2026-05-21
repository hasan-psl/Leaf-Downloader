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
        self.append(self.preferences)
        
    def on_multithread_toggled(self, switch, *args):
        active = switch.get_active()
        self.config.set_setting("multithread", active)
        self.fragment_row.set_visible(active)
        
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
