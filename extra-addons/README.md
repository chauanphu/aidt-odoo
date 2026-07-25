# extra-addons — code của bên thứ ba

Thư mục này chỉ chứa những gì có thể tải lại được từ internet.
Nếu xoá cả thư mục rồi kéo lại mà mất mát thông tin, nghĩa là có thứ đã bị
đặt sai chỗ — nó phải nằm ở `custom-addons/`.

Mỗi repo vendor là một thư mục con và cần **một mục riêng trong
`addons_path`** (xem `docker/odoo.conf`), vì module nằm ở tầng con của nó.

## dms/

| | |
|---|---|
| Nguồn | https://github.com/OCA/dms |
| Branch | 18.0 |
| Commit pin | `6da958550a511dfa382c1f4208d6024adb4a5d95` (2026-07-22) |
| Cách kéo về | `git subtree add --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash` |
| Cách cập nhật | `git subtree pull --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash` |

### Module đã xoá khỏi bản vendor

| Module | Lý do |
|---|---|
| `dms_user_role` | Cần `base_user_role` (OCA/server-backend), chưa vendor repo đó |
| `web_editor_media_dialog_dms` | Cần `web_editor`, module này không còn trong Odoo 19 (đã thay bằng `html_editor`). Muốn dùng phải port thật, không phải bump version. |

### Patch đã áp lên code upstream

Mọi mục dưới đây là **thay đổi của chúng ta**, sẽ gây xung đột khi
`git subtree pull`. Khi OCA phát hành branch 19.0 chính thức, đối chiếu danh
sách này để bỏ những patch đã được upstream giải quyết.

| Commit | Nội dung |
|---|---|
| 3e58728 | dms: `_compute_users` dùng `res.groups.user_ids` (Odoo 19 đổi tên `users`) |
| d50c4a1 | dms: migrate security data `res.groups` sang `privilege_id` |
| fa227855 | dms: bỏ thuộc tính group không hợp lệ trong search view |
| 4d638e4 | dms: đổi `ir.actions.server.groups_id` → `group_ids` |
| adbdbd1 | dms: bỏ act_window target `inline` (Odoo 19 gỡ) |
| c29c66d | dms: bump manifest 18.0 → 19.0 series |
| 3549911 | dms: hoàn tất rename `res.users.groups_id` → `group_ids` ở demo + test (sót từ 3e58728, gây ParseError chặn toàn bộ demo) |
| 4c6d4f8 | dms: sửa search `permission_*` bị mất lọc quyền trên Odoo 19 (domain optimizer ép giá trị field boolean thành `OrderedSet`, HACK `value == uid` hỏng nên trả TRUE_DOMAIN → user/portal thấy mọi file/thư mục). Bỏ sudo để tính domain theo đúng user thật |
| c0c06ef | dms: sửa search `starred` bị đảo ngược trên Odoo 19 (`operator == "="` không còn đúng vì domain thành `('starred','in',OrderedSet([True]))`, rơi vào nhánh `not in`). Chuẩn hoá operator + operand dạng set |
| 919ebf8 | dms_field: bump manifest 18.0 → 19.0 series |
| e858055 | dms_field: đổi `res.groups.users` → `user_ids` trong test setup (Odoo 19 đổi tên field) |
| 7d295e2 | dms_field: thay `odoo.fields.first()` (đã bị gỡ ở Odoo 19) bằng slicing `[:1]` trong test |
| 6b94dd1 | dms_field: viết lại `DmsDirectory._search_parents` — Odoo 19 gỡ `_where_calc`/`_apply_ir_rules`, dựng lại bằng `Domain`/`Query`/`ir.rule._compute_domain` |
| d57cbf8 | dms: sửa template nút kanban/list (`dms.KanbanButtons`, `dms.ListButtons`) — `web.KanbanView.Buttons`/`web.ListView.Buttons` giờ rỗng ở Odoo 19 nên `<xpath expr="//div">` gãy (OwlError khi mở Files). Đổi sang `<xpath expr="." position="inside">` theo pattern core. Lỗi frontend test Python không bắt được |

| (fix) | dms: `_create_model_attachment` chấp nhận cả `content_binary` (bytes thô, từ controller upload hàng loạt) lẫn `content` (base64) — trước đó chỉ đọc key `content` nên upload vào kho attachment (văn bản) KeyError('content') |

## Nguyên tắc

- **Không sửa code ở đây để đổi hành vi.** Muốn đổi hành vi thì tạo/ sửa module
  `aidt_*` trong `custom-addons/` và dùng `_inherit`.
- Chỉ sửa khi module **không chạy được** nếu không sửa, hoặc vá bug gấp của upstream.
- Mỗi lần sửa: một commit riêng, tiêu đề bắt đầu `[MIG]` hoặc `[FIX]`, và thêm
  một dòng vào bảng "Patch đã áp" ở trên.
