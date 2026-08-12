from odoo import fields, models


class AidtMeetingPause(models.Model):
    _name = 'aidt.meeting.pause'
    _description = 'Khoảng tạm dừng ghi âm'
    _order = 'paused_at_ms'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    # Cùng trục thời gian với `offset_ms` của mẩu audio: mili-giây kể từ lúc
    # bắt đầu ghi. Nhờ vậy mốc trong biên bản và mốc ở đây đọc được cạnh nhau.
    paused_at_ms = fields.Integer(string='Dừng lúc (ms)', required=True)
    # Rỗng nghĩa là chưa ghi tiếp — hoặc cuộc họp kết thúc luôn trong lúc
    # đang dừng. Không được điền một giá trị đoán: ta biết lúc dừng, không
    # biết cuộc họp còn kéo dài bao lâu sau đó.
    resumed_at_ms = fields.Integer(string='Ghi tiếp lúc (ms)')
    paused_by_id = fields.Many2one(
        'res.users', string='Người bấm dừng', readonly=True)
