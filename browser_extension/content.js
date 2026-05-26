/**
 * Leaf Downloader — Firefox Extension Content Script
 *
 * Injected into all pages to provide a highly stable download bridge.
 * Features:
 * - YouTube SPA URL polling safety net
 * - Lightweight controls-only MutationObserver for YouTube
 * - Universal hover video overlay for any page with <video> elements
 * - MutationObserver for dynamically loaded video elements
 * - Context menu "Download with App" integration via background.js
 * - Deduplication via WeakSet to avoid double hover-bar injection
 */

const API_BASE = "http://127.0.0.1:9549";
const BUTTON_ID = "leaf-download-btn";
const POPUP_ID = "leaf-popup-menu";
const HOVER_BAR_ID = "leaf-hover-bar";

let lastUrl = window.location.href;

// Tracks which <video> elements already have a hover bar attached
const attachedVideos = new WeakSet();

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatBytes(bytes) {
  if (!bytes) return "Unknown size";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

/**
 * Returns true if this page is a YouTube video watch/shorts page.
 * Only YouTube uses yt-dlp; everything else gets direct download.
 */
function isYouTube() {
  const host = window.location.hostname;
  return host.includes("youtube.com") || host.includes("youtu.be");
}

/**
 * Extract a usable (non-blob) video source URL from a <video> element.
 * Checks `src` attr first, then <source> children.
 * Returns null if only blob: URLs are found (HLS/DASH in-browser streams
 * that can't be fetched directly).
 */
function getVideoSourceUrl(video) {
  // Direct src attribute
  if (video.src && !video.src.startsWith("blob:") && video.src.startsWith("http")) {
    return video.src;
  }
  // <source> children
  const sources = video.querySelectorAll("source");
  for (const srcEl of sources) {
    if (srcEl.src && !srcEl.src.startsWith("blob:") && srcEl.src.startsWith("http")) {
      return srcEl.src;
    }
  }
  // currentSrc fallback (set by browser after source selection)
  if (video.currentSrc && !video.currentSrc.startsWith("blob:") && video.currentSrc.startsWith("http")) {
    return video.currentSrc;
  }
  return null;
}

/**
 * Decide the best URL to send for a given video element.
 *
 * - For YouTube:  always send window.location.href → yt-dlp handles it
 * - For everything else: prefer the direct video src URL. If no direct src
 *   is found (blob: only), fall back to page URL with is_direct_fallback=true
 *   so the API server probes it generically.
 *
 * Returns { url, isDirectFallback }
 */
function resolveDownloadUrl(video) {
  if (isYouTube()) {
    return { url: window.location.href, isDirectFallback: false };
  }

  const srcUrl = getVideoSourceUrl(video);
  if (srcUrl) {
    return { url: srcUrl, isDirectFallback: false };
  }

  // No direct src (blob: or nothing) — send page URL, tell server it's a fallback
  return { url: window.location.href, isDirectFallback: true };
}

// ---------------------------------------------------------------------------
// YouTube injection
// ---------------------------------------------------------------------------

function createDownloadButton() {
  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.className = "ytp-button leaf-download-btn";
  btn.title = "Download with Leaf";
  btn.setAttribute("aria-label", "Download with Leaf Downloader");

  btn.innerHTML = `
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="leaf-dl-icon">
      <path d="M12 3v12"/>
      <path d="M8 11l4 4 4-4"/>
      <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
      <circle cx="12" cy="3" r="1" fill="currentColor" stroke="none"/>
    </svg>
  `;

  btn.addEventListener("click", handleDownloadClick);
  return btn;
}

function handleDownloadClick(e) {
  e.preventDefault();
  e.stopPropagation();

  const player = document.getElementById("movie_player");
  if (!player) return;

  const existingPopup = document.getElementById(POPUP_ID);
  if (existingPopup) {
    closePopup(existingPopup);
    return;
  }

  showYouTubePopup(player);
}

function closePopup(popup) {
  if (!popup) return;
  popup.classList.add("leaf-fade-out");
  setTimeout(() => {
    if (popup.parentNode) popup.remove();
  }, 200);
}

function buildPopupSkeleton() {
  return `
    <div class="leaf-popup-header">
      <div class="leaf-popup-brand-row">
        <span class="leaf-popup-brand-title">Leaf Downloader</span>
        <button class="leaf-popup-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="leaf-popup-video-info">
        <div class="leaf-skeleton leaf-skeleton-thumb"></div>
        <div class="leaf-popup-video-text">
          <div class="leaf-skeleton leaf-skeleton-title"></div>
          <div class="leaf-skeleton leaf-skeleton-uploader"></div>
        </div>
      </div>
    </div>
    <div class="leaf-popup-content">
      <div class="leaf-skeleton-list">
        <div class="leaf-skeleton leaf-skeleton-item"></div>
        <div class="leaf-skeleton leaf-skeleton-item"></div>
        <div class="leaf-skeleton leaf-skeleton-item"></div>
      </div>
    </div>
  `;
}

function attachCloseBtn(popup) {
  const closeBtn = popup.querySelector(".leaf-popup-close-btn");
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      closePopup(popup);
    });
  }
}

