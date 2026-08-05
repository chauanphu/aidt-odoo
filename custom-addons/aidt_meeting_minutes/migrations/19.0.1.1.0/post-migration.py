import logging

_logger = logging.getLogger(__name__)

# Model ASR mặc định: đổi từ bản tinh chỉnh tiếng Việt sang Whisper gốc.
#
# VÌ SAO ĐỔI. `vinai/PhoWhisper-large` được tinh chỉnh trên tiếng Việt ĐỌC
# (kiểu VLSP): xuất chữ thường, không dấu câu, không có vốn từ cho hội thoại
# kỹ thuật hay từ tiếng Anh chen vào. Bản ghi 1140 ngày 05/08/2026 cho ra
# "lô cồ" (= local), "con ngôi đồ" (= con model), "hỗn hợp" (= cuộc họp),
# "ghim"/"găm" (= ghi âm). Âm thanh đã được NGHE đúng — chỉ TỪ là sai, tức
# lỗi mô hình ngôn ngữ chứ không phải lỗi tín hiệu.
#
# VÌ SAO PHẢI CÓ SCRIPT NÀY — VÀ VÌ SAO BA THAM SỐ MỚI CÙNG ĐỢT THÌ KHÔNG.
# `data/ir_config_parameter.xml` nằm trong `<data noupdate="1">`. Cơ chế đó
# KHÔNG phải "không bao giờ nạp lại file": nó bỏ qua các bản ghi ĐÃ CÓ trong
# `ir_model_data`, còn xml_id MỚI thì vẫn được TẠO khi nâng cấp (đã kiểm
# chứng thật trên `aidt_demo` ngày 05/08/2026 với `param_asr_response_format`
# — tham số xuất hiện đúng giá trị sau `-u aidt_meeting_minutes`).
#
# Nên `param_asr_language`, `param_asr_prompt`, `param_asr_temperature` tự lo
# được. Còn `param_asr_model` thì ĐÃ TỒN TẠI trên mọi CSDL cài từ trước —
# sửa giá trị trong XML sẽ KHÔNG bao giờ tới được `aidt_demo`, và mọi lần
# bóc băng sẽ âm thầm chạy tiếp bằng model cũ trong khi cả file dữ liệu lẫn
# tài liệu đều nói là đã đổi. Đây đúng là cái bẫy đã cắn dự án này một lần
# rồi: xem migrations/19.0.1.0.1, nơi `llm_url`/`llm_model` sai vẫn nằm y
# nguyên trên `aidt_demo` sau khi commit sửa XML đã merge, và hậu quả là
# tóm tắt hỏng ÂM THẦM.
#
# CHỈ SỬA khi giá trị hiện tại ĐÚNG BẰNG mặc định cũ. Quản trị viên đã tự
# trỏ sang dịch vụ bên thứ ba (OpenAI, Deepgram…) hay một checkpoint khác là
# một quyết định có ý thức; ghi đè nó là làm hỏng cấu hình của người ta.
KEY = 'aidt_meeting.asr_model'
OLD = 'vinai/PhoWhisper-large'
NEW = 'openai/whisper-large-v3'


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "UPDATE ir_config_parameter SET value = %s "
        " WHERE key = %s AND value = %s",
        (NEW, KEY, OLD))
    if cr.rowcount:
        _logger.info(
            'aidt_meeting_minutes: đổi %s từ %r sang %r', KEY, OLD, NEW)
    else:
        # Không phải lỗi: hoặc CSDL đã ở giá trị mới, hoặc quản trị viên đã
        # trỏ sang chỗ khác. Ghi lại để người vận hành biết vì sao không có
        # gì đổi, thay vì phải đoán.
        cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s",
                   (KEY,))
        row = cr.fetchone()
        _logger.info(
            'aidt_meeting_minutes: giữ nguyên %s = %r (không phải mặc định '
            'cũ %r), không ghi đè', KEY, row and row[0], OLD)
