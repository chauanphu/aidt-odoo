from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestCallHost(TransactionCase):
    """Chủ phòng được chốt lúc cuộc gọi bắt đầu.

    Odoo không có khái niệm chủ phòng cho cuộc gọi. Suy ra sau bằng cách tìm
    phiên RTC sớm nhất là không đáng tin: phiên bị xoá rồi tạo lại mỗi lần
    người ta rớt mạng và vào lại, nên "sớm nhất" đổi theo thời gian.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thử chủ phòng',
            'channel_type': 'channel',
        })
        cls.user_a = cls.env['res.users'].create({
            'name': 'Người A', 'login': 'host_a@test.local'})
        cls.user_b = cls.env['res.users'].create({
            'name': 'Người B', 'login': 'host_b@test.local'})
        cls.channel.add_members(
            partner_ids=[cls.user_a.partner_id.id, cls.user_b.partner_id.id])
        # Kênh phải là PHÒNG HỌP: từ 19.0.1.4.0, chủ phòng chỉ được chốt và
        # ghi âm chỉ bật được trong kênh có `calendar.event` đứng sau.
        # `user_id` = A vì mọi test dưới đây coi A là người chủ trì.
        now = fields.Datetime.now()
        cls.event = cls.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': 'Cuộc họp thử',
            'start': now - timedelta(minutes=5),
            'stop': now + timedelta(hours=1),
            'user_id': cls.user_a.id,
            'videocall_channel_id': cls.channel.id,
        })

    def _member(self, user):
        return self.env['discuss.channel.member'].search([
            ('channel_id', '=', self.channel.id),
            ('partner_id', '=', user.partner_id.id),
        ], limit=1)

    def _join(self, user):
        return self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': self._member(user).id,
        })

    def test_nguoi_vao_dau_tien_thanh_chu_phong(self):
        """Từ khi `setUpClass` gắn `calendar.event` (user_id=user_a), test
        này không còn phân biệt được "A là người vào trước" với "A là người
        chủ trì lịch" — cả hai lý do đều cho cùng kết quả A, nên test không
        chứng minh được nó nói gì nữa. Giữ lại vì kết luận (A là chủ phòng)
        vẫn đúng và vẫn đáng kiểm; `test_chu_tri_thang_du_vao_sau` bên dưới
        mới là chỗ tách được hai lý do đó ra."""
        self._join(self.user_a)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_nguoi_vao_sau_khong_doi_chu_phong(self):
        """Cùng lưu ý như test phía trên: A vào trước, B vào sau, host vẫn
        là A — giờ đúng nhờ CẢ HAI cơ chế cùng lúc (thứ tự vào lẫn
        `event.user_id`) nên không còn chứng minh riêng được "người vào sau
        không đổi chủ phòng". Test dưới đây (`test_chu_tri_thang_du_vao_sau`)
        đảo ngược thứ tự vào để tách hai cơ chế ra."""
        self._join(self.user_a)
        self._join(self.user_b)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_chu_tri_thang_du_vao_sau(self):
        """Bất biến MỚI kể từ khi kênh có lịch: người chủ trì LỊCH thắng bất
        kể thứ tự vào phòng. Khác hẳn hai test phía trên (nơi A vừa vào
        trước vừa là chủ trì, không tách được lý do), ở đây B vào TRƯỚC và A
        (chủ trì) vào SAU — host vẫn phải là A.

        Đây chính là lỗi I1 đã sửa ở nhánh trước: một chuyên viên vào sớm 2
        phút không được nghiễm nhiên khoá chết quyền ghi âm của lãnh đạo chủ
        trì. Thiếu test này thì lỗi đó quay lại mà không ai biết, vì hai test
        phía trên không còn đủ sức phân biệt hai cơ chế nữa."""
        self._join(self.user_b)
        self._join(self.user_a)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_chu_phong_roi_nhung_con_nguoi_khac_thi_giu_nguyen(self):
        """Rớt mạng vài giây rồi vào lại là chuyện thường. Đổi chủ phòng
        theo mỗi lần đó thì quyền điều khiển nhảy loạn giữa cuộc họp."""
        session_a = self._join(self.user_a)
        self._join(self.user_b)
        session_a.unlink()
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_a.partner_id)

    def test_cuoc_goi_trong_thi_xoa_chu_phong(self):
        session_a = self._join(self.user_a)
        session_a.unlink()
        self.assertFalse(self.channel.aidt_call_host_partner_id)


@tagged('post_install', '-at_install')
class TestStartPermission(TestCallHost):
    """Chỉ người chủ trì cuộc họp mới bật được ghi âm, và chỉ trong phòng họp.

    Từ 19.0.1.4.0 chỉ còn MỘT nhánh: mọi phòng ghi âm được đều có
    `calendar.event`, nên `event.user_id` luôn tồn tại. Nhánh "cuộc gọi tự
    phát, chủ phòng cuộc gọi bật được" đã bị gỡ — chính nhánh đó sinh ra lỗi
    I1 ở nhánh trước (người vào sớm khoá chết quyền của lãnh đạo chủ trì).
    """

    def test_chu_phong_bat_duoc(self):
        self._join(self.user_a)
        recording = self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)
        self.assertEqual(recording.state, 'recording')
        self.assertEqual(recording.host_partner_id, self.user_a.partner_id)

    def test_nguoi_khong_phai_chu_phong_bi_chan(self):
        """Thông điệp thật là "Chỉ chủ phòng…", KHÔNG phải "Chỉ người chủ trì
        cuộc họp…": trong phòng họp, chủ phòng LUÔN được chốt vào
        `event.user_id`, nên guard chủ phòng bắt trước guard chủ trì. Ba test
        ở lớp này ghim đúng ba thông điệp mà `docs/GUIDANCE.md` §2.3 hứa với
        người dùng."""
        self._join(self.user_a)
        self._join(self.user_b)
        with self.assertRaisesRegex(
                AccessError, 'Chỉ chủ phòng mới bật được ghi âm.'):
            self.env['aidt.meeting.recording'].with_user(
                self.user_b)._start_for_channel(self.channel)

    def test_khong_co_cuoc_goi_thi_khong_ai_bat_duoc(self):
        """Chưa ai vào cuộc gọi thì chưa có chủ phòng."""
        with self.assertRaisesRegex(
                AccessError, 'Chưa có cuộc gọi nào đang diễn ra trên kênh này.'):
            self.env['aidt.meeting.recording'].with_user(
                self.user_a)._start_for_channel(self.channel)

    def test_chu_phong_la_ban_chup_khong_phai_related(self):
        """Chủ phòng của KÊNH đổi được sau đó (họp đổi người chủ trì, cuộc
        gọi mới). "Ai đã bật bản ghi này" là dữ kiện lịch sử của biên bản,
        phải đứng yên.

        Trước 19.0.1.4.0, kịch bản minh hoạ là "người khác vào phòng trước".
        Giờ chủ phòng luôn chốt vào `event.user_id` bất kể thứ tự vào, nên
        kịch bản đó không còn tạo ra được sự khác biệt nào — phải đổi
        `event.user_id` (họp được phân công lại người chủ trì) để chủ phòng
        của KÊNH thực sự đổi sang người khác, trong khi bản ghi đã tạo vẫn
        giữ nguyên `host_partner_id` cũ."""
        session_a = self._join(self.user_a)
        recording = self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)
        session_a.unlink()
        self.event.user_id = self.user_b
        self._join(self.user_b)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         self.user_b.partner_id)
        self.assertEqual(recording.host_partner_id, self.user_a.partner_id)

    def test_kenh_khong_phai_phong_hop_thi_khong_bat_duoc(self):
        """Bắt ĐÚNG thông điệp, không chỉ `AccessError`. Kênh thường không
        bao giờ được chốt chủ phòng (`discuss_channel_rtc_session`), nên nếu
        khối chủ phòng lại bị đưa lên trước khối "phòng họp" trong
        `_start_for_channel` thì test này vẫn xanh với `assertRaises` trần —
        trong khi người dùng nhận "Chưa có cuộc gọi nào đang diễn ra trên
        kênh này." dù cuộc gọi ĐANG diễn ra thật (phiên RTC dựng ngay dưới
        đây), và câu "Chỉ ghi âm được trong phòng họp." thành mã chết."""
        thuong = self.env['discuss.channel'].create({
            'name': 'Kênh thường', 'channel_type': 'channel'})
        thuong.add_members(partner_ids=[self.user_a.partner_id.id])
        self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': self.env['discuss.channel.member'].search([
                ('channel_id', '=', thuong.id),
                ('partner_id', '=', self.user_a.partner_id.id)], limit=1).id,
        })
        with self.assertRaisesRegex(
                AccessError, 'Chỉ ghi âm được trong phòng họp.'):
            self.env['aidt.meeting.recording'].with_user(
                self.user_a)._start_for_channel(thuong)

    def test_chu_tri_khong_o_trong_kenh_thi_khong_ai_ghi_am_duoc(self):
        """Người chủ trì KHÔNG nằm trong Danh sách dự => phòng chết.

        Nếp làm việc bình thường ở đây: văn thư mở "Quản lý cuộc họp", đặt
        Organizer = lãnh đạo, tích ô phòng họp. Odoo KHÔNG tự thêm người chủ
        trì vào `partner_ids` (`_default_partners` chỉ điền chính người tạo,
        `addons/calendar/models/calendar_event.py:110`), mà thành viên kênh
        lấy từ `partner_ids` (`_create_videocall_channel_id`, :1069). Kết quả
        là chủ phòng được chốt vào một người KHÔNG có trong kênh:

        * lãnh đạo -> "Bạn không thuộc cuộc gọi này." (và không thấy phòng
          trong thanh bên vì không phải thành viên);
        * văn thư  -> "Chỉ chủ phòng mới bật được ghi âm.";

        tức không ai bật được ghi âm và màn hình không nói vì sao. Logic này
        có TỪ TRƯỚC đợt "phòng họp"; đợt này chỉ làm nó dễ gặp hơn nhiều
        (trang tạo họp nay đặt trước mặt mọi người dùng nội bộ). Test khoá
        cả hai thông điệp lẫn LỐI THOÁT đã ghi ở `docs/GUIDANCE.md` §2.5 —
        thêm người chủ trì vào Danh sách dự, `write` sẽ gọi `add_members`
        (`calendar_event.py:794`) và phòng sống lại.
        """
        vang_mat = self.env['res.users'].create({
            'name': 'Lãnh đạo chủ trì', 'login': 'host_absent@test.local'})
        self.event.user_id = vang_mat
        self.assertNotIn(
            vang_mat.partner_id,
            self.channel.sudo().channel_member_ids.partner_id,
            'tiền đề: người chủ trì KHÔNG được là thành viên kênh')

        # Văn thư (thành viên) vào cuộc gọi -> chủ phòng chốt vào người vắng.
        self._join(self.user_a)
        self.assertEqual(self.channel.aidt_call_host_partner_id,
                         vang_mat.partner_id)

        with self.assertRaisesRegex(
                AccessError, 'Chỉ chủ phòng mới bật được ghi âm.'):
            self.env['aidt.meeting.recording'].with_user(
                self.user_a)._start_for_channel(self.channel)
        with self.assertRaisesRegex(
                AccessError, 'Bạn không thuộc cuộc gọi này.'):
            self.env['aidt.meeting.recording'].with_user(
                vang_mat)._start_for_channel(self.channel)

        # Lối thoát: thêm người chủ trì vào Danh sách dự.
        self.event.write({'partner_ids': [(4, vang_mat.partner_id.id)]})
        self.assertIn(
            vang_mat.partner_id,
            self.channel.sudo().channel_member_ids.partner_id,
            'ghi `partner_ids` phải kéo người chủ trì vào kênh')
        recording = self.env['aidt.meeting.recording'].with_user(
            vang_mat)._start_for_channel(self.channel)
        self.assertEqual(recording.state, 'recording')

    def test_action_active_recording_tra_rong_cho_kenh_thuong(self):
        """Đây là điều kiện DUY NHẤT làm nút "Bật ghi âm biên bản" hiện ra.
        Trả `host_partner_id` cho kênh thường nghĩa là nút vẫn mời người ta
        bấm rồi mới ăn AccessError."""
        thuong = self.env['discuss.channel'].create({
            'name': 'Kênh thường 2', 'channel_type': 'channel'})
        thuong.add_members(partner_ids=[self.user_a.partner_id.id])
        info = self.env['aidt.meeting.recording'].with_user(
            self.user_a).action_active_recording(thuong.id)
        self.assertEqual(info, {})


@tagged('post_install', '-at_install')
class TestEndRecording(TestCallHost):
    def _start(self):
        self._join(self.user_a)
        self._join(self.user_b)
        return self.env['aidt.meeting.recording'].with_user(
            self.user_a)._start_for_channel(self.channel)

    def test_chu_phong_ket_thuc_duoc(self):
        recording = self._start()
        self.assertTrue(recording.with_user(self.user_a).action_stop())
        self.assertEqual(recording.state, 'processing')

    def test_nguoi_du_khong_ket_thuc_duoc(self):
        recording = self._start()
        with self.assertRaises(AccessError):
            recording.with_user(self.user_b).action_stop()
        self.assertEqual(recording.state, 'recording')

    def test_nguoi_du_roi_cuoc_goi_thi_ban_ghi_VAN_chay(self):
        """Khiếm khuyết đang có hôm nay: rời cuộc gọi -> clear() ->
        leaveCall() -> stop() -> POST finalize_recording -> action_stop()
        cho TOÀN BỘ bản ghi. Người vô tình đóng tab ở phút thứ 5 làm cả cuộc
        họp mất phần còn lại của biên bản."""
        recording = self._start()
        member_b = self._member(self.user_b)
        self.env['discuss.channel.rtc.session'].sudo().search(
            [('channel_member_id', '=', member_b.id)]).unlink()
        self.assertEqual(recording.state, 'recording')

    def test_cuoc_goi_trong_thi_tu_ket_thuc(self):
        recording = self._start()
        self.env['discuss.channel.rtc.session'].sudo().search(
            [('channel_id', '=', self.channel.id)]).unlink()
        self.assertEqual(recording.state, 'processing')

    def test_dang_tam_dung_van_ket_thuc_duoc(self):
        """Không bắt chủ phòng phải ghi tiếp rồi mới dừng được."""
        recording = self._start()
        recording.with_user(self.user_a).action_pause()
        self.assertTrue(recording.with_user(self.user_a).action_stop())
        self.assertEqual(recording.state, 'processing')

    def test_ket_thuc_luc_dang_dung_thi_khong_dien_moc_ghi_tiep(self):
        recording = self._start()
        recording.with_user(self.user_a).action_pause()
        recording.with_user(self.user_a).action_stop()
        self.assertFalse(recording.pause_ids.resumed_at_ms)
