from odoo import api, fields, models


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    index_state = fields.Selection(
        [('none', 'Chưa nạp'), ('pending', 'Đang xử lý'),
         ('indexed', 'Đã chỉ mục'), ('failed', 'Lỗi chỉ mục')],
        string='Trạng thái chỉ mục', compute='_compute_index_state', store=True)
    chunk_count = fields.Integer(string='Số đoạn', compute='_compute_chunk_count')

    @api.depends('directory_id.file_ids')
    def _compute_index_state(self):
        Job = self.env['aidt.index.job'].sudo()
        for doc in self:
            states = set(Job.search([('document_id', '=', doc.id)]).mapped('state'))
            if not states:
                doc.index_state = 'none'
                continue
            if 'failed' in states:
                doc.index_state = 'failed'
            elif states - {'done'}:
                doc.index_state = 'pending'
            else:
                doc.index_state = 'indexed'

    def _compute_chunk_count(self):
        Chunk = self.env['aidt.doc.chunk'].sudo()
        for doc in self:
            doc.chunk_count = Chunk.search_count([('document_id', '=', doc.id)])

    def action_reindex(self):
        """Nạp lại chỉ mục cho mọi tệp của văn bản.

        `_enqueue_document` chạy sudo bên trong (nó phải đọc dms.file), nên
        không có kiểm tra quyền nào tự xảy ra trên đường đi: thiếu dòng dưới
        đây thì bất kỳ ai chỉ có quyền ĐỌC văn bản cũng xếp được việc GPU cho
        toàn bộ tệp của nó, lặp bao nhiêu lần tuỳ thích. Nạp lại chỉ mục là
        thao tác sửa dữ liệu dẫn xuất của văn bản -> đòi quyền 'write'.
        """
        self.check_access('write')
        self.env['aidt.index.job']._enqueue_document(self)
        return True
