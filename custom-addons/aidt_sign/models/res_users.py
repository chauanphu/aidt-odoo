from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    digital_signature_img = fields.Binary(string='Ảnh chữ ký tay tươi')
    certificate_ids = fields.One2many('aidt.sign.certificate', 'owner_id', string='Chứng thư số cá nhân')
    pin = fields.Char(groups='hr.group_hr_user')
