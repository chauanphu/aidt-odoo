from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AidtDocumentOcrWizard(models.TransientModel):
    _name = 'aidt.document.ocr.wizard'
    _description = 'Wizard Trích xuất AI (OCR) từ tệp/ảnh scan'

    document_id = fields.Many2one('aidt.document', string='Văn bản liên quan')
    direction = fields.Selection([('den', 'Văn bản đến'), ('di', 'Văn bản đi')], default='den', string='Hướng')
    
    file_scan = fields.Binary('Tệp scan / Ảnh công văn (Kéo thả hoặc Chọn tệp)', required=True, attachment=False)
    file_scan_name = fields.Char('Tên tệp scan', default='Cong_van_scan_demo.pdf')
    
    ai_engine = fields.Selection([
        ('gemini_15', 'Gemini 1.5 Flash Vision (AI OCR Trích xuất tiếng Việt chuẩn)'),
        ('deepseek_vision', 'DeepSeek OCR (Tối ưu văn bản bản in & con dấu đỏ)'),
        ('tesseract_local', 'Engine OCR Nội bộ (Offline)'),
    ], string='Mô hình AI OCR', default='gemini_15', required=True)

    # Simulated AI Extracted Preview Fields
    extracted_name = fields.Char(
        'Trích yếu nhận diện (AI OCR)', 
        default='Công văn v/v triển khai Kế hoạch bảo đảm an toàn hệ thống thông tin Tỉnh năm 2026'
    )
    extracted_reference = fields.Char('Số ký hiệu gốc nhận diện', default='185/CV-STTTT')
    extracted_issuer = fields.Char('Cơ quan gửi nhận diện', default='Sở Thông tin và Truyền thông')
    extracted_date = fields.Date('Ngày ban hành gốc nhận diện', default=fields.Date.today)
    extracted_doc_type = fields.Selection([
        ('cong_van', 'Công văn'), ('bao_cao', 'Báo cáo'),
        ('ke_hoach', 'Kế hoạch'), ('quyet_dinh', 'Quyết định'),
        ('thong_bao', 'Thông báo'), ('to_trinh', 'Tờ trình'),
    ], string='Loại văn bản', default='cong_van')
    extracted_do_khan = fields.Selection([
        ('thuong', 'Thường'), ('khan', 'Khẩn'),
        ('thuong_khan', 'Thượng khẩn'), ('hoa_toc', 'Hỏa tốc'),
    ], string='Độ khẩn', default='khan')

    def action_start_ocr(self):
        """Thực hiện giả lập OCR, tạo/cập nhật document và lưu file đính kèm."""
        self.ensure_one()
        if not self.file_scan:
            raise UserError(_("Vui lòng tải lên hoặc kéo thả tệp scan/ảnh văn bản."))

        doc = self.document_id
        vals = {
            'name': self.extracted_name,
            'direction': self.direction,
            'doc_type': self.extracted_doc_type,
        }
        if self.direction == 'den':
            vals.update({
                'so_ky_hieu_gui': self.extracted_reference,
                'co_quan_gui': self.extracted_issuer,
                'ngay_ban_hanh_gui': self.extracted_date,
                'do_khan': self.extracted_do_khan,
                'state': 'tiep_nhan',
            })

        if doc:
            doc.write(vals)
        else:
            doc = self.env['aidt.document'].create(vals)

        # Save uploaded file scan to DMS directory
        if doc.directory_id and self.file_scan:
            self.env['dms.file'].sudo().create({
                'name': self.file_scan_name or 'Cong_van_scan.pdf',
                'directory_id': doc.directory_id.id,
                'content': self.file_scan,
                'res_model': 'aidt.document',
                'res_id': doc.id,
            })

        # Return client notification and reload form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document',
            'res_id': doc.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_direction': self.direction},
        }
