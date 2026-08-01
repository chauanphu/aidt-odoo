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
    def log_search(self, parsed, document_ids, channels, degraded, duration_ms):
        """Ghi một dòng nhật ký cho một lượt gọi `aidt.search.service.search()`.

        KHÔNG BAO GIỜ được ném lỗi ra ngoài: ghi log là nghĩa vụ PHỤ của
        search(), một khiếm khuyết ở tầng này (ACL cấu hình sai, cột thiếu
        sau một migration dở dang, deadlock, bảng đầy...) không được phép
        làm người dùng mất kết quả tìm kiếm hợp lệ của chính họ. Đây là lưới
        an toàn duy nhất và có chủ đích đặt Ở ĐÂY (trong model), không phải
        ở nơi gọi — bất kỳ ai gọi `log_search` sau này (một controller,
        Task 17...) đều được bảo đảm tương tự mà không phải tự nhớ bọc
        try/except.

        `sudo()` có chủ đích: người tìm kiếm thật (Chuyên viên) không có
        `perm_create` trên bảng này (xem `ir.model.access.csv`) — lối ghi
        DUY NHẤT là qua hàm có kiểm soát này, không phải `create()`/`write()`
        trực tiếp từ RPC. Mục đích không phải hạn chế người dùng, mà để
        chính người bị ghi lại không tự sửa được bằng chứng kiểm toán của
        mình — sudo() ở đây không mở lại đường đọc chéo giữa các user, vì
        quyền ĐỌC vẫn hoàn toàn do `ir.rule` của model này quyết định (xem
        `security/aidt_search_rules.xml`), không bị hàm này đụng tới.
        """
        try:
            return self.sudo().create({
                'user_id': self.env.uid,
                'query_raw': parsed.raw,
                'query_semantic': parsed.semantic or False,
                'filters_json': [
                    {'field': f.field, 'label': f.label} for f in parsed.filters],
                'channels_used': ','.join(channels),
                'degraded': degraded,
                'result_document_ids': [(6, 0, list(document_ids))],
                'duration_ms': duration_ms,
            })
        except Exception:                                # noqa: BLE001
            _logger.exception(
                'Không ghi được nhật ký tìm kiếm cho user %s; bỏ qua, không '
                'chặn kết quả tìm kiếm trả về cho người dùng.', self.env.uid)
            return self.browse()

    def action_click(self, document_id):
        """Ghi nhận văn bản người dùng đã mở từ kết quả tìm kiếm này.

        Tự kiểm tra chủ sở hữu TRƯỚC khi `sudo()`: bản thân `sudo()` bỏ qua
        cả ACL lẫn `ir.rule`, nên nếu không chặn tường minh ở đây thì bất kỳ
        ai đoán được id bản ghi cũng có thể gán `clicked_document_id` lên
        nhật ký của người khác. Việc đó không lộ thêm dữ liệu (không phải
        đọc), nhưng phá tính toàn vẹn của bằng chứng kiểm toán N-08 — một
        nhật ký mà ai cũng sửa được thì không còn là nhật ký.
        """
        self.ensure_one()
        is_owner = self.sudo().user_id.id == self.env.uid
        if not is_owner and not self.env.user.has_group('aidt_org.group_aidt_admin'):
            raise AccessError('Không được sửa nhật ký tìm kiếm của người khác.')
        self.sudo().write({'clicked_document_id': document_id})
        return True
