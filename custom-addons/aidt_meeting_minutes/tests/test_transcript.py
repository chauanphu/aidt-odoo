from odoo.tests.common import TransactionCase


class TranscriptCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.builder = cls.env['aidt.meeting.transcript']
        cls.an = cls.env['res.partner'].create({'name': 'Nguyễn Văn An'})
        cls.binh = cls.env['res.partner'].create({'name': 'Trần Thị Bình'})
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cuộc gọi', 'channel_type': 'channel',
        })
        cls.recording = cls.env['aidt.meeting.recording'].sudo().create({
            'channel_id': cls.channel.id, 'secrecy_at_start': 'thuong',
        })

    def _seg(self, partner, start_ms, end_ms, text):
        return self.env['aidt.meeting.segment'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': partner.id,
            'start_ms': start_ms, 'end_ms': end_ms, 'text': text,
        })


class TestTranscript(TranscriptCase):
    def test_tron_dung_thu_tu_giua_hai_nguoi(self):
        self._seg(self.binh, 5000, 7000, 'Tôi đồng ý')
        self._seg(self.an, 1000, 3000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertLess(text.index('Xin chào'), text.index('Tôi đồng ý'))

    def test_gop_luot_noi_lien_tiep_cua_cung_mot_nguoi(self):
        """Ba đoạn liền của một người phải thành một khối, không phải ba
        dòng lặp tên — biên bản đọc được mới là mục tiêu."""
        self._seg(self.an, 0, 1000, 'Câu một.')
        self._seg(self.an, 1000, 2000, 'Câu hai.')
        self._seg(self.an, 2000, 3000, 'Câu ba.')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('Nguyễn Văn An'), 1)
        self.assertIn('Câu một. Câu hai. Câu ba.', text)

    def test_khu_trung_lap_o_moi_noi_chong_lan(self):
        """Chunk chồng lấn 1.5 giây nên câu ở mối nối bị bóc băng hai lần.
        Không khử thì biên bản lặp chữ ở mỗi 15 giây."""
        self._seg(self.an, 0, 15000, 'Chúng ta bắt đầu cuộc họp')
        self._seg(self.an, 13500, 28000, 'cuộc họp hôm nay bàn ba việc')
        text = self.builder._build(self.recording)
        self.assertEqual(text.count('cuộc họp'), 1)

    def test_danh_dau_khoang_thieu_am_thanh(self):
        """Khoảng khuyết phải được nói ra. Một biên bản có lỗ hổng vô hình
        tệ hơn một biên bản thừa nhận nó."""
        chunk = self.env['aidt.meeting.chunk'].sudo().create({
            'recording_id': self.recording.id, 'partner_id': self.an.id,
            'seq': 5, 'offset_ms': 60000, 'duration_ms': 15000,
            'state': 'failed', 'error': 'ASR chết',
        })
        self.assertTrue(chunk)
        text = self.builder._build(self.recording)
        self.assertIn('[thiếu âm thanh', text)
        self.assertIn('01:00', text)

    def test_neu_ten_nguoi_tu_choi_o_dau_ban(self):
        self.recording.sudo().declined_partner_ids = [(4, self.binh.id)]
        self._seg(self.an, 0, 1000, 'Xin chào')
        text = self.builder._build(self.recording)
        self.assertIn('Trần Thị Bình', text.split('\n\n')[0])

    def test_ban_rong_van_tra_ve_chuoi_khong_nem_loi(self):
        text = self.builder._build(self.recording)
        self.assertIsInstance(text, str)
