# Real-time Subtitle Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real-time audio streaming from frontend to backend for STT processing, broadcasting the subtitles to all participants via Odoo's WebSocket bus.

**Architecture:** A new frontend service captures 1.5s audio chunks and POSTs them to a new Odoo controller endpoint. The controller processes them with a fast STT pass (or simulates it for now) and broadcasts the result via `bus.bus`. The `RecordingSubtitle` component listens to these events and renders them.

**Tech Stack:** JavaScript (Odoo OWL), Python (Odoo controllers), XML.

## Global Constraints

- Modify files within the `aidt_meeting_minutes` custom addon.
- Follow the existing Odoo OWL component and service patterns.

---

### Task 1: Create Audio Stream Service (Frontend)

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/audio_stream_service.js`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py:150-160`
- Modify: `custom-addons/aidt_meeting_minutes/static/src/call_patch.js`

**Interfaces:**
- Consumes: `discuss.rtc` service to access the microphone.
- Produces: Continuously POSTs audio blobs to `/discuss/channel/<id>/stream_audio`.

- [ ] **Step 1: Write `audio_stream_service.js`**

```javascript
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

export class AudioStreamService {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.recorder = null;
        this.intervalId = null;
        this.isActive = false;
        
        this.env.bus.addEventListener("discuss.call.joined", () => this.start());
        this.env.bus.addEventListener("discuss.call.left", () => this.stop());
    }

    start() {
        if (this.isActive) return;
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack) return;

        this.isActive = true;
        const stream = new MediaStream([micTrack.clone()]);
        try {
            this.recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
        } catch (e) {
            console.warn("MediaRecorder not supported", e);
            return;
        }

        this.recorder.ondataavailable = async (e) => {
            if (e.data.size > 0 && this.rtc.state?.channel?.id) {
                const channelId = this.rtc.state.channel.id;
                const form = new FormData();
                form.append("audio", e.data, "chunk.webm");
                
                try {
                    await browser.fetch(`/discuss/channel/${channelId}/stream_audio`, {
                        method: "POST",
                        body: form,
                    });
                } catch (err) {
                    console.error("Failed to upload subtitle chunk", err);
                }
            }
        };

        this.recorder.start(1500); // 1.5 second chunks
    }

    stop() {
        this.isActive = false;
        if (this.recorder && this.recorder.state !== "inactive") {
            this.recorder.stop();
        }
        this.recorder = null;
    }
}

export const audioStreamService = {
    dependencies: ["discuss.rtc"],
    start(env, services) {
        return new AudioStreamService(env, services);
    },
};

registry.category("services").add("aidt_meeting.audio_stream", audioStreamService);
```

- [ ] **Step 2: Register in `__manifest__.py`**

Add `'aidt_meeting_minutes/static/src/audio_stream_service.js',` to `web.assets_backend` right before `recording_subtitle.js`.

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/audio_stream_service.js custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "feat(ui): add audio_stream_service for realtime subtitles"
```

---

### Task 2: Create Stream Audio Endpoint (Backend)

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/controllers/main.py`

**Interfaces:**
- Consumes: POST `/discuss/channel/<id>/stream_audio` from frontend.
- Produces: Broadcasts `aidt_meeting_minutes/subtitle_update` to `discuss.channel_<id>`.

- [ ] **Step 1: Add Endpoint in `controllers/main.py`**

Add the following route to `AidtMeetingController`:

```python
    @http.route('/discuss/channel/<int:channel_id>/stream_audio', type='http', auth='user', methods=['POST'], csrf=False)
    def stream_audio_subtitle(self, channel_id, audio, **kwargs):
        """Nhận chunk audio ngắn, xử lý STT nhanh và broadcast qua bus."""
        partner = request.env.user.partner_id
        channel = request.env['discuss.channel'].search([('id', '=', channel_id)])
        if not channel:
            return request.make_json_response({'error': 'not_found'}, status=404)
        
        raw_audio = audio.read()
        if len(raw_audio) < 100:  # Quá ngắn hoặc rỗng
            return request.make_json_response({'ok': True})
            
        # TODO: Tích hợp VAD và Whisper fast STT ở đây.
        # Tạm thời giả lập kết quả trả về để hoàn thiện luồng UI.
        transcript = "..."  # Sẽ thay bằng kết quả của model ASR sau
        
        if transcript:
            request.env['bus.bus']._sendone(
                channel,
                'aidt_meeting_minutes/subtitle_update',
                {
                    'text': transcript,
                    'speaker_name': partner.name,
                    'partner_id': partner.id,
                }
            )
            
        return request.make_json_response({'ok': True})
```

- [ ] **Step 2: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/controllers/main.py
git commit -m "feat(backend): add stream_audio endpoint for realtime subtitles"
```

---

### Task 3: Refactor Recording Subtitle Component

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.js`
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.xml`

**Interfaces:**
- Consumes: `bus_service` for `aidt_meeting_minutes/subtitle_update` events.

- [ ] **Step 1: Update `recording_subtitle.js`**

```javascript
/** @odoo-module **/
import { Component, onWillStart, onWillDestroy, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class RecordingSubtitle extends Component {
    static template = "aidt_meeting_minutes.RecordingSubtitle";
    static props = {
        isActiveCall: { type: Boolean, optional: true },
    };

    setup() {
        this.busService = useService("bus_service");
        this.state = useState({
            text: "",
            speakerName: "",
            isVisible: false,
        });

        this.timeoutId = null;
        this.onSubtitleUpdate = this.onSubtitleUpdate.bind(this);

        onWillStart(() => {
            this.busService.subscribe("aidt_meeting_minutes/subtitle_update", this.onSubtitleUpdate);
        });

        onWillDestroy(() => {
            if (this.timeoutId) clearTimeout(this.timeoutId);
            // Odoo bus_service doesn't have an explicit unsubscribe in older versions,
            // but normally it removes listeners automatically if bound to component lifecycle,
            // or we use addEventListener on a custom bus. For simple subscribe, it's fine.
        });
    }
    
    onSubtitleUpdate(payload) {
        if (!this.props.isActiveCall) return;
        
        this.state.text = payload.text;
        this.state.speakerName = payload.speaker_name;
        this.state.isVisible = true;

        if (this.timeoutId) clearTimeout(this.timeoutId);
        this.timeoutId = setTimeout(() => {
            this.state.isVisible = false;
        }, 4000);
    }
}
```

- [ ] **Step 2: Update `recording_subtitle.xml`**

Change the rendering to include the speaker name:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <!-- Inject right after RecordingBanner -->
    <t t-name="aidt_meeting_minutes.CallSubtitle"
       t-inherit="discuss.Call" t-inherit-mode="extension">
        <xpath expr="//RecordingBanner" position="after">
            <RecordingSubtitle isActiveCall="isActiveCall"/>
        </xpath>
    </t>

    <t t-name="aidt_meeting_minutes.RecordingSubtitle">
        <div t-if="state.isVisible and state.text" class="o-aidt-recording-subtitle">
            <strong><t t-esc="state.speakerName"/>: </strong>
            <span t-esc="state.text"/>
        </div>
    </t>
</templates>
```

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.*
git commit -m "refactor(ui): make subtitle component listen to websocket events"
```
