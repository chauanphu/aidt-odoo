from odoo import models, fields, _
from odoo.exceptions import UserError


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    def action_check_format(self):
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'aidt.document'),
            ('res_id', '=', self.id),
            '|',
            ('name', '=like', '%.docx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        ], limit=1)

        if not attachment:
            raise UserError(_("Vui lòng đính kèm tệp văn bản định dạng .docx trước khi kiểm tra thể thức."))

        ruleset = self.env['aidt.format.ruleset'].search([('active', '=', True)], limit=1)

        wizard = self.env['aidt.format.check.wizard'].create({
            'docx_file': attachment.datas,
            'filename': attachment.name,
            'ruleset_id': ruleset.id if ruleset else False,
        })

        return {
            'name': _("Kiểm tra thể thức văn bản"),
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.format.check.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
