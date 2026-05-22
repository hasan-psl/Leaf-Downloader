/**
 * Leaf Downloader — Background Service Worker
 * 
 * Polls the desktop app's API server to check connectivity
 * and updates the extension badge accordingly.
 */

const API_BASE = "http://127.0.0.1:9549";
const POLL_INTERVAL = 5000; // 5 seconds

let isAppRunning = false;

/**
 * Check if the desktop app is reachable
 */
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

/**
 * Update the extension badge to show app status
 */
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

// Start polling
checkAppStatus();
setInterval(checkAppStatus, POLL_INTERVAL);

// Listen for messages from popup
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "getStatus") {
    sendResponse({ running: isAppRunning });
  }
});
