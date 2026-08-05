import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Kẹp lại các đoạn có `end_ms < start_ms` TRƯỚC khi ràng buộc
    `CHECK (end_ms >= start_ms)` được áp lên bảng.

    Ràng buộc mới không thể tạo được nếu bảng còn hàng vi phạm — Odoo sẽ ghi
    cảnh báo rồi bỏ qua, và CSDL đó âm thầm chạy tiếp mà KHÔNG có lưới an
    toàn, đúng thứ mà ràng buộc này sinh ra để có. Những hàng vi phạm là hậu
    quả của việc `_write_segments()` trước đây chuyển tiếp nguyên văn mốc
    thời gian của ASR (xem migrations/19.0.1.0.1 và README §2.3): đã quan sát
    thật hàng `start_ms=16860, end_ms=4980`.

    Thu về độ dài 0 chứ không xoá: `text` là nội dung đã bóc băng được thật,
    và bản bóc băng chỉ đọc `start_ms`.
    """
    if not version:
        return
    cr.execute("""
        UPDATE aidt_meeting_segment
           SET end_ms = start_ms
         WHERE end_ms < start_ms
    """)
    if cr.rowcount:
        _logger.info(
            'aidt_meeting_minutes: kẹp %s đoạn có end_ms < start_ms',
            cr.rowcount)
