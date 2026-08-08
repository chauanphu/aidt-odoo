# Real-time Subtitle Pipeline V2 (STT Redesign)

**Date**: 2026-08-08
**Status**: Approved
**Context**: Re-architecting the real-time subtitle pipeline to minimize latency, eliminate Whisper hallucination on silent/noisy audio, and decouple immediate client feedback from background database persistence.

## 1. Architecture & Data Flow

We are implementing a 3-tier streaming architecture replacing the previous HTTP-polling/chunking approach for subtitles:

1. **Frontend Client (`audio_stream_service.js`)**: Captures audio with `noiseSuppression` and `autoGainControl` enabled. Streams raw 16kHz PCM audio directly to the ASR service over a native `WebSocket`.
2. **ASR Microservice (FastAPI + Faster-Whisper)**: Replaces the `vLLM` container. Maintains an `AudioBuffer` for the WebSocket stream, performs STT decoding with confidence filtering, immediately returns the text to the client via WS, and asynchronously POSTs the result to Odoo.
3. **Odoo Backend**: Receives the async POST from the ASR service, saves the segment to the database, and broadcasts it to other participants via `bus.bus`.

## 2. Frontend Implementation (`audio_stream_service.js`)

- **Audio Capture**: Update `getUserMedia` constraints to include `echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1, sampleRate: 16000`.
- **WebSocket Streaming**: Replace `MediaRecorder` HTTP POSTs with a `WebSocket` connecting to `ws://aidt-asr:8002/ws/stream/{channel_id}_{partner_id}`.
- **AudioWorklet**: Reuse the `worklet_processor` pattern from `recorder_service.js` to extract raw PCM frames and stream them as `Float32Array` or `Int16Array` binary messages over the WebSocket.
- **Immediate Feedback**: When the WebSocket receives a message `{"type": "subtitle", "text": "..."}`, it immediately dispatches the `aidt_meeting_minutes/subtitle_update` event so the speaker sees their own text instantly.

## 3. ASR Microservice (FastAPI)

- **Containerization**: Update `docker/asr.Dockerfile` and `docker-compose.ai.yml` to run a Python FastAPI app using Uvicorn on port 8002, replacing the `vLLM` entrypoint.
- **WebSocket Endpoint**: `/ws/stream/{session_id}`.
- **AudioBuffer**: 
  - Debounce logic: Merge chunks until `is_speech_end` and `duration >= 300ms`, or `duration >= 8s`.
- **Faster-Whisper**:
  - Model: `PhoWhisper-large-ct2` (or mapped model path).
  - Parameters: `beam_size=2`, `vad_filter=True`, `no_speech_threshold=0.6`.
  - Filter logic: Drop segments if `avg_logprob < -1.0` or `no_speech_prob > 0.6`.
- **Hallucination Filter**: 
  - Port `HALLUCINATION_BLACKLIST` and `is_hallucination()` logic from `text_filter.py`.
  - Drop known YouTube subtitle patterns and repetition loops.
- **Async Persistence**: 
  - After sending the subtitle to the WS client, spawn an `asyncio.create_task` to send a POST request with `httpx` to Odoo's backend API.

## 4. Odoo Backend Integration

- **Controller**: Add `POST /aidt_meeting/api/save_segment` (auth via internal IP or a shared secret token since the ASR service is making the request).
- **Data Persistence**: Accept `{"session_id", "text", "speaker_id"}`. Create `aidt.meeting.segment` records for the meeting.
- **Broadcasting**: Execute `request.env['bus.bus']._sendone(...)` with the `subtitle_update` event. The speaker's frontend will ignore this bus event if it already rendered the text from the WS, but other participants in the channel will receive it and display the subtitle.

## 5. Deployment & Configuration

- `docker-compose.ai.yml`: The `aidt-asr` service will map its port and run the new FastAPI server. It requires access to the Whisper model weights.
- Network routing: The Odoo frontend needs to connect to the ASR WebSocket. If Odoo is served via a reverse proxy (Nginx), the WS route `/asr-ws/` might need to be proxied to `aidt-asr:8002`.

## 6. Spec Self-Review Notes
- *Placeholder scan*: No placeholders.
- *Internal consistency*: The flow from Frontend -> WS -> FastAPI -> HTTP -> Odoo is consistent.
- *Scope*: This strictly focuses on the real-time subtitle pipeline redesign. It does not touch the 15s MP3 batch recording pipeline for the final meeting minutes (which continues to use `recorder_service.js`).
