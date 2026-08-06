"""Đường đi ĐẦY ĐỦ của một mẩu: giải mã -> cổng lọc -> ASR -> lọc ảo giác.

`test_audio_prep.py` và `test_text_filter.py` kiểm từng mảnh riêng lẻ. File
này kiểm chúng ĐÃ ĐƯỢC NỐI VÀO `_process_one` — hai mảnh đúng nhưng không ai
gọi thì vẫn là một tính năng không tồn tại. Chỉ lời gọi HTTP tới ASR là giả;
mọi bước còn lại chạy thật.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.aidt_meeting_minutes.tests.audio_fixtures import (
    silent_mp3, speech_like_mp3,
)

PATH = ('odoo.addons.aidt_meeting_minutes.models.asr_client.'
        'AidtMeetingAsrClient._transcribe')

SPEECH_MP3 = speech_like_mp3()
SILENT_MP3 = silent_mp3()


class ChunkPipelineCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Người nói', 'login': 'p_nguoinoi@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])
        member = cls.env['discuss.channel.member'].search([
            ('channel_id', '=', cls.channel.id),
            ('partner_id', '=', cls.user.partner_id.id),
        ], limit=1)
        cls.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.user)._start_for_channel(cls.channel)

    def _chunk(self, raw, seq=0, offset_ms=0):
        return self.env['aidt.meeting.chunk'].with_user(self.user)._store(
            self.recording, self.user.partner_id, seq, offset_ms, 15000, raw)

    def _segments(self, chunk):
        return self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])

    # ---------------------------------------------------------------- #
    # Cổng lọc tiếng nói
    # ---------------------------------------------------------------- #
    def test_mau_im_lang_khong_bao_gio_toi_duoc_ASR(self):
        """Điểm mấu chốt của cả đợt thay đổi này.

        Đo thật 05/08/2026: `openai/whisper-large-v3` nhận 15 giây im lặng
        tuyệt đối và trả về "Hãy subscribe cho kênh La La School…" với
        avg_logprob -0.108 — tức là rất tự tin về một câu không ai nói. Cách
        duy nhất chắc chắn để nó không bịa là ĐỪNG HỎI.
        """
        chunk = self._chunk(SILENT_MP3)
        with patch(PATH) as transcribe:
            self.env['aidt.meeting.chunk']._cron_process()
        transcribe.assert_not_called()
        self.assertEqual(chunk.state, 'done')
        self.assertFalse(self._segments(chunk))

    def test_mau_im_lang_la_done_chu_khong_phai_failed(self):
        """`failed` sẽ sinh dòng "[thiếu âm thanh …]" giữa biên bản cho MỌI
        quãng im lặng bình thường, và đốt sạch lượt retry cho một việc chắc
        chắn ra cùng kết quả."""
        chunk = self._chunk(SILENT_MP3)
        with patch(PATH):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'done')
        self.assertEqual(chunk.attempt, 0)
        self.assertFalse(chunk.error)
        transcript = self.env['aidt.meeting.transcript']._build(self.recording)
        self.assertNotIn('thiếu âm thanh', transcript)

    def test_mau_im_lang_ghi_lai_ly_do(self):
        """Bỏ qua thì được, bỏ qua ÂM THẦM thì không: phải còn dấu vết để
        hiệu chỉnh ngưỡng sau này."""
        chunk = self._chunk(SILENT_MP3)
        with patch(PATH):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertTrue(chunk.skip_note)
        self.assertIn('tiếng nói', chunk.skip_note)

    def test_mau_co_tieng_noi_van_di_toi_ASR(self):
        """Mặt còn lại: cổng lọc không được chặn nhầm audio thật."""
        chunk = self._chunk(SPEECH_MP3)
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': 1000, 'text': 'xin chào'}]) as tr:
            self.env['aidt.meeting.chunk']._cron_process()
        tr.assert_called_once()
        self.assertEqual(chunk.state, 'done')
        self.assertEqual(self._segments(chunk).text, 'xin chào')

    def test_gui_toi_ASR_la_WAV_chu_khong_phai_MP3_goc(self):
        """Bằng chứng tiền xử lý thật sự chạy chứ không chuyển tiếp nguyên
        byte đã upload."""
        captured = {}

        def fake(raw, filename):
            captured['filename'] = filename
            captured['raw'] = raw
            return []

        self._chunk(SPEECH_MP3)
        with patch(PATH, side_effect=fake):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertTrue(captured['filename'].endswith('.wav'))
        self.assertEqual(captured['raw'][:4], b'RIFF')
        self.assertNotEqual(captured['raw'], SPEECH_MP3)

    # ---------------------------------------------------------------- #
    # Lọc ảo giác
    # ---------------------------------------------------------------- #
    def test_ao_giac_bi_bo_va_ghi_lai(self):
        """Câu dưới đây là đầu ra THẬT của large-v3 trên nhiễu nền."""
        chunk = self._chunk(SPEECH_MP3)
        with patch(PATH, return_value=[{
                'start_ms': 0, 'end_ms': 15000,
                'text': 'Cảm ơn các bạn đã theo dõi và hẹn gặp lại.'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'done')
        self.assertFalse(self._segments(chunk))
        self.assertIn('ảo giác', chunk.skip_note)

    def test_cau_noi_that_trung_khuon_mau_van_duoc_giu(self):
        chunk = self._chunk(SPEECH_MP3)
        real = ('Trước khi kết thúc phần trình bày về ngân sách quý ba, tôi '
                'xin cảm ơn các bạn đã theo dõi và mong nhận được ý kiến '
                'đóng góp của các đồng chí.')
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': 15000, 'text': real}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(self._segments(chunk).text, real)
        self.assertFalse(chunk.skip_note)

    def test_bo_mot_doan_ao_giac_khong_keo_theo_doan_that(self):
        chunk = self._chunk(SPEECH_MP3)
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': 5000, 'text': 'Ta bắt đầu họp.'},
                {'start_ms': 5000, 'end_ms': 10000, 'text': 'Please subscribe'},
                {'start_ms': 10000, 'end_ms': 15000, 'text': 'Xin hết ý kiến.'},
        ]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(
            self._segments(chunk).mapped('text'),
            ['Ta bắt đầu họp.', 'Xin hết ý kiến.'])
        self.assertIn('ảo giác', chunk.skip_note)

    # ---------------------------------------------------------------- #
    # Chạy lại bóc băng
    # ---------------------------------------------------------------- #
    @mute_logger('odoo.addons.aidt_meeting_minutes.models.meeting_recording')
    def test_boc_bang_lai_xoa_doan_cu_va_dua_ban_ghi_ve_processing(self):
        chunk = self._chunk(SPEECH_MP3)
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': 1000, 'text': 'bản cũ'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.recording.sudo().write({'state': 'done'})

        self.recording.action_retranscribe()
        self.assertEqual(self.recording.state, 'processing')
        self.assertEqual(chunk.state, 'pending')
        self.assertEqual(chunk.attempt, 0)

        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': 1000, 'text': 'bản mới'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(self._segments(chunk).mapped('text'), ['bản mới'])

    @mute_logger('odoo.addons.aidt_meeting_minutes.models.meeting_recording')
    def test_boc_bang_lai_bao_loi_ro_rang_khi_audio_da_bi_xoa(self):
        """Với `audio_retention_days = 0` (mặc định xuất xưởng) đây là ca
        BÌNH THƯỜNG, không phải ngoại lệ hiếm — người dùng phải hiểu vì sao
        chứ không gặp một nút bấm im lặng."""
        chunk = self._chunk(SPEECH_MP3)
        chunk.sudo().attachment_id.unlink()
        self.recording.sudo().write({'state': 'done'})
        with self.assertRaises(UserError) as caught:
            self.recording.action_retranscribe()
        self.assertIn('audio', str(caught.exception).lower())
