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

async function callApi(endpoint, method, body) {
  try {
    const response = await browser.runtime.sendMessage({
      type: "fetchApi",
      endpoint,
      method,
      body
    });
    if (!response.ok) {
      throw new Error(response.error || `HTTP ${response.status}`);
    }
    return response.data;
  } catch (err) {
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function setSafeHTML(element, htmlString) {
  const doc = new DOMParser().parseFromString(htmlString, "text/html");
  element.replaceChildren(...doc.body.childNodes);
}

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

function isSocialPlatformSupportedByYtdlp() {
  const host = window.location.hostname;
  return (
    host.includes("youtube.com") ||
    host.includes("youtu.be") ||
    host.includes("instagram.com") ||
    host.includes("facebook.com") ||
    host.includes("twitter.com") ||
    host.includes("x.com") ||
    host.includes("tiktok.com") ||
    host.includes("reddit.com") ||
    host.includes("dailymotion.com") ||
    host.includes("vimeo.com")
  );
}

function getSocialPlatformPostUrl(video) {
  const host = window.location.hostname;
  
  if (host.includes("instagram.com")) {
    const article = video.closest("article");
    if (article) {
      const links = Array.from(article.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && (href.includes("/p/") || href.includes("/reel/") || href.includes("/reels/") || href.includes("/tv/"))) {
          return new URL(href, window.location.origin).href;
        }
      }
    }
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && (href.includes("/p/") || href.includes("/reel/") || href.includes("/reels/") || href.includes("/tv/"))) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  if (host.includes("facebook.com")) {
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && (href.includes("/watch/") || href.includes("/videos/") || href.includes("/reel/") || href.includes("/reels/"))) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  if (host.includes("twitter.com") || host.includes("x.com")) {
    const article = video.closest("article");
    if (article) {
      const links = Array.from(article.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && href.includes("/status/")) {
          return new URL(href, window.location.origin).href;
        }
      }
    }
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && href.includes("/status/")) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  if (host.includes("tiktok.com")) {
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && href.includes("/video/")) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  if (host.includes("dailymotion.com")) {
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        if (href && href.includes("/video/")) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  if (host.includes("vimeo.com")) {
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 10) {
      const links = Array.from(parent.querySelectorAll("a"));
      for (const link of links) {
        const href = link.getAttribute("href");
        const path = new URL(href, window.location.origin).pathname;
        if (href && /^\/\d+$/.test(path)) {
          return new URL(href, window.location.origin).href;
        }
      }
      parent = parent.parentElement;
      depth++;
    }
  }

  return null;
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
 * - For YouTube/Instagram/FB/X/TikTok: send specific post/reel permalink so yt-dlp extracts real video streams.
 * - For direct/standard sites: send direct video src URL.
 * - Otherwise: fallback to page URL as direct fallback.
 *
 * Returns { url, isDirectFallback }
 */
/**
 * Converts embedded player URLs (from iframes) into their corresponding standard watch URLs.
 * This guarantees maximal compatibility with yt-dlp.
 */
function convertEmbedToWatchUrl(urlStr) {
  try {
    const url = new URL(urlStr);
    const host = url.hostname;
    const path = url.pathname;

    // 1. If we are running inside an iframe, check document.referrer.
    // If the host page URL is a standard platform watch page, we can use it directly!
    if (window !== window.top && document.referrer) {
      try {
        const refUrl = new URL(document.referrer);
        const refHost = refUrl.hostname;
        
        if (host.includes("dailymotion.com") && refHost.includes("dailymotion.com") && refUrl.pathname.includes("/video/")) {
          return refUrl.href;
        }
        if (host.includes("vimeo.com") && refHost.includes("vimeo.com") && /^\/\d+$/.test(refUrl.pathname)) {
          return refUrl.href;
        }
        if ((host.includes("youtube.com") || host.includes("youtu.be")) && 
            (refHost.includes("youtube.com") || refHost.includes("youtu.be")) && 
            refUrl.pathname.includes("/watch")) {
          return refUrl.href;
        }
      } catch (e) {
        // Ignore referrer parsing errors
      }
    }

    // 2. Query parameter or path-based embed parsers
    // Dailymotion embed or geo player
    if (host.includes("dailymotion.com")) {
      const videoParam = url.searchParams.get("video");
      if (videoParam) {
        return `https://www.dailymotion.com/video/${videoParam}`;
      }
      const match = path.match(/\/embed\/video\/([a-zA-Z0-9]+)/);
      if (match) {
        return `https://www.dailymotion.com/video/${match[1]}`;
      }
    }

    // Vimeo embed
    if (host.includes("vimeo.com")) {
      const match = path.match(/\/video\/([0-9]+)/);
      if (match) {
        return `https://vimeo.com/${match[1]}`;
      }
    }

    // YouTube embed
    if (host.includes("youtube.com") || host.includes("youtu.be")) {
      const match = path.match(/\/embed\/([a-zA-Z0-9_-]+)/);
      if (match) {
        return `https://www.youtube.com/watch?v=${match[1]}`;
      }
    }

    // Facebook video plugin embeds
    if (host.includes("facebook.com")) {
      const hrefParam = url.searchParams.get("href");
      if (hrefParam) {
        return hrefParam;
      }
    }
  } catch (e) {
    // Ignore URL parsing errors
  }
  return urlStr;
}

/**
 * Decide the best URL to send for a given video element.
 *
 * - For YouTube/Instagram/FB/X/TikTok/Dailymotion/Vimeo: send specific watch/post permalink so yt-dlp extracts real video streams.
 * - For direct/standard sites: send direct video src URL.
 * - Otherwise: fallback to page URL as direct fallback.
 *
 * When running inside an iframe, asks the background script for the real
 * top-level tab URL via sender.tab.url — this is essential for sites like
 * Dailymotion where the <video> lives inside a cross-origin iframe
 * (e.g. geo.dailymotion.com) and document.referrer is empty.
 *
 * Returns { url, isDirectFallback }
 */
async function resolveDownloadUrl(video) {
  let url = window.location.href;

  // If we are inside an iframe, get the real top-level page URL from the
  // background script. This is the same URL that "Send Current Tab" uses,
  // and yt-dlp already works on it.
  if (window !== window.top) {
    try {
      const resp = await browser.runtime.sendMessage({ type: "getTabUrl" });
      if (resp && resp.url) {
        url = resp.url;
      }
    } catch (e) {
      // Messaging failed — fall back to iframe URL
    }
  }

  if (isYouTube()) {
    // YouTube: use the page/tab URL directly
  } else if (isSocialPlatformSupportedByYtdlp()) {
    const postUrl = getSocialPlatformPostUrl(video);
    if (postUrl) {
      url = postUrl;
    }
  } else {
    const srcUrl = getVideoSourceUrl(video);
    if (srcUrl) {
      return { url: srcUrl, isDirectFallback: false };
    }
  }

  // Convert embed player URLs to standard watch URLs for maximum yt-dlp compatibility
  url = convertEmbedToWatchUrl(url);

  // If it's a social/media platform supported by yt-dlp, always use isDirectFallback = false
  // We check both the iframe host and the resolved URL host
  const resolvedHost = (() => { try { return new URL(url).hostname; } catch { return ''; } })();
  const isKnownPlatform = isYouTube() || isSocialPlatformSupportedByYtdlp() ||
    resolvedHost.includes("dailymotion.com") || resolvedHost.includes("vimeo.com") ||
    resolvedHost.includes("youtube.com") || resolvedHost.includes("twitch.tv");

  return { url: url, isDirectFallback: !isKnownPlatform };
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

  setSafeHTML(btn, `
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="leaf-dl-icon">
      <path d="M12 3v12"/>
      <path d="M8 11l4 4 4-4"/>
      <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
      <circle cx="12" cy="3" r="1" fill="currentColor" stroke="none"/>
    </svg>
  `);

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
  setSafeHTML(popup, buildPopupSkeleton());
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
    const data = await callApi("/api/metadata", "POST", { url, is_direct_fallback: isDirectFallback });
    if (data.error) {
      throw new Error(data.error);
    }

    // The actual download URL: for direct links use videoSrcUrl (the src attr),
    // for YouTube use the page URL (which yt-dlp will resolve)
    const downloadUrl = videoSrcUrl || url;

    renderMetadata(data, popup, downloadUrl);
  } catch (err) {
    console.warn("[Leaf] Metadata fetch failed:", err.message);
    renderError(popup, url, isDirectFallback, videoSrcUrl, err.message);
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
    setSafeHTML(header, `
      ${data.thumbnail ? `<img class="leaf-popup-thumb" src="${data.thumbnail}" alt="Thumbnail" />` : ''}
      <div class="leaf-popup-video-text">
        <h3 class="leaf-popup-title" title="${data.title}">${data.title}</h3>
        <p class="leaf-popup-uploader">${data.uploader || "Direct Link"}</p>
      </div>
    `);
  }

  if (!data.formats || data.formats.length === 0) {
    setSafeHTML(content, `<div class="leaf-popup-no-formats">No downloadable formats found.</div>`);
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
  setSafeHTML(content, listHtml);

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
  setSafeHTML(button, `
    <div class="leaf-mini-spinner"></div>
    <span style="margin-left: 12px; font-weight: 500;">Starting download...</span>
  `);

  try {
    await callApi("/api/download", "POST", {
      url: downloadUrl,
      title: title,
      format_id: format.format_id,
      audio_format_id: format.audio_format_id,
      ext: format.ext,
      resolution: resolution
    });

    setSafeHTML(popup, `
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
        <p>Please confirm download in the Leaf app</p>
      </div>
    `);

    setTimeout(() => closePopup(popup), 2000);

  } catch (err) {
    setSafeHTML(button, origContent);
    button.classList.remove("leaf-format-loading");

    popup.classList.add("leaf-popup-error-shake");
    setTimeout(() => popup.classList.remove("leaf-popup-error-shake"), 800);
  }
}

function renderError(popup, url, isDirectFallback, videoSrcUrl, errorMsg) {
  const content = popup.querySelector(".leaf-popup-content");
  const headerInfo = popup.querySelector(".leaf-popup-video-info");
  if (headerInfo) headerInfo.remove();

  // Determine if this is a connection/offline error or a specific extraction error
  const isOffline = !errorMsg || 
                    errorMsg.includes("Failed to fetch") || 
                    errorMsg.includes("NetworkError") || 
                    errorMsg.includes("Could not establish connection") || 
                    errorMsg.includes("HTTP 502") ||
                    errorMsg.includes("HTTP 504");

  const title = isOffline ? "Leaf App Offline" : "Extraction Failed";
  const desc = isOffline 
    ? "Please open the Leaf Downloader desktop application and try again." 
    : (errorMsg || "Unable to extract playable video streams from this page.");

  setSafeHTML(content, `
    <div class="leaf-error-container">
      <div class="leaf-error-icon">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <h3>${title}</h3>
      <p style="margin-top: 8px; color: #888; font-size: 13px; line-height: 1.4; padding: 0 15px; word-break: break-word;">${desc}</p>
      <button class="leaf-retry-btn" style="margin-top: 15px;">Retry Connection</button>
    </div>
  `);

  const retryBtn = content.querySelector(".leaf-retry-btn");
  retryBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setSafeHTML(popup, buildPopupSkeleton());
    attachCloseBtn(popup);
    fetchMetadata(url, popup, isDirectFallback, videoSrcUrl);
  });
}

