# Nâng chất lượng bóc băng: tiền xử lý audio + đổi model ASR

Ngày: 05/08/2026
Nhánh: `feat/meeting-transcription-minutes`
Module: `custom-addons/aidt_meeting_minutes`

## 1. Vấn đề

Tính năng đã bóc băng được (từ 05/08/2026), nhưng chất lượng thấp và có ảo
giác (hallucination). Bằng chứng thật — bản ghi 1140, hai người nói, kênh
1020:

```
[873] vương bị trần quyền nhưng mà đợi kéo như này nó nó tắt lại nó ng?em lại cái cuộc họp này nà.
[874] nó lưu lại đúng không anh nó tùy theo cái mức độ mật của hỗn hợp ví dụ mà người dùng mà không cho ghim á thì họ cứ tắt đó đang ghim.
[875] đang găm nếu ví dụ anh muốn cho thì bút bấm từ chối nên sẽ không găm bên cũ của anh á không anh chạy lô cồ á toàn bộ lô cồ của mình thậm chí con ngôi đồ chạy này là của mình.
[876] thậm chí con mua đồ chạy này cũng là con whisper luôn.
```

Giải mã: `lô cồ` = "local", `con ngôi đồ` / `con mua đồ` = "con model",
`ghim`/`găm` = "ghi âm", `hỗn hợp` = "cuộc họp", `vương bị trần quyền` =
"vấn đề phân quyền".

Âm thanh đã được nghe ĐÚNG — chỉ có TỪ là sai. Đây là lỗi mô hình ngôn ngữ,
không phải lỗi chất lượng tín hiệu. `vinai/PhoWhisper-large` được tinh chỉnh
trên tiếng Việt đọc (kiểu VLSP): nó xuất chữ thường, không dấu câu, và không
có vốn từ cho hội thoại kỹ thuật hay từ tiếng Anh chen vào.

## 2. Nguồn tham chiếu và điều PHẢI nói rõ

Dự án tham chiếu: `~/projects/STT_T-m-T-t-AI`.

**Dự án đó KHÔNG có tiền xử lý tín hiệu audio nào cả.** Grep toàn repo cho
`loudnorm|dynaudnorm|afftdn|arnndn|highpass|lowpass|silenceremove|volume=|dcshift`
không có kết quả nào ngoài CSS. Toàn bộ "tiền xử lý" của nó là:

```
ffmpeg -y -hide_banner -loglevel error -i <src> -vn -ar 16000 -ac 1 \
       -acodec pcm_s16le -f wav normalized.wav
```

— không có `-af` nào hết.

**Dự án đó cũng KHÔNG dùng Whisper** ở bất kỳ dạng nào. Engine thật là
sherpa-onnx Zipformer (local), Nvidia Riva Parakeet, và Soniox. Hai nhãn UI
ghi "Whisper AI Engine" trong `SettingsPanel.tsx:310` và `MeetingDetail.tsx:488`
là mô tả SAI trong chính code của họ.

Vậy bài học rút ra từ repo đó KHÔNG phải "thiếu tiền xử lý", mà là **thiếu
HẬU xử lý và cắt mẩu thông minh hơn**:

| Repo tham chiếu có | Ta có | Nhằm vào |
|---|---|---|
| Blocklist 23 mẫu ảo giác + bỏ `len(text) <= 3` | không có | **ảo giác** |
| Cắt tại điểm giữa khoảng lặng (Silero VAD, tối thiểu 300 ms) | cắt cứng 15 giây | chính xác ở mối nối |
| Khử trùng 2 tầng: hậu tố 120 ký tự, rồi n-gram 15 từ với dò lùi 6 vị trí | chỉ khớp đuôi 12 từ chính xác | lặp chữ ở mối nối |
| `language_hints` / `language_code` ở MỌI engine | **ta không gửi `language` gì cả** | **sai từ** |

## 3. Phạm vi đã chốt

Người dùng đã chọn:
- **Đổi sang `openai/whisper-large-v3` ngay**, không đo trước.
- **Đặt phần xử lý audio ở SERVER (trong Odoo)**, không ở trình duyệt.

