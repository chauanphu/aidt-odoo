import logging

_logger = logging.getLogger(__name__)

# Dọn sáu tham số của đường vLLM cũ.
#
# VÌ SAO GỠ. Chúng phục vụ `models/asr_client.py` và
# `models/summary_client.py`; cả hai đã bị xoá khi chuyển sang xử lý theo lô
# ở `docker/ai_worker`. Không còn dòng code nào đọc chúng, nhưng trang Cấu
# hình vẫn hiện đủ sáu ô — người vận hành đổi, thấy không có gì thay đổi,
# rồi đi tìm nguyên nhân ở chỗ khác. Đúng loại lỗi đã tốn cả buổi truy ngày
# 10/08/2026: `asr_model` ghi `openai/whisper-large-v3` trong khi thứ thực
# sự chạy là `PhoWhisper-small` ghim cứng trong worker.
#
# VÌ SAO PHẢI CÓ SCRIPT NÀY — và đây là chỗ dễ tưởng nhầm nhất.
# Với một khối dữ liệu THƯỜNG, xoá bản ghi khỏi file XML là đủ: `_process_end`
# thấy xml_id biến mất và tự xoá cả `ir_model_data` lẫn dòng nó trỏ tới.
# Nhưng khối này là `<data noupdate="1">`, và bản ghi noupdate được GIỮ LẠI
# nguyên vẹn. Đã kiểm chứng bằng chính test
# `TestConfig.test_khong_con_tham_so_cua_duong_vllm_da_go`: sau `-u`,
# `aidt_meeting.asr_url` vẫn còn với giá trị quản trị viên tự đặt
# ('http://192.168.92.114:8002/v1'). Cùng họ với cái bẫy đã cắn `llm_url`/
# `llm_model` (19.0.1.0.1), `asr_model` (19.0.1.1.0) và `asr_prompt`
# (19.0.1.1.1) — khác ở chỗ ba lần trước là về SỬA giá trị, lần này là về XOÁ.
#
# XOÁ CẢ HAI PHÍA: chỉ xoá `ir_config_parameter` mà để lại `ir_model_data`
# thì lần `-u` sau Odoo thấy một xml_id trỏ vào khoảng không.
OBSOLETE_KEYS = (
    'aidt_meeting.asr_url',
    'aidt_meeting.asr_api_key',
    'aidt_meeting.asr_response_format',
    'aidt_meeting.asr_temperature',
    'aidt_meeting.llm_url',
    'aidt_meeting.llm_api_key',
)

OBSOLETE_XMLIDS = (
    'param_asr_url',
    'param_asr_api_key',
    'param_asr_response_format',
    'param_asr_temperature',
    'param_llm_url',
    'param_llm_api_key',
    # `param_asr_model` mang tên model theo cách gọi của vLLM (một repo
    # Hugging Face). Đường mới dùng khoá RIÊNG `asr_ct2_model` vì
    # faster-whisper không nhận giá trị đó — hai khoá cùng tên mang hai
    # nghĩa là bảo đảm sẽ có người điền nhầm.
    'param_asr_model',
)


def migrate(cr, version):
    if not version:
        return

    cr.execute("DELETE FROM ir_config_parameter WHERE key IN %s",
               (OBSOLETE_KEYS + ('aidt_meeting.asr_model',),))
    removed_params = cr.rowcount

    cr.execute(
        "DELETE FROM ir_model_data "
        " WHERE module = 'aidt_meeting_minutes' AND name IN %s",
        (OBSOLETE_XMLIDS,))
    removed_xmlids = cr.rowcount

    _logger.info(
        'aidt_meeting_minutes: gỡ %s tham số và %s xml_id của đường vLLM cũ '
        '(asr_client/summary_client đã bị xoá).',
        removed_params, removed_xmlids)
