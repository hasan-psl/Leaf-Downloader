/**
 * Leaf Downloader — Firefox Extension Content Script
 * 
 * Injected into all pages to provide a highly stable download bridge.
 * Features:
 * - Ultra-robust YouTube SPA URL polling safety net
 * - Ultra-lightweight controls-only MutationObserver (0% CPU impact)
 * - Universal hover video overlay for Facebook, Instagram, Reddit, X, and direct links
 */

const API_BASE = "http://127.0.0.1:9549";
const BUTTON_ID = "leaf-download-btn";
const POPUP_ID = "leaf-popup-menu";
const HOVER_BAR_ID = "leaf-hover-bar";

let lastUrl = window.location.href;
let hoverTimeout = null;
let activeVideo = null;
let activeBar = null;

/**
 * Format bytes into readable filesize
 */
function formatBytes(bytes) {
  if (!bytes) return "Unknown size";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

/**
 * Create the YouTube player controls download button
 */
function createDownloadButton() {
  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.className = "ytp-button leaf-download-btn";
  btn.title = "Download with Leaf";
  btn.setAttribute("aria-label", "Download with Leaf Downloader");

  // SVG download icon
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

/**
 * Handle download button click — toggle or create floating popup
 */
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

  showFloatingPopup(player);
}

/**
 * Close popup with transition
 */
function closePopup(popup) {
  if (!popup) return;
  popup.classList.add("leaf-fade-out");
  setTimeout(() => {
    if (popup.parentNode) popup.remove();
  }, 200);
}

/**
 * Create and show the floating popup menu with skeleton loaders
 */
function showFloatingPopup(player) {
  const popup = document.createElement("div");
  popup.id = POPUP_ID;
  popup.className = "leaf-popup-card leaf-fade-in";

  popup.innerHTML = `
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

  const closeBtn = popup.querySelector(".leaf-popup-close-btn");
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    closePopup(popup);
  });

  player.appendChild(popup);

  // Position absolutely inside the player
  popup.style.position = "absolute";
  popup.style.bottom = "55px";
  popup.style.right = "12px";
  popup.style.zIndex = "2001";

  fetchMetadata(window.location.href, popup);
}

/**
 * Fetch video metadata from local API
 */
async function fetchMetadata(url, popup, isDirectFallback = false) {
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
    renderMetadata(data, popup, url);
  } catch (err) {
    renderError(popup);
  }
}

/**
 * Populate popup card with actual metadata and qualities list
 */
function renderMetadata(data, popup, url) {
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
    const sizeStr = f.size > 0 ? formatBytes(f.size) : "Direct Stream";
    const fpsStr = f.fps ? `${f.fps}fps` : "";
    
    let resolutionLabel = "";
    let subDetails = "";
    let badgeHtml = "";

    if (isAudio) {
      const abrStr = f.abr ? ` (${f.abr}kbps)` : "";
      resolutionLabel = `Audio (${f.ext})${abrStr}`;
      subDetails = `Audio: ${f.acodec || "unknown"}`;
    } else {
      const fpsLabel = fpsStr ? ` @ ${fpsStr}` : "";
      resolutionLabel = `${f.height}${f.height !== "Direct" ? 'p' : ''}${fpsLabel} (${f.ext})`;
      
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
      const resolutionLabel = isAudio ? `Audio (${f.ext})` : `${f.height}${f.height !== "Direct" ? 'p' : ''}`;
      
      await startDownload(url, data.title, f, resolutionLabel, popup, btn);
    });
  });
}

/**
 * Handle direct download dispatch
 */
async function startDownload(url, title, format, resolution, popup, button) {
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
        url: url,
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

/**
 * Render error state in the popup
 */
function renderError(popup) {
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
      <p>Please open the Leaf Downloader desktop application on your computer and try again.</p>
      <button class="leaf-retry-btn">Retry Connection</button>
    </div>
  `;

  const retryBtn = content.querySelector(".leaf-retry-btn");
  retryBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    popup.innerHTML = `
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
    const closeBtn = popup.querySelector(".leaf-popup-close-btn");
    closeBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      closePopup(popup);
    });
    fetchMetadata(window.location.href, popup);
  });
}

/**
 * Inject the download button into YouTube's player controls
 */
function injectButton() {
  if (document.getElementById(BUTTON_ID)) return;

  const rightControls = document.querySelector(".ytp-right-controls");
  if (!rightControls) return;

  const btn = createDownloadButton();
  rightControls.insertBefore(btn, rightControls.firstChild);
}

/**
 * Remove existing button and popup
 */
function removeButton() {
  const existing = document.getElementById(BUTTON_ID);
  if (existing) existing.remove();

  const popup = document.getElementById(POPUP_ID);
  if (popup) popup.remove();
}

/**
 * Check if current page is a video watch page
 */
function isWatchPage() {
  return window.location.hostname.includes("youtube.com") && 
         (window.location.pathname === "/watch" || window.location.pathname.startsWith("/shorts/"));
}

/**
 * Main injection logic — tries to inject
 */
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

/**
 * Watch for controls container adjustments using light MutationObserver
 */
function setupLightweightObserver() {
  if (!window.location.hostname.includes("youtube.com")) return;

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

/**
 * SPA page URL polling listener (Safety net)
 */
function handlePageChange() {
  removeButton();
  removeHoverBar();
  setTimeout(tryInject, 400);
  setTimeout(setupLightweightObserver, 600);
}

setInterval(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    handlePageChange();
  }
}, 500);


/**
 * =========================================================================
 * UNIVERSAL HOVER VIDEO DETECTOR (Facebook, Instagram, Reddit, X, etc.)
 * =========================================================================
 */

function isKnownPlatform() {
  const host = window.location.hostname;
  return host.includes("youtube.com") || 
         host.includes("youtu.be") || 
         host.includes("facebook.com") || 
         host.includes("instagram.com") || 
         host.includes("reddit.com") || 
         host.includes("twitter.com") || 
         host.includes("x.com");
}

function getVideoSourceUrl(video) {
  if (video.src && !video.src.startsWith("blob:")) {
    return video.src;
  }
  const sources = video.querySelectorAll("source");
  for (const srcEl of sources) {
    if (srcEl.src && !srcEl.src.startsWith("blob:")) {
      return srcEl.src;
    }
  }
  return null;
}

function handleGlobalMouseOver(e) {
  const videos = document.querySelectorAll("video");
  const x = e.clientX;
  const y = e.clientY;
  
  let hoveredVideo = null;
  for (const video of videos) {
    if (video.offsetWidth < 120 || video.offsetHeight < 80) continue;
    if (video.dataset.leafDismissed === "true") continue;

    const rect = video.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      hoveredVideo = video;
      break;
    }
  }

  if (hoveredVideo) {
    const parent = hoveredVideo.parentElement;
    if (parent && !parent.querySelector("#" + HOVER_BAR_ID)) {
      createHoverBarFor(hoveredVideo);
    }
  }
}

function createHoverBarFor(video) {
  const bar = document.createElement("div");
  bar.id = HOVER_BAR_ID;
  bar.className = "leaf-video-hover-bar leaf-fade-in";
  
  bar.innerHTML = `
    <div class="leaf-hover-bar-btn">
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px; flex-shrink: 0;">
        <path d="M12 3v12"/>
        <path d="M8 11l4 4 4-4"/>
        <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
      </svg>
      <span>Download Video</span>
    </div>
    <div class="leaf-hover-bar-close" title="Dismiss panel">&times;</div>
  `;
  
  const dlBtn = bar.querySelector(".leaf-hover-bar-btn");
  dlBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const parent = video.parentElement;
    if (!parent) return;
    
    const existingPopup = document.getElementById(POPUP_ID);
    if (existingPopup) {
      closePopup(existingPopup);
      return;
    }
    
    showUniversalPopup(parent, video);
  });

  const closeBtn = bar.querySelector(".leaf-hover-bar-close");
  closeBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    video.dataset.leafDismissed = "true";
    bar.remove();
  });
  
  const parent = video.parentElement;
  if (parent) {
    const computedStyle = window.getComputedStyle(parent);
    if (computedStyle.position === "static") {
      parent.style.position = "relative";
    }
    parent.appendChild(bar);
  }
}

function removeHoverBar() {
  const bars = document.querySelectorAll("#" + HOVER_BAR_ID);
  bars.forEach(bar => bar.remove());
}

/**
 * Show formats selection card overlapping any webpage's video parent element
 */
function showUniversalPopup(parent, video) {
  const popup = document.createElement("div");
  popup.id = POPUP_ID;
  popup.className = "leaf-popup-card leaf-fade-in";

  popup.innerHTML = `
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

  const closeBtn = popup.querySelector(".leaf-popup-close-btn");
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    closePopup(popup);
  });

  parent.appendChild(popup);

  // Position popup absolute inside the relative container
  popup.style.position = "absolute";
  popup.style.top = "42px";
  popup.style.right = "10px";
  popup.style.zIndex = "100000";

  let targetUrl = window.location.href;
  let isDirectFallback = false;
  if (!isKnownPlatform()) {
    const srcUrl = getVideoSourceUrl(video);
    if (srcUrl) {
      targetUrl = srcUrl;
      isDirectFallback = true;
    }
  }

  fetchMetadata(targetUrl, popup, isDirectFallback);
}

// Global mouse listeners
document.addEventListener("mouseover", handleGlobalMouseOver);

// Global click outside popup cleanup
document.addEventListener("click", (e) => {
  const popup = document.getElementById(POPUP_ID);
  const btn = document.getElementById(BUTTON_ID);
  const hoverBtn = document.getElementById(HOVER_BAR_ID);
  if (popup && !popup.contains(e.target) && (!btn || !btn.contains(e.target)) && (!hoverBtn || !hoverBtn.contains(e.target))) {
    closePopup(popup);
  }
});

// Initial injection triggers
tryInject();
setupLightweightObserver();
