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
        # sudo() vì bất biến "phòng họp = kênh có calendar.event" phải được
        # trả lời ở MỘT mức quyền duy nhất. `_event_for_channel`
        # (meeting_recording.py) đã đọc có sudo, cố ý, vì người ta dự họp
        # được mà không có quyền đọc `calendar.event` qua
        # `aidt_calendar.calendar_event_rule_secrecy`. Đọc không sudo ở đây
        # thì cùng một kênh trả về HAI câu trả lời khác nhau: chuyên viên
        # clearance thấp được mời họp `mật` thấy phòng của chính mình rơi
        # xuống "Direct messages" và kết luận mình không được mời, trong khi
        # server vẫn coi đó là phòng họp.
        #
        # Không lộ thêm gì: giá trị này chỉ nói "kênh này có một cuộc họp
        # đứng sau" — không tên, không giờ, không người dự — và nó chỉ đi
        # kèm gói tin của một kênh mà người nhận vốn đã đọc được. Đổi lại,
        # sudo() cũng bịt luôn đường ném AccessError khi một máy khách không
        # có quyền model `calendar.event` (portal/khách của im_livechat) tải
        # được gói tin kênh.
        #
        # PHẢI là `search()` có sudo, KHÔNG phải `channel.sudo().calendar_
        # event_ids`: cache của trường x2many không mang theo người đọc. Nếu
        # bất cứ thứ gì đọc `calendar_event_ids` dưới quyền người dùng
        # TRƯỚC, giá trị đã bị rule lọc nằm sẵn trong cache và `sudo()` đọc
        # trúng đúng cái rỗng đó — `sudo()` không dọn cache. Đây là dạng
        # search y hệt `_event_for_channel` dùng, nên hai bên chắc chắn nhìn
        # thấy cùng một tập cuộc họp.
        stored = self.filtered(lambda channel: isinstance(channel.id, int))
        rooms = set()
        if stored:
            rooms = set(self.env['calendar.event'].sudo().search(
                [('videocall_channel_id', 'in', stored.ids)]
            ).videocall_channel_id.ids)
        for channel in self:
            channel.aidt_is_meeting_room = channel.id in rooms

    def _to_store_defaults(self, target):
        """Đẩy `aidt_is_meeting_room` sang client.

        `_to_store` (`addons/mail/models/discuss/discuss_channel.py:1313`)
        chỉ gửi đúng những trường mà hàm này liệt kê. Thiếu tên trường ở đây
        thì `Thread` phía JS không bao giờ thấy nó, và mục "Họp" trong thanh
        bên rỗng vĩnh viễn mà không có lỗi nào.
        """
        return super()._to_store_defaults(target) + ['aidt_is_meeting_room']
