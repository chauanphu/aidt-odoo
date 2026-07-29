# Demo credentials — `aidt_demo`

> **Local demo database only.** These accounts exist solely in the `aidt_demo`
> dev database seeded by `addons/aidt_org_demo/data/org_employees_users.xml`.
> They are throwaway demo identities with a shared, publicly-known password —
> never reuse these logins, passwords, or this file for staging or production.
>
> This file is listed in `.gitignore` so it is not committed. Remove that entry
> only if you have decided a plaintext credential file belongs in the repo.

**Server:** http://localhost:8069  **Database:** `aidt_demo`

Verified working against the running dev stack on 2026-07-29.

## Administrator

| Login | Password | Notes |
|---|---|---|
| `admin` | `admin` | uid 2, system administrator, clearance 3 |

The **database-manager master password** is a separate secret — it is not a
login. It comes from `ODOO_ADMIN_PASSWD` in `.env`; read it there rather than
copying it here.

## Demo users

All 20 accounts below share the password **`demo2026`**.

| Login | Name | Chức vụ | Đơn vị | Nhóm quyền | Mức mật |
|---|---|---|---|---|---|
| `bithu` | Nguyễn Văn An | Bí thư | Tỉnh ủy Demo | `group_bi_thu` | 3 |
| `photbt` | Trần Thị Bình | Phó Bí thư Thường trực | Tỉnh ủy Demo | `group_pho_bi_thu` | 3 |
| `chanhvp` | Lê Minh Châu | Chánh Văn phòng | Văn phòng Tỉnh ủy | `group_chanh_vp` | 2 |
| `phochanhvp` | Phạm Quốc Dũng | Phó Chánh Văn phòng | Văn phòng Tỉnh ủy | `group_chanh_vp` | 2 |
| `tp.tonghop` | Hoàng Thu Em | Trưởng phòng Tổng hợp | Phòng Tổng hợp | `group_chanh_vp` | 1 |
| `cv.tonghop1` | Vũ Văn Phú | Chuyên viên | Phòng Tổng hợp | `group_chuyen_vien` | 0 |
| `cv.tonghop2` | Đỗ Thị Giang | Chuyên viên | Phòng Tổng hợp | `group_chuyen_vien` | 0 |
| `tp.hanhchinh` | Ngô Đức Inh | Trưởng phòng Hành chính – Lưu trữ | Phòng Hành chính – Lưu trữ | `group_chanh_vp` | 1 |
| `vanthu` | Bùi Thị Hoa | Văn thư | Phòng Hành chính – Lưu trữ | `group_van_thu` | 1 |
| `tp.quantri` | Đặng Văn Khang | Trưởng phòng Quản trị | Phòng Quản trị | `group_chanh_vp` | 1 |
| `truongban.tc` | Cao Thị Lan | Trưởng Ban Tổ chức | Ban Tổ chức Tỉnh ủy | `group_chanh_vp` | 2 |
| `tp.tccb` | Lý Văn Minh | Trưởng phòng Tổ chức – Cán bộ | Phòng Tổ chức – Cán bộ | `group_chanh_vp` | 1 |
| `cv.tccb` | Phan Thị Nga | Chuyên viên | Phòng Tổ chức – Cán bộ | `group_chuyen_vien` | 1 |
| `cv.csd` | Trịnh Văn Oanh | Chuyên viên | Phòng Cơ sở đảng – Đảng viên | `group_chuyen_vien` | 0 |
| `truongban.tg` | Mai Quốc Phong | Trưởng Ban Tuyên giáo | Ban Tuyên giáo Tỉnh ủy | `group_chanh_vp` | 2 |
| `cv.tuyentruyen` | Chu Thị Quỳnh | Chuyên viên | Phòng Tuyên truyền | `group_chuyen_vien` | 0 |
| `cv.lyluan` | Tạ Văn Sơn | Chuyên viên | Phòng Lý luận chính trị | `group_chuyen_vien` | 0 |
| `chunhiem.ubkt` | Dương Thị Tâm | Chủ nhiệm Ủy ban Kiểm tra | Ủy ban Kiểm tra Tỉnh ủy | `group_chanh_vp` | 3 |
| `cv.nv1` | Hồ Văn Út | Chuyên viên | Phòng Nghiệp vụ 1 | `group_chuyen_vien` | 2 |
| `cv.nv2` | Lưu Thị Vân | Chuyên viên | Phòng Nghiệp vụ 2 | `group_chuyen_vien` | 2 |

Group names are relative to the `aidt_org` module (e.g. `aidt_org.group_bi_thu`).

## Clearance levels — applied 2026-07-29

The **Mức mật** column above now matches the live `aidt_demo` database: all 20
demo users were verified against the seed XML with **0 mismatches**.

These values were applied by direct SQL, **not** by the module install. The seed
file `org_employees_users.xml` is wrapped in `<data noupdate="1">`, so once the
`res.users` records exist Odoo will not rewrite their fields on upgrade — the
clearance values declared there had never taken effect (every demo user sat at
`clearance_level = 0`, making document-secrecy rules untestable).

**Consequence:** the fix lives only in this database. It will be lost if
`aidt_demo` is rebuilt from scratch, and a fresh install elsewhere will show the
same all-zero state. Re-apply with:

```sql
-- run against aidt_demo
UPDATE res_users u SET clearance_level = v.clr
FROM (VALUES
  ('bithu',3),('photbt',3),('chanhvp',2),('phochanhvp',2),('tp.tonghop',1),
  ('cv.tonghop1',0),('cv.tonghop2',0),('tp.hanhchinh',1),('vanthu',1),
  ('tp.quantri',1),('truongban.tc',2),('tp.tccb',1),('cv.tccb',1),('cv.csd',0),
  ('truongban.tg',2),('cv.tuyentruyen',0),('cv.lyluan',0),('chunhiem.ubkt',3),
  ('cv.nv1',2),('cv.nv2',2)
) AS v(login, clr)
WHERE u.login = v.login;
```

For a durable fix, the clearance assignment should move out of the
`noupdate="1"` block — or into a post-install hook — so a fresh install seeds it
correctly.

## Source of truth

- User/password/clearance definitions: `addons/aidt_org_demo/data/org_employees_users.xml`
- Passwords are stored in `res_users.password` as PBKDF2 hashes and cannot be
  read back out of the database — the plaintext values above come from the seed
  file, confirmed by authenticating against `/web/session/authenticate`.
