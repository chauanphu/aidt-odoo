import hashlib
import logging
import time

import psycopg2

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

MAX_ATTEMPT = 3
# Lùi lịch theo cấp số nhân: service vừa chết thì thử lại ngay không ích gì.
# Phần tử thứ ba (16) hiện không bao giờ tới được vì MAX_ATTEMPT=3 (chỉ số
# dùng tới min(attempt-1, len-1) = 1 ở lần thử cuối) — giữ lại có chủ đích,
# làm chỗ trống sẵn nếu sau này nâng MAX_ATTEMPT lên.
RETRY_BACKOFF_MINUTES = (1, 4, 16)


class AidtIndexJob(models.Model):
    _name = 'aidt.index.job'
    _description = 'Việc chỉ mục tài liệu'
    _order = 'create_date desc, id desc'

    document_id = fields.Many2one(
        'aidt.document', string='Văn bản', required=True,
        ondelete='cascade', index=True)
    file_id = fields.Many2one(
        'dms.file', string='Tệp', ondelete='cascade', index=True)
    content_hash = fields.Char(string='Hash nội dung', size=64, index=True)

    state = fields.Selection(
        [('pending', 'Chờ xử lý'), ('extracting', 'Đang trích xuất'),
         ('chunking', 'Đang chia đoạn'), ('embedding', 'Đang tạo vector'),
         ('done', 'Xong'), ('failed', 'Lỗi')],
        string='Trạng thái', default='pending', required=True, index=True)
    error_kind = fields.Selection(
        [('transient', 'Tạm thời'), ('permanent', 'Vĩnh viễn')],
        string='Loại lỗi')
    attempt = fields.Integer(string='Số lần thử', default=0)
    next_retry_at = fields.Datetime(string='Thử lại lúc')
    error = fields.Text(string='Thông điệp lỗi')
    stage_ms = fields.Json(string='Thời gian từng chặng')

    def init(self):
        """Chỉ mục UNIQUE riêng phần cho job đang hoạt động của một tệp.

        Không có ràng buộc này, hai sự kiện create/write gần như đồng thời
        trên CÙNG một dms.file (hai tab trình duyệt lưu nội dung liên tiếp,
        hai request chồng nhau) đều gọi `_enqueue_file` và mỗi lời gọi đều
        `create()` vô điều kiện — sinh ra hai job 'pending' trỏ cùng file_id.
        Hai job đó là hai row riêng biệt nên khoá `FOR UPDATE SKIP LOCKED`
        của `_claim()` không loại trừ lẫn nhau: hai worker chạy song song có
        thể nhận MỖI worker MỘT job trong cặp đó và cùng lúc viết chunk cho
        cùng file_id. Việc chặn ở tầng CSDL (thay vì đọc-rồi-ghi trong
        Python, vốn vẫn có thể đua) là cách duy nhất an toàn thật sự. Job đã
        'done'/'failed' không tính — văn bản đổi reference sau khi đã xong
        vẫn phải được xếp lại hàng (test_doi_reference_xep_lai_hang_chi_muc).
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS aidt_index_job_active_file_uniq
              ON aidt_index_job (file_id)
              WHERE state NOT IN ('done', 'failed')
        """)

    # ------------------------------------------------------------------ #
    # Xếp hàng
    # ------------------------------------------------------------------ #
    @api.model
    def _enqueue_file(self, dms_file):
        """Tạo job cho một dms.file thuộc aidt.document. Trả về job hoặc None."""
        directory = dms_file.sudo().directory_id
        if directory.res_model != 'aidt.document' or not directory.res_id:
            return None
        content = dms_file.sudo().with_context(bin_size=False).content
        digest = hashlib.sha256(content or b'').hexdigest() if content else False
        try:
            with self.env.cr.savepoint():
                return self.sudo().create({
                    'document_id': directory.res_id,
                    'file_id': dms_file.id,
                    'content_hash': digest,
                    'state': 'pending',
                })
        except psycopg2.IntegrityError:
            # Đụng chỉ mục UNIQUE ở init(): đã có job đang hoạt động cho
            # đúng tệp này (đua create/write). Dùng tiếp job đó thay vì sinh
            # bản sao — nhưng KHÔNG được ghi đè content_hash vô điều kiện.
            existing = self.sudo().search([
                ('file_id', '=', dms_file.id),
                ('state', 'not in', ('done', 'failed')),
            ], limit=1)
            if not existing:
                return existing
            if existing.state == 'pending':
                # Chưa ai claim: chưa có chunk nào gắn với hash cũ, ghi đè
                # thẳng là an toàn — job sẽ được xử lý đúng nội dung mới.
                existing.write({'content_hash': digest})
            else:
                # Job đang dở (extracting/chunking/embedding) — pipeline có
                # thể đang trích xuất/chia đoạn/tạo vector cho NỘI DUNG CŨ.
                # Nếu chỉ đổi content_hash mà để job tự hoàn tất, nó sẽ
                # _mark_done với chunk của nội dung cũ nhưng lại mang hash
                # của nội dung mới — sau đó _copy_chunks_from_twin có thể
                # gán nhầm đúng những chunk cũ này cho một tệp khác thực sự
                # có nội dung trùng hash mới. Đưa job về lại 'pending' với
                # hash mới: nó sẽ bị `_claim()` nhận lại và xử lý đúng nội
                # dung mới từ đầu — không có đường nào để hash và chunk của
                # cùng một job lệch nhau, và tệp không bị bỏ rơi ở trạng
                # thái dở dang vì vẫn quay lại hàng đợi.
                existing.write({
                    'state': 'pending', 'content_hash': digest,
                    'attempt': 0, 'error': False, 'error_kind': False,
                    'next_retry_at': False,
                })
            return existing

    @api.model
    def _enqueue_document(self, documents):
        """Xếp lại hàng toàn bộ tệp của văn bản — dùng khi đổi reference/name/
        doc_type, vì ba trường đó nằm trong contextual header đã embed."""
        for doc in documents:
            for dms_file in doc.sudo().directory_id.file_ids:
                self._enqueue_file(dms_file)

    # ------------------------------------------------------------------ #
    # Trạng thái
    # ------------------------------------------------------------------ #
    def _mark_transient(self, message):
        """Lỗi tạm thời: giữ pending, lùi lịch. Quá trần mới thành failed."""
        for job in self:
            attempt = job.attempt + 1
            if attempt >= MAX_ATTEMPT:
                job.write({
                    'state': 'failed', 'error_kind': 'transient',
                    'attempt': attempt, 'error': message, 'next_retry_at': False,
                })
                continue
            delay = RETRY_BACKOFF_MINUTES[min(attempt - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
            job.write({
                'state': 'pending', 'error_kind': 'transient', 'attempt': attempt,
                'error': message,
                'next_retry_at': fields.Datetime.add(fields.Datetime.now(), minutes=delay),
            })

    def _mark_permanent(self, message):
        """Lỗi vĩnh viễn: failed ngay. Retry chỉ đốt GPU để nhận đúng lỗi đó."""
        self.write({
            'state': 'failed', 'error_kind': 'permanent',
            'error': message, 'next_retry_at': False,
        })

    def _mark_done(self, stage_ms=None):
        self.write({
            'state': 'done', 'error': False, 'error_kind': False,
            'next_retry_at': False, 'stage_ms': stage_ms or {},
        })

    def action_retry(self):
        self.write({
            'state': 'pending', 'attempt': 0, 'error': False,
            'error_kind': False, 'next_retry_at': False,
        })

    def write(self, vals):
        """`aidt.document.index_state` là `store=True` nhưng chỉ `@api.depends`
        trên `directory_id.file_ids` — đổi `state` của job không tự kích hoạt
        tính lại. Ép tính lại tường minh ở đây để badge trên form văn bản
        luôn khớp trạng thái job mới nhất."""
        res = super().write(vals)
        if 'state' in vals:
            self.mapped('document_id')._compute_index_state()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Cùng lý do với `write()` ở trên, cho nhánh CÒN LẠI: job MỚI luôn
        được tạo với `state='pending'` (xem `_enqueue_file`), nhưng đó là một
        `create()` trên `aidt.index.job`, không phải một `write()` trên
        `directory_id.file_ids` của văn bản cha — đã đo trực tiếp (không suy
        luận): `@api.depends('directory_id.file_ids')` KHÔNG kích hoạt tính
        lại `index_state` khi một `dms.file` con được tạo thẳng với
        `directory_id` đã đặt sẵn trong `vals` (chỉ nhánh đổi `directory_id`
        trên chính văn bản mới kích hoạt, không phải nhánh đổi tập con của
        `file_ids` phía sau nó). Không có dòng này, badge trên form văn bản
        đứng yên ở 'none' cho tới lần `write()` trạng thái job kế tiếp."""
        jobs = super().create(vals_list)
        jobs.mapped('document_id')._compute_index_state()
        return jobs

    # ------------------------------------------------------------------ #
    # Worker
    # ------------------------------------------------------------------ #
    @api.model
    def _claim(self, limit=5):
        """Nhận việc bằng SKIP LOCKED — an toàn khi sau này chạy nhiều worker.

        `write()` của ORM chỉ đánh dấu field bẩn trong cache, KHÔNG tự ghi
        xuống bảng ngay — câu SELECT thô dưới đây đọc thẳng bảng Postgres
        nên phải tự flush trước, nếu không nó thấy dữ liệu cũ (job vừa
        `_mark_transient`/chuyển 'done' vẫn hiện 'pending' trong kết quả).
        """
        self.flush_model()
        self.env.cr.execute("""
            SELECT id FROM aidt_index_job
             WHERE state = 'pending'
               AND (next_retry_at IS NULL OR next_retry_at <= now() AT TIME ZONE 'UTC')
             ORDER BY id
             LIMIT %s
               FOR UPDATE SKIP LOCKED
        """, (limit,))
        return self.browse([r[0] for r in self.env.cr.fetchall()])

    def _copy_chunks_from_twin(self):
        """Chép chunk từ job đã done có cùng content_hash. True nếu chép được.

        Trong ERP cùng một công văn bị đính kèm lại liên tục — đây là chỗ
        tiết kiệm nhiều nhất và gần như miễn phí.
        """
        self.ensure_one()
        if not self.content_hash:
            return False
        twin = self.sudo().search([
            ('content_hash', '=', self.content_hash),
            ('state', '=', 'done'), ('id', '!=', self.id),
        ], limit=1)
        if not twin or not twin.file_id:
            return False
        Chunk = self.env['aidt.doc.chunk'].sudo()
        source = Chunk.search([('file_id', '=', twin.file_id.id)])
        if not source:
            return False
        Chunk.search([('file_id', '=', self.file_id.id)]).unlink()
        for chunk in source:
            chunk.copy({'document_id': self.document_id.id, 'file_id': self.file_id.id})
        self.env.cr.execute("""
            UPDATE aidt_doc_chunk tgt
               SET embedding = src.embedding
              FROM aidt_doc_chunk src
             WHERE tgt.file_id = %s AND src.file_id = %s AND tgt.seq = src.seq
        """, (self.file_id.id, twin.file_id.id))
        return True

    def _process_one(self):
        """Xử lý đúng một job đã được `_claim()` khoá. Tách riêng khỏi
        `_cron_process` để việc khoá + xử lý + commit luôn đi cùng nhau
        trong một giao dịch — xem ghi chú trong `_cron_process`."""
        self.ensure_one()
        try:
            if self._copy_chunks_from_twin():
                self._mark_done({'dedup': 0})
            else:
                self.env['aidt.index.pipeline']._run(self)
        except Exception as exc:                    # noqa: BLE001
            _logger.exception("Chỉ mục thất bại cho job %s", self.id)
            self._mark_transient(str(exc))

    @api.model
    def _cron_process(self, limit=5, budget_seconds=300):
        """Chạy mỗi phút, xử lý tối đa `limit` job.

        Nhận (`_claim`) và xử lý TỪNG job một, commit ngay sau job đó, thay
        vì khoá nguyên một lô rồi lặp qua với commit xen giữa. Lý do: khoá
        `FOR UPDATE SKIP LOCKED` chỉ tồn tại trong giao dịch hiện tại — nếu
        khoá cả lô rồi commit sau job đầu tiên, các job còn lại trong lô
        (chưa xử lý) bị NHẢ khoá ngay lập tức dù trạng thái CSDL của chúng
        vẫn là 'pending'. Một tiến trình cron khác chạy chồng lên đúng lúc
        đó có thể `_claim()` trúng những job "còn lại" ấy và xử lý song
        song với vòng lặp này — hai worker cùng ghi chunk cho cùng job. Nhận
        từng job một khiến khoá + xử lý + commit luôn nằm trong đúng một
        giao dịch, đóng hoàn toàn cửa sổ đua này. Cũng vì thế: một tệp hỏng
        không kéo đổ những tệp tốt. Có ngân sách đồng hồ để không giữ cron
        quá lâu.

        Không commit khi `test_enable` bật: cursor của TransactionCase cấm
        commit/rollback trực tiếp (ném AssertionError) để bảo toàn khả năng
        rollback toàn bộ test — xem `odoo/tests/common.py`. `TestDedup` gọi
        thẳng `_cron_process()` bên trong một test nên hàm này phải chạy
        được mà không commit thật; mỗi test tự rollback khi kết thúc nên
        không commit ở đây không ảnh hưởng gì tới hành vi thật khi cron chạy
        qua ir.cron (lúc đó `test_enable` luôn tắt).
        """
        started = time.monotonic()
        processed = 0
        while processed < limit:
            if time.monotonic() - started > budget_seconds:
                break
            job = self._claim(limit=1)
            if not job:
                break
            job._process_one()
            if not config['test_enable']:
                self.env.cr.commit()
            processed += 1
        return True
