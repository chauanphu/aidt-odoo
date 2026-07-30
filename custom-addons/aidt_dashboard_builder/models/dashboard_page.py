from odoo import fields, models


class DynamicDashboardPage(models.Model):
    _name = 'dynamic.dashboard.page'
    _description = 'Dynamic Dashboard Page (Tab)'
    _order = 'sequence, id'

    name = fields.Char(string='Tên trang/tab', required=True)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade', index=True
    )
    sequence = fields.Integer(string='Thứ tự', default=10)
    icon = fields.Char(string='Icon (FontAwesome/Odoo icon)', default='fa-tachometer')
    widget_ids = fields.One2many('dynamic.dashboard.widget', 'page_id', string='Widgets trong trang')
