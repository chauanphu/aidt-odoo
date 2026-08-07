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

    month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
    import re
    m1 = re.search(r'\b(\d{1,2})\s+([a-zA-Z]{3,9})(?:[,\s]+(\d{4}))?\b', val)
    if m1:
        d_str, mon_str, y_str = m1.groups()
        mon = month_map.get(mon_str.lower()[:3])
        if mon:
            y = int(y_str) if y_str else datetime.now().year
            try:
                return date(y, mon, int(d_str))
            except Exception:
                pass

    m2 = re.search(r'\b([a-zA-Z]{3,9})\s+(\d{1,2})(?:[,\s]+(\d{4}))?\b', val)
    if m2:
        mon_str, d_str, y_str = m2.groups()
        mon = month_map.get(mon_str.lower()[:3])
        if mon:
            y = int(y_str) if y_str else datetime.now().year
            try:
                return date(y, mon, int(d_str))
            except Exception:
                pass

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
    is_analyzed = fields.Boolean('Đã bóc tách AI', default=False)

    # Simulated AI Extracted Preview Fields
    extracted_name = fields.Char(
        'Trích yếu nhận diện (AI OCR)', 
        default='Công văn v/v triển khai Kế hoạch bảo đảm an toàn hệ thống thông tin Tỉnh năm 2026'
    )
    extracted_reference = fields.Char('Số ký hiệu gốc nhận diện', default='185/CV-STTTT')
    extracted_issuer = fields.Char('Cơ quan gửi nhận diện', default='Sở Thông tin và Truyền thông')
    extracted_date = fields.Char('Ngày ban hành gốc nhận diện', default=lambda self: fields.Date.today().strftime('%d/%m/%Y'))
    extracted_doc_type = fields.Selection([
        ('cong_van', 'Công văn'), ('bao_cao', 'Báo cáo'),
        ('ke_hoach', 'Kế hoạch'), ('quyet_dinh', 'Quyết định'),
        ('thong_bao', 'Thông báo'), ('ket_luan', 'Kết luận'),
        ('nghi_quyet', 'Nghị quyết'), ('to_trinh', 'Tờ trình'),
        ('giay_moi', 'Giấy mời'), ('bien_ban', 'Biên bản'),
        ('nghi_dinh', 'Nghị định'), ('chi_thi', 'Chỉ thị'),
        ('thong_tu', 'Thông tư'), ('quy_che', 'Quy chế'),
        ('quy_dinh', 'Quy định'), ('de_an', 'Đề án'),
        ('khac', 'Khác'),
    ], string='Loại văn bản', default='cong_van')
    extracted_secrecy = fields.Selection([
        ('thuong', 'Thường'), ('mat', 'Mật'),
        ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật'),
    ], string='Độ mật', default='thuong')
    extracted_do_khan = fields.Selection([
        ('thuong', 'Thường'), ('khan', 'Khẩn'),
        ('thuong_khan', 'Thượng khẩn'), ('hoa_toc', 'Hỏa tốc'),
    ], string='Độ khẩn', default='khan')
    extracted_so_den = fields.Char('Số đến nhận diện')
    extracted_ngay_den = fields.Char('Ngày đến nhận diện', default=lambda self: fields.Date.today().strftime('%d/%m/%Y'))
    extracted_so_ban = fields.Integer('Số bản nhận diện', default=1)
    extracted_department_id = fields.Many2one('hr.department', string='Đơn vị nhận diện')
    extracted_date_received = fields.Char('Ngày tiếp nhận nhận diện', default=lambda self: fields.Date.today().strftime('%d/%m/%Y'))
    extracted_shared_user_ids = fields.Many2many('res.users', string='Chia sẻ với nhận diện')
    extracted_reasoning = fields.Text(
        'Nhật ký AI Gemma 4 Suy luận & Căn cứ phân công (CoT)',
        default='Gemma 4 CoT: Phân tích ngữ cảnh văn bản hành chính và định tuyến đơn vị tiếp nhận.'
    )

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
            self.extracted_date = _clean_str(extracted.get('ngay_ban_hanh_goc') or extracted.get('ngay_ban_hanh') or extracted.get('ngay_ban_hanh_gui')) or fields.Date.today().strftime('%d/%m/%Y')
            
            # Safe doc_type assignment with fallback (defaults to 'khac' if title like NGHỊ ĐỊNH is not in selection list)
            raw_doc_type = extracted.get('loai_van_ban') or 'khac'
            valid_doc_types = dict(self._fields['extracted_doc_type'].selection).keys()
            self.extracted_doc_type = raw_doc_type if raw_doc_type in valid_doc_types else 'khac'
            
            raw_secrecy = extracted.get('do_mat') or extracted.get('secrecy') or 'thuong'
            valid_secrecy = dict(self._fields['extracted_secrecy'].selection).keys()
            self.extracted_secrecy = raw_secrecy if raw_secrecy in valid_secrecy else 'thuong'

            raw_do_khan = extracted.get('do_khan') or 'thuong'
            valid_do_khan = dict(self._fields['extracted_do_khan'].selection).keys()
            self.extracted_do_khan = raw_do_khan if raw_do_khan in valid_do_khan else 'thuong'
            self.extracted_so_den = _clean_str(extracted.get('so_den'))
            self.extracted_ngay_den = _clean_str(extracted.get('ngay_den') or extracted.get('ngay_tiep_nhan')) or fields.Date.today().strftime('%d/%m/%Y')
            self.extracted_so_ban = int(extracted.get('so_ban')) if extracted.get('so_ban') else 1
            self.extracted_date_received = _clean_str(extracted.get('ngay_tiep_nhan') or extracted.get('date')) or fields.Date.today().strftime('%d/%m/%Y')
            self.extracted_reasoning = _clean_str(extracted.get('ly_do_phan_cong') or extracted.get('cot_reasoning')) or self.extracted_reasoning

            # Map extracted don_vi to Odoo hr.department
            dept_name = _clean_str(extracted.get('don_vi') or extracted.get('department_name'))
            if dept_name:
                dept = self.env['hr.department'].sudo().search([('name', 'ilike', dept_name)], limit=1)
                if not dept:
                    dept = self.env['hr.department'].sudo().search([('name', 'ilike', 'Văn phòng')], limit=1)
                if dept:
                    self.extracted_department_id = dept.id

        self.is_analyzed = True
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
        self.is_analyzed = False
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
        """Bước 2: Điền thông tin vào Form dạng bản nháp + Đánh dấu Dirty để Odoo hỏi khi rời trang."""
        self.ensure_one()
        
        doc_fields = self.env['aidt.document']._fields

        fill_context = {
            'mark_ocr_dirty': True,
            'default_direction': self.direction,
            'default_name': self.extracted_name,
            'default_reference': self.extracted_reference,
            'default_so_ky_hieu_gui': self.extracted_reference,
            'default_co_quan_gui': self.extracted_issuer,
            'default_date': _parse_date(self.extracted_date_received) or _parse_date(self.extracted_date) or fields.Date.today(),
            'default_ngay_ban_hanh_gui': _parse_date(self.extracted_date) or fields.Date.today(),
            'default_doc_type': self.extracted_doc_type if 'doc_type' in doc_fields else 'cong_van',
            'default_secrecy': self.extracted_secrecy,
            'default_do_khan': self.extracted_do_khan,
            'default_so_den': self.extracted_so_den,
            'default_ngay_den': _parse_date(self.extracted_ngay_den) or fields.Date.today(),
            'default_so_ban': self.extracted_so_ban,
            'default_department_id': self.extracted_department_id.id if self.extracted_department_id else False,
            'default_shared_user_ids': [(6, 0, self.extracted_shared_user_ids.ids)] if self.extracted_shared_user_ids else False,
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
            vals = {
                'name': self.extracted_name,
                'so_ky_hieu_gui': self.extracted_reference,
                'reference': self.extracted_reference,
                'co_quan_gui': self.extracted_issuer,
                'date': _parse_date(self.extracted_date_received) or _parse_date(self.extracted_date) or fields.Date.today(),
                'ngay_ban_hanh_gui': _parse_date(self.extracted_date) or fields.Date.today(),
                'doc_type': self.extracted_doc_type if 'doc_type' in doc_fields else 'cong_van',
                'secrecy': self.extracted_secrecy,
                'do_khan': self.extracted_do_khan,
                'so_den': self.extracted_so_den,
                'ngay_den': _parse_date(self.extracted_ngay_den) or fields.Date.today(),
                'so_ban': self.extracted_so_ban,
                'department_id': self.extracted_department_id.id if self.extracted_department_id else False,
                'shared_user_ids': [(6, 0, self.extracted_shared_user_ids.ids)] if self.extracted_shared_user_ids else False,
            }
            valid_vals = {k: v for k, v in vals.items() if k in doc_fields and v}
            doc.write(valid_vals)
            res_id = doc.id
        else:
            res_id = False

        view_id = False
        if self.direction == 'den':
            form_view = self.env.ref('aidt_vanban_den.aidt_vanban_den_view_form', raise_if_not_found=False)
            if form_view:
                view_id = form_view.id

        action = {
            'name': _('Văn bản đến'),
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
            response = requests.post(endpoint, files=files, timeout=180)
            response.raise_for_status()
            res_data = response.json()
            return res_data
        except requests.exceptions.RequestException as e:
            _logger.warning("Pipeline AI OCR request failed: %s", str(e))
            raise UserError(_("Không thể kết nối dịch vụ AI bóc tách (Port 8001). Vui lòng kiểm tra dịch vụ backend hoặc nhập thủ công. Chi tiết: %s") % str(e))

