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
