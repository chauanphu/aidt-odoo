# Flow ghi âm cuộc họp & tóm tắt AI — Odoo Meeting

**Phiên bản:** v2 — đơn giản hóa từ real-time streaming sang **batch processing**.

**Thay đổi lớn so với v1:** Bỏ hoàn toàn subtitle real-time, WebSocket streaming, và broadcast qua `bus.bus` theo từng câu. Thay bằng: ghi âm toàn bộ cuộc họp → khi kết thúc mới xử lý một lần → tóm tắt thành các trường có cấu trúc.

**Vì sao đổi:** Bỏ áp lực latency cho phép dùng cấu hình Whisper chính xác nhất, giải quyết được phần lớn vấn đề ảo giác chỉ bằng việc đổi kiến trúc. Đồng thời giảm mạnh độ phức tạp hệ thống (không cần quản lý WebSocket session, không cần đồng bộ đa người dùng theo thời gian thực).

**Đối tượng đọc:** Team frontend (ghi âm), team backend AI service, team Odoo module.

---

## 1. Luồng nghiệp vụ

```
Sếp tạo cuộc họp          → trạng thái: Nháp
Sếp bấm "Ghi âm"          → trạng thái: Đang ghi     (audio upload theo chunk)
Sếp bấm "Kết thúc"        → trạng thái: Đang xử lý   (đẩy job vào queue)
    ├─ Ghép + chuẩn hóa audio
    ├─ Speech to text (PhoWhisper, batch)
    ├─ LLM tóm tắt → JSON có cấu trúc
    └─ Ghi vào các trường Odoo
                          → trạng thái: Xong
Lỗi ở bất kỳ bước nào     → trạng thái: Lỗi          (giữ audio để chạy lại)
```

---

## 2. Bước 1 — Ghi âm tại client

### 2.1. Yêu cầu bắt buộc

**Upload theo chunk, không giữ toàn bộ trong RAM.** Một cuộc họp 1 tiếng có thể tạo file hàng trăm MB. Nếu chỉ upload khi bấm "Kết thúc", chỉ cần trình duyệt crash / mất mạng / máy hết pin là mất trắng dữ liệu.

### 2.2. Code mẫu

```javascript
class MeetingRecorder {
  constructor(meetingId) {
    this.meetingId = meetingId;
    this.chunkIndex = 0;
  }

  async start() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,   // khử nhiễu nền sẵn có của trình duyệt
        autoGainControl: true,    // chuẩn hóa volume, tránh người nói nhỏ bị mất tiếng
        channelCount: 1,          // mono là đủ cho STT, giảm 50% dung lượng
      }
    });

    this.recorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus',
      audioBitsPerSecond: 32000,  // opus 32kbps đủ chất lượng cho giọng nói
    });

    // Mỗi 30s bắn ra 1 chunk -> upload ngay, không tích trong RAM
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.uploadChunk(e.data);
    };

    this.recorder.start(30000);
  }

  async uploadChunk(blob) {
    const form = new FormData();
    form.append('meeting_id', this.meetingId);
    form.append('chunk_index', this.chunkIndex++);
    form.append('audio', blob);

    // Nên có retry: nếu upload fail thì đẩy vào hàng đợi local
    // và thử lại, tránh mất đoạn giữa cuộc họp
    await fetch('/aidt_meeting/api/upload_chunk', { method: 'POST', body: form });
  }

  async stop() {
    this.recorder.stop();
    this.recorder.stream.getTracks().forEach(t => t.stop());
    // Báo server biết đã hết chunk -> bắt đầu xử lý
    await fetch('/aidt_meeting/api/finalize_recording', {
      method: 'POST',
      body: JSON.stringify({ meeting_id: this.meetingId, total_chunks: this.chunkIndex }),
    });
  }
}
```

### 2.3. Việc cần xử lý thêm

- **Retry khi upload chunk thất bại** — giữ chunk trong IndexedDB và thử lại, không được bỏ qua im lặng.
- **Cảnh báo khi user đóng tab lúc đang ghi** — dùng `beforeunload`.
- **Hiển thị thời lượng đang ghi** để người dùng biết hệ thống vẫn đang hoạt động.

---

## 3. Bước 2 — Hàng đợi xử lý nền

**Nguyên tắc:** Odoo web request **không được** chờ quá trình STT + LLM hoàn tất (có thể mất vài phút với cuộc họp dài). Phải đẩy sang job nền.

