# Ghi âm cuộc họp do chủ phòng điều khiển — Kế hoạch thực thi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển quyền điều khiển ghi âm về một chủ phòng duy nhất, buộc mọi người dự thấy thông báo đang ghi âm, và cho phép tạm dừng rồi ghi tiếp trong cùng một bản ghi với mốc dừng được đưa tới AI.

**Architecture:** Chủ phòng được chốt tại thời điểm cuộc gọi bắt đầu và lưu trên `discuss.channel`. Bản ghi thêm trạng thái `paused` và một bảng con `aidt.meeting.pause` ghi từng khoảng dừng. Mỗi lần ghi tiếp tăng `take`; client đánh số `seq` lại từ 0 nhưng giữ nguyên trục thời gian, nên worker ghép audio theo từng cặp `(người, take)` thay vì theo từng người.

**Tech Stack:** Odoo 19 (Python 3.12, OWL 2, hoot), PostgreSQL 16, FastAPI + faster-whisper trong `docker/ai_worker`, pytest cho worker.

**Spec:** [`docs/superpowers/specs/2026-08-10-meeting-recording-host-control-design.md`](../specs/2026-08-10-meeting-recording-host-control-design.md)

## Global Constraints

- Module `aidt_meeting_minutes`: `19.0.1.2.1` → **`19.0.1.3.0`**. Chỉ bump ở Task 12.
- Mọi chuỗi hiển thị cho người dùng viết bằng **tiếng Việt**. Comment trong `custom-addons/` cũng tiếng Việt.
- Cơ sở dữ liệu dev duy nhất là **`aidt_demo`**. Không tạo database mới. Database test tạm phải drop kèm filestore khi xong.
- Lệnh chạy test Odoo:
  `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes --test-enable --test-tags '/aidt_meeting_minutes:<TestClass>' --stop-after-init --http-port=8079`
- Lệnh chạy test worker:
  `docker exec aidt-odoo-dev-odoo-1 bash -lc 'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 -m pytest docker/ai_worker/<file> -q'`
- Sau khi sửa `docker/ai_worker/*.py`: `docker compose -f docker-compose.ai.yml restart ai-worker` (mất ~1 phút nạp lại `large-v3`).
- Sau khi sửa `.py` trong `custom-addons/`: restart container Odoo. `--dev=reload` **không** đáng tin ở môi trường này.
- Không đụng tới hai lỗ hổng đã biết (`webhook/summary` không xác thực, `/aidt_meeting/audio/<id>` public) — thuộc đợt khác.

---

## File Structure

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `custom-addons/aidt_meeting_minutes/models/discuss_channel.py` | Trường `aidt_call_host_partner_id` trên kênh |
| `custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py` | Hai móc `create`/`unlink`: chốt chủ phòng, kết thúc bản ghi khi cuộc gọi trống |
| `custom-addons/aidt_meeting_minutes/models/meeting_pause.py` | Model `aidt.meeting.pause` |
| `custom-addons/aidt_meeting_minutes/tests/test_host_control.py` | Phân quyền chủ phòng, kết thúc, người rời cuộc gọi |
| `custom-addons/aidt_meeting_minutes/tests/test_pause.py` | Tạm dừng / ghi tiếp / `take` |
| `custom-addons/aidt_meeting_minutes/migrations/19.0.1.3.0/pre-migration.py` | Bốn thao tác DDL |
| `docker/ai_worker/test_takes.py` | Ghép theo take, cắt tại mốc dừng, mốc trong transcript |

**Sửa**

| File | Sửa gì |
|---|---|
| `models/meeting_recording.py` | `host_partner_id`, `current_take`, `pause_ids`, `pause_summary`, state `paused`, `_is_host`, `action_pause/resume`, `action_stop` siết quyền, `_end_recording`, `action_active_recording`, `_broadcast_state`, gỡ `declined_partner_ids`/`_decline`/`action_decline` |
| `models/meeting_chunk.py` | Trường `take`, khoá duy nhất mới, `_store` nhận `take` |
| `models/__init__.py` | Import ba model mới |
| `controllers/main.py` | `upload_chunk` nhận `take`; gỡ `finalize_recording` |
| `static/src/recorder_service.js` | `take`, `pause()`, `resume()`, bỏ `fetch` finalize |
| `static/src/recording_banner.js` + `.xml` | Hai vai × ba trạng thái, gỡ nút Từ chối và Mock Audio |
| `views/meeting_recording_views.xml` | Bỏ `declined_partner_ids`, thêm mục đoạn dừng |
| `security/ir.model.access.csv` | Hai dòng cho `aidt.meeting.pause` |
| `docker/ai_worker/main.py` | `_load_speakers` hai tầng, ghép theo take, cắt tại `paused_at_ms`, mốc dừng, `SYSTEM_PROMPT` |
| `__manifest__.py` | Bump `19.0.1.3.0` (Task 12) |

---

## Task 1: Chủ phòng trên kênh

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/discuss_channel.py`
- Create: `custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py`
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_host_control.py`

