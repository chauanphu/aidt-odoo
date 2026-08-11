from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class RecordingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Recording = cls.env['aidt.meeting.recording']
        cls.organizer = cls.env['res.users'].create({
            'name': 'Người chủ trì', 'login': 'chutri@test.local',
        })
        cls.member = cls.env['res.users'].create({
            'name': 'Thành viên', 'login': 'thanhvien@test.local',
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Người ngoài', 'login': 'nguoingoai@test.local',
        })

    def _channel(self, partners, in_call=True):
        """Kênh có `partners` là thành viên.

        `in_call=True` (mặc định) còn cho họ một phiên RTC — tức là họ đang
        THỰC SỰ ở trong cuộc gọi. Phân biệt này là bản chất: quyền dừng/từ
        chối/gửi audio xét theo người có mặt trong cuộc gọi, không theo danh
        sách thành viên kênh (xem `_is_participant`).
        """
        channel = self.env['discuss.channel'].create({
            'name': 'Cuộc gọi thử', 'channel_type': 'channel',
        })
        channel.add_members(partner_ids=[p.id for p in partners])
        if in_call:
            for partner in partners:
                self._join_call(channel, partner)
        return channel

    def _join_call(self, channel, partner):
        member = self.env['discuss.channel.member'].search([
            ('channel_id', '=', channel.id), ('partner_id', '=', partner.id),
        ], limit=1)
        return self.env['discuss.channel.rtc.session'].sudo().create({
            'channel_member_id': member.id,
        })

    def _event(self, channel, secrecy='thuong'):
        return self.env['calendar.event'].create({
            'name': 'Họp giao ban',
            'start': '2026-08-04 01:00:00', 'stop': '2026-08-04 02:00:00',
            'user_id': self.organizer.id,
            'secrecy': secrecy,
            'videocall_channel_id': channel.id,
            'partner_ids': [(6, 0, [self.organizer.partner_id.id,
                                    self.member.partner_id.id])],
        })


