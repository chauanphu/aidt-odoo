import json
import logging
import re
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

FINAL_JSON_PROMPT = """Bạn là thư ký cuộc họp. Hãy tổng hợp các phần tóm tắt sau đây và xuất kết quả BẮT BUỘC ở định dạng JSON chính xác như cấu trúc sau:
{
  "title": "Tên cuộc họp",
  "overview": "Tóm tắt tổng quan",
  "key_points": [{"content": "Ý chính", "timestamp": "00:00:00"}],
  "decisions": [{"content": "Quyết định", "timestamp": "00:00:00"}],
  "action_items": [{"task": "Công việc", "owner": "Người phụ trách", "deadline": "Hạn chót", "priority": "high/medium/low", "timestamp": "00:00:00"}],
  "risks": [{"content": "Rủi ro"}],
  "meeting_minutes": "Biên bản hoàn chỉnh"
}
Không thêm văn bản nào ngoài JSON."""


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
    def _chat(self, prompt, system_prompt=SYSTEM_PROMPT):
        base = (self._config('llm_url') or '').rstrip('/')
        url = f'{base}/chat/completions'
        body = {
            'model': self._config('llm_model') or '',
            'messages': [
                {'role': 'system', 'content': system_prompt},
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
            return {}
        lines = text.split('\n')
        if len(lines) <= WINDOW_LINES:
            final_text = text
        else:
            partials = []
            for start in range(0, len(lines), WINDOW_LINES):
                window = '\n'.join(lines[start:start + WINDOW_LINES])
                partials.append(self._chat(window))
            final_text = '\n\n'.join(partials)

        prompt = _('Dưới đây là các phần của bản bóc băng. Hãy tóm tắt thành JSON:\n\n%s', final_text)

        for attempt in range(3):
            try:
                response = self._chat(prompt, system_prompt=FINAL_JSON_PROMPT)
                # Strip markdown blocks
                json_str = re.sub(r'^```(?:json)?\s*', '', response, flags=re.MULTILINE)
                json_str = re.sub(r'```$', '', json_str, flags=re.MULTILINE).strip()
                return json.loads(json_str)
            except json.JSONDecodeError as exc:
                _logger.warning("Lỗi parse JSON từ LLM (lần %s): %s\nResponse: %s", attempt + 1, exc, response)
                if attempt == 2:
                    raise SummaryError(f'Tóm tắt trả về JSON hỏng sau 3 lần thử: {repr(response)[:500]}') from exc
        return {}
