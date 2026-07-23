# Thiết kế: Seed dữ liệu phân cấp tổ chức demo (aidt_org + aidt_org_demo)

**Ngày:** 2026-07-23
**Mục tiêu:** Seed dữ liệu demo chứng minh Odoo đáp ứng N-02 (cây tổ chức), N-03 (RBAC theo vai trò), N-05 (phân quyền theo phạm vi) trong `docs/mvp.md`, theo kịch bản kiểm thử đóng vai O-03.

## Quyết định kiến trúc

Hai module tách biệt (phương án A đã duyệt):

- **`addons/aidt_org`** — core, production-ready: model, security, views. Là skeleton cho module văn bản thật sau này.
- **`addons/aidt_org_demo`** — chỉ chứa data seed (`noupdate="1"`), depends `aidt_org`. Gỡ demo = uninstall module này, core còn nguyên.

Không dùng cơ chế `demo/` chuẩn của Odoo vì DB tạo bởi docker compose prod không bật demo data.

## Cấu trúc thư mục

```
addons/aidt_org/
├── __manifest__.py               # depends: hr, mail
├── models/
│   ├── __init__.py
│   ├── hr_department.py          # + unit_type
│   └── aidt_document.py
├── security/
│   ├── aidt_org_groups.xml       # privilege + 6 groups
│   ├── ir.model.access.csv
│   └── aidt_org_rules.xml        # 2 ir.rule
├── views/
│   ├── aidt_document_views.xml   # list/form + menu "Văn bản"
│   └── hr_department_views.xml   # thêm unit_type vào form
└── tests/
    ├── __init__.py
    └── test_document_scope.py    # TransactionCase, 4 kịch bản O-03

addons/aidt_org_demo/
├── __manifest__.py               # depends: aidt_org
└── data/
    ├── org_departments.xml       # 14 hr.department (noupdate)
    ├── org_employees_users.xml   # 20 hr.employee + 20 res.users (noupdate)
    └── org_documents.xml         # ~15 aidt.document (noupdate)
```

## Data model

### `hr.department` (inherit)

- `unit_type`: Selection `[('cap_uy', 'Cấp ủy'), ('ban', 'Ban'), ('phong', 'Phòng')]` — lấp khoảng trống "Odoo không phân biệt loại đơn vị" của N-02. Chưa có ràng buộc cấp cha-con (YAGNI, thêm sau nếu cần).

### `aidt.document` (model mới, `_inherit = ['mail.thread']`)

| Field | Kiểu | Ghi chú |
|---|---|---|
| `name` | Char, required | Trích yếu |
| `reference` | Char | Số/ký hiệu (vd `01-CV/VPTU`) |
| `department_id` | Many2one `hr.department`, required | Đơn vị sở hữu — trục phân quyền N-05 |
| `shared_user_ids` | Many2many `res.users` | Chia sẻ đích danh |
| `doc_type` | Selection: cong_van / bao_cao / ke_hoach / quyet_dinh | |
| `date` | Date | Ngày ban hành |
| `state` | Selection: draft / issued / archived, default draft | Vòng đời rút gọn V-05 |

## RBAC (N-03)

`res.groups.privilege` "Quản lý văn bản". 6 groups, kế thừa qua `implied_ids`:

```
group_chuyen_vien ← group_van_thu ← group_chanh_vp ← group_pho_bi_thu ← group_bi_thu ← group_aidt_admin
```

| Group | Gán cho | Quyền cộng thêm |
|---|---|---|
| `group_chuyen_vien` | mọi chuyên viên | đọc + soạn dự thảo trong phạm vi |
| `group_van_thu` | `vanthu` | đăng ký/cấp số VB đơn vị |
| `group_chanh_vp` | `chanhvp`, trưởng ban, trưởng phòng | duyệt, ban hành |
| `group_pho_bi_thu` | `photbt` | — (danh nghĩa vai trò) |
| `group_bi_thu` | `bithu` | — |
| `group_aidt_admin` | admin | toàn quyền, bypass phạm vi |

**ACL `aidt.document`:** chuyên viên trở lên read/write/create; unlink chỉ `group_aidt_admin`.

## Record rules (N-05)

```python
# Rule 1 — group_chuyen_vien, perm read/write/create/unlink:
['|', ('department_id', 'child_of', user.employee_id.department_id.ids),
      ('shared_user_ids', 'in', [user.id])]

# Rule 2 — group_aidt_admin: [(1, '=', 1)]
```

Phạm vi tự nở theo vị trí trên cây tổ chức: CV thấy phòng mình, Chánh VP thấy nhánh Văn phòng (`child_of`), Bí thư ở root thấy tất cả. User không có employee/department → chỉ thấy VB được chia sẻ (mặc định an toàn).

## Dữ liệu seed

### Cây đơn vị (14 `hr.department`)

```
Tỉnh ủy Demo                        [cap_uy]
├── Văn phòng Tỉnh ủy               [ban]
│   ├── Phòng Tổng hợp              [phong]
│   ├── Phòng Hành chính – Lưu trữ  [phong]
│   └── Phòng Quản trị              [phong]
├── Ban Tổ chức Tỉnh ủy             [ban]
│   ├── Phòng Tổ chức – Cán bộ      [phong]
│   └── Phòng Cơ sở đảng – Đảng viên [phong]
├── Ban Tuyên giáo Tỉnh ủy          [ban]
│   ├── Phòng Tuyên truyền          [phong]
│   └── Phòng Lý luận chính trị     [phong]
└── Ủy ban Kiểm tra Tỉnh ủy         [ban]
    ├── Phòng Nghiệp vụ 1           [phong]
    └── Phòng Nghiệp vụ 2           [phong]
```