```python
# Odoo controller — chỉ nhận yêu cầu và đẩy job, trả về ngay
@http.route('/aidt_meeting/api/finalize_recording', type='json', auth='user')
def finalize_recording(self, meeting_id, total_chunks, **kw):
    meeting = request.env['aidt.meeting'].browse(meeting_id)
    meeting.write({'state': 'processing'})

    # Đẩy job sang AI service, không chờ kết quả
    requests.post(
        f"{AI_SERVICE_URL}/jobs/process_meeting",
        json={'meeting_id': meeting_id, 'total_chunks': total_chunks},
        timeout=5,   # chỉ chờ xác nhận nhận job, không chờ xử lý xong
    )
    return {'status': 'queued'}
```

**Khuyến nghị hạ tầng:** dùng một queue thật (Celery/RQ/Redis) thay vì `asyncio.create_task` đơn thuần — vì job dài, cần retry, cần theo dõi trạng thái, và không được mất khi service restart.

---

## 4. Bước 3 — Ghép audio & XỬ LÝ TẠP ÂM

Đây là mục quan trọng nhất để giải quyết ảo giác. Tạp âm không được xử lý ở một chỗ duy nhất mà chia làm **4 lớp**, mỗi lớp giải quyết một loại nhiễu khác nhau.

### 4.0. Bối cảnh: phòng họp khác hoàn toàn với thu âm cá nhân

| Đặc điểm | Thu âm cá nhân (headset) | Phòng họp (mic xa) |
|---|---|---|
| Khoảng cách mic | 5–10 cm | 1–5 m |
| Tỷ lệ tín hiệu/nhiễu | Cao | **Thấp** — giọng nói yếu, nhiễu tương đối mạnh |
| Vọng âm (reverb) | Gần như không | **Đáng kể** — tường kính, trần cao |
| Loại nhiễu chính | Tiếng thở, gõ phím | Điều hòa, quạt máy chiếu, giấy tờ, ghế kéo, nhiều người nói chồng |

Hệ quả: cấu hình khử nhiễu cho thu âm cá nhân **không áp dụng thẳng được** cho phòng họp. Nhiễu ở phòng họp yêu cầu chuẩn hóa âm lượng mạnh hơn (vì giọng nói yếu) nhưng khử nhiễu nhẹ tay hơn (vì dễ cắt luôn giọng nói yếu).

---

### 4.1. Lớp 1 — Thu âm tại client

Xử lý ngay tại nguồn, dùng khả năng có sẵn của trình duyệt (đã nêu ở mục 2.2):

```javascript
audio: {
  echoCancellation: true,   // khử vọng âm — quan trọng với loa ngoài phòng họp
  noiseSuppression: true,   // khử nhiễu nền đều đặn
  autoGainControl: true,    // khuếch đại giọng nói yếu ở mic xa
}
```

**Xử lý được:** echo từ loa, nhiễu đều đặn (điều hòa, quạt).
**Không xử lý được:** nhiễu đột ngột (ghế kéo, cửa đóng), vọng âm phòng lớn.
**Chi phí:** gần như bằng không — nên bật mặc định.

> Lưu ý: các constraint này là *gợi ý* cho trình duyệt, không đảm bảo. Chrome hỗ trợ tốt, Safari/Firefox hỗ trợ khác nhau. Không được coi lớp này là đủ.

---

### 4.2. Lớp 2 — Tiền xử lý ffmpeg trên server (lớp chính)

```python
import subprocess
from pathlib import Path

# Chuỗi filter — mỗi bước có mục đích riêng, xem giải thích bên dưới
AUDIO_FILTER_CHAIN = (
    "highpass=f=85,"                          # 1. cắt tần số thấp
    "lowpass=f=8000,"                         # 2. cắt tần số cao
    "afftdn=nf=-20:tn=1,"                     # 3. khử nhiễu nền
    "dynaudnorm=f=150:g=15:p=0.7,"            # 4. chuẩn hóa âm lượng động
    "loudnorm=I=-16:TP=-1.5:LRA=11"           # 5. chuẩn hóa mức tổng thể
)

def merge_and_denoise(meeting_id: str, total_chunks: int) -> Path:
    """Ghép chunk webm -> wav 16kHz mono đã khử nhiễu, sẵn sàng cho Whisper."""
    chunk_dir = Path(f"/data/meetings/{meeting_id}")
    output = chunk_dir / "full_audio.wav"

    list_file = chunk_dir / "chunks.txt"
    missing = []
    with open(list_file, "w") as f:
        for i in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{i}.webm"
            if chunk_path.exists():
                f.write(f"file '{chunk_path}'\n")
            else:
                missing.append(i)   # ghi log, vẫn xử lý phần còn lại

    if missing:
        logger.warning(f"Meeting {meeting_id} thiếu chunk: {missing}")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-ar", "16000",   # sample rate Whisper yêu cầu
        "-ac", "1",       # mono
        "-af", AUDIO_FILTER_CHAIN,
        str(output)
    ], check=True)

    return output
```

