from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # 19.0.1.2.0 — ĐÃ GỠ sáu trường của đường vLLM cũ (`asr_url`,
    # `asr_api_key`, `asr_response_format`, `asr_temperature`, `llm_url`,
    # `llm_api_key`). Chúng phục vụ models/asr_client.py và
    # models/summary_client.py, cả hai đã bị xoá khi chuyển sang xử lý theo
    # lô ở docker/ai_worker. Một ô cấu hình không nối vào đâu tệ hơn là
    # không có ô nào: người vận hành đổi nó, thấy không có gì thay đổi, rồi
    # đi tìm nguyên nhân ở chỗ khác.

    # Endpoint là DỮ LIỆU chứ không phải hằng số trong code: tầng AI nằm ở
    # docker-compose.ai.yml riêng và phải thay được bằng dịch vụ bên thứ ba
    # bất cứ lúc nào mà không sửa một dòng Python nào.
    aidt_meeting_ai_service_url = fields.Char(
        string='URL dịch vụ xử lý cuộc họp',
        help='Địa chỉ worker nhận job hậu kỳ (ghép audio, bóc băng, tóm '
             'tắt). Odoo chỉ đẩy job rồi trả về ngay; kết quả quay lại bằng '
             'webhook nên địa chỉ này KHÔNG cần Odoo chờ.',
        config_parameter='aidt_meeting.ai_service_url')

    # Char, và cố ý KHÔNG dùng chung tên với tham số `asr_model` cũ: xem
    # khối giải thích ở data/ir_config_parameter.xml. Tên model ở đây theo
    # cách gọi của faster-whisper (`large-v3`), không phải repo Hugging Face.
    aidt_meeting_asr_ct2_model = fields.Char(
        string='Model bóc băng',
        help='Tên model theo cách gọi của faster-whisper: "large-v3", '
             '"medium", "small"… hoặc một repo đã chuyển sang định dạng '
             'CTranslate2.\n'
             'KHÔNG điền repo Hugging Face thường (ví dụ '
             '"openai/whisper-large-v3") — worker sẽ báo "Invalid model '
             'size" và cuộc họp chuyển sang trạng thái Lỗi.\n'
             'Model nhỏ hơn chạy nhanh và tốn ít VRAM hơn, nhưng với hội '
             'thoại kỹ thuật tiếng Việt thì "small" chọn sai từ tới mức bản '
             'bóc băng không dùng được.\n'
             'Để trống = dùng mặc định của worker.',
        config_parameter='aidt_meeting.asr_ct2_model')

    # Hai tham số GIẢI MÃ dưới đây quyết định chất lượng bản bóc băng nhiều
    # hơn hẳn URL. Để chúng ở UI chứ không ghi cứng vì việc tinh chỉnh vốn
    # từ là công việc lặp đi lặp lại của người vận hành, không phải việc
    # phải sửa code rồi deploy lại.
    aidt_meeting_asr_language = fields.Char(
        string='Ngôn ngữ bóc băng',
        help='Mã ngôn ngữ ISO gửi cho dịch vụ, ví dụ "vi" cho tiếng Việt.\n'
             'Để TRỐNG nghĩa là để model tự nhận dạng — chỉ nên dùng cho '
             'cuộc họp song ngữ, vì một cuộc họp tiếng Việt có thể bị bóc '
             'thành tiếng Anh ở vài đoạn mà không có cảnh báo nào.',
        config_parameter='aidt_meeting.asr_language')
    # Char chứ KHÔNG phải Text, dù đây là một đoạn văn. `res.config.settings.
    # execute()` gọi `_get_classified_fields()`, và hàm đó ném thẳng
    # Exception cho mọi kiểu ngoài boolean/integer/float/char/selection/
    # many2one/datetime. Với Text thì KHÔNG chỉ trường này hỏng — cả trang
    # Cấu hình không lưu được gì, vì lỗi ném ra trước khi phân loại xong.
    # Đã dính thật khi làm tính năng này (05/08/2026): bốn test settings đổ
    # cùng lúc với 'must have type ...'.
    aidt_meeting_asr_prompt = fields.Char(
        string='Mồi vốn từ (prompt)',
        help='Một đoạn văn ngắn chứa các từ hay bị bóc sai. Model coi đoạn '
             'này như văn bản đứng ngay trước audio, nên nó vừa gợi TỪ vừa '
             'gợi VĂN PHONG — hãy viết hoa và chấm câu đầy đủ để bản bóc '
             'băng cũng có hoa và dấu câu.\n'
             'Dùng để sửa các lỗi kiểu "lô cồ" (đúng ra là "local") hay '
             '"bê đét" ("PDF"): thêm chính từ đúng vào đây.\n'
             'PHẢI VIẾT THÀNH VĂN XUÔI. Viết kiểu liệt kê ("Nội dung thường '
             'gặp: a, b, c") đã gây sự cố thật hai lần: model tiếp nối danh '
             'sách đang dở, nhả ngược prompt ra rồi lặp hàng chục lần giữa '
             'biên bản.\n'
             'Để trống nếu không muốn mồi gì.',
        config_parameter='aidt_meeting.asr_prompt')

    # Chỉ còn TÊN MODEL. Địa chỉ dịch vụ tóm tắt nằm ở biến môi trường
    # LLM_URL của worker (docker-compose.ai.yml) vì worker gọi API native
    # của Ollama (/api/chat), không phải đường /v1 tương thích OpenAI như
    # bản cũ — giữ một ô URL ở đây chỉ tạo ra giá trị không ai đọc.
    aidt_meeting_llm_model = fields.Char(
        string='Model tóm tắt',
        help='Phải khớp NGUYÊN VĂN tag của Ollama, ví dụ '
             '"gemma3:12b-it-qat". Lệch một ký tự là lỗi 404 và cuộc họp '
             'chuyển sang trạng thái Lỗi.',
        config_parameter='aidt_meeting.llm_model')

    aidt_meeting_max_secrecy = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật tối đa được ghi âm',
        config_parameter='aidt_meeting.max_secrecy')
    aidt_meeting_audio_retention_days = fields.Integer(
        string='Giữ audio (ngày)',
        help='0 = xoá ngay sau khi bóc băng xong.',
        config_parameter='aidt_meeting.audio_retention_days')
