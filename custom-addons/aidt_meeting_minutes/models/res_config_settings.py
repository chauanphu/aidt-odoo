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