**Giải thích từng filter — team cần hiểu để tinh chỉnh, không copy mù:**

| Filter | Tác dụng | Nhiễu xử lý được | Rủi ro nếu chỉnh sai |
|---|---|---|---|
| `highpass=f=85` | Cắt tần số dưới 85Hz | Tiếng ù điện, rung bàn, tiếng bước chân | Đặt quá cao (>120Hz) làm giọng nam trầm bị mỏng |
| `lowpass=f=8000` | Cắt tần số trên 8kHz | Tiếng rít, nhiễu số | Whisper chỉ dùng đến 8kHz nên bước này an toàn |
| `afftdn=nf=-20` | Khử nhiễu bằng FFT | Điều hòa, quạt, tiếng ù nền | **`nf` càng âm càng mạnh** — quá tay tạo artifact gây ảo giác |
| `dynaudnorm` | Chuẩn hóa âm lượng theo từng đoạn | Người nói xa/gần mic khác nhau | Quá mạnh sẽ khuếch đại cả nhiễu lúc im lặng |
| `loudnorm` | Chuẩn hóa mức âm tổng thể | Đưa về mức chuẩn Whisper quen thuộc | Ít rủi ro |

**Vì sao `dynaudnorm` quan trọng với phòng họp:** người ngồi đầu bàn và cuối bàn có âm lượng chênh nhau rất nhiều. Không chuẩn hóa thì người ngồi xa sẽ bị Whisper bỏ qua hoặc nhận dạng sai.

---

### 4.3. Lớp 3 — RNNoise (chỉ dùng khi lớp 2 chưa đủ)

`afftdn` xử lý tốt nhiễu **đều đặn** nhưng kém với nhiễu **đột ngột** (gõ phím, sột soạt giấy, ghế kéo). RNNoise là mạng nơ-ron được huấn luyện riêng cho việc này.

```bash
# Tải model RNNoise (file .rnnn)
# https://github.com/GregorR/rnnoise-models

# Chèn arnndn vào chuỗi filter, ĐẶT TRƯỚC afftdn
ffmpeg -i input.wav \
  -af "highpass=f=85,arnndn=m=/models/std.rnnn,afftdn=nf=-12,dynaudnorm,loudnorm=I=-16" \
  -ar 16000 -ac 1 output.wav
```

**Quan trọng:** khi bật `arnndn`, phải **giảm cường độ `afftdn`** (từ `nf=-20` xuống `nf=-12` hoặc bỏ hẳn). Hai bộ khử nhiễu chồng lên nhau ở cường độ cao là công thức chắc chắn tạo ra artifact.

**Chi phí:** tăng thời gian xử lý khoảng 20–40% (chạy trên CPU). Với batch processing thì chấp nhận được, nhưng cần đo trên hạ tầng thực tế.

---

### 4.4. Lớp 4 — Lọc hậu kiểm sau khi nhận dạng

Dù lọc kỹ đến đâu vẫn có nhiễu lọt qua và khiến Whisper sinh ra câu vô nghĩa. Lớp này chặn chúng **sau** khi đã có text.

