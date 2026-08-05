from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


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

    def test_xoa_ca_audio_cua_mau_boc_bang_that_bai(self):
        """Mẩu `failed` là mẩu đã hết lượt thử — không ai còn xử lý nó nữa,
        nên audio thô của nó cũng hết lý do tồn tại. Bỏ `failed` ra khỏi
        domain nghĩa là đúng những mẩu HỎNG giữ nguyên audio cuộc họp VĨNH
        VIỄN, kể cả khi chính sách là "xoá ngay" — một hệ thống lấy chính
        sách lưu trữ làm cam kết tuân thủ không được phép có ngoại lệ âm thầm
        như vậy."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='failed')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertFalse(chunk.attachment_id)

    def test_van_giu_audio_cua_mau_dang_cho_thu_lai(self):
        """Nhưng `pending` (đang chờ thử lại) thì PHẢI giữ — xoá audio ở đó
        là tự tay bảo đảm lượt thử lại không bao giờ thành công."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='transcribing')
        self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertTrue(chunk.attachment_id)


class TestCronPurgeRobustness(RetentionCase):
    """`_cron_purge_audio` phải sống sót qua đúng những lỗi mà anh em song
    sinh của nó (`_purge_own_audio`) đã ghi rõ trong docstring là chắc chắn
    xảy ra. Không có savepoint + try/except thì MỘT giá trị cấu hình rác
    giết lượt cron này mỗi ngày, mãi mãi, và âm thầm."""

    def test_cau_hinh_rac_khong_giet_cron(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', 'khong_phai_so')
        chunk = self._chunk(state='done')
        with mute_logger(
                'odoo.addons.aidt_meeting_minutes.models.meeting_recording'):
            result = self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertFalse(result)
        # Không xoá được thì cũng KHÔNG được để lại attachment mồ côi đã bị
        # tháo khỏi chunk — savepoint trả cả hai bước về nguyên vẹn.
        self.assertTrue(chunk.attachment_id)

    def test_unlink_that_bai_khong_de_lai_attachment_mo_coi(self):
        """Hai thao tác (tháo `attachment_id` rồi `unlink`) chạy nối nhau.
        Lỗi ở bước sau mà không có savepoint sẽ để chunk mất liên kết trong
        khi tệp vẫn nằm đó — mất dấu vết của chính thứ cần dọn."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.audio_retention_days', '0')
        chunk = self._chunk(state='done')
        with patch('odoo.addons.base.models.ir_attachment.IrAttachment.unlink',
                   side_effect=ValueError('filestore hỏng')), \
                mute_logger('odoo.addons.aidt_meeting_minutes.models.'
                            'meeting_recording'):
            result = self.env['aidt.meeting.recording']._cron_purge_audio()
        self.assertFalse(result)
        self.env.invalidate_all()
        self.assertTrue(chunk.attachment_id)
