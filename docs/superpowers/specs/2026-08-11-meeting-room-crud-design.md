# Phòng họp là một loại kênh riêng — thiết kế (khối A)

**Ngày:** 2026-08-11
**Module:** `aidt_meeting_minutes` 19.0.1.3.1 → 19.0.1.4.0, có đụng `aidt_calendar` (chỉ view)
**Trạng thái:** đã duyệt thiết kế, chưa lập kế hoạch thực thi

## 1. Mục tiêu

Biến "cuộc họp" từ *một cuộc gọi ngẫu nhiên trong kênh bất kỳ* thành *một loại phòng có
vòng đời riêng*:

1. Tạo, sửa, xoá cuộc họp được từ một trang "Quản lý cuộc họp" trong ứng dụng Thảo luận,
   dữ liệu ăn khớp với Lịch và với Thảo luận.
2. Thanh bên Thảo luận có mục thứ ba **"Họp"**, cạnh "Kênh" và "Tin nhắn trực tiếp".
3. Ghi âm và biên bản AI **chỉ tồn tại trong phòng họp**. Kênh thường và tin nhắn trực
   tiếp không còn nút ghi âm.
4. Trang quản lý bản ghi hiện tại đổi tên thành **"Lịch sử cuộc họp"**.

## 2. Phạm vi

**Trong phạm vi (khối A):** toàn bộ mục 1.

**Ngoài phạm vi, ghi nhận để làm đợt sau:**

- **Khối B — vòng đời theo lịch:** trạng thái cuộc họp (sắp diễn ra / đang họp / đã xong),
  phòng chỉ mở trong khung giờ, nhắc trước giờ kèm nút vào phòng. Khối B phụ thuộc hoàn
  toàn vào khối A và sẽ có spec riêng.
- **Hàng đợi cho `docker/ai_worker`.** `create_job` và `process_meeting_task`
  (`docker/ai_worker/main.py:1069`) đều là hàm đồng bộ chạy trong threadpool của FastAPI,
  nên nhiều cuộc họp kết thúc cùng lúc sẽ cho ra nhiều lượt bóc băng chạy **song song
  thật** trên một GPU. `_whisper_model` (dòng 527) là biến toàn cục dùng chung, sửa không
  có khoá. Đo ngày 11/08/2026 với đúng một job: 14720/16311 MiB, và gemma3 đã phải đẩy 26%
  số lớp sang CPU vì thiếu chỗ. Rủi ro OOM là suy luận từ số đo thật, **chưa ai thử hai
  job đồng thời**.
- 5 bản ghi ở trạng thái `failed` chưa có đường xử lý lại.
- Hai lỗ hổng đã biết: `/aidt_meeting/api/webhook/summary/<id>` không xác thực, và
  `/aidt_meeting/audio/<id>` công khai kèm `cors='*'`.

## 3. Bối cảnh code hiện tại

Những sự thật dưới đây đã đọc từ code ngày 11/08/2026, không lấy từ tài liệu.

