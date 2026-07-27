from odoo import fields, models


class AidtTaskResult(models.Model):
    _name = 'aidt.task.result'
    _description = 'Báo cáo kết quả nhiệm vụ'
    _order = 'submit_date desc, id desc'

    task_id = fields.Many2one(
        'aidt.task', string='Nhiệm vụ', required=True,
        ondelete='cascade', index=True)
    report = fields.Text(string='Nội dung báo cáo')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='File minh chứng')
    submit_uid = fields.Many2one(
        'res.users', string='Người báo cáo',
        default=lambda self: self.env.user)
    submit_date = fields.Datetime(
        string='Thời điểm báo cáo', default=fields.Datetime.now)
    # Kế thừa mức mật của nhiệm vụ để ir.rule chặn rò rỉ (N-04/V-13).
    secrecy_level = fields.Integer(
        related='task_id.secrecy_level', store=True, index=True,
        string='Mức mật')
