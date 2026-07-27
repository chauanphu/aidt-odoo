from odoo import api, fields, models


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    task_ids = fields.One2many(
        'aidt.task', 'document_id', string='Nhiệm vụ bóc tách')
    task_count = fields.Integer(
        string='Số nhiệm vụ', compute='_compute_task_count')

    @api.depends('task_ids')
    def _compute_task_count(self):
        for doc in self:
            doc.task_count = len(doc.task_ids)

    def action_extract_tasks(self):
        """Màn bóc tách nhiệm vụ (T-05): mở nhiệm vụ của văn bản này, prefill
        đơn vị + độ mật. Đây là chỗ AI (T-01→T-04) sẽ điền sẵn sau."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nhiệm vụ: %s' % (self.reference or self.name),
            'res_model': 'aidt.task',
            'view_mode': 'list,form',
            'domain': [('document_id', '=', self.id)],
            'context': {
                'default_document_id': self.id,
                'default_department_id': self.department_id.id,
                'default_secrecy': self.secrecy,
            },
        }
