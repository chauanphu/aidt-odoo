import json
import logging
import urllib.error
import urllib.request
import uuid

from odoo import api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 300


class AsrError(RuntimeError):
    """Không gọi được dịch vụ bóc băng, hoặc dịch vụ trả cấu trúc lạ."""


class AidtMeetingAsrClient(models.AbstractModel):
    _name = 'aidt.meeting.asr.client'
    _description = 'Client dịch vụ bóc băng'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_meeting.{key}', default)

    @api.model
    def _build_multipart(self, raw, filename, model):
        """Dựng thân multipart/form-data thủ công.

        Endpoint /audio/transcriptions theo chuẩn OpenAI nhận multipart chứ
        không phải JSON, mà stdlib không có bộ mã hoá multipart — nên phải
        tự ghép. Trả (content_type, body_bytes).
        """
        boundary = uuid.uuid4().hex
        crlf = b'\r\n'
        parts = []
        for name, value in (('model', model), ('response_format', 'verbose_json')):
            parts += [
                f'--{boundary}'.encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b'', value.encode('utf-8'),
            ]
        parts += [
            f'--{boundary}'.encode(),
            (f'Content-Disposition: form-data; name="file"; '
             f'filename="{filename}"').encode(),
            b'Content-Type: audio/mpeg',
            b'', raw,
            f'--{boundary}--'.encode(), b'',
        ]
        return (f'multipart/form-data; boundary={boundary}',
                crlf.join(parts))

    @api.model
    def _headers(self, content_type):
        headers = {'Content-Type': content_type}
        api_key = (self._config('asr_api_key') or '').strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        return headers

    @api.model
    def _transcribe(self, raw, filename):
        """bytes -> list[{'start_ms', 'end_ms', 'text'}].

        `end_ms` có thể là None khi dịch vụ không trả mốc thời gian; bên gọi
        phải coi đoạn đó phủ trọn chunk.
        """
        base = (self._config('asr_url') or '').rstrip('/')
        url = f'{base}/audio/transcriptions'
        model = self._config('asr_model') or ''
        content_type, body = self._build_multipart(raw, filename, model)
        req = urllib.request.Request(
            url, data=body, headers=self._headers(content_type))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise AsrError(f'gọi bóc băng thất bại: {exc}') from exc
        return self._parse(data)

    @api.model
    def _parse(self, data):
        if not isinstance(data, dict):
            raise AsrError(f'bóc băng trả cấu trúc lạ: {data!r}')
        segments = data.get('segments')
        if isinstance(segments, list) and segments:
            parsed = []
            for seg in segments:
                try:
                    parsed.append({
                        'start_ms': int(float(seg['start']) * 1000),
                        'end_ms': int(float(seg['end']) * 1000),
                        'text': (seg.get('text') or '').strip(),
                    })
                except (KeyError, TypeError, ValueError) as exc:
                    raise AsrError(
                        f'segment thiếu mốc thời gian: {seg!r}') from exc
            return [p for p in parsed if p['text']]
        text = data.get('text')
        if text is None:
            raise AsrError(f'bóc băng không trả text: {data!r}')
        text = text.strip()
        if not text:
            return []
        # Không có segment: phủ trọn chunk. end_ms=None để bên gọi tự lấy
        # duration của chunk làm biên.
        return [{'start_ms': 0, 'end_ms': None, 'text': text}]
