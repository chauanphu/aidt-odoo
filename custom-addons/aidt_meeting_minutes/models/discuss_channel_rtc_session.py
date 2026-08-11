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
                channel.sudo().aidt_call_host_partner_id = \
                    self._resolve_host_partner(channel, session.partner_id)
        return sessions

    @api.model
    def _resolve_host_partner(self, channel, joiner_partner):
        """Chủ phòng của một cuộc gọi VỪA BẮT ĐẦU trên `channel`.

        Kênh có gắn `calendar.event`: chủ phòng CHỐT NGAY LÚC NÀY vào người
        chủ trì cuộc họp trong lịch (`event.user_id`), BẤT KỂ ai là người tạo
        ra phiên RTC đầu tiên — một chuyên viên vào phòng sớm 2 phút không
        được nghiễm nhiên thành chủ phòng của cuộc họp mà lãnh đạo chủ trì.
        Đây là quyết định có ý thức: nếu người chủ trì không vào cuộc gọi thì
        không ai bật ghi âm được (fail-closed), đúng hành vi đã có TRƯỚC
        nhánh này (trước đây `_start_for_channel` chỉ đòi `event.user_id`).

        Kênh KHÔNG gắn lịch (cuộc gọi tự phát): giữ nguyên quy tắc "người vào
        đầu tiên", vì không có ai khác để tham chiếu tới.

        Dùng CHUNG `_event_for_channel` với `_start_for_channel` chứ không tự
        viết lại domain: hai bên phải nhìn thấy ĐÚNG một sự kiện thì "ai là
        chủ phòng" và "ai được bật ghi âm" mới không thể lệch nhau. Khi kênh
        có nhiều `calendar.event`, hai lượt tìm độc lập có thể trả về hai bản
        ghi khác nhau và khoá chết tính năng mà không ai hiểu vì sao.
        """
        event = self.env['aidt.meeting.recording']._event_for_channel(channel)
        if event and event.user_id:
            return event.user_id.partner_id
        return joiner_partner

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