```python
import re
from collections import Counter

# Các câu Whisper hay "bịa" khi gặp im lặng/nhiễu
# (di chứng từ dữ liệu huấn luyện lấy từ video YouTube)
# ĐÂY LÀ DANH SÁCH SỐNG — team bổ sung dần từ log thực tế
HALLUCINATION_BLACKLIST = {
    "cảm ơn các bạn đã theo dõi",
    "cảm ơn đã xem video",
    "hẹn gặp lại các bạn",
    "đăng ký kênh",
    "nhấn like và đăng ký",
    "subscribe",
    "phụ đề được thực hiện bởi",
    "ghiền mì gõ",
}


def is_hallucination(text: str) -> bool:
    normalized = text.lower().strip()

    if not normalized:
        return True

    # 1. Khớp blacklist
    if any(phrase in normalized for phrase in HALLUCINATION_BLACKLIST):
        return True

    # 2. Lặp từ bất thường — dấu hiệu model bị kẹt vòng lặp
    words = normalized.split()
    if len(words) >= 6:
        most_common_count = Counter(words).most_common(1)[0][1]
        if most_common_count / len(words) > 0.5:
            return True

    # 3. Segment quá ngắn và không có nội dung thực chất
    if len(normalized) <= 3:
        return True

    return False


def clean_text(text: str) -> str:
    # Xóa từ lặp liên tiếp: "tôi tôi nghĩ" -> "tôi nghĩ"
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text, flags=re.IGNORECASE)
    # Gộp khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def filter_segments(segments: list[dict]) -> list[dict]:
    """Áp dụng cả lọc confidence và lọc ảo giác."""
    kept, dropped = [], []

    for seg in segments:
        # Lọc theo confidence của model
        if seg.get("avg_logprob", 0) < -1.0 or seg.get("no_speech_prob", 0) > 0.6:
            dropped.append({**seg, "reason": "low_confidence"})
            continue

        if is_hallucination(seg["text"]):
            dropped.append({**seg, "reason": "hallucination"})
            continue

        kept.append({**seg, "text": clean_text(seg["text"])})

    # BẮT BUỘC: log lại phần bị loại để review và tinh chỉnh ngưỡng
    # Nếu tỷ lệ dropped quá cao -> đang lọc nhầm câu thật
    logger.info(f"Giữ {len(kept)} segment, loại {len(dropped)}")
    save_dropped_for_review(dropped)

    return kept
```

**Việc phải làm định kỳ:** review danh sách `dropped` hàng tuần trong giai đoạn đầu. Hai chỉ số cần theo dõi:
- Tỷ lệ loại quá cao (>15%) → ngưỡng đang quá gắt, đang cắt mất câu thật.
- Có câu ảo giác lọt qua → bổ sung vào blacklist.

---

### 4.5. Cảnh báo: đừng khử nhiễu quá tay

**Đây là cái bẫy dễ mắc nhất.** Khi nghe file còn nhiễu, phản xạ tự nhiên là tăng cường độ filter. Nhưng:

> Khử nhiễu quá mạnh tạo ra artifact — âm thanh méo mó nhân tạo nghe như "bị bóp dưới nước". Whisper gặp những đoạn này **sinh ảo giác nhiều hơn** so với khi để nguyên nhiễu nhẹ. Model được huấn luyện trên audio thực tế có nhiễu, nó chịu được nhiễu nhẹ tốt hơn là chịu được audio bị xử lý quá tay.

**Quy trình tinh chỉnh đúng:**
1. Lấy 3–5 file ghi âm thật từ các phòng họp khác nhau làm bộ test cố định.
2. Chạy thử từng mức cấu hình, **nghe lại bằng tai** file sau khi lọc.
3. So sánh transcript đầu ra, đếm số lỗi thực tế — không đoán dựa trên "nghe có vẻ sạch hơn".
4. Chọn mức **nhẹ nhất** vẫn cho kết quả transcript tốt, không chọn mức lọc mạnh nhất.

**Cách kiểm tra nhanh xem có đang lọc quá tay:** nếu số segment bị `avg_logprob` thấp *tăng lên* sau khi bạn tăng cường độ khử nhiễu, tức là bạn đang làm hỏng audio chứ không phải làm sạch nó.

---

### 4.6. Đo lường mức nhiễu để hiệu chỉnh

Thay vì dùng ngưỡng cố định cho mọi phòng, đo mức nhiễu nền thực tế của từng file:

