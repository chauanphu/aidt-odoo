# Phòng họp là một loại kênh riêng — kế hoạch thực thi (khối A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến cuộc họp từ một cuộc gọi ngẫu nhiên trong kênh bất kỳ thành một loại phòng có vòng đời riêng — có mục "Họp" trong thanh bên Thảo luận, có trang quản lý CRUD, và chỉ phòng họp mới ghi âm được.

**Architecture:** Bất biến duy nhất — một `discuss.channel` là phòng họp khi và chỉ khi `calendar_event_ids` không rỗng. Không thêm trường lưu trữ nào lên `discuss.channel`, không thêm giá trị nào cho `channel_type`. Mọi thứ khác suy ra từ đó: mục thanh bên, quyền ghi âm, người chủ trì.

**Tech Stack:** Odoo 19 (Python + OWL), `addons/mail` + `addons/calendar` upstream, hoot cho test JS, `TransactionCase` cho test Python.

**Spec:** `docs/superpowers/specs/2026-08-11-meeting-room-crud-design.md`

## Global Constraints

- Module `aidt_meeting_minutes`: `19.0.1.3.1` → `19.0.1.4.0`. Bump **một lần duy nhất**, ở Task 3.
- Mọi thứ người dùng nhìn thấy — nhãn trường, menu, thông báo lỗi — viết bằng **tiếng Việt**. Comment trong `custom-addons/` cũng tiếng Việt.
- **Không sửa `odoo/` và `addons/`.** Mọi mở rộng làm từ `custom-addons/aidt_meeting_minutes/`.
- Cơ sở dữ liệu dev duy nhất là **`aidt_demo`**. Test tự động được dùng CSDL tạm nhưng **phải xoá cả CSDL lẫn thư mục filestore của nó khi chạy xong**.
- **Mốc nghiệm thu:** `recorder.test.js` đang đỏ sẵn **đúng 9 test** (`mute gating` 6, `chồng lấn` 3). Sau mỗi task phải vẫn đúng 9 — không hơn.
- Hoot **bỏ qua chứ không báo trượt** khi thiếu chromium hoặc `websocket-client`. Một bộ test báo 0 assertion là dấu hiệu bị skip, không phải đã qua.
- Không đụng tới hai lỗ hổng đã biết (`webhook/summary` không xác thực, `/aidt_meeting/audio/<id>` công khai) — thuộc đợt khác.
- Chạy test Python phải kèm `--http-port=8073 --gevent-port=8074` vì server dev đang giữ 8069; thiếu nó thì tiến trình chết ở `Address already in use` **nhưng vẫn thoát mã 0**.

## Cấu trúc file

| File | Trách nhiệm | Task |
|---|---|---|
| `models/meeting_recording.py` (sửa) | `_event_for_channel` chọn đúng buổi; siết `_start_for_channel`, `action_active_recording` | 1, 4 |
| `models/discuss_channel.py` (sửa) | `aidt_is_meeting_room` + đẩy sang store | 2 |
| `models/calendar_event.py` (tạo) | `aidt_has_room` — ô "tạo phòng" | 3 |
| `models/discuss_channel_rtc_session.py` (sửa) | Chỉ chốt chủ phòng cho phòng họp | 4 |
| `views/calendar_event_views.xml` (tạo) | Ô "Phòng họp trực tuyến" trên form; action + view_mode cho trang quản lý | 3, 7 |
| `views/meeting_recording_views.xml` (sửa) | Menu: thêm "Quản lý cuộc họp", đổi tên "Lịch sử cuộc họp" | 7 |
| `static/src/discuss_app_model_patch.js` (tạo) | Thêm `DiscussAppCategory` "Họp" | 5 |
| `static/src/thread_model_patch.js` (tạo) | Xếp phòng họp vào mục "Họp" | 5 |
| `static/src/discuss_sidebar_meetings.xml` (tạo) | Nút `+` "Họp ngay" ở đầu mục | 6 |
| `tests/test_event_for_channel.py` (tạo) | Ba nấc chọn buổi | 1 |
| `tests/test_meeting_room.py` (tạo) | `aidt_is_meeting_room`, `aidt_has_room` | 2, 3 |
| `tests/test_host_control.py`, `tests/test_recording_auth.py` (viết lại) | Gắn `calendar.event` vào kênh thử | 4 |
| `static/tests/sidebar_category.test.js` (tạo) | Phòng họp rơi vào mục "Họp" | 5 |
| `docs/GUIDANCE.md`, `README.md` (sửa) | Tài liệu người dùng và mục "đã/chưa kiểm chứng" | 8 |

---

### Task 1: `_event_for_channel` chọn đúng buổi đang diễn ra

