# Meeting AI Summary Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the meeting recording and AI summarization flow from a real-time streaming model to a batch processing microservice architecture.

**Architecture:** 
Odoo acts as the central hub to receive audio chunks and orchestrate state, but delegates all heavy processing (ffmpeg, STT, LLM) to an external AI service. We will delete internal Odoo ML models (asr_client, etc.), update the recording model to trigger the AI service webhook upon completion, and update the JS frontend to upload audio in 30-second chunks using MediaRecorder without real-time subtitle sockets.

**Tech Stack:** Python, Odoo 16, JavaScript (Odoo OWL)

## Global Constraints

- No real-time streaming or subtitle websocket usage.
- Audio chunks must be uploaded every 30 seconds via JS, never held entirely in RAM.
- Transcript and audio chunks must not be deleted upon AI failure to allow manual retry.
- AI Service interactions must be non-blocking. Odoo only sends the job and waits for a webhook.

---

### Task 1: Odoo Models Cleanup

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Modify: `custom-addons/aidt_meeting_minutes/security/ir.model.access.csv`
- Delete: `custom-addons/aidt_meeting_minutes/models/asr_client.py`
- Delete: `custom-addons/aidt_meeting_minutes/models/summary_client.py`
- Delete: `custom-addons/aidt_meeting_minutes/models/audio_prep.py`
- Delete: `custom-addons/aidt_meeting_minutes/models/text_filter.py`
- Delete: `custom-addons/aidt_meeting_minutes/models/transcript_builder.py`
- Delete: `custom-addons/aidt_meeting_minutes/models/meeting_segment.py`

**Interfaces:**
- Consumes: Existing Odoo model structures.
- Produces: A cleaner module without old ML model files.

- [ ] **Step 1: Delete obsolete Python files**

Run the following command to delete the obsolete AI client and segment models:
```bash
rm custom-addons/aidt_meeting_minutes/models/asr_client.py
rm custom-addons/aidt_meeting_minutes/models/summary_client.py
rm custom-addons/aidt_meeting_minutes/models/audio_prep.py
rm custom-addons/aidt_meeting_minutes/models/text_filter.py
rm custom-addons/aidt_meeting_minutes/models/transcript_builder.py
rm custom-addons/aidt_meeting_minutes/models/meeting_segment.py
```

- [ ] **Step 2: Update models `__init__.py`**

Remove the deleted files from `custom-addons/aidt_meeting_minutes/models/__init__.py`.

- [ ] **Step 3: Update `ir.model.access.csv`**

Remove the ACL lines referencing `aidt.meeting.segment`, `asr_client`, `summary_client`, `audio_prep`, `text_filter`, and `transcript_builder` from `custom-addons/aidt_meeting_minutes/security/ir.model.access.csv`.

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/ custom-addons/aidt_meeting_minutes/security/ir.model.access.csv
git commit -m "refactor: remove obsolete AI and segment models"
```

### Task 2: Refactor aidt.meeting.chunk

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_chunk.py`

**Interfaces:**
- Consumes: Upload requests from frontend.
- Produces: Cleaned `aidt.meeting.chunk` model that only stores audio chunk metadata.

- [ ] **Step 1: Remove Cron and Transcription Methods from meeting_chunk.py**

Modify `custom-addons/aidt_meeting_minutes/models/meeting_chunk.py` to remove:
- `_process_one`
- `_write_segments`
- `_claim`
- `_recover_from_broken_chunk`
- `_cron_process`
- Remove fields `state`, `attempt`, `next_retry_at`, `error`, `skip_note` since we no longer track local transcription state for each chunk.

Ensure the `AidtMeetingChunk` class only contains fields like `recording_id`, `partner_id`, `seq`, `offset_ms`, `duration_ms`, and `attachment_id`, plus the `_store` method.

- [ ] **Step 2: Verify Odoo syntax is correct**

Run a syntax check (or `flake8`/`ruff`) on the modified file to ensure no hanging imports or syntax errors.

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_chunk.py
git commit -m "refactor: remove transcription logic from meeting_chunk"
```

### Task 3: Refactor aidt.meeting.recording

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`

**Interfaces:**
- Consumes: Odoo standard `requests` library to trigger external AI.
- Produces: Updated `aidt.meeting.recording` model that triggers AI job and waits for webhook.

- [ ] **Step 1: Clean up obsolete methods in meeting_recording.py**

Remove `_cron_sweep`, `_sweep_late_chunks`, `_finalize`, `_run_summary`, `action_retry_summary`, `_purge_own_audio`, `_cron_purge_audio` from `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`.
Remove fields `finalized_at`, `finalized_segment_count`, `summary_error`, `segment_ids`.

