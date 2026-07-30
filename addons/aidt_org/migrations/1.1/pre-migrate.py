"""Cho phép nạp lại các ir.rule của aidt_org khi nâng cấp.

Trước đây `security/aidt_org_rules.xml` mang `noupdate="1"`. Cờ này được ghi vào
từng bản ghi `ir_model_data`, nên chỉ gỡ thuộc tính trong file XML là chưa đủ:
`models._load_records()` vẫn đọc cờ đã lưu trong CSDL (odoo/orm/models.py:5165,
`if not (update and d_noupdate)`) và bỏ qua bản ghi. Hệ quả: mọi thay đổi
`domain_force` không bao giờ tới được CSDL đã cài — một bản vá siết quyền sẽ âm
thầm không có hiệu lực trên production.

Script chạy ở `pre-migrate`, tức trước khi các file dữ liệu của module được nạp,
nên sau khi xoá cờ thì lượt nạp ngay sau đó sẽ ghi đè domain mới.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'aidt_org'
           AND model = 'ir.rule'
           AND noupdate
    """)
