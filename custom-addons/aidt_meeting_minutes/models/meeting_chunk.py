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
    # KHÁC `error`: mẩu vẫn xử lý THÀNH CÔNG, chỉ là phần nội dung nào đó đã
    # bị bỏ đi có chủ ý (không có tiếng nói, hoặc đầu ra bị nhận là ảo giác).
    # Phải có chỗ ghi riêng vì hai thứ này dẫn tới hai hành động khác nhau:
    # `error` là thứ cần sửa hạ tầng, `skip_note` là thứ cần hiệu chỉnh
    # ngưỡng. Gộp chung vào `error` sẽ biến mọi mẩu im lặng bình thường thành
    # một mẩu "lỗi" và làm hỏng luôn ý nghĩa của trạng thái `failed`.
    skip_note = fields.Text(string='Ghi chú bỏ qua')

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
        # 'processing' VẪN nhận audio. Lệnh dừng được phát đi SAU khi bản ghi
        # đã chuyển sang 'processing', nên mẩu cuối của mỗi máy — tới 15 giây
        # lời kết — bao giờ cũng tới nơi khi trạng thái đã đổi. Chốt ở
        # 'recording' nghĩa là mọi cuộc họp đều mất đoạn kết của mọi người.
        # Việc hoàn tất vốn đã chờ thêm một nhịp cron chính là để đợi những
        # mẩu đến muộn này (xem meeting_recording._cron_sweep).
        if recording.sudo().state not in ('recording', 'processing'):
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
            chunk = self.sudo().create({
                'recording_id': recording.id,
                'partner_id': partner.id,
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
        """Bóc băng đúng một mẩu đã được `_claim()` khoá. Tách riêng khỏi
        `_cron_process` để việc khoá + xử lý + commit luôn đi cùng nhau
        trong một giao dịch — xem ghi chú trong `_cron_process`."""
        self.ensure_one()
        try:
            # SAVEPOINT là thứ khiến khối `except` dưới đây CHẠY ĐƯỢC. Nếu
            # `_transcribe()` hoặc `_write_segments()` ném một lỗi TẦNG CSDL
            # (deadlock/serialization failure khi ghi segment, vi phạm khoá
            # ngoại vì bản ghi bị xoá song song), cursor rơi vào
            # InFailedSqlTransaction: mọi câu lệnh sau đó đều lỗi, nên
            # `_mark_retry` -> `write()` -> flush LẠI NÉM TIẾP. Lỗi thứ hai
            # đó thoát khỏi cả `_process_one` lẫn vòng `while` của
            # `_cron_process` và giết nguyên lượt cron. Hậu quả không dừng ở
            # một mẩu: state vẫn 'pending', attempt vẫn nguyên nên trần retry
            # không bao giờ chạm tới, mà `_claim()` lại sắp xếp theo `id` —
            # đúng mẩu hỏng đó được nhận đầu tiên ở MỌI nhịp cron, mãi mãi,
            # và mọi mẩu phía sau không bao giờ chạy. Rollback về savepoint
            # trả cursor về trạng thái dùng được, nên thất bại mới ghi
            # lại được.
            with self.env.cr.savepoint():
                raw = base64.b64decode(self.attachment_id.sudo().datas or b'')
                # Tiền xử lý TRƯỚC khi gọi ASR, không phải lọc đầu ra sau đó.
                # Ảo giác trên khoảng lặng là lỗi nặng nhất của Whisper, và
                # cách chắc chắn nhất để nó không sinh ra một câu bịa là
                # ĐỪNG HỎI nó về đoạn audio không có tiếng nói. Lọc đầu ra
                # (`text_filter` bên dưới) chỉ là lưới thứ hai cho những gì
                # lọt qua cổng này.
                wav, skip = self.env['aidt.meeting.audio.prep']._prepare(
                    raw, self.duration_ms)
                if wav is None:
                    # 'done' chứ KHÔNG phải 'failed': không có gì hỏng cả,
                    # mẩu này chỉ không có nội dung để bóc băng. Đánh dấu
                    # 'failed' sẽ đốt lượt retry cho một việc chắc chắn ra
                    # cùng kết quả, và tệ hơn — `transcript_builder` in một
                    # dòng "[thiếu âm thanh …]" cho mọi mẩu `failed`, nên mỗi
                    # quãng im lặng bình thường sẽ thành một lời cáo lỗi giữa
                    # biên bản.
                    self._write_segments([])
                    self.sudo().write({
                        'state': 'done', 'error': False, 'skip_note': skip})
                    return
                parsed = self.env['aidt.meeting.asr.client']._transcribe(
                    wav, f'chunk-{self.id}.wav')
                kept, notes = self.env[
                    'aidt.meeting.text.filter']._filter_segments(parsed)
                self._write_segments(kept)
                self.sudo().write({
                    'state': 'done', 'error': False,
                    'skip_note': '\n'.join(notes) if notes else False})
        except Exception as exc:                     # noqa: BLE001
            _logger.exception('Bóc băng thất bại cho mẩu %s', self.id)
            self.env.invalidate_all()
            self._mark_retry(str(exc))

    def _write_segments(self, parsed):
        """Quy đổi mốc tương đối trong chunk sang tuyệt đối trong cuộc họp.

        Mốc thời gian từ ASR là ĐẦU VÀO NGOÀI, KHÔNG TIN ĐƯỢC — phải kẹp lại
        trước khi ghi, không chuyển tiếp nguyên văn. Quan sát thật ngày
        05/08/2026 trên `vinai/PhoWhisper-large` chạy vLLM 0.26.0: với một
        mẩu dài 8.208 giây, service trả `end: 40.08`, và các segment khác có
        `end` tới 415.6 / 264.46 giây. Ghi thẳng những giá trị đó xuống tạo
        ra hàng `start_ms=16860, end_ms=4980` — `end_ms` NHỎ HƠN `start_ms`,
        một trạng thái vô nghĩa theo chính ngữ nghĩa của hai trường này.
        Hiện chưa chỗ nào đọc `end_ms` nên chưa ai thấy, và đó chính là lý do
        phải chặn ở đây: một dữ liệu hỏng âm thầm sẽ mục ra trong CSDL cho
        tới khi có người bắt đầu tin nó.

        Ba bước kẹp:
          * `start` phải nằm trong `[0, duration_ms]`. Đây là bước QUAN TRỌNG
            NHẤT và là bước duy nhất mà ràng buộc CSDL không thể bắt hộ:
            `CHECK (end_ms >= start_ms)` bất lực vì `end` được suy ra TỪ
            `start`, nên một `start` sai kéo `end` sai theo đúng chiều hợp lệ.
            Cùng dịch vụ trả `end: 415.6` cho một mẩu 8.2 giây cũng trả `start`
            vô nghĩa, và `start_ms` chính là thứ `transcript_builder._build`
            dùng để SẮP XẾP toàn bộ bản bóc băng, đồng thời là thứ phần khử
            trùng ở mối nối dựa vào để biết hai đoạn có liền nhau hay không.
            Một giá trị hỏng vừa ném một câu nói sang chỗ khác cách đó vài
            phút, vừa làm hỏng luôn việc khử trùng cho chính người đó.
          * `end` không được vượt quá độ dài mẩu — ngoài mẩu là không thể;
          * `end` không được nhỏ hơn `start`. Đoạn suy biến thu về độ dài 0
            chứ không bị bỏ đi: `text` vẫn là nội dung thật đã bóc băng
            được, và bản bóc băng chỉ đọc `start_ms`.

        Ràng buộc `CHECK (end_ms >= start_ms)` ở `aidt.meeting.segment` là
        lưới an toàn tầng CSDL cho mọi đường ghi khác.
        """
        self.ensure_one()
        Segment = self.env['aidt.meeting.segment'].sudo()
        Segment.search([('chunk_id', '=', self.id)]).unlink()
        rows = []
        for item in parsed:
            start = min(max(item['start_ms'], 0), self.duration_ms)
            end = item['end_ms']
            if end is None:
                end = self.duration_ms
            end = min(end, self.duration_ms)
            end = max(end, start)
            rows.append({
                'recording_id': self.recording_id.id,
                'chunk_id': self.id,
                'partner_id': self.partner_id.id,
                'start_ms': self.offset_ms + start,
                'end_ms': self.offset_ms + end,
                'text': item['text'],
            })
        if rows:
            Segment.create(rows)

    @api.model
    def _recover_from_broken_chunk(self, chunk):
        """Đưa cursor về trạng thái dùng được và đóng đinh mẩu thành 'failed'.

        Chỉ chạy khi `_process_one` đã thất bại CẢ ở đường ghi lỗi bên trong
        nó (savepoint của `_process_one` đã không cứu được, hoặc chính
        `_mark_retry`/`_mark_failed` bên trong đó ném tiếp). Bọc thêm một lớp
        try/except quanh chính lời gọi `_mark_failed` ở đây vì lý do y hệt:
        nếu bản thân câu ghi 'failed' này CŨNG ném lỗi (ví dụ cursor đã bị
        đầu độc sâu, hoặc write() đụng một ràng buộc khác), lỗi đó sẽ thoát
        ra khỏi vòng `while` của `_cron_process` và giết cả lượt cron —
        đúng cái bẫy mà lớp chắn thứ hai này sinh ra để tránh. Không bọc thì
        toàn bộ ý nghĩa của "lớp chắn thứ hai" biến mất: một chunk hỏng kép
        vẫn có thể kéo sập mọi chunk phía sau nó.

        Không rollback khi `test_enable`: cursor của TransactionCase cấm
        rollback trực tiếp (cùng lý do với chỗ không commit ở `_cron_process`).
        """
        if not config['test_enable']:
            self.env.cr.rollback()
        self.env.invalidate_all()
        try:
            chunk._mark_failed(
                'Mẩu làm hỏng lượt xử lý và không ghi được lỗi tạm thời; '
                'đánh dấu failed để hàng đợi không bị kẹt. Xem log máy chủ.')
        except Exception:                           # noqa: BLE001
            _logger.exception(
                'Không đánh dấu failed được cho mẩu %s — hàng đợi có thể bị '
                'kẹt ở mẩu này.', chunk.id)

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
                # Lớp chắn thứ hai, cố tình thừa: `_process_one` đã tự bọc
                # savepoint + except, nhưng nếu chính đường ghi lỗi bên
                # trong nó cũng hỏng thì không được để một mẩu kéo đổ cả lô
                # — những mẩu phía sau không liên quan gì tới nó, và nếu
                # vòng lặp chết ở đây thì mẩu này lại được `_claim()` nhận
                # đầu tiên ở nhịp sau (sắp theo `id`), lặp vô hạn.
                _logger.exception(
                    'Mẩu %s làm hỏng cả lượt xử lý; đánh dấu failed và '
                    'chạy tiếp lô.', chunk.id)
                self._recover_from_broken_chunk(chunk)
            if not config['test_enable']:
                self.env.cr.commit()
            processed += 1
        return True