Cuộc họp định kỳ dùng **chung một kênh** cho mọi lần (`addons/calendar/models/calendar_event.py:1057-1078` cố ý gán như vậy). `_event_for_channel` hiện dùng `limit=1` không kèm `order`, nên rơi vào `_order = "start desc"` của `calendar.event` và **luôn trả về buổi xa nhất trong tương lai**.

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:189-197`
- Create: `custom-addons/aidt_meeting_minutes/tests/test_event_for_channel.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/__init__.py`

**Interfaces:**
- Produces: `AidtMeetingRecording._event_for_channel(self, channel, at=None) -> calendar.event` (recordset 0 hoặc 1 bản ghi). Chữ ký cũ `(self, channel)` vẫn gọi được — `at` mặc định là `fields.Datetime.now()`. Task 4 dùng lại nguyên chữ ký này.

- [ ] **Step 1: Viết test thất bại**

Tạo `custom-addons/aidt_meeting_minutes/tests/test_event_for_channel.py`:

```python
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEventForChannel(TransactionCase):
    """Một kênh có thể đứng sau NHIỀU cuộc họp.

    `addons/calendar/models/calendar_event.py:1057` cố ý gán một kênh cho
    TOÀN BỘ các lần của một cuộc họp định kỳ. Giao ban hằng tuần chạy cả năm
    là một kênh, 52 `calendar.event`. Hỏi "cuộc họp nào đứng sau kênh này"
    mà không kèm mốc thời gian là câu hỏi không có câu trả lời đúng.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Giao ban tuần',
            'channel_type': 'group',
        })
        cls.now = fields.Datetime.now()
        cls.Recording = cls.env['aidt.meeting.recording']

    def _event(self, offset_hours, hours=1):
        """Một buổi họp gắn vào kênh chung, cách `now` đúng `offset_hours`.

        `no_mail_to_attendees` + `mail_notrack`: tạo `calendar.event` bình
        thường sẽ gửi thư mời và ghi tracking, chậm và ồn trong test.
        """
        start = self.now + timedelta(hours=offset_hours)
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True,
            mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': f'Buổi {offset_hours}h',
            'start': start,
            'stop': start + timedelta(hours=hours),
            'videocall_channel_id': self.channel.id,
        })

    def test_khong_co_buoi_nao_thi_tra_rong(self):
        self.assertFalse(self.Recording._event_for_channel(self.channel))

    def test_mot_buoi_thi_tra_dung_buoi_do(self):
        event = self._event(-100)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), event)

    def test_uu_tien_buoi_dang_dien_ra(self):
        """Đây là ca lỗi trung tâm: trước khi sửa, hàm trả về buổi tuần sau."""
        self._event(-24 * 7)
        ongoing = self._event(-0.5)
        self._event(24 * 7)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), ongoing)

    def test_khong_co_buoi_dang_chay_thi_lay_buoi_sap_toi_gan_nhat(self):
        self._event(-24 * 7)
        soon = self._event(2)
        self._event(24 * 7)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), soon)

    def test_het_roi_thi_lay_buoi_vua_qua_gan_nhat(self):
        """Cuộc họp định kỳ đã chạy hết: bản ghi phải gắn vào buổi CUỐI,
        không phải buổi đầu tiên của chuỗi."""
        self._event(-24 * 7)
        last = self._event(-3)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), last)

    def test_lay_theo_moc_thoi_gian_truyen_vao(self):
        first = self._event(-24 * 7)
        self._event(24 * 7)
        at = first.start + timedelta(minutes=10)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel, at=at), first)
```

Thêm vào `custom-addons/aidt_meeting_minutes/tests/__init__.py`:

```python
from . import test_event_for_channel
```

- [ ] **Step 2: Chạy để chắc là nó trượt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:TestEventForChannel \
  --stop-after-init
```

Expected: `test_uu_tien_buoi_dang_dien_ra`, `test_khong_co_buoi_dang_chay_thi_lay_buoi_sap_toi_gan_nhat`, `test_het_roi_thi_lay_buoi_vua_qua_gan_nhat` và `test_lay_theo_moc_thoi_gian_truyen_vao` FAIL. Bốn cái này thất bại vì hàm cũ trả về buổi `start` lớn nhất.

- [ ] **Step 3: Sửa `_event_for_channel`**

Thay nguyên thân hàm ở `models/meeting_recording.py:189-197`:

```python
    @api.model
    def _event_for_channel(self, channel, at=None):
        """Cuộc họp đứng sau kênh này TẠI MỐC `at`, hoặc bản ghi rỗng.

        Một kênh có thể đứng sau NHIỀU cuộc họp: `addons/calendar` cố ý cho
        cả chuỗi họp định kỳ dùng chung một kênh
        (`calendar_event.py:1057`). Bản cũ dùng `limit=1` không kèm `order`
        nên rơi vào `_order = "start desc"` của `calendar.event` và LUÔN trả
        về buổi xa nhất trong tương lai — giao ban sáng nay trả về buổi
        tháng 12. Bốn chỗ hỏng vì nó: kiểm người chủ trì, `secrecy_at_start`,
        `recording.event_id`, và `_resolve_host_partner`.

        Thứ tự ưu tiên: buổi ĐANG diễn ra -> buổi SẮP tới gần nhất -> buổi
        VỪA qua gần nhất. Nấc thứ ba cần thiết vì bản ghi được tạo lúc bấm
        "Bật ghi âm", có thể muộn hơn `stop` vài phút khi cuộc họp kéo dài.

        sudo() vì người dùng có thể dự họp mà không có quyền đọc
        calendar.event qua record rule của aidt_calendar; ở đây ta chỉ cần
        biết cuộc họp TỒN TẠI và độ mật của nó để quyết định cho phép.
        """
        at = at or fields.Datetime.now()
        events = self.env['calendar.event'].sudo().search(
            [('videocall_channel_id', '=', channel.id)])
        # Đường tắt: cuộc họp thường — tuyệt đại đa số — không phải trả giá
        # cho ba lượt lọc dưới đây.
        if len(events) <= 1:
            return events
        ongoing = events.filtered(
            lambda e: e.start and e.stop and e.start <= at <= e.stop)
        if ongoing:
            return ongoing.sorted('start')[0]
        upcoming = events.filtered(lambda e: e.start and e.start > at)
        if upcoming:
            return upcoming.sorted('start')[0]
        return events.sorted('start')[-1]
```

- [ ] **Step 4: Chạy lại, phải xanh hết**

Lệnh y như Step 2. Expected: 6/6 PASS.

- [ ] **Step 5: Chạy toàn bộ test module để chắc không làm vỡ gì**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes --stop-after-init
```

Expected: `1 failed, 0 error(s)` — đúng một cái, là wrapper `AidtMeetingJsSuite` bọc 9 test hoot đỏ sẵn. Bất kỳ con số nào khác là hồi quy.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/tests/test_event_for_channel.py \
        custom-addons/aidt_meeting_minutes/tests/__init__.py
git commit -m "fix(meeting): pick the occurrence that is actually running"
```

---

### Task 2: `aidt_is_meeting_room` trên `discuss.channel` và đẩy sang client

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/discuss_channel.py`
- Create: `custom-addons/aidt_meeting_minutes/tests/test_meeting_room.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/__init__.py`

**Interfaces:**
- Produces: trường tính **không lưu** `discuss.channel.aidt_is_meeting_room` (Boolean), và tên trường đó xuất hiện trong `_to_store_defaults()` nên client nhận được nó trên `Thread`. Task 5 đọc `thread.aidt_is_meeting_room` phía JS.

- [ ] **Step 1: Viết test thất bại**

Tạo `custom-addons/aidt_meeting_minutes/tests/test_meeting_room.py`:

```python
from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tools.discuss import Store
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestMeetingRoomFlag(TransactionCase):
    """Phòng họp = kênh có `calendar.event` đứng sau. Không có cờ riêng."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thường', 'channel_type': 'channel'})

    def _attach_event(self, channel):
        now = fields.Datetime.now()
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': 'Cuộc họp thử',
            'start': now,
            'stop': now + timedelta(hours=1),
            'videocall_channel_id': channel.id,
        })

    def test_kenh_khong_co_lich_thi_khong_phai_phong_hop(self):
        self.assertFalse(self.channel.aidt_is_meeting_room)

    def test_kenh_co_lich_thi_la_phong_hop(self):
        self._attach_event(self.channel)
        self.channel.invalidate_recordset(['aidt_is_meeting_room'])
        self.assertTrue(self.channel.aidt_is_meeting_room)

    def test_truong_nam_trong_goi_gui_client(self):
        """Thiếu bước này thì thanh bên không bao giờ biết kênh nào là
        phòng họp — mục "Họp" sẽ rỗng vĩnh viễn."""
        defaults = self.channel._to_store_defaults(Store.Target())
        self.assertIn('aidt_is_meeting_room', defaults)
        self.assertIn(
            'channel_type', defaults,
            'phải nối vào kết quả của super(), không thay thế nó')
```

Thêm vào `tests/__init__.py`:

```python
from . import test_meeting_room
```

- [ ] **Step 2: Chạy để chắc là nó trượt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:TestMeetingRoomFlag \
  --stop-after-init
```

Expected: cả 3 FAIL/ERROR với `AttributeError` hoặc `KeyError` quanh `aidt_is_meeting_room`.

- [ ] **Step 3: Thêm trường và ghi đè `_to_store_defaults`**

Sửa `models/discuss_channel.py` — đổi dòng import đầu file thành `from odoo import api, fields, models`, rồi thêm vào cuối lớp:

```python
    # Phòng họp KHÔNG có cờ riêng: nó là kênh có `calendar.event` đứng sau.
    # `calendar_event_ids` do `addons/calendar/models/discuss_channel.py:9`
    # khai sẵn (quan hệ ngược của `calendar.event.videocall_channel_id`).
    #
    # Không lưu (`store=False`): lưu là đẻ ra nguồn sự thật thứ hai, và nó
    # sẽ trôi — xoá cuộc họp trong Lịch thì cờ vẫn bật, kênh thành phòng họp
    # không có cuộc họp nào.
    aidt_is_meeting_room = fields.Boolean(
        string='Là phòng họp',
        compute='_compute_aidt_is_meeting_room',
    )

    @api.depends('calendar_event_ids')
    def _compute_aidt_is_meeting_room(self):
        for channel in self:
            channel.aidt_is_meeting_room = bool(channel.calendar_event_ids)

    def _to_store_defaults(self, target):
        """Đẩy `aidt_is_meeting_room` sang client.

        `_to_store` (`addons/mail/models/discuss/discuss_channel.py:1313`)
        chỉ gửi đúng những trường mà hàm này liệt kê. Thiếu tên trường ở đây
        thì `Thread` phía JS không bao giờ thấy nó, và mục "Họp" trong thanh
        bên rỗng vĩnh viễn mà không có lỗi nào.
        """
        return super()._to_store_defaults(target) + ['aidt_is_meeting_room']
```