```python
def estimate_noise_floor(audio_path: str) -> float:
    """Ước lượng mức nhiễu nền (dB) để chọn cường độ lọc phù hợp."""
    result = subprocess.run([
        "ffmpeg", "-i", audio_path,
        "-af", "silencedetect=noise=-30dB:d=0.5",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    # Phân tích các đoạn im lặng để lấy mức nhiễu nền
    # Đoạn "im lặng" thực chất chính là room tone -> đo được mức nhiễu
    return parse_silence_output(result.stderr)


def choose_filter_strength(noise_floor_db: float) -> str:
    """Chọn cấu hình lọc theo mức nhiễu đo được, thay vì áp cứng 1 mức."""
    if noise_floor_db < -50:      # phòng rất yên
        return "highpass=f=85,loudnorm=I=-16"
    elif noise_floor_db < -35:    # nhiễu vừa
        return AUDIO_FILTER_CHAIN
    else:                         # nhiễu nặng
        return ("highpass=f=85,arnndn=m=/models/std.rnnn,"
                "afftdn=nf=-12,dynaudnorm,loudnorm=I=-16")
```

Cách này tránh được việc phòng yên tĩnh bị xử lý quá tay, còn phòng ồn thì xử lý chưa đủ.

---

## 5. Bước 4 — Speech to text (batch, chính xác cao)

**Điểm mấu chốt:** Vì không còn real-time, ta dùng được cấu hình chính xác nhất. Đây là lý do chính khiến ảo giác giảm mạnh.

```python
from faster_whisper import WhisperModel

model = WhisperModel("PhoWhisper-large-ct2", device="cuda", compute_type="float16")

def transcribe_meeting(audio_path: str) -> list[dict]:
    segments, info = model.transcribe(
        audio_path,
        language="vi",
        beam_size=5,              # batch mode: dùng được beam cao, chính xác hơn nhiều
        vad_filter=True,          # tự loại bỏ khoảng lặng -> giảm ảo giác
        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,  # đệm 2 đầu, tránh cắt cụt đầu/cuối câu
        },
        no_speech_threshold=0.6,
        condition_on_previous_text=False,  # tránh lỗi lặp dây chuyền
        word_timestamps=False,             # segment-level là đủ cho use case này
    )

    results = []
    for seg in segments:
        # Lọc segment mà model không tự tin
        if seg.avg_logprob < -1.0 or seg.no_speech_prob > 0.6:
            continue
        results.append({
            "start": seg.start,     # giây, dùng cho cột "Thời gian trong file"
            "end": seg.end,
            "text": seg.text.strip(),
        })
    return results


def format_timestamp(seconds: float) -> str:
    """Chuyển giây -> mm:ss hoặc hh:mm:ss để hiển thị."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_transcript_for_llm(segments: list[dict]) -> str:
    """Transcript có timestamp — BẮT BUỘC để LLM trích xuất được
    cột 'Thời gian trong file' cho bảng Công việc và Quyết định."""
    return "\n".join(f"[{format_timestamp(s['start'])}] {s['text']}" for s in segments)
```

> **Lưu ý thiết kế quan trọng:** Giao diện có cột "Thời gian trong file" ở cả bảng Công việc và Quyết định. Nếu transcript đưa vào LLM không kèm timestamp, cột này sẽ luôn trống. Đây không phải tính năng thêm — nó là ràng buộc bắt buộc của bước này.

---

## 6. Bước 5 — LLM tóm tắt thành JSON có cấu trúc

### 6.1. JSON schema mục tiêu (khớp đúng các trường trên giao diện)

```json
{
  "tong_quan": "string — tóm tắt 3-5 câu về mục đích và kết quả cuộc họp",
  "bien_ban_chi_tiet": "string — biên bản đầy đủ theo trình tự, chia mục rõ ràng",
  "y_chinh": ["string — các ý chính, mỗi ý 1 dòng"],
  "rui_ro": ["string — các rủi ro/vấn đề được nêu"],
  "cong_viec": [
    {
      "cong_viec": "string — nội dung công việc",
      "nguoi_phu_trach": "string — tên người, để trống nếu không rõ",
      "thoi_han": "string — deadline dạng text, để trống nếu không nêu",
      "muc_do": "cao | trung bình | thấp",
      "thoi_gian_trong_file": "mm:ss — mốc thời gian trong audio"
    }
  ],
  "quyet_dinh": [
    {
      "quyet_dinh": "string — nội dung quyết định",
      "thoi_gian_trong_file": "mm:ss"
    }
  ]
}
```

### 6.2. Prompt mẫu

