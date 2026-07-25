import base64

from odoo import _, api, fields, models


class AidtFormatCheckWizard(models.TransientModel):
    _name = 'aidt.format.check.wizard'
    _description = 'Kiểm tra thể thức văn bản'

    docx_file = fields.Binary(string='Tệp .docx', required=True)
    filename = fields.Char(string='Tên tệp')
    ruleset_id = fields.Many2one(
        'aidt.format.ruleset', string='Bộ luật', required=True,
        domain=[('active', '=', True)],
        default=lambda self: self._default_ruleset_id())
    line_ids = fields.One2many(
        'aidt.format.check.line', 'wizard_id', string='Phát hiện',
        readonly=True)
    da_kiem = fields.Boolean(string='Đã kiểm', default=False)
    so_loi = fields.Integer(
        string='Số lỗi chặn', compute='_compute_so_luong')
    so_canh_bao = fields.Integer(
        string='Số cảnh báo', compute='_compute_so_luong')

    def _default_ruleset_id(self):
        return self.env['aidt.format.ruleset'].search(
            [('active', '=', True)], limit=1)

    @api.depends('line_ids.severity')
    def _compute_so_luong(self):
        for wizard in self:
            wizard.so_loi = len(
                wizard.line_ids.filtered(lambda l: l.severity == 'error'))
            wizard.so_canh_bao = len(
                wizard.line_ids.filtered(lambda l: l.severity == 'warning'))

    def action_kiem_tra(self):
        self.ensure_one()
        noi_dung = base64.b64decode(self.docx_file or b'')
        findings = self.env['aidt.format.checker'].check(
            noi_dung, self.ruleset_id)
        self.line_ids.unlink()
        self.line_ids = [
            (0, 0, {
                'rule_id': f['rule_id'],
                'severity': f['severity'],
                'zone': f['zone'],
                'location': f['location'],
                'expected': f['expected'],
                'actual': f['actual'],
                'suggestion': f['suggestion'],
            }) for f in findings
        ]
        self.da_kiem = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class AidtFormatCheckLine(models.TransientModel):
    _name = 'aidt.format.check.line'
    _description = 'Phát hiện thể thức'
    _order = "severity, id"

    wizard_id = fields.Many2one(
        'aidt.format.check.wizard', string='Wizard',
        required=True, ondelete='cascade')
    rule_id = fields.Char(string='Mã quy tắc')
    severity = fields.Selection(
        [('error', 'Lỗi chặn'), ('warning', 'Cảnh báo')],
        string='Mức độ')
    zone = fields.Char(string='Vùng')
    location = fields.Char(string='Vị trí')
    expected = fields.Char(string='Cần')
    actual = fields.Char(string='Đang')
    suggestion = fields.Char(string='Gợi ý sửa')