function showYouTubePopup(player) {
  const popup = document.createElement("div");
  popup.id = POPUP_ID;
  popup.className = "leaf-popup-card leaf-fade-in";
  popup.innerHTML = buildPopupSkeleton();
  attachCloseBtn(popup);

  player.appendChild(popup);
  popup.style.position = "absolute";
  popup.style.bottom = "55px";
  popup.style.right = "12px";
  popup.style.zIndex = "2001";

  // YouTube always uses the page URL — yt-dlp backend
  fetchMetadata(window.location.href, popup, false, null);
}

function injectButton() {
  if (document.getElementById(BUTTON_ID)) return;

  const rightControls = document.querySelector(".ytp-right-controls");
  if (!rightControls) return;

  const btn = createDownloadButton();
  rightControls.insertBefore(btn, rightControls.firstChild);
}

function removeButton() {
  const existing = document.getElementById(BUTTON_ID);
  if (existing) existing.remove();

  const popup = document.getElementById(POPUP_ID);
  if (popup) popup.remove();
}

function isWatchPage() {
  return isYouTube() &&
    (window.location.pathname === "/watch" || window.location.pathname.startsWith("/shorts/"));
}

function tryInject() {
  if (!isWatchPage()) {
    removeButton();
    return;
  }

  injectButton();

  if (!document.getElementById(BUTTON_ID)) {
    const retryInterval = setInterval(() => {
      if (document.getElementById(BUTTON_ID) || !isWatchPage()) {
        clearInterval(retryInterval);
        return;
      }
      injectButton();
    }, 500);

    setTimeout(() => clearInterval(retryInterval), 10000);
  }
}

function setupLightweightObserver() {
  if (!isYouTube()) return;

  const target = document.querySelector(".ytp-right-controls");
  if (target) {
    const observer = new MutationObserver(() => {
      if (isWatchPage() && !document.getElementById(BUTTON_ID)) {
        injectButton();
      }
    });
    observer.observe(target, { childList: true });
  } else {
    setTimeout(setupLightweightObserver, 1000);
  }
}

// ---------------------------------------------------------------------------
// Metadata fetching and popup rendering
// ---------------------------------------------------------------------------

/**
 * Fetch video metadata from the local desktop app API.
 *
 * @param {string} url          - URL to fetch metadata for (page or direct media)
 * @param {Element} popup       - The popup DOM element to render into
 * @param {boolean} isDirectFallback - Tell API to treat as generic direct link
 * @param {string|null} videoSrcUrl  - The actual direct video URL for download dispatch
 *                                     (may differ from `url` which could be page URL)
 */
async function fetchMetadata(url, popup, isDirectFallback, videoSrcUrl) {
  try {
    const response = await fetch(`${API_BASE}/api/metadata`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, is_direct_fallback: isDirectFallback })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }

    // The actual download URL: for direct links use videoSrcUrl (the src attr),
    // for YouTube use the page URL (which yt-dlp will resolve)
    const downloadUrl = videoSrcUrl || url;

    renderMetadata(data, popup, downloadUrl);
  } catch (err) {
    console.warn("[Leaf] Metadata fetch failed:", err.message);
    renderError(popup, url, isDirectFallback, videoSrcUrl);
  }
}

/**
 * Populate popup with metadata and format list.
 * downloadUrl is the URL that will actually be sent to the download API.
 */
