from odoo import fields, models


class DynamicDashboardFilterBinding(models.Model):
    _name = 'dynamic.dashboard.filter.binding'
    _description = 'Dynamic Dashboard Filter Binding to Widget Field'

    filter_id = fields.Many2one(
        'dynamic.dashboard.filter', string='Bộ Lọc', required=True, ondelete='cascade', index=True
    )
    widget_id = fields.Many2one(
        'dynamic.dashboard.widget', string='Widget áp dụng', required=True, ondelete='cascade', index=True
    )
    field_id = fields.Many2one(
        'ir.model.fields', string='Trường dữ liệu (Field)', required=True, ondelete='cascade'
    )
    field_name = fields.Char(string='Tên trường dữ liệu', related='field_id.name', store=True)
    operator = fields.Char(string='Toán tử so sánh', default='=')
    transform_type = fields.Selection([
        ('none', 'Giữ nguyên'),
        ('start_of_day', 'Đầu ngày'),
        ('end_of_day', 'Cuối ngày')
    ], string='Chuyển đổi dữ liệu', default='none')
