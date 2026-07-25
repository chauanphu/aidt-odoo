from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    directory_id = fields.Many2one(
        'dms.directory', string='Thư mục lưu trữ',
        readonly=True, copy=False, ondelete='set null')
    file_ids = fields.One2many(
        related='directory_id.file_ids', string='Tệp đính kèm', readonly=True)
    file_count = fields.Integer(
        string='Số tệp', compute='_compute_file_count')

    @api.depends('file_ids')
    def _compute_file_count(self):
        for doc in self:
            doc.file_count = len(doc.file_ids)

    def action_open_files(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dms.file',
            'name': 'Tệp: %s' % self.name,
            'view_mode': 'list,kanban,form',
            'domain': [('directory_id', '=', self.directory_id.id)],
            'context': {'default_directory_id': self.directory_id.id},
        }

    def _dir_name(self):
        """Tên thư mục hợp lệ: bỏ '/' và NUL (check_name của DMS từ chối '/'),
        ưu tiên số ký hiệu, thêm id để duy nhất."""
        self.ensure_one()
        base = (self.reference or self.name or 'VB')
        base = base.replace('/', '-').replace('\x00', '').strip() or 'VB'
        return f"{base} [{self.id}]"

    @api.model_create_multi
    def create(self, vals_list):
        docs = super().create(vals_list)
        root = self.env.ref('aidt_dms.directory_root_aidt')
        Directory = self.env['dms.directory'].sudo()
        for doc in docs:
            directory = Directory.create({
                'name': doc._dir_name(),
                'parent_id': root.id,
                'res_model': 'aidt.document',
                'res_id': doc.id,
            })
            doc.directory_id = directory.id
        return docs

    def write(self, vals):
        res = super().write(vals)
        if {'reference', 'name'} & set(vals):
            for doc in self.filtered('directory_id'):
                doc.directory_id.sudo().name = doc._dir_name()
        return res

    def unlink(self):
        for doc in self.filtered('directory_id'):
            if doc.directory_id.sudo().file_ids:
                raise UserError(_(
                    "Không thể xóa văn bản '%s' vì còn tệp đính kèm. "
                    "Hãy chuyển sang trạng thái Lưu trữ.", doc.name))
        directories = self.directory_id
        res = super().unlink()
        directories.sudo().unlink()
        return res
