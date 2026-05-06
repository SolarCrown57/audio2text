"""
WebSocket Server - Multi-tab support
Receives audio streams from browser extension and forwards to speech recognition
"""

import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Optional
from speech_recognizer import SpeechRecognizer
from event_bus import event_bus


class AudioSession:
    """Single audio session for a browser tab"""

    def __init__(self, tab_id: str, tab_title: str = "", sample_rate: int = 16000):
        self.tab_id = tab_id
        self.tab_title = tab_title or f"Tab {tab_id}"
        self.sample_rate = sample_rate
        self.recognizer: Optional[SpeechRecognizer] = None
        self.is_active = False

    async def start(self):
        """Start recognition session"""
        self.recognizer = SpeechRecognizer(
            tab_id=self.tab_id,
            sample_rate=self.sample_rate,
            on_result=self._on_result
        )
        await self.recognizer.start()
        self.is_active = True
        print(f"[Tab {self.tab_id}] Recognition started: {self.tab_title}")

    async def process_audio(self, audio_data: bytes):
        """Process audio data"""
        if self.recognizer and self.is_active:
            await self.recognizer.send_audio(audio_data)

    async def stop(self):
        """Stop recognition session"""
        self.is_active = False
        if self.recognizer:
            await self.recognizer.stop()
            self.recognizer = None
        print(f"[Tab {self.tab_id}] Recognition stopped: {self.tab_title}")

    def _on_result(self, text: str, is_final: bool):
        """Recognition result callback"""
        event_bus.emit('subtitle_update', {
            'tab_id': self.tab_id,
            'tab_title': self.tab_title,
            'text': text,
            'is_final': is_final
        })


class WebSocketServer:
    """WebSocket Server"""

    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.sessions: Dict[str, AudioSession] = {}
        self.connections: Dict[WebSocketServerProtocol, str] = {}

    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """Handle WebSocket connection"""
        tab_id = None
        tab_title = ""
        session = None

        try:
            async for message in websocket:
                if isinstance(message, str):
                    # JSON control message
                    data = json.loads(message)
                    msg_type = data.get('type')

                    if msg_type == 'init':
                        # Initialize session
                        tab_id = str(data.get('tabId', 'unknown'))
                        tab_title = data.get('tabTitle', f'Tab {tab_id}')
                        sample_rate = data.get('sampleRate', 16000)

                        print(f"[Tab {tab_id}] New connection: {tab_title}, {sample_rate}Hz")

                        # Create and start session
                        session = AudioSession(tab_id, tab_title, sample_rate)
                        self.sessions[tab_id] = session
                        self.connections[websocket] = tab_id

                        await session.start()

                        # Send confirmation
                        await websocket.send(json.dumps({
                            'type': 'ready',
                            'message': 'Recognition service ready'
                        }))

                    elif msg_type == 'end':
                        # End session
                        if session:
                            await session.stop()
                        break

                elif isinstance(message, bytes):
                    # Binary audio data
                    if session and session.is_active:
                        await session.process_audio(message)

        except websockets.exceptions.ConnectionClosed:
            tab_label = tab_id or 'unknown'
            print(f"[Tab {tab_label}] Connection closed")
        except Exception as e:
            print(f"[Tab {tab_id}] Error: {e}")
        finally:
            # Cleanup
            if session:
                await session.stop()
            if tab_id and tab_id in self.sessions:
                del self.sessions[tab_id]
            if websocket in self.connections:
                del self.connections[websocket]

            # Notify UI that tab is closed
            if tab_id:
                event_bus.emit('tab_closed', {'tab_id': tab_id})

    async def start(self):
        """Start server"""
        async with websockets.serve(
            self.handle_connection,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024,  # 10MB max message size
            ping_interval=30,
            ping_timeout=10
        ):
            print(f"WebSocket server started: ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever
