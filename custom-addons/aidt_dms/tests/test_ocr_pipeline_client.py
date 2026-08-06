from odoo.tests.common import TransactionCase
import base64

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
