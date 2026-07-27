# Plan: Core Nhiệm vụ (Nhóm 5, không-AI)

> Spec: `docs/superpowers/specs/2026-07-27-nhiem-vu-core-design.md` (đã duyệt).
> REQUIRED SUB-SKILL: superpowers:subagent-driven-development (có subagent) hoặc
> test-driven-development. Mỗi task viết test TRƯỚC.

## Global Constraints

- Odoo 19. Module mới `custom-addons/aidt_task/` (depends `aidt_org`, `mail`) +
  `custom-addons/aidt_task_demo/`. KHÔNG sửa `odoo/`, `addons/` core.
- Tái dùng 6 nhóm `aidt_org.group_*` — KHÔNG tạo nhóm mới.
- Bảo mật độ mật là bắt buộc (mirror `aidt_org.rule_aidt_document_secrecy`).
- Test chạy: `docker compose -f docker-compose.dev.yml run --rm odoo odoo -d <db>
  -i aidt_task --without-demo=False --test-enable --test-tags /aidt_task
  --stop-after-init`. Dùng db tạm, drop sau.
- Commit từng task, prefix `[ADD]`/`[IMP]`, trailer
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Source bind-mounted → sửa .py/.xml là live; chỉ cần `-u aidt_task` để nạp lại
  schema/data, KHÔNG cần rebuild image.

### Task 1: Skeleton + model `aidt.task` (fields & computes)

**Files:** `aidt_task/__init__.py`, `__manifest__.py`, `models/__init__.py`,
`models/aidt_task.py`, `tests/__init__.py`, `tests/test_task_model.py`

- [ ] **Test trước** (`test_task_model.py`): tạo dept + doc (secrecy=mat); tạo
  `aidt.task`. Assert: `secrecy_level` đúng; `is_overdue` True khi
  `deadline`=hôm qua & state≠done, False khi state=done hoặc deadline tương
  lai/không có; `result_count`=0.
- [ ] Manifest: name, depends `['aidt_org','mail']`, data để trống (task sau),
  license LGPL-3, `application=False`.
- [ ] Model `aidt.task`: các field theo spec; `_SECRECY_LEVEL` map;
  `_compute_secrecy_level` (@depends secrecy) store index;
  `_compute_overdue` (@depends deadline,state) store; `_compute_result_count`.
- [ ] **Onchange** `_onchange_document_secrecy`: khi set `document_id`, gán
  `secrecy` = document.secrecy (cho override).
- [ ] Chạy test → xanh. Commit `[ADD] aidt_task: model aidt.task + computes`.

### Task 2: Model `aidt.task.result` (T-12)

**Files:** `models/aidt_task_result.py`, `models/__init__.py`, thêm `result_ids`
vào `aidt.task`; test trong `tests/test_task_result.py`

- [ ] **Test trước**: tạo task + 2 result; assert `result_count`=2; xóa task →
  result cascade; `result.secrecy_level` == task.secrecy_level (related).
- [ ] Model theo spec (task_id cascade, report, attachment_ids, submit_uid/date,
  secrecy_level related store).
- [ ] Test xanh. Commit `[ADD] aidt_task: aidt.task.result (báo cáo kết quả)`.

### Task 3: Vòng đời + nút (T-09, T-13)

**Files:** thêm method vào `aidt_task.py`; `tests/test_task_workflow.py`

- [ ] **Test trước**: `action_start` new→in_progress; `action_submit_review`
  →pending_review; `action_approve` bởi assigner →done; `action_approve` bởi
  user khác → raise `UserError`; `action_reject` →in_progress; `action_hold`.
- [ ] Cài đặt các method + kiểm `self.env.user == assigner_id` cho approve.
- [ ] Test xanh. Commit `[ADD] aidt_task: vòng đời + duyệt đóng (assigner-only)`.

### Task 4: Bảo mật (N-04, phạm vi, O-03)

**Files:** `security/ir.model.access.csv`, `security/aidt_task_rules.xml`; thêm
2 file vào manifest data; `tests/test_task_security.py`

- [ ] **Test trước** (dùng `with_user`): user clearance=0 KHÔNG đọc được task
  secrecy=mat (search trả rỗng / read raise AccessError); user clearance=3 đọc
  được. User đơn vị khác không thấy; assignee thấy. Admin thấy hết.
