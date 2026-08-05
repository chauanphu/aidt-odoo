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
        # Cả hai người ĐANG trong cuộc gọi: quyền gửi audio xét theo người có
        # mặt trong CUỘC GỌI, không phải theo thành viên kênh.
        cls._join_call(cls.speaker)
        cls._join_call(cls.other)
        cls.recording = cls.env['aidt.meeting.recording'].with_user(
            cls.speaker)._start_for_channel(cls.channel)

    @classmethod
    def _join_call(cls, user):
        member = cls.env['discuss.channel.member'].search([
            ('channel_id', '=', cls.channel.id),
            ('partner_id', '=', user.partner_id.id),
        ], limit=1)
        return cls.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })

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

    def test_van_nhan_chunk_khi_dang_xu_ly(self):
        """Mẩu cuối tới SAU lệnh dừng — và vẫn phải được nhận.

        `action_stop` ghi trạng thái 'processing' RỒI mới phát lệnh dừng cho
        các máy, nên mẩu đang dở của mỗi người (tới 15 giây lời kết) bao giờ
        cũng tới nơi khi bản ghi đã sang 'processing'. Chốt cửa ở 'recording'
        thì mọi cuộc họp đều mất đoạn kết của mọi người mà không báo gì.
        """
        self.recording.with_user(self.speaker).action_stop()
        self.assertEqual(self.recording.state, 'processing')
        chunk = self._store(seq=9)
        self.assertTrue(chunk.attachment_id)

    def test_khong_nhan_chunk_khi_ban_ghi_da_xong(self):
        """Nhưng khi đã chốt biên bản thì cửa đóng hẳn."""
        self.recording.with_user(self.speaker).action_stop()
        self.recording.sudo().write({'state': 'done'})
        with self.assertRaises(AccessError):
            self._store(seq=10)

    def test_khong_nhan_chunk_khi_ban_ghi_da_huy(self):
        self.recording.sudo().write({'state': 'cancelled'})
        with self.assertRaises(AccessError):
            self._store(seq=11)

    def test_khong_nhan_chunk_tu_nguoi_ngoai_kenh(self):
        outsider = self.env['res.users'].create({
            'name': 'Ngoài', 'login': 'ngoai2@test.local',
        })
        with self.assertRaises(AccessError):
            self.Chunk.with_user(outsider)._store(
                self.recording, outsider.partner_id, 0, 0, 15000, b'X')

    def test_khong_nhan_chunk_tu_thanh_vien_kenh_khong_trong_cuoc_goi(self):
        """Thành viên kênh nhưng CHƯA BAO GIỜ vào cuộc gọi ⇒ từ chối.

        Đây là nửa server của lỗi "kênh A ghi trộm micro của cuộc gọi B": bus
        phát lệnh bật ghi âm tới mọi thành viên kênh, và nếu server nhận audio
        của bất kỳ thành viên kênh nào thì nửa cuộc gọi riêng của họ ở một kênh
        khác vẫn được nhận, bóc băng và đăng dưới đúng tên họ. Một kênh phòng
        ban 200 người thì 197 người trong đó chưa từng vào cuộc gọi 3 người
        này.
        """
        lurker = self.env['res.users'].create({
            'name': 'Ngồi ngoài', 'login': 'ngoiongoai@test.local',
        })
        self.channel.add_members(partner_ids=[lurker.partner_id.id])
        with self.assertRaises(AccessError):
            self.Chunk.with_user(lurker)._store(
                self.recording, lurker.partner_id, 0, 0, 15000, b'X')

    def test_vao_hop_muon_van_gui_duoc_chunk(self):
        """Vào họp SAU khi ghi âm đã bắt đầu vẫn phải gửi được audio — người
        đó chỉ chưa có trong danh sách lúc bật, không phải người ngoài."""
        latecomer = self.env['res.users'].create({
            'name': 'Vào muộn', 'login': 'vaomuon@test.local',
        })
        self.channel.add_members(partner_ids=[latecomer.partner_id.id])
        self._join_call(latecomer)
        chunk = self.Chunk.with_user(latecomer)._store(
            self.recording, latecomer.partner_id, 0, 0, 15000, b'X')
        self.assertTrue(chunk.attachment_id)

    def test_gap_may_roi_van_gui_duoc_mau_cuoi(self):
        """Mẩu cuối tới SAU khi người đó đã rời cuộc gọi (không còn phiên RTC)
        vẫn phải được nhận: tới 15 giây lời kết nằm trong đó. Vì vậy quyền xét
        theo tập người ĐÃ TỪNG có mặt, không theo phiên RTC còn sống."""
        self.env['discuss.channel.rtc.session'].sudo().search([
            ('channel_id', '=', self.channel.id),
            ('partner_id', '=', self.speaker.partner_id.id),
        ]).unlink()
        chunk = self._store(seq=20)
        self.assertTrue(chunk.attachment_id)

    def test_khong_gan_audio_cho_partner_khac(self):
        """Đây là điểm chống giả mạo cốt lõi: partner PHẢI là người gọi,
        không bao giờ lấy từ dữ liệu client gửi lên. Một dòng transcript giả
        mạo là đúng loại sản phẩm không được phép tồn tại trong hệ thống này.
        """
        with self.assertRaises(AccessError):
            self.Chunk.with_user(self.speaker)._store(
                self.recording, self.other.partner_id, 0, 0, 15000, b'X')
