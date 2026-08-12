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

    def _meeting_channel(self, partners, secrecy='thuong'):
        """Kênh ĐÃ LÀ phòng họp — có `calendar.event` đứng sau.

        Từ 19.0.1.4.0 ghi âm chỉ tồn tại trong phòng họp, nên đây là hình
        dạng mặc định của gần như mọi test dưới đây. `_channel()` trần được
        giữ lại đúng cho những test cần chứng minh kênh THƯỜNG bị từ chối.

        Lưu ý: `_event()` ghim CỨNG `user_id = self.organizer` — kênh nào
        qua đây cũng chỉ có `self.organizer` bật ghi âm được. Test nào cần
        một người KHÁC bật thành công thì không dùng helper này.

        THỨ TỰ ở đây là bắt buộc, không phải tình cờ: `discuss_channel_rtc_session`
        chỉ chốt chủ phòng lúc TẠO phiên RTC, và Bước 4 của Task 4 chỉ làm
        vậy khi `_event_for_channel(channel)` đã có gì đó để trả về NGAY LÚC
        ĐÓ. Gọi `_channel(partners)` mặc định (`in_call=True`) tạo phiên RTC
        trước khi có `calendar.event`, nên `aidt_call_host_partner_id` không
        bao giờ được ghi — mọi `_start_for_channel` sau đó rơi vào nhánh
        "Chưa có cuộc gọi nào đang diễn ra" thay vì nhánh đang muốn kiểm.
        Vì `AccessError` là con của `UserError`
        (`odoo/exceptions.py:AccessError(UserError)`), nhiều test mong
        `UserError` (vượt ngưỡng độ mật) vẫn "xanh" dù bắt nhầm exception —
        lỗi loại im lặng nguy hiểm nhất. Phải `in_call=False` rồi tự vào
        cuộc gọi SAU khi `_event()` đã gắn xong.
        """
        channel = self._channel(partners, in_call=False)
        self._event(channel, secrecy=secrecy)
        for partner in partners:
            self._join_call(channel, partner)
        return channel


class TestScheduledMeeting(RecordingCase):
    def test_nguoi_chu_tri_bat_duoc(self):
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        event = self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        self._join_call(channel, self.member.partner_id)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.event_id, event)

    def test_nguoi_khong_chu_tri_khong_bat_duoc(self):
        """Chỉ người chủ trì được bật. Từ 19.0.1.4.0 không còn vế đối chiếu
        nào để "khác hẳn": cuộc gọi không có lịch đứng sau thì không ai bật
        được — xem `TestKhongPhaiPhongHop`."""
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        self._join_call(channel, self.member.partner_id)
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.member)._start_for_channel(channel)

    def test_do_mat_vuot_nguong_thi_chan(self):
        channel = self._channel([self.organizer.partner_id], in_call=False)
        self._event(channel, secrecy='mat')
        self._join_call(channel, self.organizer.partner_id)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)

    def test_chup_lai_do_mat_luc_bat_dau(self):
        """Bản chụp, không phải related: đổi phân loại về sau không được làm
        một bản ghi đã hoàn tất trở thành trái phép một cách hồi tố, và hạ
        phân loại cũng không được hợp thức hoá nó."""
        channel = self._channel([self.organizer.partner_id], in_call=False)
        event = self._event(channel, secrecy='thuong')
        self._join_call(channel, self.organizer.partner_id)
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
        channel = self._channel([self.organizer.partner_id], in_call=False)
        self._event(channel, secrecy='mat')
        self._join_call(channel, self.organizer.partner_id)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)


