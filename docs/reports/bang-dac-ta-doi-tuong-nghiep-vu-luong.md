# BÁO CÁO ĐẶC TẢ CHI TIẾT: ĐỐI TƯỢNG, NGHIỆP VỤ VÀ LUỒNG VĂN BẢN (AIDT-ODOO)

> **Cập nhật ngày:** 2026-07-30  
> **Hệ thống:** Quản lý Văn bản Điện tử & Trợ lý AI Nội bộ Cơ quan Tỉnh ủy (`aidt-odoo`)

---

## I. DÂN MỤC ĐỐI TƯỢNG VÀ NHÓM QUYỀN (ACTORS & ROLES)

Hệ thống phân chia 6 nhóm vai trò người dùng (Security Groups) gắn liền với mô hình tổ chức của cơ quan Đảng / Tỉnh ủy:

| STT | Tên Vai trò (Actor) | Mã Nhóm Quyền (Security Group) | Mức Mật tối đa | Ví dụ Tài khoản | Vai trò Cốt lõi |
|---|---|---|---|---|---|
| **1** | **Bí thư Tỉnh ủy** | `aidt_org.group_bi_thu` | Level 3 (Tuyệt mật) | `bithu` (Nguyễn Văn An) | Người đứng đầu: Bút phê chỉ đạo, Ký số ban hành |
| **2** | **Phó Bí thư Tỉnh ủy** | `aidt_org.group_pho_bi_thu` | Level 3 (Tuyệt mật) | `photbt` (Trần Thị Bình) | Lãnh đạo Thường trực: Bút phê chỉ đạo, Ký số |
| **3** | **Chánh Văn phòng** | `aidt_org.group_chanh_vp` | Level 2 (Tối mật) | `chanhvp` (Lê Minh Châu) | Tổng tham mưu: Duyệt trình ký, Ký nháy, Đôn đốc tiến độ |
| **4** | **Trưởng phòng** | `aidt_org.group_truong_phong` | Level 1 (Mật) | `tp.tonghop` (Hoàng Thu Em) | Lãnh đạo phòng: Duyệt cấp phòng đối với văn bản đi |
| **5** | **Chuyên viên** | `aidt_org.group_chuyen_vien` | Level 0 (Thường) | `cv.tonghop1` (Vũ Văn Phú) | Người thực thi: Soạn dự thảo, Kiểm thể thức, Xử lý nhiệm vụ |
| **6** | **Văn thư** | `aidt_org.group_van_thu` | Level 1 (Mật) | `vanthu` (Bùi Thị Hoa) | Quản lý sổ sách: Đăng ký sổ đến, Cấp số đi, Phát hành |

---

## II. MA TRẬN PHÂN QUYỀN VÀ NGHIỆP VỤ THEO TỪNG ĐỐI TƯỢNG

```
+---------------------------------------------------------------------------------------------------------+
|                                    MA TRẬN NÚT BẤM THAO TÁC (ACTION BUTTONS)                            |
+-------------------+- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
| Nút bấm / Tác vụ  | Chuyên viên  | Trưởng phòng | Chánh VP     | Bí thư / Phó BT | Văn thư      | Admin |
+-------------------+--------------+--------------+--------------+-----------------+--------------+-------+
| [Đăng ký Sổ đến]  | ❌           | ❌           | ❌           | ❌              | ✅           | ✅    |
| [Trình lãnh đạo]  | ❌           | ❌           | ✅           | ❌              | ✅           | ✅    |
| [Bút phê + Giao]  | ❌           | ❌           | ✅           | ✅              | ❌           | ✅    |
| [Duyệt hoàn thành]| ❌           | ❌           | ✅           | ✅              | ❌           | ✅    |
+-------------------+--------------+--------------+--------------+-----------------+--------------+-------+
| [Kiểm tra thể thức| ✅           | ✅           | ✅           | ✅              | ✅           | ✅    |
| [Trình Trưởng phòng| ✅          | ❌           | ❌           | ❌              | ❌           | ✅    |
| [TP Duyệt/Trả về] | ❌           | ✅           | ❌           | ❌              | ❌           | ✅    |
| [CVP Duyệt/Trả về]| ❌           | ❌           | ✅           | ❌              | ❌           | ✅    |
| [LĐ Duyệt/Trả về] | ❌           | ❌           | ❌           | ✅              | ❌           | ✅    |
| [Ký số Ban hành]  | ❌           | ❌           | ❌           | ✅              | ❌           | ✅    |
| [Cấp số & Phát hành| ❌          | ❌           | ❌           | ❌              | ✅           | ✅    |
+-------------------+--------------+--------------+--------------+-----------------+--------------+-------+
```

