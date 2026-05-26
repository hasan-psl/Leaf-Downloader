/**
 * Leaf Downloader — Popup Script
 */

const API_BASE = "http://127.0.0.1:9549";

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const sendBtn = document.getElementById("sendUrlBtn");
const feedback = document.getElementById("feedback");

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

/**
 * Check app status and update UI
 */
async function checkStatus() {
  try {
    const data = await callApi("/api/ping", "GET");
    if (data && data.status === "running") {
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
    await callApi("/api/download", "POST", { url });
    showFeedback("✓ Sent to Leaf!", "success");
  } catch (err) {
    showFeedback(err.message || "Cannot reach Leaf app", "error");
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
