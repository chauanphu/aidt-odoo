from odoo import api, models

# Ba trường này nằm trong contextual header nên đã được embed vào vector.
# Đổi mà không nạp lại thì header lệch thực tế.
HEADER_FIELDS = {'reference', 'name', 'doc_type'}


class DmsFile(models.Model):
    _inherit = 'dms.file'

    @api.model_create_multi
    def create(self, vals_list):
        files = super().create(vals_list)
        for dms_file in files:
            self.env['aidt.index.job']._enqueue_file(dms_file)
        return files

    def write(self, vals):
        res = super().write(vals)
        if 'content' in vals:
            for dms_file in self:
                self.env['aidt.index.job']._enqueue_file(dms_file)
        return res


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    def write(self, vals):
        res = super().write(vals)
        if HEADER_FIELDS & set(vals):
            self.env['aidt.index.job']._enqueue_document(self)
        return res
