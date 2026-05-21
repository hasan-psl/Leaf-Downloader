import gi
import os
import subprocess
from gi.repository import Gtk, Adw, Gio, GLib

from leaf_downloader.core.config import ConfigManager

class HistoryPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.append(self.stack)
        
        # Empty State
        self.status_page = Adw.StatusPage()
        self.status_page.set_title("No History")
        self.status_page.set_description("Completed downloads will appear here.")
        self.status_page.set_icon_name("document-open-recent-symbolic")
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
        
        self.load_history()
        
    def load_history(self):
        # Clear existing rows
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
            
        config = ConfigManager()
        history = config.get_history()
        
        if not history:
            self.stack.set_visible_child_name("empty")
            return
            
        self.stack.set_visible_child_name("list")
        
        for i, entry in enumerate(history):
            row = self._create_history_row(entry, i)
            self.listbox.append(row)
            
    def _create_history_row(self, entry, index):
        row = Adw.ActionRow()
        title = entry.get("title", "Unknown")
        resolution = entry.get("resolution", "")
        if resolution:
            row.set_title(f"{title} [{resolution}]")
        else:
            row.set_title(title)
        
        filepath = entry.get("filepath", "")
        file_exists = os.path.exists(filepath) if filepath else False
        
        if file_exists:
            row.set_subtitle(filepath)
        else:
            row.set_subtitle(f"⚠️ File missing: {filepath}")
            
        # Buttons box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)
        
        if file_exists:
            # Open File button
            open_file_btn = Gtk.Button(icon_name="document-open-symbolic")
            open_file_btn.add_css_class("flat")
            open_file_btn.set_tooltip_text("Open File")
            open_file_btn.connect("clicked", self.on_open_file, filepath)
            btn_box.append(open_file_btn)
            
            # Open Folder button
            open_folder_btn = Gtk.Button(icon_name="folder-open-symbolic")
            open_folder_btn.add_css_class("flat")
            open_folder_btn.set_tooltip_text("Open Folder")
            open_folder_btn.connect("clicked", self.on_open_folder, filepath)
            btn_box.append(open_folder_btn)
        else:
            # Re-download button
            redownload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
            redownload_btn.add_css_class("flat")
            redownload_btn.set_tooltip_text("Re-download")
            redownload_btn.connect("clicked", self.on_redownload, entry)
            btn_box.append(redownload_btn)
        
        # Remove button
        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.set_tooltip_text("Remove")
        remove_btn.connect("clicked", self.on_remove_clicked, index, filepath, file_exists)
        btn_box.append(remove_btn)
        
        row.add_suffix(btn_box)
        
        return row
        
    def on_open_file(self, btn, filepath):
        try:
            uri = GLib.filename_to_uri(filepath, None)
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception as e:
            # Fallback: try xdg-open
            try:
                subprocess.Popen(["xdg-open", filepath])
            except Exception as e2:
                print(f"Failed to open file: {e2}")
            
    def on_open_folder(self, btn, filepath):
        try:
            # Use dbus to open folder and highlight file in GNOME Files
            folder = os.path.dirname(filepath)
            uri = GLib.filename_to_uri(filepath, None)
            subprocess.Popen(["dbus-send", "--session", "--dest=org.freedesktop.FileManager1",
                              "--type=method_call", "/org/freedesktop/FileManager1",
                              "org.freedesktop.FileManager1.ShowItems",
                              f"array:string:{uri}", "string:"])
        except Exception:
            # Fallback: just open the folder
            try:
                folder = os.path.dirname(filepath)
                subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                print(f"Failed to open folder: {e}")
            
    def on_redownload(self, btn, entry):
        window = self.get_root()
        if window:
            from leaf_downloader.ui.download_confirm_dialog import DownloadConfirmDialog
            dialog = DownloadConfirmDialog(
                parent_window=window,
                url=entry.get("url", ""),
                title=entry.get("title", "Unknown"),
                format_id=entry.get("format_id", ""),
                audio_format_id=entry.get("audio_format_id"),
                ext=entry.get("ext", "mp4"),
                resolution=entry.get("resolution", "")
            )
            dialog.present(window)
            
    def on_remove_clicked(self, btn, index, filepath, file_exists):
        window = self.get_root()
        if not window:
            return
            
        dialog = Adw.MessageDialog(parent=window, heading="Remove Download",
                                   body="How would you like to remove this entry?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("history", "Remove History Only")
        
        if file_exists:
            dialog.add_response("both", "Remove File & History")
            dialog.set_response_appearance("both", Adw.ResponseAppearance.DESTRUCTIVE)
        
        def on_response(dlg, response):
            if response == "history":
                ConfigManager().remove_history(index)
                self.load_history()
            elif response == "both":
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Failed to delete file: {e}")
                ConfigManager().remove_history(index)
                self.load_history()
                
        dialog.connect("response", on_response)
        dialog.present()
        
    def refresh(self):
        """Called when the page becomes visible to re-check file existence."""
        self.load_history()
