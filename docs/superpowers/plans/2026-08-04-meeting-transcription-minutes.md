# Meeting Transcription & Minutes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record Odoo Discuss calls by having each participant's browser capture only its own microphone, transcribe the audio with PhoWhisper, and post a speaker-attributed transcript plus a Vietnamese summary to the meeting.

**Architecture:** Each client clones its own mic track into a private `AudioContext`, encodes ~15 s MP3 chunks at 16 kHz and uploads them to Odoo. An `ir.cron` drains the chunk queue into an OpenAI-compatible ASR service, producing timestamped segments. When the call ends, segments are interleaved by absolute time into a transcript, summarised through an OpenAI-compatible chat endpoint, and posted to the `calendar.event` chatter (scheduled meetings) or the `discuss.channel` (ad-hoc calls).

**Tech Stack:** Odoo 19, Python 3, PostgreSQL, OWL 2 / JavaScript, `urllib.request` (no new Python deps), lamejs (already bundled in `mail`), PhoWhisper-large, an OpenAI-compatible LLM.

**Spec:** `docs/superpowers/specs/2026-08-04-meeting-transcription-minutes-design.md`

## Global Constraints

- Module lives at `custom-addons/aidt_meeting_minutes`. Odoo version `19.0`, manifest `'version': '19.0.1.0.0'`, `'license': 'LGPL-3'`.
- **All user-facing strings, field labels, docstrings and code comments are Vietnamese.** Test method names are Vietnamese too (`def test_khong_cho_nguoi_ngoai_bat_ghi_am`). This matches every module in `custom-addons/`.
- **No new Python dependencies.** HTTP uses `urllib.request`, exactly as `custom-addons/aidt_search/models/embed_client.py` does.
- **No new JavaScript dependencies.** MP3 encoding reuses `@mail/discuss/voice_message/common/mp3_encoder`.
- **Never fork Odoo core files.** Client-side changes are `patch()` calls plus new files under `custom-addons/aidt_meeting_minutes/static/src/`.
- **Service endpoints are configuration, never constants.** Read via `ir.config_parameter` under the `aidt_meeting.` prefix. No `localhost` or container names in Python.
- **`partner_id` is always derived from `request.env.user.partner_id`**, never read from a request payload.
- Development and demo installs target the `aidt_demo` database only: `-d aidt_demo -i aidt_meeting_minutes` / `-u aidt_meeting_minutes`. Any throwaway test DB must be dropped along with its filestore directory.
- Commands run inside the dev stack, e.g.
  `docker compose -f docker-compose.dev.yml exec odoo odoo -d aidt_demo --test-enable --stop-after-init -i aidt_meeting_minutes`.
- Cron/queue code must tolerate `test_enable`: guard `self.env.cr.commit()` with `if not config['test_enable']:` (see `aidt_search/models/index_job.py::_cron_process`).

## File Structure

**New module `custom-addons/aidt_meeting_minutes/`:**

| Path | Responsibility |
|---|---|
| `__manifest__.py`, `__init__.py` | Module definition |
| `models/meeting_recording.py` | `aidt.meeting.recording` — lifecycle, authorization, finalize |
| `models/meeting_chunk.py` | `aidt.meeting.chunk` — audio queue rows, claim/retry |
| `models/meeting_segment.py` | `aidt.meeting.segment` — transcribed text units |
| `models/asr_client.py` | `aidt.meeting.asr.client` — ASR adapter (only file that knows the ASR wire format) |
| `models/summary_client.py` | `aidt.meeting.summary.client` — LLM adapter (only file that knows the chat wire format) |
| `models/transcript_builder.py` | `aidt.meeting.transcript` — pure assembly: sort, dedupe seams, merge speakers, mark gaps |
| `models/res_config_settings.py` | Settings UI bound to `ir.config_parameter` |
| `controllers/main.py` | `POST /aidt_meeting/chunk` upload endpoint |
| `data/ir_config_parameter.xml` | Endpoint/model defaults |
| `data/ir_cron.xml` | Queue + end-detection crons |
| `security/ir.model.access.csv`, `security/aidt_meeting_rules.xml` | ACLs and channel-based record rules |
| `views/meeting_recording_views.xml`, `views/res_config_settings_views.xml` | Backend UI |
| `static/src/recorder_service.js` | Capture, chunk, upload |
| `static/src/rtc_service_patch.js` | Re-attach recorder when the mic track is replaced |
| `static/src/recording_banner.js` / `.xml` / `.scss` | Consent banner with Từ chối / Dừng ghi âm |
| `tests/` | One file per concern |

**Modified outside the module:** `docker-compose.yml` and new `docker-compose.ai.yml` (Task 11), `docs/GUIDANCE.md` (Task 12).

`transcript_builder.py` is deliberately separate from `meeting_recording.py`: interleaving is the logic most likely to be subtly wrong, and isolating it makes it testable without creating channels, calls, or attachments.

---

### Task 1: Module scaffold and configuration

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/__init__.py`
- Create: `custom-addons/aidt_meeting_minutes/__manifest__.py`
- Create: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Create: `custom-addons/aidt_meeting_minutes/models/res_config_settings.py`
- Create: `custom-addons/aidt_meeting_minutes/data/ir_config_parameter.xml`
- Create: `custom-addons/aidt_meeting_minutes/views/res_config_settings_views.xml`
- Create: `custom-addons/aidt_meeting_minutes/security/ir.model.access.csv`
- Test: `custom-addons/aidt_meeting_minutes/tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: config keys `aidt_meeting.asr_url`, `aidt_meeting.asr_model`, `aidt_meeting.asr_api_key`, `aidt_meeting.llm_url`, `aidt_meeting.llm_model`, `aidt_meeting.llm_api_key`, `aidt_meeting.max_secrecy`, `aidt_meeting.audio_retention_days`.

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py`:

```python
from . import test_config
```

Create `tests/test_config.py`:

```python
from odoo.tests.common import TransactionCase


class TestConfig(TransactionCase):
    def _param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    def test_co_gia_tri_mac_dinh_cho_moi_tham_so(self):
        self.assertTrue(self._param('aidt_meeting.asr_url'))
        self.assertEqual(self._param('aidt_meeting.asr_model'),
                         'vinai/PhoWhisper-large')
        self.assertTrue(self._param('aidt_meeting.llm_url'))

    def test_mac_dinh_chi_cho_ghi_am_muc_thuong(self):
        """Mặc định phải là mức thấp nhất: bật rộng hơn phải là quyết định
        có ý thức của quản trị viên, không phải thứ có sẵn khi cài."""
        self.assertEqual(self._param('aidt_meeting.max_secrecy'), 'thuong')

    def test_mac_dinh_xoa_audio_ngay_sau_khi_boc_bang(self):
        """0 ngày = xoá ngay. Audio thô là rủi ro lớn hơn transcript."""
        self.assertEqual(self._param('aidt_meeting.audio_retention_days'), '0')

    def test_settings_ghi_duoc_va_doc_lai_dung(self):
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_url': 'http://phowhisper:8002/v1',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_url'),
                         'http://phowhisper:8002/v1')
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -i aidt_meeting_minutes
```
Expected: FAIL — module `aidt_meeting_minutes` not found.

- [ ] **Step 3: Create the module skeleton**

`__init__.py`:

```python
from . import models
```

`__manifest__.py`:

```python
{
    'name': 'AIDT Biên bản cuộc họp',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Ghi âm, bóc băng và tóm tắt cuộc họp Discuss Meet',
    'depends': ['mail', 'calendar', 'aidt_calendar'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
```

`models/__init__.py`:

```python
from . import res_config_settings
```

`models/res_config_settings.py`:

```python
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Endpoint là DỮ LIỆU chứ không phải hằng số trong code: tầng AI nằm ở
    # docker-compose.ai.yml riêng và phải thay được bằng dịch vụ bên thứ ba
    # bất cứ lúc nào mà không sửa một dòng Python nào.
    aidt_meeting_asr_url = fields.Char(
        string='URL dịch vụ bóc băng',
        config_parameter='aidt_meeting.asr_url')
    aidt_meeting_asr_model = fields.Char(
        string='Model bóc băng',
        config_parameter='aidt_meeting.asr_model')
    # API key rỗng với dịch vụ nội bộ. Có trường này từ đầu là điều kiện để
    # chuyển sang bên thứ ba mà không phải sửa code — thiếu nó thì lời hứa
    # "thay được bất cứ lúc nào" không thực hiện được.
    aidt_meeting_asr_api_key = fields.Char(
        string='API key dịch vụ bóc băng',
        config_parameter='aidt_meeting.asr_api_key')

    aidt_meeting_llm_url = fields.Char(
        string='URL dịch vụ tóm tắt',
        config_parameter='aidt_meeting.llm_url')
    aidt_meeting_llm_model = fields.Char(
        string='Model tóm tắt',
        config_parameter='aidt_meeting.llm_model')
    aidt_meeting_llm_api_key = fields.Char(
        string='API key dịch vụ tóm tắt',
        config_parameter='aidt_meeting.llm_api_key')

    aidt_meeting_max_secrecy = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật tối đa được ghi âm',
        config_parameter='aidt_meeting.max_secrecy')
    aidt_meeting_audio_retention_days = fields.Integer(
        string='Giữ audio (ngày)',
        help='0 = xoá ngay sau khi bóc băng xong.',
        config_parameter='aidt_meeting.audio_retention_days')
```

`data/ir_config_parameter.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Giá trị mặc định trỏ tới service trong docker-compose.ai.yml. Đổi
         được từ UI, không cần deploy lại. Cùng triết lý với aidt_search. -->
    <data noupdate="1">
        <record id="param_asr_url" model="ir.config_parameter">
            <field name="key">aidt_meeting.asr_url</field>
            <field name="value">http://aidt-asr:8002/v1</field>
        </record>
        <record id="param_asr_model" model="ir.config_parameter">
            <field name="key">aidt_meeting.asr_model</field>
            <field name="value">vinai/PhoWhisper-large</field>
        </record>
        <record id="param_asr_api_key" model="ir.config_parameter">
            <field name="key">aidt_meeting.asr_api_key</field>
            <field name="value"></field>
        </record>
        <record id="param_llm_url" model="ir.config_parameter">
            <field name="key">aidt_meeting.llm_url</field>
            <field name="value">http://aidt-llm:8003/v1</field>
        </record>
        <record id="param_llm_model" model="ir.config_parameter">
            <field name="key">aidt_meeting.llm_model</field>
            <field name="value">gemma4:12b</field>
        </record>
        <record id="param_llm_api_key" model="ir.config_parameter">
            <field name="key">aidt_meeting.llm_api_key</field>
            <field name="value"></field>
        </record>
        <record id="param_max_secrecy" model="ir.config_parameter">
            <field name="key">aidt_meeting.max_secrecy</field>
            <field name="value">thuong</field>
        </record>
        <record id="param_audio_retention_days" model="ir.config_parameter">
            <field name="key">aidt_meeting.audio_retention_days</field>
            <field name="value">0</field>
        </record>
    </data>
</odoo>
```

`views/res_config_settings_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form" model="ir.ui.view">
        <field name="name">res.config.settings.form.aidt.meeting</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="base.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//form" position="inside">
                <app data-string="Biên bản cuộc họp" string="Biên bản cuộc họp"
                     name="aidt_meeting_minutes">
                    <block title="Dịch vụ AI" name="aidt_meeting_ai">
                        <setting string="Bóc băng">
                            <field name="aidt_meeting_asr_url"/>
                            <field name="aidt_meeting_asr_model"/>
                            <field name="aidt_meeting_asr_api_key" password="True"/>
                        </setting>
                        <setting string="Tóm tắt">
                            <field name="aidt_meeting_llm_url"/>
                            <field name="aidt_meeting_llm_model"/>
                            <field name="aidt_meeting_llm_api_key" password="True"/>
                        </setting>
                    </block>
                    <block title="Chính sách" name="aidt_meeting_policy">
                        <setting string="Độ mật tối đa">
                            <field name="aidt_meeting_max_secrecy"/>
                        </setting>
                        <setting string="Lưu trữ audio">
                            <field name="aidt_meeting_audio_retention_days"/>
                        </setting>
                    </block>
                </app>
            </xpath>
        </field>
    </record>
</odoo>
```

`security/ir.model.access.csv` (header only for now; rows arrive with their models):

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -i aidt_meeting_minutes
```
Expected: PASS, 4 tests in `TestConfig`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): scaffold aidt_meeting_minutes with AI endpoint settings"
```

---

### Task 2: Recording lifecycle and authorization

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`
- Create: `custom-addons/aidt_meeting_minutes/security/aidt_meeting_rules.xml`
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_recording_auth.py`

**Interfaces:**
- Consumes: config keys from Task 1.
- Produces:
  - `aidt.meeting.recording` with fields `event_id`, `channel_id`, `state`, `started_by_id`, `started_at`, `ended_at`, `secrecy_at_start`, `declined_partner_ids`, `transcript_text`, `summary_text`.
  - `AidtMeetingRecording._start_for_channel(channel)` → recording record; raises `UserError`/`AccessError`.
  - `AidtMeetingRecording.action_stop()` → sets state `processing`.
  - `AidtMeetingRecording._decline(partner)` → adds to `declined_partner_ids`.
  - `AidtMeetingRecording._is_participant(partner)` → bool.
  - Group `aidt_meeting_minutes.group_meeting_minutes_manager`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recording_auth.py`:

