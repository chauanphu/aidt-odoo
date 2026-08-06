# Thiết kế Tích hợp Mô hình AI Gemma 4 (Chain-of-Thought Reasoning 5 Bước) cho Bóc tách & Phân công Văn bản Hành chính

## 1. Mục tiêu & Tổng quan
Khắc phục tình trạng hệ thống bị vướng luồng xử lý tắt (Fast-Path Regex) dẫn tới việc bỏ qua mô hình **Gemma 4 12B**. 

Kích hoạt mô hình **Gemma 4 Multimodal Vision (Port 11434)** chạy chính thức cho 100% các tệp scan/PDF với quy trình suy luận 5 bước **Chain-of-Thought (CoT)**, đồng thời hiển thị toàn bộ nhật ký tư duy suy luận của AI lên Bảng Preview cho người dùng rà soát.

---

## 2. Kiến trúc Xử lý AI Pipeline (`docker_unlimited_ocr/server/pipeline.py`)

### 2.1. Loại bỏ Fast-Path Regex Bypass
- Tắt hoàn toàn việc tự động trả kết quả Regex khi chuỗi ký tự dài > 50.
- Mọi văn bản scan/PDF đều bắt buộc thực hiện gọi API sang mô hình **Ollama Gemma 4 12B** trên cổng `11434`.

### 2.2. Quy trình Suy luận Chain-of-Thought (CoT) 5 Bước của Gemma 4
AI Gemma 4 sẽ nhận đầu vào gồm:
1. Hình ảnh trang scan (Base64 PNG 150 DPI) để "nhìn" con dấu, thể thức, bố cục.
2. Văn bản OCR thô để đọc chính xác từng từ.

AI sẽ thực thi CoT theo 5 bước:
- **Bước 1 (Phân tích thể thức):** Xác định `loai_van_ban` (Công văn, Báo cáo, Quyết định, Kế hoạch...).
- **Bước 2 (Đánh giá khẩn/mật):** Phân tích ngữ cảnh tính chất cấp bách (`do_khan`) và độ nhạy cảm thông tin (`do_mat`).
- **Bước 3 (Trích xuất chỉ mục):** Đọc số đến, ngày đến, số/ký hiệu gốc, ngày ban hành gốc.
- **Bước 4 (Định tuyến phân công):** Suy luận đơn vị xử lý (`don_vi`) phù hợp trong danh sách 15 phòng ban Odoo.
- **Bước 5 (Trích dẫn bằng chứng):** Trích dẫn nguyên văn câu/đoạn văn bản làm căn cứ phân công (`ly_do_phan_cong` / `cot_reasoning`), cam kết chống bịa đặt (Anti-Hallucination).

---

## 3. Giao diện Odoo Preview & Wizard (`aidt_dms`)

### 3.1. Thêm trường Nhật ký Suy luận
- Thêm trường `extracted_reasoning = fields.Text('Nhật ký AI Gemma 4 Suy luận & Căn cứ phân công')` vào `aidt.document.ocr.wizard`.

### 3.2. Hiển thị trên Bảng Xem trước (Preview Dialog)
- Thêm khu vực hiển thị nổi bật **"NHẬT KÝ AI GEMMA 4 SUY LUẬN & CĂN CỨ PHÂN CÔNG (CHAIN-OF-THOUGHT)"** trong cửa sổ Xem trước.
- Người dùng trực tiếp nhìn thấy các bước tư duy của Gemma 4 và lý do AI đề xuất đơn vị xử lý trước khi bấm **"Xác nhận & Điền vào Form"**.

---

## 4. Kế hoạch Kiểm thử & Xác minh
1. Kiểm tra log Docker của Ollama `http://ollama:11434` đảm bảo nhận request từ Pipeline Backend port 8001.
2. Chạy thử nghiệm bóc tách tệp PDF mẫu và xác nhận thông báo suy luận 5 bước xuất hiện trên Bảng Preview.
3. Chạy toàn bộ Odoo Unit Tests đảm bảo không phát sinh lỗi.
