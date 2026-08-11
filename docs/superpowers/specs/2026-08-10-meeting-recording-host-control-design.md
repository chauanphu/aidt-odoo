# Ghi âm cuộc họp: chủ phòng điều khiển, thông báo bắt buộc, tạm dừng và ghi tiếp

**Ngày:** 10/08/2026
**Module:** `aidt_meeting_minutes` (19.0.1.2.1 → **19.0.1.3.0**)
**Trạng thái:** thiết kế đã duyệt, chưa lập kế hoạch thực thi

---

## 1. Vấn đề

Cơ chế ghi âm hiện tại phân tán quyền điều khiển cho mọi người tham gia, và ba điều
dưới đây đã được kiểm chứng trực tiếp trên code cùng dữ liệu `aidt_demo`:

**Không ai thật sự là chủ phòng.** `_start_for_channel` chỉ chặn khi cuộc gọi gắn với
một `calendar.event` — lúc đó bắt buộc là `event.user_id`. Nhưng truy vấn toàn bộ bản
ghi trên `aidt_demo` cho thấy **`event_id` rỗng ở 100%**, kể cả kênh mang tên "Họp
hàng tuần" (đó là tên *kênh*, không phải cuộc họp có lịch). Nghĩa là nhánh "chỉ chủ trì
mới bật được ghi âm" **chưa từng chạy lần nào**; mọi cuộc gọi đều rơi vào nhánh `else`,
nơi bất kỳ thành viên kênh nào cũng bật được.

**Một người rời cuộc gọi là cả bản ghi dừng.** Đường đi: rời cuộc gọi → `Rtc.clear()` →
`recorder.leaveCall()` → `stop()` → `POST /aidt_meeting/api/finalize_recording` →
`action_stop()` cho *toàn bộ* bản ghi. Người vô tình đóng tab ở phút thứ 5 làm cả cuộc
họp mất phần còn lại của biên bản.

**Không có cách nào ngưng ghi một đoạn.** Cuộc họp chuyển sang nội dung không nên vào
biên bản thì lựa chọn duy nhất là kết thúc hẳn — và không bật lại được, vì chỉ mục
`aidt_meeting_recording_channel_active_uniq` chặn bản ghi thứ hai trên cùng kênh.

## 2. Phạm vi

**Làm:** siết quyền bật/tạm dừng/ghi tiếp/kết thúc về chủ phòng; thông báo bắt buộc cho
mọi người dự kể cả người vào sau; tạm dừng và ghi tiếp trong cùng một bản ghi; đưa mốc
tạm dừng tới AI và tới người đọc biên bản.

**Không làm:** khử trùng lặp chéo luồng khi nhiều người ngồi chung phòng (rủi ro đã
biết, ghi ở §12); xác thực webhook `/aidt_meeting/api/webhook/summary/<id>` và bảo vệ
`/aidt_meeting/audio/<id>` (hai lỗ hổng đã biết, thuộc đợt riêng); viết lại bộ hoot
`recorder` đang đỏ.

## 3. Các quyết định và lý do

| Quyết định | Lý do |
|---|---|
| Chủ phòng = **người vào cuộc gọi đầu tiên** trên kênh | Khớp cách dùng thật (100% cuộc gọi không có lịch). Buộc phải có `calendar.event` sẽ chặn toàn bộ quy trình đang chạy. Lấy `create_uid` của kênh thì sai bản chất: người tạo kênh "general" một năm trước không phải người chủ trì cuộc họp hôm nay và có thể không có mặt. |
| Người dự **không có nút nào** | Yêu cầu nghiệp vụ: ghi âm là bắt buộc. Kéo theo `declined_partner_ids` thành dữ liệu chết. |
| Kết thúc khi **chủ phòng bấm HOẶC cuộc gọi trống** | Chỉ dựa vào thao tác của chủ phòng thì chủ phòng đóng tab là bản ghi treo vĩnh viễn ở `recording`, và chỉ mục duy nhất chặn luôn mọi bản ghi mới trên kênh đó. Chọn "chủ phòng rời thì kết thúc" cũng sai: rớt wifi 5 giây sẽ chẻ cuộc họp thành hai biên bản. |
| Tạm dừng **dừng hẳn `MediaRecorder`**, không phải thu rồi vứt | Không sinh ra dữ liệu thì không có gì để rò rỉ — không phụ thuộc vào việc code nhớ vứt đúng chỗ. Chi phí bằng không vì đã có `take`. |
| Đánh số `take` thay vì suy khoảng trống từ `offset_ms` | Xem §4.4 — nếu không có `take` thì audio sau lần ghi tiếp **không giải mã được**. Và khoảng trống suy ra được cũng không phân biệt nổi dừng cố ý với mất mạng. |

