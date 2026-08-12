import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .meeting_recording import ACTIVE_STATES

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
        #
        # KHÔNG có lưới an toàn nào quét lại mẩu đến muộn: `_end_recording`
        # chỉ đợi 10 giây (một ước lượng, không phải số đo) rồi gọi thẳng
        # `_trigger_ai_service()` trong một thread nền — không có cron nào
        # tên `_cron_sweep`/`_sweep_late_chunks` trong module này
        # (`data/ir_cron.xml` rỗng). Mẩu tới SAU khi `_trigger_ai_service()`
        # đã export xong bị `_store` NHẬN (state vẫn hợp lệ) nhưng không bao
        # giờ được xuất ra `/var/lib/odoo/meetings/<id>/`, không bao giờ được
        # bóc băng, và không có gì báo lại — mất trong im lặng.
        if recording.sudo().state not in ACTIVE_STATES:
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
                # `raw` chứ không phải `datas`: `datas` là base64 của chính
                # `raw`, nên đi qua nó là encode ở đây rồi decode lại ở
                # `_export_chunks` — hai lần biến đổi và +33% bộ nhớ cho mỗi
                # mẩu, đổi lấy đúng cùng một chuỗi byte.
                'raw': raw,
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

        Kiểm tra ở đầu `_store` đọc `state='processing'` và cho qua; nhưng
        `_trigger_ai_service()` đã export chunk ra
        `/var/lib/odoo/meetings/<id>/` và gọi worker RỒI (đợi 10 giây sau khi
        chuyển sang 'processing', xem `_end_recording`) — nếu mẩu này tới sau
        thời điểm export, nó KHÔNG BAO GIỜ được đưa vào bản bóc băng. Bản ghi
        chỉ chuyển tiếp sang 'done' khi webhook `/aidt_meeting/api/webhook/
        summary/<id>` trả về, nên cửa sổ này có thể dài bằng cả lượt bóc băng
        + tóm tắt (nhiều chục giây tới vài phút), không phải một khoảng ngắn.
        KHÔNG có gì quét lại và dựng lại bản bóc băng cho trường hợp này —
        không có cron nào trong module (`data/ir_cron.xml` rỗng). Đọc lại
        trạng thái sau khi ghi (Postgres READ COMMITTED ⇒ thấy được commit
        vừa rồi của giao dịch khác) và ghi log CẢNH BÁO nếu trúng cửa sổ đó,
        để ít nhất việc mất mẩu không hoàn toàn im lặng.
        """
        recording.sudo().invalidate_recordset(['state'])
        # `.exists()` chứ không đọc thẳng `.state`: bản ghi có thể đã bị xoá
        # bởi một giao dịch khác trong đúng khoảng này, và một `MissingError`
        # từ MỘT CÂU LOG sẽ biến một upload thành công thành HTTP 500
        # (`controllers/main.py` không bắt MissingError).
        if recording.sudo().exists().state == 'done':
            _logger.warning(
                'Mẩu %s (bản ghi %s, seq %s) được nhận sau khi bản ghi đã '
                'xuất audio cho worker (hoặc đã hoàn tất) — KHÔNG có cơ chế '
                'nào dựng lại bản bóc băng để đưa mẩu này vào, mẩu bị bỏ.',
                chunk.id, recording.id, chunk.seq)