class TestScheduledMeetingHost(RecordingCase):
    """I1: chủ phòng của một cuộc gọi có lịch chốt vào người chủ trì lịch
    NGAY LÚC phiên RTC đầu tiên được tạo (`discuss_channel_rtc_session.py`),
    bất kể ai vào phòng trước. Khôi phục đúng ngữ nghĩa TRƯỚC nhánh
    fix/meeting-stt-pipeline (chỉ người chủ trì lịch bật được ghi âm cuộc
    họp có lịch) — luật cũ "đồng thời là chủ phòng cuộc gọi VÀ event.user_id"
    là một hồi quy: một chuyên viên vào phòng sớm 2 phút thành chủ phòng,
    lãnh đạo chủ trì vào sau thì KHÔNG AI ghi âm được.
    """

    def test_chuyen_vien_vao_truoc_lanh_dao_van_la_chu_phong(self):
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        self._event(channel)  # lịch gắn kênh TRƯỚC khi ai vào cuộc gọi
        self._join_call(channel, self.member.partner_id)      # chuyên viên vào trước
        self._join_call(channel, self.organizer.partner_id)   # chủ trì vào sau
        self.assertEqual(channel.aidt_call_host_partner_id,
                         self.organizer.partner_id)
        rec = self.Recording.with_user(
            self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.host_partner_id, self.organizer.partner_id)

    def test_khong_co_lich_thi_khong_con_chu_phong(self):
        """Đảo ngược so với bản gốc
        (`test_khong_co_lich_thi_van_la_nguoi_vao_dau_tien`): bản gốc khẳng
        định kênh KHÔNG gắn lịch vẫn theo quy tắc "người vào đầu tiên thành
        chủ phòng" — đúng hành vi TRƯỚC Bước 4 của Task 4.

        Bước 4 (`discuss_channel_rtc_session.py`) đổi vòng lặp chốt chủ
        phòng để BỎ QUA hoàn toàn các kênh không có `calendar.event` đứng
        sau (`if not _event_for_channel(channel): continue`) — không còn ai
        đọc trường này cho kênh thường nữa: `_start_for_channel` chặn ngay
        từ cửa, `action_active_recording` trả `{}` tuyệt đối không kèm cả
        `host_partner_id`. Vì vậy với kênh không có lịch,
        `aidt_call_host_partner_id` giờ KHÔNG BAO GIỜ được ghi, bất kể ai
        vào trước hay sau."""
        channel = self._channel(
            [self.member.partner_id, self.organizer.partner_id],
            in_call=False)
        self._join_call(channel, self.member.partner_id)
        self._join_call(channel, self.organizer.partner_id)
        self.assertFalse(channel.aidt_call_host_partner_id)