**Tạm dừng chỉ dừng thu biên bản. Cuộc gọi không bị đụng tới** — mọi người vẫn nghe và
nói với nhau bình thường. Trong kiến trúc này có hai luồng mic riêng: track của WebRTC
(`rtc.state.micAudioTrack`, truyền tiếng cho người khác) và luồng `getUserMedia` riêng
mà `recorder_service` tự mở để ghi. Tạm dừng chỉ đóng luồng thứ hai.

> Lưu ý cho ai đọc sau: đừng lập luận rằng nhả luồng recorder làm **đèn báo mic của
> trình duyệt tắt** để người dự tự xác minh. Điều đó **không đúng** — cuộc gọi vẫn giữ
> mic để truyền tiếng nên đèn vẫn sáng bất kể ghi âm đang chạy hay đã dừng.

## 4. Mô hình dữ liệu

### 4.1. Chủ phòng lưu ở đâu

Odoo không có khái niệm chủ phòng cho cuộc gọi, nên ta **chốt tại thời điểm cuộc gọi
bắt đầu** chứ không suy ra sau:

- `discuss.channel` thêm `aidt_call_host_partner_id` (Many2one `res.partner`).
- `_inherit` `discuss.channel.rtc.session`:
  - `create()`: khi đây là phiên **đầu tiên** trên kênh — Odoo đã tính sẵn điều kiện
    `len(c.rtc_session_ids) == 1` ở `discuss_channel_rtc_session.py:51` — ghi partner đó
    làm chủ phòng.
  - `unlink()`: Odoo đã tính sẵn `call_ended_channels` ở dòng 66; cuộc gọi trống thì
    xoá trường này **và** kết thúc bản ghi đang hoạt động (§5).

Chủ phòng rớt mạng rồi vào lại mà **vẫn còn người khác trong cuộc gọi** thì giữ nguyên
chủ phòng — trường chỉ bị xoá khi cuộc gọi thật sự trống.

### 4.2. `aidt.meeting.recording`

| Thay đổi | Chi tiết |
|---|---|
| `state` | thêm `paused`: `recording · paused · processing · done · failed · cancelled` |
| `host_partner_id` | **mới**, readonly. Chụp lại chủ phòng lúc bật ghi. Cố ý **không** dùng `related` tới kênh: chủ phòng của kênh đổi được sau đó, còn "ai đã bật bản ghi này" là dữ kiện lịch sử của biên bản. |
| `declined_partner_ids` | **gỡ** — không còn nút Từ chối |
| `pause_ids` | **mới**, One2many tới `aidt.meeting.pause` |
| `pause_summary` | **mới**, compute, không lưu — chuỗi hiển thị "2 đoạn không được ghi · tổng 7 phút 12 giây" |
| chỉ mục duy nhất | `WHERE state IN ('recording','paused','processing')` — thêm `paused`, nếu không thì đang tạm dừng lại bật được bản ghi thứ hai trên cùng kênh |

### 4.3. `aidt.meeting.pause` (mới)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `recording_id` | Many2one, ondelete cascade, required | |
| `paused_at_ms` | Integer, required | Cùng trục thời gian với `offset_ms` của mẩu audio |
| `resumed_at_ms` | Integer | Rỗng khi đang tạm dừng hoặc khi bản ghi kết thúc trong lúc dừng |
| `paused_by_id` | Many2one `res.users`, readonly | Ai bấm — phục vụ truy vết, dù hiện chỉ chủ phòng bấm được |

Quyền: đọc cho `base.group_user`, toàn quyền cho
`aidt_meeting_minutes.group_meeting_minutes_manager` — cùng khuôn với
`aidt.meeting.action.item`.

### 4.4. `aidt.meeting.chunk` — vì sao phải có `take`

