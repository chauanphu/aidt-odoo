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

    upload_file = fields.Binary('Tải tệp đính kèm', attachment=False)
    upload_filename = fields.Char('Tên tệp đính kèm')

    def action_save_upload_file(self):
        """Tạo dms.file từ upload_file."""
        for doc in self:
            if doc.upload_file and doc.directory_id:
                self.env['dms.file'].sudo().create({
                    'name': doc.upload_filename or 'Tep_dinh_kem.pdf',
                    'directory_id': doc.directory_id.id,
                    'content': doc.upload_file,
                    'res_model': 'aidt.document',
                    'res_id': doc.id,
                })
                doc.write({'upload_file': False, 'upload_filename': False})

    def action_ocr_extract(self):
        """Demo AI OCR: Trích xuất tự động thông tin từ văn bản scan/giấy."""
        for doc in self:
            vals = {}
            if not doc.name or doc.name == 'New':
                vals['name'] = 'Công văn v/v phối hợp công tác kiểm tra an toàn hệ thống thông tin năm 2026 (Trích xuất từ AI OCR)'
            if hasattr(doc, 'so_ky_hieu_gui') and not doc.so_ky_hieu_gui:
                vals['so_ky_hieu_gui'] = '185/CV-STTTT'
            if hasattr(doc, 'co_quan_gui') and not doc.co_quan_gui:
                vals['co_quan_gui'] = 'Sở Thông tin và Truyền thông'
            if hasattr(doc, 'ngay_ban_hanh_gui') and not doc.ngay_ban_hanh_gui:
                vals['ngay_ban_hanh_gui'] = fields.Date.today()
            if hasattr(doc, 'do_khan') and not doc.do_khan:
                vals['do_khan'] = 'khan'
            if vals:
                doc.write(vals)

            if doc.upload_file:
                doc.action_save_upload_file()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'AI OCR Trích xuất thành công!',
                'message': 'Đã tự động nhận diện & điền các trường: Trích yếu, Số ký hiệu gốc, Cơ quan gửi, Ngày ban hành!',
                'type': 'success',
                'sticky': False,
            }
        }

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
            if doc.upload_file:
                doc.action_save_upload_file()
        return docs

    def write(self, vals):
        res = super().write(vals)
        if {'reference', 'name'} & set(vals):
            for doc in self.filtered('directory_id'):
                doc.directory_id.sudo().name = doc._dir_name()
        if 'upload_file' in vals and vals['upload_file']:
            self.action_save_upload_file()
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
