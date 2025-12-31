// popup.js - Popup control logic (Multi-tab support)

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const stopAllBtn = document.getElementById('stopAllBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const activeCountEl = document.getElementById('activeCount');
const sessionsList = document.getElementById('sessionsList');

let currentTabId = null;

// Update UI status
function updateStatus(state, text, activeCount = 0) {
  statusDot.className = 'status-dot ' + state;
  statusText.textContent = text;

  // Update active count badge
  if (activeCount > 0) {
    activeCountEl.textContent = activeCount;
    activeCountEl.style.display = 'inline';
    stopAllBtn.style.display = 'block';
  } else {
    activeCountEl.style.display = 'none';
    stopAllBtn.style.display = 'none';
  }
}

// Update button states based on current tab capture status
function updateButtons(isCurrentTabCapturing) {
  if (isCurrentTabCapturing) {
    startBtn.style.display = 'none';
    stopBtn.style.display = 'block';
  } else {
    startBtn.style.display = 'block';
    stopBtn.style.display = 'none';
    startBtn.disabled = false;
  }
}

// Render active sessions list
function renderSessions(sessions) {
  sessionsList.innerHTML = '';

  if (sessions.length === 0) {
    return;
  }

  sessions.forEach(session => {
    const item = document.createElement('div');
    item.className = 'session-item';

    const dot = document.createElement('div');
    dot.className = 'dot';

    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = session.tabTitle || ('Tab ' + session.tabId);
    title.title = session.tabTitle;

    const stopBtnItem = document.createElement('button');
    stopBtnItem.className = 'stop-btn';
    stopBtnItem.textContent = 'Stop';
    stopBtnItem.onclick = () => stopTabCapture(session.tabId);

    item.appendChild(dot);
    item.appendChild(title);
    item.appendChild(stopBtnItem);
    sessionsList.appendChild(item);
  });
}

// Stop capture for a specific tab
function stopTabCapture(tabId) {
  chrome.runtime.sendMessage({
    action: 'stopCapture',
    tabId: tabId
  }, (response) => {
    if (response && response.success) {
      refreshStatus();
    }
  });
}

// Refresh all status
async function refreshStatus() {
  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    currentTabId = tab.id;
  }

  // Get status for current tab
  chrome.runtime.sendMessage({
    action: 'getActiveTabStatus',
    tabId: currentTabId
  }, (response) => {
    if (response) {
      updateButtons(response.isCapturing);

      if (response.isCapturing) {
        updateStatus('capturing', 'Capturing this tab...', response.activeCount);
      } else if (response.activeCount > 0) {
        updateStatus('connected', response.activeCount + ' tab(s) active', response.activeCount);
      } else {
        updateStatus('', 'Not connected', 0);
      }
    }
  });

  // Get all active sessions
  chrome.runtime.sendMessage({ action: 'getAllSessions' }, (response) => {
    if (response && response.sessions) {
      renderSessions(response.sessions);
    }
  });
}

// Initialize
refreshStatus();

// Start capture for current tab
startBtn.addEventListener('click', async () => {
  startBtn.disabled = true;
  updateStatus('', 'Connecting...', 0);

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab) {
      updateStatus('error', 'Cannot get current tab', 0);
      startBtn.disabled = false;
      return;
    }

    currentTabId = tab.id;

    chrome.runtime.sendMessage({
      action: 'startCapture',
      tabId: tab.id
    }, (response) => {
      if (response && response.success) {
        updateStatus('capturing', 'Capturing this tab...', response.activeCount);
        updateButtons(true);
        refreshStatus();
      } else {
        updateStatus('error', response?.error || 'Start failed', 0);
        startBtn.disabled = false;
      }
    });
  } catch (error) {
    updateStatus('error', error.message, 0);
    startBtn.disabled = false;
  }
});

// Stop capture for current tab
stopBtn.addEventListener('click', () => {
  if (currentTabId) {
    stopTabCapture(currentTabId);
  }
});

// Stop all captures
stopAllBtn.addEventListener('click', () => {
  chrome.runtime.sendMessage({ action: 'stopAllCaptures' }, (response) => {
    if (response && response.success) {
      updateStatus('', 'All captures stopped', 0);
      updateButtons(false);
      renderSessions([]);
    }
  });
});

// Listen for status updates
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'statusUpdate') {
    refreshStatus();
  }
});
