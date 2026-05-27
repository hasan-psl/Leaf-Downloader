<div align="center">
  <h1>🍃 Leaf-Downloader</h1>
  <p><strong>A modern, native Linux download manager inspired by IDM, built for the GNOME desktop.</strong></p>

  ![Status Beta](https://img.shields.io/badge/Status-Beta-orange?style=for-the-badge)
  ![Python Version](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
  ![GTK4 Libadwaita](https://img.shields.io/badge/GTK4-Libadwaita-green?style=for-the-badge)
  ![yt-dlp](https://img.shields.io/badge/Powered%20By-yt--dlp-red?style=for-the-badge&logo=youtube)
  ![License GPLv3](https://img.shields.io/badge/License-GPLv3-blue?style=for-the-badge)
</div>

<br>

Welcome to **Leaf-Downloader**, a high-performance desktop download manager designed specifically for Linux. By combining a custom native segmented download engine with `yt-dlp` and the elegance of GTK4 and Libadwaita, Leaf-Downloader delivers a blazing-fast, visually stunning, and deeply integrated downloading experience — right at home on GNOME.

---

<img width="950" height="750" alt="App Home - Download Dashboard" src="https://github.com/user-attachments/assets/d3f71ab7-87b4-4870-b7ed-524e304376fa" /> <img width="442" height="507" alt="image" src="https://github.com/user-attachments/assets/9698dd60-4510-4b3f-993e-9a5273f383b5" /> <img width="552" height="424" alt="InShot_20260527_141021462" src="https://github.com/user-attachments/assets/69c4c30c-d3fe-4930-abe0-3b8c80e2d855" />

---

## ✨ Features

### 🚀 Dual Download Engine
Leaf-Downloader operates two independent download backends that are automatically selected for you:

- **Native Segmented Engine** (`direct_downloader.py`): A custom-built, IDM-style HTTP download engine using byte-range requests. Splits files into multiple chunks downloaded in parallel via a `ThreadPoolExecutor`. Features:
  - Automatic server probing (`HEAD` / ranged `GET`) to detect file size and range support
  - Configurable chunk count (2–32 simultaneous segments)
  - Per-chunk retry logic with exponential backoff (up to 3 retries by default)
  - **Pause, resume, and cancel** with full thread-safe control
  - **Resume after crash** — a `.leafdl` manifest file persists the download state to disk so interrupted downloads can pick up exactly where they left off
  - 3-second rolling-window speed calculation for stable speed readouts
  - Desktop notification on completion (via `Gio.Notification`)
  - Global semaphore limits concurrent downloads to 10 to prevent overload

<img width="984" height="752" alt="Download card highlight at 40fps" src="https://github.com/user-attachments/assets/9eca25b5-28fb-4c72-bdc1-56f6e394d090" />


- **yt-dlp Backend** (`downloader.py`): Full `yt-dlp` integration for all platform-hosted media. Features:
  - Supports **YouTube, Instagram, Facebook, X/Twitter, TikTok, Reddit, Dailymotion, Vimeo**, and hundreds more yt-dlp-compatible sites
  - Muxed (progressive), DASH video-only, and audio-only format selection
  - Automatic best-audio pairing for DASH video streams
  - Concurrent fragment downloading via `--concurrent-fragments`
  - Smooth 1-second moving-average speed stabilization
  - SIGSTOP/SIGCONT-based pause and resume of the yt-dlp subprocess

> The `DownloadManager` routes automatically: URLs with `format_id = "direct"` go to the native engine; everything else goes through `yt-dlp`.

---

### 🦊 Smart Firefox Browser Extension (Manifest V3)

A fully functional, feature-rich Firefox extension bridges the browser to the desktop app via a local HTTP API:

- **YouTube Integration**: Injects a native **Download button** directly into the YouTube player controls bar (`ytp-right-controls`). Clicking it shows a rich popup with video thumbnail, title, uploader, and all available format/quality options.
  <img width="476" height="540" alt="Youtube download pill" src="https://github.com/user-attachments/assets/935b2189-ac28-42c2-8ffd-90f4760d5a93" />

- **Universal Video Hover Bar**: Detects any `<video>` element on **any website** and overlays a draggable download bar when you hover over it. Supports dynamically loaded video elements via `MutationObserver`.

- **Smart URL Resolution**: Intelligently determines the best URL to send per platform:
  - Social platforms (Instagram, Facebook, X/Twitter, TikTok, Dailymotion, Vimeo) — resolves the correct post/reel permalink for yt-dlp
  - Cross-origin iframe support — queries the background script for the real top-level tab URL when content runs inside iframes (e.g. Dailymotion geo-players)
  - Embed URL converter — automatically converts `/embed/VIDEO_ID` URLs to standard watch URLs
  - Direct media files (`.mp4`, `.mkv`, `.webm`, `.m3u8`, `.ts`, etc.) — bypasses yt-dlp and routes to the native segmented engine
- **Right-Click Context Menu**: "Download with App" context menu item on any page, powered by `background.js`
- **Extension Popup**: Toolbar popup with quick status check (ping), "Open App" and "New Download" shortcuts

  <img width="564" height="360" alt="Extension Pop-up" src="https://github.com/user-attachments/assets/ffd01b5e-f1ef-42b2-a0d0-f7b2dbc530ef" />
  
- **Deduplication**: Uses a `WeakSet` to prevent double-injecting hover bars on the same `<video>` element
- **Animated UI**: Format list popups with skeleton loading states, fade animations, shake-on-error, and a success checkmark animation
- **Rate Limiting**: The API server enforces a 200ms minimum between requests to prevent spam
  
<img width="530" height="862" alt="Download pill on a Facebook video" src="https://github.com/user-attachments/assets/4c440991-bfcb-4e04-8f2f-724c180fc955" />

---

### 🎨 Native GNOME UI (GTK4 + Libadwaita)

- **Sidebar Navigation**: Clean `Adw.NavigationSplitView` layout with pages for Downloads, Queue, History, and Settings
- **Standalone Download Card Windows** (`DownloadCardWindow`): Each active download opens its own draggable `Adw.Window` featuring:
  - Animated Cairo-rendered **speed graph** (60-point rolling history with adaptive Y-axis scaling)
  - **Segmented progress bar**: Per-chunk real-time fill for direct downloads (blue = in-progress, green = complete); simulated segments for yt-dlp downloads
  - Live speed, ETA, total size, and percentage readouts
  - Pause/Resume and Cancel controls; Open File and Open Folder buttons on completion
  - Smooth 60fps progress animation via `GLib.timeout_add(16, ...)`
    
    <img width="552" height="424" alt="InShot_20260527_141021462" src="https://github.com/user-attachments/assets/d368ec3c-4ec0-4ba7-9134-55c3f11f2e7c" />
    
    <img width="600" height="473" alt="Standalone Download Progress Card Window" src="https://github.com/user-attachments/assets/d8b197ed-6ab0-485f-945e-782debb0fddc" />

- **IDM-style Download Confirmation Dialog** (`DownloadConfirmDialog`): When triggered from the browser extension with a resolved format, shows title, resolution, format, and file extension with an editable filename and directory picker before starting

    <img width="950" height="750" alt="IDM-style Download Confirmation Dialog" src="https://github.com/user-attachments/assets/902391af-d416-4232-9bfc-4b4f9cb5404c" />

- **New Download Dialog** (`NewDownloadDialog`): Paste a URL, fetch full metadata (thumbnail, title, uploader, all available formats), and choose your format before confirming
- **Dark Mode**: Forces `Adw.ColorScheme.PREFER_DARK` on startup for a premium dark aesthetic
- **Automatic app hold**: Application runs in the background even when the window is closed, keeping the API server and clipboard monitor alive

<img width="950" height="750" alt="Video metadata fetching from URL" src="https://github.com/user-attachments/assets/60e2f5ee-cdb9-48a5-9a1f-85b2a990348b" />

---

### 📋 Intelligent Clipboard Monitoring

- Watches the system clipboard via `Gdk.Clipboard` for copied media URLs
- Recognizes **YouTube** (`youtube.com`, `youtu.be`), and **direct media files** (`.mp4`, `.webm`, `.mkv`, `.mp3`, `.m4a`, `.avi`, `.ogg`, `.wav`)
- On detection, pops up a **native GTK4 window** (non-intrusive) with "Ignore" and "Download" actions — no notification daemon required
- Deduplicates: the same URL won't trigger the popup twice in a row
- Opt-in via the Settings page (disabled by default)

<img width="450" height="230" alt="This is how the clipboard url detection pop-up looks" src="https://github.com/user-attachments/assets/e8b123c3-6ea3-4d44-9e44-8f31dd5bfe66" />


---

### 🗂️ Download Queue & History

- **Persistent JSON-based storage** (`~/.config/Leaf-Downloader/`):
  - `settings.json` — all user preferences
  - `history.json` — completed downloads (title, URL, format, resolution, filepath)
  - `queue.json` — queued-but-not-started downloads
- **History page**: Browse all past downloads with file existence checks, one-click "Open File", "Open Folder", and **re-download** support
- **Queue page**: View queued downloads and start them on demand
- Queue and history survive app restarts

  <img width="431" height="370" alt="Link Expiration Warning card" src="https://github.com/user-attachments/assets/308777bd-69c8-43c7-93ab-8ea68fdb6ffc" />

  <img width="950" height="750" alt="Queue page" src="https://github.com/user-attachments/assets/8bb074ce-408f-4ae3-888f-9b6087a05b97" />

  <img width="950" height="750" alt="History page" src="https://github.com/user-attachments/assets/ac734c33-c55a-4504-888b-6a33f19d77e1" />

---

### 🖥️ System Tray Icon

- A separate helper process (`tray_helper.py`) spawns an **AyatanaAppIndicator3** tray icon
- Tray menu: **Show Leaf Downloader** and **Quit** — both communicate via the local API
- Auto-exits if the main application goes offline (detected via periodic `/api/ping` heartbeat every 3 seconds)

  <img width="565" height="145" alt="System Tray Icon" src="https://github.com/user-attachments/assets/6779cdab-5b3f-49ca-a221-ea01158d332a" />

---

### 🌐 Local HTTP API Server

A lightweight, zero-dependency HTTP server (`http.server`) runs on `127.0.0.1:9549` (localhost only):

| Endpoint | Method | Description |
|---|---|---|
| `/api/ping` | `GET` | Health check — returns app name and version |
| `/api/metadata` | `POST` | Fetches video metadata via yt-dlp or returns direct-file metadata (skips yt-dlp for direct URLs) |
| `/api/download` | `POST` | Dispatches a download to the GTK app on the main thread |
| `/api/show` | `POST` | Brings the main window to the foreground |
| `/api/quit` | `POST` | Gracefully quits the application |

- Runs in a **background daemon thread** — never blocks the GTK main loop
- CORS headers enabled for browser extension communication
- Configurable port; can be enabled/disabled live from Settings

---

### ⚙️ Settings & Configuration

All settings are managed by a singleton `ConfigManager` and persisted in `~/.config/Leaf-Downloader/settings.json`:

| Setting | Default | Description |
|---|---|---|
| `download_dir` | `~/Downloads/Leaf` | Default save directory |
| `monitor_clipboard` | `false` | Enable/disable clipboard URL monitoring |
| `multithread` | `false` | Enable concurrent fragment downloads |
| `fragments` | `4` | Number of concurrent fragments (2–32) |
| `api_server_enabled` | `true` | Enable/disable the local HTTP API server |
| `api_server_port` | `9549` | Port for the local API server |
| `direct_download_max_retries` | `3` | Max retries per chunk in the native engine |
| `direct_download_timeout` | `30` | Connection timeout (seconds) for the native engine |

<img width="950" height="750" alt="Settings Page" src="https://github.com/user-attachments/assets/3f9532d9-6a8f-4ba1-9d18-fb8b80a66325" />

---

## 🚀 Getting Started

### Prerequisites

Make sure you have the following installed on your system:
- Python 3.10 or higher
- PyGObject (for GTK4 bindings)
- Libadwaita development libraries (`libadwaita-1-dev`)
- AyatanaAppIndicator3 (`gir1.2-ayatanaappindicator3-0.1`) — for the system tray
- `pip` for Python packages

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hasan-psl/Leaf-Downloader.git
   cd Leaf-Downloader
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Leaf-Downloader:**
   ```bash
   python main.py
   ```

---

## 🧩 Browser Extension Setup

The Firefox extension must currently be loaded manually as a temporary add-on:

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`.
2. Click **"Load Temporary Add-on..."**.
3. Select the `manifest.json` file inside the `browser_extension/` directory.
4. Open any YouTube video — a **Download** button will appear in the player controls.
5. Hover over any `<video>` element on any other site — a **Leaf download bar** will appear.

> **Note:** Leaf-Downloader must be running in the background for the extension to communicate with the local API server on `127.0.0.1:9549`.

---
<img width="949" height="761" alt="How it looks after loading the temporary extension" src="https://github.com/user-attachments/assets/2deb829b-c179-448d-8559-0c680049e0bf" />



## 🗺️ Roadmap & Future Plans

Leaf-Downloader is currently in a highly functional **Beta** phase. Upcoming plans include:

- [ ] 📦 **Official Packaging**: Proper `.deb` Debian packages and portable `AppImage` releases for easy installation across all distributions.
- [ ] 🦊 **Firefox Web Store**: Publishing the extension to the official Mozilla Add-ons store for one-click installation.
- [ ] 🌐 **Chromium Support**: Expanding the browser extension to support Google Chrome, Brave, and Edge.
- [ ] 🎨 **Continued Polish**: Smooth micro-animations, additional platform support, and further UI/UX refinements.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
See the [LICENSE](LICENSE) file for more details.

<div align="center">
  <i>Developed with ❤️ by Khondokar Shazid Hassan (@hasan-psl)</i>
</div>
