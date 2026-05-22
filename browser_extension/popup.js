/**
 * Leaf Downloader — Popup Script
 */

const API_BASE = "http://127.0.0.1:9549";

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const sendBtn = document.getElementById("sendUrlBtn");
const feedback = document.getElementById("feedback");

/**
 * Check app status and update UI
 */
async function checkStatus() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);

    const res = await fetch(`${API_BASE}/api/ping`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (res.ok) {
      setStatus(true);
    } else {
      setStatus(false);
    }
  } catch {
    setStatus(false);
  }
}

function setStatus(online) {
  if (online) {
    statusDot.className = "status-dot online";
    statusText.textContent = "Connected to Leaf";
    sendBtn.disabled = false;
  } else {
    statusDot.className = "status-dot offline";
    statusText.textContent = "App is offline";
    sendBtn.disabled = true;
  }
}

/**
 * Send the active tab's URL to the desktop app
 */
sendBtn.addEventListener("click", async () => {
  sendBtn.disabled = true;
  feedback.textContent = "";
  feedback.className = "feedback";

  try {
    const tabs = await browser.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tabs.length || !tabs[0].url) {
      showFeedback("No active tab found", "error");
      return;
    }

    const url = tabs[0].url;

    const res = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (res.ok) {
      showFeedback("✓ Sent to Leaf!", "success");
    } else {
      const data = await res.json().catch(() => ({}));
      showFeedback(data.error || "Request failed", "error");
    }
  } catch (err) {
    showFeedback("Cannot reach Leaf app", "error");
  } finally {
    setTimeout(() => {
      sendBtn.disabled = false;
    }, 1000);
  }
});

function showFeedback(text, type) {
  feedback.textContent = text;
  feedback.className = `feedback ${type}`;
  setTimeout(() => {
    feedback.textContent = "";
    feedback.className = "feedback";
  }, 3000);
}

// Check on open
checkStatus();
