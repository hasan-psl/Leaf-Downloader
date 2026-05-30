import gi
import threading
import subprocess
import json
import urllib.request
import re
import sys
from gi.repository import Gtk, Adw, GLib, Gio, GdkPixbuf, Gdk

from leaf_downloader.ui.download_confirm_dialog import DownloadConfirmDialog

class NewDownloadDialog(Adw.Dialog):
    def __init__(self, parent_window):
        super().__init__()
        self.set_title("New Download")
        self.set_content_width(750)
        self.set_content_height(650)
        
        self.parent_window = parent_window

        self.setup_ui()
        
    def setup_ui(self):
        toolbar_view = Adw.ToolbarView()
        
        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_title(False)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *args: self.close())
        header_bar.pack_start(cancel_btn)
        
        title_widget = Adw.WindowTitle(title="New Download")
        header_bar.set_title_widget(title_widget)
        
        toolbar_view.add_top_bar(header_bar)
        
        # Main content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        
        # Input section
        input_group = Adw.PreferencesGroup()
        self.url_entry = Adw.EntryRow(title="Video URL")
        self.url_entry.set_activates_default(True)
        self.url_entry.connect("changed", self.on_url_changed)
        input_group.add(self.url_entry)
        main_box.append(input_group)
        
        # Action button and Spinner
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_box.set_halign(Gtk.Align.CENTER)
        
        self.fetch_btn = Gtk.Button(label="Fetch Metadata")
        self.fetch_btn.add_css_class("suggested-action")
        self.fetch_btn.add_css_class("pill")
        self.fetch_btn.set_sensitive(False)
        self.fetch_btn.connect("clicked", self.on_fetch_clicked)
        action_box.append(self.fetch_btn)
        
        self.spinner = Gtk.Spinner()
        action_box.append(self.spinner)
        
        main_box.append(action_box)
        
        # Error Label
        self.error_label = Gtk.Label()
        self.error_label.add_css_class("error")
        self.error_label.set_visible(False)
        self.error_label.set_wrap(True)
        main_box.append(self.error_label)
        
        # Metadata Section (Hidden initially)
        self.meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.meta_box.set_visible(False)
        self.meta_box.set_vexpand(True)
        
        # Thumbnail and Title box
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        
        # Thumbnail
        self.thumbnail_pic = Gtk.Picture()
        self.thumbnail_pic.set_size_request(160, 90)
        self.thumbnail_pic.set_content_fit(Gtk.ContentFit.COVER)
        info_box.append(self.thumbnail_pic)
        
        # Text details
        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details_box.set_valign(Gtk.Align.CENTER)
        
        self.title_label = Gtk.Label()
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_wrap(True)
        self.title_label.add_css_class("title-4")
        
        self.uploader_label = Gtk.Label()
        self.uploader_label.set_halign(Gtk.Align.START)
        self.uploader_label.add_css_class("dim-label")
        
        self.duration_label = Gtk.Label()
        self.duration_label.set_halign(Gtk.Align.START)
        self.duration_label.add_css_class("dim-label")
        
        details_box.append(self.title_label)
        details_box.append(self.uploader_label)
        details_box.append(self.duration_label)
        
        info_box.append(details_box)
        self.meta_box.append(info_box)
        
        # Formats list
        formats_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        formats_label = Gtk.Label(label="Available Formats")
        formats_label.set_halign(Gtk.Align.START)
        formats_label.add_css_class("heading")
        formats_header_box.append(formats_label)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search formats...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        formats_header_box.append(self.search_entry)
        
        self.meta_box.append(formats_header_box)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.formats_listbox = Gtk.ListBox()
        self.formats_listbox.add_css_class("boxed-list")
        self.formats_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.formats_listbox.set_header_func(self.update_row_header)
        self.formats_listbox.set_filter_func(self.filter_row)
        
        scroll.set_child(self.formats_listbox)
        self.meta_box.append(scroll)
        
        main_box.append(self.meta_box)
        
        toolbar_view.set_content(main_box)
        self.set_child(toolbar_view)
        
    def update_row_header(self, row, before):
        current_group = getattr(row, '_group_name', '')
        before_group = getattr(before, '_group_name', '') if before else None
        
        if not before or current_group != before_group:
            header = Gtk.Label(label=current_group)
            header.set_halign(Gtk.Align.START)
            header.add_css_class("dim-label")
            header.set_margin_top(12)
            header.set_margin_bottom(6)
            header.set_margin_start(12)
            row.set_header(header)
        else:
            row.set_header(None)

    def filter_row(self, row):
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True
        title = row.get_title().lower() if row.get_title() else ""
        subtitle = row.get_subtitle().lower() if row.get_subtitle() else ""
        return search_text in title or search_text in subtitle

    def on_search_changed(self, entry):
        self.formats_listbox.invalidate_filter()

    def on_download_clicked(self, btn, format_id, audio_format_id, ext='mp4', resolution=""):
        url = self.url_entry.get_text().strip()
        title = getattr(self, 'current_title', 'Unknown Video')
        
        confirm = DownloadConfirmDialog(
            parent_window=self.parent_window,
            url=url,
            title=title,
            format_id=format_id,
            audio_format_id=audio_format_id,
            ext=ext,
            resolution=resolution
        )
        confirm.present(self.parent_window)

    def set_url_and_fetch(self, url):
        self.url_entry.set_text(url)
        self.on_fetch_clicked(self.fetch_btn)

    def on_url_changed(self, entry):
        url = entry.get_text().strip()
        # Basic URL validation
        is_valid = re.match(r'^https?://[\w\-]+(\.[\w\-]+)+[/#?]?.*$', url)
        self.fetch_btn.set_sensitive(bool(is_valid))
        
    def on_fetch_clicked(self, btn):
        url = self.url_entry.get_text().strip()
        if not url:
            return
            
        self.fetch_btn.set_sensitive(False)
        self.url_entry.set_sensitive(False)
        self.spinner.start()
        self.error_label.set_visible(False)
        self.meta_box.set_visible(False)
        
        # Clear previous formats
        while child := self.formats_listbox.get_first_child():
            self.formats_listbox.remove(child)
            
        # Run in background
        thread = threading.Thread(target=self._fetch_metadata, args=(url,))
        thread.daemon = True
        thread.start()
        
    def _fetch_metadata(self, url):
        try:
            cmd = [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", url]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise Exception(stderr.strip() or "Unknown error occurred")
                
            data = json.loads(stdout)
            
            # Extract fields
            title = data.get("title", "Unknown Title")
            thumbnail = data.get("thumbnail", "")
            duration_sec = data.get("duration") or 0
            uploader = data.get("uploader", "Unknown Uploader")
            formats = data.get("formats", [])
            
            # Format duration
            mins, secs = divmod(duration_sec, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                duration = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                duration = f"{mins}:{secs:02d}"
                
            # Categorize formats
            prog_formats = []
            dash_video_formats = []
            audio_formats = []
            
            for f in formats:
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                
                has_video = vcodec != 'none' and vcodec is not None
                has_audio = acodec != 'none' and acodec is not None
                
                if has_video and has_audio:
                    prog_formats.append(f)
                elif has_video and not has_audio:
                    dash_video_formats.append(f)
                elif not has_video and has_audio:
                    audio_formats.append(f)
                    
            # Find best audio formats (sort by audio bitrate or total bitrate)
            audio_formats.sort(key=lambda x: x.get('abr') or x.get('tbr') or 0, reverse=True)
            best_audio = audio_formats[0] if audio_formats else None
            
            def get_size(f_dict):
                if not f_dict: return 0
                return f_dict.get('filesize') or f_dict.get('filesize_approx') or 0
                
            display_formats = []
            
            # Process Muxed (Progressive)
            seen_prog = set()
            for f in sorted(prog_formats, key=lambda x: (x.get('height') or 0, x.get('fps') or 0), reverse=True):
                key = (f.get('height'), f.get('ext'), f.get('fps'))
                if key not in seen_prog:
                    seen_prog.add(key)
                    display_formats.append({
                        'type': 'Muxed',
                        'format_id': f.get('format_id'),
                        'audio_format_id': None,
                        'height': f.get('height'),
                        'fps': f.get('fps'),
                        'ext': f.get('ext'),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec'),
                        'size': get_size(f)
                    })
                    
            # Process DASH Video
            seen_dash = set()
            for f in sorted(dash_video_formats, key=lambda x: (x.get('height') or 0, x.get('fps') or 0), reverse=True):
                key = (f.get('height'), f.get('ext'), f.get('fps'))
                if key not in seen_dash:
                    seen_dash.add(key)
                    
                    vid_ext = f.get('ext')
                    comp_audio = best_audio
                    
                    # Match container
                    if vid_ext == 'mp4':
                        m4a_audios = [a for a in audio_formats if a.get('ext') == 'm4a']
                        if m4a_audios: comp_audio = m4a_audios[0]
                    elif vid_ext == 'webm':
                        webm_audios = [a for a in audio_formats if a.get('ext') == 'webm' or a.get('acodec') == 'opus']
                        if webm_audios: comp_audio = webm_audios[0]
                    
                    total_size = get_size(f) + get_size(comp_audio)
                    
                    display_formats.append({
                        'type': 'DASH',
                        'format_id': f.get('format_id'),
                        'audio_format_id': comp_audio.get('format_id') if comp_audio else None,
                        'height': f.get('height'),
                        'fps': f.get('fps'),
                        'ext': f.get('ext'),
                        'vcodec': f.get('vcodec'),
                        'acodec': comp_audio.get('acodec') if comp_audio else 'none',
                        'size': total_size
                    })
                    
            # Process Audio Only (Top 3)
            seen_audio = set()
            audio_count = 0
            for f in audio_formats:
                key = (f.get('ext'), f.get('acodec'))
                if key not in seen_audio and audio_count < 3:
                    seen_audio.add(key)
                    audio_count += 1
                    display_formats.append({
                        'type': 'Audio Only',
                        'format_id': f.get('format_id'),
                        'audio_format_id': None,
                        'height': None,
                        'fps': None,
                        'ext': f.get('ext'),
                        'vcodec': 'none',
                        'acodec': f.get('acodec'),
                        'size': get_size(f),
                        'abr': f.get('abr')
                    })
                    
            # Sort final display list: Muxed -> DASH -> Audio, then highest resolution
            def sort_key(x):
                order = {'Muxed': 1, 'DASH': 2, 'Audio Only': 3}
                group_val = order.get(x.get('type'), 4)
                # Use negative for descending order within groups
                return (group_val, -(x.get('height') or 0), -(x.get('fps') or 0))
                
            display_formats.sort(key=sort_key)
            unique_formats = display_formats
            
            # Download thumbnail
            thumb_file = None
            if thumbnail:
                try:
                    req = urllib.request.Request(thumbnail, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        thumb_bytes = response.read()
                        thumb_file = GLib.Bytes.new(thumb_bytes)
                except Exception as e:
                    print(f"Failed to download thumbnail: {e}")
                    
            GLib.idle_add(self._on_metadata_success, title, uploader, duration, unique_formats, thumb_file)
            
        except Exception as e:
            GLib.idle_add(self._on_metadata_error, str(e))
            
    def _on_metadata_success(self, title, uploader, duration, formats, thumb_bytes):
        self.spinner.stop()
        self.fetch_btn.set_sensitive(True)
        self.url_entry.set_sensitive(True)
        
        self.current_title = title
        self.title_label.set_label(f"<b>{title}</b>")
        self.title_label.set_use_markup(True)
        self.uploader_label.set_label(uploader)
        self.duration_label.set_label(duration)
        
        if thumb_bytes:
            try:
                stream = Gio.MemoryInputStream.new_from_bytes(thumb_bytes)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, 160, 90, True, None)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.thumbnail_pic.set_paintable(texture)
            except Exception as e:
                print(f"Error loading thumbnail pixbuf: {e}")
        else:
            self.thumbnail_pic.set_paintable(None)
            
        for f in formats:
            row = Adw.ActionRow()
            
            ftype = f.get('type')
            ext = f.get('ext', 'unknown')
            size = f.get('size', 0)
            
            size_str = f" - {size / (1024 * 1024):.1f} MB" if size else ""
            sub_elements = []
            
            if ftype in ('DASH', 'Muxed'):
                height = f.get('height') or '?'
                fps = f.get('fps')
                fps_str = f" {fps}fps" if fps else ""
                
                resolution_str = f"{height}p{fps_str} ({ext})"
                row.set_title(f"{resolution_str}{size_str}")
                
                vcodec = f.get('vcodec', 'unknown')
                sub_elements.append(f"Video: {vcodec}")
                
                if ftype == 'Muxed':
                    acodec = f.get('acodec', 'unknown')
                    sub_elements.append(f"Audio: {acodec}")
                    row._group_name = "Video + Audio"
                else:
                    acodec = f.get('acodec', 'unknown')
                    sub_elements.append(f"Audio: {acodec} (Merged)")
                    row._group_name = "Video Only (DASH)"
            else:
                abr = f.get('abr')
                abr_str = f" {abr}kbps" if abr else ""
                resolution_str = f"Audio ({ext}){abr_str}"
                row.set_title(f"{resolution_str}{size_str}")
                
                acodec = f.get('acodec', 'unknown')
                sub_elements.append(f"Audio: {acodec}")
                row._group_name = "Audio Only"
                
            subtitle_text = " | ".join(sub_elements)
            if ftype == 'DASH':
                subtitle_text += "\n⚠️ This format requires merging with ffmpeg."
                
            row.set_subtitle(subtitle_text)
            row.set_subtitle_lines(2)
            
            # Download button
            download_btn = Gtk.Button()
            download_btn.set_icon_name("folder-download-symbolic")
            download_btn.add_css_class("flat")
            download_btn.set_valign(Gtk.Align.CENTER)
            
            format_id = f.get('format_id')
            audio_format_id = f.get('audio_format_id')
            download_btn.connect("clicked", self.on_download_clicked, format_id, audio_format_id, ext, resolution_str)
            
            row.add_suffix(download_btn)
            
            # Store IDs for future downloading
            row._format_id = format_id
            row._audio_format_id = audio_format_id
            
            self.formats_listbox.append(row)
            
        self.meta_box.set_visible(True)
        return False
        
    def _on_metadata_error(self, error_msg):
        self.spinner.stop()
        self.fetch_btn.set_sensitive(True)
        self.url_entry.set_sensitive(True)
        
        self.error_label.set_label(f"Error: {error_msg}")
        self.error_label.set_visible(True)
        return False
