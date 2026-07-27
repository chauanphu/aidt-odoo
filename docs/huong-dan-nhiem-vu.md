# Hướng dẫn sử dụng — Quản lý Nhiệm vụ (`aidt_task`)

> Module: `custom-addons/aidt_task` (+ `aidt_task_demo` dữ liệu mẫu).
> Đáp ứng Nhóm 5 (MVP) phần không-AI: T-05, T-06, T-07, T-08, T-09, T-11,
> T-12, T-13, T-14, T-15. Phần AI bóc tách (T-01→T-04) sẽ bổ sung sau.

---

## 1. Chức năng này để làm gì?

Theo dõi **nhiệm vụ** trong Văn phòng cấp ủy — từ khi giao đến khi đóng:

- Giao việc **từ một văn bản** (nghị quyết, kết luận, thông báo…) hoặc **giao
  trực tiếp** (ad-hoc, không cần văn bản).
- Gắn **đơn vị chủ trì + đơn vị phối hợp**, **người thực hiện**, **hạn**, **độ mật**.
- Đi theo **vòng đời** rõ ràng: Mới → Đang thực hiện → Chờ duyệt → Hoàn thành.
- **Tự nhắc việc** trước hạn 7/3/1 ngày và khi quá hạn; **cảnh báo lãnh đạo**
  danh sách quá hạn hằng tuần.
- **Báo cáo kết quả** kèm file minh chứng; **người giao duyệt đóng**.
- **Bảng điều khiển** đếm nhanh: quá hạn / chờ duyệt / chưa hoàn thành.

**Nguyên tắc bảo mật quan trọng:** nhiệm vụ trích từ văn bản mật thì bản thân
nhiệm vụ (và báo cáo của nó) **cũng mật tương đương** — người không đủ độ mật
**không nhìn thấy** ở mọi nơi (danh mục, tìm kiếm, dashboard). Đây là chặn ở
**tầng dữ liệu**, không chỉ ẩn trên giao diện.

---

## 2. Vai trò & quyền

Dùng lại 6 vai trò sẵn có của hệ thống (`aidt_org`):
Chuyên viên → Văn thư → Chánh VP → Phó Bí thư → Bí thư → Quản trị.

Nhìn thấy nhiệm vụ nào phụ thuộc **2 điều kiện cùng lúc (AND)**:

1. **Độ mật:** `mức mật của nhiệm vụ ≤ mức thanh khoản (clearance) của bạn`.
   Thang: Thường(0) < Mật(1) < Tối mật(2) < Tuyệt mật(3).
2. **Phạm vi:** bạn thuộc **đơn vị chủ trì/phối hợp** của nhiệm vụ, **hoặc**
   bạn là **người thực hiện / người giao**.

> Quản trị viên ứng dụng thấy mọi phạm vi, nhưng **vẫn bị chặn theo độ mật** —
> muốn xem Tuyệt mật phải có clearance = 3. Đây là cố ý (N-04).

---

## 3. Tạo nhiệm vụ

### Cách A — Bóc tách từ văn bản (khuyến nghị)

1. Mở **Văn bản** cần giao việc (app Văn bản → chọn văn bản).
2. Bấm nút **"Nhiệm vụ"** (nút tròn góc trên form — hiển thị số nhiệm vụ đã có).
3. Bấm **Tạo** (New). Hệ thống **điền sẵn**:
   - **Đơn vị chủ trì** = đơn vị của văn bản,
   - **Độ mật** = độ mật của văn bản (bạn có thể **nâng cao hơn**, không hạ thấp).
4. Điền **Nội dung nhiệm vụ**, dán **Đoạn trích nguồn** + **Vị trí đoạn**
   (trang/mục) để đối chiếu về sau (T-07).
5. Chọn **Người thực hiện**, **Hạn**, **Đơn vị phối hợp** (nếu có). Lưu.

> Mọi nhiệm vụ tạo cách này **luôn trỏ về văn bản gốc** — mở nhiệm vụ là truy
> được văn bản + đoạn nguồn.

### Cách B — Giao trực tiếp (ad-hoc)

1. Vào app **Nhiệm vụ → Danh mục nhiệm vụ → Tạo**.
2. Bỏ trống **Văn bản nguồn**. Chọn **Đơn vị chủ trì** và **Độ mật** thủ công
   (mặc định *Thường*).
3. Điền nội dung, người thực hiện, hạn. Lưu.

### Các trường chính

| Trường | Ý nghĩa |
|---|---|
| Nội dung nhiệm vụ | Việc cần làm |
| Văn bản nguồn | Văn bản phát sinh nhiệm vụ (tùy chọn) |
| Đoạn trích / Vị trí đoạn | Trích dẫn để đối chiếu nguồn |
| Đơn vị chủ trì / phối hợp | Ai chịu trách nhiệm chính / cùng làm |
| Người thực hiện | Cán bộ cụ thể |
| Người giao | Mặc định = người tạo; **là người có quyền duyệt đóng** |
| Hạn + Mô tả hạn | Ngày hạn + câu gốc ("trong quý II") |
| Độ mật | Không được thấp hơn văn bản nguồn |

