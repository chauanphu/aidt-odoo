"""Dịch vụ tìm kiếm: định tuyến ý định → ba kênh truy hồi → RRF → gom văn bản.

Điểm quan trọng nhất của tệp này KHÔNG phải chất lượng xếp hạng mà là THỨ TỰ
lọc quyền: tập văn bản được phép đọc phải được xác định TRƯỚC khi truy hồi và
được nhúng thẳng vào SQL dưới dạng subquery. Lọc sau khi xếp hạng là lỗ hổng —
top-50 có thể toàn văn bản mật, lọc xong còn rỗng, trong khi kết quả hợp lệ
nằm ở hạng 51 và người dùng bị báo "không có kết quả" cho thứ họ có quyền đọc.
"""

import logging
import time

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

from odoo.addons.aidt_search_engine.fusion import reciprocal_rank_fusion
from odoo.addons.aidt_search_engine.intent import parse_query
from odoo.addons.aidt_search_engine.rerank import rerank
from odoo.addons.aidt_search_engine.text import strip_accents

_logger = logging.getLogger(__name__)

CHANNEL_TOP_K = 50
SNIPPETS_PER_DOC = 3
MAX_LIMIT = 200

# Trần số văn bản ứng viên, DÙNG CHUNG cho cả hai nhánh để `total` chỉ có một
# nghĩa duy nhất: "số văn bản trong tập ứng viên đã trả về". Nhánh ba kênh tự
# nhiên bị chặn ở 3 × CHANNEL_TOP_K; nhánh metadata phải chặn tường minh, nếu
# không một câu chỉ-có-filter ("kế hoạch") sẽ nạp cả kho về Python. Khi chạm
# trần, kết quả trả kèm cờ `truncated` để giao diện nói "hơn N" chứ không nói
# dối một con số chính xác.
CANDIDATE_MAX_DOCS = 3 * CHANNEL_TOP_K

# Chỉ ba cột tsvector này được phép ghép vào SQL — danh sách trắng để tên cột
# không bao giờ đến từ dữ liệu người dùng.
TS_COLUMNS = ('ts', 'ts_noaccent', 'ts_seg')

HEADLINE_OPTIONS = (
    'StartSel=<mark>,StopSel=</mark>,MaxFragments=1,MaxWords=35,MinWords=12'
)

DEGRADED_WARNING = 'Tìm kiếm ngữ nghĩa tạm ngưng — đang tìm bằng từ khoá.'

# Job chưa tới đích: dùng để phân biệt "kho đang xử lý N tệp" với "không có
# kết quả" (§6.2 — cái bẫy im lặng thứ ba).
PENDING_JOB_STATES = ('pending', 'extracting', 'chunking', 'embedding')

FACET_FIELDS = ('doc_type', 'department_id', 'secrecy')

# Sàn liên quan của kênh vector: khoảng cách cosine LỚN HƠN ngưỡng này thì
# chunk không được vào kênh. Không có sàn thì `_channel_vector` trả top-50 vô
# điều kiện, và RRF (fusion.py) xếp hạng THUẦN THEO THỨ HẠNG nên đã bỏ hẳn độ
# lớn — không tầng nào phía sau còn cơ hội loại một chunk đã lọt vào kênh. Hệ
# quả: MỌI câu hỏi đều trả về văn bản, kể cả câu không có câu trả lời nào
# trong kho. Ba công văn kèm trích đoạn bôi vàng cho một câu hỏi vô nghĩa là
# mặc định phá vỡ lòng tin, không phải một ca biên.
#
# Con số dưới đây ĐO trên kho e2e của aidt_demo với chính service
# AITeamVN/Vietnamese_Embedding đang chạy (35 chunk, không phải suy đoán):
#
#   truy vấn ĐÚNG chủ đề (6 câu)   : khoảng cách gần nhất 0.365 … 0.798
#   truy vấn NGOÀI chủ đề (8 câu)  : khoảng cách gần nhất 0.815 … 0.926
#
# Hai phân bố tách nhau, ranh giới nằm trong khoảng (0.798, 0.815). Lấy 0.80:
# giữ đủ cả 6 câu đúng chủ đề, loại sạch cả 8 câu ngoài chủ đề. Biên rất hẹp
# nên giá trị này phải chỉnh được không cần deploy -> ir.config_parameter.
# Lệch về phía chặt là có chủ ý: hai kênh lexical vẫn chạy song song và tự có
# sàn (`@@ q` phải khớp), nên một chunk bị kênh vector loại oan vẫn còn đường
# vào kết quả, còn chunk vô can lọt vào thì không gì cứu được nữa.
DEFAULT_VECTOR_MAX_DISTANCE = 0.80


