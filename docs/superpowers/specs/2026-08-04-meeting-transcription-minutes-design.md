# Ghi âm, bóc băng và tóm tắt cuộc họp Discuss Meet

**Ngày:** 2026-08-04
**Module:** `custom-addons/aidt_meeting_minutes`
**Trạng thái:** Thiết kế đã chốt, chưa triển khai

## 1. Mục tiêu

Cuộc họp trực tuyến trong Odoo Discuss được ghi âm, bóc băng thành transcript
có ghi rõ người nói, và tóm tắt bằng tiếng Việt. Áp dụng cho cả cuộc họp có
lịch lẫn cuộc gọi tự phát / gọi trực tiếp. Kết quả được đăng vào chatter của
`calendar.event` nếu cuộc gọi thuộc một cuộc họp có lịch, ngược lại đăng thẳng
vào channel nơi cuộc gọi diễn ra.

Ngoài phạm vi (để dành cho spec sau):

- Phụ đề trực tiếp trong giao diện cuộc gọi.
- Tự động bóc tách nhiệm vụ (`project.task`) từ kết luận cuộc họp.
- Sinh biên bản chính thức (`aidt.document`) và đưa vào luồng trình ký.
- Cuộc họp trực tiếp tại phòng họp (`room_id`) — không đi qua WebRTC.

"Trực tiếp" ở đây chỉ có nghĩa là audio được đẩy lên liên tục trong lúc họp để
transcript sẵn sàng ngay sau khi cuộc gọi kết thúc. Không có gì hiển thị theo
thời gian thực.

## 2. Bối cảnh kỹ thuật

Đã kiểm chứng trực tiếp trên cây nguồn Odoo 19 trong repo này:

- Media **không bao giờ đi qua server Python**. Odoo chỉ làm signalling qua bus
  websocket (`addons/mail/controllers/discuss/rtc.py`). Audio đi P2P hoặc qua
  SFU ngoài.
- Odoo chạy **đồng thời** P2P và SFU (`class Network`,
  `addons/mail/static/src/discuss/call/common/rtc_service.js:107-213`). SFU chỉ
  bật từ 3 người trở lên (`SFU_MODE_THRESHOLD = 3`,
  `addons/mail/models/discuss/discuss_channel_member.py:19`), và tự động lùi về
  P2P nếu cấp phát SFU thất bại.
- Micro cục bộ: `getUserMedia` tại `rtc_service.js:2087`, track nằm ở
  `this.state.micAudioTrack`. Tắt tiếng và push-to-talk hoạt động bằng cách bật
  tắt `track.enabled` (`rtc_service.js:2107`), không đàm phán lại.
- Audio của người khác: mỗi phiên có `session.audioElement` với
  `srcObject = stream` (`rtc_service.js:2196-2204`). Các phần tử `Audio()` này
  **không nằm trong DOM**.
- Tiền lệ sẵn có trong Odoo cho việc thu và xử lý audio:
  `addons/mail/static/src/utils/common/media_monitoring.js:24-56` (clone track,
  AudioContext riêng, AudioWorklet) và
  `addons/mail/static/src/discuss/voice_message/common/voice_recorder.js:92-131`
  (AudioWorklet → `Mp3Encoder` → attachment).
- Liên kết cuộc gọi với cuộc họp: `calendar.event.videocall_channel_id` →
  `discuss.channel` (`addons/calendar/models/calendar_event.py:144`).
- `aidt_calendar` đã mở rộng `calendar.event` với `secrecy` (Thường / Mật /
  Tối mật / Tuyệt mật), `room_id`, `department_id`, `document_id`
  (`custom-addons/aidt_calendar/models/calendar_event.py:10-27`).
- Quy ước gọi dịch vụ AI tương thích OpenAI đã có:
  `custom-addons/aidt_search_engine/extract/ocr.py:92`.

Hiện **không có** tính năng ghi âm nào trong cây nguồn: không dùng
`MediaRecorder` ở đâu, không có addon `voip`.
`addons/mail/models/discuss/discuss_call_history.py` chỉ lưu metadata.

## 3. Phương án thu âm: mỗi máy tự thu micro của mình