```python
SYSTEM_PROMPT = """Bạn là trợ lý ghi biên bản cuộc họp. Nhiệm vụ: đọc bản
ghi lời nói (transcript) và trích xuất thành biên bản có cấu trúc.

QUY TẮC BẮT BUỘC:
1. CHỈ dùng thông tin có trong transcript. Tuyệt đối không suy diễn,
   không bổ sung thông tin không được nói ra.
2. Nếu một trường không có thông tin trong transcript, để chuỗi rỗng
   hoặc mảng rỗng. KHÔNG được bịa để lấp chỗ trống.
3. Mỗi công việc và quyết định PHẢI kèm mốc thời gian [mm:ss] lấy từ
   dòng transcript tương ứng nơi nội dung đó được nói.
4. Transcript có thể có lỗi nhận dạng giọng nói. Nếu một câu không rõ
   nghĩa, bỏ qua thay vì đoán.
5. Chỉ trả về JSON hợp lệ, không kèm giải thích, không kèm markdown.

Trả về đúng schema sau: {schema}"""


def summarize_meeting(transcript: str) -> dict:
    response = call_llm(
        system=SYSTEM_PROMPT.format(schema=JSON_SCHEMA),
        user=f"Transcript cuộc họp:\n\n{transcript}",
        temperature=0.2,  # thấp để giảm sáng tạo, tăng bám sát nội dung gốc
    )
    return parse_and_validate(response)
```

### 6.3. Validate output

```python
import json
from jsonschema import validate, ValidationError

def parse_and_validate(raw: str, max_retry: int = 2) -> dict:
    # LLM đôi khi bọc JSON trong markdown fence
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")

    try:
        data = json.loads(cleaned)
        validate(instance=data, schema=MEETING_SCHEMA)
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        # Retry với thông báo lỗi cụ thể cho LLM sửa
        if max_retry > 0:
            return retry_with_error_feedback(raw, str(e), max_retry - 1)
        raise
```

### 6.4. Xử lý cuộc họp dài

Cuộc họp 2-3 tiếng có thể vượt context window của model. Chiến lược:
1. Chia transcript thành các đoạn theo thời gian (ví dụ 30 phút/đoạn, có overlap nhẹ).
2. Tóm tắt từng đoạn riêng, **giữ nguyên timestamp gốc**.
3. Gộp các bản tóm tắt đoạn → tóm tắt lần 2 để ra `tong_quan` và `y_chinh` toàn cuộc họp.
4. `cong_viec` và `quyet_dinh` thì gộp trực tiếp danh sách từ các đoạn (khử trùng lặp).

---

## 7. Bước 6 — Ghi vào Odoo

### 7.1. Thiết kế model

```python
class AidtMeeting(models.Model):
    _name = 'aidt.meeting'

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('recording', 'Đang ghi'),
        ('processing', 'Đang xử lý'),
        ('done', 'Xong'),
        ('error', 'Lỗi'),
        ('cancelled', 'Đã huỷ'),
    ], default='draft')

    audio_file = fields.Binary('File ghi âm')
    transcript_raw = fields.Text('Transcript gốc')  # giữ lại để đối chiếu khi AI sai

    tong_quan = fields.Text('Tổng quan')
    bien_ban_chi_tiet = fields.Html('Biên bản chi tiết')
    y_chinh = fields.Text('Ý chính')
    rui_ro = fields.Text('Rủi ro')

    task_ids = fields.One2many('aidt.meeting.task', 'meeting_id', 'Công việc')
    decision_ids = fields.One2many('aidt.meeting.decision', 'meeting_id', 'Quyết định')

    error_message = fields.Text('Lý do lỗi')


class AidtMeetingTask(models.Model):
    _name = 'aidt.meeting.task'

    meeting_id = fields.Many2one('aidt.meeting', ondelete='cascade')
    name = fields.Char('Công việc', required=True)
    assignee_name = fields.Char('Người phụ trách')   # tên thô từ AI
    assignee_id = fields.Many2one('res.users', 'Người phụ trách (đã map)')
    deadline_text = fields.Char('Thời hạn')          # text thô từ AI
    deadline_date = fields.Date('Thời hạn (đã parse)')
    priority = fields.Selection([('low','Thấp'),('medium','Trung bình'),('high','Cao')])
    audio_timestamp = fields.Char('Thời gian trong file')


class AidtMeetingDecision(models.Model):
    _name = 'aidt.meeting.decision'

    meeting_id = fields.Many2one('aidt.meeting', ondelete='cascade')
    name = fields.Text('Quyết định', required=True)
    audio_timestamp = fields.Char('Thời gian trong file')
```

