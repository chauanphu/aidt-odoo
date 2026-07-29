# Văn bản ↔ DMS Bridge + Độ mật N-04 — Implementation Plan (Tăng 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trên nhánh hiện tại (đã migrate OCA `dms`+`dms_field` lên Odoo 19), bổ sung hai năng lực còn thiếu bằng cách port từ nhánh `origin/feat/oca-dms-integration`: (1) độ mật 4 mức N-04 trên `aidt.document`, (2) cầu nối `aidt.document ↔ OCA DMS` để mỗi văn bản có một thư mục DMS riêng, tệp kế thừa quyền phạm vi + độ mật của văn bản.

**Architecture:** Giữ nguyên nền của nhánh hiện tại (`extra-addons/dms/` đã migrate 19). Xóa module demo `custom-addons/aidt_dms` (gắn Sale Order — không phục vụ dự án) để giải phóng tên. Port N-04 vào `addons/aidt_org` (thêm thuần, không phá cấu trúc cũ). Tạo module mới **`custom-addons/aidt_dms`** là cầu nối văn bản↔DMS, depends `aidt_org` (ở `addons/`) + `dms` (ở `extra-addons/dms/`) — Odoo resolve depends theo TÊN nên vị trí thư mục không ảnh hưởng. Dùng `dms.storage` chế độ `attachment`+`inherit_access_from_parent_record` để tệp ủy quyền cho `aidt.document`.

> **Ghi chú vị trí:** module bridge đặt ở `custom-addons/` theo quy ước "code dự án nằm ở custom-addons/" (như `aidt_base`). `aidt_org`/`aidt_org_demo` vẫn ở `addons/` (đến từ merge 19.0) — chấp nhận split tạm này; thống nhất chỗ đặt toàn bộ hệ aidt là việc riêng, ngoài phạm vi plan này.

**Tech Stack:** Odoo 19 (repo này), PostgreSQL 16 qua `docker-compose.dev.yml`, OCA/dms (đã migrate 19, ở `extra-addons/dms/`), `addons/aidt_org` (cây tổ chức + RBAC + `aidt.document`), Python model + XML data/security/views, `odoo.tests.TransactionCase`.

## Global Constraints

- Odoo series **19.0**. Field users↔groups là `group_ids` (KHÔNG `groups_id`); list view dùng `<list>` (KHÔNG `<tree>`).
- KHÔNG sửa module core (`odoo/`, `addons/hr`...) và KHÔNG sửa code vendored trong `extra-addons/dms/` trong plan này (nó đã migrate xong; nếu thấy cần sửa, dừng và báo).
- Module mới/ sửa: `license` = `LGPL-3`. Nhãn tiếng Việt có dấu; xml id/login không dấu.
- Nguồn port: nhánh `origin/feat/oca-dms-integration` đã có sẵn code này (đã fetch). Dùng `git show <ref>:<path>` / `git checkout <ref> -- <path>` để mang file — đây là code có thật, không phải viết mới.
  - **Lưu ý shell:** ref có dấu `/` dễ bị nuốt khi nhét vào biến; luôn viết ref đầy đủ, quote: `git show 'origin/feat/oca-dms-integration:addons/...'`.
- `addons_path` hiện tại (docker/odoo.conf): `/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons` — cả `addons/` (chứa aidt_org, aidt_dms mới) lẫn `extra-addons/dms` (chứa dms) đều đã nằm trong path. KHÔNG cần sửa addons_path, KHÔNG cần rebuild image (source bind-mount).
- Lệnh cài/test (chạy FOREGROUND, để block, KHÔNG background rồi chờ notification):
  `docker compose -f docker-compose.dev.yml run --rm odoo odoo -d <FRESH_DB> -i <mod> --test-enable --test-tags /<mod> --stop-after-init`
  Mỗi lần cần DB sạch dùng tên mới (`vb1`, `vb2`...). `db` service phải chạy: `docker compose -f docker-compose.dev.yml up -d db`.
- Commit prefix theo repo: `[ADD]`/`[IMP]`/`[REM] <scope>: ...`, kết thúc bằng trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- **Ngoài phạm vi Tăng 1 (để Tăng 2):** preview PDF/office (`dms_preview_pane`, `dms_libreoffice_preview`), Docker libreoffice-writer, backfill thư mục cho văn bản demo cũ.

