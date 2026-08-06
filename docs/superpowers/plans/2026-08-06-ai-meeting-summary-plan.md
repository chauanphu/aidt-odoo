# Odoo AI Meeting Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Integrate structured JSON output from LLM for meeting summaries and store them properly into Odoo Models.

**Architecture:** Extend existing `aidt.meeting.recording` with new JSON fields, create new models for decisions and action items, update `summary_client.py` to enforce and parse JSON, and refactor the UI to display the structured data cleanly.

**Tech Stack:** Python 3, Odoo 17/18, XML, PostgreSQL.

## Global Constraints
- Custom addon is `aidt_meeting_minutes`.
- Map-reduce approach: only final step uses JSON.
- Fallback/Retry logic is required if JSON parsing fails.
- Adhere to the exact output schema from the `odoo_ai_meeting_summary_usecase_pipeline.md` specification.

---

## Phase 1: Database Models & Security

### Task 1: Create Data Models
**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_action_item.py`
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_decision.py`
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`

**Interfaces:**
- Produces: `aidt.meeting.action.item`, `aidt.meeting.decision` models.
- Produces: `title`, `overview`, `meeting_minutes`, `key_points`, `risks`, `action_item_ids`, `decision_ids` fields on `aidt.meeting.recording`.

- [x] **Step 1: Write Action Item & Decision models**
```python
# custom-addons/aidt_meeting_minutes/models/meeting_action_item.py
from odoo import models, fields

class AidtMeetingActionItem(models.Model):
    _name = 'aidt.meeting.action.item'
    _description = 'Meeting Action Item'

    recording_id = fields.Many2one('aidt.meeting.recording', string='Bản ghi', ondelete='cascade')
    task = fields.Text(string='Công việc')
    owner = fields.Char(string='Người phụ trách')
    deadline = fields.Char(string='Thời hạn')
    priority = fields.Selection([('high', 'Cao'), ('medium', 'Trung bình'), ('low', 'Thấp')], string='Mức độ', default='medium')
    timestamp = fields.Char(string='Thời gian trong file')

# custom-addons/aidt_meeting_minutes/models/meeting_decision.py
from odoo import models, fields

class AidtMeetingDecision(models.Model):
    _name = 'aidt.meeting.decision'
    _description = 'Meeting Decision'

    recording_id = fields.Many2one('aidt.meeting.recording', string='Bản ghi', ondelete='cascade')
    content = fields.Text(string='Quyết định')
    timestamp = fields.Char(string='Thời gian trong file')
```

- [x] **Step 2: Update `__init__.py`**
```python
# append to custom-addons/aidt_meeting_minutes/models/__init__.py
from . import meeting_action_item
from . import meeting_decision
```

- [x] **Step 3: Modify `meeting_recording.py` to add fields**
Add these fields to `AidtMeetingRecording`:
```python
    title = fields.Char(string='Tiêu đề')
    overview = fields.Text(string='Tổng quan')
    meeting_minutes = fields.Text(string='Biên bản')
    key_points = fields.Text(string='Ý chính (JSON)')
    risks = fields.Text(string='Rủi ro (JSON)')
    action_item_ids = fields.One2many('aidt.meeting.action.item', 'recording_id', string='Công việc')
    decision_ids = fields.One2many('aidt.meeting.decision', 'recording_id', string='Quyết định')
```

- [x] **Step 4: Restart Odoo and Upgrade Module to verify schema creation**
Run: `odoo-bin -c /etc/odoo.conf -d aidt_demo -u aidt_meeting_minutes --stop-after-init`
Expected: Module upgrades without DB errors.

- [x] **Step 5: Commit Phase 1.1**
```bash
git add custom-addons/aidt_meeting_minutes/models/
git commit -m "feat: add meeting summary data models"
```

### Task 2: Security Rules
**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/security/ir.model.access.csv`

- [x] **Step 1: Add Access Rights**
Append to `ir.model.access.csv`:
```csv
access_aidt_meeting_action_item,aidt.meeting.action.item,model_aidt_meeting_action_item,base.group_user,1,1,1,1
access_aidt_meeting_decision,aidt.meeting.decision,model_aidt_meeting_decision,base.group_user,1,1,1,1
```