Ba phương án đã cân nhắc:

| Phương án | Kết luận |
|---|---|
| Máy chủ trì thu tất cả | Loại. Audio người khác đã qua nén Opus và mất gói — chất lượng nhận dạng kém. Đóng tab là mất bản ghi. |
| Trộn tất cả thành một luồng | Loại. Mất hoàn toàn thông tin ai nói, phải diarization mới lấy lại được. |
| **Mỗi máy tự thu micro của mình** | **Chọn.** |

Lý do chọn:

- **Gán người nói là chính xác về mặt cấu trúc**, không phải suy đoán: mỗi
  chunk audio đến từ đúng một người đã biết.
- **Chất lượng audio tốt nhất có thể** — thu micro thô trước khi nén Opus và
  trước khi đi qua mạng.
- **Chi phí mỗi máy thấp**: mỗi máy mã hoá đúng một luồng.
- **Hỏng cục bộ**: một người rời họp thì chỉ audio của người đó dừng.
- **Câu chuyện đồng thuận sạch hơn**: máy của mỗi người ghi giọng của chính họ.

Đánh đổi: nhiều luồng upload hơn, và cần xử lý thứ tự chunk cùng lệch đồng hồ
giữa các máy (xem §5).

## 4. Kiến trúc và ranh giới phạm vi

Module mới `custom-addons/aidt_meeting_minutes`, phụ thuộc `mail`, `calendar`,
`aidt_calendar`. Không fork `rtc_service.js` — phía client là OWL patch, phía
server là model mới cộng một controller.

**Phạm vi: mọi cuộc gọi Discuss đều ghi âm được**, gồm cả cuộc gọi tự phát và
cuộc gọi trực tiếp (DM). Có hai trường hợp, khác nhau ở chỗ lấy độ mật và ai
được bật:

| | Cuộc họp có lịch | Cuộc gọi tự phát |
|---|---|---|
| Nhận biết | channel truy ngược được về `calendar.event` qua `videocall_channel_id` | không có `calendar.event` |
| Độ mật | lấy từ `event.secrecy` | coi như `thuong` |
| Ai bật được | người chủ trì cuộc họp | **bất kỳ thành viên nào** của channel |
| Nơi đăng kết quả | chatter của `calendar.event` | tin nhắn trong chính channel |

Cuộc gọi tự phát được coi là `thuong` vì không có gì để phân loại nó. Hệ quả:
ngưỡng độ mật không kiểm soát được cuộc gọi tự phát — nếu hai người bàn nội
dung Mật trong một cuộc gọi DM, hệ thống không có cách nào biết.

**Giả định đã chốt:** người tham gia sẽ chủ động tắt ghi âm khi nội dung là
Mật. Thiết kế dựa vào quyết định của con người ở đây, không dựa vào phân loại
tự động. Vì vậy hai thứ ở §5 phải luôn hiển thị và luôn dùng được trong suốt
cuộc gọi, không được ẩn sau menu: banner cho biết đang ghi âm, và nút tắt.
Chúng là cơ chế thực thi của giả định này, không phải chi tiết giao diện.

Luồng đầy đủ:

```
người có quyền bật ghi âm
   └─ server kiểm tra: có calendar.event? → độ mật ≤ ngưỡng? đúng người chủ trì?
                       không có          → coi là thuong, cần là thành viên channel
        └─ phát bus tới channel: đã bắt đầu ghi âm
             └─ MỌI máy tham gia bắt đầu thu MICRO CỦA CHÍNH NÓ
                  └─ chunk ~15s POST kèm (session, partner, seq, offset)
                       └─ Odoo xếp hàng chunk → PhoWhisper (HTTP) → segment
                            └─ [họp kết thúc] trộn segment theo thời gian
                                 └─ /v1/chat/completions → tóm tắt tiếng Việt
                                      └─ đăng vào chatter của cuộc họp
```

Ba ranh giới cố ý:

- **Client** chỉ thu và upload. Không ra quyết định chính sách, không biết gì
  về ASR.
- **Controller** chỉ xác thực và lưu chunk. Không bao giờ chờ ASR — bóc băng
  chạy trong cron, nên GPU chậm không thể làm nghẽn cuộc gọi.