## File Structure

| File | Trách nhiệm | Thao tác |
|---|---|---|
| `custom-addons/aidt_dms/**` | Module demo gắn Sale Order — bỏ | Xóa (Task 1) |
| `addons/aidt_org/models/aidt_document.py` | + `secrecy`, `secrecy_level` | Sửa (Task 2) |
| `addons/aidt_org/models/res_users.py` | + `clearance_level` | Tạo (Task 2) |
| `addons/aidt_org/security/aidt_org_rules.xml` | + global secrecy rule | Sửa (Task 2) |
| `addons/aidt_org/data/aidt_clearance.xml` | seed admin clearance 3 | Tạo (Task 2) |
| `addons/aidt_org/views/{aidt_document_views,res_users_views}.xml` | field độ mật/clearance | Sửa/Tạo (Task 2) |
| `addons/aidt_org/tests/test_secrecy.py` | 6 test N-04 | Tạo (Task 2) |
| `custom-addons/aidt_dms/**` | Cầu nối văn bản↔DMS (model, storage, security, views, tests) | Tạo (Task 3) |

---

### Task 1: Bỏ module demo `aidt_dms` (Sale Order)

Giải phóng tên `aidt_dms` cho cầu nối văn bản, và loại module không phục vụ dự án. Phần migrate `dms`/`dms_field` (ở `extra-addons/dms/`) và `aidt_base` giữ nguyên.

**Files:**
- Delete: `custom-addons/aidt_dms/` (toàn bộ thư mục)

**Interfaces:**
- Consumes: không
- Produces: tên module `aidt_dms` không còn ai chiếm; `custom-addons/` chỉ còn `aidt_base`.

- [ ] **Step 1: Xác nhận không module nào depends vào aidt_dms**

```bash
cd /home/harryitc/my_project/aidt-odoo
grep -rn "'aidt_dms'\|\"aidt_dms\"" addons custom-addons extra-addons --include=__manifest__.py | grep -v "custom-addons/aidt_dms/"
```
Expected: không có dòng nào (không ai depends). Nếu có, dừng và báo — cần xử lý phụ thuộc trước.

- [ ] **Step 2: Xóa thư mục**

```bash
git rm -r custom-addons/aidt_dms
```
Expected: git liệt kê các file bị xóa, exit 0.

- [ ] **Step 3: Xác nhận aidt_base vẫn cài được (không vỡ do xóa)**

```bash
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d vb_t1 -i aidt_base --stop-after-init 2>&1 | grep -E "Modules loaded|CRITICAL|Traceback"
```
Expected: có `Modules loaded.`, không `CRITICAL`/`Traceback`.

- [ ] **Step 4: Commit**

