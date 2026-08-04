# Thiết kế Kỹ thuật: Module Ký số Điện tử PAdES & Quy trình 2 bước Văn bản đi (`aidt_sign`)

**Ngày tạo**: 04-08-2026  
**Trạng thái**: Đã phê duyệt (Approved)  
**Module liên quan**: `aidt_sign` (mới), `aidt_vanban_di`, `aidt_dms`

---

## 1. Mục đích & Tổng quan (Goal & Overview)

Hệ thống AIDT Odoo hiện tại đang dùng hàm `action_sign` dạng *placeholder MVP* (chỉ cập nhật trạng thái database mà chưa thực hiện ký số mật mã). Spec này thiết kế module mới `aidt_sign` nhằm cung cấp tính năng **Ký số điện tử chuẩn PAdES (PDF Advanced Electronic Signature)** tuân thủ quy định Nghị định 30/2020/NĐ-CP và tiêu chuẩn kỹ thuật Việt Nam.

### Các tính năng cốt lõi:
1. **Chuyển đổi tự động (`.docx` ➔ `.pdf`)**: Khi trình duyệt/ký, hệ thống tự động chuyển đổi file dự thảo Word sang PDF thông qua LibreOffice Headless CLI.
2. **Ký số PAdES 2 bước (Incremental Multi-Signing)**:
   - **Bước 1 (Lãnh đạo ký cá nhân)**: Nút `[ Ký số & Duyệt ]` chèn hình ảnh chữ ký tay cá nhân vào đúng khu vực "Người ký" và mã hoá chữ ký số PAdES #1.
   - **Bước 2 (Văn thư đóng dấu & Ban hành)**: Nút `[ Cấp số & Ban hành ]` tự động chèn Số/Ngày phát hành lên file PDF, chèn hình ảnh con dấu đỏ cơ quan và thực hiện chữ ký số PAdES #2 (dấu tổ chức) cập nhật gia tăng (Incremental Update).
3. **Quản lý Chứng thư số PKCS#12 (`.p12`/`.pfx`)**: Lưu trữ và quản lý chứng thư số cá nhân/tổ chức kèm mật khẩu giải mã.

---

## 2. Kiến trúc & Cấu trúc Module (`custom-addons/aidt_sign`)

### 2.1. Cấu trúc thư mục module:
```text
custom-addons/aidt_sign/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── aidt_sign_certificate.py   # Model quản lý file chứng thư .p12/.pfx
│   ├── aidt_sign_log.py           # Nhật ký lịch sử ký số & SHA256 digest
│   └── res_users.py               # Thêm quan hệ chứng thư cá nhân & ảnh chữ ký tươi
├── services/
│   ├── __init__.py
│   ├── pdf_converter.py           # Service gọi LibreOffice CLI convert docx -> pdf
│   └── pades_signer.py            # Service wrapper pyHanko chèn visual stamp & ký PKCS#7
├── views/
│   ├── aidt_sign_certificate_views.xml
│   └── res_users_views.xml
└── security/
    ├── ir.model.access.csv
    └── sign_groups.xml
```

### 2.2. Phụ thuộc (Dependencies):
- **Python packages** (`requirements.txt`):
  - `pyhanko[pypdf]>=0.20.0`
  - `cryptography>=41.0.0`
  - `pillow>=10.0.0`
- **System Packages** (`Dockerfile`):
  - `libreoffice-writer`
  - `fonts-liberation` (bảo đảm font chữ Times New Roman/Arial hiển thị chuẩn khi convert)

---

## 3. Chi tiết Xử lý Kỹ thuật (Technical Implementation Specs)

### 3.1. Engine Chuyển đổi `.docx` ➔ `.pdf` (`pdf_converter.py`)
- Sử dụng subprocess gọi `soffice --headless --convert-to pdf --outdir <tmp_dir> <input_file.docx>`.
- Xử lý timeout (tối đa 30s) và dọn dẹp file tạm sau khi convert.
- Nhận diện nếu file đính kèm đã là `.pdf` thì bỏ qua bước convert.

### 3.2. Engine Ký số PAdES & Visual Stamp (`pades_signer.py`)
- **Thư viện chính**: `pyhanko.pdf_utils` và `pyhanko.sign`.
- **Chế độ Ký**: `subfilter = adbe.pkcs7.detached` hoặc `ETSI.CAdES.detached` (Chuẩn PAdES).
- **Incremental Update**: Khi ký bước 2 (Văn thư), pyHanko thực hiện append revision mới vào PDF để giữ nguyên tính toàn vẹn chữ ký 1 của Lãnh đạo.
- **Visual Stamp Positioning**:
  - Chữ ký Lãnh đạo: Vị trí góc phải bên dưới trang cuối văn bản (trùng khu vực chức vụ/tên người ký).
  - Con dấu Văn thư: Vị trí trùm 1/3 chữ ký Lãnh đạo về phía bên trái hoặc góc trên bên trái (bên cạnh số ký hiệu).

