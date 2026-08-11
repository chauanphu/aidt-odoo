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
