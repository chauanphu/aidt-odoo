"""Cho phép nạp lại các ir.rule của aidt_calendar khi nâng cấp.

Cùng nguyên nhân với aidt_org: cờ `noupdate` được ghi vào từng bản ghi
`ir_model_data`, nên gỡ thuộc tính trong file XML là chưa đủ — `_load_records()`
vẫn đọc cờ đã lưu (odoo/orm/models.py:5165) và bỏ qua bản ghi. Không xoá cờ thì
mọi thay đổi `domain_force` về sau sẽ không bao giờ tới được CSDL production.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'aidt_calendar'
           AND model = 'ir.rule'
           AND noupdate
    """)
