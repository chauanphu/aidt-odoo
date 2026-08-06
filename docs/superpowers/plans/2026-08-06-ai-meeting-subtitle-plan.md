# AI Meeting Real-Time Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real-time subtitles (Closed Captions) using Web Speech API in the Odoo Discuss Call UI and prevent the backend summary process from posting spam to the chat.

**Architecture:** A new OWL component `RecordingSubtitle` will be injected into the `discuss.Call` interface to display real-time text from the browser's `SpeechRecognition` API. On the backend, `message_post` calls in `_finalize` and `_run_summary` will be removed.

**Tech Stack:** JavaScript (Odoo OWL), Python (Odoo models), XML.

## Global Constraints

- Modify files within the `aidt_meeting_minutes` custom addon.
- Follow the existing Odoo OWL component patterns.
- Ensure the app doesn't break if `window.SpeechRecognition` is not supported (fail gracefully).

---

### Task 1: Real-time Subtitles UI (Frontend)

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.xml`
- Create: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.scss`
- Create: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.js`
- Modify: `custom-addons/aidt_meeting_minutes/static/src/call_patch.js`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py`

**Interfaces:**
- Consumes: The Odoo Discuss Call UI (`isActiveCall` state).
- Produces: A new `RecordingSubtitle` component visible when a recording is active.

- [ ] **Step 1: Write the Subtitle Component Logic (`recording_subtitle.js`)**

```javascript
/** @odoo-module **/
import { Component, onWillStart, onWillDestroy, useState } from "@odoo/owl";

export class RecordingSubtitle extends Component {
    setup() {
        this.state = useState({
            text: "",
            isVisible: false,
        });
        
        this.recognition = null;
        this.timeoutId = null;

        onWillStart(() => {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition && this.props.isActiveCall) {
                this.recognition = new SpeechRecognition();
                this.recognition.continuous = true;
                this.recognition.interimResults = true;
                this.recognition.lang = "vi-VN"; // Default to Vietnamese
                
                this.recognition.onresult = (event) => {
                    let interimTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        if (event.results[i].isFinal) {
                            interimTranscript += event.results[i][0].transcript;
                        } else {
                            interimTranscript += event.results[i][0].transcript;
                        }
                    }
                    this.state.text = interimTranscript;
                    this.state.isVisible = true;

                    // Auto-hide after 4 seconds of silence
                    if (this.timeoutId) clearTimeout(this.timeoutId);
                    this.timeoutId = setTimeout(() => {
                        this.state.isVisible = false;
                    }, 4000);
                };

                try {
                    this.recognition.start();
                } catch (e) {
                    console.error("Speech recognition failed to start", e);
                }
            }
        });

        onWillDestroy(() => {
            if (this.recognition) {
                this.recognition.stop();
            }
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
        });
    }
}
RecordingSubtitle.props = ["isActiveCall"];
```

- [ ] **Step 2: Write the Subtitle Component Template (`recording_subtitle.xml`)**

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
            <span t-esc="state.text"/>
        </div>
    </t>
</templates>
```

- [ ] **Step 3: Add Styles (`recording_subtitle.scss`)**

```scss
.o-aidt-recording-subtitle {
    position: absolute;
    bottom: 100px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 1.2rem;
    max-width: 80%;
    text-align: center;
    z-index: 1000;
    pointer-events: none;
    transition: opacity 0.3s ease-in-out;
}
```

- [ ] **Step 4: Register the Component (`call_patch.js`)**

```javascript
import { Call } from "@mail/discuss/call/common/call";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";
import { RecordingSubtitle } from "@aidt_meeting_minutes/recording_subtitle";

Call.components = { ...Call.components, RecordingBanner, RecordingSubtitle };
```

- [ ] **Step 5: Include Files in Manifest (`__manifest__.py`)**
Add the new paths to `web.assets_backend`:
```python
        'web.assets_backend': [
            'aidt_meeting_minutes/static/src/recorder_service.js',
            'aidt_meeting_minutes/static/src/rtc_service_patch.js',
            'aidt_meeting_minutes/static/src/recording_banner.js',
            'aidt_meeting_minutes/static/src/recording_banner.xml',
            'aidt_meeting_minutes/static/src/recording_banner.scss',
            'aidt_meeting_minutes/static/src/recording_subtitle.js',
            'aidt_meeting_minutes/static/src/recording_subtitle.xml',
            'aidt_meeting_minutes/static/src/recording_subtitle.scss',
            'aidt_meeting_minutes/static/src/call_patch.js',
        ],
```

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.*
git add custom-addons/aidt_meeting_minutes/static/src/call_patch.js
git add custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "feat(ui): add real-time meeting subtitles via Web Speech API"
```

---

### Task 2: Suppress Chat Notifications for Summary

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`

**Interfaces:**
- Modifies: `_finalize` and `_run_summary` methods.

- [ ] **Step 1: Remove `message_post` from `_finalize`**

In `_finalize`, remove the following lines:
```python
        body = Markup('<p><b>%s</b></p><pre>%s</pre>') % (
            _('Bản bóc băng cuộc họp'), transcript or _('(không có nội dung)'))
        self._post_target().message_post(body=body)
```

- [ ] **Step 2: Remove `message_post` from `_run_summary`**

In `_run_summary`, remove the following lines:
```python
        if summary_data:
            body = Markup('<p><b>%s</b>: %s</p><p><i>%s Action Items, %s Decisions</i></p>') % (
                _('Tóm tắt cuộc họp'), summary_data.get('title', ''), len(summary_data.get('action_items') or []), len(summary_data.get('decisions') or [])
            )
            self._post_target().message_post(body=body)
```

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py
git commit -m "feat(backend): prevent meeting summary and transcript from spamming chat"
```
