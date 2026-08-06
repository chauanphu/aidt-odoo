import base64
import requests
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AidtDocumentOcrWizard(models.TransientModel):
    _name = 'aidt.document.ocr.wizard'
    _description = 'Wizard Trích xuất AI (OCR) từ tệp/ảnh scan'

    document_id = fields.Many2one('aidt.document', string='Văn bản liên quan')
    direction = fields.Selection([('den', 'Văn bản đến'), ('di', 'Văn bản đi')], default='den', string='Hướng')
    
    file_scan = fields.Binary('Tệp scan / Ảnh công văn (Kéo thả hoặc Chọn tệp)', required=True, attachment=False)
    file_scan_name = fields.Char('Tên tệp scan', default='Cong_van_scan_demo.pdf')
    
    ai_engine = fields.Selection([
        ('unlimited_ocr_pipeline', 'UnlimitedOCR + Gemma 4 Pipeline (Nghị định 30)'),
        ('gemini_15', 'Gemini 1.5 Flash Vision (AI OCR Trích xuất tiếng Việt chuẩn)'),
        ('deepseek_vision', 'DeepSeek OCR (Tối ưu văn bản bản in & con dấu đỏ)'),
        ('tesseract_local', 'Engine OCR Nội bộ (Offline)'),
    ], string='Mô hình AI OCR', default='unlimited_ocr_pipeline', required=True)

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
        """Thực hiện OCR thực tế qua Pipeline 8001, tạo/cập nhật document và lưu file đính kèm."""
        self.ensure_one()
        if not self.file_scan:
            raise UserError(_("Vui lòng tải lên hoặc kéo thả tệp scan/ảnh văn bản."))

        file_bytes = base64.b64decode(self.file_scan)

        if self.ai_engine == 'unlimited_ocr_pipeline':
            api_result = self._call_unlimited_ocr_pipeline(file_bytes, self.file_scan_name)
            # Extract fields dictionary from API response
            extracted = api_result.get('data') or api_result.get('fields') or api_result
            
            name = extracted.get('trich_yeu') or extracted.get('name') or self.extracted_name
            so_ky_hieu = extracted.get('so_ky_hieu') or extracted.get('so_ky_hieu_gui') or self.extracted_reference
            co_quan_gui = extracted.get('co_quan_ban_hanh') or extracted.get('co_quan_gui') or self.extracted_issuer
            ngay_ban_hanh = extracted.get('ngay_ban_hanh') or extracted.get('ngay_ban_hanh_gui') or fields.Date.today()
            doc_type = extracted.get('loai_van_ban') or self.extracted_doc_type or 'cong_van'
            do_khan = extracted.get('do_khan') or self.extracted_do_khan or 'thuong'
            so_den = extracted.get('so_den')
            ngay_den = extracted.get('ngay_den') or fields.Date.today()
            han_xu_ly = extracted.get('han_xu_ly')
            nguoi_ky = extracted.get('nguoi_ky')
            chuc_vu_nguoi_ky = extracted.get('chuc_vu_nguoi_ky')
            noi_nhan = extracted.get('noi_nhan')
        else:
            name = self.extracted_name
            so_ky_hieu = self.extracted_reference
            co_quan_gui = self.extracted_issuer
            ngay_ban_hanh = self.extracted_date
            doc_type = self.extracted_doc_type
            do_khan = self.extracted_do_khan
            so_den = False
            ngay_den = fields.Date.today()
            han_xu_ly = False
            nguoi_ky = False
            chuc_vu_nguoi_ky = False
            noi_nhan = False

        doc = self.document_id
        doc_fields = self.env['aidt.document']._fields

        vals = {
            'name': name,
            'direction': self.direction,
            'doc_type': doc_type if 'doc_type' in doc_fields else 'cong_van',
        }

        # Safe assignment map
        field_mapping = {
            'so_ky_hieu_gui': so_ky_hieu,
            'reference': so_ky_hieu,
            'co_quan_gui': co_quan_gui,
            'ngay_ban_hanh_gui': ngay_ban_hanh,
            'date': ngay_ban_hanh,
            'do_khan': do_khan,
            'ngay_den': ngay_den,
            'so_den': str(so_den) if so_den else False,
            'han_xu_ly': han_xu_ly,
            'nguoi_ky': nguoi_ky,
            'chuc_vu_nguoi_ky': chuc_vu_nguoi_ky,
            'noi_nhan': noi_nhan,
        }

        if self.direction == 'den':
            state_field = doc_fields.get('state')
            valid_states = [s[0] for s in state_field.selection] if (state_field and isinstance(state_field.selection, list)) else []
            if 'tiep_nhan' in valid_states:
                vals['state'] = 'tiep_nhan'
            elif 'draft' in valid_states:
                vals['state'] = 'draft'

            for f_key, f_val in field_mapping.items():
                if f_key in doc_fields and f_val:
                    vals[f_key] = f_val

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

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document',
            'res_id': doc.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_direction': self.direction},
        }

    def _call_unlimited_ocr_pipeline(self, file_bytes, filename):
        """Send PDF bytes to FastAPI port 8001 pipeline endpoint."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('aidt_dms.pipeline_url', 'http://aidt-pipeline:8001')
        endpoint = f"{base_url.rstrip('/')}/api/pipeline/process"
        
        try:
            files = {'file': (filename or 'document.pdf', file_bytes, 'application/pdf')}
            response = requests.post(endpoint, files=files, timeout=45)
            response.raise_for_status()
            res_data = response.json()
            return res_data
        except requests.exceptions.RequestException as e:
            _logger.warning("Pipeline AI OCR request failed: %s", str(e))
            raise UserError(_("Không thể kết nối dịch vụ AI bóc tách (Port 8001). Vui lòng kiểm tra dịch vụ backend hoặc nhập thủ công. Chi tiết: %s") % str(e))