function renderMetadata(data, popup, downloadUrl) {
  const header = popup.querySelector(".leaf-popup-video-info");
  const content = popup.querySelector(".leaf-popup-content");

  if (header) {
    header.innerHTML = `
      ${data.thumbnail ? `<img class="leaf-popup-thumb" src="${data.thumbnail}" alt="Thumbnail" />` : ''}
      <div class="leaf-popup-video-text">
        <h3 class="leaf-popup-title" title="${data.title}">${data.title}</h3>
        <p class="leaf-popup-uploader">${data.uploader || "Direct Link"}</p>
      </div>
    `;
  }

  if (!data.formats || data.formats.length === 0) {
    content.innerHTML = `<div class="leaf-popup-no-formats">No downloadable formats found.</div>`;
    return;
  }

  let listHtml = `<div class="leaf-formats-list">`;

  data.formats.forEach((f, idx) => {
    const isAudio = f.type === "Audio Only";
    const isDirect = f.format_id === "direct";
    const sizeStr = f.size > 0 ? formatBytes(f.size) : (isDirect ? "Direct File" : "Unknown size");
    const fpsStr = f.fps ? `${f.fps}fps` : "";

    let resolutionLabel = "";
    let subDetails = "";
    let badgeHtml = "";

    if (isAudio) {
      const abrStr = f.abr ? ` (${f.abr}kbps)` : "";
      resolutionLabel = `Audio (${f.ext})${abrStr}`;
      subDetails = `Audio: ${f.acodec || "unknown"}`;
      badgeHtml = `<span class="leaf-format-badge leaf-badge-muxed">Audio</span>`;
    } else if (isDirect) {
      // Direct file download (mp4, mkv, zip, etc.)
      resolutionLabel = `Direct Download (.${f.ext})`;
      subDetails = `Segmented HTTP download via native engine`;
      badgeHtml = `<span class="leaf-format-badge leaf-badge-direct">Direct</span>`;
    } else {
      const fpsLabel = fpsStr ? ` @ ${fpsStr}` : "";
      resolutionLabel = `${f.height}p${fpsLabel} (${f.ext})`;

      const vcodec = f.vcodec || "unknown";
      if (f.merged) {
        subDetails = `Video + Audio (Merged automatically)`;
        badgeHtml = `<span class="leaf-format-badge leaf-badge-merged">Merged</span>`;
      } else {
        subDetails = `Video: ${vcodec} | Audio: ${f.acodec || "unknown"}`;
        badgeHtml = `<span class="leaf-format-badge leaf-badge-muxed">Direct</span>`;
      }
    }

    listHtml += `
      <button class="leaf-format-item" data-index="${idx}">
        <div class="leaf-format-icon-box">
          ${isAudio ? `
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 18V5l12-2v13"/>
              <circle cx="6" cy="18" r="3"/>
              <circle cx="18" cy="16" r="3"/>
            </svg>
          ` : `
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/>
              <line x1="7" y1="2" x2="7" y2="22"/>
              <line x1="17" y1="2" x2="17" y2="22"/>
              <line x1="2" y1="12" x2="22" y2="12"/>
              <line x1="2" y1="7" x2="7" y2="7"/>
              <line x1="2" y1="17" x2="7" y2="17"/>
              <line x1="17" y1="17" x2="22" y2="17"/>
              <line x1="17" y1="7" x2="22" y2="7"/>
            </svg>
          `}
        </div>
        <div class="leaf-format-details">
          <div class="leaf-format-res-row">
            <span class="leaf-format-resolution">${resolutionLabel}</span>
            ${badgeHtml}
          </div>
          <span class="leaf-format-subtext">${subDetails}</span>
        </div>
        <div class="leaf-format-side">
          <span class="leaf-format-size">${sizeStr}</span>
        </div>
      </button>
    `;
  });

  listHtml += `</div>`;
  content.innerHTML = listHtml;

  const formatButtons = content.querySelectorAll(".leaf-format-item");
  formatButtons.forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.getAttribute("data-index"));
      const f = data.formats[idx];
      const isAudio = f.type === "Audio Only";
      const isDirect = f.format_id === "direct";
      let resolutionLabel;
      if (isDirect) {
        resolutionLabel = f.ext.toUpperCase();
      } else if (isAudio) {
        resolutionLabel = `Audio (${f.ext})`;
      } else {
        resolutionLabel = `${f.height}p`;
      }

      await startDownload(downloadUrl, data.title, f, resolutionLabel, popup, btn);
    });
  });
}

/**
 * Dispatch a download request to the desktop app.
 * downloadUrl must be the actual file/video URL, not the page URL.
 */
