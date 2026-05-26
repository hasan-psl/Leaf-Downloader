/**
 * Leaf Downloader — Background Service Worker
 *
 * - Polls the desktop app's API server for connectivity
 * - Updates the extension badge
 * - Registers a "Download with App" right-click context menu
 * - Forwards context menu clicks to content.js for popup display
 */

const API_BASE = "http://127.0.0.1:9549";
const POLL_INTERVAL = 5000; // ms

let isAppRunning = false;

// ---------------------------------------------------------------------------
// App connectivity polling
// ---------------------------------------------------------------------------

async function checkAppStatus() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);

    const response = await fetch(`${API_BASE}/api/ping`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (response.ok) {
      if (!isAppRunning) {
        isAppRunning = true;
        updateBadge(true);
      }
    } else {
      throw new Error("Not OK");
    }
  } catch (err) {
    if (isAppRunning) {
      isAppRunning = false;
      updateBadge(false);
    }
  }
}

function updateBadge(online) {
  if (online) {
    browser.action.setBadgeText({ text: "ON" });
    browser.action.setBadgeBackgroundColor({ color: "#4caf50" });
    browser.action.setTitle({ title: "Leaf Downloader — Connected" });
  } else {
    browser.action.setBadgeText({ text: "OFF" });
    browser.action.setBadgeBackgroundColor({ color: "#757575" });
    browser.action.setTitle({ title: "Leaf Downloader — App Offline" });
  }
}

checkAppStatus();
setInterval(checkAppStatus, POLL_INTERVAL);

// Register alarms to wake up the background script and check status periodically
browser.alarms.create("checkAppStatusAlarm", { periodInMinutes: 1 });
browser.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "checkAppStatusAlarm") {
    checkAppStatus();
  }
});

// ---------------------------------------------------------------------------
// Context menus
// ---------------------------------------------------------------------------

// Remove any previously registered menus first to avoid duplicates on reload
browser.contextMenus.removeAll().then(() => {
  // Shown when right-clicking on a link
  browser.contextMenus.create({
    id: "leaf-download-link",
    title: "Download with App",
    contexts: ["link"],
  });

  // Shown when right-clicking on a video element
  browser.contextMenus.create({
    id: "leaf-download-video",
    title: "Download with App",
    contexts: ["video"],
  });

  // Shown on any page (selection or background click)
  browser.contextMenus.create({
    id: "leaf-download-page",
    title: "Download Page Video with App",
    contexts: ["page", "selection"],
  });
});

browser.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;

  // Build the payload for content.js
  const payload = {
    type: "contextMenuDownload",
    linkUrl: info.linkUrl || null,
    srcUrl: info.srcUrl || null,
    pageUrl: info.pageUrl || tab.url || null,
  };

  try {
    await browser.tabs.sendMessage(tab.id, payload);
  } catch (err) {
    // Content script may not be injected (e.g. about: pages) — ignore
    console.warn("[Leaf] Could not send context menu message:", err.message);
  }
});

// ---------------------------------------------------------------------------
// Message listener (from popup.js or content.js)
// ---------------------------------------------------------------------------

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "getStatus") {
    sendResponse({ running: isAppRunning });
    return false;
  }

  // Return the top-level tab URL to content scripts running inside iframes.
  // This is essential for sites like Dailymotion/Vimeo where the <video> lives
  // inside a cross-origin iframe (e.g. geo.dailymotion.com) and the content
  // script cannot access the parent page URL via document.referrer or window.top.
  if (message.type === "getTabUrl") {
    sendResponse({ url: sender.tab?.url || null });
    return false;
  }

  if (message.type === "fetchApi") {
    const { endpoint, method, body } = message;
    const url = `${API_BASE}${endpoint}`;

    const options = {
      method: method || "GET",
      headers: {
        "Content-Type": "application/json"
      }
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    fetch(url, options)
      .then(async (response) => {
        const text = await response.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }

        // Successfully reached backend app, update app running state to true
        if (!isAppRunning) {
          isAppRunning = true;
          updateBadge(true);
        }

        sendResponse({
          ok: response.ok,
          status: response.status,
          data: data
        });
      })
      .catch((err) => {
        // Failed to reach backend app, update app running state to false
        if (isAppRunning) {
          isAppRunning = false;
          updateBadge(false);
        }

        sendResponse({
          ok: false,
          error: err.message
        });
      });

    return true; // Keep response channel open for async sendResponse
  }
});