```python
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class RecordingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.organizer = cls.env['res.users'].create({
            'name': 'Người chủ trì', 'login': 'chutri@test.local',
        })
        cls.member = cls.env['res.users'].create({
            'name': 'Thành viên', 'login': 'thanhvien@test.local',
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Người ngoài', 'login': 'nguoingoai@test.local',
        })

    def _channel(self, partners):
        channel = self.env['discuss.channel'].create({
            'name': 'Cuộc gọi thử', 'channel_type': 'channel',
        })
        channel.add_members(partner_ids=[p.id for p in partners])
        return channel

    def _event(self, channel, secrecy='thuong'):
        return self.env['calendar.event'].create({
            'name': 'Họp giao ban',
            'start': '2026-08-04 01:00:00', 'stop': '2026-08-04 02:00:00',
            'user_id': self.organizer.id,
            'secrecy': secrecy,
            'videocall_channel_id': channel.id,
            'partner_ids': [(6, 0, [self.organizer.partner_id.id,
                                    self.member.partner_id.id])],
        })


class TestScheduledMeeting(RecordingCase):
    def test_nguoi_chu_tri_bat_duoc(self):
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        event = self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.event_id, event)

    def test_nguoi_khong_chu_tri_khong_bat_duoc(self):
        """Cuộc họp có lịch thì chỉ người chủ trì được bật — khác hẳn cuộc
        gọi tự phát, nơi thành viên bất kỳ đều bật được."""
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.member)._start_for_channel(channel)

    def test_do_mat_vuot_nguong_thi_chan(self):
        channel = self._channel([self.organizer.partner_id])
        self._event(channel, secrecy='mat')
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)

    def test_chup_lai_do_mat_luc_bat_dau(self):
        """Bản chụp, không phải related: đổi phân loại về sau không được làm
        một bản ghi đã hoàn tất trở thành trái phép một cách hồi tố, và hạ
        phân loại cũng không được hợp thức hoá nó."""
        channel = self._channel([self.organizer.partner_id])
        event = self._event(channel, secrecy='thuong')
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        event.secrecy = 'tuyet_mat'
        self.assertEqual(rec.secrecy_at_start, 'thuong')


class TestAdHocCall(RecordingCase):
    def test_khong_co_lich_van_bat_duoc(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertFalse(rec.event_id)

    def test_cuoc_goi_tu_phat_coi_nhu_thuong(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertEqual(rec.secrecy_at_start, 'thuong')

    def test_khong_cho_nguoi_ngoai_bat_ghi_am(self):
        channel = self._channel([self.member.partner_id])
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.outsider)._start_for_channel(channel)

    def test_khong_bat_trung_hai_ban_ghi_tren_mot_channel(self):
        channel = self._channel([self.member.partner_id])
        self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.member)._start_for_channel(channel)


class TestStopPermission(RecordingCase):
    def test_nguoi_tham_gia_bat_ky_deu_dung_duoc(self):
        """Bật thì hạn chế, dừng thì không — thiết kế dựa vào việc con người
        tự tắt ghi âm khi nội dung là Mật, nên người nhận ra điều đó phải tắt
        được ngay chứ không phải đi nhờ người khác."""
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.member).action_stop()
        self.assertEqual(rec.state, 'processing')

    def test_nguoi_ngoai_khong_dung_duoc(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    def test_tu_choi_ghi_lai_partner(self):
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.member)._decline(self.member.partner_id)
        self.assertIn(self.member.partner_id, rec.declined_partner_ids)
```

Add to `tests/__init__.py`:

```python
from . import test_config
from . import test_recording_auth
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `KeyError: 'aidt.meeting.recording'`.

- [ ] **Step 3: Write the implementation**

Create `models/meeting_recording.py`:

```python
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Thứ tự tăng dần. Dùng để so sánh với ngưỡng cấu hình.
SECRECY_ORDER = ['thuong', 'mat', 'toi_mat', 'tuyet_mat']


