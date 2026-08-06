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
    start_time_str = fields.Char(string='Thời gian', compute='_compute_start_time_str')
    text = fields.Text(string='Nội dung', required=True)

    def _compute_start_time_str(self):
        for rec in self:
            total = max(0, rec.start_ms) // 1000
            rec.start_time_str = f'{total // 60:02d}:{total % 60:02d}'

    # Lưới an toàn tầng CSDL cho mốc thời gian đến từ dịch vụ ASR bên ngoài.
    # `meeting_chunk._write_segments()` đã kẹp giá trị trước khi ghi, nhưng
    # ràng buộc ở đây mới là thứ bảo đảm cho MỌI đường ghi — kể cả import,
    # sửa tay, hay một client ASR khác được cắm vào sau này. Một đoạn kết
    # thúc trước khi nó bắt đầu là vô nghĩa theo đúng ngữ nghĩa của hai
    # trường này, không phải chuyện "hiếm khi xảy ra".
    _end_after_start = models.Constraint(
        'CHECK (end_ms >= start_ms)',
        'Đoạn bóc băng không thể kết thúc trước khi bắt đầu.',
    )