---

## 4. Tích hợp Luồng Nghiệp vụ Văn bản đi (`aidt_vanban_di`)

### 4.1. Thay đổi Model `aidt.document`:
- **`action_sign()`**:
  1. Kiểm tra file đính kèm chính: Nếu là `.docx`, gọi `pdf_converter.py` tạo bản `.pdf`.
  2. Lấy chứng thư cá nhân của `env.user` từ `res.users`.
  3. Gọi `pades_signer.py` thực hiện ký Lãnh đạo (Visual Stamp ảnh chữ ký tay + PAdES #1).
  4. Lưu file `.pdf` đã ký mới làm attachment chính.
  5. Cập nhật `state = 'cho_cap_so'`, `nguoi_ky_id = env.uid`, `ngay_ky = now()`.
  6. Lưu nhật ký vào `aidt.sign.log`.

- **`action_issue_vbd()`**:
  1. Sinh `so_ky_hieu` từ sequence Odoo (`ir.sequence`).
  2. Điền chuỗi `so_ky_hieu` và ngày phát hành lên vị trí header của file PDF.
  3. Lấy chứng thư số cơ quan/tổ chức (Organization Certificate).
  4. Gọi `pades_signer.py` thực hiện ký đóng dấu (Visual Stamp con dấu đỏ + PAdES #2 Incremental).
  5. Cập nhật `state = 'da_ban_hanh'`, `date = today()`.
  6. Lưu nhật ký vào `aidt.sign.log`.

---

## 5. Quản lý Chứng thư số & Bảo mật

1. **Model `aidt.sign.certificate`**:
   - `name`: Tên chứng thư (vd: "Chứng thư Lãnh đạo - Nguyễn Văn A").
   - `cert_file`: Binary file `.p12`/`.pfx`.
   - `password`: Password mở chứng thư (được mã hoá lưu trữ).
   - `valid_from`, `valid_to`: Thời hạn chứng thư.
   - `owner_id`: User sở hữu (Many2one `res.users`).
   - `cert_type`: Selection (`personal` - Chữ ký cá nhân, `org` - Con dấu cơ quan).

2. **Bảo mật**:
   - Chỉ Admin hoặc chính User sở hữu mới có quyền truy cập file chứng thư `.p12` của mình.
   - File chứng thư số được mã hoá cơ sở dữ liệu.

---

## 6. Xử lý Lỗi & Cảnh báo (Error Handling)

| Tình huống lỗi | Hành vi xử lý của Hệ thống |
| :--- | :--- |
| Chưa có file đính kèm khi ký | Ném lỗi `UserError("Chưa có tệp dự thảo đính kèm để ký số.")` |
| LibreOffice convert lỗi/timeout | Ném lỗi `UserError("Không thể chuyển đổi file Word sang PDF. Vui lòng kiểm tra định dạng file.")` |
| User chưa cấu hình Chứng thư số | Ném lỗi `UserError("Bạn chưa được thiết lập Chứng thư số cá nhân. Vui lòng liên hệ Quản trị viên.")` |
| Mật khẩu chứng thư sai | Ném lỗi `UserError("Không thể giải mã Chứng thư số. Mật khẩu không chính xác.")` |
| PyHanko ký thất bại | Rollback transaction, trạng thái văn bản giữ nguyên, ném log chi tiết. |

---

## 7. Kế hoạch Kiểm thử (Test Plan)

1. **Test Unit Conversion**: Test `pdf_converter` chuyển đổi file `.docx` sang `.pdf`.
2. **Test Single Signature**: Test ký số 1 lần bằng `pyhanko` với file test `.p12` tự sinh (self-signed cert).
3. **Test Incremental Double Signature**: Test ký bước 1 (Lãnh đạo) ➔ ký bước 2 (Văn thư) và kiểm tra bằng `pyhanko validate` đảm bảo cả 2 chữ ký đều `VALID`.
4. **Test UI Integration**: Test luồng trên giao diện Odoo từ Chuyên viên ➔ Lãnh đạo ký ➔ Văn thư cấp số & ban hành.
