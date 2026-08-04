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

    def _channel(self, partners):
        channel = self.env['discuss.channel'].create({
            'name': 'Cuộc gọi thử', 'channel_type': 'channel',
        })
        channel.add_members(partner_ids=[p.id for p in partners])
        return channel

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
    def test_nguoi_tham_gia_bat_ky_deu_dung_duoc(self):
        """Bật thì hạn chế, dừng thì không — thiết kế dựa vào việc con người
        tự tắt ghi âm khi nội dung là Mật, nên người nhận ra điều đó phải tắt
        được ngay chứ không phải đi nhờ người khác."""
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.member).action_stop()
        self.assertEqual(rec.state, 'processing')

    def test_nguoi_ngoai_khong_dung_duoc(self):
        channel = self._channel([self.member.partner_id])
        rec = self.Recording.with_user(self.member)._start_for_channel(channel)
        with self.assertRaises(AccessError):
            rec.with_user(self.outsider).action_stop()

    def test_tu_choi_ghi_lai_partner(self):
        channel = self._channel([self.organizer.partner_id,
                                 self.member.partner_id])
        self._event(channel)
        rec = self.Recording.with_user(self.organizer)._start_for_channel(channel)
        rec.with_user(self.member)._decline(self.member.partner_id)
        self.assertIn(self.member.partner_id, rec.declined_partner_ids)