Thêm `take` (Integer, mặc định 0). Khoá duy nhất đổi từ
`(recording_id, partner_id, seq)` thành `(recording_id, partner_id, take, seq)`; `seq`
đếm lại từ 0 mỗi lần ghi tiếp.

Đây **không phải** để cho gọn dữ liệu. Khi tạm dừng, client gọi `MediaRecorder.stop()`;
lúc ghi tiếp nó tạo một `MediaRecorder` **mới**, và luồng mới mang **EBML header
riêng**. Pipeline hiện nối các mẩu ở mức byte theo `seq`
(`docker/ai_worker/main.py::assemble_speaker_stream`), nên nối xuyên qua ranh giới tạm
dừng cho ra một tệp có header nằm giữa: ffmpeg giải mã được phần đầu rồi dừng, **im
lặng mất toàn bộ phần sau lần ghi tiếp**. `take` là thứ cho worker biết chỗ nào được
phép nối và chỗ nào không.

## 5. Vòng đời và phân quyền

```
       ┌──────────────── chủ phòng [Tạm dừng] ───────────────┐
       ▼                                                     │
  recording ◄──────── chủ phòng [Ghi tiếp] (take+1) ──── paused
       │                                                     │
       └──── [Kết thúc] hoặc cuộc gọi trống ─────┬───────────┘
                                                 ▼
                                            processing → done | failed
```

Tạm dừng cũng kết thúc được — không bắt chủ phòng phải ghi tiếp rồi mới dừng được.

| Hành động | Ai | Ghi chú |
|---|---|---|
| Bật ghi âm | Chỉ chủ phòng | Cuộc họp có lịch vẫn ưu tiên `event.user_id` như code hiện có |
| Tạm dừng / Ghi tiếp | Chỉ chủ phòng | |
| Kết thúc | Chủ phòng **hoặc** hệ thống khi cuộc gọi trống | Cùng một hàm nội bộ, hai đường gọi |
| Từ chối | **Không còn** | |
| Gửi mẩu audio | Mọi người có mặt trong cuộc gọi | Giữ nguyên `_is_participant` |

**Phải gỡ:** endpoint `/aidt_meeting/api/finalize_recording`. Nó kết thúc cả bản ghi khi
bất kỳ ai rời cuộc gọi (§1), mâu thuẫn trực tiếp với thiết kế này. Việc đợi mẩu cuối đã
do độ trễ 10 giây trong `action_stop` lo, và điểm kết thúc giờ chỉ còn hai nguồn ở bảng
trên.

## 6. Giao diện

Người dự **luôn thấy trạng thái thật**, kể cả lúc tạm dừng. Giấu trạng thái tạm dừng
còn tệ hơn không hiện gì: người ta sẽ giữ ý trong khi thực ra không bị ghi, hoặc nói
thoải mái vì tưởng đang dừng.

```
NGƯỜI DỰ — đang ghi                    CHỦ PHÒNG — đang ghi
┌────────────────────────────┐         ┌────────────────────────────────┐
│ ● Cuộc họp đang được ghi âm│         │ ● Đang ghi âm  05:12           │
│   để tạo biên bản.         │         │      [Tạm dừng]  [Kết thúc]    │
└────────────────────────────┘         └────────────────────────────────┘

NGƯỜI DỰ — tạm dừng                    CHỦ PHÒNG — tạm dừng
┌────────────────────────────┐         ┌────────────────────────────────┐
│ ⏸ Ghi âm đang tạm dừng.    │         │ ⏸ Tạm dừng từ 05:12            │
│   Cuộc họp vẫn tiếp tục.   │         │      [Ghi tiếp]  [Kết thúc]    │
└────────────────────────────┘         └────────────────────────────────┘
```

Bus phát **một payload chung** cho mọi người (không cá nhân hoá được), nên payload mang
`host_partner_id` và mỗi client tự so với partner của chính mình (`mail.store.self`) để
chọn dạng băng.

Nút **"Mock Audio (Dev)"** gỡ luôn — nó là đường nạp tệp audio tuỳ ý vào biên bản, không
nên tồn tại trên bản chạy thật.

**Người vào trước / vào sau / vào giữa lúc tạm dừng:**

