import base64
from odoo import models, fields, _
from odoo.exceptions import UserError


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    format_ok = fields.Boolean(string='Thể thức đạt', default=False, readonly=True)
    format_note = fields.Text(string='Ghi chú thể thức', readonly=True)

    def _auto_check_format(self):
        for rec in self:
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id),
                '|',
                ('name', '=like', '%.docx'),
                ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ], order='id desc', limit=1)

            if not attachment:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Chưa có tệp đính kèm .docx để kiểm tra thể thức.")
                })
                continue

            ruleset = self.env['aidt.format.ruleset'].search([('active', '=', True)], limit=1)
            if not ruleset:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Chưa có bộ quy tắc thể thức nào đang kích hoạt.")
                })
                continue

            try:
                content = base64.b64decode(attachment.datas or b'')
                findings = self.env['aidt.format.checker'].check(content, ruleset)
                errors = [f for f in findings if f.get('severity') == 'error']
                warnings = [f for f in findings if f.get('severity') == 'warning']

                is_ok = len(errors) == 0
                summary_lines = []
                if is_ok:
                    summary_lines.append(_("Đạt thể thức (%d lỗi chặn, %d cảnh báo)") % (len(errors), len(warnings)))
                else:
                    summary_lines.append(_("Không đạt thể thức (%d lỗi chặn, %d cảnh báo):") % (len(errors), len(warnings)))

                for idx, item in enumerate(errors + warnings, 1):
                    sev = _("[LỖI CHẶN]") if item.get('severity') == 'error' else _("[CẢNH BÁO]")
                    loc = f" (Vị trí: {item.get('location')})" if item.get('location') else ""
                    sug = f" -> Gợi ý: {item.get('suggestion')}" if item.get('suggestion') else ""
                    summary_lines.append(f"{idx}. {sev} {item.get('rule_id') or ''}{loc}{sug}")

                rec.sudo().write({
                    'format_ok': is_ok,
                    'format_note': "\n".join(summary_lines)
                })
            except Exception as e:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Lỗi khi kiểm tra thể thức tệp: %s") % str(e)
                })

    def action_check_format(self):
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'aidt.document'),
            ('res_id', '=', self.id),
            '|',
            ('name', '=like', '%.docx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        ], order='id desc', limit=1)

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