- [ ] **Step 4: Chạy lại, phải xanh hết**

Lệnh y như Step 2. Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/discuss_channel.py \
        custom-addons/aidt_meeting_minutes/tests/test_meeting_room.py \
        custom-addons/aidt_meeting_minutes/tests/__init__.py
git commit -m "feat(meeting): expose whether a channel is a meeting room"
```

---

### Task 3: Ô "Phòng họp trực tuyến" trên form cuộc họp

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/models/calendar_event.py`
- Modify: `custom-addons/aidt_meeting_minutes/models/__init__.py`
- Create: `custom-addons/aidt_meeting_minutes/views/calendar_event_views.xml`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py` (`data`, `version`)
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_meeting_room.py`

**Interfaces:**
- Consumes: `discuss.channel.aidt_is_meeting_room` (Task 2) — chỉ để khẳng định trong test rằng tạo phòng xong thì kênh thành phòng họp.
- Produces: `calendar.event.aidt_has_room` (Boolean, compute + inverse). Task 6 đặt `default_aidt_has_room=True` trong context của nút "Họp ngay".

- [ ] **Step 1: Viết test thất bại**

Thêm lớp này vào cuối `tests/test_meeting_room.py`:

```python
@tagged('post_install', '-at_install')
class TestHasRoom(TransactionCase):
    """Ô "tạo phòng" là trường TÍNH có nghịch đảo, không phải cờ lưu riêng."""

    def _event(self, **vals):
        now = fields.Datetime.now()
        base = {
            'name': 'Họp thử',
            'start': now,
            'stop': now + timedelta(hours=1),
        }
        base.update(vals)
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create(base)

    def test_khong_tich_thi_khong_co_phong(self):
        event = self._event()
        self.assertFalse(event.aidt_has_room)
        self.assertFalse(event.videocall_channel_id)

    def test_tich_luc_tao_thi_co_phong_ngay(self):
        """Odoo chạy `inverse` cả trong create(), nên đúng một trường phục vụ
        cả 'tích lúc tạo lịch' lẫn 'tạo phòng sau ở trang quản lý'."""
        event = self._event(aidt_has_room=True)
        self.assertTrue(event.videocall_channel_id)
        self.assertTrue(event.aidt_has_room)
        self.assertTrue(event.videocall_channel_id.aidt_is_meeting_room)

    def test_tich_sau_thi_tao_phong(self):
        event = self._event()
        event.aidt_has_room = True
        self.assertTrue(event.videocall_channel_id)

    def test_tich_hai_lan_khong_tao_phong_thu_hai(self):
        event = self._event(aidt_has_room=True)
        first = event.videocall_channel_id
        event.aidt_has_room = True
        self.assertEqual(event.videocall_channel_id, first)

    def test_bo_tich_khong_xoa_phong(self):
        """Một chiều là CỐ Ý: phòng giữ lịch sử ghi âm và biên bản. Gỡ nó đi
        là bỏ rơi các `aidt.meeting.recording` trỏ vào kênh không còn ai
        dùng. Muốn bỏ phòng thì xoá cuộc họp."""
        event = self._event(aidt_has_room=True)
        channel = event.videocall_channel_id
        event.aidt_has_room = False
        self.assertEqual(event.videocall_channel_id, channel)
        self.assertTrue(event.aidt_has_room,
                        'compute phải đọc lại từ kênh, nên vẫn là True')
```

- [ ] **Step 2: Chạy để chắc là nó trượt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:TestHasRoom --stop-after-init
```

Expected: 5/5 FAIL với `ValueError: Invalid field 'aidt_has_room'`.

- [ ] **Step 3: Thêm model**

Tạo `custom-addons/aidt_meeting_minutes/models/calendar_event.py`:

```python
from odoo import api, fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Ô "tạo phòng" trên form. KHÔNG lưu: trạng thái thật nằm ở
    # `videocall_channel_id`, lưu thêm một boolean là đẻ ra nguồn sự thật
    # thứ hai sẽ trôi khỏi nó.
    #
    # Odoo tự nhiên khớp với cách dùng ta cần: `inverse` chạy cả trong
    # `create()`, nên đúng một trường phục vụ cả "tích lúc tạo lịch" lẫn
    # "tạo phòng sau ở trang quản lý cuộc họp". Không cần hai cơ chế.
    aidt_has_room = fields.Boolean(
        string='Phòng họp trực tuyến',
        compute='_compute_aidt_has_room',
        inverse='_inverse_aidt_has_room',
        help='Tạo một phòng trong Thảo luận cho cuộc họp này. '
             'Chỉ phòng họp mới bật được ghi âm và biên bản tự động.',
    )

    @api.depends('videocall_channel_id')
    def _compute_aidt_has_room(self):
        for event in self:
            event.aidt_has_room = bool(event.videocall_channel_id)

    def _inverse_aidt_has_room(self):
        """CHỈ TẠO, không bao giờ xoá.

        Bỏ tích không gỡ phòng, và đó là chủ ý: phòng giữ toàn bộ lịch sử
        ghi âm, mẩu audio và biên bản. Gỡ nó bằng một cái tích chuột là bỏ
        rơi cả đống `aidt.meeting.recording` trỏ vào một kênh không còn ai
        dùng, không có gì cảnh báo. Muốn bỏ phòng thì xoá cuộc họp — đường
        đó rõ ràng hơn và Odoo đã hỏi xác nhận sẵn.

        Trên form, ô này thành chỉ-đọc ngay khi phòng đã tồn tại, nên người
        dùng không rơi vào cảnh bỏ tích rồi thấy nó tự bật lại.
        """
        for event in self:
            if event.aidt_has_room and not event.videocall_channel_id:
                event._create_videocall_channel()
        # Giá trị đang nằm trong cache là thứ người dùng VỪA GÁN, không phải
        # sự thật. Bỏ tích ghi False vào cache, mà `_inverse` ở trên không
        # đụng tới `videocall_channel_id` — trường mà `_compute` phụ thuộc —
        # nên Odoo không có lý do gì để tự tính lại. Lần đọc sau vẫn thấy
        # False trong khi phòng còn nguyên, tức là trường nói dối về chính
        # thứ nó tồn tại để trả lời. Ép tính lại cho khớp trạng thái thật.
        self.invalidate_recordset(['aidt_has_room'])
