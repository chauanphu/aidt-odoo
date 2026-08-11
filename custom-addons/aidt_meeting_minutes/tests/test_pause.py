from datetime import timedelta
from odoo import fields
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
        # Tạo recording mới cho mỗi test
        self.recording = self.env['aidt.meeting.recording'].with_user(
            self.host)._start_for_channel(self.channel)


    def test_tam_dung_tao_mot_dong_va_doi_trang_thai(self):
        # Dịch started_at lùi lại 5 giây để tạm dừng có elapsed_ms > 0
        self.recording.sudo().started_at = fields.Datetime.now() - timedelta(seconds=5)
        self.recording.with_user(self.host).action_pause()
        self.assertEqual(self.recording.state, 'paused')
        self.assertEqual(len(self.recording.pause_ids), 1)
        pause = self.recording.pause_ids
        self.assertGreaterEqual(pause.paused_at_ms, 5000)
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

    def test_nguoi_vao_giua_luc_tam_dung_van_thay_ban_ghi(self):
        """Hàm này hiện chỉ tìm `state = 'recording'`, nên người vào lúc đang
        tạm dừng KHÔNG thấy gì và tưởng cuộc họp không được ghi. Đó là đúng
        thứ 'thông báo bắt buộc' phải chặn."""
        self.recording.with_user(self.host).action_pause()
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info.get('recording_id'), self.recording.id)
        self.assertEqual(info.get('state'), 'paused')

    def test_tra_ve_du_thong_tin_de_client_dung_bang(self):
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info['state'], 'recording')
        self.assertEqual(info['take'], 0)
        self.assertEqual(info['host_partner_id'], self.host.partner_id.id)

    def test_take_phan_anh_so_lan_ghi_tiep(self):
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertEqual(info['take'], 1)

    def test_tom_tat_doan_dung_cho_nguoi_doc_bien_ban(self):
        """Biên bản KHÔNG phủ hết cuộc họp là điều ảnh hưởng tới giá trị
        pháp lý của nó — người đọc phải thấy ngay, không phải tự suy ra."""
        self.recording.with_user(self.host).action_pause()
        self.recording.with_user(self.host).action_resume()
        self.assertIn('1 đoạn không được ghi', self.recording.pause_summary)

    def test_khong_co_doan_dung_thi_tom_tat_rong(self):
        self.assertFalse(self.recording.pause_summary)

    def test_doan_dung_con_mo_khi_ket_thuc_khong_bao_khong_phut(self):
        """Kết thúc trong lúc đang tạm dừng để lại một khoảng dừng CÒN MỞ
        (`resumed_at_ms` rỗng) — theo hợp đồng Task 9, đó là khoảng dừng kéo
        dài tới HẾT cuộc họp, tức loại DÀI NHẤT có thể có, không phải 0 giây.
        Tóm tắt phải nói rõ có một đoạn không ghi tới hết cuộc họp, không
        được ngầm cộng nó là 0."""
        self.recording.sudo().started_at = fields.Datetime.now() - timedelta(seconds=5)
        self.recording.with_user(self.host).action_pause()
        summary = self.recording.pause_summary
        self.assertIn('1 đoạn không được ghi', summary)
        self.assertIn('tới hết cuộc họp', summary)
        self.assertNotIn('tổng 0 phút 0 giây', summary)

    def test_ket_thuc_van_tra_ve_chu_phong_de_bat_lai(self):
        """Task 8 vòng 2: `canStart` ở client chỉ cho chủ phòng thấy nút
        "Bật ghi âm biên bản". Sau khi bản ghi kết thúc mà cuộc gọi vẫn còn
        (chủ phòng chưa rời — `setUpClass` cho cả `host` và `guest` phiên
        RTC), `host_partner_id` phải vẫn còn đúng — không thì không ai bật
        lại được lần hai trong cùng cuộc gọi."""
        self.recording.with_user(self.host).action_stop()
        info = self.env['aidt.meeting.recording'].with_user(
            self.guest).action_active_recording(self.channel.id)
        self.assertNotIn('recording_id', info)
        self.assertEqual(info['host_partner_id'], self.host.partner_id.id)