async function startDownload(downloadUrl, title, format, resolution, popup, button) {
  button.classList.add("leaf-format-loading");
  const origContent = button.innerHTML;
  button.innerHTML = `
    <div class="leaf-mini-spinner"></div>
    <span style="margin-left: 12px; font-weight: 500;">Starting download...</span>
  `;

  try {
    const response = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: downloadUrl,
        title: title,
        format_id: format.format_id,
        audio_format_id: format.audio_format_id,
        ext: format.ext,
        resolution: resolution
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    popup.innerHTML = `
      <div class="leaf-popup-success-container">
        <div class="leaf-success-checkmark">
          <div class="leaf-check-icon">
            <span class="leaf-icon-line leaf-line-tip"></span>
            <span class="leaf-icon-line leaf-line-long"></span>
            <div class="leaf-icon-circle"></div>
            <div class="leaf-icon-fix"></div>
          </div>
        </div>
        <h3>Sent to Leaf!</h3>
        <p>Download started in the background</p>
      </div>
    `;

    setTimeout(() => closePopup(popup), 2000);

  } catch (err) {
    button.innerHTML = origContent;
    button.classList.remove("leaf-format-loading");

    popup.classList.add("leaf-popup-error-shake");
    setTimeout(() => popup.classList.remove("leaf-popup-error-shake"), 800);
  }
}

function renderError(popup, url, isDirectFallback, videoSrcUrl) {
  const content = popup.querySelector(".leaf-popup-content");
  const headerInfo = popup.querySelector(".leaf-popup-video-info");
  if (headerInfo) headerInfo.remove();

  content.innerHTML = `
    <div class="leaf-error-container">
      <div class="leaf-error-icon">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <h3>Leaf App Offline</h3>
      <p>Please open the Leaf Downloader desktop application and try again.</p>
      <button class="leaf-retry-btn">Retry Connection</button>
    </div>
  `;

  const retryBtn = content.querySelector(".leaf-retry-btn");
  retryBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    popup.innerHTML = buildPopupSkeleton();
    attachCloseBtn(popup);
    fetchMetadata(url, popup, isDirectFallback, videoSrcUrl);
  });
}

// ---------------------------------------------------------------------------
// Universal Hover Video Detector
// ---------------------------------------------------------------------------

function createHoverBarFor(video) {
  // Guard: already attached or too small
  if (attachedVideos.has(video)) return;
  if (video.offsetWidth < 120 || video.offsetHeight < 80) return;
  if (video.dataset.leafDismissed === "true") return;

  // Mark as attached immediately to prevent races
  attachedVideos.add(video);

  const bar = document.createElement("div");
  bar.className = "leaf-video-hover-bar leaf-fade-in";
  bar.dataset.leafBar = "1";

  bar.innerHTML = `
    <div class="leaf-hover-bar-btn">
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px; flex-shrink: 0;">
        <path d="M12 3v12"/>
        <path d="M8 11l4 4 4-4"/>
        <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
      </svg>
      <span>Download Video</span>
    </div>
    <div class="leaf-hover-bar-close" title="Dismiss">&times;</div>
  `;

  const dlBtn = bar.querySelector(".leaf-hover-bar-btn");
  dlBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();

    const existingPopup = document.getElementById(POPUP_ID);
    if (existingPopup) {
      closePopup(existingPopup);
      return;
    }

    showVideoPopup(video);
  });

  const closeBtn = bar.querySelector(".leaf-hover-bar-close");
  closeBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    video.dataset.leafDismissed = "true";
    bar.remove();
    // Allow re-attach if user navigates away and back
    attachedVideos.delete(video);
  });

  const parent = video.parentElement;
  if (parent) {
    const computedStyle = window.getComputedStyle(parent);
    if (computedStyle.position === "static") {
      parent.style.position = "relative";
    }
    parent.appendChild(bar);
  }

  // Remove the bar when the video element leaves the DOM
  const removalObserver = new MutationObserver(() => {
    if (!document.contains(video)) {
      bar.remove();
      attachedVideos.delete(video);
      removalObserver.disconnect();
    }
  });
  removalObserver.observe(document.body, { childList: true, subtree: true });
}

/**
 * Show the format picker popup for any <video> element.
 */
function showVideoPopup(video) {
  const { url, isDirectFallback } = resolveDownloadUrl(video);
  // The actual video src (for dispatch) — may differ from url
  const videoSrcUrl = getVideoSourceUrl(video);

  const parent = video.parentElement;
  if (!parent) return;

  const popup = document.createElement("div");
  popup.id = POPUP_ID;
  popup.className = "leaf-popup-card leaf-fade-in";
  popup.innerHTML = buildPopupSkeleton();
  attachCloseBtn(popup);

  parent.appendChild(popup);
  popup.style.position = "absolute";
  popup.style.top = "42px";
  popup.style.right = "10px";
  popup.style.zIndex = "100000";

  // For direct links, the download URL is the video src; otherwise page URL (yt-dlp)
  fetchMetadata(url, popup, isDirectFallback, videoSrcUrl);
}

