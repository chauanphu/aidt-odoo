import logging

_logger = logging.getLogger(__name__)

# Bốn thao tác ở tầng CSDL mà Odoo KHÔNG tự làm khi nâng cấp.
#
# Cùng họ với ba cái bẫy `noupdate` đã cắn ở 19.0.1.0.1, 19.0.1.1.0 và
# 19.0.1.2.0: thay đổi ở tầng định nghĩa không tự tới được cơ sở dữ liệu đã
# cài. Ở đây là hai cơ chế khác nhau nhưng cùng hậu quả.


def migrate(cr, version):
    if not version:
        return

    # 1. Chỉ mục duy nhất MỘT PHẦN không tự cập nhật.
    #    `init()` dùng `CREATE UNIQUE INDEX IF NOT EXISTS`, nên khi mệnh đề
    #    WHERE đổi (thêm 'paused') lệnh đó KHÔNG LÀM GÌ CẢ và chỉ mục cũ ở
    #    lại. Hậu quả: đang tạm dừng vẫn bật được một bản ghi thứ hai trên
    #    cùng kênh. Phải drop tường minh rồi để `init()` tạo lại.
    cr.execute("DROP INDEX IF EXISTS aidt_meeting_recording_channel_active_uniq")

    # 2. Khoá duy nhất của chunk đổi từ (recording, partner, seq) sang
    #    (recording, partner, take, seq). Không gỡ trước thì mẩu đầu tiên sau
    #    mỗi lần ghi tiếp đụng khoá của mẩu đầu tiên trước khi tạm dừng, và
    #    cả lần ghi tiếp bị mất.
    cr.execute("ALTER TABLE aidt_meeting_chunk "
               "DROP CONSTRAINT IF EXISTS aidt_meeting_chunk_seq_uniq")

    # 3. Bảng quan hệ của `declined_partner_ids` — cơ chế Từ chối đã gỡ vì
    #    ghi âm nay là bắt buộc.
    cr.execute("DROP TABLE IF EXISTS aidt_meeting_recording_res_partner_rel")

    # 4. Tàn dư của đợt chuyển sang xử lý theo lô: model `aidt.meeting.segment`
    #    đã xoá từ lâu mà bảng vẫn còn trong aidt_demo.
    cr.execute("DROP TABLE IF EXISTS aidt_meeting_segment")

    _logger.info('aidt_meeting_minutes: dọn xong chỉ mục, khoá duy nhất và '
                 'hai bảng chết trước khi lên 19.0.1.3.0.')
