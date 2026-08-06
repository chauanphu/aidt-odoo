from odoo.tests.common import TransactionCase
import base64
from unittest.mock import patch

class TestOcrPipelineClient(TransactionCase):

    def test_pipeline_url_parameter(self):
        param = self.env['ir.config_parameter'].sudo().get_param('aidt_dms.pipeline_url', 'http://localhost:8001')
        self.assertTrue(param.startswith('http'))

    def test_wizard_pipeline_method_exists(self):
        wizard = self.env['aidt.document.ocr.wizard'].create({
            'file_scan': base64.b64encode(b'%PDF-1.4 test dummy content'),
            'file_scan_name': 'test.pdf',
            'ai_engine': 'unlimited_ocr_pipeline',
        })
        self.assertTrue(hasattr(wizard, '_call_unlimited_ocr_pipeline'))

    def test_action_start_ocr_pipeline_data_mapping(self):
        wizard = self.env['aidt.document.ocr.wizard'].create({
            'file_scan': base64.b64encode(b'%PDF-1.4 test content'),
            'file_scan_name': 'test.pdf',
            'ai_engine': 'unlimited_ocr_pipeline',
            'direction': 'den',
        })
        mock_data = {
            'trich_yeu': 'Trích yếu từ OCR AI Pipeline',
            'so_ky_hieu': '99/CV-STTTT',
            'co_quan_ban_hanh': 'Sở Thông tin và Truyền thông',
            'ngay_ban_hanh': '2026-08-06',
            'loai_van_ban': 'cong_van',
            'do_khan': 'khan',
            'nguoi_ky': 'Nguyễn Văn A',
            'chuc_vu_nguoi_ky': 'Giám đốc',
            'noi_nhan': 'Các phòng ban',
        }
        with patch.object(type(wizard), '_call_unlimited_ocr_pipeline', return_value={'data': mock_data}):
            wizard.action_run_ai_ocr()
            self.assertEqual(wizard.extracted_name, 'Trích yếu từ OCR AI Pipeline')
            action = wizard.action_confirm_and_fill()
            self.assertEqual(action.get('context', {}).get('default_name'), 'Trích yếu từ OCR AI Pipeline')
