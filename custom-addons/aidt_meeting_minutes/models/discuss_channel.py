from odoo import fields, models


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
