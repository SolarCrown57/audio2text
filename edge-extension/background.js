// background.js - Service Worker (Multi-tab support)

// Store all active capture sessions { tabId: { streamId, tabTitle, isCapturing } }
const captureSessions = new Map();

// Create offscreen document for audio processing
async function setupOffscreenDocument() {
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT']
  });

  if (existingContexts.length > 0) {
    return;
  }

  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['USER_MEDIA'],
    justification: 'Process audio streams from multiple tabs'
  });
}

// Close offscreen document only when no active sessions
async function closeOffscreenDocumentIfEmpty() {
  if (captureSessions.size > 0) {
    return;
  }

  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT']
  });

  if (existingContexts.length > 0) {
    await chrome.offscreen.closeDocument();
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getStatus') {
    const tabId = message.tabId;
    if (tabId && captureSessions.has(tabId)) {
      sendResponse({
        isCapturing: true,
        isConnected: true,
        activeCount: captureSessions.size
      });
    } else {
      sendResponse({
        isCapturing: false,
        isConnected: captureSessions.size > 0,
        activeCount: captureSessions.size
      });
    }
    return true;
  }

  if (message.action === 'getActiveTabStatus') {
    const tabId = message.tabId;
    const isCapturing = captureSessions.has(tabId);
    sendResponse({ isCapturing, activeCount: captureSessions.size });
    return true;
  }

  if (message.action === 'getAllSessions') {
    const sessions = [];
    captureSessions.forEach((value, key) => {
      sessions.push({ tabId: key, tabTitle: value.tabTitle });
    });
    sendResponse({ sessions, activeCount: captureSessions.size });
    return true;
  }

  if (message.action === 'startCapture') {
    handleStartCapture(message.tabId)
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.action === 'stopCapture') {
    handleStopCapture(message.tabId)
      .then(() => sendResponse({ success: true, activeCount: captureSessions.size }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.action === 'stopAllCaptures') {
    handleStopAllCaptures()
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }

  // Status update from offscreen
  if (message.action === 'captureStatus') {
    chrome.runtime.sendMessage({
      action: 'statusUpdate',
      tabId: message.tabId,
      state: message.state,
      text: message.text,
      activeCount: captureSessions.size
    }).catch(() => {});
    return false;
  }
});

// Start capturing a specific tab
async function handleStartCapture(tabId) {
  try {
    if (captureSessions.has(tabId)) {
      return { success: false, error: 'This tab is already being captured' };
    }

    const tab = await chrome.tabs.get(tabId);
    const tabTitle = tab.title || `Tab ${tabId}`;

    const streamId = await chrome.tabCapture.getMediaStreamId({
      targetTabId: tabId
    });

    await setupOffscreenDocument();

    await chrome.runtime.sendMessage({
      action: 'startAudioCapture',
      streamId: streamId,
      tabId: tabId,
      tabTitle: tabTitle
    });

    captureSessions.set(tabId, { streamId, tabTitle, isCapturing: true });

    console.log(`[Tab ${tabId}] Capture started: ${tabTitle}`);
    return { success: true, activeCount: captureSessions.size };
  } catch (error) {
    console.error(`[Tab ${tabId}] Capture failed:`, error);
    return { success: false, error: error.message };
  }
}

// Stop capturing a specific tab
async function handleStopCapture(tabId) {
  try {
    if (!captureSessions.has(tabId)) {
      return { success: true };
    }

    await chrome.runtime.sendMessage({
      action: 'stopAudioCapture',
      tabId: tabId
    });

    captureSessions.delete(tabId);
    console.log(`[Tab ${tabId}] Capture stopped`);

    await closeOffscreenDocumentIfEmpty();

    return { success: true };
  } catch (error) {
    console.error(`[Tab ${tabId}] Stop failed:`, error);
    captureSessions.delete(tabId);
    throw error;
  }
}

// Stop all captures
async function handleStopAllCaptures() {
  const tabIds = Array.from(captureSessions.keys());

  for (const tabId of tabIds) {
    try {
      await handleStopCapture(tabId);
    } catch (error) {
      console.error(`[Tab ${tabId}] Stop failed:`, error);
    }
  }

  await closeOffscreenDocumentIfEmpty();
}

// Listen for tab close events
chrome.tabs.onRemoved.addListener((tabId) => {
  if (captureSessions.has(tabId)) {
    handleStopCapture(tabId).catch(console.error);
  }
});

// Listen for tab refresh events
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'loading' && captureSessions.has(tabId)) {
    handleStopCapture(tabId).catch(console.error);
  }
});