---

## III. CHI TIẾT LUỒNG NGHIỆP VỤ VĂN BẢN ĐẾN (INCOMING FLOW)

```
[Công văn bên ngoài]
        │
        ▼
 (1) VĂN THƯ (`vanthu`)
   • Đăng ký sổ đến ➔ Cấp Số Đến (ir.sequence tự động)
   • Trạng thái: `tiep_nhan` ➔ `da_dang_ky`
        │
        ▼
 (2) VĂN THƯ / CHÁNH VP (`chanhvp`)
   • Kiểm tra tệp scan ➔ Trình Lãnh đạo
   • Trạng thái: `da_dang_ky` ➔ `trinh_lanh_dao`
        │
        ▼
 (3) BÍ THƯ / PHÓ BÍ THƯ / CHÁNH VP (`bithu` / `photbt` / `chanhvp`)
   • Nhập Ý kiến Bút phê chỉ đạo & Chọn Đơn vị chủ trì
   • Bấm [Bút phê + Giao việc]
   • Trạng thái: `trinh_lanh_dao` ➔ `dang_xu_ly`
   • ⚡ HỆ THỐNG TỰ ĐỘNG TẠO NHIỆM VỤ (`aidt.task`) liên kết với Văn bản
        │
        ▼
 (4) CHUYÊN VIÊN ĐƠN VỊ CHỦ TRÌ (`cv.tonghop1`)
   • Nhận Nhiệm vụ ➔ Cập nhật tiến độ ➔ Hoàn thành
        │
        ▼
 (5) LÃNH ĐẠO / CHÁNH VP
   • Duyệt kết quả ➔ Bấm [Duyệt hoàn thành]
   • Trạng thái: `dang_xu_ly` ➔ `hoan_thanh`
```

---

## IV. CHI TIẾT LUỒNG NGHIỆP VỤ VĂN BẢN ĐI (OUTGOING FLOW)

```
 (1) CHUYÊN VIÊN (`cv.tonghop1`)
   • Soạn dự thảo `.docx` ➔ Upload file
   • Bấm [Kiểm tra thể thức] ➔ Soi lỗi Quy định 66-QĐ/TW
   • Bấm [Trình Trưởng phòng] ➔ Trạng thái: `draft` ➔ `cho_duyet_tp`
        │
        ▼
 (2) TRƯỞNG PHÒNG (`tp.tonghop`)
   • Kiểm tra nội dung ➔ Bấm [TP Duyệt]
   • Trạng thái: `cho_duyet_tp` ➔ `cho_duyet_cvp` (hoặc Trả về nháp)
        │
        ▼
 (3) CHÁNH VĂN PHÒNG (`chanhvp`)
   • Kiểm tra thể thức lần cuối & Ký nháy ➔ Bấm [CVP Duyệt]
   • Trạng thái: `cho_duyet_cvp` ➔ `cho_duyet_lanh_dao` (hoặc Trả về cho TP)
        │
        ▼
 (4) BÍ THƯ / PHÓ BÍ THƯ (`bithu` / `photbt`)
   • Xem bản chốt ➔ Bấm [Lãnh đạo Duyệt] ➔ Bấm [Ký số]
   • Trạng thái: `cho_duyet_lanh_dao` ➔ `cho_ky` ➔ `cho_cap_so`
        │
        ▼
 (5) VĂN THƯ (`vanthu`)
   • Bấm [Cấp số & Phát hành] ➔ Cấp Số Ký hiệu chính thức (ir.sequence)
   • Trạng thái: `cho_cap_so` ➔ `da_ban_hanh` ➔ Lưu Sổ Văn bản đi
```

---

## V. TÍNH NĂNG BẢO MẬT & TRỢ LÝ AI HỖ TRỢ

1. **Bảo mật 4 Mức Mật (Record Rules)**:
   - Người dùng chỉ nhìn thấy các văn bản có `secrecy_level <= user.clearance_level`.
   - Chuyên viên (`Level 0`) hoàn toàn không thấy văn bản Mật / Tối mật / Tuyệt mật.

2. **Khóa chỉnh sửa Form (Field Readonly)**:
   - Thông tin cơ bản tự động khóa `readonly="1"` khi văn bản chuyển trạng thái khỏi `draft`/`tiep_nhan`.
   - Khối Bút phê chỉ sửa được khi ở trạng thái `trinh_lanh_dao`.

3. **Trợ lý AI**:
   - Tự động bóc tách thực thể & metadata.
   - Kiểm tra thể thức 66-QĐ/TW (khoanh vùng lỗi trực quan).
   - Tìm kiếm kết hợp (Keyword + Vector Search).