class AidtMeetingRecording(models.Model):
    _name = 'aidt.meeting.recording'
    _description = 'Bản ghi cuộc họp'
    _order = 'started_at desc, id desc'

    # channel_id mới là khoá thật: cuộc gọi tự phát không có calendar.event.
    # Mọi truy vấn phân quyền phải đi qua trường này.
    channel_id = fields.Many2one(
        'discuss.channel', string='Kênh', required=True,
        ondelete='cascade', index=True)
    event_id = fields.Many2one(
        'calendar.event', string='Cuộc họp', ondelete='set null', index=True)

    state = fields.Selection(
        [('recording', 'Đang ghi'), ('processing', 'Đang xử lý'),
         ('done', 'Xong'), ('failed', 'Lỗi'), ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='recording', required=True, index=True)

    started_by_id = fields.Many2one('res.users', string='Người bật', readonly=True)
    started_at = fields.Datetime(string='Bắt đầu', readonly=True)
    ended_at = fields.Datetime(string='Kết thúc', readonly=True)

    # Bản chụp, KHÔNG phải related. Xem test_chup_lai_do_mat_luc_bat_dau.
    secrecy_at_start = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật lúc bắt đầu', required=True, default='thuong',
        readonly=True)

    declined_partner_ids = fields.Many2many(
        'res.partner', string='Người từ chối ghi âm')

    transcript_text = fields.Text(string='Bản bóc băng', readonly=True)
    summary_text = fields.Text(string='Tóm tắt', readonly=True)
    summary_error = fields.Text(string='Lỗi tóm tắt', readonly=True)

    _channel_active_uniq = models.Constraint(
        "EXCLUDE (channel_id WITH =) WHERE (state IN ('recording', 'processing'))",
        'Mỗi kênh chỉ có một bản ghi đang hoạt động.',
    )

    # ------------------------------------------------------------------ #
    # Phân quyền
    # ------------------------------------------------------------------ #
    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _event_for_channel(self, channel):
        """Cuộc họp có lịch gắn với kênh này, hoặc bản ghi rỗng.

        sudo() vì người dùng có thể dự họp mà không có quyền đọc
        calendar.event qua record rule của aidt_calendar; ở đây ta chỉ cần
        biết cuộc họp TỒN TẠI và độ mật của nó để quyết định cho phép.
        """
        return self.env['calendar.event'].sudo().search(
            [('videocall_channel_id', '=', channel.id)], limit=1)

    @api.model
    def _is_channel_member(self, channel, partner):
        return bool(self.env['discuss.channel.member'].sudo().search_count([
            ('channel_id', '=', channel.id), ('partner_id', '=', partner.id),
        ]))

    def _is_participant(self, partner):
        self.ensure_one()
        return self._is_channel_member(self.channel_id, partner)

    @api.model
    def _check_secrecy_allowed(self, secrecy):
        ceiling = self._config('max_secrecy', 'thuong')
        try:
            allowed = SECRECY_ORDER.index(ceiling)
        except ValueError:
            # Cấu hình rác thì KHÔNG mở rộng quyền — lùi về mức chặt nhất.
            _logger.warning(
                'aidt_meeting.max_secrecy không hợp lệ (%r), coi như "thuong".',
                ceiling)
            allowed = 0
        if SECRECY_ORDER.index(secrecy) > allowed:
            raise UserError(_(
                'Cuộc họp ở mức "%(muc)s" vượt ngưỡng cho phép ghi âm. '
                'Liên hệ quản trị viên nếu cần thay đổi.',
                muc=dict(SECRECY_ORDER and self._fields['secrecy_at_start'].selection)[secrecy],
            ))

    @api.model
    def _start_for_channel(self, channel):
        """Bật ghi âm cho một kênh đang có cuộc gọi. Trả về bản ghi."""
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))

        event = self._event_for_channel(channel)
        if event:
            # Cuộc họp có lịch: chỉ người chủ trì được bật.
            if event.user_id != self.env.user:
                raise AccessError(_(
                    'Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
            secrecy = event.secrecy or 'thuong'
        else:
            # Cuộc gọi tự phát: không có gì để phân loại nên coi là thường,
            # và thành viên bất kỳ đều bật được. Ngưỡng độ mật KHÔNG kiểm
            # soát được ca này — banner đồng thuận và nút dừng ở §5 của spec
            # mới là cơ chế thực thi.
            secrecy = 'thuong'
        self._check_secrecy_allowed(secrecy)

        existing = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'processing')),
        ], limit=1)
        if existing:
            raise UserError(_('Cuộc gọi này đang được ghi âm rồi.'))

        recording = self.sudo().create({
            'channel_id': channel.id,
            'event_id': event.id if event else False,
            'secrecy_at_start': secrecy,
            'started_by_id': self.env.user.id,
            'started_at': fields.Datetime.now(),
        })
        recording._broadcast_state('started')
        return recording

    def action_stop(self):
        """Dừng ghi âm. BẤT KỲ người tham gia nào cũng gọi được."""
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        if self.state != 'recording':
            return False
        self.sudo().write({
            'state': 'processing', 'ended_at': fields.Datetime.now(),
        })
        self._broadcast_state('stopped')
        return True

    def _decline(self, partner):
        self.ensure_one()
        if not self._is_participant(self.env.user.partner_id):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        self.sudo().write({'declined_partner_ids': [(4, partner.id)]})
        return True

    def _broadcast_state(self, action):
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm.

        Gửi kèm `elapsed_ms` để máy vào giữa chừng tính được vị trí tuyệt
        đối của chunk mà không cần đồng hồ tường của nó khớp với server.
        """
        self.ensure_one()
        elapsed = 0
        if self.started_at:
            delta = fields.Datetime.now() - self.started_at
            elapsed = int(delta.total_seconds() * 1000)
        self.channel_id._bus_send('aidt_meeting_minutes/recording_state', {
            'action': action,
            'recording_id': self.id,
            'channel_id': self.channel_id.id,
            'elapsed_ms': elapsed,
        })
```

Add to `models/__init__.py`:

```python
from . import res_config_settings
from . import meeting_recording
```

Create `security/aidt_meeting_rules.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="group_meeting_minutes_manager" model="res.groups">
            <field name="name">Quản lý biên bản cuộc họp</field>
            <field name="category_id" ref="base.module_category_productivity"/>
        </record>

        <!-- Rule viết theo channel_id là BẮT BUỘC, không phải theo event_id:
             event_id rỗng với mọi cuộc gọi tự phát, nên một rule chỉ dựa vào
             event_id sẽ để lọt toàn bộ bản ghi của các cuộc gọi đó. -->
        <record id="rule_recording_participant" model="ir.rule">
            <field name="name">Bản ghi: người trong kênh mới đọc được</field>
            <field name="model_id" ref="model_aidt_meeting_recording"/>
            <field name="domain_force">
                ['|',
                 ('channel_id.channel_member_ids.partner_id', '=', user.partner_id.id),
                 ('event_id.partner_ids', 'in', [user.partner_id.id])]
            </field>
            <field name="groups" eval="[(4, ref('base.group_user'))]"/>
        </record>

        <record id="rule_recording_manager" model="ir.rule">
            <field name="name">Bản ghi: quản lý thấy tất cả</field>
            <field name="model_id" ref="model_aidt_meeting_recording"/>
            <field name="domain_force">[(1, '=', 1)]</field>
            <field name="groups"
                   eval="[(4, ref('group_meeting_minutes_manager'))]"/>
        </record>
    </data>
</odoo>
```

Append to `security/ir.model.access.csv`:

```csv
access_meeting_recording_user,aidt.meeting.recording.user,model_aidt_meeting_recording,base.group_user,1,0,0,0
access_meeting_recording_manager,aidt.meeting.recording.manager,model_aidt_meeting_recording,aidt_meeting_minutes.group_meeting_minutes_manager,1,1,1,1
```

Add `'security/aidt_meeting_rules.xml',` to `__manifest__.py` `data`, immediately after `'security/ir.model.access.csv',`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, all `TestScheduledMeeting`, `TestAdHocCall`, `TestStopPermission` tests.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): recording lifecycle with secrecy ceiling and channel-based rules"
```

---

### Task 3: Chunk model and upload controller

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_chunk.py`
- Create: `custom-addons/aidt_meeting_minutes/controllers/__init__.py`, `controllers/main.py`
- Modify: `models/__init__.py`, `__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_chunk_upload.py`

**Interfaces:**
- Consumes: `aidt.meeting.recording` from Task 2.
- Produces:
  - `aidt.meeting.chunk` with `recording_id`, `partner_id`, `seq`, `offset_ms`, `duration_ms`, `attachment_id`, `state`, `attempt`, `next_retry_at`, `error`.
  - `AidtMeetingChunk._store(recording, partner, seq, offset_ms, duration_ms, raw_bytes)` → chunk record.
  - Route `POST /aidt_meeting/chunk` (`type="http"`, `auth="user"`, `csrf=False`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_chunk_upload.py`:

```python
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class ChunkCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Chunk = cls.env['aidt.meeting.chunk']
        cls.speaker = cls.env['res.users'].create({
            'name': 'Người nói', 'login': 'nguoinoi@test.local',
        })
        cls.other = cls.env['res.users'].create({
            'name': 'Người khác', 'login': 'nguoikhac@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[
            cls.speaker.partner_id.id, cls.other.partner_id.id])
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.speaker)._start_for_channel(cls.channel)

    def _store(self, seq=0, offset_ms=0, user=None):
        user = user or self.speaker
        return self.Chunk.with_user(user)._store(
            self.recording, user.partner_id, seq, offset_ms, 15000, b'FAKEMP3')


class TestChunkStore(ChunkCase):
    def test_luu_duoc_chunk_va_gan_attachment(self):
        chunk = self._store()
        self.assertEqual(chunk.state, 'pending')
        self.assertTrue(chunk.attachment_id)
        self.assertEqual(chunk.partner_id, self.speaker.partner_id)

    def test_trung_seq_bi_tu_choi(self):
        """Upload thử lại sau lỗi mạng KHÔNG được nhân đôi audio."""
        self._store(seq=3)
        with self.assertRaises(Exception):
            self._store(seq=3)
            self.env.flush_all()

    def test_khong_nhan_chunk_khi_ban_ghi_da_dung(self):
        self.recording.with_user(self.speaker).action_stop()
        with self.assertRaises(AccessError):
            self._store(seq=9)

    def test_khong_nhan_chunk_tu_nguoi_ngoai_kenh(self):
        outsider = self.env['res.users'].create({
            'name': 'Ngoài', 'login': 'ngoai2@test.local',
        })
        with self.assertRaises(AccessError):
            self.Chunk.with_user(outsider)._store(
                self.recording, outsider.partner_id, 0, 0, 15000, b'X')

    def test_khong_gan_audio_cho_partner_khac(self):
        """Đây là điểm chống giả mạo cốt lõi: partner PHẢI là người gọi,
        không bao giờ lấy từ dữ liệu client gửi lên. Một dòng transcript giả
        mạo là đúng loại sản phẩm không được phép tồn tại trong hệ thống này.
        """
        with self.assertRaises(AccessError):
            self.Chunk.with_user(self.speaker)._store(
                self.recording, self.other.partner_id, 0, 0, 15000, b'X')
```

Add `from . import test_chunk_upload` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `KeyError: 'aidt.meeting.chunk'`.

- [ ] **Step 3: Write the implementation**

Create `models/meeting_chunk.py`:

```python
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

MAX_ATTEMPT = 3
# Service vừa chết thì thử lại ngay không ích gì. Cùng triết lý với
# aidt_search/models/index_job.py.
RETRY_BACKOFF_MINUTES = (1, 4, 16)


class AidtMeetingChunk(models.Model):
    _name = 'aidt.meeting.chunk'
    _description = 'Mẩu audio cuộc họp'
    _order = 'recording_id, offset_ms, id'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Người nói', required=True, index=True)
    seq = fields.Integer(string='Thứ tự', required=True)
    # Tính bằng performance.now() của CHÍNH máy đó so với lúc nó bắt đầu ghi,
    # không bao giờ bằng đồng hồ tường — nhờ vậy lệch đồng hồ giữa các máy
    # không thể làm rối thứ tự khi trộn.
    offset_ms = fields.Integer(string='Vị trí (ms)', required=True)
    duration_ms = fields.Integer(string='Độ dài (ms)', required=True)

    attachment_id = fields.Many2one(
        'ir.attachment', string='Tệp audio', ondelete='set null')

    state = fields.Selection(
        [('pending', 'Chờ xử lý'), ('transcribing', 'Đang bóc băng'),
         ('done', 'Xong'), ('failed', 'Lỗi')],
        string='Trạng thái', default='pending', required=True, index=True)
    attempt = fields.Integer(string='Số lần thử', default=0)
    next_retry_at = fields.Datetime(string='Thử lại lúc')
    error = fields.Text(string='Lỗi')

    _seq_uniq = models.Constraint(
        'UNIQUE(recording_id, partner_id, seq)',
        'Mỗi người chỉ có một mẩu audio cho mỗi thứ tự trong một bản ghi.',
    )

    @api.model
    def _store(self, recording, partner, seq, offset_ms, duration_ms, raw):
        """Lưu một mẩu audio. `partner` PHẢI là partner của người đang gọi.

        Kiểm tra lại ở đây (chứ không chỉ ở controller) để mọi đường vào đều
        đi qua cùng một cửa: gán audio cho người khác nghĩa là giả mạo được
        một dòng trong biên bản.
        """
        caller = self.env.user.partner_id
        if partner != caller:
            raise AccessError(_('Không thể gán audio cho người khác.'))
        if not recording.sudo()._is_participant(caller):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        if recording.sudo().state != 'recording':
            raise AccessError(_('Bản ghi không còn nhận audio.'))

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'meeting-{recording.id}-{partner.id}-{seq}.mp3',
            'datas': base64.b64encode(raw),
            'mimetype': 'audio/mpeg',
            'res_model': 'aidt.meeting.recording',
            'res_id': recording.id,
        })
        return self.sudo().create({
            'recording_id': recording.id,
            'partner_id': partner.id,
            'seq': seq,
            'offset_ms': offset_ms,
            'duration_ms': duration_ms,
            'attachment_id': attachment.id,
        })

    def _mark_failed(self, message):
        """Hết lượt thử: đóng đinh 'failed' để hàng đợi không kẹt mãi ở đây."""
        self.ensure_one()
        self.sudo().write({'state': 'failed', 'error': message})

    def _mark_retry(self, message):
        self.ensure_one()
        attempt = self.attempt + 1
        if attempt >= MAX_ATTEMPT:
            return self._mark_failed(message)
        minutes = RETRY_BACKOFF_MINUTES[min(attempt - 1,
                                            len(RETRY_BACKOFF_MINUTES) - 1)]
        self.sudo().write({
            'state': 'pending', 'attempt': attempt, 'error': message,
            'next_retry_at': fields.Datetime.add(
                fields.Datetime.now(), minutes=minutes),
        })
```

Create `controllers/__init__.py`:

```python
from . import main
```

Create `controllers/main.py`:

```python
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Chặn trần kích thước để một client hỏng không đẩy được tệp khổng lồ:
# 15 giây mono 32 kbps ~ 60 KB, nên 2 MB đã rộng gấp nhiều lần.
MAX_CHUNK_BYTES = 2 * 1024 * 1024


class AidtMeetingController(http.Controller):

    @http.route('/aidt_meeting/chunk', type='http', auth='user',
                methods=['POST'], csrf=False)
    def upload_chunk(self, recording_id, seq, offset_ms, duration_ms,
                     audio, **kwargs):
        """Nhận một mẩu audio và trả 200 ngay. KHÔNG gọi ASR ở đây.

        Bóc băng chạy trong cron: nếu gọi ASR đồng bộ trong request thì một
        GPU chậm sẽ giữ worker HTTP và làm nghẽn chính cuộc gọi đang diễn ra.
        """
        recording = request.env['aidt.meeting.recording'].browse(
            int(recording_id)).exists()
        if not recording:
            return request.make_json_response({'error': 'not_found'}, status=404)

        raw = audio.read()
        if len(raw) > MAX_CHUNK_BYTES:
            return request.make_json_response(
                {'error': 'too_large'}, status=413)

        # partner LẤY TỪ PHIÊN ĐĂNG NHẬP, không bao giờ từ payload.
        partner = request.env.user.partner_id
        try:
            request.env['aidt.meeting.chunk']._store(
                recording, partner, int(seq), int(offset_ms),
                int(duration_ms), raw)
        except Exception as exc:                     # noqa: BLE001
            _logger.warning('Từ chối mẩu audio cho bản ghi %s: %s',
                            recording.id, exc)
            return request.make_json_response({'error': 'rejected'}, status=403)
        return request.make_json_response({'ok': True})
```

Modify `__init__.py`:

```python
from . import models
from . import controllers
```

Add to `models/__init__.py`:

```python
from . import meeting_chunk
```

Append to `security/ir.model.access.csv`:

```csv
access_meeting_chunk_manager,aidt.meeting.chunk.manager,model_aidt_meeting_chunk,aidt_meeting_minutes.group_meeting_minutes_manager,1,1,1,1
```

Chunks are intentionally **not** readable by `base.group_user`: audio is reached only through `_store` (sudo) and the retention job. Nothing in the UI exposes it.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 5 tests in `TestChunkStore`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): chunk model and upload endpoint with partner spoofing guard"
```

---

### Task 4: ASR adapter

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/asr_client.py`
- Modify: `models/__init__.py`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_asr_client.py`

**Interfaces:**
- Consumes: config keys `aidt_meeting.asr_url`, `asr_model`, `asr_api_key`.
- Produces:
  - `aidt.meeting.asr.client._transcribe(raw_bytes, filename)` → `list[dict]` with keys `start_ms`, `end_ms`, `text`.
  - Exception `AsrError`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_asr_client.py`:

```python
import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.asr_client import AsrError


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AsrCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['aidt.meeting.asr.client']
        cls.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_url', 'http://asr:8002/v1/')

    def _call(self, payload, api_key=''):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_api_key', api_key)
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['url'] = req.full_url
            captured['headers'] = dict(req.headers)
            return FakeResponse(payload)

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            result = self.client._transcribe(b'AUDIO', 'a.mp3')
        return result, captured


class TestAsrClient(AsrCase):
    def test_ghep_dung_duong_dan_va_bo_gach_cheo_thua(self):
        _, captured = self._call({'text': 'xin chào'})
        self.assertEqual(captured['url'],
                         'http://asr:8002/v1/audio/transcriptions')

    def test_co_api_key_thi_gui_bearer(self):
        _, captured = self._call({'text': 'a'}, api_key='sk-abc')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertEqual(header['authorization'], 'Bearer sk-abc')

    def test_khong_co_api_key_thi_bo_han_header(self):
        """Dịch vụ nội bộ không cần key; gửi 'Bearer ' rỗng làm một số
        gateway trả 401 thay vì bỏ qua."""
        _, captured = self._call({'text': 'a'}, api_key='')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertNotIn('authorization', header)

    def test_doc_duoc_segment_co_moc_thoi_gian(self):
        payload = {'segments': [
            {'start': 0.0, 'end': 1.5, 'text': 'câu một'},
            {'start': 1.5, 'end': 3.0, 'text': 'câu hai'},
        ]}
        result, _ = self._call(payload)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertEqual(result[1]['end_ms'], 3000)
        self.assertEqual(result[1]['text'], 'câu hai')

    def test_khong_co_segment_thi_lui_ve_mot_doan_duy_nhat(self):
        """Timestamp bên trong Whisper là thứ dễ suy giảm nhất ở một bản
        fine-tune. Thiết kế lấy mốc từ offset của chunk nên vẫn dùng được:
        chỉ cần trả một đoạn phủ trọn chunk."""
        result, _ = self._call({'text': 'toàn bộ nội dung'})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertIsNone(result[0]['end_ms'])
        self.assertEqual(result[0]['text'], 'toàn bộ nội dung')

    def test_phan_hoi_la_khong_nem_asr_error(self):
        with self.assertRaises(AsrError):
            self._call({'khong_biet': 1})
```

Add `from . import test_asr_client` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `ModuleNotFoundError` for `asr_client`.

- [ ] **Step 3: Write the implementation**

Create `models/asr_client.py`:

```python
import json
import logging
import urllib.error
import urllib.request
import uuid

from odoo import api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 300


class AsrError(RuntimeError):
    """Không gọi được dịch vụ bóc băng, hoặc dịch vụ trả cấu trúc lạ."""


class AidtMeetingAsrClient(models.AbstractModel):
    _name = 'aidt.meeting.asr.client'
    _description = 'Client dịch vụ bóc băng'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _build_multipart(self, raw, filename, model):
        """Dựng thân multipart/form-data thủ công.

        Endpoint /audio/transcriptions theo chuẩn OpenAI nhận multipart chứ
        không phải JSON, mà stdlib không có bộ mã hoá multipart — nên phải
        tự ghép. Trả (content_type, body_bytes).
        """
        boundary = uuid.uuid4().hex
        crlf = b'\r\n'
        parts = []
        for name, value in (('model', model), ('response_format', 'verbose_json')):
            parts += [
                f'--{boundary}'.encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b'', value.encode('utf-8'),
            ]
        parts += [
            f'--{boundary}'.encode(),
            (f'Content-Disposition: form-data; name="file"; '
             f'filename="{filename}"').encode(),
            b'Content-Type: audio/mpeg',
            b'', raw,
            f'--{boundary}--'.encode(), b'',
        ]
        return (f'multipart/form-data; boundary={boundary}',
                crlf.join(parts))

    @api.model
    def _headers(self, content_type):
        headers = {'Content-Type': content_type}
        api_key = (self._config('asr_api_key') or '').strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        return headers

    @api.model
    def _transcribe(self, raw, filename):
        """bytes -> list[{'start_ms', 'end_ms', 'text'}].

        `end_ms` có thể là None khi dịch vụ không trả mốc thời gian; bên gọi
        phải coi đoạn đó phủ trọn chunk.
        """
        base = (self._config('asr_url') or '').rstrip('/')
        url = f'{base}/audio/transcriptions'
        model = self._config('asr_model') or ''
        content_type, body = self._build_multipart(raw, filename, model)
        req = urllib.request.Request(
            url, data=body, headers=self._headers(content_type))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise AsrError(f'gọi bóc băng thất bại: {exc}') from exc
        return self._parse(data)

    @api.model
    def _parse(self, data):
        if not isinstance(data, dict):
            raise AsrError(f'bóc băng trả cấu trúc lạ: {data!r}')
        segments = data.get('segments')
        if isinstance(segments, list) and segments:
            parsed = []
            for seg in segments:
                try:
                    parsed.append({
                        'start_ms': int(float(seg['start']) * 1000),
                        'end_ms': int(float(seg['end']) * 1000),
                        'text': (seg.get('text') or '').strip(),
                    })
                except (KeyError, TypeError, ValueError) as exc:
                    raise AsrError(
                        f'segment thiếu mốc thời gian: {seg!r}') from exc
            return [p for p in parsed if p['text']]
        text = data.get('text')
        if text is None:
            raise AsrError(f'bóc băng không trả text: {data!r}')
        text = text.strip()
        if not text:
            return []
        # Không có segment: phủ trọn chunk. end_ms=None để bên gọi tự lấy
        # duration của chunk làm biên.
        return [{'start_ms': 0, 'end_ms': None, 'text': text}]
```

Add `from . import asr_client` to `models/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 6 tests in `TestAsrClient`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): ASR adapter with multipart upload and optional bearer auth"
```

---

### Task 5: Segment model and transcription queue

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_segment.py`
- Create: `custom-addons/aidt_meeting_minutes/data/ir_cron.xml`
- Modify: `models/meeting_chunk.py`, `models/__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_queue.py`

**Interfaces:**
- Consumes: `aidt.meeting.chunk` (Task 3), `aidt.meeting.asr.client._transcribe` (Task 4).
- Produces:
  - `aidt.meeting.segment` with `recording_id`, `chunk_id`, `partner_id`, `start_ms`, `end_ms`, `text`.
  - `AidtMeetingChunk._claim(limit)` → chunk recordset.
  - `AidtMeetingChunk._process_one()`.
  - `AidtMeetingChunk._cron_process(limit=20, budget_seconds=300)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_queue.py`:

```python
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.asr_client import AsrError

PATH = ('odoo.addons.aidt_meeting_minutes.models.asr_client.'
        'AidtMeetingAsrClient._transcribe')


class QueueCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Người nói', 'login': 'q_nguoinoi@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.user)._start_for_channel(cls.channel)

    def _chunk(self, seq=0, offset_ms=0):
        return self.env['aidt.meeting.chunk'].with_user(self.user)._store(
            self.recording, self.user.partner_id, seq, offset_ms, 15000,
            b'AUDIO')


class TestQueue(QueueCase):
    def test_boc_bang_xong_thi_sinh_segment(self):
        chunk = self._chunk()
        with patch(PATH, return_value=[
                {'start_ms': 500, 'end_ms': 2000, 'text': 'xin chào'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'done')
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(len(segment), 1)
        self.assertEqual(segment.text, 'xin chào')

    def test_moc_thoi_gian_la_tuyet_doi_theo_offset_cua_chunk(self):
        """Segment lưu vị trí tuyệt đối trong cuộc họp, không phải vị trí
        trong chunk — nếu không thì trộn nhiều người sẽ sai hoàn toàn."""
        chunk = self._chunk(seq=2, offset_ms=30000)
        with patch(PATH, return_value=[
                {'start_ms': 500, 'end_ms': 2000, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.start_ms, 30500)
        self.assertEqual(segment.end_ms, 32000)

    def test_khong_co_end_ms_thi_lay_het_do_dai_chunk(self):
        chunk = self._chunk(offset_ms=10000)
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': None, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.end_ms, 25000)

    def test_loi_thi_lui_lich_thu_lai_chu_khong_chet_han(self):
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('service chết')):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'pending')
        self.assertEqual(chunk.attempt, 1)
        self.assertTrue(chunk.next_retry_at)

    def test_het_ba_lan_thi_danh_dau_failed(self):
        """Phải đóng đinh 'failed': để 'pending' mãi thì `_claim` (sắp theo
        id) nhận lại đúng chunk hỏng ở mọi nhịp cron và không chunk nào phía
        sau được chạy."""
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('chết')):
            for _i in range(3):
                chunk.next_retry_at = False
                self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'failed')

    def test_chua_toi_han_thu_lai_thi_khong_nhan(self):
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('chết')):
            self.env['aidt.meeting.chunk']._cron_process()
        claimed = self.env['aidt.meeting.chunk']._claim(limit=5)
        self.assertNotIn(chunk, claimed)
```

Add `from . import test_queue` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `KeyError: 'aidt.meeting.segment'`.

- [ ] **Step 3: Write the implementation**

Create `models/meeting_segment.py`:

```python
from odoo import fields, models


class AidtMeetingSegment(models.Model):
    _name = 'aidt.meeting.segment'
    _description = 'Đoạn lời nói đã bóc băng'
    _order = 'recording_id, start_ms, id'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    chunk_id = fields.Many2one(
        'aidt.meeting.chunk', string='Mẩu audio', ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Người nói', required=True, index=True)
    # TUYỆT ĐỐI trong cuộc họp, không phải tương đối trong chunk.
    start_ms = fields.Integer(string='Bắt đầu (ms)', required=True, index=True)
    end_ms = fields.Integer(string='Kết thúc (ms)', required=True)
    text = fields.Text(string='Nội dung', required=True)
```

Append to `models/meeting_chunk.py`:

```python
    # ------------------------------------------------------------------ #
    # Hàng đợi bóc băng
    # ------------------------------------------------------------------ #
    @api.model
    def _claim(self, limit=1):
        """Nhận việc bằng SKIP LOCKED — an toàn khi chạy nhiều worker.

        `write()` của ORM chỉ đánh dấu field bẩn trong cache chứ chưa ghi
        xuống bảng, mà câu SELECT dưới đây đọc thẳng Postgres — phải flush
        trước, nếu không nó thấy dữ liệu cũ.
        """
        self.flush_model()
        self.env.cr.execute("""
            SELECT id FROM aidt_meeting_chunk
             WHERE state = 'pending'
               AND (next_retry_at IS NULL
                    OR next_retry_at <= now() AT TIME ZONE 'UTC')
             ORDER BY id
             LIMIT %s
               FOR UPDATE SKIP LOCKED
        """, (limit,))
        return self.browse([r[0] for r in self.env.cr.fetchall()])

    def _process_one(self):
        """Bóc băng đúng một mẩu đã được `_claim()` khoá."""
        self.ensure_one()
        try:
            # SAVEPOINT là thứ khiến khối `except` dưới đây chạy được: nếu
            # lỗi đến từ tầng CSDL thì cursor rơi vào InFailedSqlTransaction
            # và chính đường ghi trạng thái lỗi cũng sẽ ném tiếp, giết cả
            # lượt cron và kẹt hàng đợi vĩnh viễn ở đúng mẩu này.
            with self.env.cr.savepoint():
                raw = base64.b64decode(self.attachment_id.sudo().datas or b'')
                parsed = self.env['aidt.meeting.asr.client']._transcribe(
                    raw, f'chunk-{self.id}.mp3')
                self._write_segments(parsed)
                self.sudo().write({'state': 'done', 'error': False})
        except Exception as exc:                     # noqa: BLE001
            _logger.exception('Bóc băng thất bại cho mẩu %s', self.id)
            self.env.invalidate_all()
            self._mark_retry(str(exc))

    def _write_segments(self, parsed):
        """Quy đổi mốc tương đối trong chunk sang tuyệt đối trong cuộc họp."""
        self.ensure_one()
        Segment = self.env['aidt.meeting.segment'].sudo()
        Segment.search([('chunk_id', '=', self.id)]).unlink()
        rows = []
        for item in parsed:
            end = item['end_ms']
            if end is None:
                end = self.duration_ms
            rows.append({
                'recording_id': self.recording_id.id,
                'chunk_id': self.id,
                'partner_id': self.partner_id.id,
                'start_ms': self.offset_ms + item['start_ms'],
                'end_ms': self.offset_ms + end,
                'text': item['text'],
            })
        if rows:
            Segment.create(rows)

    @api.model
    def _cron_process(self, limit=20, budget_seconds=300):
        """Chạy mỗi phút. Nhận và xử lý TỪNG mẩu một, commit ngay sau mẩu đó.

        Không khoá cả lô rồi commit giữa chừng: khoá FOR UPDATE SKIP LOCKED
        chỉ sống trong giao dịch hiện tại, nên commit sau mẩu đầu sẽ NHẢ khoá
        những mẩu còn lại trong lô dù chúng vẫn 'pending' — một tiến trình
        cron chồng lên có thể nhận trúng và xử lý song song.
        """
        started = time.monotonic()
        processed = 0
        while processed < limit:
            if time.monotonic() - started > budget_seconds:
                break
            chunk = self._claim(limit=1)
            if not chunk:
                break
            try:
                chunk._process_one()
            except Exception:                        # noqa: BLE001
                # Lớp chắn thứ hai, cố tình thừa: nếu chính đường ghi lỗi
                # cũng hỏng thì vẫn không được để một mẩu kéo đổ cả lô.
                _logger.exception(
                    'Mẩu %s làm hỏng lượt xử lý; đánh dấu failed.', chunk.id)
                if not config['test_enable']:
                    self.env.cr.rollback()
                self.env.invalidate_all()
                chunk._mark_failed('Làm hỏng lượt xử lý, xem log máy chủ.')
            if not config['test_enable']:
                self.env.cr.commit()
            processed += 1
        return True
```

Update the imports at the top of `models/meeting_chunk.py`:

```python
import base64
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import config
```

Create `data/ir_cron.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="cron_transcribe" model="ir.cron">
            <field name="name">AIDT: bóc băng mẩu audio cuộc họp</field>
            <field name="model_id" ref="model_aidt_meeting_chunk"/>
            <field name="state">code</field>
            <field name="code">model._cron_process()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">minutes</field>
            <field name="nextcall"
                   eval="(DateTime.now() + timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')"/>
            <field name="active" eval="True"/>
        </record>
    </data>
</odoo>
```

Add `'data/ir_cron.xml',` to `__manifest__.py` `data`, after `'data/ir_config_parameter.xml',`.

Add to `models/__init__.py`: `from . import meeting_segment` (before `meeting_chunk` is fine; ORM resolves by name).

Append to `security/ir.model.access.csv`:

```csv
access_meeting_segment_user,aidt.meeting.segment.user,model_aidt_meeting_segment,base.group_user,1,0,0,0
access_meeting_segment_manager,aidt.meeting.segment.manager,model_aidt_meeting_segment,aidt_meeting_minutes.group_meeting_minutes_manager,1,1,1,1
```

Add a segment record rule to `security/aidt_meeting_rules.xml` inside `<data noupdate="1">`:

```xml
        <record id="rule_segment_participant" model="ir.rule">
            <field name="name">Đoạn bóc băng: theo quyền của bản ghi</field>
            <field name="model_id" ref="model_aidt_meeting_segment"/>
            <field name="domain_force">
                ['|',
                 ('recording_id.channel_id.channel_member_ids.partner_id', '=', user.partner_id.id),
                 ('recording_id.event_id.partner_ids', 'in', [user.partner_id.id])]
            </field>
            <field name="groups" eval="[(4, ref('base.group_user'))]"/>
        </record>
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 6 tests in `TestQueue`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): transcription queue with skip-locked claiming and backoff"
```

---

### Task 6: Transcript assembly

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/transcript_builder.py`
- Modify: `models/__init__.py`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_transcript.py`

**Interfaces:**
- Consumes: `aidt.meeting.segment` (Task 5).
- Produces: `aidt.meeting.transcript._build(recording)` → `str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transcript.py`:

```python
from odoo.tests.common import TransactionCase


class TranscriptCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.builder = cls.env['aidt.meeting.transcript']
        cls.an = cls.env['res.partner'].create({'name': 'Nguyễn Văn An'})
        cls.binh = cls.env['res.partner'].create({'name': 'Trần Thị Bình'})
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
        })

    def _seg(self, partner, start_ms, end_ms, text):
        return self.env['aidt.meeting.segment'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': partner.id,
            'start_ms': start_ms, 'end_ms': end_ms, 'text': text,
        })


class TestTranscript(TranscriptCase):
    def test_tron_dung_thu_tu_giua_hai_nguoi(self):
        self._seg(self.binh, 5000, 7000, 'Tôi đồng ý')
        self._seg(self.an, 1000, 3000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertLess(text.index('Xin chào'), text.index('Tôi đồng ý'))

    def test_gop_luot_noi_lien_tiep_cua_cung_mot_nguoi(self):
        """Ba đoạn liền của một người phải thành một khối, không phải ba
        dòng lặp tên — biên bản đọc được mới là mục tiêu."""
        self._seg(self.an, 0, 1000, 'Câu một.')
        self._seg(self.an, 1000, 2000, 'Câu hai.')
        self._seg(self.an, 2000, 3000, 'Câu ba.')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('Nguyễn Văn An'), 1)
        self.assertIn('Câu một. Câu hai. Câu ba.', text)

    def test_khu_trung_lap_o_moi_noi_chong_lan(self):
        """Chunk chồng lấn 1.5 giây nên câu ở mối nối bị bóc băng hai lần.
        Không khử thì biên bản lặp chữ ở mỗi 15 giây."""
        self._seg(self.an, 0, 15000, 'Chúng ta bắt đầu cuộc họp')
        self._seg(self.an, 13500, 28000, 'cuộc họp hôm nay bàn ba việc')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('cuộc họp'), 1)

    def test_danh_dau_khoang_thieu_am_thanh(self):
        """Khoảng khuyết phải được nói ra. Một biên bản có lỗ hổng vô hình
        tệ hơn một biên bản thừa nhận nó."""
        chunk = self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': self.an.id,
            'seq': 5, 'offset_ms': 60000, 'duration_ms': 15000,
            'state': 'failed', 'error': 'ASR chết',
        })
        self.assertTrue(chunk)
        text = self.builder._build(self.recording)
        self.assertIn('[thiếu âm thanh', text)
        self.assertIn('01:00', text)

    def test_neu_ten_nguoi_tu_choi_o_dau_ban(self):
        self.recording.sudo().declined_partner_ids = [(4, self.binh.id)]
        self._seg(self.an, 0, 1000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertIn('Trần Thị Bình', text.split('\n\n')[0])

    def test_ban_rong_van_tra_ve_chuoi_khong_nem_loi(self):
        text = self.builder._build(self.recording)
        self.assertIsInstance(text, str)
```

Add `from . import test_transcript` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `KeyError: 'aidt.meeting.transcript'`.

- [ ] **Step 3: Write the implementation**

Create `models/transcript_builder.py`:

```python
from odoo import api, models

# Số từ tối đa thử khớp ở mối nối. Chồng lấn là 1.5 giây, người nói nhanh
# nhất cũng khó vượt ~12 từ trong ngần ấy thời gian.
MAX_OVERLAP_WORDS = 12


class AidtMeetingTranscript(models.AbstractModel):
    _name = 'aidt.meeting.transcript'
    _description = 'Dựng bản bóc băng từ các đoạn'

    @api.model
    def _format_ts(self, ms):
        total = max(0, ms) // 1000
        return f'{total // 60:02d}:{total % 60:02d}'

    @api.model
    def _strip_overlap(self, previous, current):
        """Bỏ phần đầu của `current` nếu nó lặp lại phần đuôi của `previous`.

        Khớp theo TỪ chứ không theo ký tự: bóc băng hai lần cùng một đoạn
        audio hiếm khi ra chuỗi ký tự trùng khít, nhưng chuỗi từ thì thường
        trùng. Thử từ dài đến ngắn để lấy phần chồng lớn nhất.
        """
        prev_words = previous.split()
        cur_words = current.split()
        if not prev_words or not cur_words:
            return current
        limit = min(MAX_OVERLAP_WORDS, len(prev_words), len(cur_words))
        for size in range(limit, 0, -1):
            tail = [w.lower().strip('.,;:!?') for w in prev_words[-size:]]
            head = [w.lower().strip('.,;:!?') for w in cur_words[:size]]
            if tail == head:
                return ' '.join(cur_words[size:])
        return current

    @api.model
    def _gap_markers(self, recording):
        """Một dòng cho mỗi mẩu audio hỏng, kèm mốc thời gian."""
        failed = self.env['aidt.meeting.chunk'].sudo().search([
            ('recording_id', '=', recording.id), ('state', '=', 'failed'),
        ], order='offset_ms')
        markers = []
        for chunk in failed:
            start = self._format_ts(chunk.offset_ms)
            end = self._format_ts(chunk.offset_ms + chunk.duration_ms)
            markers.append({
                'start_ms': chunk.offset_ms,
                'line': (f'[thiếu âm thanh {start}–{end}: '
                         f'{chunk.partner_id.name}]'),
            })
        return markers

    @api.model
    def _build(self, recording):
        segments = self.env['aidt.meeting.segment'].sudo().search(
            [('recording_id', '=', recording.id)], order='start_ms, id')

        blocks = []
        for seg in segments:
            text = (seg.text or '').strip()
            if not text:
                continue
            if blocks and blocks[-1]['partner'] == seg.partner_id:
                text = self._strip_overlap(blocks[-1]['text'], text)
                if not text:
                    continue
                blocks[-1]['text'] = f"{blocks[-1]['text']} {text}"
                continue
            blocks.append({
                'partner': seg.partner_id,
                'start_ms': seg.start_ms,
                'text': text,
            })

        lines = []
        for block in blocks:
            lines.append({
                'start_ms': block['start_ms'],
                'line': (f"[{self._format_ts(block['start_ms'])}] "
                         f"{block['partner'].name}: {block['text']}"),
            })
        lines += self._gap_markers(recording)
        lines.sort(key=lambda item: item['start_ms'])

        header = []
        declined = recording.sudo().declined_partner_ids
        if declined:
            names = ', '.join(declined.mapped('name'))
            # Nêu tên ngay đầu bản: người đọc phải biết thiếu giọng của ai,
            # thay vì tưởng những người đó im lặng suốt cuộc họp.
            header.append(
                f'Không ghi âm giọng của: {names} (đã từ chối ghi âm).')

        body = '\n'.join(item['line'] for item in lines)
        if header:
            return '\n\n'.join(['\n'.join(header), body])
        return body
```

Add `from . import transcript_builder` to `models/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 6 tests in `TestTranscript`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): transcript assembly with seam dedup and gap markers"
```

---

### Task 7: End detection and finalize

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py`
- Modify: `data/ir_cron.xml`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_finalize.py`

**Interfaces:**
- Consumes: `aidt.meeting.transcript._build` (Task 6), chunk states (Task 5).
- Produces:
  - `AidtMeetingRecording._cron_sweep()` — ends abandoned calls, finalizes ready ones.
  - `AidtMeetingRecording._finalize()` — writes `transcript_text`, posts it, sets `done`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_finalize.py`:

```python
from odoo.tests.common import TransactionCase


class FinalizeCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.user = cls.env['res.users'].create({
            'name': 'Chủ trì', 'login': 'f_chutri@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])

    def _recording(self, with_event=False):
        event = False
        if with_event:
            event = self.env['calendar.event'].create({
                'name': 'Họp giao ban',
                'start': '2026-08-04 01:00:00',
                'stop': '2026-08-04 02:00:00',
                'user_id': self.user.id,
                'videocall_channel_id': self.channel.id,
                'partner_ids': [(6, 0, [self.user.partner_id.id])],
            })
        return self.Recording.sudo().create({
            'channel_id': self.channel.id,
            'event_id': event.id if event else False,
            'secrecy_at_start': 'thuong',
            'state': 'processing',
        })

    def _segment(self, recording, text='Xin chào'):
        return self.env['aidt.meeting.segment'].sudo().create({
            'recording_id': recording.id,
            'partner_id': self.user.partner_id.id,
            'start_ms': 0, 'end_ms': 1000, 'text': text,
        })


class TestFinalize(FinalizeCase):
    def test_xong_het_chunk_thi_dung_transcript(self):
        rec = self._recording()
        self._segment(rec)
        rec._finalize()
        self.assertEqual(rec.state, 'done')
        self.assertIn('Xin chào', rec.transcript_text)

    def test_con_chunk_pending_thi_chua_hoan_tat(self):
        rec = self._recording()
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': rec.id, 'partner_id': self.user.partner_id.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 15000, 'state': 'pending',
        })
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'processing')

    def test_co_cuoc_hop_thi_dang_vao_chatter_su_kien(self):
        rec = self._recording(with_event=True)
        self._segment(rec)
        rec._finalize()
        bodies = rec.event_id.message_ids.mapped('body')
        self.assertTrue(any('Xin chào' in (b or '') for b in bodies))

    def test_khong_co_cuoc_hop_thi_dang_vao_kenh(self):
        """Cuộc gọi tự phát: transcript quay lại đúng nơi cuộc gọi diễn ra."""
        rec = self._recording(with_event=False)
        self._segment(rec)
        rec._finalize()
        bodies = self.channel.message_ids.mapped('body')
        self.assertTrue(any('Xin chào' in (b or '') for b in bodies))

    def test_cuoc_goi_bo_do_duoc_quet_sang_processing(self):
        """Kiểu kết thúc phổ biến không phải bấm nút mà là tất cả cùng gập
        máy — không có lớp quét này thì bản ghi treo ở 'recording' mãi."""
        rec = self.Recording.sudo().create({
            'channel_id': self.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'recording',
        })
        self.Recording._cron_sweep()
        self.assertEqual(rec.state, 'processing')
```

Add `from . import test_finalize` to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `AttributeError: '_finalize'`.

- [ ] **Step 3: Write the implementation**

Append to `models/meeting_recording.py`:

```python
    # ------------------------------------------------------------------ #
    # Kết thúc và hoàn tất
    # ------------------------------------------------------------------ #
    def _has_live_session(self):
        self.ensure_one()
        return bool(self.env['discuss.channel.rtc.session'].sudo().search_count(
            [('channel_id', '=', self.channel_id.id)]))

    def _chunks_settled(self):
        """True khi mọi mẩu audio đã 'done' hoặc 'failed'."""
        self.ensure_one()
        return not self.env['aidt.meeting.chunk'].sudo().search_count([
            ('recording_id', '=', self.id),
            ('state', 'in', ('pending', 'transcribing')),
        ])

    def _post_target(self):
        """Cuộc họp có lịch thì đăng vào chatter sự kiện; cuộc gọi tự phát
        thì đăng thẳng vào kênh, đúng nơi cuộc gọi đã diễn ra."""
        self.ensure_one()
        return self.event_id.sudo() if self.event_id else self.channel_id.sudo()

    def _finalize(self):
        self.ensure_one()
        transcript = self.env['aidt.meeting.transcript']._build(self)
        self.sudo().write({'transcript_text': transcript, 'state': 'done'})
        body = Markup('<p><b>%s</b></p><pre>%s</pre>') % (
            _('Bản bóc băng cuộc họp'), transcript or _('(không có nội dung)'))
        self._post_target().message_post(body=body)
        return True

    @api.model
    def _cron_sweep(self):
        """Hai việc: đóng bản ghi bị bỏ dở, và hoàn tất bản ghi đã đủ dữ liệu."""
        for recording in self.sudo().search([('state', '=', 'recording')]):
            if not recording._has_live_session():
                recording.write({
                    'state': 'processing', 'ended_at': fields.Datetime.now(),
                })
                recording._broadcast_state('stopped')
        for recording in self.sudo().search([('state', '=', 'processing')]):
            if recording._chunks_settled():
                try:
                    with self.env.cr.savepoint():
                        recording._finalize()
                except Exception:                    # noqa: BLE001
                    _logger.exception(
                        'Hoàn tất bản ghi %s thất bại', recording.id)
            if not config['test_enable']:
                self.env.cr.commit()
        return True
```

Update imports at the top of `models/meeting_recording.py`:

```python
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config
```

Add to `data/ir_cron.xml` inside `<data noupdate="1">`:

```xml
        <record id="cron_sweep_recording" model="ir.cron">
            <field name="name">AIDT: đóng và hoàn tất bản ghi cuộc họp</field>
            <field name="model_id" ref="model_aidt_meeting_recording"/>
            <field name="state">code</field>
            <field name="code">model._cron_sweep()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">minutes</field>
            <field name="nextcall"
                   eval="(DateTime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')"/>
            <field name="active" eval="True"/>
        </record>
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 5 tests in `TestFinalize`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): end detection sweep and transcript posting"
```

---

### Task 8: Summary adapter, map-reduce, and retention

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/summary_client.py`
- Modify: `models/meeting_recording.py`, `models/__init__.py`, `data/ir_cron.xml`, `views/meeting_recording_views.xml` (create)
- Modify: `__manifest__.py`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_summary.py`, `tests/test_retention.py`

**Interfaces:**
- Consumes: `transcript_text` from Task 7.
- Produces:
  - `aidt.meeting.summary.client._summarize(text)` → `str`; exception `SummaryError`.
  - `AidtMeetingRecording.action_retry_summary()`.
  - `AidtMeetingRecording._cron_purge_audio()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_summary.py`:

```python
import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.summary_client import SummaryError

PATH = ('odoo.addons.aidt_meeting_minutes.models.summary_client.'
        'AidtMeetingSummaryClient._chat')


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SummaryCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['aidt.meeting.summary.client']
        cls.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.llm_url', 'http://llm:8003/v1/')
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
            'state': 'processing',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'An'})
        cls.env['aidt.meeting.segment'].sudo().create({
            'recording_id': cls.recording.id, 'partner_id': cls.partner.id,
            'start_ms': 0, 'end_ms': 1000, 'text': 'Nội dung cuộc họp',
        })


class TestSummaryClient(SummaryCase):
    def test_ghep_dung_duong_dan_chat_completions(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['url'] = req.full_url
            return FakeResponse(
                {'choices': [{'message': {'content': 'tóm tắt'}}]})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            self.client._chat('xin chào')
        self.assertEqual(captured['url'], 'http://llm:8003/v1/chat/completions')

    def test_phan_hoi_la_thi_nem_summary_error(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse({'khong_biet': 1})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            with self.assertRaises(SummaryError):
                self.client._chat('xin chào')

    def test_ban_dai_thi_chia_cua_so_roi_tom_tat_lai(self):
        """Map-reduce không chỉ để lách giới hạn context — nó là thứ giữ cho
        KV cache đủ nhỏ để ba model cùng vừa trên card 16 GB."""
        long_text = '\n'.join(f'[00:{i:02d}] An: câu {i}' for i in range(400))
        calls = []

        def fake_chat(prompt):
            calls.append(prompt)
            return 'tóm tắt phần'

        with patch(PATH, side_effect=fake_chat):
            result = self.client._summarize(long_text)
        self.assertGreater(len(calls), 1)
        self.assertTrue(result)


class TestSummaryStage(SummaryCase):
    def test_llm_chet_van_giu_duoc_transcript(self):
        """Lỗi của bộ tóm tắt KHÔNG BAO GIỜ được làm mất transcript — hai
        giai đoạn tách rời chính là để sản phẩm khó tạo lại nhất sống sót."""
        with patch(PATH, side_effect=SummaryError('LLM chết')):
            self.recording._finalize()
        self.assertEqual(self.recording.state, 'done')
        self.assertIn('Nội dung cuộc họp', self.recording.transcript_text)
        self.assertFalse(self.recording.summary_text)
        self.assertIn('LLM chết', self.recording.summary_error)

    def test_tao_lai_tom_tat_duoc_sau_khi_loi(self):
        with patch(PATH, side_effect=SummaryError('chết')):
            self.recording._finalize()
        with patch(PATH, return_value='tóm tắt lại'):
            self.recording.action_retry_summary()
        self.assertEqual(self.recording.summary_text, 'tóm tắt lại')
        self.assertFalse(self.recording.summary_error)
```

Create `tests/test_retention.py`:

```python
from odoo.tests.common import TransactionCase


class RetentionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'An'})
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
        })

    def _chunk(self, state='done'):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'a.mp3', 'datas': b'QUJD', 'mimetype': 'audio/mpeg',
        })
        return self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': self.partner.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 15000,
            'state': state, 'attachment_id': attachment.id,
        })


class TestRetention(RetentionCase):
    def test_mac_dinh_khong_ngay_thi_xoa_audio_ngay(self):
        """Audio thô của một cuộc họp cấp uỷ là rủi ro lớn hơn transcript và
        không có bên nào dùng đến sau khi đã bóc băng."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='done')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertFalse(chunk.attachment_id)

    def test_giu_lai_khi_cau_hinh_lon_hon_khong(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '30')
        chunk = self._chunk(state='done')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertTrue(chunk.attachment_id)

    def test_khong_xoa_audio_cua_mau_chua_boc_bang_xong(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='pending')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertTrue(chunk.attachment_id)
