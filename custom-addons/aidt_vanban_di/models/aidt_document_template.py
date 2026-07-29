from odoo import fields, models

class AidtDocumentTemplate(models.Model):
    _name = 'aidt.document.template'
    _description = 'Mẫu văn bản đi (DOCX Template)'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Thứ tự', default=10)
    name = fields.Char(string='Tên mẫu văn bản', required=True)
    doc_type = fields.Selection([
        ('cong_van', 'Công văn'),
        ('bao_cao', 'Báo cáo'),
        ('ke_hoach', 'Kế hoạch'),
        ('quyet_dinh', 'Quyết định'),
        ('thong_bao', 'Thông báo'),
        ('ket_luan', 'Kết luận'),
        ('nghi_quyet', 'Nghị quyết'),
        ('to_trinh', 'Tờ trình'),
        ('giay_moi', 'Giấy mời'),
    ], string='Loại văn bản', required=True, default='cong_van')
    description = fields.Text(string='Mô tả / Ghi chú')
    file_template = fields.Binary(string='Tệp DOCX mẫu', required=True, attachment=True)
    file_name = fields.Char(string='Tên tệp')
    active = fields.Boolean(string='Hoạt động', default=True)