- **ASR và LLM** được gọi qua hai adapter mỏng, theo quy ước
  `extract/ocr.py:92`. Đổi được bằng cấu hình; không import ở nơi nào khác.

## 5. Phía client

Một `patch(Rtc.prototype, {...})` trong `static/src/meeting_recorder.js`, cộng
một component banner nhỏ.

**Clone track, không đụng vào cuộc gọi.** Theo tiền lệ `media_monitoring.js`,
gọi `this.state.micAudioTrack.clone()` rồi đưa clone vào `AudioContext` riêng →
`AudioWorkletNode`, dùng lại `Mp3Encoder` từ
`@mail/discuss/voice_message/common/mp3_encoder`. **Không thêm thư viện JS mới**
— lamejs đã được đóng gói sẵn.

**Tạo AudioContext ở 16 kHz** (`new AudioContext({ sampleRate: 16000 })`).
PhoWhisper resample về 16 kHz, nên làm sẵn ở trình duyệt bỏ được một bước
resample phía server và cho phép hạ bitrate xuống mức thấp mà giọng nói vẫn rõ.
Mono, ~32 kbps.

Về dung lượng: 32 kbps liên tục là ~14 MB mỗi người mỗi giờ. Nhưng cổng tắt
tiếng và ngưỡng RMS ở dưới nghĩa là chỉ lúc người đó thực sự nói mới có chunk
được gửi, nên thực tế trong một cuộc họp 5 người con số rơi vào khoảng 3–4 MB
mỗi người mỗi giờ. Lưu ý `Mp3Encoder` phải chạy ở sample rate MPEG-2 (16 kHz) —
lamejs hỗ trợ, nhưng cần kiểm chứng trong lượt chạy đầu cuối.

**Tắt tiếng là chặn cứng.** Khi `track.enabled` là false (tắt tiếng hoặc
push-to-talk), recorder **bỏ hẳn chunk** thay vì upload khoảng lặng. Whisper
thường bịa ra chữ từ khoảng lặng số, nên cách xử lý đúng là không đưa khoảng
lặng vào. Thêm ngưỡng năng lượng RMS trước khi upload.

**Chunk và thời gian.** Chunk ~15 giây, **chồng lấn ~1.5 giây**, flush sớm khi
dừng hoặc rời họp. 15 giây vừa khít cửa sổ 30 giây của kiến trúc Whisper nên
mỗi chunk đi trọn một lượt forward. Chồng lấn để câu chữ không bị cắt đôi ở mối
nối; trùng lặp được khử khi ghép segment.

Mỗi chunk mang `(rtc_session_id, partner_id, seq, offset_ms, duration_ms)`.

`offset_ms` đo bằng `performance.now()` **so với thời điểm máy đó bắt đầu ghi**,
không bao giờ dùng đồng hồ tường. Bus gửi kèm `recording_started_at` (giờ
server) và `elapsed_ms` cho người vào giữa chừng. Vị trí tuyệt đối bằng
`recording_started_at + elapsed_at_join + local_elapsed`. Chỉ dùng thời gian
trôi cục bộ, nên lệch đồng hồ giữa các máy không thể làm rối thứ tự.

**Gửi đi.** `POST /aidt_meeting/chunk` dạng FormData. Thất bại thì thử lại với
backoff trên buffer bộ nhớ có giới hạn (~2 phút, sau đó bỏ chunk cũ nhất và
đánh dấu khuyết). Lần flush cuối khi đóng tab dùng `navigator.sendBeacon`, đúng
cách `rtc_service.js:485` làm với `leave_call`.

**Đồng thuận.** Khi ghi âm bật, mọi người thấy banner thường trực trong giao
diện cuộc gọi kèm hai nút: **Từ chối** và **Dừng ghi âm**.

- *Từ chối* chỉ dừng upload của người đó; cuộc họp và bản ghi của người khác
  vẫn tiếp tục, và transcript ghi rõ người đó đã từ chối thay vì để lại khoảng
  trống im lặng.
