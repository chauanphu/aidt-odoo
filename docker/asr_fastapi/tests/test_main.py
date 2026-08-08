import sys
import os
import asyncio
import pytest
import numpy as np
from unittest.mock import patch, AsyncMock

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient


def test_websocket_endpoint_transcribes_and_posts_to_odoo():
    from main import app

    client = TestClient(app)

    # 16kHz PCM16 audio for 0.5 seconds = 8000 int16 samples = 16000 bytes
    pcm_samples = np.zeros(8000, dtype=np.int16)
    binary_data = pcm_samples.tobytes()

    with patch("main.persist_and_broadcast", new_callable=AsyncMock) as mock_persist:
        with client.websocket_connect("/ws/stream/test_session_1?channel_id=5&speaker_id=10") as websocket:
            websocket.send_bytes(binary_data)
            response = websocket.receive_json()

            assert response == {"type": "subtitle", "text": "mock transcript"}

            mock_persist.assert_called_once_with("mock transcript", "test_session_1", 5, 10)


def test_websocket_endpoint_filters_low_logprob_and_hallucination():
    from main import app, model

    client = TestClient(app)
    pcm_samples = np.zeros(8000, dtype=np.int16)
    binary_data = pcm_samples.tobytes()

    class LowConfidenceSegment:
        def __init__(self):
            self.text = "low confidence text"
            self.avg_logprob = -1.5  # < -1.0, should be filtered out
            self.no_speech_prob = 0.1

    class HallucinationSegment:
        def __init__(self):
            self.text = "cảm ơn các bạn đã theo dõi"  # Blacklisted hallucination
            self.avg_logprob = -0.2
            self.no_speech_prob = 0.1

    # Mock transcribe returning 2 segments that should both be filtered
    with patch.object(model, "transcribe", return_value=([LowConfidenceSegment(), HallucinationSegment()], None)):
        with patch("main.persist_and_broadcast", new_callable=AsyncMock) as mock_persist:
            with client.websocket_connect("/ws/stream/test_session_2") as websocket:
                websocket.send_bytes(binary_data)
                websocket.close()

            mock_persist.assert_not_called()


def test_persist_and_broadcast_success():
    from main import persist_and_broadcast, ODOO_API_URL

    async def run_test():
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200

            await persist_and_broadcast("hello odoo", "session_99", 1, 2)

            mock_post.assert_called_once_with(
                ODOO_API_URL,
                json={
                    "session_id": "session_99",
                    "text": "hello odoo",
                    "channel_id": 1,
                    "speaker_id": 2,
                },
            )

    asyncio.run(run_test())


def test_persist_and_broadcast_exception_handled():
    from main import persist_and_broadcast

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
            # Should not raise exception
            await persist_and_broadcast("hello odoo", "session_99", 1, 2)

    asyncio.run(run_test())
