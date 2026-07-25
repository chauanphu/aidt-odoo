# Tăng 2 — LibreOffice Preview (xem trước file office trong trình duyệt)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development hoặc executing-plans để thực thi. Steps dùng checkbox `- [ ]`.
> **Trạng thái:** CHƯA thực thi — tài liệu để làm sau (user để dành).

**Goal:** Cho phép xem trước (read-only) file office (`.docx/.xlsx/.pptx`) và PDF ngay trong trình duyệt, không cần tải về — bằng cách vendor 2 module OCA (`dms_preview_pane` + `dms_libreoffice_preview`) và thêm LibreOffice vào Docker image. Đáp ứng V-04 ("Xem PDF/DOCX ngay trên trình duyệt") trong `docs/mvp.md`.

**Architecture:** `dms_libreoffice_preview` chạy `soffice --headless --convert-to pdf` phía server để convert office→PDF, cache kết quả dạng `ir.attachment`, và serve inline qua controller `/dms/file/<id>/libreoffice_preview`. `dms_preview_pane` thêm một pane xem trước cạnh list/kanban của DMS (patch `FileKanbanRenderer`/`FileListRenderer` bằng `patch()`, không sửa code gốc). Cả hai đã sẵn version 19.0 trên nhánh `origin/feat/oca-dms-integration` → port nhẹ, không migrate lớn.

**Tech Stack:** Odoo 19, OCA dms (đã ở `extra-addons/dms/`), LibreOffice (gói deb), Docker (`Dockerfile` runtime stage), Owl JS.

## Global Constraints

- Odoo 19.0. Vendor 2 module vào `extra-addons/dms/` (cùng chỗ dms). Không sửa `odoo/`, `addons/` core.
- Nguồn: `origin/feat/oca-dms-integration`, `addons/dms_preview_pane` + `addons/dms_libreoffice_preview` (đã fetch, đã 19.0.1.0.0). Mang bằng `git archive origin/feat/oca-dms-integration <path> | tar -x --strip-components=1 -C extra-addons/dms`. **Shell caveat:** viết ref đầy đủ, đừng nhét vào biến `$VAR:path` (bị nuốt do dấu `/`).
- `dms_libreoffice_preview` khai `external_dependencies: {"deb": ["libreoffice","fonts-noto","fonts-liberation"]}` — Odoo **từ chối cài** nếu `libreoffice` chưa có trong image. Nên Docker phải xong TRƯỚC.
- Commit prefix `[ADD]`/`[IMP]`, trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Rebuild image bắt buộc `--build` (odoo.conf/Dockerfile COPY lúc build). Bind-mount chỉ áp cho source, không cho gói hệ thống.

## Rủi ro chính (đọc trước)

- **Docker rebuild + LibreOffice**: image hiện ~5.4GB, máy dev 7.7GB RAM. LibreOffice + fonts ~+400-600MB → **nguy cơ SIGBUS lúc "exporting layers"** (đã gặp ở Increment 1). Giảm rủi ro: `docker system prune` giải phóng dung lượng trước; build nền + Monitor bắt `SIGBUS|exporting layers ... done`; nếu vỡ, retry 1 lần, rồi báo user dọn thêm.
- LibreOffice đặt ở **runtime stage** → production image cũng to hơn (đúng — prod cũng cần preview). Nếu chỉ muốn dev có preview, đặt ở dev stage thay vì runtime (nhưng khi đó external_dependencies check ở prod sẽ fail nếu cài module ở prod).
- `dms_preview_pane` patch `FileKanbanRenderer`/`FileListRenderer` — cùng renderer đã bị sửa ở Increment 1 (button templates) + 3 file esm.js commit trong "public demo". Cần verify JS render KHÔNG lỗi OwlError sau khi cài (mở Documents/Files trên browser, hard-refresh).

---

### Task 1: Thêm LibreOffice vào Docker image

**Files:** Modify `Dockerfile` (runtime stage, khối `apt-get install` ~dòng 48)

- [ ] **Step 1: Dọn dung lượng trước (tránh SIGBUS)**

```bash
docker system prune -f
free -h | head -2   # xác nhận còn RAM/đĩa
```

- [ ] **Step 2: Thêm libreoffice + fonts-noto vào runtime apt-get**