class TestScheduledMeeting(RecordingCase):
    def test_nguoi_chu_tri_bat_duoc(self):
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        event = self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.event_id, event)

    def test_nguoi_khong_chu_tri_khong_bat_duoc(self):
        """Cuộc họp có lịch thì chỉ người chủ trì được bật — khác hẳn cuộc
        gọi tự phát, nơi thành viên bất kỳ đều bật được."""
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.member)._start_for_channel(channel)

    def test_do_mat_vuot_nguong_thi_chan(self):
        channel = self._channel([self.organizer.partner_id])
        self._event(channel, secrecy='mat')
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)

    def test_chup_lai_do_mat_luc_bat_dau(self):
        """Bản chụp, không phải related: đổi phân loại về sau không được làm
        một bản ghi đã hoàn tất trở thành trái phép một cách hồi tố, và hạ
        phân loại cũng không được hợp thức hoá nó."""
        channel = self._channel([self.organizer.partner_id])
        event = self._event(channel, secrecy='thuong')
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        event.secrecy = 'tuyet_mat'
        self.assertEqual(rec.secrecy_at_start, 'thuong')

    def test_nguong_rac_thi_chan_tren_muc_thuong(self):
        """Cấu hình `aidt_meeting.max_secrecy` bị hỏng (giá trị không nằm
        trong SECRECY_ORDER) phải lùi về mức chặt nhất ('thuong'), TUYỆT ĐỐI
        không được mở rộng quyền ghi âm. Nếu sau này ai đó "dọn dẹp" nhánh
        `except ValueError` trong `_check_secrecy_allowed` thành
        `allowed = len(SECRECY_ORDER) - 1`, ngưỡng sẽ âm thầm hỏng theo
        chiều MỞ — mọi cuộc họp có phân loại đều ghi âm được — mà cả bộ test
        vẫn xanh nếu không có test này. Test này là hàng rào chặn hồi quy
        đó: cấu hình rác + cuộc họp mức "mat" (trên "thuong" một bậc) phải
        bị chặn."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.max_secrecy', 'khong_hop_le')
        channel = self._channel([self.organizer.partner_id])
        self._event(channel, secrecy='mat')
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)


class TestAdHocCall(RecordingCase):
    def test_khong_co_lich_van_bat_duoc(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertFalse(rec.event_id)

    def test_cuoc_goi_tu_phat_coi_nhu_thuong(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertEqual(rec.secrecy_at_start, 'thuong')

    def test_khong_cho_nguoi_ngoai_bat_ghi_am(self):
        channel = self._channel([self.member.partner_id])
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.outsider)._start_for_channel(channel)

    def test_khong_bat_trung_hai_ban_ghi_tren_mot_channel(self):
        channel = self._channel([self.member.partner_id])
        self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.member)._start_for_channel(channel)


class TestStopPermission(RecordingCase):
    def test_nguoi_du_khong_phai_chu_phong_khong_dung_duoc(self):
        """Đảo ngược thiết kế cũ: trước đây để BẤT KỲ người tham gia nào cũng
        dừng được, với lý lẽ ai nhận ra nội dung Mật thì tự tắt ngay cho
        nhanh. Nhưng "ai cũng dừng được" cũng có nghĩa MỘT người bấm nhầm
        (hoặc bấm sớm) làm cả cuộc họp mất phần còn lại của biên bản — của
        cả những người khác, không chỉ của riêng họ. Quyền kết thúc giờ dồn
        về một mối: người thấy nội dung nhạy cảm phải báo chủ phòng bấm
        dừng, không tự ý cắt hộ mọi người."""
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.member).action_stop()
        self.assertEqual(rec.state, 'recording')

    def test_nguoi_ngoai_khong_dung_duoc(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    def test_thanh_vien_kenh_khong_trong_cuoc_goi_khong_dung_duoc(self):
        """"Bất kỳ người tham gia nào cũng dừng được" nghĩa là người tham gia
        CUỘC GỌI, không phải mọi người có tên trong kênh. Nếu chỉ xét thành
        viên kênh thì bất kỳ ai trong một kênh phòng ban 200 người cũng cắt
        được bản ghi của một cuộc gọi 3 người mà họ không dự — và đọc được
        audio thô của cuộc gọi đó."""
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        channel.add_members(partner_ids=[self.outsider.partner_id.id])
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    def test_nguoi_vao_hop_muon_khong_phai_chu_phong_khong_dung_duoc(self):
        """Chủ trì LỊCH không đồng nghĩa chủ phòng CUỘC GỌI. Ở đây
        `self.member` vào cuộc gọi TRƯỚC nên là chủ phòng, dù `self.organizer`
        ("Người chủ trì") mới vào sau — vào muộn, dù là ai, cũng không có
        quyền dừng thay chủ phòng."""
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        channel.add_members(partner_ids=[self.organizer.partner_id.id])
        self._join_call(channel, self.organizer.partner_id)
        with self.assertRaises(AccessError):
            rec.with_user(self.organizer).action_stop()
        self.assertEqual(rec.state, 'recording')


class TestActionStartForChannel(RecordingCase):
    """`action_start_for_channel` là wrapper PUBLIC của `_start_for_channel`
    — KHÔNG được nới lỏng bất kỳ kiểm tra phân quyền nào của bản gốc."""

    def test_nguoi_chu_tri_bat_duoc_qua_wrapper(self):
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        event = self._event(channel)
        recording_id = self.Recording.with_user(
            self.organizer).action_start_for_channel(channel.id)
        rec = self.Recording.browse(recording_id)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.event_id, event)

    def test_nguoi_khong_chu_tri_van_bi_chan_qua_wrapper(self):
        # Wrapper không được là đường vòng bỏ qua kiểm tra chủ trì.
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        with self.assertRaises(AccessError):
            self.Recording.with_user(
                self.member).action_start_for_channel(channel.id)

    def test_do_mat_vuot_nguong_van_bi_chan_qua_wrapper(self):
        # Wrapper không được là đường vòng bỏ qua ngưỡng độ mật.
        channel = self._channel([self.organizer.partner_id])
        self._event(channel, secrecy='mat')
        with self.assertRaises(UserError):
            self.Recording.with_user(
                self.organizer).action_start_for_channel(channel.id)

    def test_kenh_khong_ton_tai_bao_loi_ro_rang(self):
        with self.assertRaises(UserError):
            self.Recording.with_user(self.member).action_start_for_channel(999999)


class TestActiveRecordingReader(RecordingCase):
    """`action_active_recording` là nửa server của việc "vào họp muộn / F5 vẫn
    thấy băng đồng thuận". Broadcast `started` chỉ phát MỘT LẦN; không có
    phương thức đọc này thì người nạp lại tab giữa cuộc họp vĩnh viễn không
    biết mình đang bị ghi âm."""

    def test_tra_ve_ban_ghi_dang_chay_cho_thanh_vien(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertEqual(info['recording_id'], rec.id)
        self.assertEqual(info['channel_id'], channel.id)
        self.assertIn('elapsed_ms', info)

    def test_khong_co_ban_ghi_thi_khong_tra_ve_recording_id(self):
        """Không có bản ghi thì không còn `recording_id`/`channel_id`/... —
        nhưng KHÔNG rỗng hẳn nữa (Task 8 vòng 2): vẫn phải kèm
        `host_partner_id` của CUỘC GỌI, để client biết ai được phép thấy
        nút "Bật ghi âm biên bản" trước khi có bản ghi nào. Xem
        `TestActiveRecordingHostBeforeRecording` bên dưới cho test riêng
        của khoá đó."""
        channel = self._channel([self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)

    def test_ban_ghi_da_dung_thi_khong_tra_ve_recording_id(self):
        """Chỉ trạng thái 'recording' mới đáng bật micro. 'processing' là đã
        có lệnh dừng — không được kéo một máy vừa F5 vào thu tiếp."""
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        rec.with_user(self.member).action_stop()
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)

    def test_nguoi_ngoai_kenh_bi_chan(self):
        # Wrapper public KHÔNG được là lỗ rò id bản ghi cho người ngoài kênh.
        channel = self._channel([self.member.partner_id])
        self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            self.Recording.with_user(
                self.outsider).action_active_recording(channel.id)

    def test_ghi_nhan_nguoi_vao_hop_muon(self):
        """Gọi phương thức này là lời khai "tôi đang trong cuộc gọi" — đúng
        thời điểm để ghi người vào muộn vào tập người tham gia, nếu không họ
        sẽ bị chính `_is_participant` chặn khi gửi mẩu audio đầu tiên."""
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        channel.add_members(partner_ids=[self.organizer.partner_id.id])
        self._join_call(channel, self.organizer.partner_id)
        self.assertNotIn(self.organizer.partner_id, rec.participant_partner_ids)
        self.Recording.with_user(
            self.organizer).action_active_recording(channel.id)
        self.assertIn(self.organizer.partner_id, rec.participant_partner_ids)


class TestActiveRecordingHostBeforeRecording(RecordingCase):
    """Task 8 vòng 2: `canStart` ở client chỉ cho ĐÚNG chủ phòng thấy nút
    "Bật ghi âm biên bản" — kể cả TRƯỚC KHI có bản ghi nào. Điều kiện đó
    không có cách nào đứng vững nếu server không trả `host_partner_id`
    ngay từ đây; server chặn thật ở `_start_for_channel`, nhưng thiếu khoá
    này thì client không có gì để tự lọc nút trước khi gọi tới đó."""

    def test_chua_co_ban_ghi_van_tra_ve_chu_phong_cuoc_goi(self):
        # `_channel` cho `organizer` vào cuộc gọi TRƯỚC — đúng thứ tự
        # `discuss_channel_rtc_session.py` dùng để chốt chủ phòng: người có
        # phiên RTC đầu tiên trên kênh.
        channel = self._channel([self.organizer.partner_id, self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)
        self.assertEqual(info['host_partner_id'], self.organizer.partner_id.id)

    def test_chua_ai_vao_cuoc_goi_thi_khong_co_chu_phong(self):
        # Fail-closed đúng hướng: thành viên kênh nhưng KHÔNG có phiên RTC
        # nào (chưa ai bấm vào cuộc gọi) — không suy ra bừa một chủ phòng.
        channel = self._channel([self.member.partner_id], in_call=False)
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertFalse(info['host_partner_id'])

    def test_ket_thuc_ban_ghi_van_giu_dung_chu_phong_de_bat_lai(self):
        """Chủ phòng dừng bản ghi nhưng vẫn còn trong cuộc gọi — phải bật
        lại được lần nữa trong CÙNG cuộc gọi đó, nên `host_partner_id` không
        được biến mất chỉ vì bản ghi đã dừng."""
        channel = self._channel([self.organizer.partner_id, self.member.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.organizer).action_stop()
        info = self.Recording.with_user(
            self.organizer).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)
        self.assertEqual(info['host_partner_id'], self.organizer.partner_id.id)


class TestReadAccess(RecordingCase):
    """Ai ĐỌC được bản ghi và đoạn bóc băng.

    `security/aidt_meeting_rules.xml` tự khẳng định điều này bằng chính nó và
    không có gì khác kiểm lại: bộ test cũ chỉ phủ ai được bật/dừng/từ chối.
    Nếu ai đó "đơn giản hoá" domain về chỉ còn `event_id` — đúng sai lầm mà
    comment trong file XML cảnh báo — thì mọi bản ghi của CUỘC GỌI TỰ PHÁT
    (`event_id = False`) sẽ lộ ra cho toàn hệ thống, mà mọi test vẫn xanh.
    """

    def test_nguoi_ngoai_khong_doc_duoc_ban_ghi_nao(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertFalse(
            self.Recording.with_user(self.outsider).search(
                [('id', '=', rec.id)]))

    def test_thanh_vien_kenh_doc_duoc_ban_ghi_khong_co_cuoc_hop(self):
        """Cuộc gọi tự phát: `event_id` rỗng. Một rule chỉ dựa vào `event_id`
        sẽ khiến chính người trong cuộc gọi KHÔNG đọc nổi bản ghi của mình —
        và (tuỳ cách viết) để lọt nó cho tất cả những người khác."""
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        self.assertFalse(rec.event_id)
        self.assertTrue(
            self.Recording.with_user(self.member).search([('id', '=', rec.id)]))

    def test_nguoi_du_hop_doc_duoc_qua_event(self):
        """Nhánh thứ hai của rule: người được mời trong `event_id.partner_ids`
        đọc được kể cả khi không (hoặc không còn) là thành viên kênh."""
        channel = self._channel([self.organizer.partner_id])
        event = self._event(channel)
        rec = self.Recording.with_user(
            self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.event_id, event)
        self.assertIn(self.member.partner_id, event.partner_ids)
        self.assertTrue(
            self.Recording.with_user(self.member).search([('id', '=', rec.id)]))
