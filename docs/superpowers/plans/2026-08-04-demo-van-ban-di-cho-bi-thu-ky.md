# Demo Văn Bản Đi Chờ Bí Thư Ký Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tạo một văn bản đi `[DEMO]` trong database `aidt_demo`, đang ở trạng thái `cho_ky` và có tệp Word để Bí thư ký số.

**Architecture:** Dùng Odoo shell và ORM để upsert văn bản theo tiêu đề chính xác, sau đó upsert tệp đính kèm theo văn bản và tên file. Việc tạo dữ liệu chỉ tác động database demo; không thêm seed XML mới.

**Tech Stack:** Odoo 19 ORM, Python, PostgreSQL, Docker Compose

## Global Constraints

- Tiêu đề phải bắt đầu bằng `[DEMO]`.
- Văn bản phải dừng ở trạng thái `cho_ky`; không gọi hành động ký.
- Tác vụ phải idempotent và không tạo bản sao khi chạy lại.
- Tệp đính kèm lấy từ `aidt_sign/data/certs/sample_document.docx`.

---

### Task 1: Upsert văn bản và tệp đính kèm demo

**Files:**
- Read: `custom-addons/aidt_sign/data/certs/sample_document.docx`
- Modify: database `aidt_demo`, models `aidt.document` và `ir.attachment`

**Interfaces:**
- Consumes: XML IDs người dùng và phòng ban từ `aidt_org_demo`
- Produces: một `aidt.document` tên `[DEMO] Công văn chỉ đạo tăng cường bảo đảm an toàn thông tin` cùng tệp `sample_document.docx`

- [ ] **Step 1: Kiểm tra trạng thái ban đầu**

Chạy Odoo shell, đếm văn bản có tiêu đề chính xác và số tệp đính kèm tương ứng. Ghi nhận kết quả trước thay đổi.

- [ ] **Step 2: Upsert dữ liệu qua ORM**

Tìm văn bản theo `name` và `direction`. Nếu chưa có thì `create`; nếu đã có thì `write`. Gán `state='cho_ky'`, người soạn, các cấp duyệt, Bí thư và các ý kiến duyệt. Tìm tệp theo `res_model`, `res_id`, `name`; tạo hoặc cập nhật nội dung base64 từ file mẫu.

- [ ] **Step 3: Commit transaction**

Gọi `env.cr.commit()` sau khi cả văn bản và tệp đính kèm được ghi thành công.

- [ ] **Step 4: Xác minh kết quả**

Đọc lại qua ORM và assert: chỉ có một văn bản đúng tiêu đề, `state == 'cho_ky'`, `nguoi_ky_id` là `aidt_org_demo.user_bithu`, và có đúng một tệp `sample_document.docx` với `datas` không rỗng.
