import json
import logging
import urllib.error
import urllib.request

from odoo import _, api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 300
# Cửa sổ map-reduce, tính theo dòng transcript. Giữ nhỏ có chủ đích: KV cache
# còn khoảng 2.5 GB sau khi embedding + ASR + trọng số LLM đã chiếm chỗ.
WINDOW_LINES = 120

SYSTEM_PROMPT = (
    'Bạn là thư ký cuộc họp. Tóm tắt bằng tiếng Việt, ngắn gọn, theo ba mục: '
    'NỘI DUNG CHÍNH, KẾT LUẬN, VIỆC CẦN LÀM. Chỉ dùng thông tin có trong bản '
    'bóc băng, không suy diễn thêm. Nếu bản bóc băng có đánh dấu thiếu âm '
    'thanh, nêu rõ là nội dung có thể không đầy đủ.'
)


class SummaryError(RuntimeError):
    """Không gọi được dịch vụ tóm tắt, hoặc dịch vụ trả cấu trúc lạ."""


class AidtMeetingSummaryClient(models.AbstractModel):
    _name = 'aidt.meeting.summary.client'
    _description = 'Client dịch vụ tóm tắt'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _chat(self, prompt):
        base = (self._config('llm_url') or '').rstrip('/')
        url = f'{base}/chat/completions'
        body = {
            'model': self._config('llm_model') or '',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
        }
        headers = {'Content-Type': 'application/json'}
        api_key = (self._config('llm_api_key') or '').strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        req = urllib.request.Request(
            url, data=json.dumps(body).encode('utf-8'), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SummaryError(f'gọi tóm tắt thất bại: {exc}') from exc
        try:
            return data['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            # Cắt ngắn: thông điệp này rơi vào `summary_error`, một
            # `fields.Text` hiển thị thẳng trên form — không được để nguyên
            # cả payload vài KB của dịch vụ lạc vào giao diện người dùng.
            raise SummaryError(
                f'tóm tắt trả cấu trúc lạ: {repr(data)[:500]}') from exc

    @api.model
    def _summarize(self, transcript):
        """Map-reduce: tóm tắt từng cửa sổ rồi tóm tắt các bản tóm tắt.

        Họp hai tiếng chắc chắn vượt cửa sổ context, nên đây không phải
        trường hợp biên mà là đường đi mặc định của mọi cuộc họp dài.
        """
        text = (transcript or '').strip()
        if not text:
            return ''
        lines = text.split('\n')
        if len(lines) <= WINDOW_LINES:
            return self._chat(text)
        partials = []
        for start in range(0, len(lines), WINDOW_LINES):
            window = '\n'.join(lines[start:start + WINDOW_LINES])
            partials.append(self._chat(window))
        joined = '\n\n'.join(partials)
        return self._chat(
            _('Dưới đây là các bản tóm tắt từng phần của cùng một cuộc họp. '
              'Hợp nhất thành một bản tóm tắt duy nhất, không lặp ý:\n\n%s',
              joined))
