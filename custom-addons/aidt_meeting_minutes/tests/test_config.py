from odoo.tests.common import TransactionCase


class TestConfig(TransactionCase):
    def _param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    def test_co_gia_tri_mac_dinh_cho_moi_tham_so(self):
        self.assertTrue(self._param('aidt_meeting.asr_url'))
        self.assertEqual(self._param('aidt_meeting.asr_model'),
                         'vinai/PhoWhisper-large')
        self.assertTrue(self._param('aidt_meeting.llm_url'))

    def test_mac_dinh_chi_cho_ghi_am_muc_thuong(self):
        """Mặc định phải là mức thấp nhất: bật rộng hơn phải là quyết định
        có ý thức của quản trị viên, không phải thứ có sẵn khi cài."""
        self.assertEqual(self._param('aidt_meeting.max_secrecy'), 'thuong')

    def test_mac_dinh_xoa_audio_ngay_sau_khi_boc_bang(self):
        """0 ngày = xoá ngay. Audio thô là rủi ro lớn hơn transcript."""
        self.assertEqual(self._param('aidt_meeting.audio_retention_days'), '0')

    def test_settings_ghi_duoc_va_doc_lai_dung(self):
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_url': 'http://phowhisper:8002/v1',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_url'),
                         'http://phowhisper:8002/v1')