Trong `Dockerfile`, khối runtime `RUN apt-get update && apt-get install -y --no-install-recommends \` (khối có `fonts-liberation`, `fonts-noto-cjk`), thêm 2 gói:
```
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-noto \
```
(Dùng `libreoffice-writer/calc/impress` thay `libreoffice` full để nhẹ hơn — vẫn convert được doc/sheet/slide. Nếu muốn đủ, dùng `libreoffice`.)

- [ ] **Step 3: Rebuild image (nền + monitor SIGBUS)**

```bash
nohup docker compose -f docker-compose.dev.yml build odoo > /tmp/lo-build.log 2>&1 &
```
Monitor `/tmp/lo-build.log` cho `exporting layers .* done` (thành công) hoặc `SIGBUS|failed to solve` (vỡ → retry 1 lần, rồi báo user).

- [ ] **Step 4: Xác nhận soffice có trong image**

```bash
docker compose -f docker-compose.dev.yml run --rm --entrypoint /bin/sh odoo -c "which soffice && soffice --version"
```
Expected: đường dẫn `/usr/bin/soffice` + version LibreOffice.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile
git commit -m "$(cat <<'EOF'
[ADD] docker: LibreOffice for DMS office-file preview (Tăng 2)

Adds libreoffice-writer/calc/impress + fonts-noto to the runtime stage so
dms_libreoffice_preview can convert office files to PDF server-side. Required
by that module's external_dependencies deb check.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Vendor 2 module preview vào extra-addons/dms

**Files:** Create `extra-addons/dms/dms_preview_pane/**`, `extra-addons/dms/dms_libreoffice_preview/**`

- [ ] **Step 1: Mang 2 module từ nhánh nguồn**

```bash
cd /home/harryitc/my_project/aidt-odoo
git archive origin/feat/oca-dms-integration addons/dms_preview_pane addons/dms_libreoffice_preview \
  | tar -x --strip-components=1 -C extra-addons/dms
find extra-addons/dms/dms_preview_pane extra-addons/dms/dms_libreoffice_preview -name __manifest__.py
```
Expected: 2 manifest xuất hiện dưới `extra-addons/dms/`.

- [ ] **Step 2: Xác nhận version 19.0 (không cần bump)**

```bash
grep '"version"' extra-addons/dms/dms_preview_pane/__manifest__.py extra-addons/dms/dms_libreoffice_preview/__manifest__.py
```
Expected: cả hai `19.0.x.y.z`. Nếu là 18.0, bump `19.0.*` (như Increment 1).

- [ ] **Step 3: Cài + đọc lỗi**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d lo_t2 -i dms_libreoffice_preview --without-demo=False --stop-after-init 2>&1 \
  | grep -nE "Modules loaded|CRITICAL|Traceback|incompatible version|external"
```
Expected: `Modules loaded.` (kéo theo dms_preview_pane + dms). Nếu lỗi `external_dependencies`, kiểm Task 1 (soffice). Nếu lỗi loader/JS, sửa theo traceback (mỗi lỗi 1 commit `[MIG]` + ghi `extra-addons/README.md`).

- [ ] **Step 4: Ghi README vendor + commit**

Thêm 2 dòng vào `extra-addons/README.md` (nguồn + commit pin). Commit:
```bash
git add extra-addons/dms/dms_preview_pane extra-addons/dms/dms_libreoffice_preview extra-addons/README.md
git commit -m "$(cat <<'EOF'
[ADD] extra-addons: vendor dms_preview_pane + dms_libreoffice_preview (19.0)

In-browser office/PDF preview for DMS. Ported from
origin/feat/oca-dms-integration (already 19.0). Requires LibreOffice in the
image (previous commit).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Verify render + preview end-to-end

**Files:** không tạo code (verify). Nếu JS lỗi, sửa module preview theo traceball.

- [ ] **Step 1: Cài vào DB dự án + regenerate assets**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt -i dms_libreoffice_preview --stop-after-init
# xóa asset bundle cache để browser lấy JS mới (như Increment 1)
docker compose -f docker-compose.dev.yml exec -T db psql -U odoo -d aidt -c \
  "delete from ir_attachment where name like '%assets%' and (name like '%.js' or name like '%.css');"
docker compose -f docker-compose.dev.yml restart odoo
```

- [ ] **Step 2: Verify JS render (browser, hard-refresh)**

Mở `http://localhost:8069/web?db=aidt` → **Documents → Files**. Hard-refresh (`Ctrl+Shift+R`).
- Kanban/List file **render KHÔNG OwlError** (nếu lỗi template inheritance như Increment 1, sửa file `_patch` tương ứng).
- Chọn 1 file → **pane xem trước hiện bên cạnh**.

- [ ] **Step 3: Verify convert office→PDF**

Upload/mở `FIT & GAP Odoo.docx` (đã có sẵn ở văn bản demo) trong Documents → Files.
- Expected: pane hiện **PDF** (LibreOffice đã convert). Lần đầu chậm (convert), lần sau nhanh (cache).
- Kiểm controller: `curl -s -b <session> "http://localhost:8069/dms/file/<id>/libreoffice_preview" -o /tmp/p.pdf; file /tmp/p.pdf` → `PDF document`.

- [ ] **Step 4: (tùy) preview trong tab "Tệp đính kèm" của Văn bản**

Mở một `aidt.document` → tab **Tệp đính kèm**. Xác nhận file mở được (pane hoặc file viewer). Nếu tab này KHÔNG dùng pane của dms_preview_pane (nó là list nhúng, không phải view DMS gốc), ghi nhận: preview đầy đủ ở **Documents/Files**; tab văn bản có thể chỉ tải/xem cơ bản. Cân nhắc thêm nút "Mở trong Documents" nếu cần preview ngay trong form văn bản (việc nhỏ, tùy chọn).

---

## Ngoài phạm vi (Tăng 3+ nếu cần)

- **OnlyOffice** (biên tập online co-author) — cân nhắc sau; nặng hơn nhiều (Document Server riêng + JWT + adapt cho dms.file), và cần cô lập mạng cho văn bản mật. Xem so sánh đã bàn: với văn bản mật, LibreOffice (convert trên server Odoo, không rời ranh giới tin cậy) an toàn hơn.
- Preview inline NGAY trong tab "Tệp đính kèm" của form văn bản (nếu Task 3 Step 4 cho thấy chưa có) — cần thêm widget/nút riêng.
- Thêm LibreOffice vào production compose/Dockerfile nếu tách image dev/prod.
