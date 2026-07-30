from odoo import api, fields, models

_SECRECY_LEVEL = {'thuong': 0, 'mat': 1, 'toi_mat': 2, 'tuyet_mat': 3}


class AidtDocument(models.Model):
    _name = 'aidt.document'
    _description = 'Văn bản'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Trích yếu', required=True, tracking=True)
    reference = fields.Char(string='Số/Ký hiệu')
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị', required=True, index=True,
        default=lambda self: self.env.user.employee_id.department_id)
    shared_user_ids = fields.Many2many('res.users', string='Chia sẻ với')
    doc_type = fields.Selection(
        [('cong_van', 'Công văn'), ('bao_cao', 'Báo cáo'),
         ('ke_hoach', 'Kế hoạch'), ('quyet_dinh', 'Quyết định'),
         ('thong_bao', 'Thông báo'), ('ket_luan', 'Kết luận'),
         ('nghi_quyet', 'Nghị quyết'), ('to_trinh', 'Tờ trình'),
         ('giay_moi', 'Giấy mời')],
        string='Loại văn bản', default='cong_van', tracking=True)
    date = fields.Date(string='Ngày ban hành')
    direction = fields.Selection(
        [('den', 'Văn bản đến'), ('di', 'Văn bản đi')],
        string='Hướng', required=True, default='den', tracking=True)
    state = fields.Selection(
        [('draft', 'Dự thảo'), ('issued', 'Đã ban hành'), ('archived', 'Lưu trữ')],
        string='Trạng thái', default='draft', tracking=True)
    secrecy = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật', required=True, default='thuong', tracking=True)
    secrecy_level = fields.Integer(
        string='Mức mật', compute='_compute_secrecy_level',
        store=True, index=True)

    @api.depends('secrecy')
    def _compute_secrecy_level(self):
        for doc in self:
            doc.secrecy_level = _SECRECY_LEVEL.get(doc.secrecy, 0)

    def action_issue(self):
        self.write({'state': 'issued'})

    def action_archive_doc(self):
        self.write({'state': 'archived'})
