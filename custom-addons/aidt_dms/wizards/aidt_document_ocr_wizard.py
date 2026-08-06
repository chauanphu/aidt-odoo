import base64
import requests
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from datetime import datetime, date

_logger = logging.getLogger(__name__)

def _parse_date(val):
    if not val:
        return False
    if isinstance(val, (date, datetime)):
        return val
    if not isinstance(val, str):
        return False
    val = val.strip()
    if not val or val.lower() in ('không có', 'khong co', 'none', 'null', 'false', 'n/a'):
        return False
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return False

def _clean_str(val):
    if not val or not isinstance(val, str):
        return val
    val = val.strip()
    if val.lower() in ('không có', 'khong co', 'none', 'null', 'n/a'):
        return False
    return val

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

    state = fields.Selection([('draft', 'Chọn tệp'), ('preview', 'Xem trước')], default='draft', string='Trạng thái')

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
    extracted_so_den = fields.Char('Số đến nhận diện')
    extracted_ngay_den = fields.Date('Ngày đến nhận diện', default=fields.Date.today)
    extracted_han_xu_ly = fields.Date('Hạn xử lý nhận diện')
    extracted_nguoi_ky = fields.Char('Người ký nhận diện')
    extracted_chuc_vu_nguoi_ky = fields.Char('Chức vụ người ký nhận diện')
    extracted_noi_nhan = fields.Text('Nơi nhận nhận diện')

    def action_run_ai_ocr(self):
        """Bước 1: Gọi AI Pipeline bóc tách và nạp thông tin vào Preview Wizard."""
        self.ensure_one()
        if not self.file_scan:
            raise UserError(_("Vui lòng tải lên hoặc kéo thả tệp scan/ảnh văn bản."))

        file_bytes = base64.b64decode(self.file_scan)

        if self.ai_engine == 'unlimited_ocr_pipeline':
            api_result = self._call_unlimited_ocr_pipeline(file_bytes, self.file_scan_name)
            extracted = api_result.get('data') or api_result.get('fields') or api_result
            
            self.extracted_name = _clean_str(extracted.get('trich_yeu') or extracted.get('name')) or self.extracted_name
            self.extracted_reference = _clean_str(extracted.get('so_ky_hieu') or extracted.get('so_ky_hieu_gui')) or self.extracted_reference
            self.extracted_issuer = _clean_str(extracted.get('co_quan_ban_hanh') or extracted.get('co_quan_gui')) or self.extracted_issuer
            self.extracted_date = _parse_date(extracted.get('ngay_ban_hanh') or extracted.get('ngay_ban_hanh_goc') or extracted.get('ngay_ban_hanh_gui')) or fields.Date.today()
            self.extracted_doc_type = extracted.get('loai_van_ban') or self.extracted_doc_type or 'cong_van'
            self.extracted_do_khan = extracted.get('do_khan') or self.extracted_do_khan or 'thuong'
            self.extracted_so_den = _clean_str(extracted.get('so_den'))
            self.extracted_ngay_den = _parse_date(extracted.get('ngay_den') or extracted.get('ngay_tiep_nhan')) or fields.Date.today()
            self.extracted_han_xu_ly = _parse_date(extracted.get('han_xu_ly'))
            self.extracted_nguoi_ky = _clean_str(extracted.get('nguoi_ky'))
            self.extracted_chuc_vu_nguoi_ky = _clean_str(extracted.get('chuc_vu_nguoi_ky'))
            self.extracted_noi_nhan = _clean_str(extracted.get('noi_nhan'))

        self.state = 'preview'

        return {
            'name': _('Xác nhận kết quả bóc tách AI OCR (Preview)'),
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document.ocr.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reset_preview(self):
        """Quay lại bước chọn file."""
        self.ensure_one()
        self.state = 'draft'
        return {
            'name': _('Trích xuất AI (OCR) từ Tệp / Scan Giấy'),
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document.ocr.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_and_fill(self):
        """Bước 2: Điền thông tin đã xác nhận vào Form (Không tự động lưu - Người dùng tự bấm Lưu)."""
        self.ensure_one()
        
        doc_fields = self.env['aidt.document']._fields

        fill_context = {
            'default_direction': self.direction,
            'default_name': self.extracted_name,
            'default_reference': self.extracted_reference,
            'default_so_ky_hieu_gui': self.extracted_reference,
            'default_co_quan_gui': self.extracted_issuer,
            'default_date': self.extracted_date,
            'default_ngay_ban_hanh_gui': self.extracted_date,
            'default_doc_type': self.extracted_doc_type if 'doc_type' in doc_fields else 'cong_van',
            'default_do_khan': self.extracted_do_khan,
            'default_so_den': self.extracted_so_den,
            'default_ngay_den': self.extracted_ngay_den,
            'default_han_xu_ly': self.extracted_han_xu_ly,
            'default_nguoi_ky': self.extracted_nguoi_ky,
            'default_chuc_vu_nguoi_ky': self.extracted_chuc_vu_nguoi_ky,
            'default_noi_nhan': self.extracted_noi_nhan,
        }

        if self.direction == 'den':
            state_field = doc_fields.get('state')
            valid_states = [s[0] for s in state_field.selection] if (state_field and isinstance(state_field.selection, list)) else []
            if 'tiep_nhan' in valid_states:
                fill_context['default_state'] = 'tiep_nhan'
            elif 'draft' in valid_states:
                fill_context['default_state'] = 'draft'

        doc = self.document_id
        if doc:
            vals = {}
            mapping = {
                'name': self.extracted_name,
                'so_ky_hieu_gui': self.extracted_reference,
                'reference': self.extracted_reference,
                'co_quan_gui': self.extracted_issuer,
                'ngay_ban_hanh_gui': self.extracted_date,
                'date': self.extracted_date,
                'doc_type': self.extracted_doc_type,
                'do_khan': self.extracted_do_khan,
                'so_den': self.extracted_so_den,
                'ngay_den': self.extracted_ngay_den,
                'han_xu_ly': self.extracted_han_xu_ly,
                'nguoi_ky': self.extracted_nguoi_ky,
                'chuc_vu_nguoi_ky': self.extracted_chuc_vu_nguoi_ky,
                'noi_nhan': self.extracted_noi_nhan,
            }
            for k, v in mapping.items():
                if k in doc_fields and v:
                    vals[k] = v
            doc.write(vals)
            res_id = doc.id
        else:
            res_id = False

        if doc and doc.directory_id and self.file_scan:
            self.env['dms.file'].sudo().create({
                'name': self.file_scan_name or 'Cong_van_scan.pdf',
                'directory_id': doc.directory_id.id,
                'content': self.file_scan,
                'res_model': 'aidt.document',
                'res_id': doc.id,
            })

        view_id = False
        if self.direction == 'den':
            form_view = self.env.ref('aidt_vanban_den.aidt_vanban_den_view_form', raise_if_not_found=False)
            if form_view:
                view_id = form_view.id

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document',
            'res_id': res_id,
            'view_mode': 'form',
            'target': 'current',
            'context': fill_context,
        }
        if view_id:
            action['views'] = [(view_id, 'form')]
            action['view_id'] = view_id

        return action

    def action_start_ocr(self):
        """Deprecated fallback method."""
        return self.action_confirm_and_fill()

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