- *Dừng ghi âm* dừng toàn bộ bản ghi của cuộc gọi.

Quyền bật và quyền dừng **không đối xứng, có chủ đích**: bật thì bị giới hạn
(người chủ trì, hoặc thành viên channel với cuộc gọi tự phát), còn **dừng thì
bất kỳ người tham gia nào cũng làm được**. Đây là hệ quả trực tiếp của giả định
ở §4 — nếu hệ thống trông cậy vào việc con người tắt ghi âm khi nội dung là
Mật, thì người nhận ra điều đó phải tắt được ngay, không phải đi nhờ người khác
tắt hộ. Banner không được ẩn, không được thu gọn, và phải hiện trong suốt thời
gian ghi.

## 6. Mô hình dữ liệu

### `aidt.meeting.recording`

| Trường | Ghi chú |
|---|---|
| `event_id` | `calendar.event`, **không bắt buộc** — rỗng với cuộc gọi tự phát |
| `channel_id` | `discuss.channel`, **bắt buộc** — đây mới là khoá thật |
| `state` | `recording → processing → done` / `failed` / `cancelled` |
| `started_by_id`, `started_at`, `ended_at` | ai cho phép, và khi nào |
| `secrecy_at_start` | **bản chụp** độ mật lúc bắt đầu; `thuong` khi không có `event_id` |
| `declined_partner_ids` | M2M, ai từ chối |
| `transcript_text`, `summary_text` | kết quả cuối |

`secrecy_at_start` là bản sao chứ không phải trường related, có chủ đích. Nếu
tuần sau ai đó đổi cuộc họp thành Tối mật thì bản ghi đã hoàn tất không được
trở thành trái phép một cách hồi tố; ngược lại, hạ độ mật về sau cũng không
được hợp thức hoá một bản ghi đã tạo dưới luật chặt hơn. Bản ghi được xét theo
chính sách tại thời điểm bắt đầu, và điều đó buộc phải lưu lại.

### `aidt.meeting.chunk`

`recording_id`, `partner_id`, `rtc_session_id`, `seq`, `offset_ms`,
`duration_ms`, `attachment_id` (audio trong filestore, không phải cột DB),
`state` (`pending/transcribing/done/failed`), `error`, `retry_count`.

Ràng buộc duy nhất trên `(recording_id, partner_id, seq)` để upload thử lại
không nhân đôi audio. Index trên `(recording_id, state)` cho vòng quét cron.

### `aidt.meeting.segment`

`chunk_id`, `recording_id`, `partner_id`, `start_ms`, `end_ms` (tuyệt đối, quy
đổi qua offset của chunk), `text`. Đây là đơn vị được sắp xếp để dựng
transcript. Index trên `(recording_id, start_ms)`.

### `res.config.settings`

- `meeting_asr_url`, `meeting_asr_model`, `meeting_asr_api_key` — mặc định
  model `vinai/PhoWhisper-large`.
- `meeting_llm_url`, `meeting_llm_model`, `meeting_llm_api_key` — model tóm
  tắt (xem §9).
- `meeting_max_secrecy` — mặc định `thuong`.
- `meeting_audio_retention_days` — mặc định `0`.

**Lưu trữ mặc định là 0 — audio bị xoá ngay khi chunk bóc băng thành công.**
Văn bản mới là thứ cần cho biên bản; audio thô của một cuộc họp cấp uỷ là rủi
ro lớn hơn nhiều so với transcript và không có bên nào dùng đến trong thiết kế
này. Giữ lại phải là lựa chọn có ý thức của quản trị viên, không phải mặc định.

### Phân quyền

Bản ghi và segment đọc được bởi nhóm `Quản lý biên bản`, cộng với:

- cuộc họp có lịch: người dự họp của `event_id`;
- cuộc gọi tự phát: **thành viên của `channel_id`**.

Record rule viết theo `channel_id` là chính và `event_id` là bổ sung, vì
`channel_id` luôn có còn `event_id` thì không. Một rule chỉ dựa vào `event_id`
sẽ để lọt toàn bộ bản ghi của cuộc gọi tự phát.

Chunk audio không bao giờ lộ qua route công khai; tải về đi qua controller có
kiểm tra lại record rule.

