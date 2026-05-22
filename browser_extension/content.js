/**
 * Leaf Downloader — Firefox Extension Content Script
 * 
 * Injected into YouTube pages to add a download button
 * directly into the video player controls bar.
 * Inspired by IDM's browser integration placement.
 */

const API_BASE = "http://127.0.0.1:9549";
const BUTTON_ID = "leaf-download-btn";

/**
 * Create the download button element
 */
function createDownloadButton() {
  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.className = "ytp-button leaf-download-btn";
  btn.title = "Download with Leaf";
  btn.setAttribute("aria-label", "Download with Leaf Downloader");

  // SVG download icon
  btn.innerHTML = `
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="leaf-dl-icon">
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
 * Handle download button click — send current URL to desktop app
 */
async function handleDownloadClick(e) {
  e.preventDefault();
  e.stopPropagation();

  const btn = document.getElementById(BUTTON_ID);
  if (!btn || btn.classList.contains("leaf-sending")) return;

  const url = window.location.href;
  btn.classList.add("leaf-sending");
  btn.title = "Sending...";

  try {
    const response = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (response.ok) {
      btn.classList.remove("leaf-sending");
      btn.classList.add("leaf-success");
      btn.title = "✓ Sent to Leaf!";
      setTimeout(() => {
        btn.classList.remove("leaf-success");
        btn.title = "Download with Leaf";
      }, 2500);
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (err) {
    btn.classList.remove("leaf-sending");
    btn.classList.add("leaf-error");
    btn.title = "✗ Leaf app is offline";
    setTimeout(() => {
      btn.classList.remove("leaf-error");
      btn.title = "Download with Leaf";
    }, 3000);
  }
}

/**
 * Inject the download button into YouTube's player controls
 */
function injectButton() {
  // Don't inject if already exists
  if (document.getElementById(BUTTON_ID)) return;

  // YouTube's right-side player controls
  const rightControls = document.querySelector(".ytp-right-controls");
  if (!rightControls) return;

  const btn = createDownloadButton();
  
  // Insert as the first child of right controls (leftmost position in the right group)
  rightControls.insertBefore(btn, rightControls.firstChild);
}

/**
 * Remove existing button (for SPA navigation cleanup)
 */
function removeButton() {
  const existing = document.getElementById(BUTTON_ID);
  if (existing) existing.remove();
}

/**
 * Check if current page is a video watch page
 */
function isWatchPage() {
  return window.location.pathname === "/watch" || 
         window.location.pathname.startsWith("/shorts/");
}

/**
 * Main injection logic — tries to inject, retries if controls not ready
 */
function tryInject() {
  if (!isWatchPage()) {
    removeButton();
    return;
  }

  // Try immediately
  injectButton();

  // If controls weren't ready, retry after a short delay
  if (!document.getElementById(BUTTON_ID)) {
    const retryInterval = setInterval(() => {
      if (document.getElementById(BUTTON_ID)) {
        clearInterval(retryInterval);
        return;
      }
      injectButton();
    }, 500);

    // Give up after 10 seconds
    setTimeout(() => clearInterval(retryInterval), 10000);
  }
}

/**
 * Watch for YouTube's SPA navigation events
 */
function setupNavigationListener() {
  // YouTube fires this custom event on SPA navigation
  document.addEventListener("yt-navigate-finish", () => {
    // Small delay to let the new page render
    setTimeout(tryInject, 300);
  });

  // Also watch for player DOM changes via MutationObserver
  const observer = new MutationObserver((mutations) => {
    // Only re-inject if our button was removed (e.g., player rebuild)
    if (isWatchPage() && !document.getElementById(BUTTON_ID)) {
      const rightControls = document.querySelector(".ytp-right-controls");
      if (rightControls) {
        injectButton();
      }
    }
  });

  // Observe the player container for structural changes
  const tryObserve = () => {
    const player = document.getElementById("movie_player");
    if (player) {
      observer.observe(player, { childList: true, subtree: true });
    } else {
      setTimeout(tryObserve, 1000);
    }
  };
  tryObserve();
}

// Initialize
tryInject();
setupNavigationListener();