## 4. Thiết kế

### 4.1 Đổi model

`docker-compose.ai.yml`: `--model=openai/whisper-large-v3`, giữ
`--gpu-memory-utilization=0.25`. Cùng cỡ kiến trúc với PhoWhisper-large (vốn
là bản tinh chỉnh của large-v2), ~3.1 GB trọng số; GPU còn trống 10.5 GB.

**Rủi ro phải ghi lại:** large-v3 được ghi nhận là ảo giác trên khoảng lặng
NHIỀU HƠN v2, không phải ít hơn. Vì vậy cổng lọc tiếng nói ở §4.3 PHẢI ra
cùng đợt, không được để lại làm sau.

### 4.2 `asr_client`: gửi những tham số chưa bao giờ gửi

Đã kiểm chứng trên service đang chạy (endpoint trả 400 với tham số bịa, nên
việc nó nhận ba tham số này là có ý nghĩa), và `prompt` làm ĐỔI kết quả giải
mã thật (`turnips` → `ternips`):

- `language=vi` — không có nó, large-v3 tự đoán ngôn ngữ theo TỪNG mẩu 15
  giây và có thể lật sang tiếng Anh giữa cuộc họp. Đã quan sát PhoWhisper
  bóc một tệp tiếng Anh ra tiếng Anh.
- `prompt` — mồi vốn từ họp hành/kỹ thuật tiếng Việt. **Đây là cách sửa
  trực tiếp `lô cồ` → "local" và `ngôi đồ` → "model".** Whisper giới hạn
  initial_prompt ở 224 token (nửa ngữ cảnh 448) — phải cắt và ghi rõ.
- `temperature=0`.

Cả ba thành `ir.config_parameter` + trường ở trang Cấu hình, đúng khuôn mẫu
`asr_response_format`.

### 4.3 `models/audio_prep.py` mới — server-side, PyAV

PyAV 18 đã có sẵn trong container Odoo (không cần thêm phụ thuộc, và container
KHÔNG có binary `ffmpeg`). Giải mã + lấy mẫu lại một mẩu 10 giây mất 37 ms.
Đã xác nhận các filter `loudnorm`, `highpass`, `speechnorm`, `afftdn`,
`silenceremove`, `arnndn` đều dùng được qua PyAV.

Gọi từ `_process_one`, giữa lúc đọc attachment và lúc gọi `_transcribe`:

1. **Giải mã** MP3 → 16 kHz mono float32.
2. **Cổng lọc tiếng nói** — khung 20 ms, RMS từng khung, yêu cầu ít nhất N
   khung vượt ngưỡng. Trượt → mẩu chuyển `done` với 0 đoạn và ghi lại lý do;
   **KHÔNG gọi ASR**. Cách này diệt cả lớp lỗi ảo-giác-trên-khoảng-lặng ngay
   từ gốc thay vì lọc đầu ra của nó. `RMS_FLOOR = 0.005` hiện tại tính trên
   cả mẩu và dễ dãi hơn 6 lần so với chính cổng năng lượng dự phòng của repo
   tham chiếu (`energy > 0.001`, tức RMS > 0.0316).
3. **Điều kiện hoá** — high-pass 80 Hz + `speechnorm` cân mức.
4. **Mã hoá** → WAV `pcm_s16le` 16 kHz mono — đúng định dạng chuẩn của repo
   tham chiếu. `_part_content_type` đã map sẵn `.wav`.

**Những thứ CỐ Ý không port, kèm lý do:**

- **Khử nhiễu** (`afftdn`/`arnndn`) — audio của ta đến từ một track mic
  WebRTC vốn ĐÃ qua noise-suppression và AGC của trình duyệt. Chồng thêm một
  bộ khử nhiễu thứ hai lên tiếng nói đã xử lý sẽ làm xấu đi. Repo tham chiếu
  cũng không khử nhiễu.
- **Cắt bỏ khoảng lặng** — sẽ phá toàn bộ số học `offset_ms`/`duration_ms` →
  mốc thời gian mà mọi phép tính đoạn của ta dựa vào. Repo tham chiếu cũng
  GIỮ khoảng lặng; nó chỉ dùng VAD để chọn ĐIỂM CẮT.