**Interfaces:**
- Produces: `discuss.channel.aidt_call_host_partner_id` (Many2one `res.partner`). Được đặt khi phiên RTC **đầu tiên** trên kênh được tạo, và xoá khi phiên **cuối cùng** bị xoá.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_host_control.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCallHost(TransactionCase):
    """Chủ phòng được chốt lúc cuộc gọi bắt đầu.

    Odoo không có khái niệm chủ phòng cho cuộc gọi. Suy ra sau bằng cách tìm
    phiên RTC sớm nhất là không đáng tin: phiên bị xoá rồi tạo lại mỗi lần
    người ta rớt mạng và vào lại, nên "sớm nhất" đổi theo thời gian.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thử chủ phòng',
            'channel_type': 'channel',
        })
        cls.user_a = cls.env['res.users'].create({
            'name': 'Người A', 'login': 'host_a@test.local'})
        cls.user_b = cls.env['res.users'].create({
            'name': 'Người B', 'login': 'host_b@test.local'})
        cls.channel.add_members(
            partner_ids=[cls.user_a.partner_id.id, cls.user_b.partner_id.id])

    def _member(self, user):
        return self.env['discuss.channel.member'].search([
            ('channel_id', '=', self.channel.id),
            ('partner_id', '=', user.partner_id.id),
        ], limit=1)

    def _join(self, user):
        return self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': self._member(user).id,
        })

    def test_nguoi_vao_dau_tien_thanh_chu_phong(self):
        self._join(self.user_a)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_nguoi_vao_sau_khong_doi_chu_phong(self):
        self._join(self.user_a)
        self._join(self.user_b)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_chu_phong_roi_nhung_con_nguoi_khac_thi_giu_nguyen(self):
        """Rớt mạng vài giây rồi vào lại là chuyện thường. Đổi chủ phòng
        theo mỗi lần đó thì quyền điều khiển nhảy loạn giữa cuộc họp."""
        session_a = self._join(self.user_a)
        self._join(self.user_b)
        session_a.unlink()
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_cuoc_goi_trong_thi_xoa_chu_phong(self):
        session_a = self._join(self.user_a)
        session_a.unlink()
        self.assertFalse(self.channel.aidt_call_host_partner_id)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestCallHost'`
Expected: FAIL — `Invalid field 'aidt_call_host_partner_id' on model 'discuss.channel'`

- [ ] **Step 3: Thêm trường trên kênh**

Tạo `models/discuss_channel.py`:

```python
from odoo import fields, models


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # Chủ phòng của CUỘC GỌI đang diễn ra trên kênh này, chốt lúc cuộc gọi
    # bắt đầu (xem discuss_channel_rtc_session.py). Odoo không có khái niệm
    # này sẵn: kênh có `create_uid` nhưng người tạo kênh "general" từ một năm
    # trước không phải người chủ trì cuộc họp hôm nay và có thể không có mặt.
    #
    # Rỗng khi không có cuộc gọi nào đang chạy.
    aidt_call_host_partner_id = fields.Many2one(
        'res.partner', string='Chủ phòng cuộc gọi', readonly=True, copy=False)
```

- [ ] **Step 4: Thêm hai móc trên phiên RTC**

Tạo `models/discuss_channel_rtc_session.py`:

```python
from odoo import api, models


class DiscussChannelRtcSession(models.Model):
    _inherit = 'discuss.channel.rtc.session'

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        # `len(c.rtc_session_ids) == 1` là ĐÚNG điều kiện Odoo dùng để nhận
        # ra "cuộc gọi vừa bắt đầu" (discuss_channel_rtc_session.py:51). Dùng
        # lại nó thay vì tự nghĩ ra một cách khác.
        for session in sessions:
            channel = session.channel_id
            if len(channel.sudo().rtc_session_ids) == 1:
                channel.sudo().aidt_call_host_partner_id = session.partner_id
        return sessions

    def unlink(self):
        # Tính TRƯỚC khi xoá, cùng cách Odoo tính `call_ended_channels`
        # (dòng 66 của file gốc): sau `super()` thì không còn gì để đối chiếu.
        ended = self.channel_id.filtered(
            lambda c: not (c.sudo().rtc_session_ids - self))
        result = super().unlink()
        ended.sudo().aidt_call_host_partner_id = False
        return result
```

- [ ] **Step 5: Đăng ký hai model**

Sửa `models/__init__.py`, thêm **lên đầu** (trước `meeting_recording`, vì
`_start_for_channel` sẽ đọc trường của kênh):

```python
from . import discuss_channel
from . import discuss_channel_rtc_session
```

- [ ] **Step 6: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestCallHost'`
Expected: PASS, 4 test

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/discuss_channel.py \
        custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py \
        custom-addons/aidt_meeting_minutes/models/__init__.py \
        custom-addons/aidt_meeting_minutes/tests/test_host_control.py
git commit -m "feat(meeting): pin call host when the call starts"
```

---

## Task 2: Chỉ chủ phòng bật được ghi âm

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:193-224` (`_start_for_channel`)
- Test: `custom-addons/aidt_meeting_minutes/tests/test_host_control.py`

**Interfaces:**
- Consumes: `discuss.channel.aidt_call_host_partner_id` (Task 1)
- Produces: `aidt.meeting.recording.host_partner_id` (Many2one `res.partner`, readonly) — bản chụp chủ phòng lúc bật ghi. `_is_host(partner)` trả bool.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_host_control.py`:

```python
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestStartPermission(TestCallHost):
    """Trước thay đổi này, nhánh "chỉ chủ trì mới bật được" chỉ chạy khi cuộc
    gọi gắn `calendar.event` — và trên aidt_demo, `event_id` rỗng ở 100% bản
    ghi. Nghĩa là nhánh đó CHƯA TỪNG chạy, mọi cuộc gọi đều rơi vào `else`
    nơi bất kỳ thành viên kênh nào cũng bật được.
    """

    def test_chu_phong_bat_duoc(self):
        self._join(self.user_a)
        recording = self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)
        self.assertEqual(recording.state, 'recording')
        self.assertEqual(recording.host_partner_id, self.user_a.partner_id)

    def test_nguoi_khong_phai_chu_phong_bi_chan(self):
        self._join(self.user_a)
        self._join(self.user_b)
        with self.assertRaises(AccessError):
            self.env['aidt.meeting.recording'].with_user(
                self.user_b)._start_for_channel(self.channel)

    def test_khong_co_cuoc_goi_thi_khong_ai_bat_duoc(self):
        """Chưa ai vào cuộc gọi thì chưa có chủ phòng."""
        with self.assertRaises(AccessError):
            self.env['aidt.meeting.recording'].with_user(
                self.user_a)._start_for_channel(self.channel)

    def test_chu_phong_la_ban_chup_khong_phai_related(self):
        """Chủ phòng của KÊNH đổi được sau đó (cuộc gọi mới, người khác vào
        trước). "Ai đã bật bản ghi này" là dữ kiện lịch sử của biên bản, phải
        đứng yên."""
        session_a = self._join(self.user_a)
        recording = self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)
        session_a.unlink()
        self._join(self.user_b)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_b.partner_id)
        self.assertEqual(recording.host_partner_id, self.user_a.partner_id)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestStartPermission'`
Expected: FAIL — `Invalid field 'host_partner_id'`

- [ ] **Step 3: Thêm trường và hàm kiểm tra**

Trong `models/meeting_recording.py`, thêm sau `secrecy_at_start` (dòng 40):

```python
    # Bản chụp, KHÔNG phải related tới `channel_id.aidt_call_host_partner_id`:
    # chủ phòng của KÊNH đổi khi có cuộc gọi mới, còn "ai đã bật bản ghi này"
    # là dữ kiện lịch sử của biên bản và phải đứng yên.
    host_partner_id = fields.Many2one(
        'res.partner', string='Chủ phòng', readonly=True, index=True)
```

Thêm hàm cạnh `_is_participant` (sau dòng 165):

```python
    def _is_host(self, partner):
        """Người này có phải chủ phòng của bản ghi này không."""
        self.ensure_one()
        return bool(partner) and partner == self.sudo().host_partner_id
```

- [ ] **Step 4: Siết `_start_for_channel`**

Thay thân hàm ở `models/meeting_recording.py:193-224` bằng:

```python
    @api.model
    def _start_for_channel(self, channel):
        """Bật ghi âm cho một kênh đang có cuộc gọi. Trả về bản ghi."""
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))

        host = channel.sudo().aidt_call_host_partner_id
        if not host:
            raise AccessError(_(
                'Chưa có cuộc gọi nào đang diễn ra trên kênh này.'))
        if host != partner:
            raise AccessError(_(
                'Chỉ chủ phòng mới bật được ghi âm.'))

        event = self._event_for_channel(channel)
        if event:
            # Cuộc họp có lịch thì người chủ trì trong lịch vẫn là tiếng nói
            # cuối cùng — chủ phòng của cuộc gọi không vượt được quyền đó.
            if event.user_id != self.env.user:
                raise AccessError(_(
                    'Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
            secrecy = event.secrecy or 'thuong'
        else:
            secrecy = 'thuong'
        self._check_secrecy_allowed(secrecy)

        existing = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'paused', 'processing')),
        ], limit=1)
        if existing:
            raise UserError(_('Cuộc gọi này đang được ghi âm rồi.'))

        recording = self.sudo().create({
            'channel_id': channel.id,
            'event_id': event.id if event else False,
            'secrecy_at_start': secrecy,
            'started_by_id': self.env.user.id,
            'host_partner_id': host.id,
            'started_at': fields.Datetime.now(),
        })
        recording._broadcast_state('started')
        return recording
```

- [ ] **Step 5: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestStartPermission,/aidt_meeting_minutes:TestCallHost'`
Expected: PASS, 8 test

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/tests/test_host_control.py
git commit -m "feat(meeting): only the call host may start recording"
```

---

## Task 3: Tạm dừng và ghi tiếp

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/meeting_pause.py`
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py` (state, `current_take`, `pause_ids`, `action_pause`, `action_resume`)
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Modify: `custom-addons/aidt_meeting_minutes/security/ir.model.access.csv`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_pause.py`

**Interfaces:**
- Consumes: `_is_host(partner)` (Task 2)
- Produces: model `aidt.meeting.pause` với `recording_id`, `paused_at_ms`, `resumed_at_ms`, `paused_by_id`. Trên recording: `current_take` (Integer, mặc định 0), `pause_ids` (One2many), `action_pause()`, `action_resume()`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_pause.py`:

```python
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPause(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thử tạm dừng', 'channel_type': 'channel'})
        cls.host = cls.env['res.users'].create({
            'name': 'Chủ phòng', 'login': 'pause_host@test.local'})
        cls.guest = cls.env['res.users'].create({
            'name': 'Người dự', 'login': 'pause_guest@test.local'})
        cls.channel.add_members(
            partner_ids=[cls.host.partner_id.id, cls.guest.partner_id.id])
        for user in (cls.host, cls.guest):
            member = cls.env['discuss.channel.member'].search([
                ('channel_id', '=', cls.channel.id),
                ('partner_id', '=', user.partner_id.id)], limit=1)
            cls.env['discuss.channel.rtc.session'].sudo().create({
                'channel_member_id': member.id})
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.host)._start_for_channel(cls.channel)

    def test_tam_dung_tao_mot_dong_va_doi_trang_thai(self):
        self.recording.with_user(self.host).action_pause()
        self.assertEqual(self.recording.state, 'paused')
        self.assertEqual(len(self.recording.pause_ids), 1)
        pause = self.recording.pause_ids
        self.assertTrue(pause.paused_at_ms > 0)
        self.assertFalse(pause.resumed_at_ms)
        self.assertEqual(pause.paused_by_id, self.host)

    def test_ghi_tiep_dien_moc_va_tang_take(self):
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        self.assertEqual(self.recording.state, 'recording')
        self.assertEqual(self.recording.current_take, 1)
        pause = self.recording.pause_ids
        self.assertTrue(pause.resumed_at_ms >= pause.paused_at_ms)

    def test_hai_lan_tam_dung_cho_hai_dong_va_take_bang_hai(self):
        for _ in range(2):
            self.recording.with_user(self.host).action_pause()
            self.recording.with_user(self.host).action_resume()
        self.assertEqual(len(self.recording.pause_ids), 2)
        self.assertEqual(self.recording.current_take, 2)

    def test_nguoi_du_khong_tam_dung_duoc(self):
        with self.assertRaises(AccessError):
            self.recording.with_user(self.guest).action_pause()

    def test_nguoi_du_khong_ghi_tiep_duoc(self):
        self.recording.with_user(self.host).action_pause()
        with self.assertRaises(AccessError):
            self.recording.with_user(self.guest).action_resume()

    def test_tam_dung_hai_lan_lien_tiep_khong_tao_dong_thua(self):
        """Bấm hai lần vì mạng chậm là chuyện thường. Lần thứ hai phải là
        no-op, không được mở một khoảng dừng thứ hai chồng lên khoảng đang mở."""
        self.recording.with_user(self.host).action_pause()
        self.assertFalse(self.recording.with_user(self.host).action_pause())
        self.assertEqual(len(self.recording.pause_ids), 1)

    def test_ghi_tiep_khi_dang_ghi_la_no_op(self):
        self.assertFalse(self.recording.with_user(self.host).action_resume())
        self.assertEqual(self.recording.current_take, 0)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestPause'`
Expected: FAIL — `'aidt.meeting.recording' object has no attribute 'action_pause'`

- [ ] **Step 3: Tạo model khoảng dừng**

Tạo `models/meeting_pause.py`:

```python
from odoo import fields, models


class AidtMeetingPause(models.Model):
    _name = 'aidt.meeting.pause'
    _description = 'Khoảng tạm dừng ghi âm'
    _order = 'paused_at_ms'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    # Cùng trục thời gian với `offset_ms` của mẩu audio: mili-giây kể từ lúc
    # bắt đầu ghi. Nhờ vậy mốc trong biên bản và mốc ở đây đọc được cạnh nhau.
    paused_at_ms = fields.Integer(string='Dừng lúc (ms)', required=True)
    # Rỗng nghĩa là chưa ghi tiếp — hoặc cuộc họp kết thúc luôn trong lúc
    # đang dừng. Không được điền một giá trị đoán: ta biết lúc dừng, không
    # biết cuộc họp còn kéo dài bao lâu sau đó.
    resumed_at_ms = fields.Integer(string='Ghi tiếp lúc (ms)')
    paused_by_id = fields.Many2one(
        'res.users', string='Người bấm dừng', readonly=True)
```

- [ ] **Step 4: Đăng ký model và quyền**

Thêm vào `models/__init__.py` sau `meeting_recording`:

```python
from . import meeting_pause
```

Thêm hai dòng vào `security/ir.model.access.csv`:

```csv
access_meeting_pause_user,aidt.meeting.pause.user,model_aidt_meeting_pause,base.group_user,1,0,0,0
access_meeting_pause_manager,aidt.meeting.pause.manager,model_aidt_meeting_pause,aidt_meeting_minutes.group_meeting_minutes_manager,1,1,1,1
```

- [ ] **Step 5: Thêm trạng thái, trường và hai hành động**

Trong `models/meeting_recording.py`, đổi `state` (dòng 26-29) thành:

```python
    state = fields.Selection(
        [('recording', 'Đang ghi'), ('paused', 'Tạm dừng'),
         ('processing', 'Đang xử lý'), ('done', 'Xong'),
         ('failed', 'Lỗi'), ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='recording', required=True, index=True)
```

Thêm cạnh `host_partner_id`:

```python
    # Lần ghi hiện tại. Tăng 1 mỗi lần ghi tiếp. Client đánh `seq` lại từ 0
    # cho mỗi take, nên `take` là thứ phân biệt hai mẩu cùng `seq`.
    current_take = fields.Integer(
        string='Lần ghi hiện tại', default=0, readonly=True)
    pause_ids = fields.One2many(
        'aidt.meeting.pause', 'recording_id', string='Các đoạn tạm dừng')
```

Thêm hai hành động sau `action_start_for_channel` (sau dòng 233):

```python
    def action_pause(self):
        """Tạm dừng THU BIÊN BẢN. Cuộc gọi không bị đụng tới.

        Người tham gia vẫn nghe và nói với nhau bình thường — chỉ luồng
        `getUserMedia` riêng của bộ ghi âm bị đóng lại, không phải track
        WebRTC của cuộc gọi.
        """
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới tạm dừng được ghi âm.'))
        if self.state != 'recording':
            # Bấm hai lần vì mạng chậm là chuyện thường; lần sau phải là
            # no-op chứ không mở thêm một khoảng dừng chồng lên khoảng đang mở.
            return False

        self.env['aidt.meeting.pause'].sudo().create({
            'recording_id': self.id,
            'paused_at_ms': self._elapsed_ms(),
            'paused_by_id': self.env.user.id,
        })
        self.sudo().write({'state': 'paused'})
        self._broadcast_state('paused')
        return True

    def action_resume(self):
        """Ghi tiếp sau khi tạm dừng. Tăng `take`."""
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới ghi tiếp được.'))
        if self.state != 'paused':
            return False

        open_pause = self.sudo().pause_ids.filtered(
            lambda p: not p.resumed_at_ms)[-1:]
        if open_pause:
            open_pause.write({'resumed_at_ms': self._elapsed_ms()})
        self.sudo().write({
            'state': 'recording',
            'current_take': self.current_take + 1,
        })
        self._broadcast_state('resumed')
        return True
```

- [ ] **Step 6: Cho phép `_broadcast_state` mang `take`**

Thay `_broadcast_state` (cuối file) bằng:

```python
    def _broadcast_state(self, action):
        """Báo cho mọi client trong kênh để chúng bật/tắt thu âm.

        Bus phát MỘT payload chung cho mọi người — không cá nhân hoá được —
        nên payload mang `host_partner_id` để mỗi client tự so với partner
        của chính mình mà chọn dạng băng thông báo.
        """
        self.ensure_one()
        elapsed = self._elapsed_ms()
        if action == 'started':
            self._register_participants()
        self.channel_id._bus_send('aidt_meeting_minutes/recording_state', {
            'action': action,
            'recording_id': self.id,
            'channel_id': self.channel_id.id,
            'elapsed_ms': elapsed,
            'state': self.state,
            'take': self.current_take,
            'host_partner_id': self.sudo().host_partner_id.id,
        })
```

- [ ] **Step 7: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestPause'`
Expected: PASS, 7 test

- [ ] **Step 8: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_pause.py \
        custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/models/__init__.py \
        custom-addons/aidt_meeting_minutes/security/ir.model.access.csv \
        custom-addons/aidt_meeting_minutes/tests/test_pause.py
git commit -m "feat(meeting): host can pause and resume within one recording"
```

---

## Task 4: Kết thúc — chỉ chủ phòng, hoặc cuộc gọi trống

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:235-267` (`action_stop`), gỡ `_decline`/`action_decline`/`declined_partner_ids`
- Modify: `custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py`
- Modify: `custom-addons/aidt_meeting_minutes/controllers/main.py` (gỡ `finalize_recording`)
- Test: `custom-addons/aidt_meeting_minutes/tests/test_host_control.py`

**Interfaces:**
- Produces: `_end_recording()` — hàm nội bộ, **không** kiểm tra quyền, dùng chung cho hai đường kết thúc. `action_stop()` giữ nguyên tên, kiểm tra chủ phòng rồi gọi `_end_recording()`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_host_control.py`:

```python
@tagged('post_install', '-at_install')
class TestEndRecording(TestCallHost):
    def _start(self):
        self._join(self.user_a)
        self._join(self.user_b)
        return self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)

    def test_chu_phong_ket_thuc_duoc(self):
        recording = self._start()
        self.assertTrue(recording.with_user(self.user_a).action_stop())
        self.assertEqual(recording.state, 'processing')

    def test_nguoi_du_khong_ket_thuc_duoc(self):
        recording = self._start()
        with self.assertRaises(AccessError):
            recording.with_user(self.user_b).action_stop()
        self.assertEqual(recording.state, 'recording')

    def test_nguoi_du_roi_cuoc_goi_thi_ban_ghi_VAN_chay(self):
        """Khiếm khuyết đang có hôm nay: rời cuộc gọi -> clear() ->
        leaveCall() -> stop() -> POST finalize_recording -> action_stop()
        cho TOÀN BỘ bản ghi. Người vô tình đóng tab ở phút thứ 5 làm cả cuộc
        họp mất phần còn lại của biên bản."""
        recording = self._start()
        member_b = self._member(self.user_b)
        self.env['discuss.channel.rtc.session'].sudo().search(
            [('channel_member_id', '=', member_b.id)]).unlink()
        self.assertEqual(recording.state, 'recording')

    def test_cuoc_goi_trong_thi_tu_ket_thuc(self):
        recording = self._start()
        self.env['discuss.channel.rtc.session'].sudo().search(
            [('channel_id', '=', self.channel.id)]).unlink()
        self.assertEqual(recording.state, 'processing')

    def test_dang_tam_dung_van_ket_thuc_duoc(self):
        """Không bắt chủ phòng phải ghi tiếp rồi mới dừng được."""
        recording = self._start()
        recording.with_user(self.user_a).action_pause()
        self.assertTrue(recording.with_user(self.user_a).action_stop())
        self.assertEqual(recording.state, 'processing')

    def test_ket_thuc_luc_dang_dung_thi_khong_dien_moc_ghi_tiep(self):
        recording = self._start()
        recording.with_user(self.user_a).action_pause()
        recording.with_user(self.user_a).action_stop()
        self.assertFalse(recording.pause_ids.resumed_at_ms)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestEndRecording'`
Expected: FAIL — `test_nguoi_du_khong_ket_thuc_duoc` không ném `AccessError`; `test_cuoc_goi_trong_thi_tu_ket_thuc` vẫn ở `recording`

- [ ] **Step 3: Tách `_end_recording` và siết `action_stop`**

Thay `models/meeting_recording.py:235-267` bằng:

```python
    def _end_recording(self):
        """Kết thúc bản ghi. KHÔNG kiểm tra quyền — hai đường gọi tới đây đã
        tự kiểm: `action_stop` (chủ phòng bấm) và móc `unlink` của phiên RTC
        (cuộc gọi trống). Tách ra để hai đường không lệch hành vi.

        Bản ghi đang `paused` cũng kết thúc được: không bắt chủ phòng phải
        ghi tiếp rồi mới dừng được. Khoảng dừng đang mở giữ nguyên
        `resumed_at_ms` rỗng — ta biết lúc dừng, không biết cuộc họp còn kéo
        dài bao lâu sau đó.
        """
        self.ensure_one()
        if self.state not in ('recording', 'paused'):
            return False

        self.sudo().write({
            'state': 'processing', 'ended_at': fields.Datetime.now(),
        })
        self._broadcast_state('stopped')

        # Đợi mẩu cuối của mọi máy tới nơi rồi mới đẩy job. 10 giây là con số
        # ước lượng, không phải kết quả đo — máy có mạng chậm hơn thế vẫn mất
        # đoạn kết.
        import threading
        registry = self.env.registry

        def trigger_later(reg, recording_id):
            import time
            import logging
            from odoo import api, SUPERUSER_ID
            time.sleep(10)
            try:
                with reg.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    rec = env['aidt.meeting.recording'].browse(recording_id)
                    if rec.exists() and rec.state == 'processing':
                        rec._trigger_ai_service()
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Error in delayed AI trigger for {recording_id}: {e}")

        threading.Thread(target=trigger_later, args=(registry, self.id)).start()
        return True

    def action_stop(self):
        """Kết thúc ghi âm. CHỈ chủ phòng.

        Trước đây bất kỳ người tham gia nào cũng gọi được, và điều đó kết
        hợp với `finalize_recording` làm một người rời cuộc gọi kết thúc cả
        bản ghi của mọi người.
        """
        self.ensure_one()
        if not self._is_host(self.env.user.partner_id):
            raise AccessError(_('Chỉ chủ phòng mới kết thúc được ghi âm.'))
        return self._end_recording()
```

- [ ] **Step 4: Gỡ cơ chế từ chối — model VÀ view cùng một lượt**

Trong `models/meeting_recording.py`: xoá trường `declined_partner_ids`
(dòng 42-43) và hai hàm `_decline` / `action_decline` (dòng 357-368).

**Cùng bước này** phải xoá dòng tham chiếu trong
`views/meeting_recording_views.xml:63`:

```xml
                                    <field name="declined_partner_ids" widget="many2many_tags"/>
```

> Không được để sang task sau. Odoo kiểm tra tên trường của view lúc nạp
> module, nên gỡ trường mà để view còn tham chiếu là `ParseError` ngay ở
> `-u` — module không nạp được, và mọi test sau đó đổ theo vì lý do không
> liên quan gì tới thứ đang sửa.

`recording_banner.js` vẫn còn gọi `action_decline` cho tới Task 8. Đó là lỗi
lúc bấm, không phải lỗi lúc nạp — chấp nhận được giữa hai task.

- [ ] **Step 5: Kết thúc khi cuộc gọi trống**

Sửa `unlink` trong `models/discuss_channel_rtc_session.py`:

```python
    def unlink(self):
        ended = self.channel_id.filtered(
            lambda c: not (c.sudo().rtc_session_ids - self))
        result = super().unlink()
        if ended:
            ended.sudo().aidt_call_host_partner_id = False
            # Không còn ai trong cuộc gọi thì không còn ai bấm được nút kết
            # thúc — kể cả chủ phòng, vì họ cũng đã rời. Bỏ qua bước này thì
            # bản ghi nằm mãi ở `recording` và chỉ mục duy nhất chặn luôn mọi
            # bản ghi mới trên kênh đó.
            recordings = self.env['aidt.meeting.recording'].sudo().search([
                ('channel_id', 'in', ended.ids),
                ('state', 'in', ('recording', 'paused')),
            ])
            for recording in recordings:
                recording._end_recording()
        return result
```

- [ ] **Step 6: Gỡ endpoint `finalize_recording`**

Trong `controllers/main.py`, xoá toàn bộ route `/aidt_meeting/api/finalize_recording`
và thay bằng comment:

```python
    # ĐÃ GỠ `/aidt_meeting/api/finalize_recording`.
    #
    # Nó gọi `action_stop()` cho TOÀN BỘ bản ghi mỗi khi một client kết thúc
    # phiên thu của mình — mà `recorder_service.stop()` chạy trên mọi đường
    # rời cuộc gọi. Hệ quả: một người đóng tab ở phút thứ 5 làm cả cuộc họp
    # mất phần còn lại của biên bản.
    #
    # Bản ghi giờ chỉ kết thúc từ hai nguồn: chủ phòng bấm [Kết thúc], hoặc
    # cuộc gọi trống (móc `unlink` của discuss.channel.rtc.session).
```

- [ ] **Step 7: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestEndRecording,/aidt_meeting_minutes:TestPause'`
Expected: PASS, 13 test

- [ ] **Step 8: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py \
        custom-addons/aidt_meeting_minutes/controllers/main.py \
        custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml \
        custom-addons/aidt_meeting_minutes/tests/test_host_control.py
git commit -m "fix(meeting): leaving a call no longer ends everyone's recording"
```

---

## Task 5: Người vào sau và người vào giữa lúc tạm dừng

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:370-390` (`action_active_recording`)
- Test: `custom-addons/aidt_meeting_minutes/tests/test_pause.py`

**Interfaces:**
- Produces: `action_active_recording(channel_id)` trả dict rỗng hoặc
  `{'recording_id': int, 'channel_id': int, 'elapsed_ms': int, 'state': str, 'take': int, 'host_partner_id': int}`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_pause.py`:

```python
    def test_nguoi_vao_giua_luc_tam_dung_van_thay_ban_ghi(self):
        """Hàm này hiện chỉ tìm `state = 'recording'`, nên người vào lúc đang
        tạm dừng KHÔNG thấy gì và tưởng cuộc họp không được ghi. Đó là đúng
        thứ 'thông báo bắt buộc' phải chặn."""
        self.recording.with_user(self.host).action_pause()
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info.get('recording_id'), self.recording.id)
        self.assertEqual(info.get('state'), 'paused')

    def test_tra_ve_du_thong_tin_de_client_dung_bang(self):
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info['state'], 'recording')
        self.assertEqual(info['take'], 0)
        self.assertEqual(info['host_partner_id'], self.host.partner_id.id)

    def test_take_phan_anh_so_lan_ghi_tiep(self):
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info['take'], 1)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestPause'`
Expected: FAIL — `test_nguoi_vao_giua_luc_tam_dung_van_thay_ban_ghi` nhận `{}`

- [ ] **Step 3: Mở rộng `action_active_recording`**

Thay `models/meeting_recording.py:370-390` bằng:

```python
    @api.model
    def action_active_recording(self, channel_id):
        """Bản ghi đang chạy trên kênh này, cho một máy vừa vào họp / vừa F5.

        Tìm cả `paused`: broadcast `started` chỉ phát một lần lúc bật, nên
        người vào sau chỉ biết được qua đường này. Chốt ở `recording` nghĩa
        là người vào giữa lúc tạm dừng không thấy thông báo nào và tưởng cuộc
        họp không được ghi.
        """
        channel = self.env['discuss.channel'].browse(int(channel_id)).exists()
        if not channel:
            return {}
        partner = self.env.user.partner_id
        if not self._is_channel_member(channel, partner):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        recording = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('state', 'in', ('recording', 'paused')),
        ], limit=1)
        if not recording:
            return {}
        recording._register_participants()
        return {
            'recording_id': recording.id,
            'channel_id': channel.id,
            'elapsed_ms': recording._elapsed_ms(),
            'state': recording.state,
            'take': recording.current_take,
            'host_partner_id': recording.host_partner_id.id,
        }
```

- [ ] **Step 4: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestPause'`
Expected: PASS, 10 test

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/tests/test_pause.py
git commit -m "feat(meeting): late joiners see the recording notice during a pause"
```

---

## Task 6: `take` trên mẩu audio

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_chunk.py`
- Modify: `custom-addons/aidt_meeting_minutes/controllers/main.py:19-65` (`upload_chunk`)
- Test: `custom-addons/aidt_meeting_minutes/tests/test_chunk_upload.py`

**Interfaces:**
- Consumes: `current_take` (Task 3)
- Produces: `aidt.meeting.chunk.take` (Integer, mặc định 0); `_store(recording, partner, seq, offset_ms, duration_ms, raw, take=0)`

> **Bước thủ công chỉ dùng khi phát triển:** Odoo không tự bỏ ràng buộc cũ.
> Chạy một lần trước Step 4:
> `docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt_demo -c "ALTER TABLE aidt_meeting_chunk DROP CONSTRAINT IF EXISTS aidt_meeting_chunk_seq_uniq;"`
> Bản dọn thật cho môi trường đã cài nằm ở Task 12.

- [ ] **Step 1: Viết test thất bại**

Thêm vào lớp `TestChunkStore` trong `tests/test_chunk_upload.py`. Lớp cơ sở
`ChunkCase` đã dựng sẵn `self.Chunk`, `self.speaker`, `self.recording` —
dùng lại, đừng dựng bộ mới:

```python
    def test_cung_seq_o_hai_take_khac_nhau_deu_luu_duoc(self):
        """`seq` đếm lại từ 0 mỗi lần ghi tiếp, nên khoá duy nhất phải có
        `take`. Thiếu nó thì mẩu đầu tiên sau khi ghi tiếp đụng khoá của mẩu
        đầu tiên trước khi tạm dừng, và cả lần ghi tiếp bị mất."""
        first = self.Chunk._store(self.recording, self.speaker.partner_id,
                                  0, 0, 30000, b'take-0', take=0)
        second = self.Chunk._store(self.recording, self.speaker.partner_id,
                                   0, 60000, 30000, b'take-1', take=1)
        self.assertEqual(first.take, 0)
        self.assertEqual(second.take, 1)
        self.assertNotEqual(first.id, second.id)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestChunkStore'`
Expected: FAIL — `_store() got an unexpected keyword argument 'take'`

- [ ] **Step 3: Thêm trường và đổi khoá duy nhất**

Trong `models/meeting_chunk.py`, thêm sau `seq` (dòng 20):

```python
    # Lần ghi. Tăng 1 mỗi lần chủ phòng bấm "Ghi tiếp". Không phải để cho gọn
    # dữ liệu: khi tạm dừng, client dừng `MediaRecorder` và lúc ghi tiếp tạo
    # một cái MỚI — luồng mới mang EBML header riêng. Worker nối các mẩu ở
    # mức byte, nên nối xuyên qua ranh giới tạm dừng cho ra một tệp có header
    # nằm giữa: ffmpeg giải mã phần đầu rồi dừng, IM LẶNG mất toàn bộ phần
    # sau lần ghi tiếp. `take` là thứ cho worker biết chỗ nào được nối.
    take = fields.Integer(string='Lần ghi', default=0, required=True)
```

Đổi ràng buộc (dòng 30-33):

```python
    _seq_uniq = models.Constraint(
        'UNIQUE(recording_id, partner_id, take, seq)',
        'Mỗi người chỉ có một mẩu audio cho mỗi thứ tự trong mỗi lần ghi.',
    )
```

- [ ] **Step 4: Nhận `take` trong `_store`**

Đổi chữ ký và phần `create` trong `models/meeting_chunk.py`:

```python
    @api.model
    def _store(self, recording, partner, seq, offset_ms, duration_ms, raw,
               take=0):
```

Trong khối `with self.env.cr.savepoint():`, đổi tên tệp đính kèm và thêm `take`:

```python
            attachment = self.env['ir.attachment'].sudo().create({
                'name': f'meeting-{recording.id}-{partner.id}-t{take}-{seq}.webm',
                'datas': base64.b64encode(raw),
                'mimetype': 'audio/webm',
                'res_model': 'aidt.meeting.recording',
                'res_id': recording.id,
            })
            chunk = self.sudo().create({
                'recording_id': recording.id,
                'partner_id': partner.id,
                'take': take,
                'seq': seq,
                'offset_ms': offset_ms,
                'duration_ms': duration_ms,
                'attachment_id': attachment.id,
            })
```

Và mở rộng danh sách trạng thái được nhận mẩu (dòng 54):

```python
        if recording.sudo().state not in ('recording', 'paused', 'processing'):
            raise AccessError(_('Bản ghi không còn nhận audio.'))
```

> `paused` PHẢI nằm trong danh sách. Mẩu đang bay trên đường lúc bấm tạm
> dừng vẫn phải được nhận — chặn ở đây thì mọi lần tạm dừng đều mất tới 30
> giây lời nói ngay trước đó. Ranh giới tạm dừng được bảo đảm ở worker
> (Task 10), nơi audio bị cắt tại `paused_at_ms`.

- [ ] **Step 5: Controller chuyển tiếp `take`**

Trong `controllers/main.py`, đổi chữ ký `upload_chunk` và lượt gọi `_store`:

```python
    def upload_chunk(self, recording_id, seq, offset_ms, duration_ms,
                     audio, take=0, **kwargs):
```

```python
            request.env['aidt.meeting.chunk']._store(
                recording, partner, int(seq), int(offset_ms),
                int(duration_ms), raw, take=int(take))
```

- [ ] **Step 6: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestChunkStore'`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_chunk.py \
        custom-addons/aidt_meeting_minutes/controllers/main.py \
        custom-addons/aidt_meeting_minutes/tests/test_chunk_upload.py
git commit -m "feat(meeting): number audio chunks by take"
```

---

## Task 7: Client — thu theo take, tạm dừng, ghi tiếp

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recorder_service.js`
- Test: `custom-addons/aidt_meeting_minutes/static/tests/recorder_take.test.js` (tạo mới)

**Interfaces:**
- Consumes: bus `aidt_meeting_minutes/recording_state` với `action` ∈ `started · paused · resumed · stopped`, kèm `state`, `take`, `host_partner_id`
- Produces: `MeetingRecorder.take`, `pause()`, `resume()`; mỗi lần upload gửi thêm trường form `take`

> Bộ hoot `recorder.test.js` hiện **đỏ sẵn 9 test** vì gọi `_onAudio`,
> `retainOverlap`, `carriedStartAt` — cả ba không còn tồn tại sau đợt
> refactor chunked-upload. Task này **không** sửa file đó; nó tạo file test
> mới cho hành vi mới.
>
> **Task 7 và Task 8 phải đi cùng nhau.** Task này gỡ `state.declined` và
> `decline()`, nhưng `recording_banner.js` còn đọc chúng cho tới Task 8 —
> giữa hai task, băng thông báo hỏng lúc chạy (không hỏng lúc nạp). Đừng
> nghiệm thu Task 7 một mình bằng cách mở giao diện thật.

- [ ] **Step 1: Viết test thất bại**

Tạo `static/tests/recorder_take.test.js`:

```javascript
import { describe, expect, test } from "@odoo/hoot";
import { MeetingRecorder } from "@aidt_meeting_minutes/recorder_service";

describe.current.tags("headless");

function makeRecorder() {
    const services = {
        "discuss.rtc": { state: { channel: { id: 7 }, micAudioTrack: null } },
        bus_service: { subscribe: () => {} },
        notification: {},
        orm: { call: async () => ({}) },
    };
    return new MeetingRecorder({ services: {} }, services);
}

test("ghi tiếp tăng take và đếm lại seq từ 0", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;
    recorder.take = 0;
    recorder.seq = 4;

    recorder._onRecordingState({
        action: "resumed", recording_id: 11, channel_id: 7,
        take: 1, state: "recording", elapsed_ms: 60000,
    });

    expect(recorder.take).toBe(1);
    expect(recorder.seq).toBe(0);
});

test("tạm dừng KHÔNG xoá recordingId", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;

    recorder._onRecordingState({
        action: "paused", recording_id: 11, channel_id: 7,
        take: 0, state: "paused", elapsed_ms: 5000,
    });

    // Bản ghi vẫn đang hoạt động, chỉ là không thu nữa. Xoá recordingId ở
    // đây thì băng thông báo biến mất và client tưởng cuộc họp đã kết thúc.
    expect(recorder.state.recordingId).toBe(11);
    expect(recorder.state.paused).toBe(true);
});

test("kết thúc mới xoá recordingId", async () => {
    const recorder = makeRecorder();
    recorder.state.recordingId = 11;

    recorder._onRecordingState({
        action: "stopped", recording_id: 11, channel_id: 7,
        take: 0, state: "processing", elapsed_ms: 9000,
    });

    expect(recorder.state.recordingId).toBe(null);
});
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:AidtMeetingJsSuite'`
Expected: FAIL — `recorder.take` là `undefined`; `state.paused` không tồn tại

- [ ] **Step 3: Thêm `take` và `paused` vào state**

Trong `recorder_service.js`, trong `constructor`, đổi khối `reactive` và thêm `take`:

```javascript
        this.state = reactive({
            recordingId: null,
            channelId: null,
            paused: false,
            hostPartnerId: null,
        });

        this.take = 0;
        this.seq = 0;
```

Xoá hai dòng `declined` và `declinedRecordingId` khỏi `reactive` — cơ chế từ
chối đã gỡ ở Task 4.

- [ ] **Step 4: Xử lý bốn hành động của bus**

Thay `_onRecordingState` bằng:

```javascript
    _onRecordingState(payload) {
        if (payload.action === "summary_done" || payload.action === "summary_failed") {
            const hash = window.location.hash || "";
            if (hash.includes("model=aidt.meeting.recording") &&
                hash.includes("id=" + payload.recording_id)) {
                this.env.services.action.doAction({
                    type: "ir.actions.client", tag: "soft_reload" });
            }
            return;
        }

        const channelId = this.currentChannelId;
        if (!channelId || payload.channel_id !== channelId) {
            return;
        }

        if (payload.action === "started") {
            this.state.hostPartnerId = payload.host_partner_id;
            this.start(payload.recording_id, payload.elapsed_ms || 0, channelId,
                       payload.take || 0);
            return;
        }

        if (this.state.recordingId !== payload.recording_id) {
            return;
        }

        if (payload.action === "paused") {
            // KHÔNG xoá recordingId: bản ghi vẫn đang hoạt động, chỉ là
            // không thu nữa. Xoá ở đây thì băng thông báo biến mất và người
            // dự tưởng cuộc họp đã kết thúc.
            this.state.paused = true;
            this.pause();
        } else if (payload.action === "resumed") {
            this.state.paused = false;
            this.resume(payload.take || 0, payload.elapsed_ms || 0);
        } else {
            this.stop();
        }
    }
```

- [ ] **Step 5: Thêm `pause()` và `resume()`, nhận `take` trong `start()`**

Đổi `start()`:

```javascript
    async start(recordingId, elapsedAtJoinMs, channelId = null, take = 0) {
        if (this.state.recordingId || this.isStopping) {
            return;
        }
        this.state.recordingId = recordingId;
        this.state.channelId = channelId ?? this.currentChannelId;
        this.state.paused = false;
        this.lastOfferedId = recordingId;
        this.elapsedAtJoinMs = elapsedAtJoinMs;
        this.recorderStartedAt = browser.performance.now();
        this.take = take;
        this.seq = 0;
        await this.reattach();
    }
```

Thêm hai hàm cạnh `stop()`:

```javascript
    /**
     * Tạm dừng THU BIÊN BẢN. Cuộc gọi không bị đụng tới — track WebRTC
     * (`rtc.state.micAudioTrack`) vẫn chạy, mọi người vẫn nghe và nói bình
     * thường. Chỉ luồng `getUserMedia` RIÊNG của bộ ghi âm bị đóng.
     *
     * KHÔNG đặt lại `recorderStartedAt`: trục thời gian phải đi xuyên qua
     * khoảng dừng để `offset_ms` vẫn là giờ tường kể từ lúc bắt đầu ghi.
     */
    pause() {
        if (!this.state.recordingId) {
            return;
        }
        const sessionRecorder = this.recorder;
        this.recorder = null;
        (async () => {
            if (sessionRecorder && sessionRecorder.state !== "inactive") {
                const stopped = new Promise((resolve) =>
                    sessionRecorder.addEventListener("stop", resolve, { once: true }));
                sessionRecorder.stop();
                await stopped;
            }
            this._flushPending(this.pending, this.activeUploads);
        })();
        this._teardownGraph();
    }

    /** Ghi tiếp sau khi tạm dừng. `seq` đếm lại từ 0 trong take mới. */
    async resume(take, elapsedAtJoinMs) {
        if (!this.state.recordingId) {
            return;
        }
        this.take = take;
        this.seq = 0;
        if (elapsedAtJoinMs && !this.recorderStartedAt) {
            // Máy vào họp GIỮA lúc đang tạm dừng: chưa có mốc gốc nào.
            this.elapsedAtJoinMs = elapsedAtJoinMs;
            this.recorderStartedAt = browser.performance.now();
        }
        await this.reattach();
    }
```

- [ ] **Step 6: Gửi `take` và bỏ `finalize_recording`**

Trong `_send()`, thêm một dòng sau `form.append("seq", ...)`:

```javascript
        form.append("take", chunk.take);
```

Trong `ondataavailable` và trong nhánh mẩu cuối của `stop()`, thêm
`take: this.take` vào object truyền cho `_send`.

Trong `stop()`, xoá khối `await browser.fetch("/aidt_meeting/api/finalize_recording", …)`
— endpoint đã gỡ ở Task 4. Giữ nguyên vòng vét `sessionPending`/`sessionActive`
phía trên nó.

Trong `stop()`, thêm `this.state.paused = false;` cạnh chỗ đặt
`this.state.recordingId = null;`.

- [ ] **Step 7: Cập nhật `syncActiveRecording` cho người vào giữa lúc dừng**

```javascript
    async syncActiveRecording() {
        const channelId = this.currentChannelId;
        if (!channelId || this.state.recordingId) {
            return;
        }
        let info;
        try {
            info = await this.orm.call(
                "aidt.meeting.recording", "action_active_recording",
                [channelId], {});
        } catch {
            return;
        }
        if (!info?.recording_id || this.currentChannelId !== channelId) {
            return;
        }
        this.state.hostPartnerId = info.host_partner_id;
        if (info.state === "paused") {
            // Hiện băng nhưng KHÔNG thu: chờ broadcast `resumed`.
            this.state.recordingId = info.recording_id;
            this.state.channelId = channelId;
            this.state.paused = true;
            this.take = info.take || 0;
            return;
        }
        await this.start(info.recording_id, info.elapsed_ms || 0, channelId,
                         info.take || 0);
    }
```

- [ ] **Step 8: Gỡ `decline()` và `sendMockAudio()`**

Xoá hai hàm khỏi `recorder_service.js`. `leaveCall()` giữ lại nhưng rút gọn:

```javascript
    leaveCall() {
        this.stop();
        this.lastOfferedId = null;
    }
```

- [ ] **Step 9: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:AidtMeetingJsSuite'`
Expected: 3 test mới PASS. Bộ `recorder.test.js` cũ vẫn đỏ 9 test — đã biết,
xử lý ở đợt riêng.

- [ ] **Step 10: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/recorder_service.js \
        custom-addons/aidt_meeting_minutes/static/tests/recorder_take.test.js
git commit -m "feat(meeting): client records per take across pause boundaries"
```

---

## Task 8: Băng thông báo — hai vai, ba trạng thái

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recording_banner.js`
- Modify: `custom-addons/aidt_meeting_minutes/static/src/recording_banner.xml`
- Test: `custom-addons/aidt_meeting_minutes/static/tests/banner.test.js`

**Interfaces:**
- Consumes: `recorder.state.recordingId`, `.paused`, `.hostPartnerId` (Task 7)
- Produces: getter `isHost`, `isPaused`, `isVisible`, `canStart`, `label`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `static/tests/banner.test.js`:

```javascript
test("người dự không thấy nút nào", async () => {
    const recorder = {
        state: { recordingId: 5, channelId: 7, paused: false, hostPartnerId: 99 },
    };
    await mountWithCleanup(RecordingBanner, {
        props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
    });
    expect(".o-aidt-recording-banner").toHaveCount(1);
    expect("button[name='pause']").toHaveCount(0);
    expect("button[name='stop']").toHaveCount(0);
});

test("chủ phòng thấy Tạm dừng và Kết thúc", async () => {
    const recorder = {
        state: { recordingId: 5, channelId: 7, paused: false, hostPartnerId: 42 },
    };
    await mountWithCleanup(RecordingBanner, {
        props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
    });
    expect("button[name='pause']").toHaveCount(1);
    expect("button[name='stop']").toHaveCount(1);
});

test("đang tạm dừng thì chủ phòng thấy Ghi tiếp", async () => {
    const recorder = {
        state: { recordingId: 5, channelId: 7, paused: true, hostPartnerId: 42 },
    };
    await mountWithCleanup(RecordingBanner, {
        props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
    });
    expect("button[name='resume']").toHaveCount(1);
    expect("button[name='pause']").toHaveCount(0);
});

test("người dự vẫn thấy băng khi đang tạm dừng", async () => {
    const recorder = {
        state: { recordingId: 5, channelId: 7, paused: true, hostPartnerId: 99 },
    };
    await mountWithCleanup(RecordingBanner, {
        props: { recorder, isActiveCall: true, channelId: 7, selfPartnerId: 42 },
    });
    // Giấu trạng thái tạm dừng còn tệ hơn không hiện gì: người ta sẽ giữ ý
    // trong khi thực ra không bị ghi, hoặc nói thoải mái vì tưởng đang dừng.
    expect(".o-aidt-recording-banner").toHaveCount(1);
});
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:AidtMeetingJsSuite'`
Expected: FAIL — nút `pause`/`resume` không tồn tại

- [ ] **Step 3: Viết lại component**

Thay toàn bộ phần getter và handler của `recording_banner.js`:

```javascript
    static props = {
        recorder: { type: Object, optional: true },
        isActiveCall: { type: Boolean, optional: true },
        channelId: { type: Number, optional: true },
        selfPartnerId: { type: Number, optional: true },
    };
    static defaultProps = { isActiveCall: true };

    setup() {
        this.orm = useService("orm");
        this.recorder = this.props.recorder || useService("aidt_meeting.recorder");
        this.state = useState(this.recorder.state);
        this.store = this.env.services["mail.store"];
    }

    /** Partner của chính máy này. Bus phát một payload chung cho mọi người,
     *  nên việc phân vai phải làm ở client. */
    get selfPartnerId() {
        return this.props.selfPartnerId ?? this.store?.self?.id ?? null;
    }

    get isHost() {
        return Boolean(this.state.hostPartnerId) &&
               this.state.hostPartnerId === this.selfPartnerId;
    }

    get isPaused() {
        return Boolean(this.state.paused);
    }

    get isForThisChannel() {
        if (!this.props.channelId || !this.state.channelId) {
            return true;
        }
        return this.state.channelId === this.props.channelId;
    }

    get isVisible() {
        return Boolean(this.state.recordingId) && this.props.isActiveCall &&
               this.isForThisChannel;
    }

    get canStart() {
        return !this.isVisible && this.props.isActiveCall &&
               Boolean(this.props.channelId);
    }

    get label() {
        if (this.isPaused) {
            return this.isHost
                ? _t("Ghi âm đang tạm dừng.")
                : _t("Ghi âm đang tạm dừng. Cuộc họp vẫn tiếp tục.");
        }
        return this.isHost
            ? _t("Đang ghi âm biên bản.")
            : _t("Cuộc họp đang được ghi âm để tạo biên bản.");
    }

    async onStart() {
        await this.orm.call("aidt.meeting.recording",
                            "action_start_for_channel", [this.props.channelId], {});
    }

    async onPause() {
        await this.orm.call("aidt.meeting.recording", "action_pause",
                            [[this.state.recordingId]], {});
    }

    async onResume() {
        await this.orm.call("aidt.meeting.recording", "action_resume",
                            [[this.state.recordingId]], {});
    }

    async onStop() {
        await this.orm.call("aidt.meeting.recording", "action_stop",
                            [[this.state.recordingId]], {});
    }
```

Xoá `displayedRecordingId`, `isDeclined`, `onDecline`, `onMockAudioClick`,
`onMockAudioChange` và import `useRef`.

- [ ] **Step 4: Viết lại template**

Thay khối `aidt_meeting_minutes.RecordingBanner` trong `recording_banner.xml`:

```xml
    <t t-name="aidt_meeting_minutes.RecordingBanner">
        <div t-if="isVisible" class="o-aidt-recording-banner"
             t-att-class="{ 'o-aidt-paused': isPaused }">
            <span class="o-aidt-recording-dot"/>
            <span t-esc="label"/>
            <!-- Người dự KHÔNG có nút nào: ghi âm là bắt buộc, và việc
                 dừng thuộc về chủ phòng. -->
            <t t-if="isHost">
                <button t-if="!isPaused" name="pause" class="btn btn-sm btn-secondary"
                        t-on-click="onPause">Tạm dừng</button>
                <button t-if="isPaused" name="resume" class="btn btn-sm btn-secondary"
                        t-on-click="onResume">Ghi tiếp</button>
                <button name="stop" class="btn btn-sm btn-danger"
                        t-on-click="onStop">Kết thúc</button>
            </t>
        </div>
        <div t-if="canStart" class="o-aidt-start-recording">
            <button name="start" class="btn btn-sm btn-outline-danger"
                    t-on-click="onStart">Bật ghi âm biên bản</button>
        </div>
    </t>
```

> Nút "Mock Audio (Dev)" gỡ hẳn: nó là đường nạp tệp audio tuỳ ý vào biên
> bản, không nên tồn tại trên bản chạy thật.

- [ ] **Step 5: Gỡ các test của cơ chế từ chối đã bỏ**

Trong `static/tests/banner.test.js`, xoá mọi test còn nhắc `decline`,
`isDeclined` hoặc `declinedRecordingId` — cơ chế đó đã gỡ ở Task 4, giữ lại
test cho nó chỉ tạo cảm giác an toàn giả. Tìm bằng:

```bash
grep -n "decline\|Declined" custom-addons/aidt_meeting_minutes/static/tests/banner.test.js
```

- [ ] **Step 6: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:AidtMeetingJsSuite'`
Expected: 4 test mới PASS, không còn test nào của cơ chế từ chối

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/recording_banner.js \
        custom-addons/aidt_meeting_minutes/static/src/recording_banner.xml \
        custom-addons/aidt_meeting_minutes/static/tests/banner.test.js
git commit -m "feat(meeting): banner shows host controls and pause state"
```

---

## Task 9: Xuất mẩu audio theo `(người, take)`

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py` (`_trigger_ai_service`)
- Test: `custom-addons/aidt_meeting_minutes/tests/test_ai_trigger.py`

**Interfaces:**
- Produces: tệp `spk{partner_id}_t{take}_{seq:05d}.webm` và `metadata.json` hai tầng:
  `{"speakers": [{"partner_id", "speaker_name", "takes": [{"take", "offset_ms", "files"}]}], "pauses": [{"paused_at_ms", "resumed_at_ms"}]}`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_ai_trigger.py`:

```python
    def test_metadata_gom_theo_nguoi_va_take(self):
        """`seq` đếm lại từ 0 mỗi take, nên thiếu `t{take}` trong tên tệp thì
        lần ghi tiếp GHI ĐÈ tệp của lần trước."""
        import base64
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'chunk-take1.webm',
            'datas': base64.b64encode(b'TAKE-1-AUDIO'),
            'mimetype': 'audio/webm',
        })
        self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id,
            'partner_id': self.user.partner_id.id,
            'take': 1, 'seq': 0,
            'offset_ms': 90000, 'duration_ms': 30000,
            'attachment_id': attachment.id,
        })
        self.env['aidt.meeting.pause'].sudo().create({
            'recording_id': self.recording.id,
            'paused_at_ms': 60000, 'resumed_at_ms': 90000,
        })

        with patch('requests.post'):
            self.recording._trigger_ai_service()

        chunk_dir = Path(f'/var/lib/odoo/meetings/{self.recording.id}')
        partner_id = self.user.partner_id.id
        self.assertTrue((chunk_dir / f'spk{partner_id}_t0_00000.webm').exists())
        self.assertTrue((chunk_dir / f'spk{partner_id}_t1_00000.webm').exists())

        meta = json.loads((chunk_dir / 'metadata.json').read_text())
        speaker = meta['speakers'][0]
        self.assertEqual(len(speaker['takes']), 2)
        take0, take1 = speaker['takes']
        self.assertEqual(take0['take'], 0)
        self.assertEqual(take0['offset_ms'], 0)
        self.assertEqual(take1['take'], 1)
        self.assertEqual(take1['offset_ms'], 90000)
        self.assertEqual(meta['pauses'],
                         [{'paused_at_ms': 60000, 'resumed_at_ms': 90000}])
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestAiTrigger'`
Expected: FAIL — `KeyError: 'takes'`

- [ ] **Step 3: Viết lại phần xuất tệp**

Trong `_trigger_ai_service`, thay khối gom `speakers` bằng:

```python
        chunks = self.env['aidt.meeting.chunk'].sudo().search(
            [('recording_id', '=', self.id)], order='partner_id, take, seq')

        speakers = {}
        total_chunks = 0
        for chunk in chunks:
            if not (chunk.attachment_id and chunk.attachment_id.datas):
                continue
            partner = chunk.partner_id
            chunk_file = f"spk{partner.id}_t{chunk.take}_{chunk.seq:05d}.webm"
            (chunk_dir / chunk_file).write_bytes(
                base64.b64decode(chunk.attachment_id.datas))
            total_chunks += 1

            speaker = speakers.setdefault(partner.id, {
                'partner_id': partner.id,
                'speaker_name': partner.name or 'Unknown',
                'takes': {},
            })
            # Mốc bắt đầu của mỗi LẦN GHI là offset của mẩu sớm nhất trong
            # chính lần đó — không phải của cả người. Nối byte chỉ hợp lệ
            # trong phạm vi một take (header EBML mới ở mỗi lần ghi tiếp).
            take = speaker['takes'].setdefault(chunk.take, {
                'take': chunk.take,
                'offset_ms': chunk.offset_ms,
                'files': [],
            })
            take['files'].append(chunk_file)
            take['offset_ms'] = min(take['offset_ms'], chunk.offset_ms)

        metadata = {
            'speakers': [
                {**spk, 'takes': [spk['takes'][k] for k in sorted(spk['takes'])]}
                for spk in speakers.values()
            ],
            'pauses': [
                {'paused_at_ms': p.paused_at_ms,
                 'resumed_at_ms': p.resumed_at_ms}
                for p in self.sudo().pause_ids.sorted('paused_at_ms')
            ],
        }
        (chunk_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False))
```

- [ ] **Step 4: Chạy lại test**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestAiTrigger'`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/tests/test_ai_trigger.py
git commit -m "feat(meeting): export audio chunks grouped by speaker and take"
```

---

## Task 10: Worker — ghép theo take và cắt tại mốc dừng

**Files:**
- Modify: `docker/ai_worker/main.py` (`_load_speakers`, `assemble_speaker_stream`, `process_meeting_task`)
- Test: `docker/ai_worker/test_takes.py` (tạo mới)

**Interfaces:**
- Consumes: `metadata.json` hai tầng (Task 9)
- Produces: `_load_streams(chunk_dir, total_chunks) -> List[dict]` với mỗi phần tử
  `{"key": str, "name": str, "take": int, "offset_ms": int, "files": List[str], "max_duration_ms": Optional[int]}`;
  `assemble_speaker_stream(chunk_dir, key, files, audio_filter, max_duration_ms=None)`

- [ ] **Step 1: Viết test thất bại**

Tạo `docker/ai_worker/test_takes.py`:

```python
"""Ghép audio theo (người, take). Chạy dưới pytest của ảnh dev Odoo."""

import json

import main


def write_meta(tmp_path, meta):
    (tmp_path / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False))


class TestLoadStreams:
    def test_moi_take_la_mot_luong_rieng(self, tmp_path):
        """Nối byte xuyên qua ranh giới tạm dừng cho ra tệp có EBML header
        nằm giữa: ffmpeg giải mã phần đầu rồi dừng, im lặng mất phần sau."""
        write_meta(tmp_path, {"speakers": [{
            "partner_id": 3, "speaker_name": "A", "takes": [
                {"take": 0, "offset_ms": 0, "files": ["spk3_t0_00000.webm"]},
                {"take": 1, "offset_ms": 90000, "files": ["spk3_t1_00000.webm"]},
            ]}], "pauses": []})

        streams = main._load_streams(tmp_path, 0)

        assert len(streams) == 2
        assert [s["take"] for s in streams] == [0, 1]
        assert streams[0]["files"] == ["spk3_t0_00000.webm"]
        assert streams[1]["offset_ms"] == 90000
        assert streams[0]["name"] == "A"

    def test_cat_tai_moc_tam_dung(self, tmp_path):
        """Mẩu đang bay lúc bấm tạm dừng vẫn được nhận ở server (nếu chặn thì
        mất tới 30 giây lời nói trước mỗi lần dừng), nên ranh giới phải được
        bảo đảm ở đây."""
        write_meta(tmp_path, {"speakers": [{
            "partner_id": 3, "speaker_name": "A", "takes": [
                {"take": 0, "offset_ms": 0, "files": ["a.webm"]},
                {"take": 1, "offset_ms": 90000, "files": ["b.webm"]},
            ]}], "pauses": [{"paused_at_ms": 60000, "resumed_at_ms": 90000}]})

        streams = main._load_streams(tmp_path, 0)

        assert streams[0]["max_duration_ms"] == 60000
        assert streams[1]["max_duration_ms"] is None

    def test_doc_duoc_khuon_dang_cu(self, tmp_path):
        """Job đã nằm sẵn trên đĩa từ bản trước phải chạy lại được."""
        write_meta(tmp_path, {"speakers": [
            {"partner_id": 3, "speaker_name": "A", "offset_ms": 34,
             "files": ["spk3_00000.webm", "spk3_00001.webm"]}]})

        streams = main._load_streams(tmp_path, 0)

        assert len(streams) == 1
        assert streams[0]["take"] == 0
        assert streams[0]["offset_ms"] == 34
        assert streams[0]["max_duration_ms"] is None

    def test_khong_co_metadata_thi_coi_la_mot_luong(self, tmp_path):
        streams = main._load_streams(tmp_path, 2)
        assert len(streams) == 1
        assert streams[0]["files"] == ["chunk_0.webm", "chunk_1.webm"]
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: `docker exec aidt-odoo-dev-odoo-1 bash -lc 'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 -m pytest docker/ai_worker/test_takes.py -q'`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_load_streams'`

- [ ] **Step 3: Thay `_load_speakers` bằng `_load_streams`**

Trong `docker/ai_worker/main.py`, thay toàn bộ `_load_speakers` (dòng 760-795):

```python
def _pause_bound_for(take_offset_ms: int, pauses: List[Dict[str, Any]]):
    """Mốc tạm dừng ngay SAU lần ghi bắt đầu tại `take_offset_ms`, nếu có.

    Trả về số mili-giây tối đa mà lần ghi đó được phép dài, hoặc None nếu
    sau nó không có lần tạm dừng nào (tức là lần ghi cuối).
    """
    after = [p["paused_at_ms"] for p in pauses
             if p.get("paused_at_ms", 0) > take_offset_ms]
    if not after:
        return None
    return min(after) - take_offset_ms


def _load_streams(chunk_dir: Path, total_chunks: int) -> List[Dict[str, Any]]:
    """Mỗi phần tử trả về là một cặp (người, lần ghi) — một luồng độc lập.

    Nối byte CHỈ hợp lệ trong phạm vi một take: khi tạm dừng, client dừng
    `MediaRecorder` và lúc ghi tiếp tạo một cái mới mang EBML header riêng.
    Nối xuyên take cho ra tệp có header nằm giữa, ffmpeg giải mã phần đầu rồi
    dừng — mất im lặng toàn bộ phần sau lần ghi tiếp.

    Chấp nhận cả khuôn dạng cũ (một tầng, không có `takes`) để job đã nằm sẵn
    trên đĩa vẫn chạy lại được.
    """
    meta_file = chunk_dir / "metadata.json"
    if not meta_file.exists():
        files = [f"chunk_{i}.webm" for i in range(total_chunks)]
        return [{"key": "0_t0", "name": "", "take": 0, "offset_ms": 0,
                 "files": files, "max_duration_ms": None}]

    meta = json.loads(meta_file.read_text())
    pauses = meta.get("pauses", []) if isinstance(meta, dict) else []
    speakers = meta.get("speakers", meta) if isinstance(meta, dict) else meta

    streams: List[Dict[str, Any]] = []
    for idx, spk in enumerate(speakers):
        key = str(spk.get("partner_id") or spk.get("speaker_name") or idx)
        name = spk.get("speaker_name") or ""
        takes = spk.get("takes")
        if takes is None:
            # Khuôn dạng cũ: cả người là một lần ghi liền mạch.
            takes = [{"take": 0,
                      "offset_ms": int(spk.get("offset_ms") or 0),
                      "files": list(spk.get("files") or [])}]
        for take in takes:
            offset_ms = int(take.get("offset_ms") or 0)
            streams.append({
                "key": f"{key}_t{take.get('take', 0)}",
                "name": name,
                "take": int(take.get("take", 0)),
                "offset_ms": offset_ms,
                "files": list(take.get("files") or []),
                "max_duration_ms": _pause_bound_for(offset_ms, pauses),
            })
    return streams
```

- [ ] **Step 4: Cho `assemble_speaker_stream` cắt được**

Đổi chữ ký (dòng 252) và lượt gọi `decode_to_wav`:

```python
def assemble_speaker_stream(chunk_dir: Path, speaker_key: str,
                            files: List[str], audio_filter: str,
                            max_duration_ms: Optional[int] = None) -> Optional[Path]:
```

Đổi `decode_to_wav` để nhận giới hạn:

```python
def decode_to_wav(src: Path, dst: Path, audio_filter: str,
                  max_duration_ms: Optional[int] = None) -> bool:
    """Giải mã một tệp audio bất kỳ về WAV 16 kHz mono đã lọc.

    `max_duration_ms` cắt tại ranh giới tạm dừng. Đây là chỗ DUY NHẤT bảo
    đảm audio sau thời điểm tạm dừng không lọt vào biên bản — server vẫn
    nhận mẩu ở trạng thái `paused` để không mất lời nói ngay trước lúc dừng.
    """
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if max_duration_ms:
        cmd += ["-t", f"{max_duration_ms / 1000:.3f}"]
    cmd += ["-ar", "16000", "-ac", "1", "-af", audio_filter, str(dst)]
    res = _run(cmd)
    if res.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        logger.warning("ffmpeg không giải mã được %s: %s",
                       src.name, res.stderr[-400:])
        return False
    return True
```

Trong `assemble_speaker_stream`, truyền `max_duration_ms` vào cả lượt chính và
lượt dự phòng giải mã từng mẩu.

- [ ] **Step 5: Nối vào `process_meeting_task`**

Thay khối dựng `streams` (dòng 826-836):

```python
        raw_streams = _load_streams(chunk_dir, total_chunks)

        streams = []
        for item in raw_streams:
            if not item["files"]:
                continue
            wav = assemble_speaker_stream(
                chunk_dir, item["key"], item["files"], AUDIO_FILTER_CHAIN,
                item["max_duration_ms"])
            if wav:
                streams.append({**item, "wav": wav,
                                "duration_ms": probe_duration_ms(wav)})
```

Trong vòng bóc băng, đổi dòng log để in cả take:

```python
            logger.info("Luồng %s (%s, lần ghi %s): %s segment thô",
                        stream["key"], stream["name"], stream["take"],
                        len(raw_segments))
```

- [ ] **Step 6: Chạy lại test**

Run: `docker exec aidt-odoo-dev-odoo-1 bash -lc 'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 -m pytest docker/ai_worker/test_takes.py docker/ai_worker/test_filters.py -q'`
Expected: PASS, 15 test

- [ ] **Step 7: Commit**

```bash
git add docker/ai_worker/main.py docker/ai_worker/test_takes.py
git commit -m "feat(worker): assemble audio per speaker-take and cut at pause"
```

---

## Task 11: Mốc tạm dừng trong biên bản

**Files:**
- Modify: `docker/ai_worker/main.py` (`build_transcript_for_llm`, `SYSTEM_PROMPT`, `process_meeting_task`)
- Test: `docker/ai_worker/test_takes.py`

**Interfaces:**
- Produces: `build_transcript_for_llm(segments, pauses=())` — chèn dòng mốc đúng vị trí thời gian

- [ ] **Step 1: Viết test thất bại**

Thêm vào `docker/ai_worker/test_takes.py`:

```python
def seg(text, abs_start_ms, speaker="A"):
    return {"text": text, "abs_start": abs_start_ms,
            "abs_end": abs_start_ms + 2000, "speaker": speaker}


class TestPauseMarker:
    def test_chen_moc_dung_vi_tri_thoi_gian(self):
        segments = [seg("Trước khi dừng", 308000), seg("Sau khi ghi tiếp", 521000)]
        pauses = [{"paused_at_ms": 312000, "resumed_at_ms": 520000}]

        lines = main.build_transcript_for_llm(segments, pauses).split("\n")

        assert lines[0].startswith("[05:08]")
        assert lines[1] == ("--- TẠM DỪNG GHI ÂM 05:12 → 08:40 "
                            "(3 phút 28 giây không được ghi) ---")
        assert lines[2].startswith("[08:41]")

    def test_doan_dung_khong_ghi_tiep_dat_o_cuoi(self):
        """Chủ phòng kết thúc trong lúc đang tạm dừng: ta biết lúc dừng,
        KHÔNG biết cuộc họp còn kéo dài bao lâu sau đó."""
        segments = [seg("Câu cuối", 300000)]
        pauses = [{"paused_at_ms": 312000, "resumed_at_ms": 0}]

        lines = main.build_transcript_for_llm(segments, pauses).split("\n")

        assert lines[-1] == ("--- TẠM DỪNG GHI ÂM 05:12 — không ghi tiếp "
                             "cho tới hết cuộc họp ---")

    def test_khong_co_doan_dung_thi_khong_chen_gi(self):
        segments = [seg("Một câu", 1000), seg("Câu nữa", 3000)]
        assert "TẠM DỪNG" not in main.build_transcript_for_llm(segments, [])

    def test_prompt_he_thong_day_model_khong_suy_dien_qua_cho_dung(self):
        assert "TẠM DỪNG GHI ÂM" in main.SYSTEM_PROMPT
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: `docker exec aidt-odoo-dev-odoo-1 bash -lc 'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 -m pytest docker/ai_worker/test_takes.py::TestPauseMarker -q'`
Expected: FAIL — `build_transcript_for_llm() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Viết hàm dựng mốc**

Thêm trên `build_transcript_for_llm` trong `main.py`:

```python
def format_duration_vi(ms: int) -> str:
    """'3 phút 28 giây'. Người đọc biên bản cần biết mất bao nhiêu, không
    phải một con số mili-giây."""
    total = max(0, ms) // 1000
    minutes, seconds = divmod(total, 60)
    if minutes and seconds:
        return f"{minutes} phút {seconds} giây"
    if minutes:
        return f"{minutes} phút"
    return f"{seconds} giây"


def pause_marker(pause: Dict[str, Any]) -> str:
    start = format_timestamp(pause["paused_at_ms"] / 1000)
    resumed = pause.get("resumed_at_ms") or 0
    if not resumed:
        # Không bịa một mốc kết thúc: ta biết lúc dừng, không biết cuộc họp
        # còn kéo dài bao lâu sau đó.
        return (f"--- TẠM DỪNG GHI ÂM {start} — không ghi tiếp "
                f"cho tới hết cuộc họp ---")
    end = format_timestamp(resumed / 1000)
    gap = format_duration_vi(resumed - pause["paused_at_ms"])
    return f"--- TẠM DỪNG GHI ÂM {start} → {end} ({gap} không được ghi) ---"
```

- [ ] **Step 4: Chèn mốc khi dựng transcript**

Thay `build_transcript_for_llm`:

```python
def build_transcript_for_llm(segments: List[Dict[str, Any]],
                             pauses: List[Dict[str, Any]] = ()) -> str:
    """Transcript có mốc thời gian, kèm dòng đánh dấu các đoạn không được ghi.

    Mốc phải nằm ĐÚNG vị trí thời gian của nó giữa hai câu, chứ không gom
    hết xuống cuối: model đọc theo thứ tự, và một đoạn thiếu đặt sai chỗ còn
    khó hiểu hơn là không đánh dấu.
    """
    events = [(s["abs_start"], 0, s) for s in segments]
    events += [(p["paused_at_ms"], 1, p) for p in (pauses or [])]
    events.sort(key=lambda e: (e[0], e[1]))

    lines = []
    for _at, kind, item in events:
        if kind == 1:
            lines.append(pause_marker(item))
            continue
        stamp = format_timestamp(item["abs_start"] / 1000)
        speaker = item.get("speaker")
        lines.append(f"[{stamp}] {speaker}: {item['text']}" if speaker
                     else f"[{stamp}] {item['text']}")
    return "\n".join(lines)
```

- [ ] **Step 5: Dạy model tránh chỗ dừng**

Thêm quy tắc 8 vào `SYSTEM_PROMPT`, ngay trước dòng `Trả về đúng schema sau`:

```
8. Transcript có thể chứa dòng `--- TẠM DỪNG GHI ÂM ... ---`. Đó là khoảng
   thời gian KHÔNG được ghi. Tuyệt đối không suy diễn nội dung trong khoảng
   đó và không nối hai bên thành một mạch liên tục. Nếu một công việc hoặc
   quyết định chỉ có thể suy ra từ phần bị thiếu thì BỎ QUA.
```

- [ ] **Step 6: Truyền `pauses` vào lượt dựng transcript**

Trong `process_meeting_task`, đọc `pauses` từ metadata và truyền vào:

```python
        meta_file = chunk_dir / "metadata.json"
        pauses = []
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            if isinstance(meta, dict):
                pauses = meta.get("pauses", [])

        transcript_raw = build_transcript_for_llm(segments, pauses)
```

- [ ] **Step 7: Chạy lại test**

Run: `docker exec aidt-odoo-dev-odoo-1 bash -lc 'cd /opt/odoo && PYTHONPATH=docker/ai_worker /opt/venv/bin/python3 -m pytest docker/ai_worker/ -q'`
Expected: PASS, 19 test

- [ ] **Step 8: Nạp lại worker và commit**

```bash
docker compose -f docker-compose.ai.yml restart ai-worker
git add docker/ai_worker/main.py docker/ai_worker/test_takes.py
git commit -m "feat(worker): mark un-recorded stretches in the transcript"
```

---

## Task 12: Giao diện bản ghi và migration

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py` (`pause_summary`)
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`
- Create: `custom-addons/aidt_meeting_minutes/migrations/19.0.1.3.0/pre-migration.py`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py`
- Test: `custom-addons/aidt_meeting_minutes/tests/test_pause.py`

**Interfaces:**
- Produces: `pause_summary` (Char, compute, không lưu)

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_pause.py`:

```python
    def test_tom_tat_doan_dung_cho_nguoi_doc_bien_ban(self):
        """Biên bản KHÔNG phủ hết cuộc họp là điều ảnh hưởng tới giá trị
        pháp lý của nó — người đọc phải thấy ngay, không phải tự suy ra."""
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        self.assertIn('1 đoạn không được ghi', self.recording.pause_summary)

    def test_khong_co_doan_dung_thi_tom_tat_rong(self):
        self.assertFalse(self.recording.pause_summary)
```

- [ ] **Step 2: Chạy test để chắc là nó đỏ**

Run: lệnh test Odoo với `--test-tags '/aidt_meeting_minutes:TestPause'`
Expected: FAIL — `Invalid field 'pause_summary'`

- [ ] **Step 3: Thêm trường tóm tắt**

Trong `models/meeting_recording.py`, thêm cạnh `pause_ids`:

```python
    pause_summary = fields.Char(
        string='Đoạn không được ghi', compute='_compute_pause_summary')

    @api.depends('pause_ids.paused_at_ms', 'pause_ids.resumed_at_ms')
    def _compute_pause_summary(self):
        for rec in self:
            pauses = rec.pause_ids
            if not pauses:
                rec.pause_summary = ''
                continue
            total = sum(
                (p.resumed_at_ms - p.paused_at_ms)
                for p in pauses if p.resumed_at_ms)
            minutes, seconds = divmod(max(0, total) // 1000, 60)
            rec.pause_summary = (
                f"{len(pauses)} đoạn không được ghi · "
                f"tổng {minutes} phút {seconds} giây")
```

- [ ] **Step 4: Sửa view form**

Trong `views/meeting_recording_views.xml` (dòng `declined_partner_ids` đã
xoá ở Task 4), thêm ngay sau `<field name="ended_at"/>`:

```xml
                                    <field name="host_partner_id" readonly="1"/>
                                    <field name="pause_summary" readonly="1"
                                           invisible="not pause_summary"/>
                                    <field name="pause_ids" readonly="1"
                                           invisible="not pause_ids">
                                        <list>
                                            <field name="paused_at_ms"/>
                                            <field name="resumed_at_ms"/>
                                            <field name="paused_by_id"/>
                                        </list>
                                    </field>
```

- [ ] **Step 5: Viết migration**

Tạo `migrations/19.0.1.3.0/pre-migration.py`:

```python
import logging

_logger = logging.getLogger(__name__)

# Bốn thao tác ở tầng CSDL mà Odoo KHÔNG tự làm khi nâng cấp.
#
# Cùng họ với ba cái bẫy `noupdate` đã cắn ở 19.0.1.0.1, 19.0.1.1.0 và
# 19.0.1.2.0: thay đổi ở tầng định nghĩa không tự tới được cơ sở dữ liệu đã
# cài. Ở đây là hai cơ chế khác nhau nhưng cùng hậu quả.


def migrate(cr, version):
    if not version:
        return

    # 1. Chỉ mục duy nhất MỘT PHẦN không tự cập nhật.
    #    `init()` dùng `CREATE UNIQUE INDEX IF NOT EXISTS`, nên khi mệnh đề
    #    WHERE đổi (thêm 'paused') lệnh đó KHÔNG LÀM GÌ CẢ và chỉ mục cũ ở
    #    lại. Hậu quả: đang tạm dừng vẫn bật được một bản ghi thứ hai trên
    #    cùng kênh. Phải drop tường minh rồi để `init()` tạo lại.
    cr.execute("DROP INDEX IF EXISTS aidt_meeting_recording_channel_active_uniq")

    # 2. Khoá duy nhất của chunk đổi từ (recording, partner, seq) sang
    #    (recording, partner, take, seq). Không gỡ trước thì mẩu đầu tiên sau
    #    mỗi lần ghi tiếp đụng khoá của mẩu đầu tiên trước khi tạm dừng, và
    #    cả lần ghi tiếp bị mất.
    cr.execute("ALTER TABLE aidt_meeting_chunk "
               "DROP CONSTRAINT IF EXISTS aidt_meeting_chunk_seq_uniq")

    # 3. Bảng quan hệ của `declined_partner_ids` — cơ chế Từ chối đã gỡ vì
    #    ghi âm nay là bắt buộc.
    cr.execute("DROP TABLE IF EXISTS aidt_meeting_recording_res_partner_rel")

    # 4. Tàn dư của đợt chuyển sang xử lý theo lô: model `aidt.meeting.segment`
    #    đã xoá từ lâu mà bảng vẫn còn trong aidt_demo.
    cr.execute("DROP TABLE IF EXISTS aidt_meeting_segment")

    _logger.info('aidt_meeting_minutes: dọn xong chỉ mục, khoá duy nhất và '
                 'hai bảng chết trước khi lên 19.0.1.3.0.')
```

- [ ] **Step 6: Cập nhật `init()` và bump phiên bản**

Trong `models/meeting_recording.py`, đổi mệnh đề WHERE của `init()`:

```python
              WHERE state IN ('recording', 'paused', 'processing')
```

Trong `__manifest__.py`, thêm khối ghi chú và bump:

```python
    #
    # 19.0.1.3.0: chủ phòng điều khiển ghi âm, thông báo bắt buộc, tạm dừng
    # và ghi tiếp. Migration ở migrations/19.0.1.3.0/pre-migration.py làm bốn
    # việc mà Odoo không tự làm: chỉ mục duy nhất MỘT PHẦN không cập nhật
    # theo mệnh đề WHERE mới (`init()` dùng IF NOT EXISTS), khoá duy nhất của
    # chunk phải gỡ trước khi thêm `take`, và hai bảng chết cần dọn.
    'version': '19.0.1.3.0',
```

- [ ] **Step 7: Chạy toàn bộ test và kiểm chứng migration**

```bash
# Lùi phiên bản để migration thật sự chạy — Odoo chỉ chạy khi DB version thấp hơn
docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt_demo -tAc \
  "UPDATE ir_module_module SET latest_version='19.0.1.2.1' WHERE name='aidt_meeting_minutes';"
```

Run: lệnh test Odoo với `--test-tags /aidt_meeting_minutes`
Expected: mọi test Python PASS. Log phải có dòng
`aidt_meeting_minutes: dọn xong chỉ mục, khoá duy nhất và hai bảng chết`.

Kiểm chứng chỉ mục đã đúng:

```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt_demo -tAc \
  "SELECT indexdef FROM pg_indexes WHERE indexname='aidt_meeting_recording_channel_active_uniq';"
```
Expected: mệnh đề WHERE có chứa `'paused'`.

- [ ] **Step 8: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml \
        custom-addons/aidt_meeting_minutes/migrations/19.0.1.3.0/pre-migration.py \
        custom-addons/aidt_meeting_minutes/__manifest__.py \
        custom-addons/aidt_meeting_minutes/tests/test_pause.py
git commit -m "feat(meeting): surface un-recorded stretches and migrate schema"
```

---

## Kiểm chứng đầu-cuối sau Task 12

Không thay cho test tự động, nhưng ba điều dưới đây **chưa có test nào phủ**
và phải chạy tay một lần trước khi coi là xong:

1. **Hai máy thật, một cuộc họp.** Máy A vào trước (thành chủ phòng), máy B
   vào sau. Xác nhận: chỉ A thấy nút bật; B thấy băng thông báo không nút.
2. **Tạm dừng rồi ghi tiếp.** A bấm Tạm dừng, hai bên nói vài câu, A bấm Ghi
   tiếp, nói tiếp, rồi Kết thúc. Xác nhận biên bản **không** chứa câu nào nói
   trong lúc dừng, và có dòng `--- TẠM DỪNG GHI ÂM ... ---` đúng chỗ.
3. **Người vào giữa lúc tạm dừng** thấy băng "Ghi âm đang tạm dừng".

Lý do phải chạy tay: `MediaRecorder` sinh EBML header mới ở mỗi lần ghi tiếp
là hành vi của trình duyệt thật, không mô phỏng được trong hoot; và đường
`getUserMedia` thứ hai cũng vậy.

---

## Việc còn treo, không thuộc kế hoạch này

- Bộ hoot `recorder.test.js` **đỏ sẵn 9 test** (gọi `_onAudio`,
  `retainOverlap`, `carriedStartAt` — không còn tồn tại). Phải viết lại, không
  sửa vá.
- Webhook `/aidt_meeting/api/webhook/summary/<id>` `auth='public'` không xác
  thực; `/aidt_meeting/audio/<id>` public + `cors='*'` bỏ qua phân quyền độ
  mật.
- `docs/GUIDANCE.md` chưa có mục nào cho ghi âm cuộc họp; theo quy ước dự án
  thì tính năng chưa coi là xong khi chưa có.
- Khử trùng lặp khi hai người ngồi chung phòng (spec §13).
