from datetime import timedelta
from unittest.mock import patch

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

    def test_dinh_ky_tich_buoi_dau_gan_chung_kenh_cho_ca_chuoi(self):
        """Cả đợt này tồn tại vì họp định kỳ dùng CHUNG một kênh (xem Task
        1). `_create_videocall_channel` của upstream
        (`addons/calendar/models/calendar_event.py`) đã lo việc gán chung
        khi `recurrency=True`; test này chỉ khẳng định ô "tạo phòng" không
        vô tình phá vỡ cơ chế đó — tích ở BUỔI ĐẦU phải lan phòng ra toàn
        chuỗi, và tích tiếp ở một buổi ĐÃ CÓ phòng (do lan từ buổi đầu)
        không được đẻ ra phòng thứ hai."""
        base = self._event(recurrency=True)
        base._apply_recurrence_values({
            'rrule_type': 'daily',
            'count': 3,
        })
        events = base.recurrence_id.calendar_event_ids.sorted('start')
        self.assertEqual(len(events), 3,
                          'chuỗi phải có đúng 3 buổi trước khi tích gì cả')
        first, second, third = events

        first.aidt_has_room = True
        channel = first.videocall_channel_id
        self.assertTrue(channel)

        second.invalidate_recordset(['videocall_channel_id', 'aidt_has_room'])
        third.invalidate_recordset(['videocall_channel_id', 'aidt_has_room'])
        self.assertEqual(
            second.videocall_channel_id, channel,
            'buổi thứ hai phải tự có cùng kênh do upstream lan ra cả chuỗi')
        self.assertEqual(
            third.videocall_channel_id, channel,
            'buổi thứ ba phải tự có cùng kênh do upstream lan ra cả chuỗi')
        self.assertTrue(second.aidt_has_room)
        self.assertTrue(third.aidt_has_room)

        # Tích tiếp trên buổi đã có phòng (do lan từ buổi đầu) — không
        # được tạo phòng thứ hai cho cùng chuỗi.
        second.aidt_has_room = True
        self.assertEqual(second.videocall_channel_id, channel)

    def test_ghi_hang_loat_khong_vo_singleton(self):
        """`write` trên một recordset nhiều bản ghi phải lặp qua từng cuộc
        họp rồi mới gọi `_create_videocall_channel()` — hàm đó đòi
        singleton. Ai sau này đổi vòng lặp thành gọi thẳng trên `self` sẽ
        vỡ ở đây với `ValueError: Expected singleton`, không phải lặng lẽ
        khi chạy thật. Hai cuộc họp KHÔNG cùng chuỗi định kỳ nên mỗi cuộc
        phải có phòng RIÊNG, không chia sẻ."""
        first = self._event(name='Họp 1')
        second = self._event(name='Họp 2')
        (first + second).write({'aidt_has_room': True})
        self.assertTrue(first.videocall_channel_id)
        self.assertTrue(second.videocall_channel_id)
        self.assertNotEqual(
            first.videocall_channel_id, second.videocall_channel_id,
            'hai cuộc họp độc lập không được dùng chung một phòng')


@tagged('post_install', '-at_install')
class TestRoomPush(TransactionCase):
    """Gói tin CUỐI CÙNG đẩy sang client phải nói kênh này LÀ phòng họp.

    Đây là lỗi "phòng vừa tạo rơi vào sai mục": upstream broadcast đầu kênh
    ngay trong `discuss.channel._create_group`, tức là TRƯỚC khi
    `calendar.event.videocall_channel_id` được gán, nên gói tin đó mang
    `aidt_is_meeting_room=False`. Client tin gói tin cuối cùng nó nhận được,
    nên phòng hiện ở "Tin nhắn trực tiếp" cho tới khi nạp lại trang.

    Khẳng định "phòng có tồn tại" hay "trường tính đúng ở phía server" KHÔNG
    bắt được lỗi này — cả hai đều xanh trong khi thanh bên vẫn sai. Thứ duy
    nhất bắt được là ĐỌC ĐÚNG NHỮNG GÓI TIN ĐÃ ĐẨY.
    """

    def _pushes(self, func):
        """Chạy `func` và trả về danh sách payload của mọi `Store.bus_send`.

        Đọc `get_result()` — đúng cái dict mà `bus_send` sắp gửi đi — chứ
        không đọc trạng thái server sau cùng: server sau cùng LUÔN đúng, cái
        sai nằm ở thứ đã bay sang client.
        """
        pushes = []
        original = Store.bus_send

        def spy(store, *args, **kwargs):
            pushes.append(store.get_result())
            return original(store, *args, **kwargs)

        with patch.object(Store, 'bus_send', spy):
            result = func()
        return result, pushes

    def _room_flags(self, pushes, channel):
        """Giá trị `aidt_is_meeting_room` của kênh này, theo thứ tự đã đẩy."""
        return [
            record['aidt_is_meeting_room']
            for push in pushes
            for record in push.get('discuss.channel', [])
            if record.get('id') == channel.id
            and 'aidt_is_meeting_room' in record
        ]

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

    def test_goi_tin_cuoi_cung_noi_day_la_phong_hop(self):
        event, pushes = self._pushes(lambda: self._event(aidt_has_room=True))
        channel = event.videocall_channel_id
        self.assertTrue(channel, 'không tạo được phòng thì không có gì để đo')

        flags = self._room_flags(pushes, channel)
        self.assertTrue(
            flags,
            'không lần đẩy nào mang `aidt_is_meeting_room` — thanh bên không '
            'có cách nào biết kênh này là phòng họp')
        self.assertTrue(
            flags[-1],
            'gói tin CUỐI CÙNG client nhận được nói đây không phải phòng '
            'họp, nên phòng rơi vào mục "Tin nhắn trực tiếp". Phải đẩy lại '
            'đầu kênh sau khi đã nối kênh với cuộc họp — xem '
            '`CalendarEvent._create_videocall_channel`.')

    def test_duong_tao_phong_tu_tuyen_join_videocall_cung_duoc_day_lai(self):
        """Tuyến `/calendar/join_videocall` (nút gọi video của Lịch) đi
        thẳng vào `_create_videocall_channel`, KHÔNG qua ô "tạo phòng". Nếu
        ai đó chuyển bản vá xuống `_inverse_aidt_has_room` thì test này đỏ —
        đúng lý do bản vá phải nằm ở điểm hội tụ."""
        event = self._event()
        self.assertFalse(event.videocall_channel_id)

        _, pushes = self._pushes(event._create_videocall_channel)
        channel = event.videocall_channel_id
        self.assertTrue(channel)

        flags = self._room_flags(pushes, channel)
        self.assertTrue(flags, 'không lần đẩy nào mang trường này')
        self.assertTrue(
            flags[-1],
            'đường tạo phòng ngoài ô "tạo phòng" cũng phải được đẩy lại')