| Sự thật | Chỗ |
|---|---|
| `discuss.channel` đã có sẵn `calendar_event_ids = One2many("calendar.event", "videocall_channel_id")` | `addons/calendar/models/discuss_channel.py:9` |
| `calendar.event.videocall_channel_id` là Many2one tới `discuss.channel` | `addons/calendar/models/calendar_event.py:144` |
| Kênh **không** được tạo khi tạo `calendar.event`. `set_discuss_videocall_location` được chú thích thẳng là "dummy method... intercepted in the frontend" | `addons/calendar/models/calendar_event.py:1114-1116` |
| Cuộc họp định kỳ dùng **chung một kênh** cho mọi lần: `recurrent_events_without_channel.videocall_channel_id = videocall_channel` | `addons/calendar/models/calendar_event.py:1057-1078` |
| `calendar.event._order = "start desc"` | `addons/calendar/models/calendar_event.py:73` |
| `channel_type` chỉ có ba giá trị `chat` / `channel` / `group`; nhiều `@api.constrains` và domain trong `mail_security.xml` liệt kê cứng các giá trị này | `addons/mail/models/discuss/discuss_channel.py:69-73` |
| `_create_group()` đặt `channel_type='group'` | `addons/mail/models/discuss/discuss_channel.py:1528` |
| `group` và `chat` cùng rơi vào mục "Tin nhắn trực tiếp" | `addons/mail/static/src/discuss/core/public_web/thread_model_patch.js:58-68` |
| Mục trong thanh bên là `store.discuss.allCategories`, tập record phía client, **không** phải mảng cứng | `addons/mail/static/src/discuss/core/public_web/discuss_sidebar_categories.xml:3-9` |
| `im_livechat` đã thêm hai mục bằng cách patch `DiscussApp` — tiền lệ để làm theo | `addons/im_livechat/static/src/core/public_web/discuss_app_model_patch.js:57-84` |
| Template `mail.DiscussSidebarCategory.main` có điểm neo `name="header"` | `addons/mail/static/src/discuss/core/public_web/discuss_sidebar_categories.xml:34-35` |
| `_event_for_channel` hiện dùng `limit=1` không kèm `order` | `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:189-197` |
| `_start_for_channel` rẽ đôi: có lịch thì chỉ `event.user_id` bật được ghi âm, không có lịch thì chủ phòng cuộc gọi bật được | `custom-addons/aidt_meeting_minutes/models/meeting_recording.py:335-373` |
| Băng ghi âm chèn vào `discuss.Call`, sau `<PttAdBanner/>` | `custom-addons/aidt_meeting_minutes/static/src/recording_banner.xml:10-15` |
| Menu hiện tại: `menu_meeting_recording` sequence 3 trong Thảo luận, `mail.menu_configuration` đã bị đẩy xuống 4 | `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml:266-274` |
| `aidt_meeting_minutes` đã khai `aidt_calendar` trong `depends` | `custom-addons/aidt_meeting_minutes/__manifest__.py:76` |

## 4. Bất biến

> Một `discuss.channel` là **phòng họp** khi và chỉ khi `channel.calendar_event_ids` không rỗng.

Không thêm trường **lưu trữ** nào lên `discuss.channel`, và không thêm giá trị nào cho
`channel_type`. Trường `aidt_is_meeting_room` ở §5.3 là trường **tính, không lưu** — nó chỉ
chiếu `bool(calendar_event_ids)` sang phía client, không phải một dấu hiệu độc lập có thể
trôi khỏi sự thật.

Hệ quả: **mọi phòng họp đều có người chủ trì xác định** (`event.user_id`). Đây là lý do
chọn bất biến này thay vì một cờ boolean độc lập — nó xoá được nhánh "cuộc gọi tự phát"
trong `_start_for_channel`, chính nhánh đã sinh ra lỗi I1 ở nhánh trước (người vào sớm
khoá chết quyền của lãnh đạo chủ trì).

Hai phương án đã cân nhắc và loại:

- **`channel_type = 'meeting'`** — phải rà lại một SQL constraint, ba `@api.constrains` và
  nhiều domain trong `mail_security.xml` vốn liệt kê cứng `channel_type`. Giá trị mới rơi
  âm thầm vào nhánh "riêng tư" của các quy tắc đó; thường là hướng an toàn, nhưng "thường"
  không đủ với một hệ có độ mật tới `tuyệt_mật`. Và vẫn phải giữ hai nhánh chủ trì.
- **Cờ `is_meeting_room` trên `discuss.channel`** — tạo ra hai nguồn sự thật cho cùng một
  câu hỏi; xoá cuộc họp trong Lịch thì cờ vẫn bật.

## 5. Thiết kế

### 5.1 Ô "tạo phòng" — trường tính có nghịch đảo

Trên `calendar.event`, khai trong `aidt_meeting_minutes` (module quan tâm tới phòng họp;
`aidt_calendar` không cần biết gì về ghi âm):