// ---------------------------------------------------------------------------
// Universal Hover Video Detector
// ---------------------------------------------------------------------------

function repositionBar(bar) {
  const video = bar.leafVideo;
  if (!video || !document.contains(video)) {
    bar.remove();
    return;
  }

  if (video.dataset.leafDraggedX && video.dataset.leafDraggedY) {
    bar.style.left = `${video.dataset.leafDraggedX}px`;
    bar.style.top = `${video.dataset.leafDraggedY}px`;
    bar.style.right = "auto";
    return;
  }

  const rect = video.getBoundingClientRect();
  const top = rect.top + window.scrollY;
  const left = rect.left + window.scrollX;

  const barTop = top + 10;
  const barWidth = bar.offsetWidth || 140;
  const barLeft = left + rect.width - barWidth - 10;

  bar.style.top = `${barTop}px`;
  bar.style.left = `${barLeft}px`;
  bar.style.right = "auto";
}

function repositionPopup(popup, bar) {
  const barRect = bar.getBoundingClientRect();
  const barTop = barRect.top + window.scrollY;
  const barLeft = barRect.left + window.scrollX;

  popup.style.top = `${barTop + barRect.height + 6}px`;
  popup.style.left = `${barLeft + barRect.width - 330}px`;
}

function repositionAllHoverBars() {
  const bars = document.querySelectorAll("[data-leaf-bar]");
  bars.forEach(bar => {
    repositionBar(bar);
  });

  const popup = document.getElementById(POPUP_ID);
  if (popup && popup.dataset.leafAssocBarId) {
    const associatedBar = document.querySelector(`[data-leaf-bar-id="${popup.dataset.leafAssocBarId}"]`);
    if (associatedBar) {
      repositionPopup(popup, associatedBar);
    } else {
      closePopup(popup);
    }
  }
}

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
  
  const barId = "leaf-bar-" + Math.random().toString(36).substr(2, 9);
  bar.dataset.leafBarId = barId;
  bar.leafVideo = video;

  setSafeHTML(bar, `
    <div class="leaf-hover-bar-btn">
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px; flex-shrink: 0;">
        <path d="M12 3v12"/>
        <path d="M8 11l4 4 4-4"/>
        <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
      </svg>
      <span>Download Video</span>
    </div>
    <div class="leaf-hover-bar-close" title="Dismiss">&times;</div>
  `);

  // Drag-and-drop state variables
  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let initialBarX = 0;
  let initialBarY = 0;
  const dragThreshold = 5; // px
  let dragDetected = false;

  function onMouseMove(e) {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    if (!dragDetected && (Math.abs(dx) > dragThreshold || Math.abs(dy) > dragThreshold)) {
      dragDetected = true;
      bar.classList.add("leaf-grabbing");
    }

    if (dragDetected) {
      const newX = initialBarX + dx;
      const newY = initialBarY + dy;

      bar.style.left = `${newX}px`;
      bar.style.top = `${newY}px`;
      bar.style.right = "auto";

      video.dataset.leafDraggedX = newX;
      video.dataset.leafDraggedY = newY;

      // Real-time update of any open popup attached to this bar
      const popup = document.getElementById(POPUP_ID);
      if (popup && popup.dataset.leafAssocBarId === bar.dataset.leafBarId) {
        popup.style.top = `${newY + bar.offsetHeight + 6}px`;
        popup.style.left = `${newX + bar.offsetWidth - 330}px`;
      }
    }
  }

  function onMouseUp(e) {
    if (!isDragging) return;
    isDragging = false;
    bar.classList.remove("leaf-grabbing");
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);

    if (dragDetected) {
      // Mark as just dragged to prevent click handler trigger
      bar.dataset.leafJustDragged = "true";
      setTimeout(() => {
        delete bar.dataset.leafJustDragged;
      }, 50);
    }
  }

  bar.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return; // Left click only
    if (e.target.closest(".leaf-hover-bar-close")) return;

    isDragging = true;
    dragDetected = false;
    startX = e.clientX;
    startY = e.clientY;

    const rect = bar.getBoundingClientRect();
    initialBarX = rect.left + window.scrollX;
    initialBarY = rect.top + window.scrollY;

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);

    // Prevent text selection
    e.preventDefault();
  });

  const dlBtn = bar.querySelector(".leaf-hover-bar-btn");
  dlBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (bar.dataset.leafJustDragged === "true") {
      return;
    }

    const existingPopup = document.getElementById(POPUP_ID);
    if (existingPopup) {
      const isSame = existingPopup.dataset.leafAssocBarId === barId;
      closePopup(existingPopup);
      if (isSame) return; // Toggle off
    }

    showVideoPopup(video, bar);
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

  document.body.appendChild(bar);
  repositionBar(bar);

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
async function showVideoPopup(video, bar) {
  const videoSrcUrl = getVideoSourceUrl(video);

  const existingPopup = document.getElementById(POPUP_ID);
  if (existingPopup) closePopup(existingPopup);

  const popup = document.createElement("div");
  popup.id = POPUP_ID;
  popup.className = "leaf-popup-card leaf-fade-in";
  setSafeHTML(popup, buildPopupSkeleton());
  attachCloseBtn(popup);

  document.body.appendChild(popup);
  popup.style.position = "absolute";
  popup.style.zIndex = "2147483647";
  popup.dataset.leafAssocBarId = bar.dataset.leafBarId;

  repositionPopup(popup, bar);

  // Resolve the download URL (may be async when inside an iframe)
  const { url, isDirectFallback } = await resolveDownloadUrl(video);

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
  const popup = document.getElementById(POPUP_ID);
  if (popup) closePopup(popup);
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
    setSafeHTML(popup, buildPopupSkeleton());
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

// Update coordinates on layout/viewport events
window.addEventListener("scroll", repositionAllHoverBars, { passive: true });
window.addEventListener("resize", repositionAllHoverBars, { passive: true });

// Align layout shifts and newly added elements periodically
setInterval(repositionAllHoverBars, 150);

// Initial injection
tryInject();
setupLightweightObserver();