- [x] **Step 2: Verify Access Rights load correctly**
Run: `odoo-bin -c /etc/odoo.conf -d aidt_demo -u aidt_meeting_minutes --stop-after-init`
Expected: Loads successfully.

- [x] **Step 3: Commit Phase 1.2**
```bash
git add custom-addons/aidt_meeting_minutes/security/ir.model.access.csv
git commit -m "security: add access rights for meeting summary models"
```

> **STOP FOR USER REVIEW:** Pause execution here. Ask the user to verify the database fields and models are created successfully before proceeding to Phase 2.

---

## Phase 2: LLM JSON Output & Parsing

### Task 3: Update LLM Client
**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/summary_client.py`

**Interfaces:**
- Produces: `_summarize()` returns `dict` instead of `str`.

- [x] **Step 1: Define `FINAL_JSON_PROMPT`**
Add to top of `summary_client.py`:
```python
import re

FINAL_JSON_PROMPT = """Bạn là thư ký cuộc họp. Hãy tổng hợp các phần tóm tắt sau đây và xuất kết quả BẮT BUỘC ở định dạng JSON chính xác như cấu trúc sau:
{
  "title": "Tên cuộc họp",
  "overview": "Tóm tắt tổng quan",
  "key_points": [{"content": "Ý chính", "timestamp": "00:00:00"}],
  "decisions": [{"content": "Quyết định", "timestamp": "00:00:00"}],
  "action_items": [{"task": "Công việc", "owner": "Người phụ trách", "deadline": "Hạn chót", "priority": "high/medium/low", "timestamp": "00:00:00"}],
  "risks": [{"content": "Rủi ro"}],
  "meeting_minutes": "Biên bản hoàn chỉnh"
}
Không thêm văn bản nào ngoài JSON."""
```

- [x] **Step 2: Modify `_chat` to accept `system_prompt` as argument**
```python
    @api.model
    def _chat(self, prompt, system_prompt=SYSTEM_PROMPT):
        # Update messages array to use system_prompt
        # ...
                {'role': 'system', 'content': system_prompt},
```

- [x] **Step 3: Implement JSON extraction and retry in `_summarize`**
```python
    @api.model
    def _summarize(self, transcript):
        text = (transcript or '').strip()
        if not text:
            return {}
        lines = text.split('\n')
        
        if len(lines) <= WINDOW_LINES:
            final_text = text
        else:
            partials = []
            for start in range(0, len(lines), WINDOW_LINES):
                window = '\n'.join(lines[start:start + WINDOW_LINES])
                partials.append(self._chat(window))
            final_text = '\n\n'.join(partials)
        
        prompt = _('Dưới đây là các phần của bản bóc băng. Hãy tóm tắt thành JSON:\n\n%s', final_text)
        
        for attempt in range(3):
            try:
                response = self._chat(prompt, system_prompt=FINAL_JSON_PROMPT)
                # Strip markdown blocks
                json_str = re.sub(r'^```json\s*', '', response, flags=re.MULTILINE)
                json_str = re.sub(r'```$', '', json_str, flags=re.MULTILINE).strip()
                return json.loads(json_str)
            except json.JSONDecodeError as exc:
                _logger.warning("Lỗi parse JSON từ LLM (lần %s): %s\nResponse: %s", attempt + 1, exc, response)
                if attempt == 2:
                    raise SummaryError(f'Tóm tắt trả về JSON hỏng sau 3 lần thử: {repr(response)[:500]}') from exc
        return {}
```

- [x] **Step 4: Commit Phase 2**
```bash
git add custom-addons/aidt_meeting_minutes/models/summary_client.py
git commit -m "feat: implement JSON parsing and retry logic for LLM summary"
```

> **STOP FOR USER REVIEW:** Pause execution here. User can test LLM generation output format.

---

## Phase 3: Integration & UI

### Task 4: Store Structured Data
**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`