- [ ] `ir.model.access.csv`: chuyên viên + admin CRUD cho `aidt.task`,
  `aidt.task.result`.
- [ ] `aidt_task_rules.xml`: rule secrecy toàn cục (no groups), rule phạm vi
  (group_chuyen_vien), rule admin (group_aidt_admin); tương tự cho result.
- [ ] Cập nhật manifest data. Test xanh (đặc biệt O-03). Commit
  `[ADD] aidt_task: ir.rule độ mật + phạm vi (N-04/O-03)`.

### Task 5: Nhắc việc cron (T-11, T-14)

**Files:** `data/aidt_task_cron.xml`, `data/mail_templates.xml`, method cron
trong `aidt_task.py`; `tests/test_task_cron.py`

- [ ] **Test trước**: task deadline=+3 ngày → chạy `_cron_deadline_reminders`
  tạo 1 activity cho assignee; chạy lần 2 KHÔNG tạo trùng (idempotent). Task
  overdue → digest gộp theo đơn vị (assert nội dung/không lỗi).
- [ ] `_cron_deadline_reminders` (7/3/1 + overdue, idempotent qua summary+ngày),
  `_cron_leader_overdue_digest` (gộp theo dept, email group_chanh_vp).
- [ ] `ir.cron` records (daily, weekly-Mon) + mail template tối giản.
- [ ] Test xanh. Commit `[ADD] aidt_task: cron nhắc việc + cảnh báo lãnh đạo`.

### Task 6: Views + nút trên văn bản (T-05, T-08, T-07)

**Files:** `views/aidt_task_views.xml`, `views/aidt_document_views.xml` (inherit),
method `action_extract_tasks` + `task_count` trên `aidt.document` (inherit trong
`aidt_task/models/aidt_document.py`); thêm vào manifest.

- [ ] Inherit `aidt.document`: `task_ids` (O2m), `task_count` computed,
  `action_extract_tasks` (trả act_window list aidt.task, domain document, context
  `default_document_id/department_id/secrecy`).
- [ ] `aidt_task_views.xml`: list (decoration-danger nếu is_overdue), kanban theo
  state, form (nhóm nguồn/phân công/hạn/kết quả), search (lọc T-08), action, menu
  "Nhiệm vụ" (root riêng hoặc dưới menu văn bản).
- [ ] `aidt_document_views.xml`: nút smart "Bóc tách nhiệm vụ" + badge task_count.
- [ ] Cập nhật manifest. Cài `-u aidt_task` không lỗi loader; mở form không lỗi.
- [ ] Commit `[ADD] aidt_task: views + nút bóc tách trên văn bản`.

### Task 7: Demo data + dashboard tiles

**Files:** `custom-addons/aidt_task_demo/**`; thêm tile vào
`aidt_dashboard_demo/data/dashboard_tiles.xml`.

- [ ] `aidt_task_demo`: manifest depends `['aidt_task','aidt_org_demo']`; vài
  nhiệm vụ gắn văn bản demo (đủ độ mật khác nhau) + 1 ad-hoc + 1 quá hạn + 1 có
  result. `noupdate` hợp lý.
- [ ] Dashboard: tile "Nhiệm vụ quá hạn" (đỏ), "Đến hạn 7 ngày" (cam), "Chờ
  duyệt" — model `aidt.task`, domain tương ứng; + graph theo `department_id`.
- [ ] Cài `-u aidt_task_demo,aidt_dashboard_demo`. Commit
  `[IMP] aidt_task_demo + dashboard: dữ liệu & tile nhiệm vụ`.

### Task 8: Verify tổng hợp

- [ ] Fresh db: `-i aidt_task,aidt_task_demo --without-demo=False --test-enable
  --test-tags /aidt_task` → `0 failed, 0 error`.
- [ ] Cài vào db `aidt` (`-u`/`-i`), clear asset cache, restart; mở menu Nhiệm
  vụ + nút trên văn bản + dashboard trên browser (user xác nhận).
- [ ] Drop db tạm. Cập nhật ledger + báo user.

## Ngoài phạm vi
- T-01→T-04 (AI bóc tách) — spec riêng khi có AI infra.
- T-10 nhiệm vụ con (P1).