```bash
git add -A custom-addons/
git commit -m "$(cat <<'EOF'
[REM] aidt_dms: drop Sale Order demo module

The custom-addons/aidt_dms module only attached DMS to sale.order as a
reference demo of the vendor+custom pattern. sale.order is irrelevant to
the Party-committee document project; the name aidt_dms is reclaimed for
the aidt.document <-> DMS bridge. The dms/dms_field 19.0 migration in
extra-addons/dms and aidt_base are unaffected.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Độ mật N-04 trên `aidt_org`

Port các thay đổi N-04 từ `origin/feat/oca-dms-integration`. Đã xác minh: `git diff HEAD origin/feat/oca-dms-integration -- addons/aidt_org` **đúng bằng** phần N-04 (128 thêm, 1 xóa), không đụng gì khác — nên checkout thẳng các file aidt_org từ nhánh đó là an toàn.

**Files:**
- Modify: `addons/aidt_org/models/aidt_document.py`, `security/aidt_org_rules.xml`, `views/aidt_document_views.xml`, `models/__init__.py`, `tests/__init__.py`, `__manifest__.py`
- Create: `addons/aidt_org/models/res_users.py`, `data/aidt_clearance.xml`, `views/res_users_views.xml`, `tests/test_secrecy.py`

**Interfaces:**
- Consumes: model `aidt.document` (đã có: `name`, `reference`, `department_id`, `shared_user_ids`, `doc_type`, `date`, `state`); group `aidt_org.group_chuyen_vien`, `aidt_org.group_aidt_admin`.
- Produces:
  - `aidt.document.secrecy` (Selection `thuong`/`mat`/`toi_mat`/`tuyet_mat`, required, default `thuong`) và `aidt.document.secrecy_level` (Integer, compute từ secrecy, `store=True`, `index=True`, map `{thuong:0, mat:1, toi_mat:2, tuyet_mat:3}`).
  - `res.users.clearance_level` (Integer, default 0).
  - `ir.rule` id `aidt_org.rule_aidt_document_secrecy` — global (không group), domain `[('secrecy_level', '<=', user.clearance_level)]`, AND với rule phạm vi đơn vị.

- [ ] **Step 1: Mang toàn bộ file aidt_org (đã là bản + N-04) từ nhánh nguồn**

```bash
cd /home/harryitc/my_project/aidt-odoo
git checkout origin/feat/oca-dms-integration -- addons/aidt_org
```
Expected: exit 0, working tree có thay đổi trên 10 file aidt_org.

- [ ] **Step 2: Xác nhận thay đổi ĐÚNG bằng N-04, không dư**

```bash
git diff --cached --stat -- addons/aidt_org; git status --short addons/aidt_org
git diff --cached -- addons/aidt_org/models/aidt_document.py | grep -E "^\+" | grep -iE "secrecy|clearance"
```
Expected: 10 file thay đổi (aidt_document.py, res_users.py, aidt_org_rules.xml, aidt_clearance.xml, aidt_document_views.xml, res_users_views.xml, test_secrecy.py, 2×__init__.py, __manifest__.py); grep thấy các dòng `secrecy`/`secrecy_level`. KHÔNG có file aidt_org nào khác bị đụng.

- [ ] **Step 3: Cài + chạy test độ mật, xác nhận FAIL→không, tức PASS ngay (port code đã có test)**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d vb_t2 -i aidt_org --test-enable --test-tags /aidt_org --stop-after-init 2>&1 \
  | tee /tmp/vb-t2.log | grep -E "Module aidt_org: [0-9]|failed, [0-9]+ error|Invalid field|Traceback" | tail -5
```
Expected: `Module aidt_org: 0 failures, 0 errors` (test_secrecy 6 ca + test_document_scope 4 ca đều pass). Không `Invalid field`/`Traceback`.

Nếu có lỗi `Invalid field 'clearance_level' in 'res.users'` hoặc tương tự: nghĩa là thứ tự load data sai — kiểm `__manifest__.py` có `data/aidt_clearance.xml` SAU `security/` và model res_users được import trong `models/__init__.py`. Sửa theo traceback, đây là điều chỉnh hợp lệ.

- [ ] **Step 4: Kiểm chứng riêng bẫy OR-nới-rộng (regression quan trọng nhất)**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d vb_t2b -i aidt_org --test-enable \
  --test-tags /aidt_org:TestSecrecy.test_clearance_does_not_widen_department \
  --stop-after-init 2>&1 | grep -E "0 failed|failed, [0-9]+ error"
