import base64
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import config

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

    # ------------------------------------------------------------------ #
    # Hàng đợi bóc băng
    # ------------------------------------------------------------------ #
    @api.model
    def _claim(self, limit=1):
        """Nhận việc bằng SKIP LOCKED — an toàn khi chạy nhiều worker.

        `write()` của ORM chỉ đánh dấu field bẩn trong cache chứ chưa ghi
        xuống bảng, mà câu SELECT dưới đây đọc thẳng Postgres — phải flush
        trước, nếu không nó thấy dữ liệu cũ.
        """
        self.flush_model()
        self.env.cr.execute("""
            SELECT id FROM aidt_meeting_chunk
             WHERE state = 'pending'
               AND (next_retry_at IS NULL
                    OR next_retry_at <= now() AT TIME ZONE 'UTC')
             ORDER BY id
             LIMIT %s
               FOR UPDATE SKIP LOCKED
        """, (limit,))
        return self.browse([r[0] for r in self.env.cr.fetchall()])

    def _process_one(self):
        """Bóc băng đúng một mẩu đã được `_claim()` khoá."""
        self.ensure_one()
        try:
            # SAVEPOINT là thứ khiến khối `except` dưới đây chạy được: nếu
            # lỗi đến từ tầng CSDL thì cursor rơi vào InFailedSqlTransaction
            # và chính đường ghi trạng thái lỗi cũng sẽ ném tiếp, giết cả
            # lượt cron và kẹt hàng đợi vĩnh viễn ở đúng mẩu này.
            with self.env.cr.savepoint():
                raw = base64.b64decode(self.attachment_id.sudo().datas or b'')
                parsed = self.env['aidt.meeting.asr.client']._transcribe(
                    raw, f'chunk-{self.id}.mp3')
                self._write_segments(parsed)
                self.sudo().write({'state': 'done', 'error': False})
        except Exception as exc:                     # noqa: BLE001
            _logger.exception('Bóc băng thất bại cho mẩu %s', self.id)
            self.env.invalidate_all()
            self._mark_retry(str(exc))

    def _write_segments(self, parsed):
        """Quy đổi mốc tương đối trong chunk sang tuyệt đối trong cuộc họp."""
        self.ensure_one()
        Segment = self.env['aidt.meeting.segment'].sudo()
        Segment.search([('chunk_id', '=', self.id)]).unlink()
        rows = []
        for item in parsed:
            end = item['end_ms']
            if end is None:
                end = self.duration_ms
            rows.append({
                'recording_id': self.recording_id.id,
                'chunk_id': self.id,
                'partner_id': self.partner_id.id,
                'start_ms': self.offset_ms + item['start_ms'],
                'end_ms': self.offset_ms + end,
                'text': item['text'],
            })
        if rows:
            Segment.create(rows)

    @api.model
    def _cron_process(self, limit=20, budget_seconds=300):
        """Chạy mỗi phút. Nhận và xử lý TỪNG mẩu một, commit ngay sau mẩu đó.

        Không khoá cả lô rồi commit giữa chừng: khoá FOR UPDATE SKIP LOCKED
        chỉ sống trong giao dịch hiện tại, nên commit sau mẩu đầu sẽ NHẢ khoá
        những mẩu còn lại trong lô dù chúng vẫn 'pending' — một tiến trình
        cron chồng lên có thể nhận trúng và xử lý song song.
        """
        started = time.monotonic()
        processed = 0
        while processed < limit:
            if time.monotonic() - started > budget_seconds:
                break
            chunk = self._claim(limit=1)
            if not chunk:
                break
            try:
                chunk._process_one()
            except Exception:                        # noqa: BLE001
                # Lớp chắn thứ hai, cố tình thừa: nếu chính đường ghi lỗi
                # cũng hỏng thì vẫn không được để một mẩu kéo đổ cả lô.
                _logger.exception(
                    'Mẩu %s làm hỏng lượt xử lý; đánh dấu failed.', chunk.id)
                if not config['test_enable']:
                    self.env.cr.rollback()
                self.env.invalidate_all()
                chunk._mark_failed('Làm hỏng lượt xử lý, xem log máy chủ.')
            if not config['test_enable']:
                self.env.cr.commit()
            processed += 1
        return True
