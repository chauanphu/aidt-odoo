from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Endpoint là DỮ LIỆU chứ không phải hằng số trong code: tầng AI nằm ở
    # docker-compose.ai.yml riêng và phải thay được bằng dịch vụ bên thứ ba
    # bất cứ lúc nào mà không sửa một dòng Python nào.
    aidt_meeting_asr_url = fields.Char(
        string='URL dịch vụ bóc băng',
        config_parameter='aidt_meeting.asr_url')
    aidt_meeting_asr_model = fields.Char(
        string='Model bóc băng',
        config_parameter='aidt_meeting.asr_model')
    # API key rỗng với dịch vụ nội bộ. Có trường này từ đầu là điều kiện để
    # chuyển sang bên thứ ba mà không phải sửa code — thiếu nó thì lời hứa
    # "thay được bất cứ lúc nào" không thực hiện được.
    aidt_meeting_asr_api_key = fields.Char(
        string='API key dịch vụ bóc băng',
        config_parameter='aidt_meeting.asr_api_key')
    # Selection chứ không phải Char: `_parse()` chỉ đọc được hai khuôn dạng
    # này, nên một ô nhập tự do chỉ tạo thêm cách gõ sai. Mặc định 'json' —
    # xem models/asr_client.py::_response_format.
    aidt_meeting_asr_response_format = fields.Selection(
        [('json', 'json — một đoạn cho mỗi mẩu (mọi model đều chạy)'),
         ('verbose_json',
          'verbose_json — mốc thời gian theo lượt nói (cần model có token '
          'mốc thời gian)')],
        string='Khuôn dạng kết quả bóc băng',
        help='json: dịch vụ chỉ trả về chữ, mốc thời gian lấy từ vị trí và '
             'độ dài của chính mẩu audio (độ mịn khoảng 15 giây). Chạy được '
             'với mọi model, kể cả vinai/PhoWhisper-large.\n'
             'verbose_json: dịch vụ trả về mốc thời gian theo từng lượt nói '
             '— mịn hơn, nhưng CHỈ dùng được với model được huấn luyện kèm '
             'token mốc thời gian (PhoWhisper KHÔNG có; đặt giá trị này với '
             'PhoWhisper sẽ cho bản bóc băng RỖNG). Phù hợp khi trỏ sang '
             'dịch vụ bên thứ ba như OpenAI Whisper.',
        config_parameter='aidt_meeting.asr_response_format')

    # Ba tham số GIẢI MÃ dưới đây quyết định chất lượng bản bóc băng nhiều
    # hơn hẳn URL/API key. Để chúng ở UI chứ không ghi cứng vì việc tinh
    # chỉnh vốn từ là công việc lặp đi lặp lại của người vận hành, không
    # phải việc phải sửa code rồi deploy lại.
    aidt_meeting_asr_language = fields.Char(
        string='Ngôn ngữ bóc băng',
        help='Mã ngôn ngữ ISO gửi cho dịch vụ, ví dụ "vi" cho tiếng Việt.\n'
             'Để TRỐNG nghĩa là để dịch vụ tự nhận dạng — chỉ nên dùng cho '
             'cuộc họp song ngữ. Whisper tự nhận dạng lại cho TỪNG mẩu audio '
             '(khoảng 15 giây), nên bỏ trống có thể làm một cuộc họp tiếng '
             'Việt bị bóc thành tiếng Anh ở vài đoạn giữa chừng mà không có '
             'cảnh báo nào.',
        config_parameter='aidt_meeting.asr_language')
    # Char chứ KHÔNG phải Text, dù đây là một đoạn văn. `res.config.settings.
    # execute()` gọi `_get_classified_fields()`, và hàm đó ném thẳng
    # Exception cho mọi kiểu ngoài boolean/integer/float/char/selection/
    # many2one/datetime. Với Text thì KHÔNG chỉ trường này hỏng — cả trang
    # Cấu hình không lưu được gì, kể cả URL dịch vụ, vì lỗi ném ra trước khi
    # phân loại xong. Đã dính thật khi làm tính năng này (05/08/2026): bốn
    # test settings đổ cùng lúc với 'must have type ...'. Char giới hạn 400
    # ký tự ở `_prompt()` nên một dòng là đủ.
    aidt_meeting_asr_prompt = fields.Char(
        string='Mồi vốn từ (prompt)',
        help='Một đoạn văn ngắn chứa các từ hay bị bóc sai. Dịch vụ coi đoạn '
             'này như văn bản đứng ngay trước audio, nên nó vừa gợi TỪ vừa '
             'gợi VĂN PHONG — hãy viết hoa và chấm câu đầy đủ để bản bóc '
             'băng cũng có hoa và dấu câu.\n'
             'Dùng để sửa các lỗi kiểu "lô cồ" (đúng ra là "local") hay '
             '"con ngôi đồ" ("con model"): thêm chính từ đúng vào đây.\n'
             'PHẢI NGẮN. Chỉ 400 ký tự đầu được gửi đi; phần thừa bị cắt bỏ. '
             'Đoạn quá dài còn làm dịch vụ TỪ CHỐI cả yêu cầu (giới hạn ngữ '
             'cảnh), khiến mẩu đó bóc băng lỗi.\n'
             'Để trống nếu không muốn mồi gì.',
        config_parameter='aidt_meeting.asr_prompt')
    aidt_meeting_asr_temperature = fields.Char(
        string='Temperature bóc băng',
        help='Số trong khoảng 0 đến 2. Mặc định 0 = dịch vụ luôn chọn phương '
             'án chắc chắn nhất, và bóc lại cùng một đoạn audio sẽ ra đúng '
             'cùng một kết quả — cần thiết để so sánh được các lần chỉnh cấu '
             'hình với nhau.\n'
             'Chỉ nâng lên khi gặp đoạn bị lặp đi lặp lại một cụm từ. Giá '
             'trị không phải số hoặc nằm ngoài khoảng cho phép sẽ bị bỏ qua '
             'và tự lùi về 0.',
        config_parameter='aidt_meeting.asr_temperature')

    aidt_meeting_llm_url = fields.Char(
        string='URL dịch vụ tóm tắt',
        config_parameter='aidt_meeting.llm_url')
    aidt_meeting_llm_model = fields.Char(
        string='Model tóm tắt',
        config_parameter='aidt_meeting.llm_model')
    aidt_meeting_llm_api_key = fields.Char(
        string='API key dịch vụ tóm tắt',
        config_parameter='aidt_meeting.llm_api_key')

    aidt_meeting_max_secrecy = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật tối đa được ghi âm',
        config_parameter='aidt_meeting.max_secrecy')
    aidt_meeting_audio_retention_days = fields.Integer(
        string='Giữ audio (ngày)',
        help='0 = xoá ngay sau khi bóc băng xong.',
        config_parameter='aidt_meeting.audio_retention_days')
