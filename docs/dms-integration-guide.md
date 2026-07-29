# Gắn DMS vào một model — hướng dẫn

## Bối cảnh

Odoo Enterprise `documents` không có ở bản Community này. Ta dùng
[OCA/dms](https://github.com/OCA/dms), vendor tại `extra-addons/dms/`.
Mọi tuỳ chỉnh nằm ở `custom-addons/aidt_dms/` và **không bao giờ** sửa
code trong `extra-addons/` để đổi hành vi.

## Ba cách tích hợp — chọn cách rẻ nhất còn đủ dùng

### Cách 1 — Storage kiểu `attachment` (không viết code)

`dms.storage` có `save_type = "attachment"` cùng field `model_ids`
(Many2many tới `ir.model`). Chọn model nào ở đó thì **mọi `ir.attachment`
của record thuộc model đó tự hiện trong cây DMS**, không tạo bản sao dữ liệu.

Cấu hình hoàn toàn trong UI. Thử cách này trước.

Giới hạn: không có cây thư mục riêng cho từng record.

### Cách 2 — `dms.field.mixin` (một dòng Python + một khối XML)

Dùng khi mỗi record cần thư mục riêng. Đây là cách `aidt_dms` làm với
`sale.order` — copy nguyên mẫu đó.

**Python** — `custom-addons/aidt_dms/models/<model>.py`:

```python
from odoo import models


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "dms.field.mixin"]
```

Phải khai cả `_name` lẫn danh sách `_inherit` gồm chính model đó.

Nếu model đã override `create()`, giữ nguyên decorator
`@api.model_create_multi` trên phương thức override — bỏ nó đi thì luồng
tạo record qua RPC/`call_kw` (tức là UI thật) hỏng, dù gọi `.create()` trực
tiếp bằng Python (ví dụ trong test) vẫn chạy bình thường. Đây là lỗi thật đã
gặp khi viết `custom-addons/aidt_dms/models/sale_order.py`.

**XML** — thêm tab vào form, bằng view inheritance:

```xml
<record id="view_task_form_aidt_dms" model="ir.ui.view">
    <field name="model">project.task</field>
    <field name="inherit_id" ref="project.view_task_form2" />
    <field name="arch" type="xml">
        <notebook position="inside">
            <page name="aidt_dms" string="Documents" invisible="not id">
                <field name="dms_directory_ids" mode="dms_list" />
            </page>
        </notebook>
    </field>
</record>
```

`mode="dms_list"` là view type do `dms_field` đăng ký trên `ir.ui.view`.

**Cấu hình** — Settings → Technical → DMS Field Templates. Tạo template
trỏ tới model đó, chọn storage và `directory_format_name`. Đây là **dữ liệu,
không phải code**: người dùng nghiệp vụ tự đổi được, không cần deploy lại.

Đừng quên thêm module tương ứng vào `depends` của `aidt_dms`.

### Cách 3 — gọi thẳng model DMS

Chỉ dùng khi luồng nghiệp vụ đặc thù mà template không diễn tả được:

```python
directory = self.env["dms.directory"].create({
    "name": f"HĐ {self.name}",
    "storage_id": storage.id,
    "res_model": self._name,
    "res_id": self.id,
})
self.env["dms.file"].create({
    "name": "hop-dong.pdf",
    "directory_id": directory.id,
    "content": base64_data,
})
```

## Cấu trúc dữ liệu

```
dms.storage      save_type (database | file | attachment), model_ids, company_id
  └─ dms.directory   parent_id (cây lồng nhau), res_model + res_id (gắn record)
       └─ dms.file       content, category_id, tag_ids, mimetype
dms.access.group   phân quyền, gắn vào directory
dms.category / dms.tag   phân loại
```

## Hai cái bẫy đã gặp thật

**1. Template không chạy trong test.**
`dms.field.mixin.create()` bỏ qua template khi `config["test_enable"]` bật,
trừ khi context có `test_dms_field`. Trong test phải viết:

```python
cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
```

Không có dòng này thì thư mục không tự sinh và test fail một cách khó hiểu.

**2. Quyền truy cập.**
Mixin dùng `sudo()` trong `write()` và `unlink()` vì người dùng thường
không có quyền trên `dms.directory`. Nó còn override `web_save()` để né
lỗi access khi lưu form — chính OCA gọi đó là "hack" trong comment.
Khi bạn tự viết code đụng `dms.directory`, phải tính đến điều này.

## Cập nhật DMS từ upstream

```bash
git subtree pull --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash
```

Xung đột sẽ rơi đúng vào những chỗ ta đã patch — xem bảng "Patch đã áp"
trong `extra-addons/README.md`. `custom-addons/aidt_dms/` không bị ảnh hưởng.

Khi OCA phát hành branch 19.0 chính thức, đối chiếu bảng đó để bỏ những
patch đã được upstream giải quyết, rồi đổi branch nguồn thành `19.0`.