```

Add both to `tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: FAIL — `ModuleNotFoundError` for `summary_client`.

- [ ] **Step 3: Write the implementation**

Create `models/summary_client.py`:

```python
import json
import logging
import urllib.error
import urllib.request

from odoo import _, api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 300
# Cửa sổ map-reduce, tính theo dòng transcript. Giữ nhỏ có chủ đích: KV cache
# còn khoảng 2.5 GB sau khi embedding + ASR + trọng số LLM đã chiếm chỗ.
WINDOW_LINES = 120

SYSTEM_PROMPT = (
    'Bạn là thư ký cuộc họp. Tóm tắt bằng tiếng Việt, ngắn gọn, theo ba mục: '
    'NỘI DUNG CHÍNH, KẾT LUẬN, VIỆC CẦN LÀM. Chỉ dùng thông tin có trong bản '
    'bóc băng, không suy diễn thêm. Nếu bản bóc băng có đánh dấu thiếu âm '
    'thanh, nêu rõ là nội dung có thể không đầy đủ.'
)


class SummaryError(RuntimeError):
    """Không gọi được dịch vụ tóm tắt, hoặc dịch vụ trả cấu trúc lạ."""


class AidtMeetingSummaryClient(models.AbstractModel):
    _name = 'aidt.meeting.summary.client'
    _description = 'Client dịch vụ tóm tắt'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _chat(self, prompt):
        base = (self._config('llm_url') or '').rstrip('/')
        url = f'{base}/chat/completions'
        body = {
            'model': self._config('llm_model') or '',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
        }
        headers = {'Content-Type': 'application/json'}
        api_key = (self._config('llm_api_key') or '').strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        req = urllib.request.Request(
            url, data=json.dumps(body).encode('utf-8'), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SummaryError(f'gọi tóm tắt thất bại: {exc}') from exc
        try:
            return data['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise SummaryError(f'tóm tắt trả cấu trúc lạ: {data!r}') from exc

    @api.model
    def _summarize(self, transcript):
        """Map-reduce: tóm tắt từng cửa sổ rồi tóm tắt các bản tóm tắt.

        Họp hai tiếng chắc chắn vượt cửa sổ context, nên đây không phải
        trường hợp biên mà là đường đi mặc định của mọi cuộc họp dài.
        """
        text = (transcript or '').strip()
        if not text:
            return ''
        lines = text.split('\n')
        if len(lines) <= WINDOW_LINES:
            return self._chat(text)
        partials = []
        for start in range(0, len(lines), WINDOW_LINES):
            window = '\n'.join(lines[start:start + WINDOW_LINES])
            partials.append(self._chat(window))
        joined = '\n\n'.join(partials)
        return self._chat(
            _('Dưới đây là các bản tóm tắt từng phần của cùng một cuộc họp. '
              'Hợp nhất thành một bản tóm tắt duy nhất, không lặp ý:\n\n%s',
              joined))
```