```python
aidt_has_room = fields.Boolean(
    string='Phòng họp trực tuyến',
    compute='_compute_aidt_has_room',
    inverse='_inverse_aidt_has_room',
)
```

- `_compute_aidt_has_room` đọc `bool(rec.videocall_channel_id)`.
- `_inverse_aidt_has_room` **chỉ tạo, không bao giờ xoá**: bật mà chưa có phòng thì gọi
  `_create_videocall_channel()`; tắt thì không làm gì.

Không lưu trạng thái riêng, nên không có gì để trôi khỏi sự thật.

Một chiều là **cố ý**: phòng giữ lịch sử ghi âm và biên bản, gỡ nó đi là bỏ rơi các
`aidt.meeting.recording` trỏ vào một kênh không còn ai dùng. Muốn bỏ phòng thì xoá cuộc
họp. Trên form, ô này thành chỉ-đọc ngay khi `videocall_channel_id` có giá trị, kèm chú
thích nói rõ vì sao.

Odoo chạy `inverse` cả trong `create()`, nên đúng một trường này phục vụ cả "tích lúc tạo
lịch" lẫn "tạo phòng sau ở trang quản lý". Không cần hai cơ chế.

### 5.2 Chọn đúng buổi họp

Lỗi có sẵn: cuộc họp định kỳ dùng chung một kênh, mà `_event_for_channel` lại `limit=1`
không kèm `order`, nên rơi vào `_order = "start desc"` và **luôn trả về buổi xa nhất trong
tương lai**. Họp giao ban sáng nay trả về buổi giao ban tháng 12.

Bốn chỗ hỏng vì nó, cả bốn đều thật hôm nay: kiểm người chủ trì trong `_start_for_channel`;
`secrecy_at_start` chụp độ mật sai buổi (một buổi tương lai nâng lên `tuyệt_mật` là khoá
luôn ghi âm mọi buổi trước); `recording.event_id` trỏ sai; `_resolve_host_partner` chốt
chủ phòng theo buổi sai.