- [x] **Step 1: Refactor `_run_summary`**
Modify `_run_summary` to handle dict:
```python
    def _run_summary(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                summary_data = self.env['aidt.meeting.summary.client']._summarize(self.transcript_text)
                if not isinstance(summary_data, dict):
                    summary_data = {}
        except Exception as exc:                     # noqa: BLE001
            # ... keep existing error handling ...
            
        import json
        self.sudo().write({
            'summary_error': False,
            'title': summary_data.get('title', ''),
            'overview': summary_data.get('overview', ''),
            'meeting_minutes': summary_data.get('meeting_minutes', ''),
            'key_points': json.dumps(summary_data.get('key_points', []), ensure_ascii=False),
            'risks': json.dumps(summary_data.get('risks', []), ensure_ascii=False),
        })
        
        # Reset O2M lists for re-generation
        self.action_item_ids.unlink()
        self.decision_ids.unlink()
        
        action_items = []
        for ai in summary_data.get('action_items', []):
            action_items.append((0, 0, {
                'task': ai.get('task'),
                'owner': ai.get('owner'),
                'deadline': ai.get('deadline'),
                'priority': ai.get('priority', 'medium'),
                'timestamp': ai.get('timestamp'),
            }))
            
        decisions = []
        for dec in summary_data.get('decisions', []):
            decisions.append((0, 0, {
                'content': dec.get('content'),
                'timestamp': dec.get('timestamp'),
            }))
            
        if action_items or decisions:
            self.sudo().write({
                'action_item_ids': action_items,
                'decision_ids': decisions,
            })
            
        if summary_data:
            body = Markup('<p><b>%s</b>: %s</p><p><i>%s Action Items, %s Decisions</i></p>') % (
                _('Tóm tắt cuộc họp'), summary_data.get('title', ''), len(summary_data.get('action_items', [])), len(summary_data.get('decisions', []))
            )
            self._post_target().message_post(body=body)
        return True
```

- [x] **Step 2: Commit Phase 3.1**
```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py
git commit -m "feat: store structured JSON summary into Odoo models"
```

### Task 5: Refactor UI Views
**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`

- [x] **Step 1: Replace simple `summary_text` with Notebook**
Find `summary_text` and replace with:
```xml
<notebook>
    <page string="Tổng quan" name="overview_page">
        <group>
            <field name="title"/>
            <field name="overview"/>
            <field name="meeting_minutes"/>
            <field name="key_points"/>
            <field name="risks"/>
        </group>
    </page>
    <page string="Công việc" name="action_items_page">
        <field name="action_item_ids">
            <tree editable="bottom">
                <field name="task"/>
                <field name="owner"/>
                <field name="deadline"/>
                <field name="priority"/>
                <field name="timestamp"/>
            </tree>
        </field>
    </page>
    <page string="Quyết định" name="decisions_page">
        <field name="decision_ids">
            <tree editable="bottom">
                <field name="content"/>
                <field name="timestamp"/>
            </tree>
        </field>
    </page>
    <page string="Bản bóc băng" name="transcript_page">
        <field name="transcript_text"/>
    </page>
</notebook>
```

- [x] **Step 2: Apply XML updates**
Run: `odoo-bin -c /etc/odoo.conf -d aidt_demo -u aidt_meeting_minutes --stop-after-init`

- [x] **Step 3: Commit Phase 3.2**
```bash
git add custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml
git commit -m "style: replace flat summary text with structured notebook tabs"
```

> **FINAL STOP FOR USER REVIEW:** Implementation complete. User can fully test the integrated pipeline in Odoo.

### Task 6: Extract to Standalone App
**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`

- [x] **Step 1: Replace Calendar child menu with a Root Menu**
```xml
    <!-- Root menu -->
    <menuitem id="menu_meeting_root" 
              name="Quản lý Cuộc họp" 
              sequence="50" 
              web_icon="aidt_meeting_minutes,static/description/icon.png"/>

    <menuitem id="menu_meeting_recording"
              name="Bản ghi cuộc họp"
              parent="menu_meeting_root"
              action="action_meeting_recording"
              groups="aidt_meeting_minutes.group_meeting_minutes_manager"
              sequence="10"/>
```

- [x] **Step 2: Commit Phase 4**
```bash
git add custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml
git commit -m "feat: extract meeting minutes into a standalone Odoo app"
```
