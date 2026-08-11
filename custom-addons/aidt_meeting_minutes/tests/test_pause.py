import time
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPause(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thử tạm dừng', 'channel_type': 'channel'})
        cls.host = cls.env['res.users'].create({
            'name': 'Chủ phòng', 'login': 'pause_host@test.local'})
        cls.guest = cls.env['res.users'].create({
            'name': 'Người dự', 'login': 'pause_guest@test.local'})
        cls.channel.add_members(
            partner_ids=[cls.host.partner_id.id, cls.guest.partner_id.id])
        for user in (cls.host, cls.guest):
            member = cls.env['discuss.channel.member'].search([
                ('channel_id', '=', cls.channel.id),
                ('partner_id', '=', user.partner_id.id)], limit=1)
            cls.env['discuss.channel.rtc.session'].sudo().create({
                'channel_member_id': member.id})

    def setUp(self):
        super().setUp()
        # Tạo recording mới cho mỗi test để elapsed_ms > 0
        time.sleep(0.01)  # 10ms để chắc elapsed_ms > 0
        self.recording = self.env['aidt.meeting.recording'].with_user(
            self.host)._start_for_channel(self.channel)
        time.sleep(0.01)  # Thêm delay giữa setup và test


    def test_tam_dung_tao_mot_dong_va_doi_trang_thai(self):
        self.recording.with_user(self.host).action_pause()
        self.assertEqual(self.recording.state, 'paused')
        self.assertEqual(len(self.recording.pause_ids), 1)
        pause = self.recording.pause_ids
        self.assertTrue(pause.paused_at_ms >= 0)
        self.assertFalse(pause.resumed_at_ms)
        self.assertEqual(pause.paused_by_id, self.host)

    def test_ghi_tiep_dien_moc_va_tang_take(self):
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        self.assertEqual(self.recording.state, 'recording')
        self.assertEqual(self.recording.current_take, 1)
        pause = self.recording.pause_ids
        self.assertTrue(pause.resumed_at_ms >= pause.paused_at_ms)

    def test_hai_lan_tam_dung_cho_hai_dong_va_take_bang_hai(self):
        for _ in range(2):
            self.recording.with_user(self.host).action_pause()
            self.recording.with_user(self.host).action_resume()
        self.assertEqual(len(self.recording.pause_ids), 2)
        self.assertEqual(self.recording.current_take, 2)

    def test_nguoi_du_khong_tam_dung_duoc(self):
        with self.assertRaises(AccessError):
            self.recording.with_user(self.guest).action_pause()

    def test_nguoi_du_khong_ghi_tiep_duoc(self):
        self.recording.with_user(self.host).action_pause()
        with self.assertRaises(AccessError):
            self.recording.with_user(self.guest).action_resume()

    def test_tam_dung_hai_lan_lien_tiep_khong_tao_dong_thua(self):
        """Bấm hai lần vì mạng chậm là chuyện thường. Lần thứ hai phải là
        no-op, không được mở một khoảng dừng thứ hai chồng lên khoảng đang mở."""
        self.recording.with_user(self.host).action_pause()
        self.assertFalse(self.recording.with_user(self.host).action_pause())
        self.assertEqual(len(self.recording.pause_ids), 1)

    def test_ghi_tiep_khi_dang_ghi_la_no_op(self):
        self.assertFalse(self.recording.with_user(self.host).action_resume())
        self.assertEqual(self.recording.current_take, 0)
