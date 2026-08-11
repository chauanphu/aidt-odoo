from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEventForChannel(TransactionCase):
    """Một kênh có thể đứng sau NHIỀU cuộc họp.

    `addons/calendar/models/calendar_event.py:1057` cố ý gán một kênh cho
    TOÀN BỘ các lần của một cuộc họp định kỳ. Giao ban hằng tuần chạy cả năm
    là một kênh, 52 `calendar.event`. Hỏi "cuộc họp nào đứng sau kênh này"
    mà không kèm mốc thời gian là câu hỏi không có câu trả lời đúng.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Giao ban tuần',
            'channel_type': 'group',
        })
        cls.now = fields.Datetime.now()
        cls.Recording = cls.env['aidt.meeting.recording']

    def _event(self, offset_hours, hours=1):
        """Một buổi họp gắn vào kênh chung, cách `now` đúng `offset_hours`.

        `no_mail_to_attendees` + `mail_notrack`: tạo `calendar.event` bình
        thường sẽ gửi thư mời và ghi tracking, chậm và ồn trong test.
        """
        start = self.now + timedelta(hours=offset_hours)
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True,
            mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': f'Buổi {offset_hours}h',
            'start': start,
            'stop': start + timedelta(hours=hours),
            'videocall_channel_id': self.channel.id,
        })

    def test_khong_co_buoi_nao_thi_tra_rong(self):
        self.assertFalse(self.Recording._event_for_channel(self.channel))

    def test_mot_buoi_thi_tra_dung_buoi_do(self):
        event = self._event(-100)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), event)

    def test_uu_tien_buoi_dang_dien_ra(self):
        """Đây là ca lỗi trung tâm: trước khi sửa, hàm trả về buổi tuần sau."""
        self._event(-24 * 7)
        ongoing = self._event(-0.5)
        self._event(24 * 7)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), ongoing)

    def test_khong_co_buoi_dang_chay_thi_lay_buoi_sap_toi_gan_nhat(self):
        self._event(-24 * 7)
        soon = self._event(2)
        self._event(24 * 7)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), soon)

    def test_het_roi_thi_lay_buoi_vua_qua_gan_nhat(self):
        """Cuộc họp định kỳ đã chạy hết: bản ghi phải gắn vào buổi CUỐI,
        không phải buổi đầu tiên của chuỗi."""
        self._event(-24 * 7)
        last = self._event(-3)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel), last)

    def test_lay_theo_moc_thoi_gian_truyen_vao(self):
        first = self._event(-24 * 7)
        self._event(24 * 7)
        at = first.start + timedelta(minutes=10)
        self.assertEqual(
            self.Recording._event_for_channel(self.channel, at=at), first)
