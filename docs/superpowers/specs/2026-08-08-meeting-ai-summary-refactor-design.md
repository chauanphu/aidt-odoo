# Thiết kế (Spec): Tái cấu trúc luồng AI Tóm tắt Cuộc họp (Batch Processing)

## 1. Tổng quan
Dịch chuyển kiến trúc ghi âm và bóc băng cuộc họp từ mô hình **thời gian thực (real-time streaming)** sang mô hình **xử lý mẻ (batch processing)**.
Mục tiêu là giảm tải cho Odoo, giảm tối đa ảo giác AI bằng cách sử dụng batch mode của PhoWhisper, và tách biệt tải xử lý nặng sang một AI Service độc lập.

## 2. Kiến trúc Hệ thống mới (Microservice)
Odoo sẽ không còn đóng vai trò xử lý âm thanh hay trực tiếp gọi API AI. Thay vào đó:
1. **Odoo**: Cung cấp giao diện ghi âm, nhận file audio chunk từ client, lưu trữ vết trên filesystem/DB. Gọi webhook sang AI Service khi cuộc họp kết thúc. Cung cấp API Webhook để nhận kết quả JSON trả về.
2. **AI Service**: (Service độc lập) Nhận job từ Odoo, gộp audio bằng `ffmpeg`, bóc băng bằng `faster_whisper` (PhoWhisper), tóm tắt bằng LLM, và post kết quả trả về Odoo.

## 3. Chi tiết Thay đổi - Odoo Backend

### 3.1 Dọn dẹp Code cũ
Xóa bỏ các models và logic không còn cần thiết:
* Xóa `asr_client.py`, `summary_client.py`, `audio_prep.py`, `text_filter.py`, `transcript_builder.py`.
* Bỏ model `aidt.meeting.segment` (tính năng hiện từng câu đã cũ, thay bằng một trường `transcript_raw` lưu toàn văn bản trên `aidt.meeting.recording`).
* Bỏ các phương thức liên quan đến phát tín hiệu `bus.bus` real-time.

### 3.2 Sửa đổi Model `aidt.meeting.chunk`
* Xóa logic bóc băng nội bộ (`_cron_process`, `_process_one`, `_claim`).
* Model này chỉ còn vai trò lưu vết tiến trình upload file (`ir.attachment`) khi client tải chunk lên.

### 3.3 Sửa đổi Model `aidt.meeting.recording`
* Xóa luồng cron tự động dò mẩu (vì mọi thứ dựa vào thao tác kết thúc rõ ràng).
* Cập nhật hàm `action_stop` (Kết thúc ghi âm):
  - Đổi trạng thái sang `processing`.
  - Gọi HTTP POST sang AI Service với payload chứa `meeting_id`, `total_chunks`, URL để AI tải từng chunk file, và callback webhook.
* Xây dựng Controller Webhook để AI Service trả kết quả về:
  - Cập nhật các trường: `title`, `overview`, `key_points`, `decisions`, `action_items`, `risks`, `meeting_minutes` từ payload JSON.
  - Xử lý Fuzzy Match tìm ID người dùng cho bảng Task: Map `assignee_name` với `res.users`.

## 4. Chi tiết Thay đổi - JS Frontend
* Bỏ socket real-time. Sử dụng `MediaRecorder` cắt audio thành các chunk 30s.
* Upload tức thì mỗi 30s (qua `ondataavailable`).
* Xử lý Fault-tolerance: Thêm Retry queue trên frontend nếu upload thất bại do đứt mạng.
* Cảnh báo `beforeunload` chặn đóng tab khi đang chạy.
* Bấm nút kết thúc -> gọi `finalize_recording` báo Odoo chuyển trạng thái và gọi AI.

## 5. Xử lý Lỗi & Tự phục hồi
* Audio chunk và transcript gốc KHÔNG bao giờ bị xoá khi gặp lỗi để bảo toàn cơ hội chạy lại.
* Nếu AI trả JSON sai schema, webhook Odoo trả về lỗi `400 Bad Request` cho AI Service tự thử lại.
* Nếu AI Service sập, sếp có quyền ấn "Thử lại AI" trong trạng thái Lỗi.
