import logging

_logger = logging.getLogger(__name__)

# Cặp (key, giá trị SAI đã từng ship, giá trị đúng).
#
# `data/ir_config_parameter.xml` nằm trong `<data noupdate="1">`, nên
# `-u aidt_meeting_minutes` KHÔNG ghi đè các bản ghi đã tồn tại. Đó là chủ ý
# (quản trị viên đổi endpoint từ UI thì không được reset mỗi lần nâng cấp),
# nhưng nó có hệ quả đã QUAN SÁT ĐƯỢC THẬT trên `aidt_demo` ngày 05/08/2026:
# một CSDL cài từ trước commit 9631dac vẫn giữ nguyên
#   aidt_meeting.llm_url   = http://aidt-llm:8003/v1   (cổng của vLLM, nhưng
#                                                       aidt-llm chạy Ollama
#                                                       ở 11434)
#   aidt_meeting.llm_model = gemma4:12b                 (không khớp tag Ollama
#                                                       nào)
# sau khi commit đó đã sửa file XML. Hậu quả: mọi lần tóm tắt đều hỏng với
# "Connection refused", `summary_error` được ghi lại còn transcript vẫn đăng
# — tức là lỗi ÂM THẦM với người dùng cuối, chỉ thấy khi mở form bản ghi.
#
# Chỉ sửa khi giá trị hiện tại ĐÚNG BẰNG giá trị sai đã ship. Quản trị viên
# đã tự trỏ sang dịch vụ khác thì không đụng tới.
FIXES = [
    ('aidt_meeting.llm_url', 'http://aidt-llm:8003/v1',
     'http://aidt-llm:11434/v1'),
    ('aidt_meeting.llm_model', 'gemma4:12b', 'gemma3:12b-it-qat'),
]


def migrate(cr, version):
    if not version:
        return
    for key, broken, correct in FIXES:
        cr.execute(
            "UPDATE ir_config_parameter SET value = %s "
            " WHERE key = %s AND value = %s",
            (correct, key, broken))
        if cr.rowcount:
            _logger.info(
                'aidt_meeting_minutes: sửa %s từ %r thành %r',
                key, broken, correct)