```

Dòng `invalidate_recordset` cuối cùng là **bắt buộc**, không phải tuỳ chọn: thiếu nó thì
`test_bo_tich_khong_xoa_phong` trượt. Gán vào một trường **tính, không lưu** ghi thẳng giá
trị đó vào cache rồi mới gọi `inverse`; nếu `inverse` không đụng trường mà `compute` phụ
thuộc, Odoo không làm mới cache.

Thêm vào `models/__init__.py`:

```python
from . import calendar_event
```

Chú ý thứ tự import: `calendar_event` phải đứng **sau** `meeting_recording` nếu file đó đã import gì từ nhau; hiện tại không có phụ thuộc nào nên đặt cuối danh sách là được.

- [ ] **Step 4: Chạy lại, phải xanh hết**

Lệnh y như Step 2. Expected: 5/5 PASS.

- [ ] **Step 5: Thêm ô vào form và bump phiên bản**

Tạo `custom-addons/aidt_meeting_minutes/views/calendar_event_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Kế thừa THỨ HAI trên form cuộc họp. `aidt_calendar` đã có
         `calendar_event_view_form_inherit` của nó cho độ mật/phòng họp/đơn
         vị; ô phòng họp trực tuyến thuộc về module biên bản nên khai ở đây,
         để `aidt_calendar` không phải biết gì về ghi âm. -->
    <record id="calendar_event_form_room" model="ir.ui.view">
        <field name="name">calendar.event.form.aidt.room</field>
        <field name="model">calendar.event</field>
        <field name="inherit_id" ref="calendar.view_calendar_event_form"/>
        <field name="arch" type="xml">
            <field name="videocall_location" position="after">
                <!-- Chỉ-đọc khi phòng đã tồn tại: `_inverse_aidt_has_room`
                     một chiều nên bỏ tích không có tác dụng, và một ô tự
                     bật lại sau khi người ta bỏ tích là giao diện nói dối. -->
                <field name="aidt_has_room"
                       readonly="videocall_channel_id != False"/>
            </field>
        </field>
    </record>
</odoo>
```

Trong `__manifest__.py`, thêm vào `data` **sau** `views/meeting_recording_views.xml`:

```python
        'views/calendar_event_views.xml',
```

và đổi phiên bản, kèm ghi chú theo đúng lối changelog của file:

```python
    # 19.0.1.4.0: cuộc họp thành một loại phòng riêng — mục "Họp" trong thanh
    # bên Thảo luận, ghi âm chỉ còn trong phòng họp, trang "Quản lý cuộc họp"
    # tạo/sửa cuộc họp, trang bản ghi đổi thành "Lịch sử cuộc họp". Không cần
    # migration: bất biến "phòng họp = kênh có calendar.event" đọc từ quan hệ
    # `calendar_event_ids` upstream đã có sẵn, nên các phòng họp cũ tự động
    # được nhận đúng mà không phải sửa dữ liệu.
    'version': '19.0.1.4.0',
```

- [ ] **Step 6: Nạp lại module, không được có ParseError**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 --stop-after-init 2>&1 \
  | grep -aiE "ParseError|Traceback|CRITICAL"
```

Expected: không có dòng nào. Cảnh báo `<i> with fa class ... must have title` là có sẵn từ trước, bỏ qua.

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/calendar_event.py \
        custom-addons/aidt_meeting_minutes/models/__init__.py \
        custom-addons/aidt_meeting_minutes/views/calendar_event_views.xml \
        custom-addons/aidt_meeting_minutes/__manifest__.py \
        custom-addons/aidt_meeting_minutes/tests/test_meeting_room.py
git commit -m "feat(meeting): add a create-room checkbox on the meeting form"
```

---

### Task 4: Ghi âm chỉ còn trong phòng họp

Đây là task đắt nhất: nó **đổi hành vi** và làm đỏ hai file test đang xanh. Hai file đó mã hoá đúng cái hành vi đang bị bỏ, nên phải viết lại chứ không phải vá.

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/models/meeting_recording.py` (`_start_for_channel`, `action_active_recording`)
- Modify: `custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_host_control.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_recording_auth.py`

**Interfaces:**
- Consumes: `_event_for_channel(channel, at=None)` từ Task 1.
- Produces: `_start_for_channel` ném `AccessError('Chỉ ghi âm được trong phòng họp.')` cho kênh không có cuộc họp; `action_active_recording` trả `{}` cho kênh đó.

- [ ] **Step 1: Sửa test cho khớp hành vi mới, chạy để thấy nó trượt**

Trong `tests/test_host_control.py`, sửa `setUpClass` của `TestCallHost` để kênh thử **là phòng họp** — cần vậy vì Step 3 làm `discuss_channel_rtc_session` chỉ chốt chủ phòng cho phòng họp:

```python
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
        # Kênh phải là PHÒNG HỌP: từ 19.0.1.4.0, chủ phòng chỉ được chốt và
        # ghi âm chỉ bật được trong kênh có `calendar.event` đứng sau.
        # `user_id` = A vì mọi test dưới đây coi A là người chủ trì.
        now = fields.Datetime.now()
        cls.event = cls.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': 'Cuộc họp thử',
            'start': now - timedelta(minutes=5),
            'stop': now + timedelta(hours=1),
            'user_id': cls.user_a.id,
            'videocall_channel_id': cls.channel.id,
        })
```

Thêm hai import ở đầu file:

```python
from datetime import timedelta

from odoo import fields
```

Trong lớp `TestStartPermission`, thay docstring cũ (nó mô tả thế giới trước thay đổi) và thêm một test mới:

```python
@tagged('post_install', '-at_install')
class TestStartPermission(TestCallHost):
    """Chỉ người chủ trì cuộc họp mới bật được ghi âm, và chỉ trong phòng họp.

    Từ 19.0.1.4.0 chỉ còn MỘT nhánh: mọi phòng ghi âm được đều có
    `calendar.event`, nên `event.user_id` luôn tồn tại. Nhánh "cuộc gọi tự
    phát, chủ phòng cuộc gọi bật được" đã bị gỡ — chính nhánh đó sinh ra lỗi
    I1 ở nhánh trước (người vào sớm khoá chết quyền của lãnh đạo chủ trì).
    """

    def test_kenh_khong_phai_phong_hop_thi_khong_bat_duoc(self):
        thuong = self.env['discuss.channel'].create({
            'name': 'Kênh thường', 'channel_type': 'channel'})
        thuong.add_members(partner_ids=[self.user_a.partner_id.id])
        self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': self.env['discuss.channel.member'].search([
                ('channel_id', '=', thuong.id),
                ('partner_id', '=', self.user_a.partner_id.id)], limit=1).id,
        })
        with self.assertRaises(AccessError):
            self.env['aidt.meeting.recording'].with_user(
                self.user_a)._start_for_channel(thuong)

    def test_action_active_recording_tra_rong_cho_kenh_thuong(self):
        """Đây là điều kiện DUY NHẤT làm nút "Bật ghi âm biên bản" hiện ra.
        Trả `host_partner_id` cho kênh thường nghĩa là nút vẫn mời người ta
        bấm rồi mới ăn AccessError."""
        thuong = self.env['discuss.channel'].create({
            'name': 'Kênh thường 2', 'channel_type': 'channel'})
        thuong.add_members(partner_ids=[self.user_a.partner_id.id])
        info = self.env['aidt.meeting.recording'].with_user(
            self.user_a).action_active_recording(thuong.id)
        self.assertEqual(info, {})
```

Trong `tests/test_recording_auth.py`, mọi kênh đi qua **một** helper dùng chung
`RecordingCase._channel()` (dòng 20-34) và một helper `_event()` (dòng 44-56) đã gắn sẵn
`videocall_channel_id`. Làm ba việc:

**(a)** Thêm helper mới vào `RecordingCase`, ngay sau `_event`:

```python
    def _meeting_channel(self, partners, secrecy='thuong'):
        """Kênh ĐÃ LÀ phòng họp — có `calendar.event` đứng sau.

        Từ 19.0.1.4.0 ghi âm chỉ tồn tại trong phòng họp, nên đây là hình
        dạng mặc định của gần như mọi test dưới đây. `_channel()` trần được
        giữ lại đúng cho những test cần chứng minh kênh THƯỜNG bị từ chối.
        """
        channel = self._channel(partners)
        self._event(channel, secrecy=secrecy)
        return channel
```

**(b)** Xoá lớp `TestAdHocCall` (dòng 145-167) và viết lại thành:

```python
class TestKhongPhaiPhongHop(RecordingCase):
    """Kênh thường không ghi âm được — thay cho TestAdHocCall cũ.

    Hai test đầu của lớp cũ (`test_khong_co_lich_van_bat_duoc`,
    `test_cuoc_goi_tu_phat_coi_nhu_thuong`) khẳng định đúng cái hành vi đang
    bị bỏ, nên bị đảo chiều chứ không sửa. Hai test sau kiểm chuyện KHÁC
    (người ngoài, bản ghi trùng) nên chỉ chuyển sang phòng họp.
    """

    def test_kenh_thuong_khong_bat_duoc(self):
        channel = self._channel([self.member.partner_id])
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.member)._start_for_channel(channel)

    def test_kenh_thuong_khong_tra_thong_tin_ghi_am(self):
        channel = self._channel([self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertEqual(info, {})

    def test_khong_cho_nguoi_ngoai_bat_ghi_am(self):
        channel = self._meeting_channel([self.member.partner_id])
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.outsider)._start_for_channel(channel)

    def test_khong_bat_trung_hai_ban_ghi_tren_mot_channel(self):
        channel = self._meeting_channel([self.organizer.partner_id])
        self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)
```

Lưu ý `test_khong_bat_trung...` đổi từ `self.member` sang `self.organizer`: `_event()` đặt
`user_id = self.organizer`, và từ nay chỉ người chủ trì mới bật được.

**(c)** Chạy bộ test. Mọi test còn lại thất bại vì `AccessError('Chỉ ghi âm được trong
phòng họp.')` là test dựng kênh trần rồi mong ghi âm được — đổi `self._channel(...)` thành
`self._meeting_channel(...)` ở đúng những dòng đó. Đây là thủ tục xác định, có điều kiện
dừng rõ: lặp cho tới khi không còn `AccessError` nào mang thông điệp đó. **Không** đổi
những test cố ý kiểm kênh thường.

Chạy:

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes --stop-after-init
```

Expected: hai test mới ở `TestStartPermission` FAIL (hành vi chưa siết). Các test khác phải xanh — nếu có cái nào đỏ ngoài hai cái đó, sửa fixture trước khi sang Step 2.

- [ ] **Step 2: Siết `_start_for_channel`**

Trong `models/meeting_recording.py`, thay khối `event = ...` / `if event: ... else: secrecy = 'thuong'` bằng:

```python
        # Từ 19.0.1.4.0: ghi âm CHỈ tồn tại trong phòng họp — kênh có
        # `calendar.event` đứng sau. Nhánh "cuộc gọi tự phát" cũ đã bị gỡ:
        # nó cho phép bất kỳ chủ phòng cuộc gọi nào bật ghi âm ở bất kỳ kênh
        # nào, kể cả tin nhắn trực tiếp hai người, với độ mật mặc định
        # 'thuong' mà không ai chọn.
        event = self._event_for_channel(channel)
        if not event:
            raise AccessError(_('Chỉ ghi âm được trong phòng họp.'))
        # Người chủ trì trong lịch là tiếng nói cuối cùng — chủ phòng của
        # cuộc gọi không vượt được quyền đó.
        if event.user_id != self.env.user:
            raise AccessError(_('Chỉ người chủ trì cuộc họp mới bật được ghi âm.'))
        secrecy = event.secrecy or 'thuong'
        self._check_secrecy_allowed(secrecy)
```

- [ ] **Step 3: Siết `action_active_recording`**

Trong cùng file, ngay sau khối kiểm tra `_is_channel_member`, thêm:

```python
        # Kênh thường không có gì để trả: `host_partner_id` là điều kiện DUY
        # NHẤT làm nút "Bật ghi âm biên bản" hiện ra (RecordingBanner.canStart
        # đòi isHost, isHost đòi hostPartnerId). Trả nó cho kênh thường nghĩa
        # là mọi thành viên đều thấy nút mời họ bấm rồi ăn AccessError.
        if not self._event_for_channel(channel):
            return {}
```

- [ ] **Step 4: Chỉ chốt chủ phòng cho phòng họp**

Trong `models/discuss_channel_rtc_session.py`, sửa vòng lặp trong `create`:

```python
        for session in sessions:
            channel = session.channel_id
            if len(channel.sudo().rtc_session_ids) != 1:
                continue
            # Chỉ phòng họp mới có chủ phòng. Trước đây trường này được ghi
            # cho MỌI cuộc gọi, kể cả tin nhắn trực tiếp hai người, rồi
            # không ai đọc tới.
            if not self.env['aidt.meeting.recording']._event_for_channel(channel):
                continue
            channel.sudo().aidt_call_host_partner_id = \
                self._resolve_host_partner(channel, session.partner_id)
```

- [ ] **Step 5: Chạy lại toàn bộ**

Lệnh y như Step 1. Expected: `1 failed, 0 error(s)` — đúng một, là wrapper hoot đỏ sẵn.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/models/meeting_recording.py \
        custom-addons/aidt_meeting_minutes/models/discuss_channel_rtc_session.py \
        custom-addons/aidt_meeting_minutes/tests/test_host_control.py \
        custom-addons/aidt_meeting_minutes/tests/test_recording_auth.py
git commit -m "feat(meeting): restrict recording to meeting rooms"
```

---

### Task 5: Mục "Họp" trong thanh bên Thảo luận

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/discuss_app_model_patch.js`
- Create: `custom-addons/aidt_meeting_minutes/static/src/thread_model_patch.js`
- Create: `custom-addons/aidt_meeting_minutes/static/tests/sidebar_category.test.js`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py` (`assets`)

**Interfaces:**
- Consumes: `thread.aidt_is_meeting_room` (Task 2).
- Produces: `store.discuss.aidtMeetings` — một `DiscussAppCategory` với `id: "aidt_meeting_minutes.category_meetings"`. Task 6 gắn nút `+` vào mục này.

- [ ] **Step 1: Viết test thất bại**

Tạo `custom-addons/aidt_meeting_minutes/static/tests/sidebar_category.test.js`:

```javascript
import { describe, expect, test } from "@odoo/hoot";
import { defineMailModels, start } from "@mail/../tests/mail_test_helpers";

describe.current.tags("headless");
defineMailModels();

/** Chèn thẳng một Thread vào store, không đi qua mock server.
 *
 * Cố ý: `aidt_is_meeting_room` do server tính, và việc nó tới được client đã
 * có test Python riêng (TestMeetingRoomFlag). Ở đây ta chỉ kiểm ĐÚNG phần
 * mình viết — luật xếp mục — nên đặt thẳng giá trị vào là cách gọn nhất và
 * không phụ thuộc vào việc mock server có khai trường đó hay không.
 */
function insertThread(env, id, extra) {
    return env.services["mail.store"].Thread.insert({
        model: "discuss.channel",
        id,
        channel_type: "group",
        ...extra,
    });
}

test("phòng họp rơi vào mục Họp", async () => {
    const env = await start();
    const thread = insertThread(env, 101, { aidt_is_meeting_room: true });
    expect(thread.discussAppCategory.id).toBe(
        "aidt_meeting_minutes.category_meetings"
    );
});

test("kênh group thường vẫn ở Tin nhắn trực tiếp", async () => {
    const env = await start();
    const thread = insertThread(env, 102, { aidt_is_meeting_room: false });
    expect(thread.discussAppCategory.id).toBe("chats");
});

test("kênh channel thường vẫn ở Kênh", async () => {
    const env = await start();
    const thread = insertThread(env, 103, {
        channel_type: "channel",
        aidt_is_meeting_room: false,
    });
    expect(thread.discussAppCategory.id).toBe("channels");
});
```

