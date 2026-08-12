from odoo import api, fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Ô "tạo phòng" trên form. KHÔNG lưu: trạng thái thật nằm ở
    # `videocall_channel_id`, lưu thêm một boolean là đẻ ra nguồn sự thật
    # thứ hai sẽ trôi khỏi nó.
    #
    # Odoo tự nhiên khớp với cách dùng ta cần: `inverse` chạy cả trong
    # `create()`, nên đúng một trường phục vụ cả "tích lúc tạo lịch" lẫn
    # "tạo phòng sau ở trang quản lý cuộc họp". Không cần hai cơ chế.
    aidt_has_room = fields.Boolean(
        string='Phòng họp trực tuyến',
        compute='_compute_aidt_has_room',
        inverse='_inverse_aidt_has_room',
        help='Tạo một phòng trong Thảo luận cho cuộc họp này. '
             'Chỉ phòng họp mới bật được ghi âm và biên bản tự động.',
    )

    @api.depends('videocall_channel_id')
    def _compute_aidt_has_room(self):
        for event in self:
            event.aidt_has_room = bool(event.videocall_channel_id)

    def _inverse_aidt_has_room(self):
        """CHỈ TẠO, không bao giờ xoá.

        Bỏ tích không gỡ phòng, và đó là chủ ý: phòng giữ toàn bộ lịch sử
        ghi âm, mẩu audio và biên bản. Gỡ nó bằng một cái tích chuột là bỏ
        rơi cả đống `aidt.meeting.recording` trỏ vào một kênh không còn ai
        dùng, không có gì cảnh báo. Muốn bỏ phòng thì xoá cuộc họp — đường
        đó rõ ràng hơn và Odoo đã hỏi xác nhận sẵn.

        Trên form, ô này thành chỉ-đọc ngay khi phòng đã tồn tại, nên người
        dùng không rơi vào cảnh bỏ tích rồi thấy nó tự bật lại.
        """
        for event in self:
            if event.aidt_has_room and not event.videocall_channel_id:
                event._create_videocall_channel()
        # Giá trị đang nằm trong cache là thứ người dùng VỪA GÁN, không phải
        # sự thật. Bỏ tích ghi False vào cache, mà `_inverse` ở trên không
        # đụng tới `videocall_channel_id` — trường mà `_compute` phụ thuộc —
        # nên Odoo không có lý do gì để tự làm mới. Lần đọc sau vẫn thấy
        # False trong khi phòng còn nguyên, tức là trường nói dối về chính
        # thứ nó tồn tại để trả lời. Ép tính lại để nó luôn khớp trạng thái
        # thật của kênh.
        self.invalidate_recordset(['aidt_has_room'])

    def _create_videocall_channel(self):
        """Đẩy lại đầu kênh SAU KHI đã nối kênh với cuộc họp.

        Không có bước này thì phòng vừa tạo rơi vào SAI MỤC trên thanh bên
        đang mở: nó hiện ở "Tin nhắn trực tiếp" chứ không phải "Họp", và chỉ
        đúng lại sau khi nạp lại trang.

        Vì sao. Upstream tạo kênh bằng `discuss.channel._create_group`, mà
        hàm đó broadcast TOÀN BỘ đầu kênh ngay trong chính nó
        (`addons/mail/models/discuss/discuss_channel.py:1532`) — tức là
        TRƯỚC khi `calendar.event.videocall_channel_id` được gán ở dòng ngay
        sau lời gọi (`addons/calendar/models/calendar_event.py:1067`). Lúc
        broadcast, kênh chưa có `calendar_event_ids` nào, nên
        `_compute_aidt_is_meeting_room` trả về False và client nhận đúng cái
        False đó. Lần đẩy kế tiếp (`channel_change_description` ở dòng 1068)
        đi qua `discuss.channel.write`, mà `write` chỉ đồng bộ những trường
        có tên trong `_sync_field_names()` — `aidt_is_meeting_room` không
        nằm trong đó, và ta cũng không nên thêm vào: nó là trường TÍNH, thay
        đổi theo `calendar.event` chứ không theo một lần `write` lên kênh.

        Vì sao override Ở ĐÂY chứ không vá riêng `_inverse_aidt_has_room`.
        `_create_videocall_channel` là ĐIỂM HỘI TỤ duy nhất của mọi đường
        tạo phòng: `_create_videocall_channel_id` (hàm thật sự gọi
        `_create_group`) chỉ có đúng một nơi gọi là hàm này, và hàm này có
        đúng hai nơi gọi trong mã sản xuất — ô "tạo phòng" của ta
        (`_inverse_aidt_has_room` ở trên) và tuyến `/calendar/join_videocall`
        (`addons/calendar/controllers/main.py:112`), tuyến mà nút gọi video
        trên form Lịch dẫn tới. Vá ở `_inverse` chỉ sửa đường thứ nhất và bỏ
        nguyên lỗi ở đường thứ hai.

        Đẩy lại bằng `_broadcast` (bus của TỪNG NGƯỜI DÙNG) chứ không bằng
        `Store(bus_channel=channel)`: kênh vừa mới ra đời, client chưa kịp
        đăng ký nghe bus của chính kênh đó — nó chỉ đăng ký sau khi nhận
        được đầu kênh qua bus người dùng — nên một thông điệp gửi vào bus
        kênh ngay lúc này rất dễ rơi vào hư không. `_broadcast` cũng chính
        là cơ chế upstream dùng ở `_create_group`, nên gói tin thứ hai có
        cùng hình dạng gói tin thứ nhất, chỉ khác giá trị đã đúng.
        """
        before = self.videocall_channel_id
        super()._create_videocall_channel()
        channel = self.videocall_channel_id
        if channel and channel != before:
            channel._broadcast(channel.channel_member_ids.partner_id.ids)
