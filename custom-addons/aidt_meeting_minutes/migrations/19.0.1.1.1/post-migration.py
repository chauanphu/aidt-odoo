import logging

_logger = logging.getLogger(__name__)

# Prompt mặc định: đổi từ kiểu LIỆT KÊ sang VĂN XUÔI.
#
# VÌ SAO. Bản liệt kê ("… Nội dung thường gặp: cuộc họp, ghi âm, …") gây sự
# cố thật ngay trong ngày nó ra: bản ghi 1141, cuộc gọi thật hai người, model
# nhả ngược chính prompt ra rồi lặp 18 lần giữa biên bản —
#
#   "Các bạn có thể tham gia một cuộc họp hành chính. Nội dung thường gặp:
#    cuộc họp hành chính. Nội dung thường gặp: …"
#
# Whisper tiếp nối VĂN PHONG của prompt, mà "nhãn: a, b, c" là một danh sách
# đang dở — tiếp nối nó nghĩa là đẻ thêm mục.
#
# VÌ SAO PHẢI CÓ SCRIPT NÀY. `param_asr_prompt` được TẠO ở 19.0.1.1.0, nên
# tính từ 19.0.1.1.1 nó là bản ghi ĐÃ CÓ trong `ir_model_data` — và
# `data/ir_config_parameter.xml` nằm trong `<data noupdate="1">`, nghĩa là
# sửa giá trị trong XML sẽ KHÔNG bao giờ tới được `aidt_demo`. Đúng cái bẫy
# đã cắn `llm_url`/`llm_model` (19.0.1.0.1) và `asr_model` (19.0.1.1.0).
#
# CHỈ SỬA khi giá trị hiện tại đúng bằng bản liệt kê cũ: quản trị viên đã tự
# viết prompt riêng cho lĩnh vực của họ là một quyết định có ý thức.
KEY = 'aidt_meeting.asr_prompt'
OLD = (
    'Biên bản cuộc họp hành chính. Nội dung thường gặp: cuộc họp, ghi âm, '
    'bóc băng, biên bản, phân quyền, người dùng, hệ thống, cơ sở dữ liệu, '
    'máy chủ, cấu hình, triển khai, độ mật. Từ tiếng Anh hay chen vào: '
    'local, server, model, AI, API, Docker, Odoo, Whisper, log, file, '
    'meeting, transcript.'
)
NEW = (
    'Đây là biên bản một cuộc họp hành chính. Chúng tôi trao đổi về việc '
    'ghi âm và bóc băng biên bản, phân quyền người dùng, độ mật của văn '
    'bản, cấu hình server và cơ sở dữ liệu, cùng con model AI chạy local '
    'trên hệ thống Odoo.'
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "UPDATE ir_config_parameter SET value = %s WHERE key = %s AND value = %s",
        (NEW, KEY, OLD))
    if cr.rowcount:
        _logger.info(
            'aidt_meeting_minutes: đổi %s sang bản văn xuôi (bản liệt kê cũ '
            'gây vòng lặp nhả prompt ở bản ghi 1141).', KEY)
    else:
        _logger.info(
            'aidt_meeting_minutes: giữ nguyên %s (không phải bản liệt kê '
            'mặc định cũ), không ghi đè.', KEY)