Nếu `start()` trả về hình dạng khác `env`, đọc định nghĩa ở `addons/mail/static/tests/mail_test_helpers.js:339` và chỉnh cho khớp — đừng đoán.

- [ ] **Step 2: Chạy để chắc là nó trượt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:AidtMeetingJsSuite \
  --stop-after-init 2>&1 | grep -a "HOOT"
```

Expected: bộ `sidebar_category` báo `failed: 3`. Tổng số đỏ lúc này là 12 (9 cũ + 3 mới). Nếu bộ mới báo 0 assertion thì nó bị **skip** chứ không phải qua — kiểm tra chromium.

- [ ] **Step 3: Thêm mục "Họp"**

Tạo `custom-addons/aidt_meeting_minutes/static/src/discuss_app_model_patch.js`:

```javascript
import { fields } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

/** Id của mục, dùng chung với thread_model_patch.js và test. */
export const MEETINGS_CATEGORY_ID = "aidt_meeting_minutes.category_meetings";

// Danh sách mục trong thanh bên KHÔNG phải mảng cứng — nó là
// `store.discuss.allCategories`, tập record phía client. Thêm một mục là
// patch `DiscussApp`, đúng cách `im_livechat` đã làm cho hai mục của nó
// (addons/im_livechat/static/src/core/public_web/discuss_app_model_patch.js).
patch(DiscussApp.prototype, {
    setup() {
        super.setup(...arguments);
        this.aidtMeetings = fields.One("DiscussAppCategory", {
            compute() {
                return {
                    canView: false,
                    extraClass: "o-aidt-DiscussSidebarCategory-meeting",
                    // Người chưa có phòng họp nào thì không thấy mục này.
                    hideWhenEmpty: true,
                    icon: "fa fa-video-camera",
                    id: MEETINGS_CATEGORY_ID,
                    name: _t("Họp"),
                    // Giữa "Kênh" (10) và "Tin nhắn trực tiếp" (30).
                    sequence: 20,
                    // KHÔNG có `serverStateKey`: nó là tuỳ chọn (im_livechat
                    // bỏ nó ở `defaultLivechatCategory`), và dùng nó đòi một
                    // trường mới trên `res.users.settings`. Đổi lại, trạng
                    // thái đóng/mở của mục không được nhớ giữa các phiên —
                    // chấp nhận được, xem spec §5.3.
                };
            },
            eager: true,
        });
    },
});
```

Tạo `custom-addons/aidt_meeting_minutes/static/src/thread_model_patch.js`:

```javascript
import { Thread } from "@mail/core/common/thread_model";

import { patch } from "@web/core/utils/patch";

// Không import gì từ discuss_app_model_patch.js: chỉ cần trường
// `aidtMeetings` mà patch kia gắn lên DiscussApp, không cần hằng số id.
patch(Thread.prototype, {
    _computeDiscussAppCategory() {
        // Phòng họp trước đây rơi vào "Tin nhắn trực tiếp", vì
        // `_create_group()` đặt channel_type='group' và upstream gom cả
        // `group` lẫn `chat` vào đó
        // (addons/mail/.../thread_model_patch.js:58-68).
        //
        // `parent_channel_id` phải nhường cho super(): kênh con không bao
        // giờ hiện thành mục riêng trong thanh bên.
        if (!this.parent_channel_id && this.aidt_is_meeting_room) {
            return this.store.discuss.aidtMeetings;
        }
        return super._computeDiscussAppCategory(...arguments);
    },
});
```

Trong `__manifest__.py`, thêm vào `web.assets_backend` — **trước** `recorder_service.js` không quan trọng, nhưng giữ cùng cụm cho dễ đọc:

```python
            'aidt_meeting_minutes/static/src/discuss_app_model_patch.js',
            'aidt_meeting_minutes/static/src/thread_model_patch.js',
```

- [ ] **Step 4: Chạy lại, ba test mới phải xanh**

Lệnh y như Step 2. Expected: bộ `sidebar_category` báo `passed: 3`; tổng đỏ trở lại **đúng 9**.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/discuss_app_model_patch.js \
        custom-addons/aidt_meeting_minutes/static/src/thread_model_patch.js \
        custom-addons/aidt_meeting_minutes/static/tests/sidebar_category.test.js \
        custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "feat(meeting): give meeting rooms their own Discuss category"
```

---

### Task 6: Nút "+" tạo họp ngay ở đầu mục "Họp"

Ghi âm vừa bị siết về phòng họp, nên việc đang làm được hôm nay — bật ghi âm cho một trao đổi phát sinh — sẽ mất nếu không có đường tạo cuộc họp trong một thao tác.

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.xml`
- Create: `custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.js`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py` (`assets`)

**Interfaces:**
- Consumes: `MEETINGS_CATEGORY_ID` từ Task 5; `calendar.event.aidt_has_room` từ Task 3.

- [ ] **Step 1: Thêm hành động mở form cuộc họp**

Tạo `custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.js`:

```javascript
import { DiscussSidebarCategories } from "@mail/discuss/core/public_web/discuss_sidebar_categories";

import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

import { MEETINGS_CATEGORY_ID } from "@aidt_meeting_minutes/discuss_app_model_patch";

patch(DiscussSidebarCategories.prototype, {
    isAidtMeetingsCategory(category) {
        return category.id === MEETINGS_CATEGORY_ID;
    },

    /** Mở form cuộc họp dạng hộp thoại, đã điền sẵn "bắt đầu từ bây giờ".
     *
     * `luxon.DateTime` chứ không phải `Date` thuần: `serializeDateTime` chỉ
     * nhận luxon, và context của Odoo cần chuỗi UTC đúng định dạng — truyền
     * `Date` vào sẽ ra chuỗi ISO có hậu tố múi giờ mà server đọc sai.
     */
    onAddAidtMeeting() {
        const now = luxon.DateTime.now();
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "calendar.event",
            views: [[false, "form"]],
            target: "new",
            name: "Họp ngay",
            context: {
                default_start: serializeDateTime(now),
                default_stop: serializeDateTime(now.plus({ hours: 1 })),
                default_aidt_has_room: true,
            },
        });
    },
});
```

- [ ] **Step 2: Chèn nút vào tiêu đề mục**

Tạo `custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <!-- `name="header"` là điểm neo có sẵn trong template gốc
         (addons/mail/static/src/discuss/core/public_web/discuss_sidebar_categories.xml:34).
         Chèn vào trong nó để nút nằm cùng hàng với tên mục, giống dấu "+"
         của mục "Kênh". -->
    <t t-name="aidt_meeting_minutes.DiscussSidebarMeetingsAdd"
       t-inherit="mail.DiscussSidebarCategory.main" t-inherit-mode="extension">
        <xpath expr="//div[@name='header']" position="inside">
            <button t-if="isAidtMeetingsCategory(category)"
                    class="btn btn-link p-0 ms-auto o-aidt-add-meeting"
                    title="Họp ngay"
                    t-on-click.stop="onAddAidtMeeting">
                <i class="fa fa-plus" role="img" aria-label="Họp ngay"/>
            </button>
        </xpath>
    </t>
</templates>
```

