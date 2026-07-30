from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DynamicDashboardUserLayout(models.Model):
    _name = 'dynamic.dashboard.user.layout'
    _description = 'User Personalized Dashboard Layout'
    _rec_name = 'dashboard_id'

    user_id = fields.Many2one(
        'res.users', string='Người dùng', required=True, default=lambda self: self.env.user, ondelete='cascade', index=True
    )
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade', index=True
    )
    layout_json = fields.Text(string='Cấu hình Layout cá nhân (JSON)', default='{}')

    @api.constrains('user_id', 'dashboard_id')
    def _check_user_dashboard_uniq(self):
        for rec in self:
            domain = [
                ('user_id', '=', rec.user_id.id),
                ('dashboard_id', '=', rec.dashboard_id.id),
                ('id', '!=', rec.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError('Mỗi người dùng chỉ có 1 bản lưu layout cho mỗi Dashboard!')
