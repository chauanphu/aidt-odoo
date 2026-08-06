# Design Spec: Odoo AI Meeting Real-Time Subtitles & Summary Trigger

## 1. Overview
This specification outlines the enhancements to the Odoo Discuss Call UI and the backend summary trigger logic. The primary goals are to provide real-time subtitles (Closed Captions) during a recorded meeting and to silently store AI summaries without spamming the channel's chat log.

## 2. Architecture & Approach
We are using a **Hybrid STT Approach**:
1. **Real-time Subtitles (Frontend):** Uses the browser's native `Web Speech API` (`window.SpeechRecognition`) for 0-latency captioning overlaid directly on the Discuss video call UI. 
2. **High-Fidelity Transcription & Summary (Backend):** Continues to use the existing chunked audio recording system that sends audio to the server for Whisper/PhoWhisper STT processing and subsequent Ollama summarization.

## 3. Frontend: Real-time Subtitle UI
- **Location:** A new UI overlay component (`recording_subtitle.xml` / `recording_subtitle.js`) will be injected into the active Discuss Call interface.
- **Design:** The overlay will feature a dark translucent background with white, legible text, positioned at the bottom-center of the screen.
- **SpeechRecognition Service:**
  - Instantiated when the user is in an active recording session.
  - Listens to the local microphone, converting speech to text via `interimResults`.
  - When `onresult` is fired, the text is pushed to the subtitle component.
  - Subtitles will auto-clear (fade out) after 3-5 seconds of silence to prevent obscuring the video feed.

## 4. Backend: Summary & Notification Logic
- **Target File:** `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`
- **Modifications:**
  - Locate `_finalize()` and `_run_summary()`.
  - Remove the calls to `message_post()` that currently broadcast the raw transcript and the JSON summary results into the Discuss channel.
  - Ensure the internal state transitions (e.g., from `processing` to `done`) continue to function correctly so the data is saved in the `aidt.meeting.recording` form view.
- **Outcome:** The channel chat remains clean. Managers and participants will view the results by navigating to the "Quản lý cuộc họp" (Meeting Management) backend menu.

## 5. Limitations
- The `Web Speech API` is browser-dependent (works best on Chromium-based browsers like Chrome, Edge).
- The real-time text might slightly differ from the final Whisper-generated transcript due to different underlying STT engines.