### Nhân sự & users (20 người)

Mỗi người 1 `hr.employee` (manager chain qua `parent_id`) + 1 `res.users` gắn qua `user_id`. Mật khẩu chung `demo2026`.

| Login | Họ tên | Vai trò | Đơn vị | Group |
|---|---|---|---|---|
| `bithu` | Nguyễn Văn An | Bí thư | Tỉnh ủy | bi_thu |
| `photbt` | Trần Thị Bình | Phó Bí thư TT | Tỉnh ủy | pho_bi_thu |
| `chanhvp` | Lê Minh Châu | Chánh Văn phòng | VP Tỉnh ủy | chanh_vp |
| `phochanhvp` | Phạm Quốc Dũng | Phó Chánh VP | VP Tỉnh ủy | chanh_vp |
| `tp.tonghop` | Hoàng Thu Em | Trưởng phòng | P. Tổng hợp | chanh_vp |
| `cv.tonghop1` | Vũ Văn Phú | Chuyên viên | P. Tổng hợp | chuyen_vien |
| `cv.tonghop2` | Đỗ Thị Giang | Chuyên viên | P. Tổng hợp | chuyen_vien |
| `vanthu` | Bùi Thị Hoa | Văn thư | P. HC–Lưu trữ | van_thu |
| `tp.hanhchinh` | Ngô Đức Inh | Trưởng phòng | P. HC–Lưu trữ | chanh_vp |
| `tp.quantri` | Đặng Văn Khang | Trưởng phòng | P. Quản trị | chanh_vp |
| `truongban.tc` | Cao Thị Lan | Trưởng Ban | Ban Tổ chức | chanh_vp |
| `tp.tccb` | Lý Văn Minh | Trưởng phòng | P. TC–Cán bộ | chanh_vp |
| `cv.tccb` | Phan Thị Nga | Chuyên viên | P. TC–Cán bộ | chuyen_vien |
| `cv.csd` | Trịnh Văn Oanh | Chuyên viên | P. Cơ sở đảng | chuyen_vien |
| `truongban.tg` | Mai Quốc Phong | Trưởng Ban | Ban Tuyên giáo | chanh_vp |
| `cv.tuyentruyen` | Chu Thị Quỳnh | Chuyên viên | P. Tuyên truyền | chuyen_vien |
| `cv.lyluan` | Tạ Văn Sơn | Chuyên viên | P. Lý luận CT | chuyen_vien |
| `chunhiem.ubkt` | Dương Thị Tâm | Chủ nhiệm UBKT | UB Kiểm tra | chanh_vp |
| `cv.nv1` | Hồ Văn Út | Chuyên viên | P. Nghiệp vụ 1 | chuyen_vien |
| `cv.nv2` | Lưu Thị Vân | Chuyên viên | P. Nghiệp vụ 2 | chuyen_vien |

Admin dùng account admin sẵn có, gán thêm `group_aidt_admin`.

### Văn bản mẫu (~15 `aidt.document`)

Phân bổ: 2 Tỉnh ủy, 4 nhánh Văn phòng, 3 Ban Tổ chức, 3 Ban Tuyên giáo, 3 UB Kiểm tra. Trong đó 2 VB có `shared_user_ids` chéo đơn vị (vd kế hoạch của Ban TC chia sẻ cho `cv.tonghop1`) để demo vế "+ văn bản được chia sẻ".

## Kịch bản demo (khớp O-03)

1. Login `cv.tonghop1` → chỉ thấy VB P. Tổng hợp + VB được chia sẻ; tìm kiếm không lộ tiêu đề VB của UBKT.
2. Login `chanhvp` → thấy VB toàn nhánh Văn phòng (3 phòng con — chứng minh `child_of`).
3. Login `bithu` → thấy toàn bộ.
4. `vanthu` tạo VB gán cho đơn vị ngoài phạm vi → `AccessError`.
5. Nhân sự → Phòng ban: cây `complete_name` 3 cấp (N-02); Settings → Users: ma trận vai trò (N-03).

## Kiểm chứng tự động

`aidt_org/tests/test_document_scope.py` — `TransactionCase` tự tạo fixture tối giản (không phụ thuộc `aidt_org_demo`), chạy 4 kịch bản trên bằng `with_user()`:

- CV chỉ thấy VB đơn vị mình + VB được chia sẻ.
- Lãnh đạo đơn vị thấy VB toàn nhánh con.
- User cấp root thấy tất cả.
- Create VB cho đơn vị ngoài phạm vi bị `AccessError`.

## Cách chạy

```bash
docker compose -f docker-compose.dev.yml up -d
# cài 2 module (addons path đã trỏ vào ./addons):
odoo -d <db> -i aidt_org,aidt_org_demo
# test:
odoo -d <db> --test-tags /aidt_org --stop-after-init
```

(Lệnh chính xác theo entrypoint của compose dev sẽ chốt ở bước plan.)

## Ngoài phạm vi

- Độ mật 4 cấp (N-04), ủy quyền tạm thời (N-06), luồng trình ký (D-13), ràng buộc loại cha-con của `unit_type`.
- Không sửa module `hr` core; mọi thứ nằm trong 2 addon mới.
