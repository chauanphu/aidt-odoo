import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

MAX_ATTEMPT = 3
# Service vừa chết thì thử lại ngay không ích gì. Cùng triết lý với
# aidt_search/models/index_job.py.
RETRY_BACKOFF_MINUTES = (1, 4, 16)


class AidtMeetingChunk(models.Model):
    _name = 'aidt.meeting.chunk'
    _description = 'Mẩu audio cuộc họp'
    _order = 'recording_id, offset_ms, id'

    recording_id = fields.Many2one(
        'aidt.meeting.recording', string='Bản ghi', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Người nói', required=True, index=True)
    seq = fields.Integer(string='Thứ tự', required=True)
    # Tính bằng performance.now() của CHÍNH máy đó so với lúc nó bắt đầu ghi,
    # không bao giờ bằng đồng hồ tường — nhờ vậy lệch đồng hồ giữa các máy
    # không thể làm rối thứ tự khi trộn.
    offset_ms = fields.Integer(string='Vị trí (ms)', required=True)
    duration_ms = fields.Integer(string='Độ dài (ms)', required=True)

    attachment_id = fields.Many2one(
        'ir.attachment', string='Tệp audio', ondelete='set null')

    state = fields.Selection(
        [('pending', 'Chờ xử lý'), ('transcribing', 'Đang bóc băng'),
         ('done', 'Xong'), ('failed', 'Lỗi')],
        string='Trạng thái', default='pending', required=True, index=True)
    attempt = fields.Integer(string='Số lần thử', default=0)
    next_retry_at = fields.Datetime(string='Thử lại lúc')
    error = fields.Text(string='Lỗi')

    _seq_uniq = models.Constraint(
        'UNIQUE(recording_id, partner_id, seq)',
        'Mỗi người chỉ có một mẩu audio cho mỗi thứ tự trong một bản ghi.',
    )

    @api.model
    def _store(self, recording, partner, seq, offset_ms, duration_ms, raw):
        """Lưu một mẩu audio. `partner` PHẢI là partner của người đang gọi.

        Kiểm tra lại ở đây (chứ không chỉ ở controller) để mọi đường vào đều
        đi qua cùng một cửa: gán audio cho người khác nghĩa là giả mạo được
        một dòng trong biên bản.
        """
        caller = self.env.user.partner_id
        if partner != caller:
            raise AccessError(_('Không thể gán audio cho người khác.'))
        if not recording.sudo()._is_participant(caller):
            raise AccessError(_('Bạn không thuộc cuộc gọi này.'))
        if recording.sudo().state != 'recording':
            raise AccessError(_('Bản ghi không còn nhận audio.'))

        # Upload lặp lại sau lỗi mạng là đường đi BÌNH THƯỜNG: client không
        # biết request trước có tới nơi hay không nên gửi lại đúng seq đó,
        # và UNIQUE(recording_id, partner_id, seq) sẽ chặn ở create() thứ
        # hai. Không có savepoint thì UniqueViolation đó đầu độc cursor
        # thành InFailedSqlTransaction cho hết phần đời còn lại của request
        # HTTP — khác với TransactionCase trong test, ở đây không có gì tự
        # rollback giúp. Cùng cách làm với
        # aidt_search/models/index_job.py::_create_job().
        with self.env.cr.savepoint():
            attachment = self.env['ir.attachment'].sudo().create({
                'name': f'meeting-{recording.id}-{partner.id}-{seq}.mp3',
                'datas': base64.b64encode(raw),
                'mimetype': 'audio/mpeg',
                'res_model': 'aidt.meeting.recording',
                'res_id': recording.id,
            })
            return self.sudo().create({
                'recording_id': recording.id,
                'partner_id': partner.id,
                'seq': seq,
                'offset_ms': offset_ms,
                'duration_ms': duration_ms,
                'attachment_id': attachment.id,
            })

    def _mark_failed(self, message):
        """Hết lượt thử: đóng đinh 'failed' để hàng đợi không kẹt mãi ở đây."""
        self.ensure_one()
        self.sudo().write({'state': 'failed', 'error': message})

    def _mark_retry(self, message):
        self.ensure_one()
        attempt = self.attempt + 1
        if attempt >= MAX_ATTEMPT:
            return self._mark_failed(message)
        minutes = RETRY_BACKOFF_MINUTES[min(attempt - 1,
                                            len(RETRY_BACKOFF_MINUTES) - 1)]
        self.sudo().write({
            'state': 'pending', 'attempt': attempt, 'error': message,
            'next_retry_at': fields.Datetime.add(
                fields.Datetime.now(), minutes=minutes),
        })
