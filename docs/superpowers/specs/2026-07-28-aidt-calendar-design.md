# BAN THIẾT KẾ CHI TIẾT — TÍNH NĂNG LÊN LỊCH & QUẢN LÝ CUỘC HỌP (`AIDT_CALENDAR`)

## 1. NGUYÊN TẮC THIẾT KẾ & PHẠM VI

- **Tên module**: `aidt_calendar` (đặt tại `custom-addons/aidt_calendar`).
- **Kế thừa**: Extended từ các module chuẩn Odoo 19: `calendar`, `resource`, `project`, `portal`.
- **Mục tiêu**:
  1. Quản lý Lịch họp, Lịch công tác Thường trực Cấp ủy / Ban Thường vụ & Lịch phòng ban.
  2. Đăng ký & Kiểm tra trùng lịch phòng họp / tài nguyên (`resource.resource`).
  3. Liên kết 2 chiều với Văn bản (`aidt.document`), Kho lưu trữ tài liệu họp (`dms.file`), và Nhiệm vụ chỉ đạo sau họp (`project.task`).
  4. Phân quyền bảo mật Độ mật 4 mức (N-04 / N-05) bảo vệ ở tầng CSDL (Record Rules).
  5. Đăng ký & Phê duyệt Lịch làm việc / Tiếp công dân & Doanh nghiệp qua Portal.

---

## 2. ARCHITECTURE & DATA MODEL

### 2.1. Model `calendar.event` (Kế thừa)

Thêm các trường tùy chỉnh vào `calendar.event`:

| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `secrecy` | `Selection` | `[('thuong', 'Thường'), ('mat', 'Mật'), ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')]`, default=`thuong`, tracking=True |
| `secrecy_level` | `Integer` | Computed từ `secrecy` (0: Thường, 1: Mật, 2: Tối mật, 3: Tuyệt mật), `store=True`, `index=True` |
| `document_id` | `Many2one('aidt.document')` | Văn bản nguồn (Giấy mời họp / Thông báo kết luận) |
| `room_id` | `Many2one('resource.resource')` | Phòng họp đăng ký |
| `department_id` | `Many2one('hr.department')` | Đơn vị chủ trì |
| `is_weekly_schedule` | `Boolean` | Cờ hiển thị Lịch công tác tuần Lãnh đạo |
| `appointment_type` | `Selection` | `[('internal', 'Nội bộ'), ('leadership', 'Lịch Cấp ủy'), ('citizen', 'Tiếp công dân')]`, default=`internal` |
| `task_ids` | `One2many('project.task', 'meeting_id')` | Danh sách nhiệm vụ chỉ đạo sau họp |

### 2.2. Model `project.task` (Kế thừa)

Bổ sung trường liên kết ngược về cuộc họp:
- `meeting_id`: `Many2one('calendar.event', string='Từ cuộc họp')`

### 2.3. Model Portal `aidt.appointment.registration` (Đăng ký tiếp dân)

| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `name` | `Char` | Họ và tên người đăng ký |
| `identity_card` | `Char` | Số CCCD / MST |
| `phone` | `Char` | Số điện thoại |
| `email` | `Char` | Email liên hệ |
| `organization` | `Char` | Cơ quan / Đơn vị công tác |
| `content` | `Text` | Nội dung xin đăng ký làm việc |
| `preferred_date` | `Datetime` | Thời gian đề xuất |
| `state` | `Selection` | `[('draft', 'Mới tiếp nhận'), ('approved', 'Đã duyệt'), ('rejected', 'Từ chối')]` |
| `event_id` | `Many2one('calendar.event')` | Cuộc họp tương ứng sau khi duyệt |

---

## 3. PHÂN QUYỀN & BẢO MẬT ĐỘ MẬT (N-04 / N-05)

### 3.1. Phân quyền tầng Record Rules (Security)

1. **Lịch họp Mật / Tối mật / Tuyệt mật**:
   - `calendar.event` Record Rule: `[('secrecy_level', '<=', user.clearance_level)]`.
   - Nếu cuộc họp mang tính riêng tư hoặc thuộc đơn vị riêng:
     `['|', ('privacy', '!=', 'private'), '|', ('partner_ids', 'in', [user.partner_id.id]), ('user_id', '=', user.id)]`.

2. **Quyền truy cập tài liệu đính kèm**:
   - Tệp DMS đính kèm cuộc họp tuân thủ phân quyền `clearance_level` của `aidt_dms`.

---

## 4. QUY TRÌNH NGHIỆP VỤ CHÍNH

### 4.1. Đăng ký & Kiểm tra Trùng lịch Phòng họp
- Trên phương thức `@api.constrains('room_id', 'start', 'stop')`:
  - Tìm kiếm các `calendar.event` trùng `room_id` trong khoảng thời gian `(start < existing.stop) AND (stop > existing.start)`.
  - Nếu tìm thấy cuộc họp khác, quăng `ValidationError("Phòng họp đã được đăng ký cho cuộc họp khác trong khoảng thời gian này.")`.

### 4.2. Liên kết Văn bản & Kế thừa Độ mật
- Khi chọn `document_id`:
  - Tự động gán `secrecy = document_id.secrecy`.
  - Tự động kế thừa danh sách đại biểu từ `shared_user_ids` của văn bản.

### 4.3. Sinh Nhiệm vụ Chỉ đạo Sau Cuộc họp
- Nút bấm `action_create_followup_task()` trên form `calendar.event`:
  - Mở popup wizard/form `project.task`.
  - Gán `meeting_id = self.id`, `department_id = self.department_id`.
  - Đính kèm link trỏ ngược về cuộc họp trên Chatter.

### 4.4. Lịch Công tác Tuần Lãnh đạo
- Menu item "Lịch công tác tuần" mở view List/Matrix lọc theo `is_weekly_schedule = True`.
- Cung cấp QWeb Report xuất file PDF/Print bảng lịch tuần theo thứ và ca (Sáng / Chiều).

### 4.5. Luồng Đặt lịch Tiếp công dân trên Portal
- Form công khai tại `/dang-ky-lich-lam-viec`.
- Công dân điền thông tin -> Tạo bản ghi `aidt.appointment.registration` (trạng thái `draft`) -> Gửi `mail.activity` cho Văn thư.
- Cán bộ bấm "Phê duyệt" -> Tạo `calendar.event` (`appointment_type = 'citizen'`) -> Gửi mail/SMS xác nhận thời gian & địa điểm cho công dân.

---

## 5. KIỂM THỬ & ĐÁNH GIÁ (TEST SUITE)

1. `test_meeting_secrecy_record_rule`: Kiểm tra cán bộ Level 0 không xem được lịch họp Level 1, 2, 3.
2. `test_room_booking_conflict`: Kiểm tra chặn trùng lịch phòng họp cùng khung giờ.
3. `test_create_task_from_meeting`: Kiểm tra nút sinh nhiệm vụ tạo `project.task` thành công và giữ link 2 chiều.
4. `test_portal_appointment_approval`: Kiểm tra luồng tiếp nhận & duyệt lịch hẹn tiếp dân qua Portal.
