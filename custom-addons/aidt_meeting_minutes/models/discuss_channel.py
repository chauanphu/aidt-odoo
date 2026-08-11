from odoo import api, fields, models


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # Chủ phòng của CUỘC GỌI đang diễn ra trên kênh này, chốt lúc cuộc gọi
    # bắt đầu (xem discuss_channel_rtc_session.py). Odoo không có khái niệm
    # này sẵn: kênh có `create_uid` nhưng người tạo kênh "general" từ một năm
    # trước không phải người chủ trì cuộc họp hôm nay và có thể không có mặt.
    #
    # Rỗng khi không có cuộc gọi nào đang chạy.
    aidt_call_host_partner_id = fields.Many2one(
        'res.partner', string='Chủ phòng cuộc gọi', readonly=True, copy=False)

    # Phòng họp KHÔNG có cờ riêng: nó là kênh có `calendar.event` đứng sau.
    # `calendar_event_ids` do `addons/calendar/models/discuss_channel.py:9`
    # khai sẵn (quan hệ ngược của `calendar.event.videocall_channel_id`).
    #
    # Không lưu (`store=False`): lưu là đẻ ra nguồn sự thật thứ hai, và nó
    # sẽ trôi — xoá cuộc họp trong Lịch thì cờ vẫn bật, kênh thành phòng họp
    # không có cuộc họp nào.
    aidt_is_meeting_room = fields.Boolean(
        string='Là phòng họp',
        compute='_compute_aidt_is_meeting_room',
    )

    @api.depends('calendar_event_ids')
    def _compute_aidt_is_meeting_room(self):
        for channel in self:
            channel.aidt_is_meeting_room = bool(channel.calendar_event_ids)

    def _to_store_defaults(self, target):
        """Đẩy `aidt_is_meeting_room` sang client.

        `_to_store` (`addons/mail/models/discuss/discuss_channel.py:1313`)
        chỉ gửi đúng những trường mà hàm này liệt kê. Thiếu tên trường ở đây
        thì `Thread` phía JS không bao giờ thấy nó, và mục "Họp" trong thanh
        bên rỗng vĩnh viễn mà không có lỗi nào.
        """
        return super()._to_store_defaults(target) + ['aidt_is_meeting_room']