### 7.2. Lưu ý về việc map tên người sang user

AI trả về **tên gọi trong cuộc họp** (ví dụ "anh Tuấn", "chị Lan bên marketing"), không phải user ID. Nên:
- Lưu tên thô vào `assignee_name` (luôn giữ được nguyên văn).
- Cố gắng fuzzy match sang `res.users`, nếu khớp thì điền `assignee_id`.
- Nếu không khớp, **để trống** `assignee_id` và để người dùng tự chọn — đừng đoán bừa, gán sai người còn tệ hơn để trống.

Tương tự với `deadline_text` → `deadline_date`: giữ cả hai, vì "cuối tuần này" cần biết ngày họp mới parse được, và có thể parse sai.

---

## 8. Xử lý lỗi

| Bước lỗi | Xử lý | Có mất dữ liệu không |
|---|---|---|
| Upload chunk fail | Retry từ IndexedDB ở client | Không, nếu retry thành công |
| Ghép audio fail | State → Lỗi, giữ nguyên các chunk | Không, chạy lại được |
| STT fail (OOM, GPU busy) | Retry job, giữ file audio | Không |
| LLM trả JSON sai schema | Retry tối đa 2 lần với feedback lỗi | Không |
| LLM fail hoàn toàn | State → Lỗi nhưng **vẫn lưu transcript** | Không — transcript vẫn dùng được |

**Nguyên tắc:** File audio và transcript là dữ liệu gốc, **không bao giờ được xóa khi lỗi**. Mọi bước sau đó đều chạy lại được từ chúng.

---

## 9. Thứ tự triển khai đề xuất

1. **Ghi âm + upload chunk + lưu file** — làm trước, tự nó đã có giá trị (có bản ghi để nghe lại). Bật sẵn lớp 1 khử nhiễu ở client (chi phí bằng không).
2. **Thu thập bộ file test từ phòng họp thật** — 3–5 file từ các phòng khác nhau. Không có bộ này thì mọi việc tinh chỉnh khử nhiễu về sau đều là đoán mò.
3. **STT batch + lớp 2 khử nhiễu ffmpeg + hiển thị transcript** — bước này cho ra kết quả kiểm chứng được ngay bằng bộ test ở trên.
4. **Lớp 4 lọc hậu kiểm** (confidence + blacklist) — làm cùng lúc với bước 3, chi phí thấp, hiệu quả cao.
5. **LLM tóm tắt các trường text** (tổng quan, biên bản, ý chính, rủi ro) — dễ hơn phần bảng.
6. **Trích xuất bảng Công việc + Quyết định** — khó nhất vì cần timestamp và map người, làm sau cùng.
7. **Lớp 3 RNNoise** — chỉ làm nếu đo được là lớp 2 chưa đủ. Đừng làm trước khi có số liệu.
8. **Cho phép người dùng sửa tay mọi trường AI sinh ra** — bắt buộc phải có, AI sẽ sai và người dùng cần sửa được.

---

## 10. Việc cần đo lường sau khi chạy thật

- Thời gian xử lý trung bình / 1 giờ ghi âm (đặt kỳ vọng cho người dùng).
- Tỷ lệ trường bị người dùng sửa tay (chỉ báo trực tiếp về chất lượng AI).
- Tỷ lệ công việc AI trích ra bị xóa đi (chỉ báo về việc AI đang bịa thêm việc không có thật).
- Tỷ lệ job vào trạng thái Lỗi và nguyên nhân phân loại.

**Riêng về khử nhiễu:**
- Tỷ lệ segment bị loại ở lớp 4, tách theo lý do (`low_confidence` vs `hallucination`). Tỷ lệ > 15% là dấu hiệu lọc quá gắt.
- Phân phối `avg_logprob` trung bình theo từng phòng họp — phòng nào thấp bất thường thì cần xem lại thiết bị thu âm chứ không phải chỉnh filter.
- Số câu ảo giác lọt qua được người dùng phát hiện → bổ sung blacklist.

---

*Draft kỹ thuật để team review. Các tham số (chunk 30s, beam_size=5, temperature 0.2) là điểm khởi đầu, cần tinh chỉnh theo dữ liệu thực tế.*
