"""Nhật ký tìm kiếm — một bảng, hai nghĩa vụ.

1. Nhật ký truy cập N-08 — P0, yêu cầu tuân thủ bắt buộc trong DMS, không
   phải tính năng phụ: ai tìm gì, thấy văn bản nào, mở cái nào.
2. Dữ liệu nuôi bộ eval của dự án con D (Recall@10 / MRR trên truy vấn thật).

Bộ eval và cảnh báo truy cập bất thường (N-08 phần cảnh báo) nằm ngoài phạm
vi task này, nhưng dữ liệu để làm chúng phải tích luỹ từ ngày đầu — nhật ký
của quá khứ không hồi tố được.

An toàn: bảng này ghi lại NGƯỜI DÙNG ĐÃ TÌM GÌ, nhạy cảm ngang với chính nội
dung tài liệu mật trong một hệ thống có phân cấp độ mật — một câu truy vấn
kiểu "công văn tuyệt mật về ..." tự nó đã là rò rỉ nếu lọt ra ngoài. `ir.rule`
không cascade từ aidt.document/aidt.doc.chunk sang model này (bài học của
Task 12/13 lặp lại đúng ở đây) — xem hai rule riêng trong
`security/aidt_search_rules.xml`: Chuyên viên chỉ đọc log của chính mình,
nhóm quản trị đọc toàn bộ để phục vụ kiểm toán N-08.

Bảng này KHÔNG có retention/dọn dẹp tự động: mỗi lượt tìm kiếm ghi đúng một
dòng, không giới hạn, không cron xoá. Với tần suất tìm kiếm thực tế của một
đơn vị hành chính, đây chưa phải vấn đề trong v1, nhưng là nợ vận hành cần
theo dõi trước khi bảng này lớn tới mức ảnh hưởng sao lưu/hiệu năng — ghi
nhận ở đây để không bị quên, xử lý (chính sách lưu trữ + cron dọn) nằm ngoài
phạm vi task này.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class AidtSearchLog(models.Model):
    """Một bảng, hai nghĩa vụ — xem docstring module ở đầu tệp."""

    _name = 'aidt.search.log'
    _description = 'Nhật ký tìm kiếm'
    _order = 'create_date desc, id desc'

    user_id = fields.Many2one(
        'res.users', string='Người tìm', required=True, index=True,
        default=lambda self: self.env.user)
    query_raw = fields.Char(string='Truy vấn gốc', required=True)
    query_semantic = fields.Char(string='Phần ngữ nghĩa')
    filters_json = fields.Json(string='Filter đã bóc')
    channels_used = fields.Char(string='Kênh đã dùng')
    degraded = fields.Boolean(string='Chạy giảm cấp')
    result_document_ids = fields.Many2many('aidt.document', string='Kết quả')
    clicked_document_id = fields.Many2one('aidt.document', string='Đã mở')
    duration_ms = fields.Integer(string='Thời gian (ms)')

    @api.model
    def _log_search(self, parsed, document_ids, channels, degraded, duration_ms):
        """Ghi một dòng nhật ký cho một lượt gọi `aidt.search.service.search()`.

        Tiền tố `_` có chủ đích: hàm này KHÔNG được ở trên bề mặt RPC bên
        ngoài. Odoo tự chặn gọi các hàm bắt đầu bằng `_` qua XML-RPC/JSON-RPC
        (`dispatch_rpc`/`execute_kw`) — đây là cơ chế thật của framework,
        không phải quy ước suông, nên nó là lớp phòng thủ đầu tiên chống một
        client RPC tự dựng `document_ids`/`channels`/`degraded` tuỳ ý để nhét
        bằng chứng giả vào nhật ký kiểm toán. Trước khi đổi tên này, review
        chỉ ra rằng lối gọi trực tiếp qua RPC "tình cờ" thất bại vì
        `parsed.raw`/`.semantic`/`.filters` ném lỗi khi `parsed` là dict JSON
        — đúng nhưng đó là tai nạn kiểu dữ liệu, không phải phòng thủ, và sẽ
        ngừng đúng ngay khi ai đó nới lỏng chữ ký hàm. Không dựa vào tai nạn
        đó nữa.

        Lớp phòng thủ THỨ HAI, cho cả người gọi nội bộ (một controller của
        Task 17, một module khác...) chứ không chỉ RPC bên ngoài: `document_ids`
        được lọc lại qua `aidt.document.search()` DƯỚI ĐÚNG `self.env` của
        người gọi (chưa `sudo()`) trước khi ghi — nên một `document_ids` bị
        làm giả (id văn bản người gọi không có quyền đọc, kể cả văn bản mật
        vượt độ mật của họ) không thể lọt vào `result_document_ids`, bất kể
        người gọi đưa gì vào tham số. Vì phép lọc này chỉ có ý nghĩa khi
        `self.env` là của một người dùng thật, nếu chẳng may bị gọi dưới
        `sudo()`/`env.su` (cùng bẫy `_check_not_sudo()` của
        `aidt.search.service` cảnh báo) thì từ chối ghi luôn, không âm thầm
        ghi một bản ghi "đã lọc" nhưng thực ra chưa lọc gì cả.

        KHÔNG BAO GIỜ được ném lỗi ra ngoài: ghi log là nghĩa vụ PHỤ của
        search(), một khiếm khuyết ở tầng này (ACL cấu hình sai, cột thiếu
        sau một migration dở dang, deadlock, bảng đầy...) không được phép
        làm người dùng mất kết quả tìm kiếm hợp lệ của chính họ. Đây là lưới
        an toàn duy nhất và có chủ đích đặt Ở ĐÂY (trong model), không phải
        ở nơi gọi — bất kỳ ai gọi `_log_search` sau này đều được bảo đảm
        tương tự mà không phải tự nhớ bọc try/except.

        `sudo()` (chỉ ở bước `create`, sau khi đã lọc quyền ở trên) có chủ
        đích: người tìm kiếm thật (Chuyên viên) không có `perm_create` trên
        bảng này (xem `ir.model.access.csv`) — lối ghi DUY NHẤT là qua hàm có
        kiểm soát này, không phải `create()`/`write()` trực tiếp từ RPC. Mục
        đích không phải hạn chế người dùng, mà để chính người bị ghi lại
        không tự sửa được bằng chứng kiểm toán của mình — `sudo()` ở đây
        không mở lại đường đọc chéo giữa các user, vì quyền ĐỌC vẫn hoàn toàn
        do `ir.rule` của model này quyết định (xem
        `security/aidt_search_rules.xml`), không bị hàm này đụng tới.
        """
        try:
            if self.env.su:
                _logger.error(
                    'Từ chối ghi nhật ký tìm kiếm dưới quyền sudo/superuser: '
                    'bộ lọc document_ids theo quyền đọc của người gọi vô '
                    'nghĩa khi env.su, nên thà không ghi còn hơn ghi một '
                    'bản ghi tưởng đã lọc quyền mà thực ra chưa.')
                return self.browse()
            # Phòng thủ chống làm giả bằng chứng: chỉ ghi những id văn bản mà
            # CHÍNH người gọi (self.env chưa sudo ở trên) đọc được — không
            # tin thẳng `document_ids` do người gọi đưa vào, dù người gọi
            # hôm nay luôn là `search()` đã tự lọc đúng.
            readable_ids = self.env['aidt.document'].search(
                [('id', 'in', list(document_ids))]).ids
            return self.sudo().create({
                'user_id': self.env.uid,
                'query_raw': parsed.raw,
                'query_semantic': parsed.semantic or False,
                'filters_json': [
                    {'field': f.field, 'label': f.label} for f in parsed.filters],
                'channels_used': ','.join(channels),
                'degraded': degraded,
                'result_document_ids': [(6, 0, readable_ids)],
                'duration_ms': duration_ms,
            })
        except Exception:                                # noqa: BLE001
            _logger.exception(
                'Không ghi được nhật ký tìm kiếm cho user %s; bỏ qua, không '
                'chặn kết quả tìm kiếm trả về cho người dùng.', self.env.uid)
            return self.browse()

    def action_click(self, document_id):
        """Ghi nhận văn bản người dùng đã mở từ kết quả tìm kiếm này.

        Hai kiểm tra tách bạch, đúng hai câu hỏi khác nhau:

        1. AI được sửa bản ghi này — kiểm tra chủ sở hữu TRƯỚC khi `sudo()`:
           bản thân `sudo()` bỏ qua cả ACL lẫn `ir.rule`, nên nếu không chặn
           tường minh ở đây thì bất kỳ ai đoán được id bản ghi cũng có thể
           gán `clicked_document_id` lên nhật ký của người khác.
        2. GIÁ TRỊ được ghi có THẬT không — `document_id` là một int trần,
           gọi được qua RPC bởi chính chủ sở hữu, nên riêng kiểm tra (1) không
           đủ: không có kiểm tra này, chủ sở hữu hợp lệ vẫn có thể tự khai đã
           mở MỘT VĂN BẢN BẤT KỲ, kể cả văn bản họ chưa từng thấy trong kết
           quả tìm kiếm của chính lượt tìm đó (và do đó có thể vượt độ mật họ
           thật sự được xem) — làm giả một phần bằng chứng kiểm toán N-08.
           Bắt buộc `document_id` phải nằm trong `result_document_ids` của
           CHÍNH bản ghi này: đó là danh sách đã được lọc quyền tại thời điểm
           tìm kiếm (`_log_search`), nên kiểm tra thành viên ở đây không mở
           lại đường đọc chéo nào — chỉ từ chối những giá trị không thể nào
           là thật.
        """
        self.ensure_one()
        is_owner = self.sudo().user_id.id == self.env.uid
        if not is_owner and not self.env.user.has_group('aidt_org.group_aidt_admin'):
            raise AccessError('Không được sửa nhật ký tìm kiếm của người khác.')
        if document_id not in self.sudo().result_document_ids.ids:
            raise AccessError(
                'Văn bản này không nằm trong kết quả của chính lượt tìm '
                'kiếm này — không được khai đã mở nó.')
        self.sudo().write({'clicked_document_id': document_id})
        return True
