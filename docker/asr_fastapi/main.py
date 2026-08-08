from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import numpy as np
import httpx
from audio_buffer import AudioBuffer
from text_filter import is_hallucination, clean_transcript
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# Mock for faster_whisper to avoid downloading models in tests
class MockModel:
    def transcribe(self, audio, **kwargs):
        class MockSegment:
            def __init__(self):
                self.text = "mock transcript"
                self.avg_logprob = -0.5
                self.no_speech_prob = 0.1
        return [MockSegment()], None

model = MockModel()
ODOO_API_URL = "http://odoo:8069/aidt_meeting/api/save_segment"

async def persist_and_broadcast(text: str, session_id: str, channel_id: int, speaker_id: int):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(ODOO_API_URL, json={
                "session_id": session_id,
                "text": text,
                "channel_id": channel_id,
                "speaker_id": speaker_id
            })
        except Exception as e:
            logger.error(f"Failed to push to Odoo: {e}")

@app.websocket("/ws/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, channel_id: int = 0, speaker_id: int = 0):
    await websocket.accept()
    audio_buf = AudioBuffer()
    try:
        while True:
            data = await websocket.receive_bytes()
            # Convert bytes (PCM16) to float32 numpy array
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Assume each incoming WS frame is a chunk. We pass is_speech_end=True for simplicity here,
            # or rely on VAD from client if implemented. For now, treat every frame as ready to buffer.
            merged = audio_buf.add_chunk(audio_data, is_speech_end=True)
            
            if merged is not None:
                segments, _ = model.transcribe(
                    merged, language="vi", beam_size=2, vad_filter=True, no_speech_threshold=0.6
                )
                
                results = []
                for seg in segments:
                    if seg.avg_logprob < -1.0 or seg.no_speech_prob > 0.6:
                        continue
                    if not is_hallucination(seg.text):
                        results.append(clean_transcript(seg.text))
                
                final_text = " ".join(results).strip()
                if final_text:
                    await websocket.send_json({"type": "subtitle", "text": final_text})
                    asyncio.create_task(persist_and_broadcast(final_text, session_id, channel_id, speaker_id))
    except WebSocketDisconnect:
        pass
