// offscreen.js - Audio capture and processing (Multi-tab support)

const WS_URL = 'ws://localhost:8765';
const TARGET_SAMPLE_RATE = 16000;

// Store all active audio sessions { tabId: { audioContext, mediaStream, websocket, ... } }
const audioSessions = new Map();

// Send status update for a specific tab
function sendStatus(tabId, state, text, isCapturing = false, isConnected = false) {
  chrome.runtime.sendMessage({
    action: 'captureStatus',
    tabId,
    state,
    text,
    isCapturing,
    isConnected
  }).catch(() => {});
}

// Connect WebSocket for a specific tab
function connectWebSocket(tabId, tabTitle) {
  return new Promise((resolve, reject) => {
    try {
      const websocket = new WebSocket(WS_URL);
      websocket.binaryType = 'arraybuffer';

      websocket.onopen = () => {
        console.log('[Tab ' + tabId + '] WebSocket connected');
        sendStatus(tabId, 'connected', 'Server connected', false, true);
        websocket.send(JSON.stringify({
          type: 'init',
          tabId: tabId,
          tabTitle: tabTitle,
          sampleRate: TARGET_SAMPLE_RATE,
          channels: 1,
          format: 'pcm_s16le'
        }));
        resolve(websocket);
      };

      websocket.onclose = () => {
        console.log('[Tab ' + tabId + '] WebSocket disconnected');
        const session = audioSessions.get(tabId);
        if (session) {
          sendStatus(tabId, '', 'Disconnected', false, false);
        }
      };

      websocket.onerror = (error) => {
        console.error('[Tab ' + tabId + '] WebSocket error:', error);
        sendStatus(tabId, 'error', 'Connection failed', false, false);
        reject(error);
      };

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[Tab ' + tabId + '] Server message:', data);
        } catch (e) {
          console.log('[Tab ' + tabId + '] Server raw message:', event.data);
        }
      };
    } catch (error) {
      reject(error);
    }
  });
}

// Resample audio from original sample rate to target sample rate
function resample(audioData, fromSampleRate, toSampleRate) {
  if (fromSampleRate === toSampleRate) {
    return audioData;
  }

  const ratio = fromSampleRate / toSampleRate;
  const newLength = Math.round(audioData.length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcIndexFloor = Math.floor(srcIndex);
    const srcIndexCeil = Math.min(srcIndexFloor + 1, audioData.length - 1);
    const fraction = srcIndex - srcIndexFloor;
    result[i] = audioData[srcIndexFloor] * (1 - fraction) + audioData[srcIndexCeil] * fraction;
  }

  return result;
}

// Convert Float32 to Int16 PCM
function floatTo16BitPCM(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    // 统一使用 0x7FFF 作为量化因子，避免正负极性的不对称失真
    int16Array[i] = Math.round(s * 0x7FFF);
  }
  return int16Array;
}

// Setup audio processing for a specific tab
function setupAudioProcessing(tabId, stream, audioContext, websocket) {
  const originalSampleRate = audioContext.sampleRate;
  console.log('[Tab ' + tabId + '] Sample rate: ' + originalSampleRate + ' -> ' + TARGET_SAMPLE_RATE);

  const sourceNode = audioContext.createMediaStreamSource(stream);
  const bufferSize = 4096;
  const scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);

  let audioBuffer = new Float32Array(0);
  const SEND_INTERVAL_MS = 100;
  const samplesPerSend = Math.floor(TARGET_SAMPLE_RATE * SEND_INTERVAL_MS / 1000);

  scriptProcessor.onaudioprocess = (event) => {
    const session = audioSessions.get(tabId);
    if (!session || !session.isCapturing || !websocket || websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    const inputData = event.inputBuffer.getChannelData(0);
    const resampled = resample(inputData, originalSampleRate, TARGET_SAMPLE_RATE);

    const newBuffer = new Float32Array(audioBuffer.length + resampled.length);
    newBuffer.set(audioBuffer);
    newBuffer.set(resampled, audioBuffer.length);
    audioBuffer = newBuffer;

    while (audioBuffer.length >= samplesPerSend) {
      const chunk = audioBuffer.slice(0, samplesPerSend);
      audioBuffer = audioBuffer.slice(samplesPerSend);
      const pcmData = floatTo16BitPCM(chunk);
      websocket.send(pcmData.buffer);
    }
  };

  // Connect nodes - let user hear the audio
  sourceNode.connect(scriptProcessor);
  scriptProcessor.connect(audioContext.destination);
  sourceNode.connect(audioContext.destination);

  return { sourceNode, scriptProcessor };
}

// Start audio capture for a specific tab
async function startCapture(streamId, tabId, tabTitle) {
  try {
    if (audioSessions.has(tabId)) {
      console.log('[Tab ' + tabId + '] Already capturing');
      return;
    }

    const mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId
        }
      },
      video: false
    });

    const audioContext = new AudioContext();
    const websocket = await connectWebSocket(tabId, tabTitle);
    const { sourceNode, scriptProcessor } = setupAudioProcessing(tabId, mediaStream, audioContext, websocket);

    audioSessions.set(tabId, {
      mediaStream,
      audioContext,
      websocket,
      sourceNode,
      scriptProcessor,
      tabTitle,
      isCapturing: true
    });

    sendStatus(tabId, 'capturing', 'Capturing: ' + tabTitle, true, true);
    console.log('[Tab ' + tabId + '] Capture started: ' + tabTitle);
  } catch (error) {
    console.error('[Tab ' + tabId + '] Start capture failed:', error);
    sendStatus(tabId, 'error', 'Start failed: ' + error.message, false, false);
    throw error;
  }
}

// Stop audio capture for a specific tab
function stopCapture(tabId) {
  const session = audioSessions.get(tabId);
  if (!session) {
    console.log('[Tab ' + tabId + '] No active session to stop');
    return;
  }

  session.isCapturing = false;

  if (session.mediaStream) {
    session.mediaStream.getTracks().forEach(track => track.stop());
  }

  if (session.sourceNode) {
    session.sourceNode.disconnect();
  }
  if (session.scriptProcessor) {
    session.scriptProcessor.disconnect();
  }

  if (session.audioContext) {
    session.audioContext.close().catch(err => console.error('[Tab ' + tabId + '] AudioContext close error:', err));
  }

  if (session.websocket && session.websocket.readyState === WebSocket.OPEN) {
    session.websocket.send(JSON.stringify({ type: 'end', tabId: tabId }));
    session.websocket.close();
  }

  audioSessions.delete(tabId);
  sendStatus(tabId, '', 'Capture stopped', false, false);
  console.log('[Tab ' + tabId + '] Capture stopped');
}

// Stop all captures
function stopAllCaptures() {
  const tabIds = Array.from(audioSessions.keys());
  for (const tabId of tabIds) {
    stopCapture(tabId);
  }
}

// Listen for messages from background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'startAudioCapture') {
    startCapture(message.streamId, message.tabId, message.tabTitle || ('Tab ' + message.tabId))
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.action === 'stopAudioCapture') {
    if (message.tabId) {
      stopCapture(message.tabId);
    } else {
      stopAllCaptures();
    }
    sendResponse({ success: true });
    return false;
  }

  if (message.action === 'getActiveSessions') {
    const sessions = [];
    audioSessions.forEach((value, key) => {
      sessions.push({ tabId: key, tabTitle: value.tabTitle, isCapturing: value.isCapturing });
    });
    sendResponse({ sessions });
    return false;
  }
});