Trong `__manifest__.py`, thêm vào `web.assets_backend`:

```python
            'aidt_meeting_minutes/static/src/discuss_sidebar_meetings.js',
            'aidt_meeting_minutes/static/src/discuss_sidebar_meetings.xml',
```

- [ ] **Step 3: Test tự động cho hành động mở form**

Tạo `custom-addons/aidt_meeting_minutes/static/tests/instant_meeting.test.js`:

```javascript
import { describe, expect, test } from "@odoo/hoot";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { DiscussSidebarCategories } from "@mail/discuss/core/public_web/discuss_sidebar_categories";

import { MEETINGS_CATEGORY_ID } from "@aidt_meeting_minutes/discuss_app_model_patch";

describe.current.tags("headless");
defineMailModels();

/** Gọi thẳng phương thức đã patch trên prototype, không mount component.
 *
 * `DiscussSidebarCategories` cần trọn store Discuss mới mount được, mà thứ
 * cần kiểm ở đây chỉ là NỘI DUNG hành động được phát đi — mount cả cây chỉ
 * để đọc một object là đắt và giòn.
 */
function fakeCategories(calls) {
    const self = Object.create(DiscussSidebarCategories.prototype);
    self.env = { services: { action: { doAction: (a) => calls.push(a) } } };
    return self;
}

test("chỉ nhận đúng mục Họp", () => {
    const self = fakeCategories([]);
    expect(self.isAidtMeetingsCategory({ id: MEETINGS_CATEGORY_ID })).toBe(true);
    expect(self.isAidtMeetingsCategory({ id: "channels" })).toBe(false);
    expect(self.isAidtMeetingsCategory({ id: "chats" })).toBe(false);
});

test("mở form cuộc họp với giờ hiện tại và ô phòng đã tích", () => {
    const calls = [];
    fakeCategories(calls).onAddAidtMeeting();
    expect(calls).toHaveLength(1);
    const action = calls[0];
    expect(action.res_model).toBe("calendar.event");
    expect(action.target).toBe("new");
    expect(action.context.default_aidt_has_room).toBe(true);
    // Định dạng server chờ đợi: "YYYY-MM-DD HH:MM:SS", KHÔNG phải ISO có
    // hậu tố múi giờ. Sai định dạng thì Odoo đọc lệch giờ mà không báo lỗi.
    expect(action.context.default_start).toMatch(
        /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
    );
    expect(action.context.default_stop).toMatch(
        /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
    );
    expect(action.context.default_stop > action.context.default_start).toBe(true);
});
```

Chạy:

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:AidtMeetingJsSuite \
  --stop-after-init 2>&1 | grep -a "HOOT"
```

Expected: bộ `instant_meeting` báo `passed: 2`; tổng đỏ vẫn **đúng 9**.

- [ ] **Step 4: Nạp lại và kiểm bằng mắt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 --stop-after-init 2>&1 \
  | grep -aiE "ParseError|Traceback|CRITICAL"
```

Expected: không có dòng nào. Nếu `t-inherit` không tìm thấy `//div[@name='header']`, mở
`addons/mail/static/src/discuss/core/public_web/discuss_sidebar_categories.xml` đọc lại tên
thẻ thật ở dòng 34 và chỉnh xpath cho khớp — đừng đoán tên thẻ.

Mở `http://localhost:8069/odoo/discuss`, xác nhận: mục "Họp" hiện khi có ít nhất một phòng
họp, có dấu `+`, bấm vào mở hộp thoại cuộc họp với giờ bắt đầu là hiện tại và ô "Phòng họp
trực tuyến" đã tích.

- [ ] **Step 5: Chạy lại bộ test module để chắc không vỡ gì**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes --stop-after-init
```

Expected: `1 failed, 0 error(s)`; hoot vẫn đúng 9 đỏ.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.js \
        custom-addons/aidt_meeting_minutes/static/src/discuss_sidebar_meetings.xml \
        custom-addons/aidt_meeting_minutes/static/tests/instant_meeting.test.js \
        custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "feat(meeting): add an instant-meeting button to the Họp category"
```

---

### Task 7: Menu "Quản lý cuộc họp" và đổi tên trang bản ghi

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/views/calendar_event_views.xml`
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml:262-274`
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`

**Interfaces:**
- Consumes: view ids của `aidt_calendar` — `aidt_calendar.calendar_event_view_list_aidt`, `aidt_calendar.calendar_event_view_kanban_aidt`. `aidt_meeting_minutes` đã khai `aidt_calendar` trong `depends` nên tham chiếu chéo hợp lệ.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`:

```python
    def test_menu_quan_ly_cuoc_hop_nam_trong_thao_luan(self):
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_management')
        self.assertEqual(
            menu.parent_id, self.env.ref('mail.menu_root_discuss'))
        self.assertEqual(menu.sequence, 3)
        self.assertEqual(menu.action.res_model, 'calendar.event')

    def test_trang_ban_ghi_doi_ten_thanh_lich_su(self):
        menu = self.env.ref('aidt_meeting_minutes.menu_meeting_recording')
        self.assertEqual(menu.name, 'Lịch sử cuộc họp')
        self.assertEqual(menu.sequence, 4)

    def test_cau_hinh_bi_day_xuong_5(self):
        """Giữa 3 và 4 không còn số nguyên nào, nên "Cấu hình" phải xuống 5."""
        self.assertEqual(
            self.env.ref('mail.menu_configuration').sequence, 5)

    def test_action_dung_chung_view_cua_aidt_calendar(self):
        """Không nhân bản view: thêm một trường thì chỉ sửa một chỗ."""
        action = self.env.ref('aidt_meeting_minutes.action_meeting_management')
        view_ids = action.view_ids.mapped('view_id')
        self.assertIn(
            self.env.ref('aidt_calendar.calendar_event_view_list_aidt'),
            view_ids)
```

- [ ] **Step 2: Chạy để chắc là nó trượt**

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes:TestUIViews --stop-after-init
```

Lớp trong file tên là `TestUIViews` (chữ `UI` viết hoa cả hai) — thêm bốn phương thức trên
vào chính lớp đó.

Expected: bốn test mới ERROR vì chưa có xml_id.

- [ ] **Step 3: Thêm action và menu**

Thêm vào cuối `views/calendar_event_views.xml`, trước `</odoo>`:

```xml
    <!-- Cửa vào thứ hai cho CÙNG dữ liệu và CÙNG bộ view của aidt_calendar.
         Khác biệt duy nhất so với "Lịch tổng hợp Văn phòng" là thứ tự
         view_mode: ở đây danh sách đứng trước (người vào từ Thảo luận muốn
         tra cứu và tạo), ở Lịch thì lịch đứng trước.

         KHÔNG tạo view mới: nhân bản list/kanban/form nghĩa là mỗi lần thêm
         một trường phải sửa hai nơi, và hai nơi sẽ trôi khác nhau. -->
    <record id="action_meeting_management" model="ir.actions.act_window">
        <field name="name">Quản lý cuộc họp</field>
        <field name="res_model">calendar.event</field>
        <field name="view_mode">list,calendar,kanban,form</field>
    </record>

    <record id="action_meeting_management_list" model="ir.actions.act_window.view">
        <field name="sequence">1</field>
        <field name="view_mode">list</field>
        <field name="act_window_id" ref="action_meeting_management"/>
        <field name="view_id" ref="aidt_calendar.calendar_event_view_list_aidt"/>
    </record>

    <record id="action_meeting_management_kanban" model="ir.actions.act_window.view">
        <field name="sequence">3</field>
        <field name="view_mode">kanban</field>
        <field name="act_window_id" ref="action_meeting_management"/>
        <field name="view_id" ref="aidt_calendar.calendar_event_view_kanban_aidt"/>
    </record>

    <!-- Mọi người dùng nội bộ: tạo cuộc họp vốn là việc ai cũng làm được ở
         ứng dụng Lịch. Độ mật và record rule của aidt_calendar vẫn chặn
         như cũ, không thêm nhóm quyền mới. -->
    <menuitem id="menu_meeting_management"
              name="Quản lý cuộc họp"
              parent="mail.menu_root_discuss"
              action="action_meeting_management"
              sequence="3"/>