```
Expected: `0 failed` — chứng minh rule độ mật toàn cục **AND** với phạm vi: user clearance 3 (đọc mọi mức) vẫn KHÔNG thấy văn bản đơn vị khác. Nếu fail nghĩa là rule độ mật đang OR (nới rộng) — lỗi bảo mật, phải sửa domain rule về đúng dạng global (không group).

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_org
git commit -m "$(cat <<'EOF'
[IMP] aidt_org: N-04 độ mật + clearance + global secrecy rule (port)

Port N-04 from origin/feat/oca-dms-integration: 4-level secrecy on
aidt.document (thuong/mat/toi_mat/tuyet_mat) with stored+indexed
secrecy_level, clearance_level on res.users (admin-only), and a GLOBAL
ir.rule [('secrecy_level','<=',user.clearance_level)] that ANDs with the
department-scope rule (does not widen it). Admin seeded to clearance 3.
test_secrecy: 6 cases incl. the OR-widening regression.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Cầu nối `aidt.document ↔ DMS` — module `custom-addons/aidt_dms`

Port module bridge từ nhánh nguồn **vào `custom-addons/`** (đúng quy ước code dự án), **thích nghi một điểm**: bỏ `dms_libreoffice_preview` khỏi `depends` (preview để Tăng 2), chỉ depends `aidt_org` + `dms`. Đã xác minh tương thích với `dms` migrate-19: `dms.storage` có `inherit_access_from_parent_record` + `model_ids`; `dms.file` có `human_size`, `mimetype`; group `dms.group_dms_user` tồn tại; view gốc `aidt_org.aidt_document_view_form` khớp.

**Files:**
- Create (port từ `origin/feat/oca-dms-integration:addons/aidt_dms/`, đặt vào `custom-addons/aidt_dms/`): `__init__.py`, `models/__init__.py`, `models/aidt_document.py`, `models/dms_storage.py`, `data/dms_storage.xml`, `security/aidt_dms_groups.xml`, `views/aidt_document_views.xml`, `views/aidt_dms_menus.xml`, `tests/__init__.py`, `tests/test_directory_sync.py`, `tests/test_dms_security.py`, `tests/test_storage_guard.py`
- Create (thích nghi): `custom-addons/aidt_dms/__manifest__.py`

**Interfaces:**
- Consumes: `aidt.document` (+ N-04 từ Task 2); `dms.storage`, `dms.directory`, `dms.file`, group `dms.group_dms_user` (từ `extra-addons/dms/`).
- Produces:
  - `aidt.document` (inherit) thêm: `directory_id` (M2o `dms.directory`, readonly), `file_ids` (related `directory_id.file_ids`), `file_count` (compute); method `action_open_files()`; override `create`/`write`/`unlink` đồng bộ thư mục; `_dir_name()` sanitize (bỏ `/`, `\x00`, thêm `[id]`).
  - Data: `aidt_dms.storage_aidt` (dms.storage, `save_type='attachment'`, `inherit_access_from_parent_record=True`, `model_ids`=aidt.document), `aidt_dms.directory_root_aidt` (root dms.directory).
  - Constraint trên `dms.storage`: kho `storage_aidt` bắt buộc giữ attachment+inherit (khóa bất biến R1).

- [ ] **Step 1: Mang toàn bộ module bridge từ nhánh nguồn VÀO `custom-addons/`**

Nhánh nguồn để module ở `addons/aidt_dms`; ta cần nó ở `custom-addons/aidt_dms`. Dùng `git archive` để trích cây con rồi đặt đúng chỗ (tránh checkout vào addons/ rồi phải di chuyển):

```bash
cd /home/harryitc/my_project/aidt-odoo
mkdir -p custom-addons
git archive origin/feat/oca-dms-integration addons/aidt_dms \
  | tar -x --strip-components=1 -C custom-addons
```
Expected: exit 0, tạo `custom-addons/aidt_dms/` với 13 file (`--strip-components=1` bỏ tiền tố `addons/`, còn `aidt_dms/...`).

Kiểm nhanh:
```bash
find custom-addons/aidt_dms -type f | wc -l
```
Expected: `13`.

- [ ] **Step 2: Thích nghi manifest — bỏ dms_libreoffice_preview**

Sửa `custom-addons/aidt_dms/__manifest__.py`, đổi dòng `depends`:
```python
    'depends': ['aidt_org', 'dms', 'dms_libreoffice_preview'],
```
thành:
```python
    'depends': ['aidt_org', 'dms'],
```
(Preview để Tăng 2. Các field view `mimetype`/`human_size` là của `dms.file` core, không cần preview module.)

- [ ] **Step 3: Xác nhận không còn tham chiếu preview trong module**

```bash
grep -rn "libreoffice\|preview_pane\|preview" custom-addons/aidt_dms/
```
Expected: không có kết quả (module bridge không dùng preview). Nếu có trong view/data, gỡ tham chiếu đó — nếu không chắc, dừng và báo.

- [ ] **Step 4: Cài bridge + chạy test, xác nhận đồng bộ thư mục + kế thừa quyền**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d vb_t3 -i aidt_dms --test-enable --test-tags /aidt_dms --stop-after-init 2>&1 \
  | tee /tmp/vb-t3.log | grep -E "Module aidt_dms: [0-9]|failed, [0-9]+ error|Traceback|ValidationError" | tail -6
```
Expected: `Module aidt_dms: 0 failures, 0 errors` — 3 test suite pass:
- `test_directory_sync`: mỗi văn bản tự sinh directory, sanitize `/`, rename đồng bộ, chặn xóa khi còn tệp, dọn directory rỗng.
- `test_dms_security`: user clearance thấp/khác đơn vị KHÔNG thấy tệp của văn bản mật (kế thừa quyền qua storage inherit — dựa trên tầng lọc dms.security.mixin đã sửa ở migrate 19).
- `test_storage_guard`: constraint chặn tắt attachment/inherit trên kho AIDT.

