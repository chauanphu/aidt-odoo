# AIDT — Biên bản cuộc họp (`aidt_meeting_minutes`)

Ghi âm cuộc gọi Discuss Meet **theo từng người**, tiền xử lý audio ở server,
bóc băng bằng `openai/whisper-large-v3`, lọc ảo giác, ghép thành bản bóc băng
có gán tên người nói, rồi tóm tắt bằng Gemma 3 12B QAT và đăng cả hai vào
chatter của cuộc họp.

Hướng dẫn cho người dùng cuối: [`docs/GUIDANCE.md`](../../docs/GUIDANCE.md), mục 2.

> ## ⚠️ Trạng thái kiểm chứng (05/08/2026, cập nhật cuối ngày — đợt chất lượng bóc băng)
>
> Đọc mục [§8](#8-những-gì-đã-và-chưa-được-kiểm-chứng) TRƯỚC KHI triển khai.
>
> **Bản bóc băng rỗng: đã tìm ra nguyên nhân và đã sửa.** `response_format`
> bị ghi cứng `verbose_json`, tức là đòi mốc thời gian ở một model không
> được huấn luyện kèm token mốc thời gian — `vinai/PhoWhisper-large` sinh
> vài token đặc biệt rồi EOS và trả về rỗng. Nay là tham số, mặc định
> `json` (§4, §8.2). Audio của một cuộc gọi THẬT, giọng người THẬT, đã chạy
> qua đúng đường ống thật và cho ra chữ tiếng Việt đăng lên chatter (§8.1).
>
> **Đợt sau đó đổi model và thêm hai lưới lọc** (§8.1.d): mặc định nay là
> `openai/whisper-large-v3` chứ không phải PhoWhisper — PhoWhisper *nghe*
> đúng nhưng *chọn sai từ* trên hội thoại kỹ thuật và không xuất dấu câu
> (`lô cồ` = "local", `hỗn hợp` = "cuộc họp"; bản ghi 1140). Kèm theo là một
> **cổng lọc tiếng nói phía server** (§2.7) và một **blocklist ảo giác**
> (§2.8), vì large-v3 ảo giác trên khoảng lặng NHIỀU hơn v2 chứ không ít
> hơn — hai thứ đó là điều kiện đi kèm bắt buộc của việc đổi model, không
> phải cải tiến rời.
>
> Ba giới hạn phải đọc trước khi tin:
>
> * **Độ chính xác tiếng Việt của large-v3 CHƯA từng được đo** trên một cuộc
>   họp thật, và **chưa từng được so trực tiếp với PhoWhisper** — không còn
>   audio nào để so, `audio_retention_days = 0` đã xoá (§8.3).
> * Cổng lọc chặn được audio *gần rỗng*, **không** chặn được audio *to nhưng
>   suy biến*: một tông 440 Hz ở RMS 0.198 vẫn đi lọt và vẫn ảo giác (§8.1.d).
> * **Chưa có lượt chạy nào qua micro trình duyệt thật với hai máy** sau bản
>   sửa (§8.3).

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
   (trình duyệt, §2.5)                                       ↓  cron mỗi phút
                                              audio_prep._prepare()  (§2.7)
                                              MP3 → 16 kHz mono → CỔNG LỌC
                                              TIẾNG NÓI → highpass+speechnorm
                                              → WAV
                                                    ↓ trượt cổng: done, 0 đoạn,
                                                    ↓ ghi `skip_note` (§2.9),
                                                    ↓ KHÔNG gọi ASR
                                              asr_client._transcribe()  (HTTP)
                                                             ↓
                                              text_filter._filter_segments()
                                              blocklist ảo giác (§2.8)
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
start = min(max(item['start_ms'], 0), self.duration_ms)   # KẸP CẢ start
end = item['end_ms']
if end is None:                 # dịch vụ không trả mốc ⇒ phủ trọn mẩu
    end = self.duration_ms
end = min(end, self.duration_ms)    # không thể kết thúc ngoài mẩu
end = max(end, start)               # không thể kết thúc trước khi bắt đầu

'start_ms': self.offset_ms + start
'end_ms':   self.offset_ms + end
```

> ℹ️ Với cấu hình mặc định (`asr_response_format = json`, §4) **dịch vụ
> không trả mốc thời gian nào cả**: mỗi mẩu cho đúng một đoạn `end_ms=None`,
> và mốc đến từ `offset_ms`/`duration_ms` do chính recorder đo. Độ mịn vì
> vậy chỉ bằng một mẩu (~15 s cho mỗi lượt nói) — thô hơn, nhưng đến từ
> đồng hồ của trình duyệt đã ghi âm chứ không từ model. Phần kẹp dưới đây
> chỉ chạy khi ai đó đặt `verbose_json` — nay là một cấu hình **chạy được**
> cả với model mặc định `openai/whisper-large-v3`, không còn chỉ dành cho
> dịch vụ bên thứ ba (§4.2) — và vẫn phải giữ nguyên vì lý do y hệt.

**Mốc thời gian từ ASR là ĐẦU VÀO NGOÀI, KHÔNG TIN ĐƯỢC** — phải kẹp chứ
không chuyển tiếp nguyên văn. Đã thấy thật: service trả `end: 40.08` cho một
mẩu dài 8.208 s, sinh ra hàng `start_ms=16860, end_ms=4980` trong CSDL
(`end_ms` **nhỏ hơn** `start_ms`, vô nghĩa theo chính ngữ nghĩa của hai
trường). Đoạn suy biến bị thu về độ dài 0 chứ không bị vứt đi — `text` vẫn là
nội dung thật.

Nay đã biết **vì sao** những mốc ấy vô nghĩa: chúng là đầu ra của
`vinai/PhoWhisper-large` — một model KHÔNG có token mốc thời gian — bị ép trả
về mốc thời gian (§8.2). Đó là lý do để **giữ** phần kẹp, không phải lý do để
bỏ: model mặc định đã đổi, nhưng bất kỳ dịch vụ nào cũng vẫn là **đầu vào
ngoài**, và không ai đã đo mốc của large-v3 trên audio họp thật.

`start` phải kẹp **riêng**, và ràng buộc CSDL không thể làm hộ: `end` được
suy ra TỪ `start`, nên một `start` sai kéo `end` sai theo đúng chiều hợp lệ và
`CHECK (end_ms >= start_ms)` vẫn cho qua. `start_ms` lại là thứ
`transcript_builder._build` **sắp xếp** toàn bộ bản bóc băng theo, đồng thời
là thứ phép khử trùng mối nối dùng để biết hai đoạn có liền nhau hay không —
một giá trị hỏng vừa ném một câu nói đi vài phút, vừa vô hiệu hoá việc khử
trùng cho chính người đó.

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
* Đoạn lặp **không bắt buộc nằm sát đuôi** mẩu trước: thử thêm
  `MAX_OVERLAP_BACKSEARCH = 6` vị trí lùi dần vào trong (dò lùi, lấy từ dự án
  tham chiếu `STT_T-m-T-t-AI`). Lý do: hai mẩu liền nhau bóc băng **độc lập**
  cùng 1.5 giây audio, nên mẩu trước hay đẻ thêm vài từ ở đuôi mà mẩu sau
  không nghe ra — chỉ **một** từ thừa như vậy là phép khớp sát-đuôi trượt
  sạch và biên bản lặp chữ. Trong cùng độ dài thì ưu tiên vị trí **phải
  nhất**: sát đuôi mới là mối nối thật, các vị trí lùi chỉ là phương án dự
  phòng.
* **Tối thiểu 2 từ mới xoá.** Hai hướng sai không cân nhau: xoá thiếu để lại
  một từ lặp mà người đọc *nhìn thấy* và tự sửa được; xoá thừa làm **mất nội
  dung âm thầm** trong một biên bản chính thức. Tiếng Việt lại đầy từ đệm một
  âm ("vâng", "dạ", "rồi", "được") vừa kết câu này vừa mở câu sau, nên khớp
  1 từ là trùng hợp phổ biến chứ không phải bằng chứng về mối nối.
* Chỉ khử giữa **hai đoạn liền nhau của cùng một người**.

Cố ý **không** port tầng khớp theo **ký tự** của dự án tham chiếu (hậu tố 120
ký tự, tối thiểu 5 ký tự): với tiếng Việt đơn âm, 5 ký tự chỉ là một từ rưỡi
("cuộc", "họp l") — lỏng tới mức xoá cả nội dung thật. Chuẩn hoá khi so cũng
giữ nguyên `lower()` + `strip('.,;:!?')`, **không** dùng
`re.sub(r"[^\w\s]", "", …)` của họ (nó làm `TP.HCM` == `TPHCM`, tức khớp dễ
hơn hẳn). Đang nới một knob (dò lùi) mà nới thêm knob thứ hai cùng lúc, không
có dữ liệu hiệu chỉnh nào, là cộng dồn rủi ro xoá nhầm theo hướng không đo
được.

> ⚠️ `MAX_OVERLAP_WORDS = 12` và `MAX_OVERLAP_BACKSEARCH = 6` đều là **ước
> lượng theo giả định** (nói nhanh cỡ nào cũng khó vượt 12 từ trong 1.5 s; 6
> vị trí ≈ nửa giây lời nói), **chưa hiệu chỉnh** trên đầu ra ASR thật. Tương
> tự `WINDOW_LINES = 120` ở `summary_client`.

### 2.5. Hai cổng chặn im lặng, ở hai tầng khác nhau

Có **hai** cổng, và chúng không thay thế nhau. Cổng trình duyệt quyết định
**có gửi mẩu lên hay không** (tiết kiệm băng thông, và không bao giờ để lời
nói riêng lúc tắt micro lọt lên server). Cổng server quyết định **có gọi ASR
hay không** (§2.7) và là cổng duy nhất đo được audio theo từng khung.

**Cổng phía trình duyệt** (`recorder_service.js`):

* **Tắt tiếng thật** (`rtc.localSession.isMute`): chốt phần đã thu rồi
  **ngừng hẳn mã hoá**. Clone giữ `enabled` riêng với track gốc nên nó vẫn
  nghe thấy mọi thứ sau khi người dùng bấm tắt micro — cứ mã hoá tiếp là cả
  đoạn nói riêng đó lên thẳng biên bản dưới tên họ. **Không** thay bằng
  khung im lặng: nhét khoảng lặng số vào MP3 đúng là kiểu đầu vào làm Whisper
  bịa chữ.
* **`RMS_FLOOR = 0.005`**: mẩu dưới ngưỡng năng lượng này bị bỏ, không gửi.
  ⚠️ Ngưỡng theo ĐỘ TO TRUNG BÌNH của cả mẩu, nên nó **không** chặn được mẩu
  "2 giây nói + 13 giây im lặng" — đúng dạng làm Whisper bịa chữ.
* `shouldUpload(track, rms)` đọc cờ "mẩu này có chứa tiếng micro thật hay
  không" (`chunkHasAudio`), **không** đọc `MediaStreamTrack.enabled` — cờ đó
  bị kích hoạt-bằng-giọng-nói bật/tắt nhiều lần mỗi giây.

**Ngưỡng 0.005 này ĐÃ ĐO ĐƯỢC là quá dễ dãi, không còn là nghi vấn.** Ngày
05/08/2026, một tệp nhiễu Gauss "nền phòng" ở **RMS 0.00599** — tức **vượt**
`RMS_FLOOR` — được gửi thẳng vào chính dịch vụ đang chạy và trả về câu bịa
`"Cảm ơn các bạn đã theo dõi và hẹn gặp lại."` (§8.1.d). Trước đợt sửa này,
đúng loại audio đó đi lọt lên tới ASR và đẻ ra một câu không ai nói.

`RMS_FLOOR` **vẫn giữ nguyên 0.005**, có chủ ý: đổi nó là đổi hành vi ở tầng
mà ta không đo được (micro thật, phòng thật, đủ loại card âm thanh), trong
khi cổng server (§2.7) chặn đúng ca đó với bằng chứng đo được và có thể sửa
mà không cần nạp lại asset của trình duyệt. Trình duyệt gửi thừa vài mẩu im
lặng chỉ tốn băng thông; server mới là nơi quyết định có hỏi model hay không.

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

### 2.7. Tiền xử lý ở server: `models/audio_prep.py`

Chạy trong `_process_one`, **giữa** lúc đọc `ir.attachment` và lúc gọi
`_transcribe`. `_prepare(raw, duration_ms)` trả `(wav_bytes, None)` hoặc
`(None, lý_do)`, và **không bao giờ ném lỗi** — bên gọi bọc mọi ngoại lệ
bằng `_mark_retry`, nên một byte hỏng thoát ra khỏi đây sẽ đốt cả ba lượt
retry rồi kết thúc bằng `failed`, trong khi sự thật chỉ là "mẩu này không có
gì để bóc băng".

Bốn bước, **thứ tự không được đổi**:

| Bước | Làm gì | Vì sao |
|---|---|---|
| 1. Giải mã | MP3 → `float32` mono `SAMPLE_RATE = 16000` (PyAV) | Mọi checkpoint dòng Whisper đều tự hạ về 16 kHz bên trong; làm sẵn thì ta biết chính xác model nghe thấy gì. Đi qua `s16` rồi chia 32768 chứ không lấy thẳng `flt`: cổng lọc phải đo trên **đúng** những con số sẽ nằm trong tệp WAV gửi đi. Nhớ xả bộ lấy mẫu (`resample(None)`) — bỏ bước đó là mất vài chục ms cuối MỖI mẩu, đúng chỗ mà phần chồng lấn 1.5 s sinh ra để bảo vệ. |
| 2. **Cổng lọc tiếng nói** | Khung 20 ms, RMS từng khung; cần ≥ `MIN_VOICED_FRAMES = 5` khung vượt `VOICED_RMS = 0.01` | Trượt ⇒ **không gọi ASR**, mẩu thành `done` với 0 đoạn và một `skip_note` (§2.9). |
| 3. Điều kiện hoá | `highpass f=80` → `speechnorm e=3:r=0.0001:l=1` | Dưới 80 Hz gần như không còn gì thuộc tiếng nói (F0 nam trầm nhất ~85 Hz), chỉ còn ù điện 50 Hz và trôi DC — cắt trước khi cân mức, nếu không `speechnorm` cân theo cả phần rác đó. Dùng `speechnorm` chứ **không** `loudnorm`: `loudnorm` một lượt cần vài giây mới hội tụ, mà mỗi mẩu 15 s của ta được giải mã RIÊNG, nên lỗi đó lặp ở đầu **mọi** mẩu. |
| 4. Mã hoá | WAV `pcm_s16le` 16 kHz mono, header RIFF tự ghép | `_part_content_type()` đã map sẵn `.wav`, nên request nói đúng kiểu MIME. Kẹp về `[-1, 32767/32768]` **trước** khi nhân: `+1.0` không biểu diễn được bằng `int16`, tràn sẽ lật một đỉnh dương thành đỉnh âm — nghe thành tiếng "tách", đúng kiểu tạo tác làm ASR bịa chữ. |

**Cổng chạy TRƯỚC điều kiện hoá, không được đảo.** `speechnorm` khuếch đại
tới 3 lần, nên chạy nó trước sẽ kéo nền phòng im lặng vượt lên trên ngưỡng và
vô hiệu hoá đúng cái cổng nó vừa đi qua. Cổng phải đo tín hiệu như micro thật
sự nghe thấy.

**Độ dài phải được bảo toàn từ đầu đến cuối.** Không cắt khoảng lặng, không
xén hai đầu, không đổi tốc độ — `_write_segments` ánh xạ mốc ASR lên
`offset_ms`/`duration_ms` do recorder đo, nên rút ngắn audio 2 giây không làm
ASR trả mốc nhỏ đi 2 giây theo; nó chỉ làm **mọi** câu trong mẩu bị đặt sai
chỗ, sai một cách trông vẫn hợp lệ. `_condition()` tự kiểm điều này và **lùi
về tín hiệu gốc** nếu số mẫu đổi. Cũng vì vậy `_condition()` không bao giờ
ném lỗi: điều kiện hoá là phần THÊM VÀO, để một lỗi ở đó làm hỏng cả mẩu là
đổi một cải tiến lấy một sự cố.

**Cố ý KHÔNG có ở đây:** khử nhiễu (`afftdn`/`arnndn`) — audio đến từ track
mic WebRTC vốn đã qua noise-suppression và AGC của trình duyệt, chồng bộ khử
nhiễu thứ hai lên tiếng nói đã xử lý là làm nó méo thêm chứ không sạch thêm;
và `silenceremove` — xem đoạn trên. Cũng **không** dùng Silero VAD: cần
`onnxruntime` trong ảnh Odoo cộng một tệp model, chỉ thêm nếu đo được rằng
cổng năng lượng theo khung không đủ.

`_warn_if_duration_mismatch()` chỉ **ghi log** khi độ dài giải mã được lệch
quá `max(200 ms, 10%)` so với `duration_ms` recorder khai báo — tuyệt đối
không bỏ mẩu. Hai cách đo khác nhau (`performance.now()` vs đếm mẫu) thì lệch
chút là bình thường; lệch nhiều nghĩa là mọi mốc của mẩu đó sẽ bị kẹp sai, và
đó là thứ đáng để lại dấu vết chứ không phải thứ nên tự đoán rồi tự sửa.

> #### ⚠️ Cổng này chặn được gì, và KHÔNG chặn được gì
>
> **Chặn được, đã đo (§8.1.d):** im lặng số, nhiễu nhỏ, và nhiễu "nền phòng"
> ở RMS 0.00599 — cả ba đều làm `openai/whisper-large-v3` bịa ra một câu hoàn
> chỉnh, và hàng 0.00599 còn **vượt** `RMS_FLOOR` của trình duyệt.
>
> **KHÔNG chặn được, cũng đã đo:** tông 440 Hz ở RMS 0.19797 — to hơn khối
> tiếng nói thật — vẫn ảo giác. Mọi khung của nó đều vượt ngưỡng nên cổng cho
> qua, và đúng ra là phải cho qua: một luật theo **độ to** không có cách nào
> biết nội dung suy biến. Lưới thứ hai cho ca này là §2.8.
>
> **Đã thử và đã loại:** lọc theo độ tự tin của model. Bốn ca ảo giác trên
> cho `avg_logprob` −0.108 / −0.135 và `compression_ratio` 0.88–0.94 — model
> tự tin y hệt lúc bóc băng đúng. Đừng quay lại ý đó.
>
> **`VOICED_RMS = 0.01` có bằng chứng; `MIN_VOICED_FRAMES = 5` thì KHÔNG.**
> 0.01 là ngưỡng THẤP NHẤT còn chặn được tệp 0.00599 với biên thật (khung to
> nhất của tệp đó là 0.00693, tức 0/750 khung vượt ngưỡng). Quét trên tín
> hiệu tổng hợp cho khoảng cách nhiễu/tiếng-nói **1.45 lần** và tỉ số đó
> **không đổi theo ngưỡng** (đã quét 0.008/0.01/0.012/0.015/0.02) — nghĩa là
> chọn ngưỡng không phải chọn "cổng tốt hơn" mà chỉ là trượt cả cửa sổ. Còn
> số 5 (= 100 ms) thuần tuý là lập luận trên độ dài âm tiết tiếng Việt
> (~100–150 ms), **chưa có phép đo nào chống lưng**: bốn tệp đo được đều là
> tín hiệu ĐỀU nên chúng quyết định ở `VOICED_RMS`, không chạm tới hằng số
> này.
>
> Mọi hằng số ở đây nghiêng về phía **GIỮ**, và hai vế không cùng giá: bỏ
> nhầm một mẩu CÓ tiếng nói xoá tới 15 giây biên bản mà **không có gì trên
> giao diện** nói cho người dùng biết đoạn đó từng tồn tại; cho nhầm một mẩu
> im lặng đi qua chỉ tốn một lời gọi ASR và một câu ảo giác mà §2.8 còn cơ
> hội bắt lại.

### 2.8. Lưới thứ hai: blocklist ảo giác (`models/text_filter.py`)

21 mẫu regex (lời chào kênh, lời cảm ơn cuối video, dòng bản quyền, `www.…`)
lấy từ `HALLUCINATION_PATTERNS` của dự án tham chiếu `STT_T-m-T-t-AI`, nơi
chúng đã chạy thật trên tiếng Việt. Giữ gần nguyên văn là **có chủ ý**: đây
là dữ liệu quan sát được từ đầu ra thật của model, không phải thứ nên "cải
tiến" bằng suy đoán. Thêm mẫu mới thì thêm khi **bắt được** nó trong một bản
bóc băng thật, kèm ngày và ngữ cảnh.

Hai khác biệt bắt buộc so với bản gốc:

* **Bỏ theo TỈ LỆ, không bỏ theo "có khớp hay không".** Bên kia `re.search`
  rồi xoá **toàn bộ** văn bản nếu bất kỳ mẫu nào khớp ở bất kỳ đâu. Với phụ
  đề tiêu dùng thì hợp lý; với một lát 15 giây của biên bản họp hành chính
  thì quá tàn phá — một người nói thật câu "cảm ơn các bạn đã theo dõi" ở
  cuối phần trình bày sẽ âm thầm xoá 15 giây biên bản. Ở đây chỉ bỏ khi phần
  khớp phủ ≥ `HALLUCINATION_COVERAGE = 0.4` số ký tự, tính trên **HỢP** các
  vùng khớp (cộng dồn sẽ vượt 1.0 khi các vùng chồng nhau; xét riêng từng
  vùng thì ca ảo giác nhiều câu điển hình nhất lại lọt lưới).
* **Bốn mẫu `.*` không chặn đã đổi thành `.{0,N}`.** Bên kia xoá cả đoạn ngay
  khi khớp nên độ dài `.*` không đổi kết quả; ở đây một `.*` tham lam tự nó
  thổi tỉ lệ lên gần 1.0. Ca thật: `hẹn gặp lại.*video` nuốt trọn 84% câu
  *"Hẹn gặp lại các đồng chí vào tuần sau, chúng ta sẽ xem lại video hướng
  dẫn"* — một câu hoàn toàn bình thường.

Một mẫu còn phải **sửa** so với bản gốc: `nh[uư]ng` của họ **không khớp
được** `những` (`ữ` là ký tự Unicode riêng, không phải `ư`), nên mẫu gốc
trượt đúng nửa sau câu ảo giác đo được, kéo tỉ lệ xuống 0.31 và cho cả câu
lọt lưới. Nay là `nh[uưữ]ng`.

Hai luật **cố ý không port**:

* `len(text) <= 3` — ở biên bản họp tiếng Việt, những lượt nói ngắn nhất lại
  thường là lượt mang tính pháp lý nhất: "Dạ" (2), "Ừ" (1), "OK" (2) là tiếng
  đồng ý của người chủ trì. Thứ luật đó thật sự bắt được — chuỗi chỉ có dấu
  câu — đã có `_has_no_word_char()` phủ tổng quát hơn mà không đụng tới chữ.
* `normalize_vietnamese_text` — nó `.lower()` mọi từ không đứng đầu câu, biến
  "Nguyễn Ngọc Thịnh" thành "Nguyễn ngọc thịnh". Trong một văn bản chủ yếu là
  tên người và tên cơ quan, đó là làm hỏng dữ liệu. large-v3 tự xuất đúng hoa
  thường và dấu câu; PhoWhisper mới là lý do ta từng không có.

Đoạn khớp mẫu nhưng **dưới** ngưỡng thì được **giữ** và ghi `INFO` vào log —
để còn hiệu chỉnh `HALLUCINATION_COVERAGE` bằng dữ liệu thật về sau.

> ⚠️ **0.4 hiệu chỉnh trên đúng BỐN ca** (§8.1.d). Ngưỡng nào trong khoảng
> (0.16, 0.62) cũng phân tách đúng bốn ca đó; 0.4 chỉ là điểm chừa biên hai
> phía. Tập mẫu nhỏ ⇒ đây là hiệu chỉnh sơ bộ, **không phải số chốt**.

### 2.9. `skip_note`: nội dung bị bỏ CÓ CHỦ Ý, khác `error`

`aidt.meeting.chunk.skip_note` ghi lại phần nội dung đã bị bỏ đi có chủ ý
(mẩu trượt cổng §2.7, hoặc đoạn bị §2.8 nhận là ảo giác). Mẩu vẫn `done` —
**không có gì hỏng cả**.

Vì sao phải là trường riêng chứ không nhét vào `error`:

* Hai thứ dẫn tới **hai hành động khác nhau**: `error` là thứ cần sửa hạ
  tầng; `skip_note` là thứ cần hiệu chỉnh ngưỡng.
* Gộp chung sẽ biến mọi mẩu im lặng bình thường thành một mẩu "lỗi" và làm
  hỏng luôn ý nghĩa của trạng thái `failed`.
* Và quan trọng nhất: `transcript_builder._gap_markers()` in một dòng
  `[thiếu âm thanh …]` cho **mọi** mẩu `failed`. Đánh dấu mẩu im lặng là
  `failed` sẽ biến mỗi quãng lặng bình thường của cuộc họp thành một lời cáo
  lỗi giữa biên bản — và còn đốt ba lượt retry cho một việc chắc chắn ra cùng
  kết quả.

**Hệ quả người dùng thấy được, phải nói rõ:** một mẩu trượt cổng lọc **không
để lại dấu vết nào trong bản bóc băng** — không có chữ, và cũng **không** có
dòng `[thiếu âm thanh …]`. Dấu vết duy nhất nằm ở `skip_note` trên bản ghi
mẩu, mà người dùng cuối không xem được. Đó là lý do lý do trả về từ
`_has_speech()` **bắt buộc phải có số đo** (`0/750 khung 20 ms vượt RMS
0.01`; RMS đỉnh khung; RMS cả mẩu): người đọc nó là người đang tự hỏi "vì sao
15 giây của tôi biến mất" và cần phân biệt "micro tắt" với "ngưỡng đặt sai".
Xem `docs/GUIDANCE.md` §2.9 cho phía người dùng.

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

Đừng nhầm với mẩu **trượt cổng lọc tiếng nói**: mẩu đó là `done` (không hỏng
gì cả), có `skip_note`, **0 đoạn**, và **không** sinh dòng `[thiếu âm thanh
…]` nào. Xem §2.7 và §2.9 — đây là hai trạng thái trông giống nhau trong CSDL
nhưng có ý nghĩa ngược nhau với người đọc biên bản.

Mọi chỗ có thể ném lỗi tầng CSDL đều bọc SAVEPOINT riêng
(`_process_one`, `_run_summary`, `_purge_own_audio`, `_cron_purge_audio`, và
**từng bản ghi** trong cả hai vòng lặp của `_cron_sweep`) — không bọc thì một
lỗi SQL đầu độc cursor và câu ghi-lỗi ở khối `except` **ném tiếp**, rollback
luôn transcript vừa ghi. Với cron thì hậu quả là **âm thầm và lặp lại**: một
`aidt_meeting.audio_retention_days` gõ sai giết lượt dọn audio mỗi ngày mãi
mãi, và một `_broadcast_state` hỏng (bus không sẵn sàng, kênh vừa bị xoá)
chặn mọi bản ghi khỏi được quét ở **mọi** phút sau đó. Cùng khuôn mẫu với
`aidt_search/models/index_job.py`.

> ### ⚠️ Cuộc đua đã biết, CHƯA sửa: mẩu về muộn ngay lúc hoàn tất
>
> Một request `/aidt_meeting/chunk` đọc thấy `state='processing'` ngay TRƯỚC
> khi `_finalize` commit `done` vẫn tạo được mẩu; mẩu đó vẫn được bóc băng,
> nhưng vòng `processing` của `_cron_sweep` không còn thấy bản ghi đó nữa nên
> bản bóc băng **không bao giờ được dựng lại**.
>
> Đây **không** phải đã sửa bằng khoá — chỉ không còn vô hình:
> `_store` đọc lại trạng thái sau khi ghi và **log WARNING** nếu trúng cửa sổ
> đó, và `_cron_sweep._sweep_late_chunks()` xét lại các bản ghi hoàn tất trong
> `REFINALIZE_WINDOW_MINUTES = 10` phút gần đây, so số đoạn hiện tại với
> `finalized_segment_count` đã chụp lúc hoàn tất, và dựng lại nếu lệch (đăng
> lại chatter). Ngoài cửa sổ đó thì thôi — một bản ghi đã đăng từ lâu không
> được tự ý đăng lại.

---

## 4. Cấu hình ASR / LLM

**Cài đặt → Biên bản cuộc họp** (`res_config_settings_views.xml`), hoặc
**Cài đặt → Kỹ thuật → Tham số hệ thống**.

Trang cài đặt chia làm hai khối. Khối **Dịch vụ AI** có ba ô: *Bóc băng*
(URL / Model / API key / Khuôn dạng kết quả), **Chất lượng bóc băng** (Ngôn
ngữ / Temperature / Mồi vốn từ) và *Tóm tắt*. Ba tham số giải mã được tách
riêng có chủ ý: những trường kia là **địa chỉ** dịch vụ (đặt một lần rồi
quên), còn ba trường này là **chất lượng** bản bóc băng — thứ người vận hành
quay lại chỉnh nhiều lần; gộp chung sẽ chôn chúng dưới ô API key.

| Tham số | Nhãn trên UI | Mặc định |
|---|---|---|
| `aidt_meeting.asr_url` | URL dịch vụ bóc băng | `http://aidt-asr:8002/v1` |
| `aidt_meeting.asr_model` | Model bóc băng | `openai/whisper-large-v3` |
| `aidt_meeting.asr_api_key` | API key dịch vụ bóc băng | *(rỗng)* |
| `aidt_meeting.asr_response_format` | Khuôn dạng kết quả bóc băng | `json` |
| `aidt_meeting.asr_language` | Ngôn ngữ bóc băng | `vi` |
| `aidt_meeting.asr_temperature` | Temperature bóc băng | `0` |
| `aidt_meeting.asr_prompt` | Mồi vốn từ (prompt) | *(đoạn ~289 ký tự, xem §4.3)* |
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
  trường `model`, `response_format`, `file`. Đặt `asr_url` =
  `https://api.openai.com/v1`, `asr_model` = `whisper-1`, `asr_api_key` =
  khoá. `_parse()` đọc `segments[].{start,end,text}`, và lùi về `text` phẳng
  nếu không có `segments`.

* **Tóm tắt** — cần `POST {llm_url}/chat/completions` tương thích OpenAI.
  `_chat()` đọc `choices[0].message.content`. Đặt `llm_url`, `llm_model`,
  `llm_api_key` tương ứng.

Có API key ⇒ header `Authorization: Bearer …`. Rỗng ⇒ không gửi header.
Timeout cả hai: `TIMEOUT = 300` giây.

### 4.2. `asr_response_format`: `json` hay `verbose_json`

Chỉ nhận đúng hai giá trị này (`RESPONSE_FORMATS` ở `asr_client.py`); giá trị
lạ lùi về `json` kèm cảnh báo trong log. Không có `text` — thân trả về khi đó
là chữ thuần, `json.loads()` sẽ ném lỗi.

| | `json` *(mặc định)* | `verbose_json` |
|---|---|---|
| Dịch vụ trả về | chỉ `text` | `segments[].{start,end,text}` |
| Mốc thời gian đến từ | `offset_ms`/`duration_ms` **do recorder đo** | model |
| Độ mịn | một mẩu (~15 s / lượt nói) | từng lượt nói |
| Chạy được với | **mọi** model | chỉ model có token mốc thời gian |

Mặc định xuất xưởng **vẫn là `json`**, nhưng **lý do đã đổi** kể từ khi model
mặc định là `openai/whisper-large-v3`. Đọc kỹ, vì tài liệu cũ nói một điều
không còn đúng với model hiện tại:

* **Với `vinai/PhoWhisper-large` (mặc định CŨ):** `verbose_json` cho bản bóc
  băng **RỖNG**, không lỗi, không cảnh báo — PhoWhisper là bản tinh chỉnh
  **không có token mốc thời gian**, nó sinh vài token đặc biệt rồi EOS. Đây
  là sự cố đã làm tính năng vô dụng suốt nhiều task (§8.2). Đo thật ngày
  05/08/2026, cùng một tệp 15.084 s, cùng gateway vLLM, **chỉ đổi trường
  này**:

  ```
  verbose_json -> {"duration": "15.084", "language": "vi", "text": "", "segments": []}
  json         -> {"text": "nhà trưởng nguyễn ngọc thịnh nhận tiền cho nhà thiết kế…"}
  ```

* **Với `openai/whisper-large-v3` (mặc định HIỆN TẠI): lý do đó KHÔNG còn áp
  dụng.** Whisper gốc **có** token mốc thời gian. Đã kiểm chứng 05/08/2026
  trên chính gateway đang chạy: `verbose_json` **hoạt động**, trả về
  `segments[]` với mốc thời gian thật theo từng lượt nói, kèm cả `avg_logprob`
  và `compression_ratio`. Tức là **đổi sang `verbose_json` nay là một lựa
  chọn sống**, không còn là cách tự bắn vào chân mình.

**Vậy vì sao mặc định vẫn là `json`?** Vì việc chuyển **chưa được áp dụng và
chưa được đánh giá**: mốc do model trả về là **đầu vào ngoài, không tin
được** (§2.3 — chính dịch vụ này đã từng trả `end: 40.08` cho một mẩu 8.208 s),
còn mốc từ `offset_ms`/`duration_ms` đến từ đồng hồ của trình duyệt đã ghi âm.
Đổi sang `verbose_json` là đổi **nguồn sự thật của mọi mốc thời gian** trong
biên bản để lấy độ mịn tốt hơn, và chưa ai đo được cái giá của vế đầu trên
audio họp thật. Hạng mục còn mở, ghi ở §8.3.

Trỏ sang OpenAI/Deepgram thì cũng **nên** cân nhắc `verbose_json` vì lý do y
hệt: những dịch vụ đó trả mốc thời gian đúng nghĩa.

> ⚠️ Đặt `verbose_json` **chỉ** an toàn khi model phía sau có token mốc thời
> gian. Ai trỏ `asr_model` ngược lại một checkpoint tinh chỉnh kiểu PhoWhisper
> mà quên đổi trường này sẽ nhận đúng sự cố cũ: HTTP 200, không cảnh báo, bản
> bóc băng rỗng. Phần xử lý phòng thủ trong `asr_client.py`
> (`_is_degenerate_segment_crash`) được **giữ nguyên** đúng vì cấu hình đó vẫn
> hợp lệ.

### 4.3. Ba tham số giải mã: `asr_language`, `asr_prompt`, `asr_temperature`

Ba trường này quyết định chất lượng bản bóc băng nhiều hơn hẳn URL/API key,
và trước 19.0.1.1.0 **không trường nào trong ba được gửi đi cả**.

> ⚠️ **Trước khi thêm bất kỳ trường form nào nữa, hãy đọc chỗ này.** Gateway
> vLLM **bỏ qua im lặng** mọi trường `multipart` nó không biết. Đo thật
> 05/08/2026: bốn tên bịa (`khong_ton_tai`, `foo`, `initial_prompt`,
> `temperatur`) đều trả HTTP 200 với kết quả **y hệt** baseline, không một
> lỗi 400 nào. Nên "gửi đi mà không lỗi" **không chứng minh** trường đó có
> tác dụng — phải chứng minh bằng kết quả giải mã đổi, hoặc bằng việc server
> bắt lỗi giá trị sai. Cả ba trường dưới đây đều có bằng chứng loại đó. (Chú
> ý luôn: tên đúng là `prompt`; `initial_prompt` — tên tham số của thư viện
> whisper gốc — là một trong bốn tên bị nuốt im lặng.)

**`asr_language` (mặc định `vi`).** Whisper là model đa ngôn ngữ: không gửi
`language` thì nó **tự đoán**, và đoán lại cho **từng** cửa sổ 30 giây. Ta
cắt mẩu 15 giây và gửi mỗi mẩu thành một request riêng ⇒ mỗi mẩu là một lần
đoán độc lập, một cuộc họp có thể lật sang tiếng Anh giữa chừng mà không có
gì báo. Đã quan sát thật PhoWhisper bóc một tệp thử tiếng Anh ra tiếng Anh,
tức lớp tự đoán này CÓ hoạt động và CÓ lật. Bằng chứng trường này đổi kết quả
thật (cùng tệp 2 giây, cùng model, chỉ đổi trường này):

```
(không gửi language) -> {"text": "n."}
language=en          -> {"text": " (tone ringing)"}
```

**Rỗng ở đây có nghĩa thật**: "để dịch vụ tự nhận dạng" — đường thoát duy
nhất cho cuộc họp song ngữ, hoặc cho dịch vụ bên thứ ba không nhận mã ISO của
Whisper. Vì vậy rỗng ⇒ **bỏ hẳn trường**, không gửi chuỗi rỗng (`language=''`
là một mã không hợp lệ ⇒ HTTP 400, chứ không phải "tự nhận dạng"). Khác
`_response_format`, chỗ mà rỗng không có nghĩa gì nên code phải tự lấp mặc
định.

**`asr_prompt`** — `initial_prompt` của Whisper, tức **cần gạt sửa TỪ SAI**.
Whisper coi prompt như văn bản đứng ngay trước đoạn audio nên nó mồi cả **vốn
từ** lẫn **văn phong** (prompt mặc định viết hoa và chấm câu đầy đủ là cố ý).
Vốn từ trong prompt mặc định nhắm thẳng vào các từ đã bóc **sai thật** ở bản
ghi 1140:

| PhoWhisper trả về | Đúng ra là |
|---|---|
| `lô cồ` | local |
| `con ngôi đồ` / `con mua đồ` | con model |
| `ghim` / `găm` | ghi âm |
| `hỗn hợp` | cuộc họp |
| `vương bị trần quyền` | vấn đề phân quyền |

Bằng chứng trường này đổi kết quả thật (cùng tệp, cùng model, cùng
`language=en`, chỉ thêm/bớt trường này):

```
(không prompt)                                      -> " (tone ringing)"
prompt='A telephone is ringing in an empty office.' -> " [phone ringing]"
```

> #### ⚠️ `ASR_PROMPT_MAX_CHARS = 400` là ràng buộc CỨNG, không phải phép làm đẹp
>
> Gateway **không tự cắt bớt prompt dài — nó TỪ CHỐI CẢ REQUEST.** Đo thật
> 05/08/2026 với prompt tiếng Việt: 400 / 500 / 600 / 800 ký tự ⇒ HTTP 200;
> **1000 ký tự ⇒ HTTP 400 "This model's maximum context length is 448
> tokens"**. Qua `_transcribe` thì 400 đó thành `AsrError` ⇒ **đốt sạch lượt
> retry** ⇒ mẩu `failed`. Nghĩa là một quản trị viên dán nguyên bảng thuật
> ngữ vào ô cấu hình sẽ làm **CHẾT** toàn bộ việc bóc băng, chứ không phải
> làm nó kém đi. Cắt ở tầng code biến sự cố đó thành không thể xảy ra.
>
> Vì sao 400 ký tự: `initial_prompt` bị giới hạn 224 token (nửa ngữ cảnh 448;
> bản gốc `openai/whisper` chỉ giữ 223 token **cuối** rồi vứt phần đầu).
> Container Odoo **không có** tokenizer của Whisper nên phải quy đổi ra ký
> tự — đo bằng tokenizer `openai/whisper-large-v3` chạy trong chính container
> `aidt-asr`, trên ba mẫu tiếng Việt thật: **2.18–2.45 ký tự/token**. Lấy sàn
> 2.18 thì 400 ký tự ≈ 183 token. Đây là quy đổi **thực nghiệm**, không phải
> bảo đảm toán học: một chuỗi bịa toàn dấu phụ hiếm (`ựỡễỷữ…`) đo được 0.81
> ký tự/token, tức 400 ký tự có thể thành ~490 token — chấp nhận, vì ngay cả
> ca bệnh lý đó cũng chỉ làm mẩu lỗi **thấy được** chứ không hỏng dữ liệu âm
> thầm.
>
> Cắt ở **ĐẦU** (giữ phần đầu) là có chủ ý: whisper gốc cắt ngược lại, nên để
> mặc thì phần bị vứt là câu mở đầu định hình văn phong. Ta chọn phần nào
> sống sót, không phải model chọn hộ.
>
> Prompt mặc định **chỉ có một bản duy nhất**, ở `data/ir_config_parameter.xml`
> (`param_asr_prompt`, 289 ký tự). Cố ý **không** có bản sao trong Python: một
> đoạn văn ~300 ký tự để ở hai nơi thì chắc chắn sẽ lệch, và bản trong code sẽ
> là bản KHÔNG chạy (`_prompt()` chỉ đọc cấu hình).
>
> Trường ở `res.config.settings` là `Char` chứ **không phải** `Text`, và đây
> không phải tuỳ tiện: `res.config.settings.execute()` gọi
> `_get_classified_fields()`, hàm đó ném thẳng `Exception` cho mọi kiểu ngoài
> `boolean/integer/float/char/selection/many2one/datetime`. Với `Text` thì
> **cả trang Cấu hình không lưu được gì**, kể cả URL dịch vụ. Đã dính thật
> khi làm tính năng này — bốn test settings đổ cùng lúc.

**`asr_temperature` (mặc định `0`).** 0 = giải mã tham lam. Whisper mặc định
có cơ chế lùi: gặp mẩu khó thì nâng dần temperature để thoát vòng lặp. Với
biên bản họp hành chính, đặt 0 làm đầu ra **tái lập được** — chạy lại cùng
audio phải ra cùng chữ — và đó chính là điều kiện để nút **Bóc băng lại**
(§4.4) so sánh được các lần chỉnh cấu hình với nhau. Nhưng vẫn là tham số:
người bị mẩu lặp chữ nặng có thể muốn nới lên.

Trường này **luôn được gửi**, khác `language`/`prompt`: rỗng ở hai trường kia
có nghĩa thật, còn rỗng ở đây chỉ có nghĩa "dùng mặc định của dịch vụ", mà
mặc định đó khác nhau tuỳ dịch vụ. Gửi `0` tường minh thì hành vi giống nhau
ở mọi backend.

Giá trị lạ lùi về 0 kèm cảnh báo, đúng như `_response_format`, và **chặn cả
giá trị ngoài `[0, 2]` chứ không chỉ chặn chữ** (`'1e9'` là số hợp lệ với
`float()` nhưng vẫn cho 400). Server **không** bỏ qua giá trị hỏng — đo thật
05/08/2026: `temperature=5` ⇒ 400 *"temperature must be in [0, 2]"*;
`temperature=-1` ⇒ 400 *"temperature must be non-negative"*. Chuyển tiếp
nguyên văn một giá trị sai sẽ làm hỏng **mọi** lần bóc băng cho tới khi có
người phát hiện.

### 4.4. Nút "Bóc băng lại" — và vì sao mặc định xuất xưởng làm nó vô dụng

`action_retranscribe()` trên form bản ghi (§ mục dành cho quản trị viên trong
`docs/GUIDANCE.md`): đưa mọi mẩu **còn audio** về `pending` (xoá `attempt`,
`error`, `skip_note`, `next_retry_at`), đưa bản ghi về `processing` và đặt
`finalized_segment_count = 0`, rồi để `_cron_process`/`_cron_sweep` chạy lại
qua **cấu hình ASR hiện hành**. Kết quả là **một cặp bài đăng mới** trong
chatter, không sửa bài cũ.

Lý do tồn tại: không có nút này thì **mọi thay đổi về model, tham số giải mã
hay ngưỡng lọc đều KHÔNG ĐO ĐƯỢC** — cách duy nhất để so "trước/sau" là họp
thật thêm lần nữa và hy vọng người ta nói giống hệt, tức là không so được. Và
một bản bóc băng tệ cũng vì thế mà vĩnh viễn tệ.

> ### ⚠️ Với mặc định xuất xưởng, nút này gần như KHÔNG dùng được
>
> `audio_retention_days = 0` nghĩa là audio bị xoá **ngay lúc hoàn tất**
> (`_finalize` → `_purge_own_audio`). Nút này **không** tự nâng ngưỡng đó —
> `0` là một lựa chọn riêng tư **có chủ ý** cho biên bản họp hành chính, không
> phải sơ suất.
>
> Hệ quả thực tế: **muốn bóc băng lại được thì admin phải đặt
> `audio_retention_days > 0` TRƯỚC khi cuộc họp diễn ra.** Đặt sau khi họp
> xong là quá muộn — audio đã không còn, và không khôi phục được (§8.1.b).
> Không còn mẩu nào có audio ⇒ nút ném `UserError` nói rõ tham số nào đang
> chặn và giá trị hiện tại của nó.
>
> Ngay cả khi có audio: mỗi lượt chạy lại vẫn đi qua đúng một vòng
> `_finalize`, và `_finalize` lại xoá audio theo chính sách — nên với ngưỡng
> `0` thì mỗi bản ghi chỉ chạy lại được **một lần**, và chỉ khi bấm trước lượt
> cron xoá.
>
> Mẩu đã mất audio được **giữ nguyên**, không đụng tới: đoạn cũ của nó vẫn vào
> bản bóc băng mới. Xoá đi cho "sạch" là đổi một bản bóc băng thiếu chính xác
> lấy một bản bóc băng **thiếu hẳn** — mất mát không hoàn lại được.
>
> **Chưa có lượt chạy nào của nút này trên một bản ghi THẬT** (§8.3).

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
>
> Ngược lại, **THAM SỐ MỚI thì vẫn được TẠO** khi nâng cấp: `noupdate` chỉ bỏ
> qua bản ghi mà `ir_model_data` ĐÃ có, còn xml_id mới thì không có gì để bỏ
> qua. Đã kiểm chứng chứ không suy đoán — sau `-u aidt_meeting_minutes` trên
> `aidt_demo` (CSDL cài từ trước), `aidt_meeting.asr_response_format` xuất
> hiện với giá trị `json` và `ir_model_data.name = param_asr_response_format`.
> Vì vậy `19.0.1.0.3` **không cần** script migration; phiên bản vẫn được bump
> để môi trường tự nâng cấp theo số phiên bản cũng nạp lại file dữ liệu.
>
> **`19.0.1.1.0` là đúng ví dụ của CẢ HAI vế cùng một lúc**, và nhầm chỗ này
> là nhầm âm thầm:
>
> * `param_asr_language`, `param_asr_prompt`, `param_asr_temperature` —
>   xml_id **mới** ⇒ tự được tạo khi nâng cấp, **không cần** migration.
> * `param_asr_model` (`vinai/PhoWhisper-large` → `openai/whisper-large-v3`) —
>   xml_id **đã tồn tại** trên mọi CSDL cài từ trước ⇒ sửa giá trị trong XML
>   **không bao giờ** tới được `aidt_demo`. Không có script thì mọi lần bóc
>   băng vẫn chạy bằng model cũ trong khi cả file dữ liệu lẫn tài liệu đều nói
>   đã đổi. Vì vậy có `migrations/19.0.1.1.0/post-migration.py`, và nó **chỉ**
>   đổi khi giá trị hiện tại **đúng bằng** mặc định cũ — admin đã tự trỏ sang
>   dịch vụ khác là một quyết định có ý thức, ghi đè nó là làm hỏng cấu hình
>   của người ta. Không đổi gì thì script vẫn ghi log nói rõ giá trị hiện tại
>   là gì, để người vận hành không phải đoán.
>
> Bump lên nhánh `.1.x` (không phải `.0.4`) vì đây là **đổi hành vi mặc định
> kèm migration**, không phải vá thêm một tham số.

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

| | Bật ghi âm | Dừng ghi âm | Từ chối / gửi audio |
|---|---|---|---|
| Cuộc họp **có lịch** | Chỉ `event.user_id` (người chủ trì) | **Bất kỳ** người trong CUỘC GỌI | Bất kỳ người trong CUỘC GỌI |
| Cuộc gọi **tự phát** | Bất kỳ thành viên kênh | **Bất kỳ** người trong CUỘC GỌI | Bất kỳ người trong CUỘC GỌI |

"Người trong cuộc gọi", **không phải** "thành viên kênh" (`_is_participant`).
Thành viên kênh chỉ là điều kiện *cần*. Kênh phòng ban 200 người thì 197
người trong đó chưa bao giờ vào cuộc gọi 3 người đang được ghi; nếu chỉ xét
thành viên kênh thì bất kỳ ai trong 197 người đó cũng **cắt được** bản ghi và
**đọc được** audio thô của cuộc gọi họ không dự.

Tập người tham gia được ghi vào `participant_partner_ids` từ
`discuss.channel.rtc.session` tại hai thời điểm: lúc phát `started`, và mỗi
lần một máy gọi `action_active_recording` (tức lúc nó khai "tôi đang trong
cuộc gọi này"). Xét theo tập **đã từng có mặt** chứ **không** đòi phiên RTC
còn sống lúc gửi: mẩu cuối của mỗi người tới nơi *sau* khi họ đã gập máy, và
đòi phiên sống sẽ vứt đúng 15 giây lời kết mà `_store` cố ý giữ lại.

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

### 5.6. Bus phát tới CẢ KÊNH, nên client phải tự lọc theo kênh

`_broadcast_state` gửi trên **kênh**, và theo
`addons/mail/models/discuss/ir_websocket.py` (`("is_member", "=", True)`) mọi
trình duyệt đăng ký bus của **mọi kênh mình là thành viên**, bất kể có đang
trong cuộc gọi ở đó hay không. Vì vậy payload mang theo `channel_id`, và
nhánh **`started`** của `recorder_service._onRecordingState` **bắt buộc** đối
chiếu nó với `rtc.state.channel.id` trước khi bật micro. Băng thông báo cũng
đối chiếu (`isForThisChannel`).

Nhánh **`stopped`** thì **không** — và đúng ra là không được — đối chiếu kênh:
nó khớp theo `recording_id`, vốn là id duy nhất toàn hệ thống. Hai phép so
trong nhánh đó (`declinedRecordingId` và `recordingId`) đã tự khoá vào đúng
bản ghi mình đang thu / đã từ chối, nên một `stopped` của kênh khác không thể
chạm tới. Thêm điều kiện kênh vào đây chỉ tạo ra một cách BỎ SÓT lệnh dừng
(ví dụ payload cũ không kèm `channel_id`, hoặc `rtc.state.channel` đã bị xoá
trước khi tin dừng tới) — tức là tiếp tục thu sau khi cuộc họp đã dừng, đúng
hướng sai nguy hiểm hơn.

Không đối chiếu ở nhánh `started` thì: U là thành viên kênh phòng ban A và
đang họp riêng ở kênh B; ai đó bật ghi âm ở A; tab của U bật thu, `_attachToMic`
tóm đúng `rtc.state.micAudioTrack` — **micro đang sống trong cuộc gọi B** — và
đẩy lên bản ghi của A. Server nhận, vì U đúng là thành viên A. Nửa cuộc gọi
riêng của U được bóc băng, gán tên U, đăng vào chatter của A. Không cần ai
phá hoại, không cần tab cũ.

### 5.7. Trạng thái ghi âm phải HỎI LẠI được, không chỉ nghe broadcast

`started` phát đúng **một lần**. Người nạp lại tab giữa cuộc họp, hoặc vào họp
sau thời điểm bật, không bao giờ nhận được nó. Vì vậy có
`action_active_recording(channel_id)` — public, vẫn qua kiểm tra thành viên
kênh, trả `{recording_id, channel_id, elapsed_ms}` — và client gọi nó **lúc
service khởi động** lẫn **mỗi lần vào cuộc gọi** (patch `joinCall`).

Không có nửa client này thì với người vừa F5: băng đồng thuận **không hiện**
(cơ chế thực thi việc xin phép ghi âm biến mất đúng với người đang bị ghi),
tiếng của họ không được thu nên biên bản làm họ trông như ngồi im chứ không
phải đã từ chối, và nút "Bật ghi âm" lại hiện ra để rồi báo "Cuộc gọi này đang
được ghi âm rồi."

### 5.8. Audio

`audio_retention_days = 0` (mặc định) ⇒ tệp audio bị xoá **ngay sau khi hoàn
tất**, bản bóc băng được giữ. `_purge_own_audio()` giới hạn domain theo
`self` — nếu không, hoàn tất bản ghi A sẽ xoá audio của mọi bản ghi B, C đã
`done` từ trước.

Đây cũng chính là thứ làm nút **Bóc băng lại** (§4.4) gần như vô dụng với
cấu hình xuất xưởng, và là lý do **chưa đo được** độ chính xác của model mới
(§8.3). Nâng ngưỡng lên là một quyết định **về quyền riêng tư**, phải do
người vận hành chủ động ra, **trước** cuộc họp — không phải thứ code tự nới.

Domain dọn phủ mẩu `done` **và `failed`**: `failed` là mẩu đã hết lượt thử,
không ai còn xử lý nữa, nên audio thô của nó cũng hết lý do tồn tại. Chỉ lọc
`done` nghĩa là đúng những mẩu **hỏng** giữ audio cuộc họp vĩnh viễn, kể cả
khi chính sách là "xoá ngay". Mẩu `pending`/`transcribing` thì giữ — chúng
còn cần audio để thử lại.

---

## 6. Ngân sách GPU

Số đo thật trên **RTX 5060 Ti, 16311 MiB**, ngày 05/08/2026, cả ba service
`healthy` cùng lúc, dựng bằng chính `docker-compose.ai.yml`:

| Service | Chạy trên | Ghim | VRAM |
|---|---|---|---|
| `aidt-embed` (`AITeamVN/Vietnamese_Embedding`) | vLLM 0.26.0 | `--gpu-memory-utilization=0.15` | 1602 MiB |
| `aidt-asr` (`openai/whisper-large-v3`) | vLLM 0.26.0 | `--gpu-memory-utilization=0.25` | 4416 MiB* |
| `aidt-llm` (`gemma3:12b-it-qat`) | Ollama 0.32.5 | *(không có cờ tương đương)* | 8534 MiB |
| màn hình | | | 82 MiB |
| **Tổng** | | | **14843 / 16311 MiB** |

> \* **Con số 4416 MiB đo khi `aidt-asr` còn chạy `vinai/PhoWhisper-large`, và
> CHƯA đo lại sau khi đổi sang `openai/whisper-large-v3`.** Lý do để vẫn dùng
> bảng này: PhoWhisper-large **chính là** bản tinh chỉnh của Whisper large-v2,
> tức cùng kiến trúc, cùng cỡ trọng số (~3.1 GB) và cùng cửa sổ 448 token —
> nên `--gpu-memory-utilization=0.25` giữ nguyên và vLLM cấp phát theo **tỉ
> lệ** chứ không theo cỡ model. Dù vậy đây là **suy luận, không phải phép
> đo**: nếu bạn vừa dựng lại stack, hãy chạy lại `nvidia-smi` và sửa bảng
> này.

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

Kết quả 05/08/2026 (sau đợt chất lượng bóc băng), chép nguyên văn hai dòng
tổng kết của lượt chạy `--test-tags '/aidt_meeting_minutes'` (gồm cả bộ JS):

```
odoo.tests.stats:  aidt_meeting_minutes: 265 tests 17.46s 12628 queries
odoo.tests.result: 0 failed, 0 error(s) of 205 tests
```

Hai con số khác nhau vì Odoo đếm hai đơn vị khác nhau (`stats` đếm cả
subTest, `result` đếm phương thức test) — chép cả hai để không ai phải đoán
đơn vị nào. Bỏ bộ JS ra (`-aidt_meeting_js`) thì còn `262 tests` / `204`.
Trước đợt này là `116 tests` / `166 test method`. **Mọi lời gọi ASR/LLM trong bộ này đều là mock** — nhưng phần
`audio_prep` thì **không**: `tests/test_audio_prep.py` và
`tests/test_chunk_pipeline.py` chạy PyAV thật trên MP3 tổng hợp thật
(`tests/audio_fixtures.py`), chỉ giả lập đúng lời gọi HTTP tới ASR. Hai mảnh
`audio_prep` + `text_filter` được kiểm riêng lẻ **và** kiểm rằng chúng đã
được nối vào `_process_one` — hai mảnh đúng mà không ai gọi thì vẫn là một
tính năng không tồn tại.

Tệp WAV do `_encode_wav()` sinh ra được đọc ngược lại bằng **`soundfile`**,
tức một bộ giải mã **độc lập với PyAV**: tự đọc lại bằng chính thư viện vừa
ghi ra thì không chứng minh được header RIFF đúng. `soundfile==0.14.0` nằm ở
stage `dev` của `Dockerfile` (production không chạy test); `av==18.0.0` và
`numpy==2.5.1` thì nằm ở **cả hai** stage vì `models/audio_prep.py` cần chúng
lúc chạy thật.

> ⚠️ **`av` và `numpy` trước đây KHÔNG có trong ảnh.** Ngày 05/08/2026 phát
> hiện cả ba gói chỉ tồn tại ở **lớp ghi của container đang chạy** (ai đó cài
> tay): `docker run --rm --entrypoint python3 aidt-odoo-dev-odoo:latest -c
> "import av"` ⇒ `ModuleNotFoundError`. Tức một lần rebuild bất kỳ sẽ làm
> module không cài được nữa, và không có gì trong repo báo trước. Nay chúng
> nằm trong `Dockerfile`, **và** trong `external_dependencies` của manifest —
> không thừa: `Dockerfile` chỉ mô tả ảnh của dự án này, còn manifest theo
> module đi bất cứ đâu nó được cài, và nó là thứ làm Odoo **chặn** việc cài
> module kèm thông báo nói rõ thiếu gói gì, thay vì để `models/__init__` ném
> `ModuleNotFoundError` giữa lúc nạp registry.

> `tests/test_js.py` kế thừa `odoo.tests.HttpCase`, **không** kế thừa
> `HOOTCommon` của `addons/web`: `HOOTCommon` mang theo ba phương thức test
> THẬT của chính nó (`test_generate_hoot_hash`, `test_get_hoot_filter`,
> `test_canonical_tags`), nên kế thừa nó khiến ba bài test của lõi `web` chạy
> lại dưới tên module này — một thay đổi trong thuật toán hash của lõi sẽ
> được báo cáo như module NÀY hỏng. Thứ duy nhất cần từ đó là `_generate_hash`
> (5 dòng), đã chép lại.

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

Kết quả 05/08/2026: **41 passed, 0 failed** (88 assertion,
`[HOOT] Test suite succeeded`).

Hoặc mở thẳng trong trình duyệt:
`http://localhost:8069/web/tests?id=c2929794` (`c2929794` là hash tất định
của tên suite gốc `@aidt_meeting_minutes`).

---

## 8. Những gì ĐÃ và CHƯA được kiểm chứng

### 8.1. Đã chạy thật (05/08/2026)

#### 8.1.a. Cuộc gọi THẬT, giọng người THẬT — bản ghi 1047

Cuộc gọi trực tiếp giữa hai tài khoản (`admin` và `bithu`) trên kênh
`discuss.channel` 1020, **không có `calendar.event`**, ghi qua **micro và
trình duyệt thật** của cả hai máy. Đây là lần đầu tiên giọng người thật đi
vào hệ thống.

| Bước | Kết quả |
|---|---|
| Recorder của **cả hai máy** thu và gửi mẩu | ✅ 4 mẩu MP3, offset 42 / 42 / 13542 / 27047 ms, độ dài 15004 / 15004 / 15008 / 3058 ms, ~60 KB cho mỗi mẩu 15 s |
| Audio có tiếng người thật | ✅ giải mã độc lập mẩu 787: 15.084 s, 16 kHz mono, đỉnh 0.447, RMS toàn mẩu 0.0172, hai phần mười có RMS 0.0367 / 0.0400 trên nền im lặng 0.0005 |
| `_cron_process()` gọi `aidt-asr` **thật** | ✅ 4/4 mẩu `done`, không lỗi — **nhưng 0 đoạn** |
| Bản bóc băng | ❌ rỗng; chatter nhận "(không có nội dung)" lúc 06:31:32 |

**Nguyên nhân, đã chứng minh chứ không còn phỏng đoán:** `response_format`
ghi cứng `verbose_json`. Thử A/B trên **chính gateway đang chạy**, **cùng
một tệp**, chỉ đổi trường đó:

```
verbose_json -> {"duration": "15.084", "language": "vi", "text": "", "segments": []}
json         -> {"text": "nhà trưởng nguyễn ngọc thịnh nhận tiền cho nhà thiết kế…"}
```

Cùng checkpoint đó chạy qua `transformers` thuần (`WhisperForConditional
Generation`, fp16, CUDA) trả 44 token tiếng Việt, nên **checkpoint không
hỏng**. Log vLLM trong các lượt hỏng: `Auto-detected language: 'vi'`,
HTTP 200, `Avg generation throughput: 1.2 tokens/s` — model sinh vài token
đặc biệt rồi EOS. `vinai/PhoWhisper-large` là bản tinh chỉnh **không có
token mốc thời gian**; hỏi nó mốc thời gian là hỏi thứ nó không có.

#### 8.1.b. Sau khi sửa: cùng audio thật đó, chạy lại qua đường ống thật

Đặt `asr_response_format = json`, đưa bản ghi 1047 về `processing`, mẩu về
`pending`, rồi để `_cron_process()` và `_cron_sweep()` chạy:

| Bước | Kết quả |
|---|---|
| Mẩu 787 (audio thật) → `aidt-asr` thật | ✅ `done` ngay lần thử đầu, **1 đoạn** `start_ms=42`, `end_ms=15046` |
| Mốc thời gian | ✅ đúng `offset_ms` + `duration_ms` do recorder đo (42 + 15004) |
| `_cron_sweep()` → `_finalize()` | ✅ `state=done`, `finalized_segment_count=1` |
| Đăng chatter "**Bản bóc băng cuộc họp**" | ✅ vào chatter **`discuss.channel` 1020** (cuộc gọi tự phát ⇒ không có `calendar.event`) — `mail.message` 3328 |
| `_run_summary()` với `aidt-llm` **đang tắt** | ✅ đúng thiết kế: `summary_error = "gọi tóm tắt thất bại: <urlopen error [Errno -3] Temporary failure in name resolution>"`, **bản bóc băng vẫn đăng** |
| Xoá audio (`audio_retention_days=0`) | ✅ 0 chunk còn giữ `attachment_id` |

Bản bóc băng đăng lên, nguyên văn:

```
[00:00] Administrator: nhà trưởng nguyễn ngọc thịnh nhận tiền cho nhà thiết kế nhưng không cho tiền cho nhà thiết kế.
[thiếu âm thanh 00:00–00:15: Nguyễn Văn An]
[thiếu âm thanh 00:13–00:28: Administrator]
[thiếu âm thanh 00:27–00:30: Administrator]
```

> ⚠️ **Vì sao chỉ một trong bốn mẩu được bóc băng lại.** `audio_retention_days
> = 0` đã xoá audio ngay khi hoàn tất lượt chạy đầu, và lượt `filestore gc`
> (chạy khi khởi tạo registry, tức là **mỗi lần chạy test**) đã xoá nốt tệp
> khỏi filestore. Chỉ mẩu 787 còn một bản sao ngoài luồng. Ba mẩu kia vào
> `_cron_process` với thân rỗng, dịch vụ trả **HTTP 400**, và chúng đi đúng
> đường thử lại thật cho tới `failed` — ba dòng `[thiếu âm thanh …]` ở trên
> là đầu ra THẬT của cơ chế đó, không phải do đặt tay. **Bài học vận hành:
> audio đã bị xoá theo chính sách lưu trữ là KHÔNG khôi phục được**; muốn
> chẩn đoán lại thì phải sao chép audio ra ngoài TRƯỚC.

#### 8.1.c. Lượt chạy bằng giọng tổng hợp gTTS (trước đó — cách diễn giải cũ đã bị bác bỏ)

Lượt chạy qua `odoo-bin shell` trên `aidt_demo`, dùng **audio tiếng Việt
TỔNG HỢP bằng gTTS** (4 lượt nói luân phiên của 2 người, 8.2 / 5.2 / 6.0 /
5.5 giây; RMS 0.10, đỉnh 0.54 — tệp không im lặng, đã kiểm bằng bộ giải mã
độc lập). Lượt này **vẫn có giá trị** cho những gì nó chứng minh: các mắt
xích Python và hai dịch vụ AI khớp khuôn dạng của nhau, và đường tóm tắt
chạy được thật với `aidt-llm`.

> ⚠️ **Phần kết luận về ASR rút ra từ lượt này đã SAI và nay bị thay thế.**
> Bản bóc băng rỗng khi đó được quy cho "giọng tổng hợp ngoài phân bố dữ
> liệu" như một khả năng chưa loại trừ. Không phải: nguyên nhân là
> `verbose_json`, và giọng người thật (§8.1.a) cũng cho ra rỗng y hệt cho
> tới khi đổi tham số. Giả thuyết gTTS chưa bao giờ được kiểm chứng — nó chỉ
> chưa bị loại trừ, và nay thì đã.

| Bước | Kết quả |
|---|---|
| Chủ trì bật ghi âm qua `action_start_for_channel` | ✅ `state=recording`, `secrecy_at_start=thuong` |
| 4 mẩu MP3 upload qua `_store()`, mỗi mẩu dưới danh tính người nói | ✅ 4 chunk, offset 0 / 8208 / 13392 / 19416 |
| Người **không chủ trì** bấm dừng | ✅ `state=processing` |
| `_cron_process()` gọi `aidt-asr` **thật** | ✅ 4/4 chunk `done`, không lỗi — nhưng nội dung chỉ là `"."` (cùng nguyên nhân `verbose_json`) |
| Quy đổi offset → `aidt.meeting.segment` | ✅ mốc tuyệt đối được ghi |
| `_cron_sweep()` → `_finalize()` | ✅ `state=done` |
| Đăng chatter "**Bản bóc băng cuộc họp**" | ✅ vào chatter của `calendar.event` (nội dung: `[00:00] Administrator: . .`) |
| `_summarize()` gọi `aidt-llm` **thật** | ✅ HTTP 200, tiếng Việt, đúng ba mục NỘI DUNG CHÍNH / KẾT LUẬN / VIỆC CẦN LÀM, **và tự nêu rõ nội dung có thể không đầy đủ khi transcript có dòng `[thiếu âm thanh …]`** |
| Đăng chatter "**Tóm tắt cuộc họp**" | ✅ |
| Xoá audio (`audio_retention_days=0`) | ✅ 0 chunk còn giữ `attachment_id` |

**Kết luận: đường ống thông suốt.** Mọi mắt xích Python + hai dịch vụ AI đều
hoạt động và khớp khuôn dạng của nhau.

#### 8.1.d. Đổi model + hai lưới lọc: đo trên dịch vụ ĐANG CHẠY (05/08/2026)

Tất cả các số dưới đây đến từ việc gửi audio **thẳng vào** `aidt-asr` thật
(`http://aidt-asr:8002`) với model **`openai/whisper-large-v3`** — không phải
mock, không phải suy đoán từ tài liệu.

**Phần 1 — model bịa chữ trên đúng loại audio mà hệ thống vẫn gửi lên.** Bốn
tệp WAV tổng hợp 15 giây, 16 kHz mono. Đầu ra nguyên văn:

| Đầu vào | RMS | Model trả về |
|---|---|---|
| im lặng số (toàn 0) | 0.00000 | *"Hãy subscribe cho kênh La La School Để không bỏ lỡ những video hấp dẫn"* |
| nhiễu Gauss | 0.00100 | *"Cảm ơn các bạn đã theo dõi và hẹn gặp lại."* |
| nhiễu Gauss "nền phòng" | **0.00599** | *"Cảm ơn các bạn đã theo dõi và hẹn gặp lại."* |
| tông 440 Hz | 0.19797 | *"Hãy subscribe cho kênh La La School Để không bỏ lỡ những video hấp dẫn"* |

Ba điều phải đọc kỹ ở bảng này:

1. **Hàng 0.00599 là hàng quyết định.** Nó **vượt** `RMS_FLOOR = 0.005` của
   `recorder_service.js`, nghĩa là **trước đợt sửa này, đúng loại audio đó đi
   lọt lên tới ASR và một câu bịa được ghi vào biên bản**. Cổng §2.7 sinh ra
   để chặn đúng nó, và nó chặn được: khung to nhất của tệp đó chỉ 0.00693 ⇒
   **0/750 khung** vượt `VOICED_RMS = 0.01`.
2. **Hàng 440 Hz là hàng nói thẳng giới hạn.** RMS 0.198 — to hơn khối tiếng
   nói thật — **đi qua cổng** (750/750 khung "có tiếng") và **vẫn ảo giác**.
   Cổng lọc bắt audio *gần rỗng*, **không** bắt audio *to nhưng suy biến*.
   Đừng mô tả nó như một "bộ lọc ảo giác".
3. **Lọc theo độ tự tin của model KHÔNG cứu được lớp lỗi này.** Bốn ca trên
   cho `avg_logprob` **−0.108 / −0.135** và `compression_ratio` **0.88–0.94**
   — toàn số **trông bình thường**. Model tự tin y hệt lúc nó bóc băng đúng.

**Phần 2 — ngưỡng blocklist 0.4 hiệu chỉnh trên đầu ra THẬT của model** (bốn
ca, xem §2.8): ảo giác thật phủ 0.80 và 0.62; câu nói thật trùng khuôn mẫu
phủ 0.16 và 0.00. Ngưỡng nào trong khoảng (0.16, 0.62) cũng phân tách đúng
bốn ca đó — **tập mẫu bốn ca là nhỏ**, đây là hiệu chỉnh sơ bộ.

**Phần 3 — chạy hết đường ống thật vào model thật.** Hai lượt:

| Đầu vào | Kết quả |
|---|---|
| Im lặng, qua đúng `_process_one` | ✅ **bị chặn TRƯỚC khi gọi ASR**, `skip_note` ghi `0/750 khung 20 ms vượt RMS 0.01`, mẩu `done` với 0 đoạn |
| Tệp tiếng nói thật | ✅ trả về chữ tiếng Việt **có dấu câu và có viết hoa** |

Vế thứ hai đáng ghi lại riêng: **PhoWhisper chưa bao giờ làm được điều đó**.
Nó xuất chữ thường, không dấu câu — nên mọi bản bóc băng cũ đều là một khối
chữ thường liền mạch. Đây cũng là lý do module **từ chối** port hàm
`normalize_vietnamese_text` của dự án tham chiếu (§2.8): nó sinh ra để vá
đúng khuyết điểm đó, và với model hiện tại nó chỉ còn là thứ làm hỏng tên
riêng.

**Phần 4 — `verbose_json` nay chạy được.** Trên `openai/whisper-large-v3`,
`response_format=verbose_json` trả về `segments[]` với mốc thời gian thật
theo từng lượt nói, kèm `avg_logprob` và `compression_ratio`. Lý do cũ để
tránh nó (§4.2) **không còn áp dụng cho model mặc định hiện tại**. Mặc định
vẫn là `json`; việc chuyển **chưa được áp dụng** (§8.3).

### 8.2. ⚠️ Đã ra chữ, nhưng chữ đó có thể là chữ BỊA

Câu tiếng Việt ở §8.1.b **không phải điều hai người trong cuộc gọi đã nói**.
Họ đếm "một… hai… ba… bốn". Đo trên chính mẩu đó (giải mã độc lập, chia 10
phần bằng nhau):

| Phần | 0 | 1 | 2 | 3 | **4** | **5** | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| RMS | .0011 | .0005 | .0012 | .0012 | **.0367** | **.0400** | .0036 | .0001 | .0003 | .0004 |

Tức **khoảng 2 trên 15 giây có tiếng nói**, phần còn lại là nền im lặng.
Whisper (mọi phiên bản, không riêng PhoWhisper) **bịa ra văn bản trôi chảy
từ khoảng gần im lặng** — đây là hành vi đã biết của kiến trúc, không phải
lỗi mới của module. Bằng chứng nội tại: câu trả về là một câu hoàn chỉnh,
đúng ngữ pháp, về một chủ đề **không liên quan gì** tới nội dung đã nói.

**Hệ quả cho người dùng:** một cuộc họp có nhiều khoảng lặng dài sẽ sinh ra
những câu trông rất thuyết phục mà **không ai từng nói**. Trong một biên bản
hành chính, đây là hướng sai nguy hiểm hơn hẳn việc thiếu chữ. Vẫn phải nói
rõ điều này với người dùng (`docs/GUIDANCE.md` §2.1) — **có hai lưới lọc
không có nghĩa là đã hết**.

> ### ✅ Đã có cơ chế chặn — nhưng chỉ chặn được MỘT nửa lớp lỗi
>
> Kể từ đợt 05/08/2026 có **hai** lưới, và cả hai đều đã đo được ranh giới
> của mình (§8.1.d):
>
> * **Cổng lọc tiếng nói ở server** (§2.7) — bỏ hẳn lời gọi ASR cho mẩu gần
>   rỗng. Đây là cách chặt nhất để diệt lớp lỗi này: **không có đầu ra thì
>   không có gì phải lọc**. Đã đo là chặn được cả tệp "nền phòng" RMS 0.00599
>   vốn đi lọt cổng trình duyệt.
> * **Blocklist ảo giác** (§2.8) — lưới thứ hai cho những gì lọt qua. Hai câu
>   bịa đo được đều nằm sẵn trong blocklist.
>
> **Nửa KHÔNG chặn được, và phải nói thẳng:** audio *to nhưng suy biến* (tông
> đơn, tiếng quạt, tiếng máy) vẫn qua cổng và vẫn ảo giác — đã đo với tông
> 440 Hz ở RMS 0.19797. Nếu câu ảo giác sinh ra **không** nằm trong 21 mẫu
> blocklist thì nó **vào thẳng biên bản**. Blocklist chỉ biết những khuôn mẫu
> đã từng bắt gặp.
>
> **`RMS_FLOOR = 0.005` của trình duyệt vẫn giữ nguyên** — nay đã biết chắc
> là **quá dễ dãi** (§2.5), nhưng cổng server chặn đúng ca đó với bằng chứng
> đo được, nên không có lý do gì đổi một hằng số ở tầng mà ta không đo được
> (micro thật, phòng thật). Mẩu 787 của bản ghi 1047 minh hoạ đúng vì sao một
> ngưỡng theo **độ to trung bình** không đủ: RMS toàn mẩu 0.0172 — gấp hơn ba
> lần ngưỡng — trong khi 8/10 phần mười của nó nằm ở mức nền 0.0005. Cổng
> server không đo trung bình mà **đếm khung**, nên nó phân biệt được "15 giây
> nói đều" với "2 giây nói cộng 13 giây im lặng".

Phần lỗi 500 `tuple index out of range` từng được ghi như một hiện tượng
riêng nay đã rõ là **cùng một gốc rễ** (hỏi mốc thời gian ở model không có
token mốc thời gian). Phần xử lý phòng thủ trong `asr_client.py` được **giữ
nguyên**: nó vẫn đúng cho bất kỳ ai đặt `verbose_json`.

Tương tự, các mốc thời gian vô lý (`end: 40.08` cho mẩu 8.208 s, `end` tới
`415.6` / `264.46`) và hàng `start_ms=16860, end_ms=4980` từng thấy trong
CSDL đều là đầu ra của cùng lỗi đó. Phần kẹp ở `_write_segments()` và ràng
buộc `CHECK (end_ms >= start_ms)` (§2.3) **giữ nguyên** — mốc từ dịch vụ
ngoài không tin được, bất kể dịch vụ nào.

### 8.3. Chưa bao giờ chạy

* **Chưa có lượt chạy hai trình duyệt nào ĐI HẾT sau bản sửa.** Phần thu ở
  §8.1.a **là** micro và trình duyệt thật của hai máy — đó là lần đầu tiên
  `getUserMedia`, `AudioWorklet`, `Mp3Encoder`, WebRTC và bus
  `recording_state` chạy thật với người thật. Nhưng phần bóc băng sau khi
  sửa được lái từ `odoo-bin shell` trên đúng audio đó, **không phải** từ một
  cuộc gọi mới bấm bằng tay từ đầu đến cuối. Băng đồng thuận, nút "Từ chối",
  nút "Dừng ghi âm" trong một cuộc gọi thật vẫn chỉ được kiểm bằng test hoot
  với micro giả.
* **Độ chính xác tiếng Việt của `openai/whisper-large-v3` trên một cuộc họp
  thật CHƯA BAO GIỜ được đo.** Đây là điều quan trọng nhất trong cả mục này.
  Việc đổi model được biện minh bằng **những gì PhoWhisper làm sai** (bản ghi
  1140: `lô cồ`, `con ngôi đồ`, `hỗn hợp`, không dấu câu, không viết hoa) chứ
  **không** bằng một phép so đo được giữa hai model. Và **không thể** so:
  `audio_retention_days = 0` đã xoá sạch audio của 1140 trước khi ai kịp nghĩ
  tới việc A/B. Điều đã đo được chỉ là large-v3 trả về chữ **có dấu câu và
  viết hoa** (§8.1.d) — một cải thiện **về hình thức**, không phải bằng chứng
  về **độ chính xác từ**.
  → Muốn đo: đặt `audio_retention_days > 0` **trước** một cuộc họp thật, giữ
  audio, rồi dùng **Bóc băng lại** (§4.4) để chạy cùng audio qua từng cấu
  hình. Không có bước "đặt trước" thì không có gì để đo.
* **Chưa hiệu chỉnh:** `MAX_OVERLAP_WORDS = 12`, `MAX_OVERLAP_BACKSEARCH = 6`,
  `WINDOW_LINES = 120`, `MIN_VOICED_FRAMES = 5` (§2.7 — thuần lập luận trên
  độ dài âm tiết, không có phép đo nào chống lưng), `RMS_FLOOR = 0.005`
  (§2.5 — đã biết là quá dễ dãi, giữ nguyên có chủ ý).
* **`HALLUCINATION_COVERAGE = 0.4` hiệu chỉnh trên đúng BỐN ca** (§8.1.d).
  Tập mẫu nhỏ. Ngưỡng nào trong (0.16, 0.62) cũng phân tách đúng bốn ca đó,
  nên con số này chưa được dữ liệu ép vào chỗ nào cả.
* **Nút "Bóc băng lại" chưa chạy trên một bản ghi THẬT lần nào.** Nó có test
  (đưa mẩu về `pending`, đưa bản ghi về `processing`, và `UserError` khi audio
  đã bị xoá), nhưng chưa có lượt nào chạy lại audio thật qua dịch vụ thật —
  đúng vì lý do ở gạch đầu dòng trên: với mặc định `audio_retention_days = 0`
  chưa từng có audio nào sống sót tới lúc bấm nút.
* **`verbose_json` chạy được nhưng CHƯA được áp dụng** (§4.2, §8.1.d). Đổi nó
  là đổi nguồn sự thật của mọi mốc thời gian trong biên bản, từ đồng hồ trình
  duyệt sang mốc do model trả về — mà mốc từ dịch vụ ngoài **không tin được**
  (§2.3). Chưa ai đo cái giá đó trên audio họp thật.
* **Biên mẩu vẫn cắt cứng 15 giây**, không nắn về khoảng lặng. Việc nắn điểm
  cắt nằm ở recorder phía trình duyệt, mà phạm vi đợt này đã chốt là
  server-side — và nên đo tác động của việc đổi model trước khi thêm biến thứ
  hai. Phần chồng lấn 1.5 s cộng khử trùng có dò lùi (§2.4) là thứ che mối
  nối hiện nay.
* **Chưa bấm giờ** một cuộc họp dài thật. Cũng chưa đo thêm bao nhiêu thời
  gian mà `audio_prep` cộng vào mỗi mẩu trên phần cứng thật (ước tính từ giai
  đoạn thiết kế: giải mã + lấy mẫu lại một mẩu 10 giây mất ~37 ms, chưa tính
  phần điều kiện hoá).
* **Khử trùng mối nối chưa gặp mối nối thật.** Với `json`, mỗi mẩu là một
  đoạn phủ trọn mẩu và phần chồng lấn 1.5 s thật sự lặp chữ ở mối nối —
  `_strip_overlap` xử lý ca này trong test, nhưng chưa lần nào trên đầu ra
  ASR thật của hai mẩu liên tiếp (bản ghi 1047 chỉ còn một mẩu có audio).
* `sendBeacon` khi đóng tab: chưa làm.
