from odoo.tests.common import TransactionCase


class RetentionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'An'})
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
        })

    def _chunk(self, state='done'):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'a.mp3', 'datas': b'QUJD', 'mimetype': 'audio/mpeg',
        })
        return self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': self.partner.id,
            'seq': 0, 'offset_ms': 0, 'duration_ms': 15000,
            'state': state, 'attachment_id': attachment.id,
        })


class TestRetention(RetentionCase):
    def test_mac_dinh_khong_ngay_thi_xoa_audio_ngay(self):
        """Audio thô của một cuộc họp cấp uỷ là rủi ro lớn hơn transcript và
        không có bên nào dùng đến sau khi đã bóc băng."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='done')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertFalse(chunk.attachment_id)

    def test_giu_lai_khi_cau_hinh_lon_hon_khong(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '30')
        chunk = self._chunk(state='done')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertTrue(chunk.attachment_id)

    def test_khong_xoa_audio_cua_mau_chua_boc_bang_xong(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='pending')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertTrue(chunk.attachment_id)