Append to `models/meeting_recording.py`:

```python
    def _run_summary(self):
        """Tóm tắt. Lỗi được ghi lại nhưng KHÔNG lan ra ngoài — transcript đã
        đăng rồi và không được mất vì bộ tóm tắt chết."""
        self.ensure_one()
        try:
            summary = self.env['aidt.meeting.summary.client']._summarize(
                self.transcript_text)
        except Exception as exc:                     # noqa: BLE001
            _logger.warning('Tóm tắt thất bại cho bản ghi %s: %s', self.id, exc)
            self.sudo().write({'summary_error': str(exc)})
            return False
        self.sudo().write({'summary_text': summary, 'summary_error': False})
        if summary:
            self._post_target().message_post(
                body=Markup('<p><b>%s</b></p><pre>%s</pre>') % (
                    _('Tóm tắt cuộc họp'), summary))
        return True

    def action_retry_summary(self):
        self.ensure_one()
        return self._run_summary()

    @api.model
    def _cron_purge_audio(self):
        """Xoá audio của những mẩu đã bóc băng xong, theo chính sách lưu trữ."""
        days = int(self._config('audio_retention_days', '0') or 0)
        domain = [('state', '=', 'done'), ('attachment_id', '!=', False)]
        if days > 0:
            cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
            domain.append(('create_date', '<=', cutoff))
        chunks = self.env['aidt.meeting.chunk'].sudo().search(domain)
        attachments = chunks.mapped('attachment_id')
        chunks.write({'attachment_id': False})
        attachments.unlink()
        return True
```

