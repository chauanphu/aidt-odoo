# Thiết kế: Core Nhiệm vụ (Nhóm 5, không-AI)

> Đã brainstorm & user duyệt 2026-07-27. Phạm vi: **Core không-AI** của Nhóm 5
> (BÓC TÁCH & THEO DÕI NHIỆM VỤ). Bỏ T-01→T-04 (AI bóc tách — spec sau, cần AI
> infra N-15→N-18). Hoãn T-10 (nhiệm vụ con, P1).

## Mục tiêu

Cán bộ tạo & theo dõi nhiệm vụ — sinh từ văn bản (`aidt.document`) hoặc giao
tay ad-hoc — với vòng đời, nhắc việc tự động, báo cáo kết quả, duyệt đóng, và
dashboard. Là khung human-in-the-loop mà AI (T-01→T-04) sẽ pre-fill sau.

## Phạm vi (T-code)

| Làm | T-05 (màn duyệt/tạo từ VB), T-06 (sửa/thêm tay), T-07 (liên kết nguồn), T-08 (danh mục+lọc), T-09 (trạng thái), T-11 (nhắc việc), T-12 (báo cáo kết quả), T-13 (duyệt đóng), T-14 (cảnh báo lãnh đạo), T-15 (bảng tổng hợp) |
|---|---|
| **Ngoài phạm vi** | T-01→T-04 (AI), T-10 (nhiệm vụ con) |

## Kiến trúc

- **`custom-addons/aidt_task/`** — model + view + security + cron. Depends
  `['aidt_org', 'mail']`. Không tạo nhóm RBAC mới — tái dùng 6 nhóm
  `aidt_org.group_*`.
- **`custom-addons/aidt_task_demo/`** — dữ liệu mẫu. Depends `['aidt_task',
  'aidt_org_demo']`.
- Dashboard tiles nhiệm vụ: thêm vào `aidt_dashboard_demo`.

## Data model

### `aidt.task` — inherit `mail.thread`, `mail.activity.mixin`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `name` | Char, required, tracking | Nội dung nhiệm vụ |
| `document_id` | M2o `aidt.document`, **optional**, index | Văn bản nguồn (T-07) |
| `source_quote` | Text | Đoạn trích nguồn (T-05/07) |
| `source_ref` | Char | Vị trí đoạn (trang/mục) |
| `department_id` | M2o `hr.department`, required, index | Đơn vị chủ trì (T-02) |
| `collaborator_department_ids` | M2m `hr.department` | Đơn vị phối hợp (T-03) |
| `assignee_id` | M2o `res.users` | Người thực hiện (T-08) |
| `assigner_id` | M2o `res.users`, default `create_uid` | Người giao = người duyệt đóng (T-13) |
| `deadline` | Date | Hạn (T-04) |
| `deadline_note` | Char | Câu hạn gốc ("trong quý II") — chỗ AI dùng sau |
| `state` | Selection | `new/in_progress/pending_review/done/on_hold` (T-09) |
| `is_overdue` | Boolean, **computed store**, `_compute_overdue` | `deadline<today AND state not in (done)` |
| `secrecy` | Selection (thuong/mat/toi_mat/tuyet_mat), required, default thuong | Onchange điền từ `document_id`, vẫn cho sửa |
| `secrecy_level` | Integer, computed store index | Map như `aidt.document` |
| `result_ids` | O2m `aidt.task.result` | Báo cáo (T-12) |
| `result_count` | Integer computed | |

**Vòng đời (state):**
`new → in_progress → pending_review → done`, nhánh `on_hold`. **"Quá hạn"
KHÔNG là state** — dùng `is_overdue` (computed, stored) để lọc/cảnh báo.
Nút: `action_start`, `action_submit_review`, `action_approve` (**chỉ
`assigner_id`**, raise `UserError` nếu khác), `action_reject`, `action_hold`.

**`secrecy_level`** map: thuong→0, mat→1, toi_mat→2, tuyet_mat→3 (tái dùng
hằng của `aidt_org`).

