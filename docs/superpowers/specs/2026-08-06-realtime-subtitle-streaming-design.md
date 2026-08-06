# Real-time Subtitle Streaming Design

## 1. Overview
The current real-time subtitle implementation uses the browser's `SpeechRecognition` API (Web Speech API). This approach has severe limitations:
- **No Synchronization**: Subtitles are only generated locally and not broadcasted to other participants in the meeting.
- **High Latency & Poor Quality**: STT quality depends entirely on the browser's engine (which struggles with Vietnamese) and often fails to capture speech.

**Goal**: Replace the local Web Speech API with a streaming architecture where the frontend sends audio chunks to the Odoo backend, which processes them using a local AI (Whisper/PhoWhisper) and broadcasts the subtitles to all participants via Odoo's WebSocket bus.

## 2. Architecture & Data Flow

### 2.1. Frontend: Audio Capture & Streaming
- Instead of using `window.SpeechRecognition`, the frontend will utilize `MediaRecorder` to capture the user's microphone.
- Audio will be recorded in small chunks (e.g., 1-2 seconds) using a lightweight format (e.g., audio/webm, mono, 16kHz).
- A new service, `audio_stream_service.js`, will handle the recording loop and stream these chunks to the Odoo backend via a new API endpoint.

### 2.2. Backend: Real-time STT Processing
- A new Odoo Controller endpoint (`POST /discuss/channel/<id>/stream_audio`) will receive the incoming audio chunks from each participant.
- The backend will maintain an audio buffer for each active speaker.
- To prevent hallucination and optimize performance, a Voice Activity Detection (VAD) mechanism will filter out silence.
- Chunks containing speech will be processed by the local Whisper/PhoWhisper model.
- Once transcribed, the backend will construct a payload containing the speaker's name, the text, and a timestamp.

### 2.3. Frontend & Backend: Subtitle Synchronization
- The backend will broadcast the transcribed text to all participants in the meeting channel using Odoo's internal WebSocket system (`bus.env['bus.bus']._sendone()`).
- The frontend component `recording_subtitle.js` will be refactored to stop listening to local mic events and instead subscribe to the channel's `meeting_subtitle_update` events via the bus service.
- When an event is received, the subtitle UI will display the text in the format: `[Speaker Name]: Transcript...`.
- Subtitles will automatically fade out after 4-5 seconds of inactivity.

## 3. Components Overview

### Frontend
1. **`audio_stream_service.js` (New)**: 
   - Manages microphone permissions and the `MediaRecorder` instance.
   - Chunks audio and handles POST requests to the backend.
   - Includes retry logic for network instability.
2. **`recording_subtitle.js` & `recording_subtitle.xml` (Modified)**:
   - Removes all `window.SpeechRecognition` logic.
   - Subscribes to Odoo bus events.
   - Updates UI to display the speaker's name alongside the text.

### Backend
1. **`meeting_ai_controller.py` (Modified/New)**:
   - Adds the endpoint `/discuss/channel/<id>/stream_audio`.
   - Handles the audio buffer, VAD, and Whisper inference invocation.
   - Dispatches bus notifications to the channel.

## 4. Error Handling & Constraints
- **Network Latency / Server Overload**: If STT responses from the backend are delayed, the frontend will queue and display them sequentially to preserve the order of conversation.
- **Microphone Access**: If the user denies microphone permissions, `audio_stream_service.js` will catch the error and display a clear, unintrusive UI warning that subtitles cannot be generated for their voice.
- **Fallback**: The backend STT process must fail gracefully. If the Whisper model crashes or is overwhelmed, the endpoint should return a 503 status, and the frontend should back off (reduce chunk sending frequency).

## 5. Testing Strategy
- Unit tests for the frontend to verify bus subscription and subtitle rendering.
- Python tests for the new controller endpoint to ensure it correctly buffers audio and triggers the STT pipeline.
- End-to-End manual testing with multiple users in a Discuss call to verify synchronization and latency.