In `_finalize`, add the summary call before `return True`:

```python
        self._run_summary()
        self._cron_purge_audio()
        return True
```

Add `from . import summary_client` to `models/__init__.py`.

Add to `data/ir_cron.xml` inside `<data noupdate="1">`:

```xml
        <record id="cron_purge_audio" model="ir.cron">
            <field name="name">AIDT: xoá audio cuộc họp theo chính sách</field>
            <field name="model_id" ref="model_aidt_meeting_recording"/>
            <field name="state">code</field>
            <field name="code">model._cron_purge_audio()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">days</field>
            <field name="nextcall"
                   eval="(DateTime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')"/>
            <field name="active" eval="True"/>
        </record>
```

Create `views/meeting_recording_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_meeting_recording_form" model="ir.ui.view">
        <field name="name">aidt.meeting.recording.form</field>
        <field name="model">aidt.meeting.recording</field>
        <field name="arch" type="xml">
            <form string="Bản ghi cuộc họp">
                <header>
                    <button name="action_stop" type="object" string="Dừng ghi âm"
                            invisible="state != 'recording'"/>
                    <button name="action_retry_summary" type="object"
                            string="Tạo lại tóm tắt"
                            invisible="not summary_error"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="event_id"/>
                        <field name="channel_id"/>
                        <field name="secrecy_at_start"/>
                        <field name="started_by_id"/>
                        <field name="started_at"/>
                        <field name="ended_at"/>
                        <field name="declined_partner_ids" widget="many2many_tags"/>
                    </group>
                    <notebook>
                        <page string="Tóm tắt">
                            <field name="summary_error" readonly="1"
                                   invisible="not summary_error"/>
                            <field name="summary_text" readonly="1"/>
                        </page>
                        <page string="Bản bóc băng">
                            <field name="transcript_text" readonly="1"/>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_meeting_recording" model="ir.actions.act_window">
        <field name="name">Bản ghi cuộc họp</field>
        <field name="res_model">aidt.meeting.recording</field>
        <field name="view_mode">list,form</field>
    </record>

    <menuitem id="menu_meeting_recording"
              name="Bản ghi cuộc họp"
              parent="calendar.mail_menu_calendar"
              action="action_meeting_recording"
              groups="aidt_meeting_minutes.group_meeting_minutes_manager"
              sequence="90"/>
</odoo>
```

Add `'views/meeting_recording_views.xml',` to `__manifest__.py` `data`, before the settings view.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: PASS, 5 tests in `TestSummaryClient`/`TestSummaryStage` and 3 in `TestRetention`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): map-reduce summary, retry action and audio retention"
```

---

### Task 9: Client-side recorder

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/recorder_service.js`
- Create: `custom-addons/aidt_meeting_minutes/static/src/rtc_service_patch.js`
- Modify: `__manifest__.py` (add `assets`)
- Test: `custom-addons/aidt_meeting_minutes/static/tests/recorder.test.js`

**Interfaces:**
- Consumes: bus event `aidt_meeting_minutes/recording_state` (Task 2), route `/aidt_meeting/chunk` (Task 3).
- Produces: service `aidt_meeting.recorder` exposing `state.recordingId`, `start(recordingId, elapsedMs)`, `stop()`, `decline()`, and `_shouldUpload(track, rms)`.

- [ ] **Step 1: Write the failing test**

Create `static/tests/recorder.test.js`:

```javascript
import { describe, expect, test } from "@odoo/hoot";
import { computeOffsetMs, shouldUpload } from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

describe("recorder timing", () => {
    test("offset đo theo thời gian trôi cục bộ, không theo đồng hồ tường", () => {
        // Máy vào giữa chừng: elapsedAtJoin do server cấp, phần còn lại là
        // performance.now() của chính máy đó. Lệch đồng hồ giữa các máy
        // không được ảnh hưởng tới kết quả.
        const offset = computeOffsetMs({
            elapsedAtJoinMs: 30000,
            recorderStartedAt: 1000,
            now: 4500,
        });
        expect(offset).toBe(33500);
    });

    test("vào ngay từ đầu thì offset bắt đầu từ 0", () => {
        const offset = computeOffsetMs({
            elapsedAtJoinMs: 0,
            recorderStartedAt: 500,
            now: 500,
        });
        expect(offset).toBe(0);
    });
});

describe("mute gating", () => {
    test("tắt tiếng thì bỏ hẳn chunk", () => {
        // Whisper bịa ra chữ từ khoảng lặng số, nên cách xử lý đúng là
        // không đưa khoảng lặng vào chứ không phải lọc kết quả về sau.
        expect(shouldUpload({ enabled: false }, 0.5)).toBe(false);
    });

    test("dưới ngưỡng năng lượng thì bỏ chunk", () => {
        expect(shouldUpload({ enabled: true }, 0.0001)).toBe(false);
    });

    test("đang nói thì gửi", () => {
        expect(shouldUpload({ enabled: true }, 0.05)).toBe(true);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Then open `http://localhost:8069/web/tests?module=aidt_meeting_minutes`.
Expected: FAIL — module `@aidt_meeting_minutes/recorder_service` not found.

- [ ] **Step 3: Write the implementation**

Create `static/src/recorder_service.js`:

```javascript
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";
import { Mp3Encoder } from "@mail/discuss/voice_message/common/mp3_encoder";

// PhoWhisper resample về 16 kHz; làm sẵn ở trình duyệt bỏ được một bước
// resample phía server và cho phép hạ bitrate mà giọng nói vẫn rõ.
const SAMPLE_RATE = 16000;
const CHUNK_MS = 15000;
// Chồng lấn để câu chữ không bị cắt đôi ở mối nối; phần trùng được khử ở
// server khi ghép segment.
const OVERLAP_MS = 1500;
// Dưới ngưỡng này coi như im lặng. Whisper bịa chữ từ khoảng lặng số.
const RMS_FLOOR = 0.005;
const MAX_BUFFERED_CHUNKS = 8;

/**
 * Vị trí tuyệt đối của chunk trong cuộc họp.
 * Chỉ dùng thời gian trôi CỤC BỘ (performance.now()) cộng với phần đã trôi
 * lúc máy này vào họp — không bao giờ dùng đồng hồ tường, nên lệch đồng hồ
 * giữa các máy không thể làm rối thứ tự khi server trộn.
 */
export function computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now }) {
    return Math.max(0, Math.round(elapsedAtJoinMs + (now - recorderStartedAt)));
}

/** Tắt tiếng hoặc quá nhỏ thì không gửi. */
export function shouldUpload(track, rms) {
    if (!track || !track.enabled) {
        return false;
    }
    return rms >= RMS_FLOOR;
}

export class MeetingRecorder {
    constructor(env, services) {
        this.env = env;
        this.rtc = services["discuss.rtc"];
        this.bus = services.bus_service;
        this.notification = services.notification;
        this.state = reactive({ recordingId: null, declined: false });

        this.seq = 0;
        this.pending = [];
        this.audioContext = null;
        this.encoder = null;
        this.clonedTrack = null;

        this.bus.subscribe("aidt_meeting_minutes/recording_state", (payload) =>
            this._onRecordingState(payload)
        );
    }

    _onRecordingState(payload) {
        if (payload.action === "started") {
            this.start(payload.recording_id, payload.elapsed_ms || 0);
        } else {
            this.stop();
        }
    }

    async start(recordingId, elapsedAtJoinMs) {
        if (this.state.recordingId || this.state.declined) {
            return;
        }
        this.state.recordingId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.seq = 0;
        await this._attachToMic();
    }

    async _attachToMic() {
        const micTrack = this.rtc.state?.micAudioTrack;
        if (!micTrack || !this.state.recordingId) {
            return;
        }
        this._teardownGraph();
        // CLONE: recorder không bao giờ được làm nhiễu thứ mà người khác
        // đang nghe. Cùng cách media_monitoring.js làm.
        this.clonedTrack = micTrack.clone();
        this.sourceTrack = micTrack;

        this.audioContext = new browser.AudioContext({ sampleRate: SAMPLE_RATE });
        await this.audioContext.audioWorklet.addModule(
            "/discuss/voice/worklet_processor"
        );
        const stream = new browser.MediaStream([this.clonedTrack]);
        const source = this.audioContext.createMediaStreamSource(stream);
        this.processor = new browser.AudioWorkletNode(this.audioContext, "processor");
        this.encoder = new Mp3Encoder({ bitRate: 32, sampleRate: SAMPLE_RATE });
        this.chunkStartedAt = browser.performance.now();
        this.peakRms = 0;

        this.processor.port.onmessage = (event) => this._onAudio(event);
        source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
    }

    _onAudio(event) {
        if (!this.state.recordingId || !event.data) {
            return;
        }
        this.peakRms = Math.max(this.peakRms, this._rms(event.data));
        this.encoder.encode(event.data);
        const now = browser.performance.now();
        if (now - this.chunkStartedAt >= CHUNK_MS) {
            this._flushChunk(now);
        }
    }

    _rms(samples) {
        let total = 0;
        for (let i = 0; i < samples.length; i++) {
            total += samples[i] * samples[i];
        }
        return Math.sqrt(total / (samples.length || 1));
    }

    _flushChunk(now) {
        const buffer = this.encoder.finish();
        const durationMs = Math.round(now - this.chunkStartedAt);
        const offsetMs = computeOffsetMs({
            elapsedAtJoinMs: this.elapsedAtJoinMs,
            recorderStartedAt: this.recorderStartedAt,
            now: this.chunkStartedAt,
        });
        const upload = shouldUpload(this.sourceTrack, this.peakRms);

        // Lùi mốc bắt đầu chunk kế tiếp để hai chunk chồng nhau OVERLAP_MS.
        this.chunkStartedAt = now - OVERLAP_MS;
        this.peakRms = 0;
        this.encoder = new Mp3Encoder({ bitRate: 32, sampleRate: SAMPLE_RATE });

        if (!upload || !buffer || !buffer.length) {
            return;
        }
        const blob = new Blob(buffer, { type: "audio/mpeg" });
        this._send({ blob, seq: this.seq++, offsetMs, durationMs });
    }

    async _send(chunk) {
        const form = new FormData();
        form.append("recording_id", this.state.recordingId);
        form.append("seq", chunk.seq);
        form.append("offset_ms", chunk.offsetMs);
        form.append("duration_ms", chunk.durationMs);
        form.append("audio", chunk.blob, `chunk-${chunk.seq}.mp3`);
        try {
            const response = await browser.fetch("/aidt_meeting/chunk", {
                method: "POST",
                body: form,
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch {
            // Buffer có trần: giữ vô hạn sẽ ăn hết RAM của tab trong một cuộc
            // họp dài khi mạng hỏng lâu. Bỏ mẩu cũ nhất và để server đánh dấu
            // khoảng khuyết — thà thiếu một đoạn còn hơn sập cả tab.
            this.pending.push(chunk);
            while (this.pending.length > MAX_BUFFERED_CHUNKS) {
                this.pending.shift();
            }
        }
    }

    _flushPending() {
        const queued = this.pending.splice(0, this.pending.length);
        for (const chunk of queued) {
            this._send(chunk);
        }
    }

    stop() {
        if (!this.state.recordingId) {
            return;
        }
        if (this.encoder) {
            this._flushChunk(browser.performance.now());
        }
        this._flushPending();
        this._teardownGraph();
        this.state.recordingId = null;
    }

    decline() {
        this.state.declined = true;
        this.stop();
    }

    _teardownGraph() {
        this.processor?.disconnect();
        this.clonedTrack?.stop();
        this.audioContext?.close();
        this.processor = null;
        this.clonedTrack = null;
        this.audioContext = null;
        this.encoder = null;
    }
}

export const meetingRecorderService = {
    dependencies: ["discuss.rtc", "bus_service", "notification"],
    start(env, services) {
        return new MeetingRecorder(env, services);
    },
};

registry.category("services").add("aidt_meeting.recorder", meetingRecorderService);
```

Create `static/src/rtc_service_patch.js`:

```javascript
import { patch } from "@web/core/utils/patch";
import { Rtc } from "@mail/discuss/call/common/rtc_service";

/**
 * Micro bị thay track khi người dùng đổi thiết bị hoặc cấp lại quyền. Nếu
 * recorder vẫn giữ clone của track cũ thì nó ghi tiếp một nguồn đã chết và
 * phần còn lại của cuộc họp mất tiếng mà không có lỗi nào lộ ra.
 */
patch(Rtc.prototype, {
    async resetMicAudioTrack(...args) {
        const result = await super.resetMicAudioTrack(...args);
        const recorder = this.env.services["aidt_meeting.recorder"];
        if (recorder?.state.recordingId) {
            await recorder._attachToMic();
        }
        return result;
    },
});
```

Add to `__manifest__.py`:

```python
    'assets': {
        'web.assets_backend': [
            'aidt_meeting_minutes/static/src/recorder_service.js',
            'aidt_meeting_minutes/static/src/rtc_service_patch.js',
            'aidt_meeting_minutes/static/src/recording_banner.js',
            'aidt_meeting_minutes/static/src/recording_banner.xml',
            'aidt_meeting_minutes/static/src/recording_banner.scss',
        ],
        'web.assets_unit_tests': [
            'aidt_meeting_minutes/static/tests/**/*',
        ],
    },
```

(The banner files land in Task 10; add all five entries now and create the banner files in the next task so the asset bundle is declared once.)

- [ ] **Step 4: Run tests to verify they pass**

Run the module upgrade, then open `http://localhost:8069/web/tests?module=aidt_meeting_minutes`.
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): client recorder capturing own mic clone at 16kHz"
```

---

### Task 10: Consent banner

**Files:**
- Create: `static/src/recording_banner.js`, `recording_banner.xml`, `recording_banner.scss`
- Test: `static/tests/banner.test.js`

**Interfaces:**
- Consumes: `aidt_meeting.recorder` service (Task 9), `action_stop` / `_decline` (Task 2).
- Produces: `RecordingBanner` component registered into the call UI.

- [ ] **Step 1: Write the failing test**

Create `static/tests/banner.test.js`:

```javascript
import { describe, expect, test } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";

describe.current.tags("headless");