```python
@api.model
def _event_for_channel(self, channel, at=None):
    at = at or fields.Datetime.now()
    events = self.env['calendar.event'].sudo().search(
        [('videocall_channel_id', '=', channel.id)])
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

`len(events) <= 1` đứng trước để cuộc họp thường — tuyệt đại đa số — không trả giá cho việc
lọc. Hai chỗ gọi phải cập nhật: `_start_for_channel` và `_resolve_host_partner`.

### 5.3 Mục "Họp" trong thanh bên

Ba mảnh, theo đúng khuôn `im_livechat`:

1. Patch `DiscussApp` thêm một `DiscussAppCategory`: id `aidt_meeting_minutes.category_meetings`,
   tên `_t("Họp")`, `sequence: 20` — giữa "Kênh" (10) và "Tin nhắn trực tiếp" (30).
2. Patch `Thread._computeDiscussAppCategory()`: phòng họp trả về mục đó, còn lại `super()`.
3. Thêm trường tính **không lưu** `aidt_is_meeting_room` trên `discuss.channel` (đọc
   `bool(calendar_event_ids)`) và đẩy vào gói dữ liệu gửi client. Chỗ đặt đã có:
   `aidt_meeting_minutes/models/discuss_channel.py`.

   **Chưa kiểm chứng:** cơ chế chính xác để thêm một trường vào gói store của
   `discuss.channel` trong Odoo 19 chưa được xác minh — cần đọc `_to_store` / phần khai báo
   trường store của `addons/mail/models/discuss/discuss_channel.py` lúc làm. Đường lui nếu
   cơ chế đó tốn kém: client tự suy ra từ dữ liệu đã có sẵn trong store thay vì thêm trường
   mới. Bước đầu tiên của task này là xác minh, không phải viết code.

Hôm nay phòng họp rơi vào "Tin nhắn trực tiếp" (vì `channel_type='group'`). Sau thay đổi
chúng chuyển sang mục "Họp" — **người dùng thấy ngay, kể cả với phòng đã tồn tại từ trước**.

**Chưa kiểm chứng:** việc nhớ trạng thái đóng/mở của mục cần một trường mới trên
`res.users.settings` và trường đó phải tới được client. Upstream làm vậy cho hai mục kia
(`is_discuss_sidebar_category_channel_open`, `..._chat_open`), nhưng đường đi cho một mục do
addon ngoài thêm vào chưa được xác minh. Nếu lúc làm thấy phải plumb quá nhiều thì **bỏ phần
ghi nhớ, để mục luôn mở** — mất mát nhỏ, không đáng đánh đổi.

### 5.4 Menu và view dùng chung

Menu trong Thảo luận thành năm mục:

```
1  Thảo luận          mail.main_menu_discuss            (upstream)
2  Kênh               mail.menu_channel                 (upstream)
3  Quản lý cuộc họp   action mới trên calendar.event    ← thêm
4  Lịch sử cuộc họp   action_meeting_recording          ← đổi tên từ "Quản lý cuộc họp"
5  Cấu hình           mail.menu_configuration           (đẩy từ 4 xuống 5)
```

Ứng dụng Lịch không đổi gì. Quyền: **mọi người dùng nội bộ**, không thêm nhóm mới — quy tắc
độ mật và record rule của `aidt_calendar` vẫn chặn như cũ. Menu "Lịch sử cuộc họp" giữ nguyên
`group_meeting_minutes_manager`.

Action mới trỏ thẳng vào các view `aidt_calendar` đã có (`calendar_event_view_list_aidt`,
`calendar_event_view_kanban_aidt`, form và calendar upstream đã được kế thừa). **Không nhân
bản view.** Khác biệt duy nhất giữa hai cửa vào là thứ tự `view_mode`: Thảo luận mở danh sách
trước, Lịch mở lịch trước.

Ô `aidt_has_room` thêm vào form bằng một `t-inherit` thứ hai từ `aidt_meeting_minutes`
(`aidt_calendar` đã có `calendar_event_view_form_inherit` của nó).

### 5.5 Siết ghi âm về phòng họp

- `_start_for_channel`: sau khi kiểm tư cách thành viên, gọi `_event_for_channel(channel)`;
  rỗng thì `AccessError('Chỉ ghi âm được trong phòng họp.')`. Nhánh `else: secrecy = 'thuong'`
  biến mất.
- `action_active_recording`: hôm nay **luôn** trả `host_partner_id`, và đó là điều kiện duy
  nhất làm nút "Bật ghi âm biên bản" hiện ra. Với kênh không phải phòng họp phải trả rỗng.
  Không cần sửa OWL: `RecordingBanner.canStart` đã đòi `isHost`, mà `isHost` đòi
  `hostPartnerId`.
- `discuss_channel_rtc_session.create`: chỉ chốt `aidt_call_host_partner_id` cho phòng họp.
  Hôm nay nó ghi trường này cho mọi cuộc gọi, kể cả tin nhắn trực tiếp hai người, rồi không
  ai dùng.

### 5.6 Nút "Họp ngay"

Đặt ở đầu mục "Họp" trong thanh bên — dấu `+`, cùng vị trí và ý nghĩa với dấu `+` của mục
"Kênh"; điểm neo `name="header"` trong `mail.DiscussSidebarCategory.main`. Bấm vào mở form
cuộc họp dạng hộp thoại với `start` = bây giờ, `stop` = +1 giờ, `aidt_has_room` đã tích.

Nút này tồn tại để bù cho việc siết ghi âm: không có nó thì việc "bật ghi âm cho một trao đổi
phát sinh" mất hẳn.

## 6. Người dùng thấy gì khác

| Trước | Sau |
|---|---|
| Phòng họp nằm trong "Tin nhắn trực tiếp" | Nằm trong mục "Họp" |
| Mọi cuộc gọi Discuss đều bật ghi âm được | Chỉ phòng họp |
| Tạo cuộc họp ở Lịch hoặc Thảo luận | Thêm cửa "Quản lý cuộc họp"; Lịch vẫn tạo được như cũ |
| "Quản lý cuộc họp" = danh sách bản ghi | "Lịch sử cuộc họp" = danh sách bản ghi |
| Không có ô tạo phòng khi tạo lịch | Có ô "Phòng họp trực tuyến" |

## 7. Tương thích ngược

Không cần script migration.

- Phòng họp đã tồn tại: `calendar_event_ids` đã có sẵn từ upstream, nên chúng tự động được
  nhận là phòng họp và tự chuyển sang mục "Họp".
- Bản ghi cũ trên kênh không phải phòng họp: **không xoá**, vẫn hiện trong "Lịch sử cuộc
  họp", `event_id` rỗng. Danh sách phải chịu được điều đó.
- `menu_meeting_recording` chỉ đổi nhãn và sequence, giữ nguyên xml_id.

## 8. Kiểm thử và mốc nghiệm thu

**Python (`aidt_meeting_minutes/tests/`):**

- `_event_for_channel` ba nấc, trên một cuộc họp định kỳ **ba buổi dùng chung một kênh**:
  đang diễn ra / sắp tới / vừa qua. Đây là ca lỗi trung tâm, phải có test riêng.
- Đường tắt một-sự-kiện trả về đúng bản ghi đó.
- `aidt_has_room` tạo phòng đúng một lần; bỏ tích không xoá gì.
- `_start_for_channel` từ chối kênh không phải phòng họp.
- `_resolve_host_partner` chốt chủ phòng theo buổi đang diễn ra.

**Hoot (`static/tests/`):**

- Kênh phòng họp rơi vào mục "Họp"; kênh thường vẫn ở mục cũ.
- Nút "Bật ghi âm biên bản" vắng mặt khi `action_active_recording` trả rỗng.

**Phải viết lại:** `test_host_control.py` và `test_recording_auth.py` dựng bản ghi trên kênh
không có lịch — chúng mã hoá đúng hành vi đang bị bỏ. Phải gắn `calendar.event` vào kênh.
Việc thật, tính vào kế hoạch.

**Mốc nghiệm thu:** `recorder.test.js` đang đỏ sẵn **đúng 9 test** (mute gating 6, chồng lấn
3). Sau khi xong phải vẫn đúng 9, không hơn. Hoot **bỏ qua chứ không báo trượt** khi thiếu
chromium hoặc `websocket-client`, nên 0 assertion không có nghĩa là đã qua.

## 9. Tài liệu

`docs/GUIDANCE.md` §2 phải viết lại phần "Bật ghi âm" theo hành vi mới.

§2 **đang sai sẵn**: nó vẫn mô tả nút "Từ chối" đã bị gỡ ở nhánh `fix/meeting-stt-pipeline`,
kèm cả một mục riêng giải thích vì sao băng thông báo còn lại sau khi từ chối. Để nguyên thì
tài liệu tự mâu thuẫn với đoạn mới. Sửa luôn trong đợt này.

`aidt_meeting_minutes/README.md` cập nhật phần "đã/chưa kiểm chứng end-to-end" kèm ngày.

## 10. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Trường ghi nhớ đóng/mở mục "Họp" cần plumb quá nhiều | Bỏ, để mục luôn mở |
| Người dùng mất thói quen ghi âm cuộc gọi phát sinh | Nút "Họp ngay" |
| Nhiều cuộc họp kết thúc cùng lúc gây OOM ở worker | **Không xử lý trong khối A.** Ghi nhận ở §2 |
| Patch `Thread._computeDiscussAppCategory` xung đột với addon khác cũng patch nó | Gọi `super()` cho mọi trường hợp không phải phòng họp |