function handleGlobalMouseOver(e) {
  const videos = document.querySelectorAll("video");
  const x = e.clientX;
  const y = e.clientY;

  for (const video of videos) {
    if (attachedVideos.has(video)) continue;
    if (video.dataset.leafDismissed === "true") continue;
    if (video.offsetWidth < 120 || video.offsetHeight < 80) continue;

    const rect = video.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      createHoverBarFor(video);
      break;
    }
  }
}

function removeHoverBars() {
  document.querySelectorAll("[data-leaf-bar]").forEach(bar => bar.remove());
}

// ---------------------------------------------------------------------------
// MutationObserver for dynamically loaded <video> elements
// ---------------------------------------------------------------------------

function onNewVideoElement(video) {
  // Small delay to let the element finish loading its src attribute
  setTimeout(() => {
    const srcUrl = getVideoSourceUrl(video);
    // Only auto-attach if it has a real src or is large enough to be meaningful
    if (video.offsetWidth >= 120 || video.offsetHeight >= 80 || srcUrl) {
      // Don't auto-inject bar — wait for hover. Just ensure clean state.
      attachedVideos.delete(video);
    }
  }, 300);
}

const videoMutationObserver = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    for (const node of mutation.addedNodes) {
      if (node.nodeType !== Node.ELEMENT_NODE) continue;

      // Check if the added node itself is a video
      if (node.tagName === "VIDEO") {
        onNewVideoElement(node);
      }

      // Check descendants
      const videos = node.querySelectorAll ? node.querySelectorAll("video") : [];
      for (const video of videos) {
        onNewVideoElement(video);
      }
    }

    // Also handle src changes on existing video elements
    if (mutation.type === "attributes" &&
        mutation.target.tagName === "VIDEO" &&
        (mutation.attributeName === "src" || mutation.attributeName === "currentSrc")) {
      const video = mutation.target;
      // Reset dismissed state when video source changes
      delete video.dataset.leafDismissed;
      attachedVideos.delete(video);
    }
  }
});

videoMutationObserver.observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src", "currentSrc"]
});

// ---------------------------------------------------------------------------
// Context Menu handler (message from background.js)
// ---------------------------------------------------------------------------

browser.runtime.onMessage.addListener((message) => {
  if (message.type === "contextMenuDownload") {
    const { linkUrl, srcUrl, pageUrl } = message;

    // Pick the most specific URL available
    const targetUrl = srcUrl || linkUrl || pageUrl;
    if (!targetUrl) return;

    // Build a simple popup attached to body
    const existingPopup = document.getElementById(POPUP_ID);
    if (existingPopup) closePopup(existingPopup);

    const popup = document.createElement("div");
    popup.id = POPUP_ID;
    popup.className = "leaf-popup-card leaf-fade-in";
    popup.innerHTML = buildPopupSkeleton();
    attachCloseBtn(popup);

    document.body.appendChild(popup);

    // Float in top-right corner
    popup.style.position = "fixed";
    popup.style.top = "20px";
    popup.style.right = "20px";
    popup.style.zIndex = "2147483647";

    // Determine if this is a direct media URL
    const isDirectMedia = /\.(mp4|mkv|webm|mov|avi|flv|mp3|m4a|zip|exe|tar|gz|7z|ts|m3u8)(\?|#|$)/i.test(targetUrl);
    fetchMetadata(targetUrl, popup, isDirectMedia, isDirectMedia ? targetUrl : null);
  }
});

// ---------------------------------------------------------------------------
// SPA navigation polling
// ---------------------------------------------------------------------------

function handlePageChange() {
  removeButton();
  removeHoverBars();
  setTimeout(tryInject, 400);
  setTimeout(setupLightweightObserver, 600);
}

setInterval(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    handlePageChange();
  }
}, 500);

// Click-outside popup cleanup
document.addEventListener("click", (e) => {
  const popup = document.getElementById(POPUP_ID);
  const btn = document.getElementById(BUTTON_ID);
  if (popup &&
      !popup.contains(e.target) &&
      (!btn || !btn.contains(e.target))) {
    closePopup(popup);
  }
});

document.addEventListener("mouseover", handleGlobalMouseOver);

// Initial injection
tryInject();
setupLightweightObserver();