class AidtSearchService(models.AbstractModel):
    _name = 'aidt.search.service'
    _description = 'Dịch vụ tìm kiếm thông minh'

    # ------------------------------------------------------------------ #
    # ACL
    # ------------------------------------------------------------------ #
    @api.model
    def _check_not_sudo(self):
        """Toàn bộ an toàn của dịch vụ này nằm ở chỗ `_search()` áp ir.rule —
        mà `_search()` BỎ QUA mọi rule khi `env.su`. Nghĩa là nếu ai đó gọi
        `self.env['aidt.search.service'].sudo().search(...)` (rất dễ xảy ra khi
        một controller với tay lấy `.sudo()` để né một AccessError không liên
        quan) thì toàn bộ phân quyền tắt lặng lẽ, không một test nào đỏ.

        Bất biến đó phải cưỡng chế được, không phải chỉ ghi trong tài liệu.
        """
        if self.env.su:
            raise AccessError(
                'aidt.search.service không được gọi dưới quyền sudo/superuser: '
                'lọc quyền của dịch vụ này dựa hoàn toàn vào ir.rule, mà '
                'ir.rule bị bỏ qua khi chạy sudo. Hãy gọi với người dùng thật '
                '(with_user).')

    @api.model
    def _allowed_document_query(self, domain, limit=None):
        """Query các văn bản user hiện tại được đọc.

        `_search()` đã áp ir.rule của aidt_org (đơn vị + secrecy_level <=
        clearance_level), nên ta KHÔNG viết một dòng luật quyền nào — không có
        bản sao ACL để lệch. Trả về Query để nhúng làm subquery: lọc trong
        SQL, TRƯỚC khi xếp hạng.
        """
        self._check_not_sudo()
        return self.env['aidt.document']._search(domain or [], limit=limit)

    @api.model
    def _domain_from_filters(self, parsed):
        """Chỉ filter CỨNG mới được AND vào domain.

        Filter mềm (`hard=False`, xem `intent._doc_type_is_hard`) vẫn đi ra
        giao diện dưới dạng chip "Đã hiểu" để người dùng biết hệ thống đọc được
        gì, nhưng không lọc: một nhãn loại văn bản khớp giữa câu ('Xin gửi báo
        cáo tổng kết') là danh từ thường, biến nó thành điều kiện AND sẽ trả về
        rỗng cho nội dung chắc chắn có trong kho.
        """
        domain = []
        for f in parsed.filters:
            if not getattr(f, 'hard', True):
                continue
            if f.field == 'date':
                start, end = f.value
                domain += [('date', '>=', start), ('date', '<=', end)]
            else:
                domain.append((f.field, '=', f.value))
        return domain

    @api.model
    def _reference_domain(self, reference):
        """Khớp chính xác số hiệu trên các cột số hiệu có thật.

        `so_ky_hieu_gui` do aidt_vanban_den thêm vào; aidt_search không phụ
        thuộc module đó nên phải kiểm tra trường tồn tại thay vì giả định.
        """
        names = [n for n in ('reference', 'so_ky_hieu_gui')
                 if n in self.env['aidt.document']._fields]
        if not names:
            return []
        return ['|'] * (len(names) - 1) + [(n, '=', reference) for n in names]

    # ------------------------------------------------------------------ #
    # Ba kênh truy hồi — mỗi kênh tự nhúng tập được phép làm subquery
    # ------------------------------------------------------------------ #
    @api.model
    def _vector_max_distance(self):
        """Sàn liên quan, chỉnh được qua ir.config_parameter — xem
        DEFAULT_VECTOR_MAX_DISTANCE để biết số mặc định đo ở đâu ra."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'aidt_search.vector_max_distance', DEFAULT_VECTOR_MAX_DISTANCE)
        try:
            return float(raw)
        except (TypeError, ValueError):
            _logger.warning(
                'aidt_search.vector_max_distance = %r không phải số, dùng mặc '
                'định %s', raw, DEFAULT_VECTOR_MAX_DISTANCE)
            return DEFAULT_VECTOR_MAX_DISTANCE

    @api.model
    def _set_hnsw_iterative_scan(self):
        """Bật quét lặp HNSW, và KHÔNG được phép làm chết cả tìm kiếm nếu không
        bật được.

        `hnsw.iterative_scan` chỉ tồn tại từ pgvector 0.8.0. Trên bản cũ hơn,
        câu `SET LOCAL` này ném lỗi, giao dịch hỏng, và vì `_channel_vector`
        được gọi trong nhánh `else` của try/except quanh `embed()` — tức NGOÀI
        mọi handler — cả tính năng tìm kiếm ngữ nghĩa thành lỗi 500 thay vì
        giảm cấp mềm về lexical như §5.6 yêu cầu. Nói cách khác: lưới an toàn
        tự nó đánh sập đúng cơ chế an toàn mà nó sinh ra để bảo vệ.

        Nuốt lỗi ở đây là an toàn về mặt đúng đắn: tiebreaker `, c.id` ở câu
        truy vấn dưới đã khiến planner không dùng HNSW cho thứ tự nữa, nên
        quét lặp hiện KHÔNG gánh phần đúng đắn nào — nó chỉ là lưới cho tương
        lai. Ghi log để nếu ai đó bỏ tiebreaker thì còn dấu vết truy ra.
        """
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        except Exception as exc:                        # noqa: BLE001
            _logger.warning(
                'Không đặt được hnsw.iterative_scan (pgvector < 0.8.0?), chạy '
                'tiếp không có lưới quét lặp: %s', exc)

    @api.model
    def _channel_vector(self, vector, allowed_sql):
        """Kênh A — cosine trên `embedding`, top-CHANNEL_TOP_K trong tập được phép.

        Về HNSW và độ triệu hồi (đã ĐO trên aidt_demo, 20 000 chunk, pgvector
        0.8.6, không phải suy luận):

        * Không lọc, không tiebreaker: kế hoạch là `Index Scan using
          aidt_doc_chunk_embedding_idx`, và `LIMIT 50` chỉ trả về **40** hàng —
          đúng bằng `hnsw.ef_search`. Đây chính là cái bẫy: quét ANN cho tối đa
          ef_search ứng viên rồi mới lọc, nên người dùng quyền hẹp có thể bị
          báo "không có kết quả" cho thứ họ được đọc — tái hiện đúng tác hại
          mà §5.4 sinh ra để chặn.
        * Có `, c.id`: planner ĐO ĐƯỢC là chuyển sang quét chính xác + `top-N
          heapsort`. Lưu ý cách nói cho đúng: HNSW vẫn phục vụ được pathkey
          DẪN ĐẦU (`embedding <=> ...`), Postgres hoàn toàn có thể chọn
          incremental sort trên chỉ mục rồi sắp phần đuôi theo `c.id` — nghĩa
          là kế hoạch dùng HNSW vẫn NẰM TRONG tầm với của planner, chỉ là ở
          quy mô hiện tại nó không chọn. Chính vì thế `SET LOCAL
          hnsw.iterative_scan` dưới đây là lưới an toàn CÒN SỐNG, không phải
          mã chết — đừng xoá vì tưởng HNSW "không bao giờ được dùng nữa".
          Đo ở mọi mức chọn lọc (1 %, 5 %, 20 %, 100 % tập được phép) đều trả
          đủ 50/50 hàng, kể cả khi ép tắt seqscan/bitmap/nestloop/hashjoin.

        Nên GIỮ `, c.id`, có chủ đích, vì hai lý do cộng lại: (1) độ triệu hồi
        chính xác, (2) thứ tự tất định khi hai chunk cùng khoảng cách (rất hay
        gặp với văn bản mẫu lặp lại) — RRF xếp hạng theo THỨ TỰ nên hoà mà
        không phá hoà thì điểm sẽ nhảy giữa các lần chạy. Giá phải trả là O(N):
        ở 20 000 chunk đo được 7 ms khi lọc quyền còn hẹp, nhưng TRƯỜNG HỢP
        XẤU NHẤT đo được là 218 ms ở mức chọn lọc 100 % (user thấy toàn kho) —
        đó mới là con số phải đem so với ngân sách 3 s của O-04. Vẫn còn xa
        trần, và xa hơn nữa so với quy mô "vài trăm văn bản" của v1, nhưng nó
        tăng tuyến tính theo số chunk chứ không đứng yên ở 7 ms.

        Sàn liên quan (`_vector_max_distance`) nằm ngay trong WHERE chứ không
        lọc ở Python phía sau: RRF chỉ nhìn thứ hạng nên một chunk đã vào kênh
        là không còn cách nào loại ra nữa.
        """
        self._set_hnsw_iterative_scan()
        vector_literal = str(list(vector))
        self.env.cr.execute(SQL(
            """
            SELECT c.id
              FROM aidt_doc_chunk c
             WHERE c.document_id IN %s
               AND c.embedding IS NOT NULL
               AND c.embedding <=> %s::vector <= %s
             ORDER BY c.embedding <=> %s::vector, c.id
             LIMIT %s
            """,
            allowed_sql, vector_literal, self._vector_max_distance(),
            vector_literal, CHANNEL_TOP_K))
        return [r[0] for r in self.env.cr.fetchall()]

    @api.model
    def _channel_lexical(self, query_text, column, allowed_sql, unaccent=False):
        if column not in TS_COLUMNS:
            raise ValueError('cột tsvector không hợp lệ: %r' % (column,))
        # websearch_to_tsquery chịu được mọi rác người dùng gõ vào (to_tsquery
        # thì nổ khi toán tử lệch cặp), và query text luôn là tham số bind.
        query_expr = SQL('f_unaccent(%s)', query_text) if unaccent else SQL('%s', query_text)
        col = SQL.identifier('c', column)
        self.env.cr.execute(SQL(
            """
            SELECT c.id
              FROM aidt_doc_chunk c,
                   websearch_to_tsquery('simple', %s) AS q
             WHERE c.document_id IN %s
               AND %s @@ q
             ORDER BY ts_rank_cd(%s, q) DESC, c.id
             LIMIT %s
            """,
            query_expr, allowed_sql, col, col, CHANNEL_TOP_K))
        return [r[0] for r in self.env.cr.fetchall()]

    # ------------------------------------------------------------------ #
    # Gom chunk về văn bản
    # ------------------------------------------------------------------ #
    @api.model
    def _fetch_chunk_rows(self, chunk_ids, query_text, allowed_sql):
        """Đọc chunk kèm trích đoạn highlight.

        Áp LẠI subquery quyền ở đây tuy thừa (chunk_ids đã ra từ các kênh đã
        lọc) nhưng rẻ: nếu mai này có kênh thứ tư quên join quyền thì nó chết
        ở đây chứ không lọt ra giao diện.
        """
        if not chunk_ids:
            return {}
        self.env.cr.execute(SQL(
            """
            SELECT c.id, c.document_id, c.page, c.heading_path, c.zone,
                   ts_headline('simple', c.text,
                               websearch_to_tsquery('simple', %s), %s)
              FROM aidt_doc_chunk c
             WHERE c.id IN %s
               AND c.document_id IN %s
            """,
            query_text, HEADLINE_OPTIONS, tuple(chunk_ids), allowed_sql))
        return {
            row[0]: {
                'chunk_id': row[0], 'document_id': row[1], 'page': row[2],
                'heading_path': row[3], 'zone': row[4], 'snippet': row[5],
            }
            for row in self.env.cr.fetchall()
        }

    @api.model
    def _group_by_document(self, chunk_ids, rows):
        """chunk_ids đã xếp hạng -> (thứ tự văn bản, {doc_id: [đoạn]}).

        Người dùng nghĩ theo văn bản, không theo đoạn: mỗi văn bản giữ tối đa
        SNIPPETS_PER_DOC đoạn khớp tốt nhất, thứ tự văn bản là thứ tự đoạn tốt
        nhất của nó.
        """
        order, snippets = [], {}
        for chunk_id in chunk_ids:
            row = rows.get(chunk_id)
            if not row:
                continue
            doc_id = row['document_id']
            if doc_id not in snippets:
                snippets[doc_id] = []
                order.append(doc_id)
            if len(snippets[doc_id]) < SNIPPETS_PER_DOC:
                snippets[doc_id].append(row)
        return order, snippets

    # ------------------------------------------------------------------ #
    # Kết quả
    # ------------------------------------------------------------------ #
    @api.model
    def _filter_payload(self, f):
        value = f.value
        if isinstance(value, (tuple, list)):
            value = [v.isoformat() if hasattr(v, 'isoformat') else v for v in value]
        # `span` (vị trí trong `raw`) được lộ ra RPC để giao diện xoá chip
        # "Đã hiểu" một cách THẬT — cắt đúng đoạn văn bản sinh ra filter này
        # khỏi câu hỏi rồi tìm lại, chứ không chỉ giấu chip đi trong khi
        # `parse_query()` phía sau vẫn bóc lại đúng filter đó từ y nguyên
        # câu hỏi cũ ở lượt tìm kế tiếp (§5.7: "AI đề xuất, người dùng quyết"
        # nghĩa là xoá phải có tác dụng thật, không phải ảo giác trên giao diện).
        return {
            'field': f.field, 'op': f.op, 'value': value, 'label': f.label,
            'span': list(f.span),
            # False = chip chỉ báo "đã hiểu", KHÔNG lọc (§F-5). Lộ ra RPC để
            # giao diện không nói dối rằng kết quả đã được thu hẹp theo nó.
            'hard': bool(getattr(f, 'hard', True)),
        }

    @api.model
    def _document_payload(self, doc_ids, snippets):
        documents = []
        for doc in self.env['aidt.document'].browse(doc_ids):
            documents.append({
                'id': doc.id,
                'name': doc.name,
                'reference': doc.reference or '',
                'doc_type': doc.doc_type,
                'secrecy': doc.secrecy,
                'date': doc.date.isoformat() if doc.date else False,
                'department_id': doc.department_id.id,
                'department_name': doc.department_id.display_name,
                'snippets': snippets.get(doc.id, []),
            })
        return documents

    @api.model
    def _facets(self, doc_ids):
        """Đếm facet trên tập ĐÃ LỌC QUYỀN.

        Con số trên facet cũng không được lộ sự tồn tại của văn bản mật, nên
        đếm trên chính doc_ids đã qua ir.rule chứ không phải trên bảng gốc —
        và `_read_group` còn áp ir.rule thêm một lần nữa.
        """
        facets = {name: [] for name in FACET_FIELDS}
        if not doc_ids:
            return facets
        Document = self.env['aidt.document']
        domain = [('id', 'in', doc_ids)]
        for name in FACET_FIELDS:
            rows = Document._read_group(domain, [name], ['__count'])
            facets[name] = [
                (value.id if isinstance(value, models.BaseModel) else value, count)
                for value, count in rows
            ]
        return facets

    @api.model
    def _pending_index_count(self):
        """Số tệp còn đang chỉ mục mà user này được thấy — để giao diện phân
        biệt "kho đang xử lý N tệp" với "không có kết quả"."""
        return self.env['aidt.index.job'].search_count(
            [('state', 'in', list(PENDING_JOB_STATES))])

    @api.model
    def _build_result(self, parsed, doc_ids, snippets, channels_used, degraded,
                      limit, truncated=False):
        """`total` có ĐÚNG MỘT nghĩa ở cả hai nhánh: số văn bản trong tập ứng
        viên đã trả về, luôn ≤ CANDIDATE_MAX_DOCS. `truncated` cho biết tập đó
        đã chạm trần hay chưa, để giao diện hiển thị "hơn N" thay vì bịa ra một
        con số chính xác — nhất là khi nó nằm ngay cạnh dòng "đang xử lý N tệp"
        của §6.2."""
        return {
            'query': parsed.raw,
            'reference': parsed.reference,
            'filters': [self._filter_payload(f) for f in parsed.filters],
            'documents': self._document_payload(doc_ids[:limit], snippets),
            'facets': self._facets(doc_ids),
            'total': len(doc_ids),
            'truncated': truncated,
            'channels_used': channels_used,
            'degraded': degraded,
            'warning': DEGRADED_WARNING if degraded else False,
            'indexing': self._pending_index_count(),
            # Ghi đè bởi `_log_search()` khi ghi nhật ký thành công. Đặt sẵn
            # `False` ở đây để khoá này LUÔN có mặt trong mọi kết quả trả về
            # (kể cả khi ghi log thất bại/bị chặn) — client không cần kiểm
            # tra `'log_id' in result` trước khi đọc.
            'log_id': False,
        }

    # ------------------------------------------------------------------ #
    # Nhật ký (N-08) — không được phép làm hỏng kết quả tìm kiếm
    # ------------------------------------------------------------------ #
    @api.model
    def _log_search(self, parsed, result, started):
        """Ghi một dòng `aidt.search.log` cho lượt gọi `search()` này.

        Ghi trên đúng những văn bản đã TRẢ VỀ cho người dùng (trang hiện
        tại), không phải toàn bộ tập ứng viên — nhật ký phải phản ánh những
        gì người dùng thực sự thấy. `_log_search()` của model (tên trùng có
        chủ đích — cả hai đều "riêng, không lên bề mặt RPC") tự bọc
        try/except và không bao giờ ném lỗi (xem docstring của nó), nhưng vẫn
        gọi trong try/except ở đây thêm một lớp: lỗi khi TÍNH `duration_ms`
        hay khi tra `result['...']` (một thay đổi shape tương lai của
        `result` chẳng hạn) cũng không được phép biến một tìm kiếm thành
        công thành lỗi 500.
        """
        try:
            duration_ms = int((time.monotonic() - started) * 1000)
            log = self.env['aidt.search.log']._log_search(
                parsed=parsed,
                document_ids=[doc['id'] for doc in result['documents']],
                channels=result['channels_used'],
                degraded=result['degraded'],
                duration_ms=duration_ms,
            )
            # Round-1 review: `aidt.search.log.action_click()` (Task 16) có
            # kiểm tra chủ sở hữu + kiểm tra thành viên trong
            # `result_document_ids` — cả hai đều siết chặt đúng như thiết
            # kế — nhưng KHÔNG CÓ CÁCH nào cho client biết PHẢI gọi trên bản
            # ghi log nào nếu `search()` không lộ id của nó ra. Không có
            # dòng này, `action_click()` là dead code vĩnh viễn, không ai
            # gọi được. Ghi vào `result` (không phải trả riêng): nếu
            # `_log_search()` thất bại/bị chặn (sudo, lỗi ghi...) và trả về
            # recordset rỗng, `log.id` là `False` — client phải coi đó là
            # "không ghi được lượt click", không phải lỗi.
            result['log_id'] = log.id
        except Exception:                                # noqa: BLE001
            _logger.exception(
                'Không ghi được nhật ký tìm kiếm; kết quả vẫn được trả về '
                'bình thường cho người dùng.')

    # ------------------------------------------------------------------ #
    # Truy vấn
    # ------------------------------------------------------------------ #
    @api.model
    def _sanitize_limit(self, limit):
        """`limit` đến từ RPC nên phải chịu được cả kiểu sai lẫn giá trị sai —
        `int('abc')` sẽ thành ValueError rồi 500, trong khi thứ đúng phải làm
        là lùi về mặc định."""
        try:
            limit = int(limit or 20)
        except (TypeError, ValueError):
            limit = 20
        return max(1, min(limit, MAX_LIMIT))

    @api.model
    def _catalogs(self):
        Document = self.env['aidt.document']
        doc_type_field = Document._fields['doc_type']
        departments = self.env['hr.department'].search_read([], ['name'])
        urgency = Document._fields.get('do_khan')
        return (
            list(doc_type_field.selection),
            [(d['id'], d['name']) for d in departments],
            list(urgency.selection) if urgency else [],
        )

    @api.model
    def _sanitize_extra_domain(self, extra_domain):
        """`extra_domain` đến thẳng từ RPC nên phải bị chặn về đúng dạng facet.

        Đây KHÔNG phải lỗ hổng bảo mật — `_search()` vẫn AND ir.rule vào nên
        tập kết quả không thể nới rộng ra. Nó là bề mặt CHI PHÍ không giới hạn:
        một domain tuỳ ý cho phép duyệt quan hệ nhiều tầng hoặc `child_of` trên
        cây đơn vị ở mỗi lượt tìm kiếm. Module đã cẩn thận đúng chỗ này với
        `TS_COLUMNS` (danh sách trắng tên cột) và `_sanitize_limit` (cùng một
        nguồn RPC) — không có lý do gì để `extra_domain` được miễn.

        Chỉ nhận danh sách PHẲNG toàn leaf 3 phần tử, field thuộc FACET_FIELDS,
        toán tử '=' — tức đúng một phép AND, đúng thứ các nút facet sinh ra.

        Sai một phần tử là BỎ CẢ `extra_domain`, không lọc bỏ từng phần tử.
        Lọc từng phần tử là bẫy: `['|', A, B]` bỏ mất token `'|'` sẽ biến một
        phép OR thành phép AND — vẫn là một domain hợp lệ, chạy ngon lành, và
        âm thầm trả lời một câu hỏi khác câu người dùng hỏi. Thà không lọc gì
        (kết quả rộng hơn, ir.rule vẫn chặn đủ) còn hơn lọc sai mà im lặng.

        Không ném lỗi: giao diện chỉ sinh ra đúng dạng hợp lệ, nên thứ khác là
        lỗi lập trình hoặc gọi tay — không đáng biến thành 500 cho người dùng.
        """
        leaves = list(extra_domain or [])
        clean = []
        for leaf in leaves:
            if (isinstance(leaf, (list, tuple)) and len(leaf) == 3
                    and leaf[0] in FACET_FIELDS and leaf[1] == '='):
                clean.append((leaf[0], '=', leaf[2]))
            else:
                _logger.warning(
                    'extra_domain có phần tử không hợp lệ (%r); bỏ toàn bộ '
                    'extra_domain thay vì áp dụng một phần: %r', leaf, leaves)
                return []
        return clean

    @api.model
    def search(self, query, extra_domain=None, limit=20):
        self._check_not_sudo()
        started = time.monotonic()
        limit = self._sanitize_limit(limit)
        doc_types, departments, urgencies = self._catalogs()
        parsed = parse_query(query, doc_types, departments, urgencies)

        extra_domain = self._sanitize_extra_domain(extra_domain)
        domain = self._domain_from_filters(parsed) + extra_domain
        if parsed.reference:
            domain += self._reference_domain(parsed.reference)

        # Nhánh 1: không còn phần ngữ nghĩa nào để xếp hạng — tra cứu số hiệu,
        # hoặc câu chỉ gồm filter cứng. Trả thẳng tập được phép đã lọc, CÓ CHẶN
        # TRẦN: không có trần thì một câu chỉ-có-filter sẽ nạp cả kho về Python
        # rồi ném tiếp vào `_read_group` và `browse`.
        if not parsed.semantic:
            # Xét `domain` (filter CỨNG + extra_domain đã lọc), không xét
            # `parsed.filters` thô: một chip mềm không thu hẹp gì cả nên không
            # được tính là "người dùng đã hỏi một cái gì đó".
            if not (parsed.reference or domain):
                # Ô tìm kiếm rỗng: không hỏi gì thì không đổ cả kho ra.
                result = self._build_result(parsed, [], {}, [], False, limit)
                self._log_search(parsed, result, started)
                return result
            doc_ids = list(self._allowed_document_query(
                domain, limit=CANDIDATE_MAX_DOCS + 1).get_result_ids())
            truncated = len(doc_ids) > CANDIDATE_MAX_DOCS
            result = self._build_result(
                parsed, doc_ids[:CANDIDATE_MAX_DOCS], {}, [], False, limit,
                truncated=truncated)
            self._log_search(parsed, result, started)
            return result

        # Query của nhánh này KHÔNG bao giờ được "chín" thành danh sách id: nó
        # phải ở nguyên dạng subselect để lọc quyền chạy trong SQL. Dựng riêng,
        # không dùng chung với nhánh trên, để hai cách dùng không lẫn vào nhau.
        allowed_sql = self._allowed_document_query(domain).subselect()

        channels, channels_used, degraded = [], [], False
        try:
            vector = self.env['aidt.embed.client']._embed([parsed.semantic])[0]
        except Exception as exc:                        # noqa: BLE001
            # Giảm cấp mềm: một container chết không được làm chết cả tính
            # năng. RRF nhận số kênh bất kỳ nên chuyện này miễn phí.
            _logger.warning('Kênh vector không dùng được, chạy tiếp lexical: %s', exc)
            degraded = True
        else:
            channels.append(self._channel_vector(vector, allowed_sql))
            channels_used.append('vector')

        channels.append(self._channel_lexical(parsed.semantic, 'ts', allowed_sql))
        channels_used.append('lexical')
        channels.append(self._channel_lexical(
            strip_accents(parsed.semantic), 'ts_noaccent', allowed_sql, unaccent=True))
        channels_used.append('lexical_noaccent')

        # Kênh nào trả về đúng CHANNEL_TOP_K hàng là kênh đã chạm trần: còn
        # ứng viên phía sau mà ta không nhìn tới, nên `total` là cận dưới.
        truncated = any(len(ch) >= CHANNEL_TOP_K for ch in channels)

        fused = rerank(parsed.semantic, reciprocal_rank_fusion(channels))
        chunk_ids = [chunk_id for chunk_id, _score in fused]
        rows = self._fetch_chunk_rows(chunk_ids, parsed.semantic, allowed_sql)
        doc_ids, snippets = self._group_by_document(chunk_ids, rows)
        result = self._build_result(
            parsed, doc_ids[:CANDIDATE_MAX_DOCS], snippets, channels_used,
            degraded, limit, truncated=truncated)
        self._log_search(parsed, result, started)
        return result
