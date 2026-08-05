from datetime import timedelta
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

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
        # Người này ĐANG trong cuộc gọi — điều kiện để `_store` nhận audio.
        member = cls.env['discuss.channel.member'].search([
            ('channel_id', '=', cls.channel.id),
            ('partner_id', '=', cls.user.partner_id.id),
        ], limit=1)
        cls.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })
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

    def test_end_ms_vuot_do_dai_chunk_thi_bi_kep_ve_do_dai(self):
        """Mốc thời gian của ASR là đầu vào NGOÀI, không tin được.

        Quan sát thật 05/08/2026: PhoWhisper-large trên vLLM 0.26.0 trả
        `end: 40.08` cho một mẩu dài 8.208 giây. Không kẹp thì đoạn đó tràn
        ra ngoài mẩu và đè lên vùng thời gian của người khác.
        """
        chunk = self._chunk(offset_ms=10000)          # duration_ms = 15000
        with patch(PATH, return_value=[
                {'start_ms': 500, 'end_ms': 40080, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.start_ms, 10500)
        # 10000 + min(40080, 15000), KHÔNG phải 10000 + 40080.
        self.assertEqual(segment.end_ms, 25000)

    def test_end_ms_nho_hon_start_ms_thi_thu_ve_do_dai_khong(self):
        """Regression cho hàng `start_ms=16860, end_ms=4980` đã thấy thật
        trong CSDL: kẹp phải bảo đảm `end_ms >= start_ms` chứ không chuyển
        tiếp nguyên văn giá trị vô nghĩa của ASR.

        Đoạn suy biến bị thu về độ dài 0 chứ KHÔNG bị vứt đi — `text` vẫn là
        nội dung thật đã bóc băng được.
        """
        chunk = self._chunk(offset_ms=13392)
        with patch(PATH, return_value=[
                {'start_ms': 3468, 'end_ms': -8412, 'text': 'nội dung thật'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(len(segment), 1)
        self.assertEqual(segment.start_ms, 16860)
        self.assertEqual(segment.end_ms, 16860)
        self.assertGreaterEqual(segment.end_ms, segment.start_ms)
        self.assertEqual(segment.text, 'nội dung thật')

    def test_start_ms_vuot_do_dai_chunk_thi_bi_kep(self):
        """`start_ms` cũng là đầu vào NGOÀI và cũng phải kẹp.

        Ràng buộc `CHECK (end_ms >= start_ms)` KHÔNG bắt được lỗi này: `end`
        được suy ra TỪ `start`, nên một `start` sai kéo `end` sai theo đúng
        chiều hợp lệ và hàng vẫn ghi xuống được. Cùng dịch vụ đã trả
        `end: 415.6` cho một mẩu 8.2 giây cũng trả `start` vô nghĩa.

        Hậu quả nếu không kẹp: `transcript_builder._build` SẮP XẾP theo
        `start_ms`, nên một câu bị ném đi vài phút so với chỗ nó thực sự
        thuộc về; và phép xét "hai đoạn có liền nhau không" của bộ khử trùng
        mối nối cũng dựa trên `start_ms`, nên đoạn chồng lấn của chính người
        đó không còn được khử.
        """
        chunk = self._chunk(offset_ms=10000)          # duration_ms = 15000
        with patch(PATH, return_value=[
                {'start_ms': 415600, 'end_ms': 416000, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        # 10000 + min(415600, 15000), KHÔNG phải 10000 + 415600.
        self.assertEqual(segment.start_ms, 25000)
        self.assertEqual(segment.end_ms, 25000)
        self.assertEqual(segment.text, 'a')

    def test_start_ms_am_thi_kep_ve_khong(self):
        """`start_ms` âm đẩy đoạn ra TRƯỚC lúc cuộc họp bắt đầu, và với mẩu
        đầu tiên (offset 0) còn sinh ra `start_ms` âm trong CSDL."""
        chunk = self._chunk(offset_ms=0)
        with patch(PATH, return_value=[
                {'start_ms': -5000, 'end_ms': 2000, 'text': 'a'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        segment = self.env['aidt.meeting.segment'].search(
            [('chunk_id', '=', chunk.id)])
        self.assertEqual(segment.start_ms, 0)
        self.assertEqual(segment.end_ms, 2000)

    def test_start_ms_hong_khong_lam_dao_thu_tu_ban_boc_bang(self):
        """Kiểm ĐÚNG hậu quả, không chỉ kiểm giá trị: hai câu nói theo thứ
        tự 1→2 phải hiện ra trong bản bóc băng theo đúng thứ tự đó, kể cả khi
        ASR khai câu đầu bắt đầu ở giây thứ 415."""
        chunk = self._chunk(offset_ms=0)
        with patch(PATH, return_value=[
                {'start_ms': 415600, 'end_ms': 416000, 'text': 'câu một'},
                {'start_ms': 9000, 'end_ms': 10000, 'text': 'câu hai'}]):
            self.env['aidt.meeting.chunk']._cron_process()
        transcript = self.env['aidt.meeting.transcript']._build(self.recording)
        self.assertLess(transcript.index('câu hai'), transcript.index('câu một'))
        # Và không câu nào bị đẩy ra ngoài mẩu (15 giây = 00:15).
        self.assertNotIn('06:5', transcript)

    def test_csdl_tu_choi_segment_ket_thuc_truoc_khi_bat_dau(self):
        """Ràng buộc CHECK là lưới an toàn cho MỌI đường ghi, không chỉ cho
        `_write_segments` — kể cả import hay một client ASR khác cắm sau."""
        chunk = self._chunk()
        with self.assertRaises(IntegrityError):
            with mute_logger('odoo.sql_db'):
                self.env['aidt.meeting.segment'].create({
                    'recording_id': self.recording.id,
                    'chunk_id': chunk.id,
                    'partner_id': self.user.partner_id.id,
                    'start_ms': 16860,
                    'end_ms': 4980,
                    'text': 'không được phép',
                })
                self.env.flush_all()

    def test_loi_thi_lui_lich_thu_lai_chu_khong_chet_han(self):
        chunk = self._chunk()
        before = fields.Datetime.now()
        with patch(PATH, side_effect=AsrError('service chết')):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.state, 'pending')
        self.assertEqual(chunk.attempt, 1)
        self.assertTrue(chunk.next_retry_at)
        # Lần thử đầu phải lùi đúng RETRY_BACKOFF_MINUTES[0] = 1 phút — một
        # lỗi lệch chỉ số (dùng `attempt` thay vì `attempt - 1`) sẽ áp lùi
        # 4 phút ngay từ lần đầu mà `assertTrue` phía trên không bắt được.
        expected = fields.Datetime.add(before, minutes=1)
        self.assertAlmostEqual(
            chunk.next_retry_at, expected, delta=timedelta(seconds=30))

    def test_lan_thu_hai_lui_lich_bon_phut(self):
        """Lần thử thứ hai phải lùi 4 phút (RETRY_BACKOFF_MINUTES[1]), không
        phải lặp lại 1 phút của lần đầu — chứng minh cấp số nhân thật sự
        tăng theo `attempt` chứ không đứng yên."""
        chunk = self._chunk()
        with patch(PATH, side_effect=AsrError('chết')):
            self.env['aidt.meeting.chunk']._cron_process()
            chunk.next_retry_at = False
            before = fields.Datetime.now()
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(chunk.attempt, 2)
        expected = fields.Datetime.add(before, minutes=4)
        self.assertAlmostEqual(
            chunk.next_retry_at, expected, delta=timedelta(seconds=30))

    def test_loi_tang_csdl_khong_dau_doc_hang_doi(self):
        """Regression cho savepoint trong `_process_one`: một câu SQL thật
        sự lỗi ở tầng CSDL (không phải AsrError của Python) phải bị savepoint
        chặn lại, không đầu độc cursor cho mẩu tiếp theo trong cùng lượt
        cron. Nếu ai đó lỡ xoá savepoint, mẩu lành phía sau sẽ không bao giờ
        ghi được nữa vì cursor đã rơi vào InFailedSqlTransaction."""
        broken = self._chunk(seq=0)
        healthy = self._chunk(seq=1, offset_ms=1000)

        def side_effect(raw, filename):
            if filename == f'chunk-{broken.id}.mp3':
                # Ép một lỗi CSDL thật (không phải ngoại lệ Python thuần)
                # ngay bên trong savepoint của `_process_one`.
                self.env.cr.execute('SELECT 1/0')
            return [{'start_ms': 0, 'end_ms': 1000, 'text': 'ok'}]

        with patch(PATH, side_effect=side_effect):
            self.env['aidt.meeting.chunk']._cron_process()
        self.assertEqual(broken.state, 'pending')
        self.assertEqual(broken.attempt, 1)
        # Mẩu lành xử lý SAU mẩu hỏng trong cùng lượt cron vẫn phải xong —
        # đây là phần khẳng định chứng minh savepoint hoạt động thật sự.
        self.assertEqual(healthy.state, 'done')

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