## 7. Xử lý phía server

**Endpoint upload.** `POST /aidt_meeting/chunk`, `auth="user"`. Kiểm tra bản
ghi đang ở trạng thái `recording`, và người gọi thực sự có phiên RTC trong
channel đó. Quan trọng: **`partner_id` lấy từ `request.env.user.partner_id`,
không bao giờ đọc từ payload** — nếu không, bất kỳ người dùng đã đăng nhập nào
cũng gán được audio cho người khác, và một dòng transcript giả mạo đúng là loại
sản phẩm không được phép giả mạo trong hệ thống này. Endpoint ghi attachment và
dòng chunk, trả 200, không làm gì với ASR.

**Hàng đợi.** Một `ir.cron` chạy mỗi phút lấy chunk `pending` theo lô, gọi
PhoWhisper, ghi segment, và commit theo từng chunk để một chunk hỏng không cuốn
cả lô. Vì chunk chảy lên **trong lúc** họp, một cuộc họp 60 phút gần như đã bóc
băng xong khi mọi người rời máy; chỉ còn audio của phút cuối. Transcript có sau
1–2 phút. Đạt yêu cầu "sẵn sàng ngay sau khi họp xong" mà không cần hạ tầng mới
và không chặn request nào.

**Phát hiện kết thúc, hai lớp.** Nút Dừng tường minh, **cộng** vòng quét cron
tìm bản ghi còn ở `recording` mà channel không còn dòng
`discuss.channel.rtc.session` nào. Lớp thứ hai mới là lớp thường dùng: kiểu kết
thúc phổ biến không phải bấm nút mà là tất cả cùng gập máy.

**Hoàn tất.** Khi mọi chunk đã `done` hoặc `failed`: sắp xếp segment theo
`start_ms` tuyệt đối, khử trùng lặp ở mối nối chồng lấn, gộp các lượt nói liên
tiếp của cùng một người thành đoạn văn, rồi đăng transcript: vào chatter của
`event_id` nếu có, ngược lại đăng thành tin nhắn trong `channel_id`. Sau đó gọi
tóm tắt, rồi xoá audio theo chính sách lưu trữ.

Với cuộc gọi tự phát, transcript quay lại đúng nơi cuộc gọi đã diễn ra — người
tham gia đọc được ngay trong khung chat mà không cần tìm ở đâu khác.

## 8. Hành vi khi lỗi

Cách hệ thống hỏng quan trọng hơn việc nó có hỏng hay không.

- **ASR chết** → chunk giữ `pending`, thử lại vòng sau. Sau 3 lần thì đánh dấu
  `failed` và transcript mang dấu `[thiếu âm thanh HH:MM–HH:MM]`. Khoảng khuyết
  luôn được nói ra, không bao giờ bị lấp im lặng — một biên bản có lỗ hổng vô
  hình còn tệ hơn một biên bản thừa nhận nó.
- **LLM chết** → transcript vẫn được đăng, tóm tắt đánh dấu thất bại, kèm nút
  "Tạo lại tóm tắt". **Lỗi của bộ tóm tắt không bao giờ được làm mất
  transcript**; hai giai đoạn tách rời chính là để sản phẩm khó tạo lại nhất
  sống sót.
- **Whisper bịa chữ từ khoảng lặng** → chặn bằng cổng tắt tiếng và ngưỡng RMS ở
  §5.
- **Transcript dài hơn context của LLM** → map-reduce: tóm tắt từng cửa sổ rồi
  tóm tắt các bản tóm tắt. Họp hai tiếng chắc chắn vượt cửa sổ 8–32k, nên đây
  không phải trường hợp biên.
- **Có người không upload gì** (từ chối, hoặc addon không tải được) → ghi vào
  `declined_partner_ids` và nêu ở đầu transcript, để người đọc biết thiếu giọng
  của ai.

## 9. Mô hình và hạ tầng

### Tách tầng AI khỏi tầng web

`docker-compose.yml` (production) chỉ chạy tầng web: Postgres và Odoo. Toàn bộ
thành phần AI — embedding, ASR, LLM — nằm ở **`docker-compose.ai.yml` riêng**,
cùng một network để Odoo gọi được theo tên service.

