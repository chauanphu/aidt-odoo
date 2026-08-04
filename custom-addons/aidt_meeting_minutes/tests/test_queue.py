from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.aidt_meeting_minutes.models.asr_client import AsrError

PATH = ('odoo.addons.aidt_meeting_minutes.models.asr_client.'
        'AidtMeetingAsrClient._transcribe')


class QueueCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Người nói', 'login': 'q_nguoinoi@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[cls.user.partner_id.id])
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.user)._start_for_channel(cls.channel)

    def _chunk(self, seq=0, offset_ms=0):
        return self.env['aidt.meeting.chunk'].with_user(self.user)._store(
            self.recording, self.user.partner_id, seq, offset_ms, 15000,
            b'AUDIO')


class TestQueue(QueueCase):
    def test_boc_bang_xong_thi_sinh_segment(self):
        chunk = self._chunk()
        with patch(PATH, return_value=[
                {'start_ms': 500, 'end_ms': 2000, 'text': 'xin chào'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'done')
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(len(segment), 1)
        self.assertEqual(segment.text, 'xin chào')

    def test_moc_thoi_gian_la_tuyet_doi_theo_offset_cua_chunk(self):
        """Segment lưu vị trí tuyệt đối trong cuộc họp, không phải vị trí
        trong chunk — nếu không thì trộn nhiều người sẽ sai hoàn toàn."""
        chunk = self._chunk(seq=2, offset_ms=30000)
        with patch(PATH, return_value=[
                {'start_ms': 500, 'end_ms': 2000, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.start_ms, 30500)
        self.assertEqual(segment.end_ms, 32000)

    def test_khong_co_end_ms_thi_lay_het_do_dai_chunk(self):
        chunk = self._chunk(offset_ms=10000)
        with patch(PATH, return_value=[
                {'start_ms': 0, 'end_ms': None, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.end_ms, 25000)

    def test_loi_thi_lui_lich_thu_lai_chu_khong_chet_han(self):
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('service chết')):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'pending')
        self.assertEqual(chunk.attempt, 1)
        self.assertTrue(chunk.next_retry_at)

    def test_het_ba_lan_thi_danh_dau_failed(self):
        """Phải đóng đinh 'failed': để 'pending' mãi thì `_claim` (sắp theo
        id) nhận lại đúng chunk hỏng ở mọi nhịp cron và không chunk nào phía
        sau được chạy."""
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('chết')):
            for _i in range(3):
                chunk.next_retry_at = False
                self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'failed')

    def test_chua_toi_han_thu_lai_thi_khong_nhan(self):
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('chết')):
            self.env['aidt.meeting.chunk']._cron_process()
        claimed = self.env['aidt.meeting.chunk']._claim(limit=5)
        self.assertNotIn(chunk, claimed)