class TestKhongPhaiPhongHop(RecordingCase):
    """Kênh thường không ghi âm được — thay cho TestAdHocCall cũ.

    Hai test đầu của lớp cũ (`test_khong_co_lich_van_bat_duoc`,
    `test_cuoc_goi_tu_phat_coi_nhu_thuong`) khẳng định đúng cái hành vi đang
    bị bỏ, nên bị đảo chiều chứ không sửa. Hai test sau kiểm chuyện KHÁC
    (người ngoài, bản ghi trùng) nên chỉ chuyển sang phòng họp.
    """

    def test_kenh_thuong_khong_bat_duoc(self):
        """Ghim ĐÚNG thông điệp: `_channel()` mặc định đã cho người ta vào
        cuộc gọi thật, nên nếu guard "phòng họp" bị đẩy xuống sau guard chủ
        phòng thì lỗi trả về là "Chưa có cuộc gọi nào đang diễn ra trên kênh
        này." — sai nguyên nhân — mà `assertRaises(AccessError)` trần vẫn
        xanh."""
        channel = self._channel([self.member.partner_id])
        with self.assertRaisesRegex(
                AccessError, 'Chỉ ghi âm được trong phòng họp.'):
            self.Recording.with_user(self.member)._start_for_channel(channel)

    def test_kenh_thuong_khong_tra_thong_tin_ghi_am(self):
        channel = self._channel([self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertEqual(info, {})

    def test_khong_cho_nguoi_ngoai_bat_ghi_am(self):
        channel = self._meeting_channel([self.member.partner_id])
        with self.assertRaises(AccessError):
            self.Recording.with_user(self.outsider)._start_for_channel(channel)

    def test_khong_bat_trung_hai_ban_ghi_tren_mot_channel(self):
        channel = self._meeting_channel([self.organizer.partner_id])
        self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(UserError):
            self.Recording.with_user(self.organizer)._start_for_channel(channel)


class TestStopPermission(RecordingCase):
    def test_nguoi_du_khong_phai_chu_phong_khong_dung_duoc(self):
        """Đảo ngược thiết kế cũ: trước đây để BẤT KỲ người tham gia nào cũng
        dừng được, với lý lẽ ai nhận ra nội dung Mật thì tự tắt ngay cho
        nhanh. Nhưng "ai cũng dừng được" cũng có nghĩa MỘT người bấm nhầm
        (hoặc bấm sớm) làm cả cuộc họp mất phần còn lại của biên bản — của
        cả những người khác, không chỉ của riêng họ. Quyền kết thúc giờ dồn
        về một mối: người thấy nội dung nhạy cảm phải báo chủ phòng bấm
        dừng, không tự ý cắt hộ mọi người."""
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        self._join_call(channel, self.member.partner_id)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.member).action_stop()
        self.assertEqual(rec.state, 'recording')

    def test_nguoi_ngoai_khong_dung_duoc(self):
        # Người BẬT đổi từ self.member sang self.organizer: từ 19.0.1.4.0
        # chỉ người chủ trì lịch mới bật được ghi âm (`_event` ghim cứng
        # user_id=organizer). Người bị kiểm ("người ngoài không dừng được")
        # giữ nguyên self.outsider — đó mới là thứ test này thật sự kiểm.
        channel = self._meeting_channel([self.organizer.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    def test_thanh_vien_kenh_khong_trong_cuoc_goi_khong_dung_duoc(self):
        """"Bất kỳ người tham gia nào cũng dừng được" nghĩa là người tham gia
        CUỘC GỌI, không phải mọi người có tên trong kênh. Nếu chỉ xét thành
        viên kênh thì bất kỳ ai trong một kênh phòng ban 200 người cũng cắt
        được bản ghi của một cuộc gọi 3 người mà họ không dự — và đọc được
        audio thô của cuộc gọi đó."""
        # Người BẬT đổi sang self.organizer cùng lý do như test phía trên.
        # self.outsider (được thêm làm thành viên KÊNH nhưng không vào cuộc
        # gọi) vẫn là người bị kiểm, không đổi.
        channel = self._meeting_channel([self.organizer.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        channel.add_members(partner_ids=[self.outsider.partner_id.id])
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    # `test_nguoi_vao_hop_muon_khong_phai_chu_phong_khong_dung_duoc` (cũ) đã
    # bị XOÁ — không sửa được. Nó dựa vào luật "ai vào cuộc gọi trước thành
    # chủ phòng" để chứng minh người vào muộn (dù tên là "chủ trì") không có
    # quyền dừng. Luật đó không còn áp dụng cho phòng họp: chủ phòng giờ LUÔN
    # chốt vào `event.user_id`, bất kể thứ tự vào (xem
    # `TestScheduledMeetingHost` và `TestCallHost.test_chu_tri_thang_du_vao_sau`
    # trong `test_host_control.py`) — nên "người chủ trì vào muộn vẫn không
    # phải chủ phòng" không còn xảy ra được nữa trong phòng họp. Còn với kênh
    # thường, ghi âm không bật được ngay từ dòng đầu của test (không còn
    # `rec` nào để thao tác tiếp). Không có kênh nào giữ được tiền đề gốc.


class TestActionStartForChannel(RecordingCase):
    """`action_start_for_channel` là wrapper PUBLIC của `_start_for_channel`
    — KHÔNG được nới lỏng bất kỳ kiểm tra phân quyền nào của bản gốc."""

    def test_nguoi_chu_tri_bat_duoc_qua_wrapper(self):
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        event = self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        self._join_call(channel, self.member.partner_id)
        recording_id = self.Recording.with_user(
            self.organizer).action_start_for_channel(channel.id)
        rec = self.Recording.browse(recording_id)
        self.assertEqual(rec.state, 'recording')
        self.assertEqual(rec.event_id, event)

    def test_nguoi_khong_chu_tri_van_bi_chan_qua_wrapper(self):
        # Wrapper không được là đường vòng bỏ qua kiểm tra chủ trì.
        channel = self._channel(
            [self.organizer.partner_id, self.member.partner_id],
            in_call=False)
        self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        self._join_call(channel, self.member.partner_id)
        with self.assertRaises(AccessError):
            self.Recording.with_user(
                self.member).action_start_for_channel(channel.id)

    def test_do_mat_vuot_nguong_van_bi_chan_qua_wrapper(self):
        # Wrapper không được là đường vòng bỏ qua ngưỡng độ mật.
        channel = self._channel([self.organizer.partner_id], in_call=False)
        self._event(channel, secrecy='mat')
        self._join_call(channel, self.organizer.partner_id)
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
        # Người BẬT đổi sang self.organizer (chỉ organizer bật được ghi âm
        # trong phòng họp). Người ĐỌC — chủ thể thật sự của test này ("cho
        # thành viên") — giữ nguyên self.member.
        channel = self._meeting_channel(
            [self.organizer.partner_id, self.member.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
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
        của khoá đó.

        Kênh phải LÀ phòng họp: từ 19.0.1.4.0, `action_active_recording`
        trả `{}` tuyệt đối (không có cả `host_partner_id`) cho kênh thường —
        xem `TestKhongPhaiPhongHop.test_kenh_thuong_khong_tra_thong_tin_ghi_am`.
        Không có `_meeting_channel` ở đây thì test này không còn phân biệt
        được với test đó."""
        channel = self._meeting_channel([self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)
        # `assertNotIn` một mình cũng đúng khi `info == {}`, tức là làm
        # `action_active_recording` trả `{}` cho MỌI kênh vẫn xanh — đúng cái
        # hồi quy sẽ giết nút "Bật ghi âm biên bản" ở phòng họp. Khoá còn lại
        # mới là thứ phân biệt phòng họp với kênh thường.
        self.assertIn('host_partner_id', info)

    def test_ban_ghi_da_dung_thi_khong_tra_ve_recording_id(self):
        """Chỉ trạng thái 'recording' mới đáng bật micro. 'processing' là đã
        có lệnh dừng — không được kéo một máy vừa F5 vào thu tiếp."""
        # Chỉ chủ phòng (organizer) mới bật/dừng được; người ĐỌC lại giữ
        # nguyên self.member — không phải chủ thể bị kiểm ở đây.
        channel = self._meeting_channel(
            [self.organizer.partner_id, self.member.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.organizer).action_stop()
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)

    def test_nguoi_ngoai_kenh_bi_chan(self):
        # Wrapper public KHÔNG được là lỗ rò id bản ghi cho người ngoài kênh.
        # Người BẬT đổi sang organizer; người bị kiểm (outsider) giữ nguyên.
        channel = self._meeting_channel([self.organizer.partner_id])
        self.Recording.with_user(self.organizer)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            self.Recording.with_user(
                self.outsider).action_active_recording(channel.id)

    def test_ghi_nhan_nguoi_vao_hop_muon(self):
        """Gọi phương thức này là lời khai "tôi đang trong cuộc gọi" — đúng
        thời điểm để ghi người vào muộn vào tập người tham gia, nếu không họ
        sẽ bị chính `_is_participant` chặn khi gửi mẩu audio đầu tiên.

        Vai "người vào muộn" đổi từ self.organizer sang self.member: chỉ
        organizer bật được ghi âm trong phòng họp (phải vào TRƯỚC để bật),
        nên không thể vừa là người bật vừa là người vào muộn. Hành vi được
        kiểm — "vào muộn thì bị đăng ký làm participant khi gọi phương thức
        này" — không gắn với danh tính cụ thể, nên đổi vai không làm mất gì.
        """
        channel = self._meeting_channel([self.organizer.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        channel.add_members(partner_ids=[self.member.partner_id.id])
        self._join_call(channel, self.member.partner_id)
        self.assertNotIn(self.member.partner_id, rec.participant_partner_ids)
        self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertIn(self.member.partner_id, rec.participant_partner_ids)


class TestActiveRecordingHostBeforeRecording(RecordingCase):
    """Task 8 vòng 2: `canStart` ở client chỉ cho ĐÚNG chủ phòng thấy nút
    "Bật ghi âm biên bản" — kể cả TRƯỚC KHI có bản ghi nào. Điều kiện đó
    không có cách nào đứng vững nếu server không trả `host_partner_id`
    ngay từ đây; server chặn thật ở `_start_for_channel`, nhưng thiếu khoá
    này thì client không có gì để tự lọc nút trước khi gọi tới đó.

    Từ 19.0.1.4.0, `action_active_recording` trả `{}` tuyệt đối cho kênh
    thường (Step 3 của Task 4) — mọi test trong lớp này phải dùng kênh ĐÃ LÀ
    phòng họp, nếu không sẽ mất luôn cả `host_partner_id` đang muốn kiểm.
    """

    def test_chua_co_ban_ghi_van_tra_ve_chu_phong_cuoc_goi(self):
        # Trước đây: `_channel` cho `organizer` vào cuộc gọi TRƯỚC để khớp
        # đúng luật "người vào đầu tiên thành chủ phòng". Từ khi kênh này là
        # phòng họp (`_meeting_channel`), thứ tự vào không còn quan trọng —
        # chủ phòng LUÔN chốt vào `event.user_id` = organizer (xem
        # `_resolve_host_partner`). Giữ nguyên thứ tự trong danh sách chỉ vì
        # nó vẫn đúng, không phải vì nó còn là điều kiện quyết định.
        channel = self._meeting_channel(
            [self.organizer.partner_id, self.member.partner_id])
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)
        self.assertEqual(info['host_partner_id'], self.organizer.partner_id.id)

    def test_chua_ai_vao_cuoc_goi_thi_khong_co_chu_phong(self):
        # Fail-closed đúng hướng: thành viên kênh nhưng KHÔNG có phiên RTC
        # nào (chưa ai bấm vào cuộc gọi) — không suy ra bừa một chủ phòng.
        # Không dùng `_meeting_channel` ở đây vì nó ép `in_call=True`; phải
        # tự ghép `_channel(..., in_call=False)` + `_event(...)` để giữ đúng
        # "chưa ai vào cuộc gọi" trong khi kênh vẫn là phòng họp.
        channel = self._channel([self.member.partner_id], in_call=False)
        self._event(channel)
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertFalse(info['host_partner_id'])

    def test_ket_thuc_ban_ghi_van_giu_dung_chu_phong_de_bat_lai(self):
        """Chủ phòng dừng bản ghi nhưng vẫn còn trong cuộc gọi — phải bật
        lại được lần nữa trong CÙNG cuộc gọi đó, nên `host_partner_id` không
        được biến mất chỉ vì bản ghi đã dừng."""
        channel = self._meeting_channel(
            [self.organizer.partner_id, self.member.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.organizer).action_stop()
        info = self.Recording.with_user(
            self.organizer).action_active_recording(channel.id)
        self.assertNotIn('recording_id', info)
        self.assertEqual(info['host_partner_id'], self.organizer.partner_id.id)


class TestPhongHopBienMatGiuaChung(RecordingCase):
    """Kênh THÔI là phòng họp trong lúc bản ghi vẫn đang chạy.

    Xảy ra thật: chủ trì xoá cuộc họp khỏi Lịch, hoặc bỏ tích tạo phòng
    (`videocall_channel_id` bị gỡ), trong khi cuộc gọi vẫn tiếp diễn.

    Đây KHÔNG phải chuyện hiển thị. `action_active_recording` là nửa server
    của băng 🔴 "Cuộc họp đang được ghi âm…": mọi máy F5 hoặc vào muộn chỉ
    biết mình đang bị ghi qua đường này. Trả `{}` ở đây làm
    `recorder_service.js` đặt `hostPartnerId = null` và băng biến mất, TRONG
    KHI bản ghi vẫn ở state `recording` và `/aidt_meeting/chunk` vẫn nhận
    audio (`_store`/`_is_participant` không hỏi tới `calendar.event`). Ghi âm
    tiếp mà không còn thông báo, trong một hệ có độ mật tới `tuyệt_mật`, là
    hỏng nghĩa vụ thông báo.
    """

    def _dang_ghi(self):
        channel = self._meeting_channel(
            [self.organizer.partner_id, self.member.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        return channel, rec

    def _kiem_van_con_bang(self, channel, rec):
        info = self.Recording.with_user(
            self.member).action_active_recording(channel.id)
        self.assertEqual(info['recording_id'], rec.id)
        self.assertEqual(info['state'], 'recording')
        self.assertEqual(info['host_partner_id'], self.organizer.partner_id.id)

    def test_go_phong_hop_giua_chung_van_con_bang_thong_bao(self):
        channel, rec = self._dang_ghi()
        rec.event_id.sudo().videocall_channel_id = False
        self.assertFalse(self.Recording._event_for_channel(channel))
        self._kiem_van_con_bang(channel, rec)

    def test_xoa_cuoc_hop_giua_chung_van_con_bang_thong_bao(self):
        """Nặng hơn ca trên: `event_id` là `ondelete='set null'` nên bản ghi
        mất luôn liên kết tới cuộc họp — băng thông báo vẫn phải đứng, vì
        `host_partner_id` là bản chụp trên chính bản ghi."""
        channel, rec = self._dang_ghi()
        rec.event_id.sudo().unlink()
        self.assertFalse(rec.event_id)
        self.assertFalse(self.Recording._event_for_channel(channel))
        self._kiem_van_con_bang(channel, rec)


class TestReadAccess(RecordingCase):
    """Ai ĐỌC được bản ghi và đoạn bóc băng.

    `security/aidt_meeting_rules.xml` tự khẳng định điều này bằng chính nó và
    không có gì khác kiểm lại: bộ test cũ chỉ phủ ai được bật/dừng/từ chối.
    Nếu ai đó "đơn giản hoá" domain về chỉ còn `event_id` — đúng sai lầm mà
    comment trong file XML cảnh báo — thì mọi THÀNH VIÊN KÊNH không nằm trong
    danh sách mời của cuộc họp sẽ bị khoá ngoài bản ghi của chính cuộc gọi
    họ có mặt, mà mọi test khác vẫn xanh. Lý do cũ ("bản ghi của cuộc gọi tự
    phát có `event_id` rỗng") đã hết hiệu lực từ 19.0.1.4.0: không tạo được
    bản ghi `event_id` rỗng qua API công khai nữa. Xem README §5.4.
    """

    def test_nguoi_ngoai_khong_doc_duoc_ban_ghi_nao(self):
        # Người BẬT đổi sang organizer; outsider (người bị kiểm) giữ nguyên.
        channel = self._meeting_channel([self.organizer.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        self.assertFalse(
            self.Recording.with_user(self.outsider).search(
                [('id', '=', rec.id)]))

    def test_thanh_vien_kenh_ngoai_danh_sach_moi_hop_van_doc_duoc(self):
        """Thay cho `test_thanh_vien_kenh_doc_duoc_ban_ghi_khong_co_cuoc_hop`
        cũ (đã XOÁ). Test cũ dựng một bản ghi `event_id = False` (cuộc gọi
        tự phát) để chứng minh nhánh `channel_id` của
        `rule_recording_participant` hoạt động ĐỘC LẬP với nhánh `event_id`
        — tức người trong cuộc gọi đọc được bản ghi của chính mình dù không
        có lịch nào đứng sau. Từ 19.0.1.4.0, `_start_for_channel` luôn đòi
        có `calendar.event` nên không còn cách nào tạo bản ghi
        `event_id = False` qua API công khai nữa — tiền đề của test cũ
        không dựng được nữa, không phải chỉ cần đổi kênh.

        Test này giữ ĐÚNG mục đích gốc bằng một kịch bản khác vẫn tồn tại
        trong thế giới mới: `self.outsider` là THÀNH VIÊN KÊNH nhưng KHÔNG
        nằm trong `event.partner_ids` (`_event()` chỉ mời organizer +
        member) — họ vẫn phải đọc được bản ghi, chứng minh nhánh `channel_id`
        vẫn đứng vững một mình. Thiếu test này, ai đó "dọn dẹp" rule về chỉ
        còn nhánh `event_id.partner_ids` sẽ khoá luôn những người có mặt
        trong kênh nhưng không được mời riêng vào lịch họp — trong một hệ có
        độ mật tới `tuyệt_mật` — mà không có test nào báo động.

        Lưu ý: ở ĐÂY `self.outsider` đóng vai "người ngoài DANH SÁCH MỜI LỊCH
        nhưng trong KÊNH", khác với các test khác trong file này coi
        `outsider` là người ngoài cả kênh lẫn cuộc gọi.
        """
        channel = self._meeting_channel([self.organizer.partner_id])
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        self.assertNotIn(self.outsider.partner_id, rec.event_id.partner_ids)
        channel.add_members(partner_ids=[self.outsider.partner_id.id])
        self.assertTrue(
            self.Recording.with_user(self.outsider).search(
                [('id', '=', rec.id)]))

    def test_nguoi_du_hop_doc_duoc_qua_event(self):
        """Nhánh thứ hai của rule: người được mời trong `event_id.partner_ids`
        đọc được kể cả khi không (hoặc không còn) là thành viên kênh."""
        channel = self._channel([self.organizer.partner_id], in_call=False)
        event = self._event(channel)
        self._join_call(channel, self.organizer.partner_id)
        rec = self.Recording.with_user(
            self.organizer)._start_for_channel(channel)
        self.assertEqual(rec.event_id, event)
        self.assertIn(self.member.partner_id, event.partner_ids)
        self.assertTrue(
            self.Recording.with_user(self.member).search([('id', '=', rec.id)]))
