from odoo import fields, models


class AidtMeetingSegment(models.Model):
    _name = 'aidt.meeting.segment'
    _description = 'Đoạn lời nói đã bóc băng'
    _order = 'recording_id, start_ms, id'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    chunk_id = fields.Many2one(
        'aidt.meeting.chunk', string='Mẩu audio', ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Người nói', required=True, index=True)
    # TUYỆT ĐỐI trong cuộc họp, không phải tương đối trong chunk.
    start_ms = fields.Integer(string='Bắt đầu (ms)', required=True, index=True)
    end_ms = fields.Integer(string='Kết thúc (ms)', required=True)
    text = fields.Text(string='Nội dung', required=True)
