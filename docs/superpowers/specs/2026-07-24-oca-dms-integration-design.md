# Thiết kế: Tích hợp OCA DMS cho quản lý văn bản tập trung

Ngày: 2026-07-24
Trạng thái: Đã duyệt thiết kế, chờ viết plan
Liên quan MVP: N-04, N-05, N-10, S-09 (một phần), V-04, V-13

## 1. Bối cảnh & mục tiêu

Tích hợp module OCA DMS (Document Management System) làm kho lưu trữ tệp
tập trung cho `aidt.document`, đáp ứng:

- **N-10** — lưu file gốc (PDF/DOCX/ảnh scan) tập trung.
- **N-05 / N-04 / V-13** — quyền truy cập tệp phải bám theo quyền của văn bản,
  lọc ở tầng dữ liệu (không lộ cả tiêu đề tệp mật).
- **V-04** — xem trước PDF/DOCX ngay trên trình duyệt, không cần tải về.

### 1.1. Ràng buộc nguồn: OCA/dms chưa có bản 19.0 chính thức

Nhánh `19.0` của OCA/dms **chỉ chứa `.github/`** — chưa module nào được merge.
Toàn bộ code 19.0 đang nằm ở PR mở. Ta vendor từ fork của PR, **ghim commit**:

| PR | Module | Fork branch | Head SHA (ghim) | CI | Review |
|---|---|---|---|---|---|
| [#475](https://github.com/OCA/dms/pull/475) | `dms` (core) | `ledoent:19.0-mig-dms` | `171bd86a1b59c846fc41eb47d2bcdbe739363111` | ✅ 4/4 xanh | ⚠️ CHANGES_REQUESTED ×2 |
| [#483](https://github.com/OCA/dms/pull/483) | `dms_preview_pane` | `ledoent:19.0-add-dms_preview_pane` | `a0da22680638138e0d8364d70e315b480f40be48` | — | chưa review |
| [#484](https://github.com/OCA/dms/pull/484) | `dms_libreoffice_preview` | `ledoent:19.0-add-dms_libreoffice_preview` | `faf9c3eccd6e7afb303cc02ff66a591faceb9bf0` | — | chưa review |

**Rủi ro:** hai maintainer OCA (etobella, victoralmau) đã request changes trên #475,
nên schema `dms` **còn có thể đổi** trước khi merge. Thiết kế phải giảm tối đa
bề mặt phụ thuộc vào nội bộ `dms`.

## 2. Kiến trúc & vendoring

Năm addon; toàn bộ coupling dồn vào **một** module mới `aidt_dms`.

```
addons/
  dms/                      ← vendor @ 171bd86   (KHÔNG sửa)
  dms_preview_pane/         ← vendor @ a0da226   (KHÔNG sửa)
  dms_libreoffice_preview/  ← vendor @ faf9c3e   (KHÔNG sửa)
  aidt_org/                 ← có sẵn; + secrecy field & rule (N-04)
  aidt_dms/                 ← MỚI: cầu nối aidt.document ↔ dms
  aidt_org_demo/            ← có sẵn; + seed tệp mẫu
```

**Nguyên tắc bất biến giúp vendoring sống được: KHÔNG BAO GIỜ sửa thư mục vendor.**
Mọi thích ứng nằm trong `aidt_dms`. Khi #475 merge (có thể kèm thay đổi schema
theo yêu cầu maintainer), refresh = thay nguyên thư mục; blast radius = 1 module
ta sở hữu.

### 2.1. Trách nhiệm `aidt_dms` (toàn bộ bề mặt coupling)

- Sở hữu bản ghi cấu hình `dms.storage`: `save_type='attachment'`,
  `inherit_access_from_parent_record=True`.
- Tạo/xử lý 1 `dms.directory` cho mỗi `aidt.document`.
- Phơi `file_ids` trên form văn bản.
- Cung cấp lối vào xem tệp (xem §5).

Secrecy (N-04) đặt ở **`aidt_org`**, không phải `aidt_dms` — độ mật là thuộc tính
của văn bản, đúng dù có DMS hay không. Giữ `aidt_dms` thuần cầu nối, không luật
nghiệp vụ.

### 2.2. Cơ chế vendoring

- `addons_path = /opt/odoo/addons` là thư mục đơn; Dockerfile `COPY . /opt/odoo`.
  Module vendor thả vào là chạy — **không đổi path, không đổi build** (trừ
  LibreOffice ở §5).
- `addons/VENDORED.md` ghi: repo, branch, PR#, SHA, ngày, lệnh refresh — để pin
  có thể kiểm toán.

## 3. Mô hình dữ liệu & vòng đời

Với `save_type='attachment'`, ba `@api.constrains` trong `dms/models/directory.py`
ép hình dạng cây (không có tự do ở đây):

- `_check_storage_id_attachment_model_id` — mọi directory cần `model_id`;
  directory không phải root cần `res_id`.
- `_check_directory_parent` — root ⇒ không parent; non-root ⇒ phải có parent.
- `_check_directory_storage` — root phải có `storage_id`.

Kết quả: đúng **hai tầng**.

```
dms.storage  "Văn bản AIDT"  save_type=attachment, inherit_access_from_parent_record=True
  └── root dms.directory   is_root_directory=True, model_id=aidt.document, res_id=∅
        ├── dir  res_id=17   "01-NQ-TU — Nghị quyết…"   ← 1 cho mỗi văn bản
        │     ├── dms.file  quyet-dinh.pdf
        │     └── dms.file  phu-luc-01.docx
        └── dir  res_id=18   …
```

Vì sao `dms.file` **không** link trực tiếp tới record: `dms.file.directory_id` là
`required, ondelete=restrict`; `res_model`/`res_id` của file là **related readonly**
từ directory (`dms_file.py:189-194`). Record-link nằm trên `dms.directory`
(`res_model`, `res_id`, `model_id`), và directory giữ `file_ids` one2many.

### 3.1. Trường thêm vào `aidt.document`

| Trường | Kiểu | Module | Ghi chú |
|---|---|---|---|
| `directory_id` | m2o `dms.directory` | `aidt_dms` | readonly, xử lý ondelete tường minh |
| `file_ids` | o2m qua `directory_id.file_ids` | `aidt_dms` | related; form hiển thị cái này |
| `secrecy` | selection ×4 | `aidt_org` | N-04, required, default `thuong` |
| `secrecy_level` | integer 0–3 | `aidt_org` | computed từ `secrecy`, **store + index** |

### 3.2. Vòng đời

- **create** — `aidt.document.create` tạo luôn directory: `parent_id=<root>`,
  `model_id=aidt.document`, `res_id=<id mới>`, `name=_dir_name(doc)`.
- **`_dir_name(doc)`** — làm sạch tên hợp lệ với `dms.tools.file.check_name`,
  ưu tiên `reference`, fallback `name`, thêm id để duy nhất.
  **Gotcha bắt buộc xử lý:** `check_name` kiểm tra bằng cách thực sự
  `open(os.path.join(tmpdir, name))` → ký tự `/` ném `OSError` → tên không hợp lệ.
  Số/ký hiệu văn bản hầu như luôn có `/` (`01-NQ/TU`, `123/QĐ-UBND`). Phải thay
  `/` (và ký tự bị từ chối khác) trước khi đặt tên directory. **Có unit test riêng.**
- **write** — sửa `reference`/`name` thì đồng bộ lại tên directory (thẩm mỹ, tránh
  cây lệch khỏi sổ văn bản).
- **unlink** — `dms.file.directory_id` và `dms.directory.parent_id` đều
  `ondelete=restrict`, không cascade. **Chặn xóa văn bản còn tệp**, báo lỗi trỏ
  sang `state='archived'`. Văn bản phải lưu trữ, không hủy — khớp tư thế N-07
  ("log không sửa được").

## 4. Bảo mật (N-04 + inheritance)

### 4.1. Vì sao "inheritance only"

`dms/models/dms_security_mixin.py` override `_search` (L237) và `_check_access`
(L256) → lọc ở **tầng ORM** (đúng yêu cầu V-13/N-04). Có đúng hai chế độ,
**loại trừ lẫn nhau theo cấu tạo**:

| Chế độ | Điều kiện | Quyết định bởi |
|---|---|---|
| Inheritance | `save_type='attachment'` **và** `inherit_access_from_parent_record=True` | `record._filtered_access(op)` trên `aidt.document` — tức **ir.rule của aidt_org** |
| Access groups | `inherit_access_from_parent_record=False` | thành viên `dms.access.group` theo directory |

Hai nhánh `Domain.OR` (L201) nhưng một nhánh cần cờ `True`, nhánh kia `False` —
mỗi storage chỉ 1 nhánh áp dụng; không đường nào access-group nới rộng vượt ir.rule.

Chọn **inheritance only**: một mô hình quyền duy nhất, một chỗ để kiểm toán,
không rủi ro lệch đồng bộ. **Đánh đổi:** cây lưu trữ nghiệp vụ S-09
(Phông → Mục lục → Hồ sơ) **không** biểu diễn được như thư mục tự do trong chế độ
này — **nằm ngoài phạm vi** đợt này, cần thiết kế riêng.

Ghi chú kỹ thuật: root directory có `res_id=∅`. `_get_domain_by_inheritance` chèn
`[('res_model','=',model),('res_id','=',False)]` **sau khi** `model.check_access(op)`
đạt → root hiển thị cho ai có quyền model; chỉ các directory con bị lọc theo record.

### 4.2. N-04 — độ mật, và cái bẫy khi thêm luật

Odoo ghép ir.rule: rule **global** (không `groups`) thì **AND**; rule theo group
áp dụng cho user thì **OR**. Rule phạm vi đơn vị hiện tại gắn với
`group_chuyen_vien`. Nếu rule độ mật gắn vào **bất kỳ group nào**, nó sẽ **OR** với
rule đơn vị và **nới rộng** quyền — user đọc được văn bản đơn vị khác chỉ vì đủ
mức mật. **Sai hoàn toàn.**

→ Rule độ mật phải **global** (không group), để **AND** với mọi thứ đã có.

Mô hình mức mật:

| Trường | Ở | Kiểu |
|---|---|---|
| `secrecy` | `aidt.document` | selection `thuong`/`mat`/`toi_mat`/`tuyet_mat`, required, default `thuong` |
| `secrecy_level` | `aidt.document` | integer 0–3, computed từ `secrecy`, store + index |
| `clearance_level` | `res.users` | integer 0–3, default 0 |

Một rule global, không group:

```xml
<field name="domain_force">[('secrecy_level', '&lt;=', user.clearance_level)]</field>
```

Vì sao integer trên `res.users` chứ không 4 `res.groups`: 4 group mỗi cái cần rule
riêng → tái lập lỗi OR-nới-rộng; `implied_ids` sẽ trộn clearance với 6 group vai
trò hiện có. Clearance trực giao với vai trò (Chuyên viên ở vị trí nhạy cảm có thể
cần mức cao hơn Chánh VP) → tách trục riêng.

- `clearance_level` **không** trong `SELF_WRITEABLE_FIELDS` → user không tự nâng
  mức mình; ghi cần quyền Settings.
- Rule global nên **`group_aidt_admin` cũng chịu**. Rule admin
  `[(1,'=',1)]` là rule-theo-group → OR trên trục đơn vị nhưng vẫn AND với rule
  mật global. Admin được clearance **như dữ liệu** (`clearance_level=3`), không
  phải miễn trừ bằng code → đúng tinh thần N-08 (kể cả admin truy cập Tuyệt mật
  là giá trị field kiểm toán được).
- `shared_user_ids` thừa hưởng bảo đảm: chia sẻ không thể lộ vượt clearance người
  nhận, vì rule global AND sau bước kiểm tra share.

### 4.3. Test bảo mật (bắt buộc, không tin suông)

- user `clearance_level=1` đọc văn bản `tuyet_mat` → `AccessError`.
- cùng user gọi `env['dms.file'].search([])` → tệp thuộc văn bản đó **vắng mặt**
  trong kết quả, không chỉ "không đọc được" (V-13).
- user đơn vị A, clearance=3, **vẫn không** thấy văn bản đơn vị B — regression cho
  bẫy OR-nới-rộng.
- chia sẻ văn bản `toi_mat` cho user `clearance_level=0` → vẫn vô hình.

## 5. Xem trước & image Docker (V-04)

### 5.1. Điều bất ngờ: `dms` core đã có sẵn preview

`dms_preview_pane` không cần cho PDF. `dms` core (qua `preview_registry.esm.js`)
**đã ship handler** cho ảnh, PDF, text/JSON/XML, markdown, audio, video. → **PDF
xem trước không cần module thêm.** Chỉ DOCX/XLSX/ODT rơi xuống thẻ tải-về.

`dms_libreoffice_preview` lo phần còn lại: `soffice --headless --convert-to pdf`
qua `subprocess.run`, cap 60s, cache kết quả thành `ir.attachment` khóa theo
`write_date` → lần xem sau miễn phí.

### 5.2. Bề mặt xem trước: dùng list view DMS Files, không custom OWL trên form

`dms_preview_pane` patch renderer **list/kanban của DMS file** — nhưng ở chế độ
inheritance-only, người dùng sống trên form `aidt.document`, nơi patch đó không
chạm.

`preview_registry.esm.js` là extension point tường minh (`{component, match,
score}`), mount lại component trên form ta là được hỗ trợ — nhưng nghĩa là custom
OWL trong `aidt_dms` gắn vào JS API của **một PR chưa review** — đúng chỗ ta muốn
coupling ~0.

**Quyết định:** dùng **list view DMS Files** làm bề mặt xem, không custom JS. Vì
`_search` đã lọc ORM, menu "Văn bản — Tệp" an toàn để phơi: user chỉ thấy tệp được
đọc, độ mật & phạm vi đơn vị đã áp. Pane hoạt động native, **zero custom JS**. Form
văn bản có `file_ids` + nút mở tệp trong view đó. Nếu UAT thấy vướng, mount
component lên form là follow-up gọn — registry vẫn còn đó.

### 5.3. Docker

`soffice` gọi in-process → phải nằm trong image runtime Odoo (sidecar sẽ buộc sửa
code vendor, phạm §2). Thêm vào stage `runtime`:

- `libreoffice-writer` (~250 MB) thay vì `libreoffice` đầy đủ (~800 MB) — văn bản
  là tài liệu Writer. Thêm `libreoffice-calc` chỉ khi S-05 (trích bảng) đến sau.
  `_check_external_dependencies` của Odoo chỉ validate key `python`/`bin` → manifest
  `deb: ["libreoffice"]` không phản đối.
- `fonts-noto` + `fonts-liberation` — **không tùy chọn**; thiếu thì dấu tiếng Việt
  thành tofu trong mọi PDF convert.

Ghi chú vận hành cho plan:
- `soffice` là subprocess → RAM của nó nằm **ngoài** `limit_memory_hard` của worker
  nhưng **trong** container. Cân lại sizing 4 GB / 5 worker.
- Nhiều lần xem-đầu-tiên DOCX lớn đồng thời có thể fan-out nhiều tiến trình
  `soffice`; cache `write_date` chặn chi phí lặp, không chặn stampede lần đầu.

## 6. Phạm vi

**Trong phạm vi:** vendor `dms` core + `aidt_dms` bridge; N-04 secrecy field + rule;
V-04 preview (core PDF + LibreOffice cho office); seed tệp demo.

**Ngoài phạm vi (flag rõ):**
- **N-10 versioning** — OCA dms **không có** (xác nhận: 0 kết quả "version" trong
  `dms_file.py`). Cần model version-history + hook riêng, độc lập.
- **S-09 cây lưu trữ nghiệp vụ** — không biểu diễn được ở chế độ inheritance-only;
  thiết kế riêng.
- Refactor không liên quan.

## 7. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| #475 đổi schema trước khi merge | Không sửa vendor; coupling dồn `aidt_dms`; ghim SHA + `VENDORED.md` |
| Preview PR chưa review, có thể bỏ rơi | Preview qua list view native, 0 custom JS phụ thuộc API của PR |
| `check_name` từ chối `/` trong số ký hiệu | `_dir_name` sanitize + unit test riêng |
| Thêm rule mật OR-nới-rộng quyền | Rule mật **global**; regression test đơn-v.-clearance |
| `soffice` RAM ngoài giới hạn worker | Cân sizing container; `libreoffice-writer` gọn; cache write_date |
| Dấu tiếng Việt lỗi trong PDF convert | `fonts-noto` bắt buộc trong image |
```