describe("recording banner", () => {
    test("không hiện khi không ghi âm", async () => {
        await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: null } } },
        });
        expect(".o-aidt-recording-banner").toHaveCount(0);
    });

    test("hiện banner và cả hai nút khi đang ghi âm", async () => {
        // Banner là CƠ CHẾ THỰC THI của giả định "người dùng tự tắt khi nội
        // dung là Mật", không phải chi tiết giao diện — nên nó không được ẩn
        // và nút dừng phải luôn có mặt.
        await mountWithCleanup(RecordingBanner, {
            props: { recorder: { state: { recordingId: 7 } } },
        });
        expect(".o-aidt-recording-banner").toHaveCount(1);
        expect("button[name='decline']").toHaveCount(1);
        expect("button[name='stop']").toHaveCount(1);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Open `http://localhost:8069/web/tests?module=aidt_meeting_minutes`.
Expected: FAIL — `@aidt_meeting_minutes/recording_banner` not found.

- [ ] **Step 3: Write the implementation**

Create `static/src/recording_banner.js`:

```javascript
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class RecordingBanner extends Component {
    static template = "aidt_meeting_minutes.RecordingBanner";
    static props = { recorder: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.recorder =
            this.props.recorder || useService("aidt_meeting.recorder");
        this.state = useState(this.recorder.state);
    }

    get label() {
        return _t("Cuộc họp đang được ghi âm để tạo biên bản.");
    }

    async onDecline() {
        // Chỉ dừng upload của MÌNH; bản ghi của người khác vẫn tiếp tục.
        this.recorder.decline();
        await this.orm.call(
            "aidt.meeting.recording",
            "_decline",
            [[this.state.recordingId]],
            {}
        );
    }

    async onStop() {
        // Bất kỳ người tham gia nào cũng dừng được toàn bộ bản ghi — xem
        // giả định ở §4 của spec.
        await this.orm.call(
            "aidt.meeting.recording",
            "action_stop",
            [[this.state.recordingId]],
            {}
        );
    }
}

// Mount vào đầu template cuộc gọi, đúng chỗ `PttAdBanner` đã đứng sẵn
// (addons/mail/static/src/discuss/call/common/call.xml:5). KHÔNG có registry
// "discuss.call/banners" trong Odoo 19 — đã kiểm chứng bằng grep; cách duy
// nhất là khai báo component rồi mở rộng template.
Call.components = { ...Call.components, RecordingBanner };
```

Create `static/src/call_patch.js`:

```javascript
import { Call } from "@mail/discuss/call/common/call";
import { RecordingBanner } from "@aidt_meeting_minutes/recording_banner";

Call.components = { ...Call.components, RecordingBanner };
```

Remove the `Call.components` line from `recording_banner.js` and drop its `Call` import — keeping the wiring in `call_patch.js` avoids a circular import between the component and the patch.

Create `static/src/recording_banner.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <!-- Chèn ngay sau PttAdBanner, đầu template cuộc gọi. -->
    <t t-name="aidt_meeting_minutes.CallBanner"
       t-inherit="discuss.Call" t-inherit-mode="extension">
        <xpath expr="//PttAdBanner" position="after">
            <RecordingBanner/>
        </xpath>
    </t>

    <t t-name="aidt_meeting_minutes.RecordingBanner">
        <div t-if="state.recordingId" class="o-aidt-recording-banner">
            <span class="o-aidt-recording-dot"/>
            <span t-esc="label"/>
            <button name="decline" class="btn btn-sm btn-secondary"
                    t-on-click="onDecline">Từ chối</button>
            <button name="stop" class="btn btn-sm btn-danger"
                    t-on-click="onStop">Dừng ghi âm</button>
        </div>
    </t>
</templates>
```

Create `static/src/recording_banner.scss`:

```scss
// Không thu gọn được, không ẩn được: banner là cơ chế thực thi chứ không
// phải trang trí.
.o-aidt-recording-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    background-color: #7a1620;
    color: #fff;
    font-size: 0.875rem;

    .o-aidt-recording-dot {
        width: 0.6rem;
        height: 0.6rem;
        border-radius: 50%;
        background-color: #ff4d4d;
    }

    button {
        margin-left: auto;
    }

    button + button {
        margin-left: 0.5rem;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Open `http://localhost:8069/web/tests?module=aidt_meeting_minutes`.
Expected: PASS, 2 tests.

Also add `'aidt_meeting_minutes/static/src/call_patch.js',` to the `web.assets_backend` list in `__manifest__.py`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes
git commit -m "feat(meeting): always-visible consent banner with decline and stop"
```

---

### Task 11: AI tier compose file

**Files:**
- Create: `docker-compose.ai.yml`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: nothing in code.
- Produces: services `aidt-asr` (port 8002) and `aidt-llm` (port 8003) on the shared network `aidt-ai-net`, matching the config defaults from Task 1.

- [ ] **Step 1: Create the shared network and attach the web stack**

Add to the end of `docker-compose.yml`:

```yaml
# Tầng AI nằm ở docker-compose.ai.yml riêng để thay được bằng dịch vụ bên
# thứ ba bất cứ lúc nào. Hai compose project khác nhau KHÔNG nói chuyện được
# qua default bridge, nên bắt buộc phải có một network đặt tên chung.
networks:
  aidt-ai-net:
    external: true
    name: aidt-ai-net
```

Add `networks: [default, aidt-ai-net]` to the `odoo` service in `docker-compose.yml`.

- [ ] **Step 2: Create `docker-compose.ai.yml`**

```yaml
# Tầng AI: embedding, bóc băng, tóm tắt. Tách khỏi docker-compose.yml để
# migrate sang dịch vụ bên thứ ba mà không đụng tới tầng web.
#
#   docker network create aidt-ai-net    # chạy một lần
#   docker compose -f docker-compose.ai.yml up -d
name: aidt-ai

services:
  aidt-embed:
    image: vllm/vllm-openai:latest
    command:
      - --model=AITeamVN/Vietnamese_Embedding
      - --served-model-name=AITeamVN/Vietnamese_Embedding
      - --runner=pooling
      - --convert=embed
      # GHIM TƯỜNG MINH. vLLM cấp phát trước KV cache theo tỉ lệ này; để mặc
      # định thì ba service sẽ tranh nhau và OOM ngay lúc khởi động. Card là
      # 16 GB, ba service chia nhau ~13.5 GB.
      - --gpu-memory-utilization=0.15
      - --max-model-len=2048
      - --host=0.0.0.0
      - --port=8001
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8001"
    ipc: host
    networks: [aidt-ai-net]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8001/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 20

  aidt-asr:
    image: vllm/vllm-openai:latest
    command:
      - --model=vinai/PhoWhisper-large
      - --served-model-name=vinai/PhoWhisper-large
      # Cửa sổ gốc của kiến trúc Whisper là 30 giây; chunk 15 giây của client
      # đi trọn một lượt forward, không cần ghép long-form bên trong model.
      - --gpu-memory-utilization=0.25
      - --host=0.0.0.0
      - --port=8002
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8002:8002"
    ipc: host
    networks: [aidt-ai-net]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8002/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 40

  aidt-llm:
    # CHƯA XÁC NHẬN: 'gemma4:12b' là cú pháp tag của Ollama, không phải
    # đường dẫn --model của vLLM. Nếu bộ tóm tắt chạy bằng Ollama thì đổi
    # image sang ollama/ollama và giữ nguyên cổng 8003 — adapter không đổi
    # vì cả hai đều phục vụ /v1/chat/completions tương thích OpenAI.
    image: vllm/vllm-openai:latest
    command:
      - --model=google/gemma-3-12b-it
      - --quantization=bitsandbytes
      - --gpu-memory-utilization=0.45
      # Cửa sổ ngắn có chủ đích: map-reduce ở tầng ứng dụng đã chia nhỏ đầu
      # vào, nên KV cache không cần lớn — và không có chỗ cho nó lớn.
      - --max-model-len=8192
      - --host=0.0.0.0
      - --port=8003
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8003:8003"
    ipc: host
    networks: [aidt-ai-net]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8003/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 60

networks:
  aidt-ai-net:
    external: true
    name: aidt-ai-net
```

- [ ] **Step 3: Verify the three services co-exist on the GPU**

```bash
docker network create aidt-ai-net || true
docker compose -f docker-compose.ai.yml up -d
sleep 180
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
docker compose -f docker-compose.ai.yml ps
```

Expected: all three `healthy`, total VRAM used under 16 GiB.

**If any service OOMs**, that is the expected failure mode and the budget is too tight — lower `--gpu-memory-utilization` on `aidt-llm` first, then reduce `--max-model-len`. Record whatever values actually work; do not leave the untested numbers in the file.

- [ ] **Step 4: Verify Odoo can reach the services**

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  python3 -c "import urllib.request; print(urllib.request.urlopen('http://aidt-asr:8002/health', timeout=5).status)"
```
Expected: `200`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.ai.yml docker-compose.yml
git commit -m "chore(ai): split AI tier into docker-compose.ai.yml on a shared network"
```

---

### Task 12: End-to-end verification and documentation

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/README.md`
- Modify: `docs/GUIDANCE.md`

**Interfaces:**
- Consumes: everything.
- Produces: user and technical documentation.

- [ ] **Step 1: Run the full automated suite**

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aidt_demo --test-enable --stop-after-init -u aidt_meeting_minutes
```
Expected: 0 failed, 0 error. Then open `http://localhost:8069/web/tests?module=aidt_meeting_minutes` and confirm the JS tests pass.

- [ ] **Step 2: Manual two-browser end-to-end run**

This cannot be automated — real `getUserMedia`, real WebRTC, and real ASR accuracy all require a live run.

1. Open `http://localhost:8069` in two different browsers (or one plus a private window), logged in as two users.
2. Create a `calendar.event` with both as attendees and a Discuss videocall link.
3. Join the call from both, speak Vietnamese for ~90 seconds each, taking turns and overlapping once.
4. Mute one participant for ~20 seconds mid-call.
5. Stop the recording from the **non-organizer's** banner.
6. Wait ~2 minutes, then check the event chatter.

Record the actual results:

- [ ] Banner appeared for both participants
- [ ] Non-organizer could stop the recording
- [ ] Transcript is speaker-attributed and in the right order
- [ ] Muted stretch produced no invented text
- [ ] No repeated words at the 15 s chunk seams
- [ ] Summary appeared, in Vietnamese
- [ ] Audio attachments were deleted afterwards (`aidt.meeting.chunk.attachment_id` is empty)
- [ ] Subjective ASR accuracy on Vietnamese meeting speech: ____

- [ ] **Step 3: Write the module README**

Create `custom-addons/aidt_meeting_minutes/README.md` covering: architecture (per-client mic capture and why, over the two rejected alternatives), the chunk protocol (fields, offset arithmetic, overlap and seam dedup), the ASR/LLM configuration keys and how to point them at third-party services, the GPU budget with the values that actually worked in Task 11, and the security model (partner derived from session, channel-based record rules).

- [ ] **Step 4: Write the end-user guidance**

Add a numbered section plus an index row to `docs/GUIDANCE.md`, in Vietnamese.

**Verify every string against the shipped files before writing it down** — `recording_banner.xml` for the banner text and button labels, `meeting_recording_views.xml` for the menu path and field labels, `res_config_settings_views.xml` for the settings page. Never from memory, and never from this plan or the spec: both describe intent, which drifts from what ships.

The section must cover: who can start recording (organizer for scheduled meetings, any member for ad-hoc calls), that anyone can stop it, what Từ chối does versus Dừng ghi âm (they look similar and mean different things — this deserves its own paragraph), where the transcript appears for each call type, what `[thiếu âm thanh …]` means, and that audio is deleted by default while the transcript is kept.

**Mark the feature as unverified with an explicit warning** unless Step 2 was completed with good results, and record the observed ASR accuracy rather than claiming any figure.

- [ ] **Step 5: Verify the database is clean and commit**

```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d postgres -c "\l"
docker exec aidt-odoo-dev-odoo-1 ls /var/lib/odoo/filestore/
```
Expected: only `aidt_demo` besides the Postgres system databases. Drop any scratch database and `rm -rf` its filestore directory.

```bash
git add custom-addons/aidt_meeting_minutes/README.md docs/GUIDANCE.md
git commit -m "docs(meeting): user guidance and module README"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| §3 per-client mic capture | 9 |
| §4 scope: scheduled + ad-hoc, secrecy ceiling, org/member start | 2 |
| §4 Mật assumption → always-visible banner, anyone can stop | 2, 10 |
| §5 clone track, 16 kHz, mute gate, RMS floor, 15 s + 1.5 s overlap, offset arithmetic, sendBeacon-style flush, consent | 9, 10 |
| §6 four models, snapshot secrecy, unique seq, retention default 0, channel-based rules | 1, 2, 3, 5, 8 |
| §7 upload endpoint, partner from session, cron queue, end detection, finalize | 3, 5, 7 |
| §8 ASR retry/failed + gap markers, LLM isolation, silence, map-reduce, declined | 5, 6, 8 |
| §9 PhoWhisper, QAT LLM, compose split, external network, API keys, pinned VRAM | 1, 4, 8, 11 |
| §10 all listed tests | 2, 3, 4, 5, 6, 7, 8, 9, 10, 12 |
| §11 GUIDANCE.md + README | 12 |

**Known gaps, deliberately deferred:**

- **`sendBeacon` on tab close is not implemented in Task 9.** `_flushChunk` runs on stop, but a hard tab close loses the final in-flight chunk. The spec calls for `sendBeacon`; `FormData` with a `Blob` is compatible with it. Add this in Task 9 Step 3 if the manual run in Task 12 shows lost tail audio — it needs a real browser to verify, so a test-first approach cannot drive it.
**Verified while writing this plan (no longer assumptions):**

- `discuss.channel` inherits `bus.listener.mixin` (`addons/mail/models/discuss/discuss_channel.py:55`), so `channel._bus_send(...)` in Task 2 is valid.
- There is **no** `discuss.call/banners` registry in Odoo 19. Task 10 mounts the banner by extending the `discuss.Call` template after `<PttAdBanner/>` (`addons/mail/static/src/discuss/call/common/call.xml:5`), which is the in-tree precedent for exactly this.
- `Mp3Encoder` is a named export of `@mail/discuss/voice_message/common/mp3_encoder`, and `Rtc` is a named export of `@mail/discuss/call/common/rtc_service` — both imports in Tasks 9 and 10 resolve.
- **`models.Constraint` with `EXCLUDE`** (Task 2) requires the `btree_gist` extension only for mixed-type exclusions; a plain equality exclusion on one integer column does not. If Postgres rejects it, replace with the partial unique index idiom from `aidt_search/models/index_job.py::init`.

**Type consistency:** `_transcribe` returns `start_ms`/`end_ms`/`text` (Task 4) and is consumed with exactly those keys in `_write_segments` (Task 5). `end_ms=None` is produced in Task 4 and handled in Task 5. `computeOffsetMs`/`shouldUpload` are exported in Task 9 and imported by name in its test. `_is_participant`, `_post_target`, `_config`, and `_broadcast_state` are defined in Task 2 and used in Tasks 3, 7, and 8.