Đây là lý do mọi endpoint AI trong thiết kế này đều là cấu hình chứ không phải
hằng số: **tầng AI phải thay được bằng dịch vụ bên thứ ba bất cứ lúc nào** mà
không sửa dòng code nào trong `aidt_meeting_minutes`. Hai adapter ở §4 là ranh
giới đó.

Hệ quả bắt buộc khi triển khai:

- **Cần một network `external` đặt tên**, khai báo ở cả hai file compose. Hai
  compose project khác nhau không nói chuyện được qua default bridge, mà
  `docker-compose.yml` hiện chưa khai báo network nào — nên phải thêm.
- **Không hardcode `localhost` hay tên service** trong code Python. Mọi thứ đi
  qua `meeting_asr_url` / `meeting_llm_url`.
- **Phải có cấu hình API key** cho cả hai adapter (`meeting_asr_api_key`,
  `meeting_llm_api_key`, gửi dạng `Authorization: Bearer`). Dịch vụ nội bộ
  không cần, nhưng dịch vụ bên thứ ba thì luôn cần — thiếu chỗ này thì lời hứa
  "chuyển sang bên thứ ba bất cứ lúc nào" không thực hiện được nếu không sửa
  code.
- **`docker-compose.ai.yml` chưa tồn tại**; tạo nó là việc thuộc phần triển
  khai. Lưu ý `docker-compose.dev.yml` hiện đang nhúng thẳng `aidt-embed` —
  cần thống nhất theo mô hình tách file, nếu không dev và production sẽ lệch
  nhau về cách Odoo tìm dịch vụ AI.
- Nếu chuyển ASR hoặc LLM sang bên thứ ba thì **audio và transcript cuộc họp
  rời khỏi hạ tầng nội bộ**. Với cuộc họp đã phân loại, đây là quyết định về
  quản trị chứ không phải về vận hành.

### Mô hình

**ASR: `vinai/PhoWhisper-large`**, một service trong `docker-compose.ai.yml`.

Hai điểm hợp với thiết kế:

- Kiến trúc Whisper, cửa sổ gốc 30 giây — chunk 15 giây của ta đi trọn một lượt
  forward, không cần ghép long-form bên trong model.
- Thiết kế lấy mốc thời gian từ **offset của chunk**, không từ timestamp token
  bên trong Whisper. Đây là điểm quan trọng, vì độ tin cậy của timestamp là thứ
  dễ suy giảm nhất ở một bản fine-tune. Trường hợp xấu nhất là lùi về gán theo
  mức chunk, transcript vẫn dùng được.

**Tóm tắt: Gemma 12B QAT int4**, qua endpoint tương thích OpenAI
`/v1/chat/completions`, theo đúng quy ước `extract/ocr.py:92`.

**Ràng buộc GPU đã đo thực tế.** Card là RTX 5060 Ti **16 GB**, đang dùng sẵn
~2.5 GB. Dự toán:

| Thành phần | VRAM |
|---|---|
| `aidt-embed` (`gpu-memory-utilization=0.15`) | ~2.4 GB |
| PhoWhisper-large (~1.5B, fp16 + activations) | ~4 GB |
| Gemma 12B QAT int4 (trọng số) | ~7 GB |
| **Tổng** | **~13.5 GB / 16 GB** |

Còn khoảng 2.5 GB cho KV cache. Hệ quả bắt buộc:

- **Mọi service phải ghim `gpu-memory-utilization` tường minh.** vLLM cấp phát
  trước KV cache theo tỉ lệ; để mặc định thì ba service sẽ tranh nhau và OOM
  ngay lúc khởi động.
- Map-reduce ở §8 không còn chỉ là cách lách giới hạn context — nó là thứ giữ
  cho KV cache đủ nhỏ để vừa.
- Dự toán trên chỉ áp dụng khi cả ba model cùng nằm trên card này qua
  `docker-compose.ai.yml`. Nếu tách LLM sang máy khác hoặc sang bên thứ ba thì
  ràng buộc VRAM biến mất, và đó chính là lý do tầng AI được tách file.

