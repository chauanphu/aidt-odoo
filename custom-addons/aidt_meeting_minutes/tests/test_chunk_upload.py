import psycopg2

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class ChunkCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Chunk = cls.env['aidt.meeting.chunk']
        cls.speaker = cls.env['res.users'].create({
            'name': 'Người nói', 'login': 'nguoinoi@test.local',
        })
        cls.other = cls.env['res.users'].create({
            'name': 'Người khác', 'login': 'nguoikhac@test.local',
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.channel.add_members(partner_ids=[
            cls.speaker.partner_id.id, cls.other.partner_id.id])
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.speaker)._start_for_channel(cls.channel)

    def _store(self, seq=0, offset_ms=0, user=None):
        user = user or self.speaker
        return self.Chunk.with_user(user)._store(
            self.recording, user.partner_id, seq, offset_ms, 15000, b'FAKEMP3')


class TestChunkStore(ChunkCase):
    def test_luu_duoc_chunk_va_gan_attachment(self):
        chunk = self._store()
        self.assertEqual(chunk.state, 'pending')
        self.assertTrue(chunk.attachment_id)
        self.assertEqual(chunk.partner_id, self.speaker.partner_id)

    def test_trung_seq_bi_tu_choi(self):
        """Upload thử lại sau lỗi mạng KHÔNG được nhân đôi audio.

        Chặn ở tầng CSDL chứ không phải đọc-rồi-ghi trong Python: hai request
        chồng nhau vẫn có thể cùng đọc "chưa có" rồi cùng ghi.
        """
        self._store(seq=3)
        with self.assertRaises(psycopg2.errors.UniqueViolation), \
                mute_logger('odoo.sql_db'):
            self._store(seq=3)
            self.env.flush_all()

    def test_khong_nhan_chunk_khi_ban_ghi_da_dung(self):
        self.recording.with_user(self.speaker).action_stop()
        with self.assertRaises(AccessError):
            self._store(seq=9)

    def test_khong_nhan_chunk_tu_nguoi_ngoai_kenh(self):
        outsider = self.env['res.users'].create({
            'name': 'Ngoài', 'login': 'ngoai2@test.local',
        })
        with self.assertRaises(AccessError):
            self.Chunk.with_user(outsider)._store(
                self.recording, outsider.partner_id, 0, 0, 15000, b'X')

    def test_khong_gan_audio_cho_partner_khac(self):
        """Đây là điểm chống giả mạo cốt lõi: partner PHẢI là người gọi,
        không bao giờ lấy từ dữ liệu client gửi lên. Một dòng transcript giả
        mạo là đúng loại sản phẩm không được phép tồn tại trong hệ thống này.
        """
        with self.assertRaises(AccessError):
            self.Chunk.with_user(self.speaker)._store(
                self.recording, self.other.partner_id, 0, 0, 15000, b'X')
