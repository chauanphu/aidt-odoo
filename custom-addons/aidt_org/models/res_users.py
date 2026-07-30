from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    clearance_level = fields.Integer(
        string='Mức mật được duyệt', default=0,
        help='0=Thường, 1=Mật, 2=Tối mật, 3=Tuyệt mật. '
             'Chỉ quản trị viên đặt được; người dùng không tự sửa.')
