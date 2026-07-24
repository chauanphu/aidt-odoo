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
| _(cập nhật ở Task 3 và Task 4)_ | |

## Nguyên tắc

- **Không sửa code ở đây để đổi hành vi.** Muốn đổi hành vi thì tạo/ sửa module
  `aidt_*` trong `custom-addons/` và dùng `_inherit`.
- Chỉ sửa khi module **không chạy được** nếu không sửa, hoặc vá bug gấp của upstream.
- Mỗi lần sửa: một commit riêng, tiêu đề bắt đầu `[MIG]` hoặc `[FIX]`, và thêm
  một dòng vào bảng "Patch đã áp" ở trên.
