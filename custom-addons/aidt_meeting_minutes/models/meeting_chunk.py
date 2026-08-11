import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


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
    # Lần ghi. Tăng 1 mỗi lần chủ phòng bấm "Ghi tiếp". Không phải để cho gọn
    # dữ liệu: khi tạm dừng, client dừng `MediaRecorder` và lúc ghi tiếp tạo
    # một cái MỚI — luồng mới mang EBML header riêng. Worker nối các mẩu ở
    # mức byte, nên nối xuyên qua ranh giới tạm dừng cho ra một tệp có header
    # nằm giữa: ffmpeg giải mã phần đầu rồi dừng, IM LẶNG mất toàn bộ phần
    # sau lần ghi tiếp. `take` là thứ cho worker biết chỗ nào được nối.
    take = fields.Integer(string='Lần ghi', default=0, required=True)
    # Tính bằng performance.now() của CHÍNH máy đó so với lúc nó bắt đầu ghi,
    # không bao giờ bằng đồng hồ tường — nhờ vậy lệch đồng hồ giữa các máy
    # không thể làm rối thứ tự khi trộn.
    offset_ms = fields.Integer(string='Vị trí (ms)', required=True)
    duration_ms = fields.Integer(string='Độ dài (ms)', required=True)

    attachment_id = fields.Many2one(
        'ir.attachment', string='Tệp audio', ondelete='set null')

    _seq_uniq = models.Constraint(
        'UNIQUE(recording_id, partner_id, take, seq)',
        'Mỗi người chỉ có một mẩu audio cho mỗi thứ tự trong mỗi lần ghi.',
    )

    @api.model
    def _store(self, recording, partner, seq, offset_ms, duration_ms, raw,
               take=0):
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
        # 'processing' VẪN nhận audio. Lệnh dừng được phát đi SAU khi bản ghi
        # đã chuyển sang 'processing', nên mẩu cuối của mỗi máy — tới 15 giây
        # lời kết — bao giờ cũng tới nơi khi trạng thái đã đổi. Chốt ở
        # 'recording' nghĩa là mọi cuộc họp đều mất đoạn kết của mọi người.
        # Việc hoàn tất vốn đã chờ thêm một nhịp cron chính là để đợi những
        # mẩu đến muộn này (xem meeting_recording._cron_sweep).
        if recording.sudo().state not in ('recording', 'paused', 'processing'):
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
                'name': f'meeting-{recording.id}-{partner.id}-t{take}-{seq}.webm',
                'datas': base64.b64encode(raw),
                'mimetype': 'audio/webm',
                'res_model': 'aidt.meeting.recording',
                'res_id': recording.id,
            })
            chunk = self.sudo().create({
                'recording_id': recording.id,
                'partner_id': partner.id,
                'take': take,
                'seq': seq,
                'offset_ms': offset_ms,
                'duration_ms': duration_ms,
                'attachment_id': attachment.id,
            })
        self._warn_if_finalised_in_flight(recording, chunk)
        return chunk

    @api.model
    def _warn_if_finalised_in_flight(self, recording, chunk):
        """Cuộc đua ĐÃ BIẾT, CHƯA sửa — nhưng không được vô hình nữa.

        Kiểm tra ở đầu `_store` đọc `state='processing'` và cho qua; ngay sau
        đó `_cron_sweep._finalize` có thể commit `done`. Mẩu này vẫn được tạo,
        vẫn được bóc băng, nhưng `_cron_sweep` chỉ duyệt `processing` nên bản
        bóc băng không bao giờ được dựng lại — âm thầm thiếu đúng đoạn kết.
        Đọc lại trạng thái sau khi ghi (Postgres READ COMMITTED ⇒ thấy được
        commit vừa rồi của giao dịch khác) và ghi log CẢNH BÁO nếu trúng cửa
        sổ đó. `_cron_sweep._sweep_late_chunks` là bên dọn hậu quả.
        """
        recording.sudo().invalidate_recordset(['state'])
        # `.exists()` chứ không đọc thẳng `.state`: bản ghi có thể đã bị xoá
        # bởi một giao dịch khác trong đúng khoảng này, và một `MissingError`
        # từ MỘT CÂU LOG sẽ biến một upload thành công thành HTTP 500
        # (`controllers/main.py` không bắt MissingError).
        if recording.sudo().exists().state == 'done':
            _logger.warning(
                'Mẩu %s (bản ghi %s, seq %s) được nhận trong lúc bản ghi đang '
                'được hoàn tất — bản bóc băng sẽ phải dựng lại ở lượt quét sau.',
                chunk.id, recording.id, chunk.seq)