---

## 4. Vòng đời & các nút

Trạng thái chạy trên thanh phía trên form:

```
Mới ──▶ Đang thực hiện ──▶ Chờ duyệt ──▶ Hoàn thành
                 ▲              │
                 └── Trả lại ◀──┘         (Tạm dừng: rẽ nhánh bất kỳ lúc nào)
```

| Nút | Ai bấm | Kết quả |
|---|---|---|
| **Bắt đầu** | Người thực hiện | Mới → Đang thực hiện |
| **Gửi duyệt** | Người thực hiện | Đang thực hiện → Chờ duyệt |
| **Duyệt đóng** | **Chỉ người giao** | Chờ duyệt → Hoàn thành |
| **Trả lại** | Người giao | Chờ duyệt → Đang thực hiện (kèm lý do ở khung trao đổi) |
| **Tạm dừng** | — | → Tạm dừng |

> **"Quá hạn" không phải một trạng thái bạn bấm.** Hệ thống tự suy ra
> (hạn đã qua và chưa hoàn thành) và hiển thị **cờ đỏ "Quá hạn"** trên form +
> tô đỏ dòng trong danh mục. Cờ này được làm mới **mỗi ngày**.

---

## 5. Báo cáo kết quả (T-12)

Trong form nhiệm vụ, mở tab **"Báo cáo kết quả"** → thêm dòng:

- **Nội dung báo cáo** (mô tả kết quả),
- **File minh chứng** (đính kèm nhiều file),
- Người và thời điểm báo cáo tự ghi nhận.

Một nhiệm vụ có thể có **nhiều lần báo cáo** (lưu lịch sử). Báo cáo **thừa hưởng
độ mật** của nhiệm vụ — báo cáo của nhiệm vụ mật cũng bị chặn với người không đủ
độ mật.

---

## 6. Nhắc việc & cảnh báo (tự động)

Chạy nền, không cần thao tác:

- **Nhắc hạn (hằng ngày):** trước hạn **7 / 3 / 1 ngày** và khi **quá hạn**, hệ
  thống tạo **hoạt động nhắc** cho *người thực hiện* + gửi email. Mỗi mốc nhắc
  **một lần**, không spam.
- **Cảnh báo lãnh đạo (hằng tuần, thứ Hai):** tổng hợp **danh sách quá hạn theo
  đơn vị**, gửi email cho nhóm **Chánh VP** (T-14).

> Cấu hình được ở *Cài đặt → Kỹ thuật → Tác vụ định kỳ (cron)*: hai tác vụ tên
> "Nhiệm vụ: nhắc hạn…" và "Nhiệm vụ: cảnh báo lãnh đạo…".

---

## 7. Danh mục & tìm kiếm (T-08)

App **Nhiệm vụ → Danh mục nhiệm vụ**:

- **Xem dạng Danh sách** (đỏ = quá hạn) hoặc **Kanban** (cột theo trạng thái —
  kéo thả để đổi trạng thái).
- **Bộ lọc nhanh:** Quá hạn · Chờ duyệt · Của tôi · Chưa hoàn thành.
- **Tìm theo:** tên, văn bản nguồn, đơn vị, người thực hiện.
- **Nhóm theo:** Đơn vị · Trạng thái · Độ mật · Người thực hiện.

---

## 8. Bảng điều khiển (T-15)

App **Bảng điều khiển → Tổng quan nhiệm vụ**: 4 ô đếm nhanh —
**Tổng nhiệm vụ**, **Quá hạn** (đỏ), **Chờ duyệt** (cam), **Chưa hoàn thành**.
Bấm vào ô để mở đúng danh sách đằng sau con số.

---

## 9. Ánh xạ tính năng MVP

| Mã | Tính năng | Ở đâu trong hệ thống |
|---|---|---|
| T-05 | Màn duyệt/tạo từ văn bản | Nút "Nhiệm vụ" trên form văn bản |
| T-06 | Sửa & bổ sung thủ công | Form nhiệm vụ |
| T-07 | Liên kết nguồn | Trường Văn bản nguồn + Đoạn trích |
| T-08 | Danh mục + lọc | Danh mục nhiệm vụ |
| T-09 | Trạng thái | Thanh trạng thái + nút |
| T-11 | Nhắc việc | Cron nhắc hạn |
| T-12 | Báo cáo kết quả | Tab Báo cáo kết quả |
| T-13 | Duyệt hoàn thành | Nút Duyệt đóng (người giao) |
| T-14 | Cảnh báo lãnh đạo | Cron hàng tuần → Chánh VP |
| T-15 | Bảng theo dõi | Dashboard Tổng quan nhiệm vụ |

---

## 10. Giới hạn hiện tại (làm sau)

- **Bóc tách tự động bằng AI (T-01→T-04):** hiện **tạo tay**. Khi có hạ tầng AI,
  AI sẽ **điền sẵn** nội dung/đơn vị/hạn vào đúng màn hình này để cán bộ xác nhận.
- **Nhiệm vụ con (T-10, P1):** chưa có — hoãn.
