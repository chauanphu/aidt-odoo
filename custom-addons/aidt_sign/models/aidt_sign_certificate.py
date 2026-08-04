from odoo import models, fields

class AidtSignCertificate(models.Model):
    _name = 'aidt.sign.certificate'
    _description = 'Chứng thư số PKCS#12'

    name = fields.Char(string='Tên chứng thư', required=True)
    cert_file = fields.Binary(string='Tệp chứng thư (.p12/.pfx)', required=True)
    cert_filename = fields.Char(string='Tên tệp')
    password = fields.Char(string='Mật khẩu mở chứng thư', required=True)
    cert_type = fields.Selection([
        ('personal', 'Chữ ký số cá nhân (Lãnh đạo)'),
        ('org', 'Chữ ký số tổ chức (Con dấu cơ quan)')
    ], string='Loại chứng thư', default='personal', required=True)
    owner_id = fields.Many2one('res.users', string='Người sở hữu')
    active = fields.Boolean(default=True)