**Chưa xác nhận:** chuỗi `gemma4:12b` là cú pháp tag của Ollama, không phải
đường dẫn `--model` của vLLM. Ollama cũng phục vụ `/v1/chat/completions` tương
thích OpenAI nên adapter không đổi, nhưng runtime thực tế của bộ tóm tắt cần
được xác nhận khi triển khai.

## 10. Kiểm thử

Test Python (`tests/`, `TransactionCase`), theo lối mock HTTP đã dùng ở
`custom-addons/aidt_search_engine/tests/test_extract_ocr.py`:

- **Phân quyền, cuộc họp có lịch** — Mật bị chặn khi ngưỡng là Thường; người
  không chủ trì không bật được.
- **Phân quyền, cuộc gọi tự phát** — không có `calendar.event` thì vẫn bật
  được; `secrecy_at_start` ghi `thuong`; thành viên bất kỳ của channel bật
  được; **người ngoài channel bị từ chối**.
- **Định tuyến kết quả** — có `event_id` thì transcript vào chatter của sự
  kiện; không có thì vào channel.
- **Record rule** — người ngoài channel không đọc được bản ghi của cuộc gọi tự
  phát (ca dễ lọt nhất nếu rule chỉ viết theo `event_id`).
- **Controller** — payload khai `partner_id` của người khác bị bỏ qua, lấy theo
  session; `(recording, partner, seq)` trùng bị từ chối; upload vào bản ghi
  không ở trạng thái `recording` bị từ chối.
- **Trộn thời gian** — segment nhiều người sắp xếp đúng, gồm một ca lệch đồng
  hồ cố ý giữa hai máy. Đây là phần logic dễ sai tinh vi nhất và khó phát hiện
  bằng mắt nhất.
- **Khử trùng lặp mối nối** — vùng chồng lấn 1.5 giây không sinh chữ lặp.
- **Hoàn tất** — chunk lỗi hiện `[thiếu âm thanh …]`; người từ chối được nêu tên.
- **Adapter** — dựng URL, retry/backoff, thất bại sau 3 lần; có API key thì gửi
  `Authorization: Bearer`, không có thì bỏ hẳn header (ca dịch vụ nội bộ).
- **Quyền dừng** — người tham gia bất kỳ dừng được bản ghi, kể cả khi không
  phải người bật; người ngoài cuộc gọi thì không.
- **Tách giai đoạn** — LLM lỗi thì transcript vẫn được đăng.
- **Lưu trữ** — audio bị xoá khi `0`, giữ lại khi `> 0`.

Test JS (hoot) cho patch recorder: tắt tiếng thì bỏ chunk chứ không upload
khoảng lặng; `offset_ms` đúng khi vào họp giữa chừng; đóng tab kích hoạt
`sendBeacon`.

**Không tự động hoá được, và sẽ ghi rõ như vậy:** `getUserMedia` thật, WebRTC
thật giữa hai trình duyệt, và độ chính xác thật của PhoWhisper trên audio họp
tiếng Việt. Phải chạy tay hai trình duyệt trên `aidt_demo`. Theo quy ước
CLAUDE.md, mục hướng dẫn của tính năng này ra mắt kèm cảnh báo cho đến khi lượt
chạy đầu cuối đó thực sự diễn ra — bao gồm cả độ chính xác ASR, hiện chưa có cơ
sở nào để khẳng định.

**Kỷ luật cơ sở dữ liệu:** cài vào `aidt_demo`. Nếu cần DB tạm thì phải drop
cùng thư mục filestore khi chạy xong.

## 11. Tài liệu

Là một phần của định nghĩa hoàn thành, không phải việc làm sau:

- `docs/GUIDANCE.md` — thêm mục đánh số và một dòng trong bảng mục lục, viết
  bằng tiếng Việt, chỉ viết sau khi đối chiếu từng đường dẫn menu, nhãn nút và
  chuỗi banner với view XML và template OWL đã ship.
- `custom-addons/aidt_meeting_minutes/README.md` — kiến trúc, giao thức chunk,
  và các tham số cấu hình ASR/LLM.