```

Trong `views/meeting_recording_views.xml`, sửa khối cuối: đổi `sequence` của
`mail.menu_configuration` từ 4 thành **5**, và đổi menu bản ghi thành:

```xml
    <record id="mail.menu_configuration" model="ir.ui.menu">
        <field name="sequence">5</field>
    </record>

    <menuitem id="menu_meeting_recording"
              name="Lịch sử cuộc họp"
              parent="mail.menu_root_discuss"
              action="action_meeting_recording"
              groups="aidt_meeting_minutes.group_meeting_minutes_manager"
              sequence="4"/>
```

Cập nhật luôn khối comment ngay trên nó cho khớp thứ tự mới (1 Thảo luận, 2 Kênh,
3 Quản lý cuộc họp, 4 Lịch sử cuộc họp, 5 Cấu hình) — comment cũ nói "3 là mục này"
sẽ sai sau thay đổi.

- [ ] **Step 4: Chạy lại, phải xanh hết**

Lệnh y như Step 2. Expected: toàn bộ `TestUiViews` PASS.

- [ ] **Step 5: Kiểm chứng thứ tự thật trong CSDL**

```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt_demo -c "
SELECT d.module||'.'||d.name AS xmlid, m.sequence,
       jsonb_extract_path_text(m.name::jsonb,'en_US') AS label
FROM ir_ui_menu m JOIN ir_model_data d ON d.res_id=m.id AND d.model='ir.ui.menu'
WHERE m.parent_id = (SELECT res_id FROM ir_model_data
                     WHERE module='mail' AND name='menu_root_discuss')
ORDER BY m.sequence, m.id;"
```

Expected: đúng thứ tự 1 Discuss, 2 Channels, 3 Quản lý cuộc họp, 4 Lịch sử cuộc họp,
5 Configuration.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/views/calendar_event_views.xml \
        custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml \
        custom-addons/aidt_meeting_minutes/tests/test_ui_views.py
git commit -m "feat(meeting): add the meeting management menu, rename the log page"
```

---

### Task 8: Tài liệu

Quy ước dự án: tính năng chưa xong nếu `docs/GUIDANCE.md` chưa phủ.

**Files:**
- Modify: `docs/GUIDANCE.md` (mục 2)
- Modify: `custom-addons/aidt_meeting_minutes/README.md`

- [ ] **Step 1: Đọc trước khi viết**

Đọc `docs/GUIDANCE.md` mục 2 từ đầu tới hết §2.7. Đối chiếu **từng câu** với view XML và
template OWL thật — không viết theo trí nhớ, không viết theo spec. Đặc biệt kiểm:
`recording_banner.xml` (nhãn nút thật), `meeting_recording_views.xml` (tên menu thật).

- [ ] **Step 2: Sửa phần đang sai sẵn**

§2.5 và §2.6 mô tả nút **"Từ chối"** và giải thích vì sao băng thông báo còn lại sau khi
bấm nó. Nút đó **đã bị gỡ** ở nhánh `fix/meeting-stt-pipeline`. Xoá hai mục đó và mọi
tham chiếu tới "Từ chối" trong bảng mục lục đầu tài liệu.

- [ ] **Step 3: Viết phần hành vi mới**

Trong §2.3 ("Bật ghi âm"), viết lại theo đúng hành vi sau Task 4-7:

- Ghi âm **chỉ có trong phòng họp**. Kênh thường và tin nhắn trực tiếp không có nút.
- Phòng họp nằm ở mục **"Họp"** trong thanh bên Thảo luận, không còn lẫn trong
  "Tin nhắn trực tiếp".
- Cách tạo phòng họp: tích ô **"Phòng họp trực tuyến"** khi tạo cuộc họp (ở ứng dụng Lịch
  hoặc ở **Thảo luận → Quản lý cuộc họp**), hoặc bấm dấu **+** ở đầu mục "Họp" để họp ngay.
- Chỉ **người chủ trì** ghi trong lịch mới bấm được "Bật ghi âm biên bản".
- Bỏ tích ô "Phòng họp trực tuyến" **không xoá phòng** — nói rõ vì sao (phòng giữ lịch sử
  ghi âm), và nói cách bỏ phòng là xoá cuộc họp.
- Trang cũ đổi tên thành **"Lịch sử cuộc họp"**.

Thêm một dòng cảnh báo cho bản ghi cũ: những cuộc họp ghi trước bản này có thể không gắn
với mục nào trong Lịch, nên cột "Cuộc họp" của chúng trống — đó là bình thường, không phải
lỗi.

Cập nhật bảng mục lục đầu `docs/GUIDANCE.md` cho khớp.

- [ ] **Step 4: Cập nhật README của module**

Trong `custom-addons/aidt_meeting_minutes/README.md`, mục "đã/chưa kiểm chứng end-to-end",
thêm mục ngày **2026-08-11** ghi rõ:

- Đã kiểm bằng test tự động: chọn đúng buổi họp đang diễn ra; `aidt_has_room` tạo phòng một
  chiều; siết ghi âm về phòng họp; luật xếp mục thanh bên.
- Đã kiểm bằng mắt trong trình duyệt: mục "Họp", nút "+", hộp thoại họp ngay.
- **Chưa kiểm** end-to-end: một cuộc họp định kỳ thật chạy qua nhiều tuần; hành vi khi hai
  cuộc họp cùng kênh chồng giờ nhau.

- [ ] **Step 5: Commit**

```bash
git add docs/GUIDANCE.md custom-addons/aidt_meeting_minutes/README.md
git commit -m "docs(meeting): document meeting rooms, drop the removed decline flow"
```

---

## Sau khi xong hết

Chạy trọn ba bộ và đối chiếu với mốc:

```bash
# Odoo Python + hoot
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_meeting_minutes \
  --http-port=8073 --gevent-port=8074 \
  --test-enable --test-tags /aidt_meeting_minutes --stop-after-init

# Thư viện thuần Python (không đụng tới trong đợt này, chạy để chắc)
docker exec aidt-odoo-dev-odoo-1 bash -lc \
  'cd /opt/odoo && PYTHONPATH=custom-addons /opt/venv/bin/python3 -m pytest \
     custom-addons/aidt_search_engine/tests custom-addons/aidt_format_engine/tests -q'
```

Mốc: Python `1 failed, 0 error(s)` (wrapper hoot), hoot **đúng 9 đỏ**, pytest xanh hết.

Kiểm CSDL còn sạch:

```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d postgres -c "\l"
docker exec aidt-odoo-dev-odoo-1 ls /var/lib/odoo/filestore/
```

Cả hai chỉ được có `aidt_demo` (ngoài các CSDL hệ thống của Postgres).
