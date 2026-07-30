from odoo import fields, models


class DynamicDashboardFilter(models.Model):
    _name = 'dynamic.dashboard.filter'
    _description = 'Dynamic Dashboard Global Filter'
    _order = 'sequence, id'

    name = fields.Char(string='Tên Bộ Lọc', required=True)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade', index=True
    )
    sequence = fields.Integer(string='Thứ tự', default=10)

    filter_type = fields.Selection([
        ('date_range', 'Khoảng thời gian (Date Range)'),
        ('company', 'Công ty (Company)'),
        ('department', 'Phòng ban (Department)'),
        ('selection', 'Lựa chọn tĩnh (Selection)'),
        ('many2one', 'Liên kết dữ liệu (Many2one)')
    ], string='Loại Bộ Lọc', required=True, default='date_range')

    target_model_id = fields.Many2one('ir.model', string='Model liên kết (với loại Many2one)')
    default_value_json = fields.Text(string='Giá trị mặc định (JSON)', default='{}')
    required = fields.Boolean(string='Bắt buộc nhập', default=False)
    binding_ids = fields.One2many('dynamic.dashboard.filter.binding', 'filter_id', string='Ánh xạ Widgets')
