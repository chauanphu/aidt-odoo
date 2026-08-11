from odoo import api, models


class DiscussChannelRtcSession(models.Model):
    _inherit = 'discuss.channel.rtc.session'

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        # `len(c.rtc_session_ids) == 1` là ĐÚNG điều kiện Odoo dùng để nhận
        # ra "cuộc gọi vừa bắt đầu" (discuss_channel_rtc_session.py:51). Dùng
        # lại nó thay vì tự nghĩ ra một cách khác.
        for session in sessions:
            channel = session.channel_id
            if len(channel.sudo().rtc_session_ids) == 1:
                channel.sudo().aidt_call_host_partner_id = session.partner_id
        return sessions

    def unlink(self):
        # Tính TRƯỚC khi xoá, cùng cách Odoo tính `call_ended_channels`
        # (dòng 66 của file gốc): sau `super()` thì không còn gì để đối chiếu.
        ended = self.channel_id.filtered(
            lambda c: not (c.sudo().rtc_session_ids - self))
        result = super().unlink()
        if ended:
            ended.sudo().aidt_call_host_partner_id = False
            # Không còn ai trong cuộc gọi thì không còn ai bấm được nút kết
            # thúc — kể cả chủ phòng, vì họ cũng đã rời. Bỏ qua bước này thì
            # bản ghi nằm mãi ở `recording` và chỉ mục duy nhất chặn luôn mọi
            # bản ghi mới trên kênh đó.
            recordings = self.env['aidt.meeting.recording'].sudo().search([
                ('channel_id', 'in', ended.ids),
                ('state', 'in', ('recording', 'paused')),
            ])
            for recording in recordings:
                recording._end_recording()
        return result
