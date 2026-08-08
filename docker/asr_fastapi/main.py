from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os
import asyncio
import numpy as np
import httpx
from audio_buffer import AudioBuffer
from text_filter import is_hallucination, clean_transcript
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

ODOO_API_URL = os.getenv("ODOO_API_URL", "http://odoo:8069/aidt_meeting/api/save_segment")


class MockModel:
    def transcribe(self, audio, **kwargs):
        class MockSegment:
            def __init__(self):
                self.text = "mock transcript"
                self.avg_logprob = -0.5
                self.no_speech_prob = 0.1

        return [MockSegment()], None


def get_model():
    testing = os.getenv("TESTING", "0") == "1"
    use_mock = os.getenv("USE_MOCK_MODEL", "1" if testing else "0") == "1"
    if testing or use_mock:
        return MockModel()
    try:
        model_path = os.getenv("MODEL_PATH", "vinai/phowhisper-large-ct2")
        device = os.getenv("DEVICE", "cpu")
        compute_type = os.getenv("COMPUTE_TYPE", "float32")
        from faster_whisper import WhisperModel

        return WhisperModel(model_path, device=device, compute_type=compute_type)
    except Exception as e:
        logger.warning(f"Failed to load WhisperModel ({e}), falling back to MockModel")
        return MockModel()


model = get_model()

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client


async def persist_and_broadcast(text: str, session_id: str, channel_id: int, speaker_id: int):
    client = get_http_client()
    try:
        await client.post(
            ODOO_API_URL,
            json={
                "session_id": session_id,
                "text": text,
                "channel_id": channel_id,
                "speaker_id": speaker_id,
            },
        )
    except Exception as e:
        logger.error(f"Failed to push to Odoo: {e}")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.websocket("/ws/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, channel_id: int = 0, speaker_id: int = 0):
    await websocket.accept()
    audio_buf = AudioBuffer()
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data or len(data) % 2 != 0:
                logger.warning(f"Received invalid audio byte length: {len(data) if data else 0}")
                continue

            try:
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
            except Exception as e:
                logger.error(f"Error processing audio frame: {e}")
    except WebSocketDisconnect:
        pass
