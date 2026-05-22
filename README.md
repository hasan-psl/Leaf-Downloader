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

Welcome to **Leaf-Downloader**, a high-performance desktop download manager designed specifically for Linux. By combining the power of `yt-dlp` with the elegance of GTK4 and Libadwaita, Leaf-Downloader delivers a blazing-fast, visually stunning, and highly integrated downloading experience.

---

## ✨ Features

- **🎨 Native Linux Experience**: Built with Python, GTK4, and Libadwaita for a seamless, modern GNOME-style interface. Forget clunky web wrappers!
- **⚡ Blazing Fast Downloads**: Powered by the robust `yt-dlp` backend, supporting multithreaded downloading to maximize your bandwidth.
- **🦊 Smart Browser Integration**: Includes a Firefox extension that injects a native "Download" button directly into YouTube players. A built-in local HTTP API server securely bridges the browser to the desktop app.
- **📋 Intelligent Clipboard Monitoring**: Automatically detects copied media URLs (YouTube, Reddit, direct links, etc.) and gracefully prompts you with an intrusive-free, native popup to start downloading.
- **🗂️ Advanced Queue & History**: Persistently tracks your downloads. Easily manage queues, view history, interact with downloaded files, and re-download with a single click.
- **🪟 Rich IDM-Style Interface**: Enjoy draggable, standalone Libadwaita download cards, detailed progress tracking, and stable speed calculations using moving averages.
- **⚙️ Highly Customizable**: Tweak thread counts, set default download paths, and configure deep `yt-dlp` settings right from the intuitive preferences page.

---

## 🚀 Getting Started

### Prerequisites

Make sure you have the following installed on your system:
- Python 3.10 or higher
- PyGObject (for GTK4 bindings)
- Libadwaita development libraries
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

Currently, the Firefox extension must be loaded manually as an unpacked add-on:

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`.
2. Click on **"Load Temporary Add-on..."**.
3. Select the `manifest.json` file located inside the `browser_extension` directory of this repository.
4. Open a YouTube video and look for the new "Download" button injected directly into the player!

*(Note: Leaf-Downloader must be running in the background for the extension to communicate with the local API server.)*

---

## 🗺️ Roadmap & Future Plans

Leaf-Downloader is currently in a highly stable **Beta** phase, with all current features working perfectly. However, the journey doesn't stop here! Upcoming plans include:

- [ ] 📦 **Official Packaging**: Proper `.deb` Debian packages and portable `AppImage` releases for easy installation across all distributions.
- [ ] 🦊 **Firefox Web Store**: Publishing the browser extension to the official Mozilla Add-ons store for a one-click install experience.
- [ ] 🎨 **Continued Polish**: Refining the UI/UX, adding smooth micro-animations, and extending support for more media platforms.
- [ ] 🌐 **Chromium Support**: Expanding the browser extension to support Google Chrome, Brave, and Edge.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. 
See the [LICENSE](LICENSE) file for more details.

<div align="center">
  <i>Developed with ❤️ by Khondokar Shazid Hassan (@hasan-psl)</i>
</div>