| | Cơ chế |
|---|---|
| Vào **trước** khi bật | Nhận bus `started` → băng hiện |
| Vào **sau** khi bật | `joinCall` → `syncActiveRecording()` → hỏi server |
| Vào **giữa lúc tạm dừng** | Cùng đường trên, nhưng `action_active_recording` phải tìm `state in ('recording','paused')` — hiện chỉ tìm `'recording'`, nên người vào lúc dừng **không thấy gì** và tưởng cuộc họp không được ghi |

`action_active_recording` trả thêm `state`, `host_partner_id`, `take` để client dựng đúng
băng và biết phải thu ngay hay chờ `resumed`.

**Trên form bản ghi** thêm mục liệt kê các đoạn dừng (`05:12 → 08:40 · 3 phút 28 giây`),
để người đọc biên bản biết biên bản này **không phủ hết cuộc họp** — điều này ảnh hưởng
tới giá trị pháp lý của biên bản, không phải chi tiết trang trí.

## 7. Luồng client

Khi tạm dừng, client **không** đặt lại mốc gốc:

```js
// GIỮ NGUYÊN qua tạm dừng — offset là giờ tường kể từ lúc bắt đầu ghi
offset_ms = elapsedAtJoinMs + (performance.now() - recorderStartedAt)

// ĐẶT LẠI mỗi lần ghi tiếp
take += 1;   seq = 0;
```

`performance.now()` vẫn chạy trong lúc tạm dừng, nên khoảng dừng tự thành **khoảng trống
thật** trên trục thời gian. Nhờ vậy mốc `[08:40]` trong biên bản là 8 phút 40 giây kể từ
lúc bắt đầu họp, không phải "phút thứ 8 của phần đã ghi" — và các luồng của những người
vào ở thời điểm khác nhau vẫn khớp nhau.

`take` đi kèm trong mỗi lần upload; controller chuyển tiếp xuống `_store`.

**`stop()` phía client không còn gọi `finalize_recording`** (endpoint đã gỡ ở §5). Nó
vẫn giữ nguyên phần quan trọng: dừng `MediaRecorder`, bắt mẩu cuối trong `ondataavailable`,
rồi vét hết hàng đợi `pending` trước khi buông. Chỉ bỏ lượt `fetch` cuối cùng.

Tạm dừng dùng **cùng đường vét đó** nhưng **không** xoá `state.recordingId`: bản ghi vẫn
đang hoạt động, chỉ là không thu nữa. Đây là khác biệt duy nhất giữa "tạm dừng" và "kết
thúc" ở phía client, và cũng là chỗ dễ viết nhầm nhất.

**Đồng hồ trên băng** chạy theo giờ tường kể từ lúc bắt đầu, trùng đúng trục của biên
bản — chủ phòng thấy `05:12` thì mốc trong biên bản cũng là `05:12`. Lúc tạm dừng thì
đóng băng và đổi chữ thành "Tạm dừng từ 05:12"; lúc ghi tiếp, số nhảy lên giá trị giờ
tường thật. Bước nhảy đó là cố ý — nó phản ánh khoảng thời gian thật sự không có trong
biên bản.

## 8. Ranh giới tạm dừng bảo đảm ở **server**

Mẩu audio đang bay trên đường lúc bấm tạm dừng vẫn phải được nhận. Chặn ở `_store` thì
mọi lần tạm dừng đều mất tới 30 giây lời nói ngay trước đó — đúng cái bẫy đã gặp với
`processing` (xem khối comment ở `meeting_chunk.py:48-53`). Nên `_store` vẫn nhận mẩu ở
`recording`, `paused` và `processing`.

Đổi lại, **worker cắt audio tại `paused_at_ms`** khi ghép take đó, bằng
`-t (paused_at_ms − take.offset_ms)`. Dù client có lỗi hay bị can thiệp mà gửi thêm
audio sau thời điểm tạm dừng, phần đó **không thể** lọt vào biên bản. Bảo đảm nằm ở chỗ
ghép, không nằm ở chỗ nhận.

## 9. Worker

`metadata.json` đổi từ phẳng sang hai tầng:

```json
{
  "speakers": [
    {"partner_id": 3, "speaker_name": "Administrator", "takes": [
      {"take": 0, "offset_ms": 34,     "files": ["spk3_t0_00000.webm", "spk3_t0_00001.webm"]},
      {"take": 1, "offset_ms": 520000, "files": ["spk3_t1_00000.webm"]}
    ]}
  ],
  "pauses": [{"paused_at_ms": 312000, "resumed_at_ms": 520000}]
}
```

Tên tệp đổi từ `spk{partner_id}_{seq:05d}.webm` thành
`spk{partner_id}_t{take}_{seq:05d}.webm` — `seq` đếm lại từ 0 mỗi take nên nếu không có
`t{take}` trong tên thì lần ghi tiếp sẽ **ghi đè** tệp của lần trước.

Mỗi `(người, take)` là **một luồng độc lập**: nối byte trong phạm vi take → giải mã →
WAV → bóc băng riêng. `abs_start = take.offset_ms + seg.start × 1000`. Trộn để nghe lại
(`amix` + `adelay`) giữ nguyên nguyên tắc, chỉ là nhiều luồng đầu vào hơn.

Worker phải giữ khả năng đọc **khuôn dạng cũ** (danh sách phẳng, không có `takes`) để
job đã nằm sẵn trên đĩa vẫn chạy lại được — `_load_speakers` hiện đã có nhánh tương thích
tương tự.

## 10. Mốc tạm dừng cho AI — hai lớp

**Lớp 1 — mốc trong transcript**, chèn đúng vị trí thời gian khi trộn segment:

```
[05:08] Nguyễn Văn An: Phần này em xin phép trao đổi riêng.
--- TẠM DỪNG GHI ÂM 05:12 → 08:40 (3 phút 28 giây không được ghi) ---
[08:41] Administrator: Quay lại nội dung ban nãy, ta chốt thế này.
```

**Lớp 2 — luật trong `SYSTEM_PROMPT`:**

> Transcript có thể chứa dòng `--- TẠM DỪNG GHI ÂM ... ---`. Đó là khoảng thời gian
> KHÔNG được ghi. Tuyệt đối không suy diễn nội dung trong khoảng đó và không nối hai bên
> thành một mạch liên tục. Nếu một công việc hoặc quyết định chỉ có thể suy ra từ phần
> bị thiếu thì BỎ QUA.

Chỉ có lớp 1 thì model vẫn dễ nối liền hai bên; chỉ có lớp 2 thì nó không biết chỗ nào
mà tránh.

**Đoạn dừng không có `resumed_at_ms`** (chủ phòng kết thúc trong lúc đang tạm dừng) dựng
mốc khác, đặt ở cuối transcript:

```
--- TẠM DỪNG GHI ÂM 05:12 — không ghi tiếp cho tới hết cuộc họp ---
```

Không được bịa một mốc kết thúc: ta biết lúc dừng, không biết cuộc họp còn kéo dài bao
lâu sau đó.

## 11. Migration `19.0.1.3.0` — bốn việc

**1. Chỉ mục duy nhất một phần không tự cập nhật.** `init()` dùng
`CREATE UNIQUE INDEX IF NOT EXISTS aidt_meeting_recording_channel_active_uniq`. Khi mệnh
đề `WHERE` đổi (thêm `paused`), lệnh đó **không làm gì cả** và chỉ mục cũ ở lại.
Migration phải `DROP INDEX IF EXISTS aidt_meeting_recording_channel_active_uniq` tường
minh, rồi `init()` tạo lại đúng.

**2. Đổi khoá duy nhất của chunk.** `DROP CONSTRAINT IF EXISTS
aidt_meeting_chunk_seq_uniq` trước, để Odoo tạo lại theo định nghĩa mới có `take`. Không
gỡ trước thì mọi lần ghi tiếp đều đụng khoá cũ.

**3. Cột `take`.** Thêm với mặc định 0 — bản ghi cũ đều là một lần ghi liền mạch, nên
`take = 0` đúng ngữ nghĩa, không phải giá trị lấp chỗ.

**4. Dọn bảng chết.** `DROP TABLE IF EXISTS aidt_meeting_recording_res_partner_rel`
(quan hệ của `declined_partner_ids`) và `DROP TABLE IF EXISTS aidt_meeting_segment` —
bảng sau là tàn dư của đợt chuyển sang xử lý theo lô, model đã xoá từ lâu mà bảng vẫn
còn trong `aidt_demo`.

