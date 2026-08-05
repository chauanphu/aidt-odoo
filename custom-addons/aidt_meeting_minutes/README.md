# AIDT — Biên bản cuộc họp (`aidt_meeting_minutes`)

Ghi âm cuộc gọi Discuss Meet **theo từng người**, bóc băng bằng
PhoWhisper-large, ghép thành bản bóc băng có gán tên người nói, rồi tóm tắt
bằng Gemma 3 12B QAT và đăng cả hai vào chatter của cuộc họp.

Hướng dẫn cho người dùng cuối: [`docs/GUIDANCE.md`](../../docs/GUIDANCE.md), mục 2.

> ## ⚠️ Trạng thái kiểm chứng (05/08/2026)
>
> Đọc mục [§8](#8-những-gì-đã-và-chưa-được-kiểm-chứng) TRƯỚC KHI triển khai.
> Tóm tắt: đường ống chạy thông từ đầu đến cuối, nhưng **`aidt-asr` trả về
> gần như không có chữ nào cho đầu vào tiếng Việt đã thử** — tính năng CHƯA
> DÙNG ĐƯỢC cho mục đích thật. Lưu ý phạm vi bằng chứng: đầu vào đó là giọng
> TỔNG HỢP, chưa bao giờ là giọng người thật (§8.2). Không có bước nào chạy
> qua micro của trình duyệt thật.

---

## 1. Vì sao thu tiếng ở TỪNG MÁY, không thu ở server

Yêu cầu cốt lõi: biên bản phải nói được **ai** đã nói câu nào. Có ba cách,
đã cân nhắc cả ba:

| Cách | Vì sao KHÔNG chọn |
|---|---|
| **Rẽ luồng ở SFU** (fork luồng media trên máy chủ) | Odoo không tự chạy SFU; nó dùng dịch vụ ngoài. Rẽ luồng đòi hỏi vận hành thêm một thành phần media nữa, và luồng tới SFU đã bị trộn/nén theo từng người nhận. Ngoài ra phải giải mã lại toàn bộ media ở server — tốn CPU đúng lúc cuộc họp đang chạy. |
| **Một "người dự họp robot"** tham gia cuộc gọi rồi thu | Robot chỉ nghe được **luồng đã trộn**. Tách người nói từ luồng trộn (diarization) là một bài toán riêng, sai số cao, và sai ở đây nghĩa là gán nhầm phát biểu cho người khác trong một văn bản hành chính. Thêm nữa robot phải có tài khoản, phải được mời, và hiện diện của nó trong danh sách người dự là một thay đổi lớn về mặt tổ chức. |
| ✅ **Thu ở từng máy** (`recorder_service.js`) | Mỗi trình duyệt thu **đúng micro của chính người đó**, nên danh tính người nói là điều **đã biết chắc**, không phải suy đoán. Không cần thành phần hạ tầng mới. Đổi lại: phải tự lo ghép thứ tự theo thời gian giữa các máy (xem §2). |

Recorder **clone** track micro (`micTrack.clone()`) chứ không dùng trực tiếp:
bộ ghi âm không bao giờ được làm nhiễu thứ người khác đang nghe. Cùng cách
`media_monitoring.js` của `mail` làm.

Dùng `state.micAudioTrack` chứ **không** dùng `audioTrack`: `audioTrack` có
thể đã bị trộn thêm tiếng của màn hình chia sẻ, không còn là lời của một
người.

---

## 2. Giao thức mẩu audio (chunk)

### 2.1. Đường đi

```
AudioWorklet (16 kHz)  →  Mp3Encoder (32 kbps mono)  →  POST /aidt_meeting/chunk
        ↓                                                        ↓
  cổng tắt tiếng + RMS                              aidt.meeting.chunk (pending)
                                                             ↓  cron mỗi phút
                                              asr_client._transcribe()  (HTTP)
                                                             ↓
                                              aidt.meeting.segment (mốc TUYỆT ĐỐI)
                                                             ↓  cron sweep
                                              transcript_builder._build()
                                                             ↓
                                    chatter: "Bản bóc băng cuộc họp"
                                                             ↓
                                    summary_client._summarize()  (HTTP)
                                                             ↓
                                    chatter: "Tóm tắt cuộc họp"
```

### 2.2. Các trường gửi lên

`POST /aidt_meeting/chunk`, `type='http'`, `auth='user'`, `csrf=False`,
`multipart/form-data`:

| Trường | Nguồn | Ý nghĩa |
|---|---|---|
| `recording_id` | ghim vào mẩu lúc tạo | Bản ghi. Ghim chứ không đọc `state.recordingId` lúc gửi: mẩu tồn đọng được gửi lại trong `stop()`, khi đó `state.recordingId` đã bị xoá. |
| `seq` | bộ đếm cục bộ của máy | Thứ tự trong phạm vi **một người, một bản ghi**. `UNIQUE(recording_id, partner_id, seq)`. |
| `offset_ms` | `computeOffsetMs()` | Vị trí **tuyệt đối** của mẩu trong cuộc họp, tính bằng ms. |
| `duration_ms` | `now - chunkStartedAt` | Độ dài mẩu. |
| `audio` | `Blob` MP3 | Tên tệp `chunk-{seq}.mp3`. Trần `MAX_CHUNK_BYTES = 2 MB` (15 s mono 32 kbps ≈ 60 KB). |

`partner_id` **không** nằm trong danh sách trên — xem §5.

### 2.3. Số học offset

```js
computeOffsetMs({ elapsedAtJoinMs, recorderStartedAt, now })
  = max(0, round(elapsedAtJoinMs + (now - recorderStartedAt)))
```

Chỉ dùng **thời gian trôi cục bộ** (`performance.now()`), **không bao giờ**
dùng đồng hồ tường. `elapsedAtJoinMs` do server gửi kèm trong bus event
`aidt_meeting_minutes/recording_state` (`_broadcast_state`), nên một máy vào
họp giữa chừng vẫn đặt được mẩu của mình đúng chỗ trên trục thời gian chung
mà **không cần đồng hồ hai máy khớp nhau**. Lệch giờ giữa các máy không thể
làm rối thứ tự khi server trộn.

Server quy đổi sang mốc tuyệt đối trong `meeting_chunk._write_segments()`:

```python
end = item['end_ms']
if end is None:                 # dịch vụ không trả mốc ⇒ phủ trọn mẩu
    end = self.duration_ms
end = min(end, self.duration_ms)    # không thể kết thúc ngoài mẩu
end = max(end, item['start_ms'])    # không thể kết thúc trước khi bắt đầu

'start_ms': self.offset_ms + item['start_ms']
'end_ms':   self.offset_ms + end
```

**Mốc thời gian từ ASR là ĐẦU VÀO NGOÀI, KHÔNG TIN ĐƯỢC** — phải kẹp chứ
không chuyển tiếp nguyên văn. Đã thấy thật: service trả `end: 40.08` cho một
mẩu dài 8.208 s, sinh ra hàng `start_ms=16860, end_ms=4980` trong CSDL
(`end_ms` **nhỏ hơn** `start_ms`, vô nghĩa theo chính ngữ nghĩa của hai
trường). Đoạn suy biến bị thu về độ dài 0 chứ không bị vứt đi — `text` vẫn là
nội dung thật.

Lưới an toàn tầng CSDL: `aidt.meeting.segment` có
`CHECK (end_ms >= start_ms)`, áp cho MỌI đường ghi (import, sửa tay, một
client ASR khác cắm sau này), không chỉ cho `_write_segments`.

### 2.4. Chồng lấn 1.5 giây và khử trùng ở mối nối

Mẩu dài `CHUNK_MS = 15000`. Cắt mẩu giữa một câu làm Whisper nghe hụt cả hai
đầu, nên mẩu kế tiếp được **mồi** bằng `OVERLAP_MS = 1500` ms PCM cuối của
mẩu trước (`retainOverlap`), tức audio thật được **mã hoá hai lần**.

Mốc bắt đầu của mẩu kế tiếp phải lùi đúng bằng **đoạn ĐÃ mồi được**, không
phải bằng 1.5 s trên giấy:

```js
carriedStartAt(now, carriedSamples, sampleRate) = now - carriedSamples / sampleRate * 1000
```

Lùi mà không mồi audio thật thì offset nói một đằng, tiếng nằm một nẻo.

Phần trùng được khử ở server, `transcript_builder._strip_overlap()`:

* Khớp theo **từ**, không theo ký tự — bóc băng hai lần cùng một đoạn audio
  hiếm khi ra chuỗi ký tự trùng khít, nhưng chuỗi từ thì thường trùng.
* Thử từ dài đến ngắn, tối đa `MAX_OVERLAP_WORDS = 12` từ.
* **Tối thiểu 2 từ mới xoá.** Hai hướng sai không cân nhau: xoá thiếu để lại
  một từ lặp mà người đọc *nhìn thấy* và tự sửa được; xoá thừa làm **mất nội
  dung âm thầm** trong một biên bản chính thức. Tiếng Việt lại đầy từ đệm một
  âm ("vâng", "dạ", "rồi", "được") vừa kết câu này vừa mở câu sau, nên khớp
  1 từ là trùng hợp phổ biến chứ không phải bằng chứng về mối nối.
* Chỉ khử giữa **hai đoạn liền nhau của cùng một người**.

> ⚠️ `MAX_OVERLAP_WORDS = 12` là **ước lượng theo giả định** (nói nhanh cỡ
> nào cũng khó vượt 12 từ trong 1.5 s), **chưa hiệu chỉnh** trên đầu ra ASR
> thật. Tương tự `WINDOW_LINES = 120` ở `summary_client`.

### 2.5. Cổng chặn im lặng và tắt tiếng

* **Tắt tiếng thật** (`rtc.localSession.isMute`): chốt phần đã thu rồi
  **ngừng hẳn mã hoá**. Clone giữ `enabled` riêng với track gốc nên nó vẫn
  nghe thấy mọi thứ sau khi người dùng bấm tắt micro — cứ mã hoá tiếp là cả
  đoạn nói riêng đó lên thẳng biên bản dưới tên họ. **Không** thay bằng
  khung im lặng: nhét khoảng lặng số vào MP3 đúng là kiểu đầu vào làm Whisper
  bịa chữ.
* **`RMS_FLOOR = 0.005`**: mẩu dưới ngưỡng năng lượng này bị bỏ, không gửi.
* `shouldUpload(track, rms)` đọc cờ "mẩu này có chứa tiếng micro thật hay
  không" (`chunkHasAudio`), **không** đọc `MediaStreamTrack.enabled` — cờ đó
  bị kích hoạt-bằng-giọng-nói bật/tắt nhiều lần mỗi giây.

### 2.6. Gửi lại

`shouldRetry(status, attempts)`: 4xx là từ chối vĩnh viễn (không thuộc cuộc
gọi, bản ghi đã chốt, mẩu quá lớn) — không gửi lại. `status === 0` (hỏng
mạng) và 5xx được gửi lại, **tối đa `MAX_ATTEMPTS = 2` lần**. Hàng đợi tồn
đọng có trần `MAX_BUFFERED_CHUNKS = 8`, bỏ mẩu cũ nhất khi tràn — thà thiếu
một đoạn (được đánh dấu `[thiếu âm thanh …]`) còn hơn ăn hết RAM của tab.

Phía server, `_store()` bọc `create()` trong SAVEPOINT vì gửi lại sau lỗi
mạng là **đường đi bình thường**: client không biết request trước có tới nơi
không, `UNIQUE(recording_id, partner_id, seq)` chặn ở lần thứ hai, và không
có savepoint thì UniqueViolation đầu độc cursor cho hết request HTTP.

`_store()` vẫn nhận audio khi bản ghi ở trạng thái `processing`: lệnh dừng
được phát **sau** khi đổi trạng thái, nên mẩu cuối của mỗi máy — tới 15 giây
lời kết — bao giờ cũng tới nơi khi trạng thái đã đổi.

> **Chưa làm:** `sendBeacon` khi đóng tab. `_flushChunk` chạy khi bấm dừng,
> nhưng đóng tab đột ngột vẫn mất mẩu đang dở.

---

## 3. Hàng đợi và vòng đời

Ba cron (`data/ir_cron.xml`):

| Cron | Chu kỳ | Việc |
|---|---|---|
| `cron_transcribe` | 1 phút | `aidt.meeting.chunk._cron_process()` — nhận việc bằng `FOR UPDATE SKIP LOCKED`, xử lý **từng mẩu một**, commit ngay sau mỗi mẩu. |
| `cron_sweep_recording` | 1 phút | `aidt.meeting.recording._cron_sweep()` — đóng bản ghi bị bỏ dở (không còn phiên RTC nào), rồi hoàn tất bản ghi đã đủ dữ liệu. |
| `cron_purge_audio` | 1 ngày | Xoá audio theo `aidt_meeting.audio_retention_days`, toàn hệ thống. |

`_cron_sweep` chụp danh sách `processing` **trước** khi chuyển các bản ghi
`recording` bị bỏ dở sang `processing`: một bản ghi vừa được phát hiện kết
thúc phải chờ ít nhất một lượt quét nữa mới được hoàn tất, để các mẩu cuối
kịp tới.

Thử lại khi bóc băng hỏng: `MAX_ATTEMPT = 3`, giãn cách
`RETRY_BACKOFF_MINUTES = (1, 4, 16)` phút. Hết lượt ⇒ `failed` ⇒ một dòng
`[thiếu âm thanh mm:ss–mm:ss: Tên người]` trong bản bóc băng.

Mọi chỗ có thể ném lỗi tầng CSDL đều bọc SAVEPOINT riêng
(`_process_one`, `_run_summary`, `_purge_own_audio`) — không bọc thì một lỗi
SQL đầu độc cursor và câu ghi-lỗi ở khối `except` **ném tiếp**, rollback luôn
transcript vừa ghi. Cùng khuôn mẫu với `aidt_search/models/index_job.py`.

---

## 4. Cấu hình ASR / LLM

**Cài đặt → Biên bản cuộc họp** (`res_config_settings_views.xml`), hoặc
**Cài đặt → Kỹ thuật → Tham số hệ thống**:

| Tham số | Nhãn trên UI | Mặc định |
|---|---|---|
| `aidt_meeting.asr_url` | URL dịch vụ bóc băng | `http://aidt-asr:8002/v1` |
| `aidt_meeting.asr_model` | Model bóc băng | `vinai/PhoWhisper-large` |
| `aidt_meeting.asr_api_key` | API key dịch vụ bóc băng | *(rỗng)* |
| `aidt_meeting.llm_url` | URL dịch vụ tóm tắt | `http://aidt-llm:11434/v1` |
| `aidt_meeting.llm_model` | Model tóm tắt | `gemma3:12b-it-qat` |
| `aidt_meeting.llm_api_key` | API key dịch vụ tóm tắt | *(rỗng)* |
| `aidt_meeting.max_secrecy` | Độ mật tối đa được ghi âm | `thuong` |
| `aidt_meeting.audio_retention_days` | Giữ audio (ngày) | `0` |

### 4.1. Trỏ sang dịch vụ bên thứ ba

Endpoint là **dữ liệu**, không phải hằng số trong code — không cần sửa Python
và không cần deploy lại.

* **Bóc băng** — cần một endpoint tương thích OpenAI
  `POST {asr_url}/audio/transcriptions`, nhận `multipart/form-data` với các
  trường `model`, `response_format=verbose_json`, `file`. Đặt `asr_url` =
  `https://api.openai.com/v1`, `asr_model` = `whisper-1`, `asr_api_key` =
  khoá. `_parse()` đọc `segments[].{start,end,text}`, và lùi về `text` phẳng
  nếu không có `segments`.
* **Tóm tắt** — cần `POST {llm_url}/chat/completions` tương thích OpenAI.
  `_chat()` đọc `choices[0].message.content`. Đặt `llm_url`, `llm_model`,
  `llm_api_key` tương ứng.

Có API key ⇒ header `Authorization: Bearer …`. Rỗng ⇒ không gửi header.
Timeout cả hai: `TIMEOUT = 300` giây.

> ### ⚠️ Bẫy khi nâng cấp: `noupdate="1"`
>
> `data/ir_config_parameter.xml` nằm trong `<data noupdate="1">`, nên
> `-u aidt_meeting_minutes` **không** ghi đè giá trị đã có trong CSDL. Đó là
> chủ ý (admin đổi endpoint từ UI thì không bị reset), nhưng nó có nghĩa là
> **sửa giá trị mặc định trong file XML không tự lan tới CSDL đã cài**.
>
> Đã xảy ra thật: `aidt_demo` giữ nguyên `llm_url=http://aidt-llm:8003/v1` và
> `llm_model=gemma4:12b` sau khi commit `9631dac` sửa file XML — mọi lần tóm
> tắt đều "Connection refused", ghi vào `summary_error` còn transcript vẫn
> đăng, tức lỗi **âm thầm** với người dùng. `migrations/19.0.1.0.1/` sửa đúng
> hai giá trị sai đó (và chỉ hai giá trị đó). **Sau mỗi lần nâng cấp, hãy đối
> chiếu bảng trên với giá trị thật trong CSDL.**

---

## 5. Mô hình bảo mật

### 5.1. Danh tính người nói lấy từ phiên đăng nhập

`partner_id` **không bao giờ** đến từ payload của client. Controller:

```python
partner = request.env.user.partner_id   # controllers/main.py
```

`_store()` kiểm tra **lại** ở tầng model (`partner != caller` ⇒ `AccessError`)
để mọi đường vào đều qua cùng một cửa — gán audio cho người khác nghĩa là
**giả mạo được một dòng trong biên bản**.

Cùng lý do, `action_decline()` **không nhận** `partner` làm đối số; nó luôn
dùng `self.env.user.partner_id`.

### 5.2. Wrapper public

`odoo/service/model.py` từ chối thẳng mọi tên phương thức bắt đầu bằng `_`
trước khi nó chạy, nên JS không gọi được `_start_for_channel` / `_decline`.
Hai wrapper `action_start_for_channel()` và `action_decline()` chỉ **đổi tên
cho gọi được** — chúng **không nới lỏng** kiểm tra nào và không nuốt ngoại lệ.

### 5.3. Ai được bật, ai được dừng

| | Bật ghi âm | Dừng ghi âm | Từ chối |
|---|---|---|---|
| Cuộc họp **có lịch** | Chỉ `event.user_id` (người chủ trì) | **Bất kỳ** người trong kênh | Bất kỳ người trong kênh |
| Cuộc gọi **tự phát** | Bất kỳ thành viên kênh | **Bất kỳ** người trong kênh | Bất kỳ người trong kênh |

Cuộc gọi tự phát không có gì để phân loại nên `secrecy_at_start = 'thuong'`.
Ngưỡng độ mật **không kiểm soát được** ca này — băng đồng thuận luôn hiện và
nút dừng cho mọi người mới là cơ chế thực thi.

`secrecy_at_start` là **bản chụp**, không phải `related`: đổi độ mật của cuộc
họp sau khi đã bắt đầu ghi không được đổi ngược lại điều đã hợp lệ lúc bắt
đầu.

### 5.4. Record rule theo KÊNH, không theo cuộc họp

```xml
['|', ('channel_id.channel_member_ids.partner_id', '=', user.partner_id.id),
      ('event_id.partner_ids', 'in', [user.partner_id.id])]
```

Viết theo `channel_id` là **bắt buộc**: `event_id` rỗng với mọi cuộc gọi tự
phát, nên một rule chỉ dựa vào `event_id` sẽ để lọt toàn bộ bản ghi của các
cuộc gọi đó. `aidt.meeting.segment` có rule tương ứng đi qua `recording_id`.

ACL (`ir.model.access.csv`): `base.group_user` chỉ **đọc** `recording` và
`segment`, không thấy `chunk`. Nhóm
`aidt_meeting_minutes.group_meeting_minutes_manager` toàn quyền và thấy tất
cả. Menu **Lịch → Bản ghi cuộc họp** chỉ hiện cho nhóm quản lý.

### 5.5. Chỉ mục chống đua

`aidt.meeting.recording.init()` tạo
`UNIQUE INDEX … ON aidt_meeting_recording (channel_id) WHERE state IN ('recording','processing')`
— mỗi kênh chỉ một bản ghi đang hoạt động. Dùng partial unique index chứ
không dùng `EXCLUDE` vì `EXCLUDE (channel_id WITH =)` cần extension
`btree_gist`, mà `CREATE EXTENSION` cần quyền superuser (đã thử và xác nhận
trên `aidt_demo`) — không môi trường triển khai nào đảm bảo có.

### 5.6. Audio

`audio_retention_days = 0` (mặc định) ⇒ tệp audio bị xoá **ngay sau khi hoàn
tất**, bản bóc băng được giữ. `_purge_own_audio()` giới hạn domain theo
`self` — nếu không, hoàn tất bản ghi A sẽ xoá audio của mọi bản ghi B, C đã
`done` từ trước.

---

## 6. Ngân sách GPU

Số đo thật trên **RTX 5060 Ti, 16311 MiB**, ngày 05/08/2026, cả ba service
`healthy` cùng lúc, dựng bằng chính `docker-compose.ai.yml`:

| Service | Chạy trên | Ghim | VRAM |
|---|---|---|---|
| `aidt-embed` (`AITeamVN/Vietnamese_Embedding`) | vLLM 0.26.0 | `--gpu-memory-utilization=0.15` | 1602 MiB |
| `aidt-asr` (`vinai/PhoWhisper-large`) | vLLM 0.26.0 | `--gpu-memory-utilization=0.25` | 4416 MiB |
| `aidt-llm` (`gemma3:12b-it-qat`) | Ollama 0.32.5 | *(không có cờ tương đương)* | 8534 MiB |
| màn hình | | | 82 MiB |
| **Tổng** | | | **14843 / 16311 MiB** |

`ollama ps` báo **"23%/77% CPU/GPU"**: Ollama tự đẩy ~23% số layer sang CPU
cho vừa chỗ còn lại. Vẫn trả lời đúng, chỉ chậm hơn.

**Thứ tự khởi động quyết định chạy được hay không.** vLLM cấp phát trước theo
tỉ lệ cố định; Ollama đo VRAM trống *tại thời điểm nạp model* rồi co giãn.
Cho Ollama vào trước (chiếm 10470 MiB khi chạy một mình) thì `aidt-asr` chết
với `ValueError: Free memory on device cuda:0 (3.54/15.47 GiB) on startup is
less than desired GPU memory utilization (0.25, 3.87 GiB)` — đã kiểm chứng.
`depends_on: service_healthy` ép đúng thứ tự; `OLLAMA_KEEP_ALIVE=-1` giữ cho
nó không nạp lại vào lúc khác.

> ⚠️ `depends_on` **chỉ** có tác dụng lúc `up`/`start`, **không** với
> `docker compose restart <service>`. Restart lẻ `aidt-embed`/`aidt-asr` thì
> phải dừng `aidt-llm` trước để nhả VRAM, rồi cho nó vào sau cùng. Xem khối
> comment của `aidt-llm` trong `docker-compose.ai.yml`.

### Độ trễ tóm tắt — số đo thật, KHÔNG phải kỳ vọng vận hành

Đo ngày 05/08/2026 qua `summary_client._summarize()` thật, transcript tiếng
Việt 6 dòng (1 cửa sổ, không kích hoạt map-reduce):

* **50.1 s** — lượt đầu, tính cả thời gian Ollama nạp model.
* **7.5 s** — lượt sau, model đã nằm sẵn trong VRAM.

> ⚠️ **Không suy ra được thời gian cho cuộc họp thật từ hai con số này.**
> `_summarize()` gọi `_chat()` **một lần cho mỗi cửa sổ `WINDOW_LINES = 120`
> dòng**, cộng một lượt reduce. Họp hai tiếng có hàng nghìn dòng ⇒ hàng chục
> lượt nối tiếp, mỗi lượt còn dài hơn vì đầu vào 120 dòng lớn hơn hẳn mẫu 6
> dòng. **Chưa ai bấm giờ một cuộc họp dài thật từ đầu đến cuối.**

### Dựng tầng AI

```bash
docker network create aidt-ai-net            # một lần
docker compose -f docker-compose.ai.yml up -d --build
docker compose -f docker-compose.ai.yml exec aidt-llm \
    ollama pull gemma3:12b-it-qat            # Ollama KHÔNG tự pull
```

> ℹ️ **Container Odoo phải nằm trên `aidt-ai-net`.**
> `docker-compose.yml` (production) **đã** khai báo sẵn
> `networks: [default, aidt-ai-net]` cho service `odoo`, cùng network
> `external` ở cuối file — **không cần làm gì thêm khi triển khai thật**.
>
> Thiếu sót chỉ có ở **môi trường dev**: `docker-compose.dev.yml` trước đây
> không khai báo network này, nên `aidt-odoo-dev-odoo-1` **không** phân giải
> được tên `aidt-asr` / `aidt-llm`. Đã kiểm chứng 05/08/2026: **trước** khi
> nối, tên không phân giải được; **sau** khi nối, cả
> `http://aidt-asr:8002/v1/models` và `http://aidt-llm:11434/v1/models` đều
> trả HTTP 200 **từ bên trong container odoo đang chạy**.
>
> Nay `docker-compose.dev.yml` đã có cùng khai báo đó, nên chỉ cần tạo
> network một lần trước khi `up`:
>
> ```bash
> docker network create aidt-ai-net
> ```
>
> (Container đang chạy từ trước bản sửa này vẫn cần
> `docker network connect aidt-ai-net aidt-odoo-dev-odoo-1` một lần, hoặc
> dựng lại stack.)

---

## 7. Chạy test

### Python

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo \
  --test-enable --stop-after-init --http-port=8078 -u aidt_meeting_minutes
```

Kết quả 05/08/2026: **0 failed, 0 error of 75 tests** (107 test method,
`odoo.tests.stats`). **Mọi lời gọi ASR/LLM trong bộ này đều là mock.**

### JavaScript (hoot, trong Chrome thật)

`tests/test_js.py` chạy `static/tests/*.test.js` qua runner hoot thật, trong
Chrome thật. `chromium` và `websocket-client` **đã nằm sẵn trong stage `dev`
của `Dockerfile`** — không cần cài tay.

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo \
  --test-enable --test-tags aidt_meeting_js --stop-after-init \
  --http-port=8078 -u aidt_meeting_minutes
```

> ⚠️ Thiếu Chrome hoặc thiếu `websocket-client` ⇒ `browser_js` **SKIP**, chứ
> không FAIL. Điều đó khiến file test an toàn ở môi trường không có trình
> duyệt, nhưng cũng có nghĩa **một môi trường thiếu công cụ trông y hệt một
> lượt chạy xanh**. Ba bộ test hoot của module này đã im lặng không chạy suốt
> mười một task vì đúng lý do đó. Vì vậy `test_js.py` còn **đối chiếu số test
> thực chạy** với `EXPECTED_TESTS` và tự tính hash tên suite lúc chạy — hoot
> vẫn in "Test suite succeeded" khi bộ lọc không khớp suite nào và không có
> test nào chạy. Thêm/bớt test JS thì phải cập nhật `EXPECTED_TESTS`.

Kết quả 05/08/2026: **30 passed, 0 failed** (`[HOOT] Test suite succeeded`).

Hoặc mở thẳng trong trình duyệt:
`http://localhost:8069/web/tests?id=c2929794` (`c2929794` là hash tất định
của tên suite gốc `@aidt_meeting_minutes`).

---

## 8. Những gì ĐÃ và CHƯA được kiểm chứng

### 8.1. Đã chạy thật (05/08/2026)

Một lượt đầu-cuối qua `odoo-bin shell` trên `aidt_demo`, dùng **audio tiếng
Việt TỔNG HỢP bằng gTTS** — *không phải giọng người thật*, xem cảnh báo ở
§8.2 (4 lượt nói luân phiên của 2 người, 8.2 / 5.2 / 6.0 / 5.5 giây; RMS
0.10, đỉnh 0.54 — tệp không im lặng, đã kiểm bằng bộ giải mã độc lập):

| Bước | Kết quả |
|---|---|
| Chủ trì bật ghi âm qua `action_start_for_channel` | ✅ `state=recording`, `secrecy_at_start=thuong` |
| 4 mẩu MP3 upload qua `_store()`, mỗi mẩu dưới danh tính người nói | ✅ 4 chunk, offset 0 / 8208 / 13392 / 19416 |
| Người **không chủ trì** bấm dừng | ✅ `state=processing` |
| `_cron_process()` gọi `aidt-asr` **thật** | ✅ 4/4 chunk `done`, không lỗi |
| Quy đổi offset → `aidt.meeting.segment` | ✅ mốc tuyệt đối được ghi |
| `_cron_sweep()` → `_finalize()` | ✅ `state=done` |
| Đăng chatter "**Bản bóc băng cuộc họp**" | ✅ vào chatter của `calendar.event` |
| `_summarize()` gọi `aidt-llm` **thật** | ✅ HTTP 200, tiếng Việt, đúng ba mục NỘI DUNG CHÍNH / KẾT LUẬN / VIỆC CẦN LÀM, **và tự nêu rõ nội dung có thể không đầy đủ khi transcript có dòng `[thiếu âm thanh …]`** |
| Đăng chatter "**Tóm tắt cuộc họp**" | ✅ |
| Xoá audio (`audio_retention_days=0`) | ✅ 0 chunk còn giữ `attachment_id` |

**Kết luận: đường ống thông suốt.** Mọi mắt xích Python + hai dịch vụ AI đều
hoạt động và khớp khuôn dạng của nhau.

### 8.2. ⚠️ CHƯA DÙNG ĐƯỢC: `aidt-asr` không trả về chữ

Trong đúng lượt chạy trên, `aidt-asr` nhận audio tiếng Việt và trả về
**`"."`** hoặc **chuỗi rỗng**. Bản bóc băng thu được nguyên văn:

```
[00:00] Administrator: . .
```

> ### ⚠️ Đọc kỹ giới hạn của bằng chứng này
>
> **Âm thanh duy nhất từng được thử là giọng TỔNG HỢP (gTTS), chưa bao giờ
> là giọng người thật.** RMS và biên độ đỉnh chỉ chứng minh tệp không im
> lặng; chúng **không** chứng minh tín hiệu nằm trong phân bố dữ liệu mà một
> model tinh chỉnh trên **giọng người Việt tự nhiên** được huấn luyện để
> nghe. Giọng TTS có phổ đều bất thường, không có hơi thở, không nhiễu nền,
> không ngữ điệu tự nhiên — hoàn toàn có khả năng đây mới là nguyên nhân,
> và khi đó kết luận sẽ **đảo ngược**.
>
> **Vì vậy: chẩn đoán dưới đây là RẤT CÓ THỂ, KHÔNG PHẢI ĐÃ CHỨNG MINH.**
>
> **Bước phân loại đầu tiên phải làm: thử lại bằng một bản ghi giọng người
> thật.** Chưa làm bước đó thì chưa được kết luận dứt khoát về
> PhoWhisper-on-vLLM.

Đã loại trừ các nguyên nhân sau bằng thử nghiệm trực tiếp:

* **Không phải tệp im lặng** — giải mã độc lập cho 8.21 s, RMS 0.1049, đỉnh
  0.539. (Xem cảnh báo trên: điều này *không* đồng nghĩa "audio hợp lệ với
  model".)
* **Không phải khuôn dạng MP3** — gửi lại đúng audio đó dưới dạng WAV 16 kHz:
  kết quả y hệt. (Lượt thử ban đầu bị gắn nhãn `Content-Type: audio/mpeg` do
  lỗi ghi cứng ở `_part_content_type`, nay đã sửa; kết quả không đổi sau khi
  sửa.)
* **Không phải nhận nhầm ngôn ngữ** — log service ghi
  `Auto-detected language: 'vi'`; ép thêm `language=vi` không đổi gì.
* **Không phải service chết** — engine sinh token thật (`Avg generation
  throughput: 13.5 tokens/s`), `Supported tasks: ['transcription']`.

**Chứng cứ mạnh nhất cho giả thuyết "lỗi tầng phục vụ" là mốc thời gian:**
cho một mẩu dài 8.208 s, service trả `end: 40.08`, và các segment khác có
`end` tới `415.6` / `264.46`. Một model chỉ *nghe nhầm* một giọng lạ thì
không có lý do gì trả về mốc thời gian dài gấp năm mươi lần đoạn audio —
đây là hành vi khó giải thích bằng riêng chuyện tín hiệu ngoài phân bố. Đó
là lý do chẩn đoán nghiêng về tầng phục vụ, nhưng vẫn chưa đủ để chốt.

Hệ quả từng thấy trong dữ liệu: một `aidt.meeting.segment` có
`start_ms=16860, end_ms=4980` — **`end_ms` nhỏ hơn `start_ms`**. **Đã sửa:**
`_write_segments()` nay kẹp `end` vào khoảng `[start, duration_ms]`, và
`aidt.meeting.segment` có ràng buộc `CHECK (end_ms >= start_ms)` ở tầng CSDL
(§2.3). Mốc thời gian từ ASR là đầu vào ngoài, không tin được, nên không
được chuyển tiếp nguyên văn.

> **Phải xử lý xong việc này trước khi tính năng có ích cho người dùng**, và
> bước đầu tiên là thử lại với giọng người thật. Task 11 từng kết luận "ASR
> verified working"; kết luận đó chỉ đúng cho **khuôn dạng dây**, không đúng
> cho **nội dung**.

### 8.3. Chưa bao giờ chạy

* **Không có bước nào đi qua micro của trình duyệt thật.** `getUserMedia`,
  `AudioWorklet`, `Mp3Encoder`, WebRTC, băng thông báo trong một cuộc gọi
  thật, bus broadcast `recording_state` — tất cả mới chỉ được kiểm bằng test
  đơn vị với đối tượng giả. Bộ test hoot **có** chạy trong Chrome thật, nhưng
  nó cũng dùng micro giả.
* **Chưa bao giờ đưa giọng người thật vào hệ thống.** Mọi phép thử đều dùng
  giọng tổng hợp gTTS. Độ chính xác tiếng Việt thật của PhoWhisper **chưa
  biết**, và bản thân kết luận ở §8.2 cũng đang chờ phép thử này.
* **Chưa hiệu chỉnh:** `MAX_OVERLAP_WORDS = 12`, `WINDOW_LINES = 120`,
  `RMS_FLOOR = 0.005`.
* **Chưa bấm giờ** một cuộc họp dài thật.
* `sendBeacon` khi đóng tab: chưa làm.
