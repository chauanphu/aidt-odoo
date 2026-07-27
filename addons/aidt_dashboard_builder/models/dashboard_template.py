from odoo import fields, models


class DynamicDashboardTemplate(models.Model):
    _name = 'dynamic.dashboard.template'
    _description = 'Dynamic Dashboard Preset Template'

    name = fields.Char(string='Tên Mẫu (Template)', required=True)
    category = fields.Char(string='Phân loại', default='General')
    dashboard_config_json = fields.Text(string='Cấu hình mẫu (JSON)', required=True)
    required_module_ids = fields.Many2many('ir.module.module', string='Các module phụ thuộc')
    preview_image = fields.Binary(string='Ảnh xem trước')