- **Silero VAD ONNX** — cần `onnxruntime` trong ảnh Odoo cộng một tệp model.
  Cổng năng lượng theo khung chính là đường dự phòng của repo tham chiếu và
  không tốn gì. Chỉ thêm Silero nếu đo đạc cho thấy cổng này không đủ.

### 4.4 Hậu xử lý — blocklist ảo giác

Port 23 mẫu, với MỘT thay đổi có chủ ý. Repo tham chiếu xoá TOÀN BỘ văn bản
nếu bất kỳ mẫu nào khớp ở BẤT KỲ đâu. Với một lát 15 giây của một cuộc họp
hành chính thì như vậy quá tàn phá — ai đó nói thật câu "cảm ơn các bạn đã
theo dõi" sẽ âm thầm xoá 15 giây biên bản. Thay vào đó: chỉ bỏ khi phần khớp
chiếm gần trọn văn bản, và **ghi lại cái đã bỏ trên bản ghi mẩu** để còn kiểm
tra được. Đây đúng theo nguyên tắc đã viết sẵn trong `transcript_builder`:
xoá thừa làm mất nội dung âm thầm, tệ hơn một dấu vết nhìn thấy được.

Cộng thêm luật bỏ `len(text) <= 3` của repo tham chiếu.

**Từ chối rõ ràng:** `normalize_vietnamese_text` của repo tham chiếu. Nó
`.lower()` mọi từ không đứng đầu câu và không phải token in hoa 2–5 ký tự —
"Nguyễn Ngọc Thịnh" thành "Nguyễn ngọc thịnh". Trong một văn bản chủ yếu là
tên người và tên cơ quan, đó là làm hỏng dữ liệu. large-v3 tự xuất đúng hoa
thường và dấu câu; PhoWhisper mới là lý do ta không có.

### 4.5 `transcript_builder` — khử trùng mối nối tốt hơn

Lấy phần dò lùi 6 vị trí của repo tham chiếu, để một từ ASR thừa ở mối nối
không còn phá được phép khớp. Giữ sàn tối thiểu 2 từ của ta. **Bỏ tầng khớp
theo ký tự của họ** (tối thiểu 5 ký tự là quá lỏng với tiếng Việt đơn âm).

### 4.6 `action_retranscribe` trên bản ghi

Thứ làm cho mọi điều trên ĐO ĐƯỢC. Hiện tại một bản bóc băng tệ là vĩnh viễn
và không thử lại được. Nút này chạy lại audio đã lưu qua cấu hình hiện hành —
nghĩa là muốn tinh chỉnh thì phải tạm nâng `audio_retention_days` trên CSDL
dev, mà không đổi mặc định riêng tư của sản phẩm (`0` là mặc định XUẤT XƯỞNG,
một lựa chọn riêng tư có chủ ý cho biên bản họp hành chính).

## 5. Ngoài phạm vi, có chủ ý

Biên mẩu vẫn cắt cứng 15 giây. Việc nắn điểm cắt về khoảng lặng nằm ở recorder
phía trình duyệt, mà phạm vi đã chốt là server-side. Phần chồng lấn 1.5 giây
cộng khử trùng cải tiến che được mối nối; nên đo tác động của việc đổi model
trước khi thêm biến thứ hai.

## 6. Kiểm thử

Test đơn vị: cổng lọc tiếng nói (im lặng / tông đơn / giống tiếng nói tổng
hợp), từng mẫu blocklist cộng một ca phủ định là tiếng nói thật, nâng cấp khử
trùng (port ca test tiếng Việt của repo tham chiếu), và một vòng round-trip
PyAV khẳng định độ dài được bảo toàn. Test tích hợp chạy qua `_process_one`
với ASR giả lập. Không thêm phụ thuộc Python. Xoá `aidt_test` sau khi chạy
theo quy ước dự án. `README.md` và `docs/GUIDANCE.md` cập nhật NGAY trong đợt
này, không để lại.