Nếu `test_dms_security` fail (user thấy tệp lẽ ra bị chặn): kiểm `dms.storage.storage_aidt` có `inherit_access_from_parent_record=True` và `save_type='attachment'` không (data/dms_storage.xml). Đây là điều kiện để tệp ủy quyền cho aidt.document.

- [ ] **Step 5: Kiểm chứng model đã đăng ký + storage/directory seed đúng**

```bash
docker compose -f docker-compose.dev.yml exec -T db psql -U odoo -d vb_t3 -tAc \
 "select save_type, inherit_access_from_parent_record from dms_storage
  where id = (select res_id from ir_model_data where module='aidt_dms' and name='storage_aidt');"
```
Expected: `attachment|t` (attachment + inherit bật).

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_dms
git commit -m "$(cat <<'EOF'
[ADD] aidt_dms: bridge aidt.document <-> OCA DMS (port, N-10/V-04/V-13)

Port the document<->DMS bridge from origin/feat/oca-dms-integration onto
the migrated OCA dms (extra-addons/dms). Each aidt.document auto-creates a
linked dms.directory (res_model/res_id) under a root; files live in an
attachment+inherit dms.storage so file access delegates to the document's
department scope + N-04 secrecy. Adds file_ids/file_count + open-files
button (V-04), rename/unlink sync, and an R1 storage-invariant constraint.
Adapted: dropped dms_libreoffice_preview dep (preview deferred to Tăng 2).
Depends aidt_org + dms only.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Kiểm chứng tích hợp end-to-end trên DB demo + UI thật

Ba module (`aidt_org` + N-04, `aidt_dms` bridge, trên nền `dms` migrate-19) chạy cùng nhau, và luồng nghiệp vụ thật hoạt động.

**Files:** không tạo/sửa code (chỉ verify). Nếu phát hiện lỗi, quay lại Task tương ứng.

**Interfaces:**
- Consumes: toàn bộ Task 1–3.
- Produces: bằng chứng vận hành; DB `aidt_demo` có `aidt_dms` cài.

- [ ] **Step 1: Cài chồng cả cụm trên DB sạch + chạy toàn bộ test liên quan**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d vb_full -i aidt_dms --test-enable --test-tags /aidt_org,/aidt_dms,/dms \
  --stop-after-init 2>&1 | tee /tmp/vb-full.log \
  | grep -E "0 failed|failed, [0-9]+ error|Module (aidt_org|aidt_dms|dms):" | tail -8
```
Expected: `0 failed, 0 error(s)` tổng — cài `aidt_dms` kéo theo `aidt_org`+`dms`; test cả ba module xanh (chứng minh N-04 + bridge không làm hồi quy dms).

- [ ] **Step 2: Cài aidt_dms vào DB demo đang dùng**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -i aidt_dms --stop-after-init 2>&1 | grep -E "Modules loaded|CRITICAL|Traceback"
docker compose -f docker-compose.dev.yml restart odoo
```
Expected: `Modules loaded.`, không lỗi.

- [ ] **Step 3: Verify UI thật — tạo văn bản trong ĐÚNG đơn vị của cv.tonghop1, độ mật `mat`**

Đặt văn bản vào chính đơn vị của `cv.tonghop1` để bước sau kiểm được độ mật **độc lập với phạm vi** (cùng đơn vị → chỉ còn clearance quyết định).