- [ ] **Step 2: Add API trigger to `action_stop`**

Modify `action_stop` method in `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`.
When state changes to `processing`, send a non-blocking POST request to the external AI service.

```python
    def action_stop(self):
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        if self.state != 'recording':
            return False
            
        self.sudo().write({
            'state': 'processing', 'ended_at': fields.Datetime.now(),
        })
        self._broadcast_state('stopped')
        
        # Trigger external AI service
        self._trigger_ai_service()
        return True

    def _trigger_ai_service(self):
        self.ensure_one()
        ai_url = self._config('ai_service_url', 'http://localhost:8000')
        webhook_url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/aidt_meeting/api/webhook/summary/{self.id}"
        total_chunks = self.env['aidt.meeting.chunk'].sudo().search_count([('recording_id', '=', self.id)])
        
        try:
            import requests
            requests.post(
                f"{ai_url}/jobs/process_meeting",
                json={
                    'meeting_id': self.id,
                    'total_chunks': total_chunks,
                    'webhook_url': webhook_url
                },
                timeout=5
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to trigger AI service for meeting {self.id}: {e}")
```

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py
git commit -m "refactor: update recording model to trigger external AI service"
```

### Task 4: Webhook Controller for Summary

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/controllers/main.py`

**Interfaces:**
- Consumes: JSON payload from AI Service.
- Produces: Updated database fields in `aidt.meeting.recording` and related records.

- [ ] **Step 1: Write Webhook Controller Method**

In `custom-addons/aidt_meeting_minutes/controllers/main.py`, add the webhook route:

```python
    @http.route('/aidt_meeting/api/webhook/summary/<int:recording_id>', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_ai_summary(self, recording_id, **kw):
        recording = request.env['aidt.meeting.recording'].sudo().browse(recording_id)
        if not recording.exists():
            return {'status': 'error', 'message': 'Recording not found'}

        data = request.jsonrequest
        
        # Update text fields
        recording.write({
            'title': data.get('title', ''),
            'overview': data.get('overview', ''),
            'meeting_minutes': data.get('meeting_minutes', ''),
            'key_points': json.dumps(data.get('key_points', []), ensure_ascii=False),
            'risks': json.dumps(data.get('risks', []), ensure_ascii=False),
            'transcript_text': data.get('transcript_raw', ''),
            'state': 'done'
        })
        
        # Clear existing action items and decisions
        recording.action_item_ids.unlink()
        recording.decision_ids.unlink()
        
        # Build action items (fuzzy match for assignee_name can be improved later)
        action_items = []
        for ai in data.get('action_items', []):
            assignee_name = ai.get('owner')
            action_items.append((0, 0, {
                'task': ai.get('task'),
                'owner': assignee_name,
                'deadline': ai.get('deadline'),
                'priority': ai.get('priority', 'medium'),
                'timestamp': ai.get('timestamp'),
            }))
            
        decisions = []
        for dec in data.get('decisions', []):
            decisions.append((0, 0, {
                'content': dec.get('content'),
                'timestamp': dec.get('timestamp'),
            }))
            
        recording.write({
            'action_item_ids': action_items,
            'decision_ids': decisions
        })
        
        return {'status': 'success'}
```

- [ ] **Step 2: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/controllers/main.py
git commit -m "feat: add webhook controller for AI summary result"
```

### Task 5: Refactor JS Frontend

**Files:**
- Delete: `custom-addons/aidt_meeting_minutes/static/src/audio_stream_service.js`
- Delete: `custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.js`
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recorder_service.js`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py`

**Interfaces:**
- Consumes: Browser MediaRecorder API.
- Produces: Audio chunks via API requests to Odoo every 30 seconds.

- [ ] **Step 1: Delete Real-time Socket JS Files**

```bash
rm custom-addons/aidt_meeting_minutes/static/src/audio_stream_service.js
rm custom-addons/aidt_meeting_minutes/static/src/recording_subtitle.js
```

- [ ] **Step 2: Remove references from manifest**

Remove the deleted JS files from the `assets` block in `custom-addons/aidt_meeting_minutes/__manifest__.py`.

- [ ] **Step 3: Update recorder_service.js for Batch Mode**

Open `custom-addons/aidt_meeting_minutes/static/src/recorder_service.js` and modify it to:
- Use `this.recorder.start(30000)` to generate 30-second chunks.
- Inside `ondataavailable`, push the blob to an upload queue and attempt to POST to `/aidt_meeting/api/upload_chunk` (or the existing route).
- If the POST fails, keep it in the queue for a retry loop.
- Send the `finalize_recording` POST request in the `stop()` method.

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/ custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "refactor: switch JS frontend to chunked batch upload and remove real-time subtitles"
```
