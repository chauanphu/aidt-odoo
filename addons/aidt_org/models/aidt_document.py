from odoo import fields, models


class AidtDocument(models.Model):
    _name = 'aidt.document'
    _description = 'Văn bản'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Trích yếu', required=True, tracking=True)
    reference = fields.Char(string='Số/Ký hiệu')
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị', required=True, index=True)
    shared_user_ids = fields.Many2many('res.users', string='Chia sẻ với')
    doc_type = fields.Selection(
        [('cong_van', 'Công văn'), ('bao_cao', 'Báo cáo'),
         ('ke_hoach', 'Kế hoạch'), ('quyet_dinh', 'Quyết định')],
        string='Loại văn bản', default='cong_van')
    date = fields.Date(string='Ngày ban hành')
    state = fields.Selection(
        [('draft', 'Dự thảo'), ('issued', 'Đã ban hành'), ('archived', 'Lưu trữ')],
        string='Trạng thái', default='draft', tracking=True)
