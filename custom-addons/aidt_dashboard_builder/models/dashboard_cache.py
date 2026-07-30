from odoo import fields, models


class DynamicDashboardCache(models.Model):
    _name = 'dynamic.dashboard.cache'
    _description = 'Dynamic Dashboard Query Cache'

    cache_key = fields.Char(string='Khóa Cache (Hash)', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Người dùng', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Công ty', index=True)
    result_json = fields.Text(string='Dữ liệu Cache (JSON)', required=True)
    expires_at = fields.Datetime(string='Thời gian hết hạn', required=True, index=True)
