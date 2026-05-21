import gi
import os
from gi.repository import Gtk, Adw, GLib, Gio

from leaf_downloader.core.downloader import DownloadManager

class DownloadConfirmDialog(Adw.Dialog):
    def __init__(self, parent_window, url, title, format_id, audio_format_id, ext, resolution=""):
        super().__init__()
        self.set_title("Download Info")
        self.set_content_width(550)
        
        self.parent_window = parent_window
        self.url = url
        self.title = title
        self.format_id = format_id
        self.audio_format_id = audio_format_id
        self.ext = ext
        self.resolution = resolution
        
        self.setup_ui()
        
    def setup_ui(self):
        toolbar_view = Adw.ToolbarView()
        
        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_title(False)
        title_widget = Adw.WindowTitle(title="Save As")
        header_bar.set_title_widget(title_widget)
        toolbar_view.add_top_bar(header_bar)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        
        pref_group = Adw.PreferencesGroup()
        
        # URL Row
        self.url_row = Adw.EntryRow(title="Download Link")
        self.url_row.set_text(self.url)
        self.url_row.set_editable(True)
        
        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_btn.set_valign(Gtk.Align.CENTER)
        copy_btn.add_css_class("flat")
        copy_btn.connect("clicked", self.on_copy_url)
        self.url_row.add_suffix(copy_btn)
        
        paste_btn = Gtk.Button(icon_name="edit-paste-symbolic")
        paste_btn.set_valign(Gtk.Align.CENTER)
        paste_btn.add_css_class("flat")
        paste_btn.connect("clicked", self.on_paste_url)
        self.url_row.add_suffix(paste_btn)
        pref_group.add(self.url_row)
        
        # Filename Row
        self.name_row = Adw.EntryRow(title="File Name")
        default_title = self.title
        if self.resolution:
            default_title = f"{self.title} [{self.resolution}]"
        self.name_row.set_text(default_title)
        
        ext_label = Gtk.Label(label=f".{self.ext}")
        ext_label.set_valign(Gtk.Align.CENTER)
        ext_label.add_css_class("dim-label")
        ext_label.set_margin_end(12)
        self.name_row.add_suffix(ext_label)
        pref_group.add(self.name_row)
        
        # Path Row
        self.path_row = Adw.EntryRow(title="Save To")
        # Default path
        from leaf_downloader.core.config import ConfigManager
        default_dir = ConfigManager().get_setting("download_dir", os.path.expanduser("~/Downloads/Leaf"))
        self.path_row.set_text(default_dir)
        
        browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.add_css_class("flat")
        browse_btn.connect("clicked", self.on_browse_clicked)
        self.path_row.add_suffix(browse_btn)
        pref_group.add(self.path_row)
        
        main_box.append(pref_group)
        
        # Error Label
        self.error_label = Gtk.Label()
        self.error_label.add_css_class("error")
        self.error_label.set_visible(False)
        main_box.append(self.error_label)
        
        # Bottom Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(16)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *args: self.close())
        btn_box.append(cancel_btn)
        
        later_btn = Gtk.Button(label="Download Later")
        later_btn.connect("clicked", self.on_download_later)
        btn_box.append(later_btn)
        
        now_btn = Gtk.Button(label="Download Now")
        now_btn.add_css_class("suggested-action")
        now_btn.connect("clicked", self.on_download_now)
        btn_box.append(now_btn)
        
        main_box.append(btn_box)
        
        toolbar_view.set_content(main_box)
        self.set_child(toolbar_view)
        
    def on_copy_url(self, btn):
        clipboard = self.get_clipboard()
        clipboard.set(self.url_row.get_text())
        
    def on_paste_url(self, btn):
        clipboard = self.get_clipboard()
        clipboard.read_text_async(None, self.on_paste_ready)
        
    def on_paste_ready(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self.url_row.set_text(text)
        except Exception:
            pass
            
    def on_browse_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Download Directory")
        try:
            initial_folder = Gio.File.new_for_path(self.path_row.get_text())
            dialog.set_initial_folder(initial_folder)
        except:
            pass
            
        def on_folder_selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self.path_row.set_text(folder.get_path())
            except GLib.Error:
                pass
                
        dialog.select_folder(self.parent_window, None, on_folder_selected)
        
    def _validate(self):
        self.error_label.set_visible(False)
        path = self.path_row.get_text().strip()
        if not path:
            self.error_label.set_label("Save path cannot be empty.")
            self.error_label.set_visible(True)
            return False
            
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except Exception as e:
                self.error_label.set_label(f"Invalid path: {e}")
                self.error_label.set_visible(True)
                return False
                
        if not os.access(path, os.W_OK):
            self.error_label.set_label("Path is not writable.")
            self.error_label.set_visible(True)
            return False
            
        return True
        
    def on_download_now(self, btn):
        if not self._validate():
            return
            
        final_url = self.url_row.get_text().strip()
        final_name = self.name_row.get_text().strip()
        final_path = self.path_row.get_text().strip()
        
        DownloadManager().add_download(
            url=final_url,
            title=final_name,
            format_id=self.format_id,
            audio_format_id=self.audio_format_id,
            dest_dir=final_path,
            ext=self.ext,
            start_immediately=True,
            resolution=self.resolution
        )
        self.close()
        
    def on_download_later(self, btn):
        if not self._validate():
            return
            
        # Warning about link expiration
        dialog = Adw.MessageDialog(parent=self.parent_window, heading="Link Expiration Warning",
                                   body="The download link for this specific format might expire if not downloaded soon. Do you still want to add it to the queue?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("queue", "Queue Anyway")
        dialog.set_response_appearance("queue", Adw.ResponseAppearance.SUGGESTED)
        
        def on_response(dlg, response):
            if response == "queue":
                final_url = self.url_row.get_text().strip()
                final_name = self.name_row.get_text().strip()
                final_path = self.path_row.get_text().strip()
                
                DownloadManager().add_download(
                    url=final_url,
                    title=final_name,
                    format_id=self.format_id,
                    audio_format_id=self.audio_format_id,
                    dest_dir=final_path,
                    ext=self.ext,
                    start_immediately=False,
                    resolution=self.resolution
                )
                self.close()
                
        dialog.connect("response", on_response)
        dialog.present()
