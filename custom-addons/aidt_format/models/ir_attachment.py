from odoo import models, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        doc_ids = set()
        for rec in records:
            if rec.res_model == 'aidt.document' and rec.res_id and (
                (rec.name and rec.name.lower().endswith('.docx')) or
                rec.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ):
                doc_ids.add(rec.res_id)
        if doc_ids:
            self.env['aidt.document'].browse(list(doc_ids))._auto_check_format()
        return records

    def write(self, vals):
        res = super().write(vals)
        doc_ids = set()
        for rec in self:
            if rec.res_model == 'aidt.document' and rec.res_id and (
                (rec.name and rec.name.lower().endswith('.docx')) or
                rec.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ):
                doc_ids.add(rec.res_id)
        if doc_ids:
            self.env['aidt.document'].browse(list(doc_ids))._auto_check_format()
        return res
