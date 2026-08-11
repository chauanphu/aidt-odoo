from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tools.discuss import Store
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestMeetingRoomFlag(TransactionCase):
    """Phòng họp = kênh có `calendar.event` đứng sau. Không có cờ riêng."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Kênh thường', 'channel_type': 'channel'})

    def _attach_event(self, channel):
        now = fields.Datetime.now()
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create({
            'name': 'Cuộc họp thử',
            'start': now,
            'stop': now + timedelta(hours=1),
            'videocall_channel_id': channel.id,
        })

    def test_kenh_khong_co_lich_thi_khong_phai_phong_hop(self):
        self.assertFalse(self.channel.aidt_is_meeting_room)

    def test_kenh_co_lich_thi_la_phong_hop(self):
        self._attach_event(self.channel)
        self.channel.invalidate_recordset(['aidt_is_meeting_room'])
        self.assertTrue(self.channel.aidt_is_meeting_room)

    def test_truong_nam_trong_goi_gui_client(self):
        """Thiếu bước này thì thanh bên không bao giờ biết kênh nào là
        phòng họp — mục "Họp" sẽ rỗng vĩnh viễn."""
        defaults = self.channel._to_store_defaults(Store.Target())
        self.assertIn('aidt_is_meeting_room', defaults)
        self.assertIn(
            'channel_type', defaults,
            'phải nối vào kết quả của super(), không thay thế nó')


@tagged('post_install', '-at_install')
class TestHasRoom(TransactionCase):
    """Ô "tạo phòng" là trường TÍNH có nghịch đảo, không phải cờ lưu riêng."""

    def _event(self, **vals):
        now = fields.Datetime.now()
        base = {
            'name': 'Họp thử',
            'start': now,
            'stop': now + timedelta(hours=1),
        }
        base.update(vals)
        return self.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_create_nolog=True,
            mail_notrack=True,
        ).create(base)

    def test_khong_tich_thi_khong_co_phong(self):
        event = self._event()
        self.assertFalse(event.aidt_has_room)
        self.assertFalse(event.videocall_channel_id)

    def test_tich_luc_tao_thi_co_phong_ngay(self):
        """Odoo chạy `inverse` cả trong create(), nên đúng một trường phục vụ
        cả 'tích lúc tạo lịch' lẫn 'tạo phòng sau ở trang quản lý'."""
        event = self._event(aidt_has_room=True)
        self.assertTrue(event.videocall_channel_id)
        self.assertTrue(event.aidt_has_room)
        self.assertTrue(event.videocall_channel_id.aidt_is_meeting_room)

    def test_tich_sau_thi_tao_phong(self):
        event = self._event()
        event.aidt_has_room = True
        self.assertTrue(event.videocall_channel_id)

    def test_tich_hai_lan_khong_tao_phong_thu_hai(self):
        event = self._event(aidt_has_room=True)
        first = event.videocall_channel_id
        event.aidt_has_room = True
        self.assertEqual(event.videocall_channel_id, first)

    def test_bo_tich_khong_xoa_phong(self):
        """Một chiều là CỐ Ý: phòng giữ lịch sử ghi âm và biên bản. Gỡ nó đi
        là bỏ rơi các `aidt.meeting.recording` trỏ vào kênh không còn ai
        dùng. Muốn bỏ phòng thì xoá cuộc họp."""
        event = self._event(aidt_has_room=True)
        channel = event.videocall_channel_id
        event.aidt_has_room = False
        self.assertEqual(event.videocall_channel_id, channel)
        self.assertTrue(event.aidt_has_room,
                        'compute phải đọc lại từ kênh, nên vẫn là True')
