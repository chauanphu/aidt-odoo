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
