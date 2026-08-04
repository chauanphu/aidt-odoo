from odoo import models, fields

class AidtSignLog(models.Model):
    _name = 'aidt.sign.log'
    _description = 'Nhật ký Ký số PAdES'
    _order = 'create_date desc'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Many2oneReference(string='ID Bản ghi', model_field='res_model', required=True)
    user_id = fields.Many2one('res.users', string='Người ký', default=lambda self: self.env.user)
    sign_type = fields.Selection([
        ('leader', 'Ký Lãnh đạo'),
        ('org', 'Đóng dấu Cơ quan')
    ], string='Loại ký', required=True)
    cert_name = fields.Char(string='Chứng thư số sử dụng')
    signed_date = fields.Datetime(string='Thời điểm ký', default=fields.Datetime.now)
    digest_sha256 = fields.Char(string='Mã băm SHA-256')