> Cùng họ với ba cái bẫy `noupdate` đã cắn ở 19.0.1.0.1, 19.0.1.1.0 và 19.0.1.2.0: thay
> đổi ở tầng định nghĩa **không** tự tới được cơ sở dữ liệu đã cài.

## 12. Kiểm thử

**Odoo** — phân quyền và vòng đời là phần dễ hỏng nhất:

- Người không phải chủ phòng bấm bật / tạm dừng / ghi tiếp / kết thúc → `AccessError`
  (bốn ca riêng).
- Tạm dừng tạo một dòng `aidt.meeting.pause`; ghi tiếp điền `resumed_at_ms` và tăng
  `take`.
- Người vào **giữa lúc tạm dừng** → `action_active_recording` trả `state='paused'`
  (canh đúng ca hiện đang hỏng).
- Cuộc gọi trống → bản ghi chuyển `processing`.
- **Người dự rời cuộc gọi → bản ghi VẪN chạy.** Canh riêng khiếm khuyết đang có hôm nay.
- Đang `paused` mà bật bản ghi thứ hai trên cùng kênh → bị chặn.
- Cùng `seq` ở hai `take` khác nhau → lưu được.
- Bản ghi kết thúc trong lúc đang tạm dừng → `resumed_at_ms` để rỗng, không dựng mốc lỗi.

**Worker** (pytest, không cần GPU, dựng từ dữ liệu thật như `test_filters.py`):

- Gom `(người, take)` đúng nhóm; nối byte không xuyên take.
- Cắt tại `paused_at_ms`.
- Mốc tạm dừng chèn đúng vị trí thời gian giữa hai segment, đúng khuôn chữ.
- Đọc được `metadata.json` khuôn dạng cũ.

**JS**: băng ở ba trạng thái × hai vai (chủ phòng / người dự).

> Bộ hoot `recorder` hiện **đỏ sẵn 9 test** vì lệch với đợt refactor chunked-upload
> trước đó — chúng gọi `_onAudio`, `retainOverlap`, `carriedStartAt`, cả ba không còn
> tồn tại trong `recorder_service.js`. Phần này phải viết lại chứ không sửa vá, và nằm
> ngoài phạm vi spec này.

## 13. Rủi ro và phần chưa giải quyết

**Hai người ngồi chung một phòng.** Mic của mỗi người bắt được cả giọng người kia, nên
cùng một câu có thể bị bóc hai lần và gán cho hai người. Pipeline giả định mỗi người một
máy ở nơi khác nhau. Chưa quan sát thấy ở bản ghi 2858 (luồng của Administrator chỉ ra 8
segment và toàn là lời của chính người đó), nên đây là rủi ro suy ra từ kiến trúc, chưa
phải sự cố đã xảy ra. Hướng xử lý nếu cần: so trùng văn bản giữa các luồng trong cửa sổ
thời gian chồng nhau, giữ luồng có RMS cao hơn.

**Mốc thời gian thô do `vad_filter`.** faster-whisper cắt khoảng lặng rồi ánh xạ mốc
ngược lại, và phép ánh xạ đó thô — ở bản ghi 2858, một câu ngắn được gán khoảng
`0.4 → 14.4` giây. Hệ quả: thứ tự chèn giữa hai người có thể lệch vài giây, và mốc tạm
dừng trong transcript có thể rơi lệch một câu. Chấp nhận được với biên bản hành chính;
muốn chính xác hơn thì bật `word_timestamps=True` (chậm hơn).

**Chủ phòng không có mặt.** Nếu người vào cuộc gọi đầu tiên rời đi trong khi những người
khác họp tiếp, không ai bật được ghi âm mới cho tới khi cuộc gọi trống rồi lập lại. Đây
là hệ quả trực tiếp của lựa chọn ở §3 và đã được chấp nhận.

**Độ trễ 10 giây khi kết thúc** vẫn là con số ước lượng, không phải kết quả đo. Nó đợi
mẩu cuối của mọi máy tới nơi. Máy có mạng chậm hơn 10 giây vẫn mất đoạn kết — chưa có
cơ chế xác nhận từng client đã gửi xong.