### `aidt.task.result` — báo cáo kết quả (T-12)

| Trường | Kiểu |
|---|---|
| `task_id` | M2o `aidt.task`, required, ondelete cascade |
| `report` | Text |
| `attachment_ids` | M2m `ir.attachment` (file minh chứng) |
| `submit_uid` | M2o `res.users`, default current |
| `submit_date` | Datetime, default now |
| `secrecy_level` | Integer related `task_id.secrecy_level`, store | (cho ir.rule) |

## Bảo mật (N-04 / V-13 — bắt buộc)

- **ir.rule toàn cục** trên `aidt.task`: `[('secrecy_level','<=',
  user.clearance_level)]` — KHÔNG gán `groups` (áp cho mọi user, AND vào rule
  khác). Mirror `aidt_org.rule_aidt_document_secrecy`.
- **ir.rule phạm vi** (gán nhóm `group_chuyen_vien`): thấy nhiệm vụ mà đơn vị
  mình chủ trì/phối hợp **hoặc** mình là assignee/assigner:
  `['|','|', ('department_id','child_of',user...dept.ids),
  ('collaborator_department_ids','child_of',user...dept.ids),
  ('assignee_id','=',user.id)]`.
- **ir.rule admin** (`group_aidt_admin`): `[(1,'=',1)]`.
- `aidt.task.result`: ir.rule toàn cục theo `secrecy_level` related.
- `ir.model.access.csv`: chuyên viên CRUD; các nhóm cao kế thừa qua
  `implied_ids` đã có.

## Nhắc việc (T-11, T-14) — cron gốc Odoo

- **`ir.cron` hằng ngày** `_cron_deadline_reminders`: nhiệm vụ chưa done, tính
  `deadline - today`. Nếu ∈ {7,3,1} hoặc vừa quá hạn → tạo `mail.activity`
  (activity_type reminder) cho `assignee_id` + gửi email template. **Idempotent**:
  không tạo trùng trong ngày (check activity đã tồn tại theo summary/ngày).
- **`ir.cron` hàng tuần** (thứ Hai) `_cron_leader_overdue_digest`: gộp
  `is_overdue=True` theo `department_id` → 1 email tổng hợp cho nhóm Chánh VP
  (`group_chanh_vp`).

## UI (T-05, T-08, T-15)

- `aidt.task`: list (màu theo `is_overdue`), kanban theo `state`, form, search
  (lọc theo đơn vị/người/trạng thái/hạn/`document_id` — T-08), action + menu
  "Nhiệm vụ".
- **Nút "Bóc tách nhiệm vụ"** trên form `aidt.document` (inherit) →
  `action_extract_tasks`: mở list nhiệm vụ của văn bản đó với context prefill
  `default_document_id`, `default_department_id`, `default_secrecy` (màn T-05).
  `task_count` badge trên document.
- **Dashboard**: tile "Quá hạn / Đến hạn 7 ngày / Chờ duyệt" + graph theo đơn
  vị (tái dùng pattern `tile.tile` + graph đã có ở `aidt_dashboard_demo`).

## Kiểm thử (TDD, O-03)

1. `_compute_overdue` đúng theo deadline/state; `_compute_secrecy_level`.
2. Onchange điền `secrecy` từ `document_id`, cho override.
3. **ir.rule**: user `clearance_level` thấp KHÔNG đọc được nhiệm vụ mật (O-03).
4. Phạm vi: user đơn vị khác không thấy; assignee thấy.
5. `action_approve` chỉ `assigner_id`; state transitions hợp lệ.
6. Cron nhắc việc idempotent (chạy 2 lần không tạo trùng activity).
7. `aidt.task.result` cascade + secrecy_level related.

## Nguyên tắc Odoo 19 (đã biết từ dms migration)

- `res.groups` field: `group_ids`/`user_ids`/`privilege_id`; rule groups
  `[(4, ref(...))]`.
- Computed-stored + `@api.depends`; Selection; `mail.activity.mixin`.