```bash
SID=/tmp/vb_sess.txt; rm -f $SID
curl -s -c $SID -X POST http://localhost:8069/web/session/authenticate -H "Content-Type: application/json" \
 -d '{"jsonrpc":"2.0","params":{"db":"aidt_demo","login":"admin","password":"admin"}}' >/dev/null
call(){ curl -s -b $SID -X POST http://localhost:8069/web/dataset/call_kw -H "Content-Type: application/json" -d "$1"; }
# lấy đơn vị của cv.tonghop1 qua hr.employee
DEPT=$(call '{"jsonrpc":"2.0","params":{"model":"hr.employee","method":"search_read","args":[[["user_id.login","=","cv.tonghop1"]],["department_id"]],"kwargs":{"limit":1}}}' | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];print(r[0]["department_id"][0] if r and r[0]["department_id"] else 0)')
echo "dept của cv.tonghop1: $DEPT"
DOC=$(call "{\"jsonrpc\":\"2.0\",\"params\":{\"model\":\"aidt.document\",\"method\":\"create\",\"args\":[{\"name\":\"CV kiểm thử\",\"reference\":\"99-CV/VP\",\"department_id\":$DEPT,\"secrecy\":\"mat\"}],\"kwargs\":{}}}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"])')
echo "doc id: $DOC"
call "{\"jsonrpc\":\"2.0\",\"params\":{\"model\":\"aidt.document\",\"method\":\"read\",\"args\":[[$DOC],[\"reference\",\"secrecy\",\"directory_id\",\"file_count\"]],\"kwargs\":{}}}" \
 | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"][0];print("directory_id:",r["directory_id"],"| secrecy:",r["secrecy"],"| files:",r["file_count"])'
```
Expected: `DEPT` là số > 0; `doc id` là số; `directory_id` KHÁC `false` (tự sinh thư mục); tên directory chứa `99-CV-VP` (dấu `/` đã sanitize); `files: 0`.

- [ ] **Step 4: Verify độ mật chặn thật — CÙNG đơn vị nhưng clearance 0 vẫn không thấy**

```bash
S2=/tmp/vb_cv.txt; rm -f $S2
curl -s -c $S2 -X POST http://localhost:8069/web/session/authenticate -H "Content-Type: application/json" \
 -d '{"jsonrpc":"2.0","params":{"db":"aidt_demo","login":"cv.tonghop1","password":"demo2026"}}' >/dev/null
curl -s -b $S2 -X POST http://localhost:8069/web/dataset/call_kw -H "Content-Type: application/json" \
 -d "{\"jsonrpc\":\"2.0\",\"params\":{\"model\":\"aidt.document\",\"method\":\"search_count\",\"args\":[[[\"id\",\"=\",$DOC]]],\"kwargs\":{}}}" \
 | python3 -c 'import sys,json;print("cv.tonghop1 (cùng đơn vị, clearance 0) thấy VB mật — kỳ vọng 0:",json.load(sys.stdin).get("result"))'
```
Expected: `0`. Vì văn bản ở CÙNG đơn vị cv.tonghop1 (qua được rule phạm vi), việc vẫn không thấy chứng minh **độ mật N-04 chặn độc lập** (clearance 0 < mức `mat`=1). Đây là bằng chứng N-04 chạy thật, không phải bị chặn nhờ phạm vi.

- [ ] **Step 5: Ghi nhận trạng thái (không commit code, chỉ xác nhận)**

Xác nhận trong báo cáo: cả 3 kiểm chứng UI (tự sinh thư mục, sanitize số ký hiệu, độ mật chặn) đều đạt. Nếu bước nào fail, quay lại Task 2/3 sửa theo traceback, không "vá tạm" ở tầng verify.

---

## Ghi chú rủi ro & ngoài phạm vi

- **Backfill:** `create()` override chỉ tạo thư mục cho văn bản MỚI. ~15 văn bản demo cũ (`aidt_org_demo`) sẽ không có `directory_id` cho tới khi được tạo lại. Không chặn Tăng 1; cân nhắc một `post_init_hook` backfill ở tăng sau nếu cần demo trên dữ liệu cũ.
- **Preview (Tăng 2):** để xem trước PDF/office (V-04 đầy đủ) cần port `dms_preview_pane` + `dms_libreoffice_preview`, migrate chúng lên Odoo 19, và thêm `libreoffice-writer` vào Dockerfile — một plan riêng.
- **Điểm rủi ro kỹ thuật duy nhất** là Task 3 Step 4 (`test_dms_security`): kế thừa quyền tệp dựa trên tầng lọc `dms.security.mixin` — chính tầng đã được sửa cho Odoo 19 ở nhánh này. Nếu fail bất ngờ, đọc traceback tại storage inherit trước khi kết luận.
