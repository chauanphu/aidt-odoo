import logging

_logger = logging.getLogger(__name__)

# Xoá prompt mặc định: `initial_prompt` làm Whisper ĐỌC TIẾP prompt thay vì
# bóc băng, và nó ăn mất nội dung thật chứ không chỉ chèn thêm rác.
#
# ĐO NGÀY 10/08/2026, cùng một luồng audio, chỉ đổi mỗi `initial_prompt`:
#   * Bản ghi 2858, luồng Nguyễn Văn An — CÓ prompt: một segment DUY NHẤT
#     trải 44 giây (0.4 -> 44.4) mang nguyên văn prompt, avg_logprob -0.06.
#     KHÔNG prompt: đúng 44 giây đó ra 8 câu thật ("hoàn thành khoảng 70%",
#     "API đôi khi phản hồi khá chậm", "bổ sung cơ chế caching"…).
#   * Bản ghi 2856 (một từ "alo" trong 9,5 giây): toàn bộ transcript là một
#     biến thể rút gọn của prompt.
#   * Bản ghi 2797: có prompt 51 segment, không prompt 53 segment; "PDF",
#     "OCR", "tàu trình" giống hệt nhau. Lợi ích đo được bằng 0.
#
# ĐÂY LÀ LẦN ĐẢO HƯỚNG, không phải một lần tinh chỉnh tiếp. 19.0.1.1.1 kết
# luận rằng lỗi nằm ở KIỂU VIẾT prompt (liệt kê -> văn xuôi). Kết luận đó
# sai: văn xuôi chỉ làm hỏng hóc bớt lộ liễu, cơ chế nhả ngược prompt vẫn
# nguyên vẹn.
#
# CHỈ XOÁ khi giá trị hiện tại đúng bằng một trong hai bản mặc định ta từng
# ship. Quản trị viên tự viết prompt riêng cho lĩnh vực của họ là một quyết
# định có ý thức — và với họ, lưới `is_prompt_echo` trong docker/ai_worker
# vẫn chặn phần nhả ngược.
KEY = 'aidt_meeting.asr_prompt'

SHIPPED_DEFAULTS = (
    # 19.0.1.1.1 — bản văn xuôi
    'Đây là biên bản một cuộc họp hành chính. Chúng tôi trao đổi về việc '
    'ghi âm và bóc băng biên bản, phân quyền người dùng, độ mật của văn '
    'bản, cấu hình server và cơ sở dữ liệu, cùng con model AI chạy local '
    'trên hệ thống Odoo.',
    # 19.0.1.1.0 — bản liệt kê, đã gây vòng lặp ở bản ghi 1141
    'Biên bản cuộc họp hành chính. Nội dung thường gặp: cuộc họp, ghi âm, '
    'bóc băng, biên bản, phân quyền, người dùng, hệ thống, cơ sở dữ liệu, '
    'máy chủ, cấu hình, triển khai, độ mật. Từ tiếng Anh hay chen vào: '
    'local, server, model, AI, API, Docker, Odoo, Whisper, log, file, '
    'meeting, transcript.',
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "UPDATE ir_config_parameter SET value = '' "
        " WHERE key = %s AND value IN %s",
        (KEY, SHIPPED_DEFAULTS))
    if cr.rowcount:
        _logger.info(
            'aidt_meeting_minutes: xoá %s (prompt mặc định làm Whisper đọc '
            'tiếp prompt và nuốt mất 44 giây nội dung ở bản ghi 2858).', KEY)
    else:
        _logger.info(
            'aidt_meeting_minutes: giữ nguyên %s (prompt do quản trị viên tự '
            'đặt), không ghi đè.', KEY)
