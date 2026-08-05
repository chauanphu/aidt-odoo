import json
import logging
import urllib.error
import urllib.request
import uuid

from odoo import api, models

_logger = logging.getLogger(__name__)

TIMEOUT = 300

# Các giá trị `response_format` mà `_parse()` đọc được.
#
# KHÔNG có 'text' trong danh sách: `response_format=text` trả về thân HTTP là
# chữ thuần chứ không phải JSON, nên `json.loads()` ở `_transcribe()` sẽ ném
# ValueError -> AsrError -> đốt hết lượt retry. Muốn thêm định dạng mới thì
# phải sửa `_parse()` trước, không phải chỉ nới danh sách này.
RESPONSE_FORMATS = ('json', 'verbose_json')

# MẶC ĐỊNH là 'json', KHÔNG phải 'verbose_json'. Xem `_response_format`.
DEFAULT_RESPONSE_FORMAT = 'json'

# Chữ ký lỗi 500 mà vLLM ném ở `_get_verbose_segments` (IndexError trên
# tokens_with_start[-2], vLLM bọc lại thành 'tuple index out of range').
#
# NAY ĐÃ BIẾT ĐÂY LÀ TRIỆU CHỨNG, KHÔNG PHẢI MỘT HIỆN TƯỢNG RIÊNG. Nó cùng
# một gốc rễ với việc bản bóc băng luôn rỗng (xem `_response_format`): hỏi
# mốc thời gian ở một model được tinh chỉnh KHÔNG kèm token mốc thời gian
# (`vinai/PhoWhisper-large`). Model sinh vài token đặc biệt rồi EOS ngay, và
# `_get_verbose_segments` của vLLM đọc chuỗi token rỗng đó rồi ngã. Vì vậy
# "audio quá ít nội dung" chỉ là điều kiện làm nó ngã SỚM hơn, không phải
# nguyên nhân. Đã tái hiện thật trên PhoWhisper-large + vLLM 0.26.0 ngày
# 05/08/2026 bằng một tông đơn 2 giây (RMS cao — qua lọt cổng RMS_FLOOR của
# recorder_service.js, vốn chỉ chặn im lặng theo độ to chứ không chặn nội
# dung suy biến).
#
# GIỮ NGUYÊN phần xử lý phòng thủ bên dưới: nó vẫn đúng, và vẫn cần cho bất
# kỳ ai đặt `asr_response_format = verbose_json` — dịch vụ bên thứ ba
# (OpenAI, Deepgram…) hoặc một checkpoint Whisper gốc CÓ token mốc thời gian
# đều là cấu hình hợp lệ, và ở đó lỗi này lại đúng nghĩa "chunk không có nội
# dung để tách segment".
_DEGENERATE_SEGMENT_CRASH = 'tuple index out of range'


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
    def _part_content_type(self, filename):
        """Kiểu MIME của phần `file`, suy từ ĐUÔI TỆP.

        Trước đây chỗ này ghi cứng `audio/mpeg` cho mọi payload. Đường đi
        thật của module chỉ gửi MP3 nên nó không gây lỗi, nhưng nó biến mọi
        phép thử với định dạng khác thành phép thử SAI: khi chẩn đoán sự cố
        ASR ngày 05/08/2026, một lượt gửi lại bằng WAV — dùng để loại trừ
        giả thuyết "lỗi ở khâu giải mã MP3" — thực ra đã được gắn nhãn
        `audio/mpeg`, nên nó không chứng minh được điều nó định chứng minh.
        Suy từ đuôi tệp để công cụ chẩn đoán nói thật.
        """
        return {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'webm': 'audio/webm',
            'm4a': 'audio/mp4',
            'flac': 'audio/flac',
        }.get(filename.rsplit('.', 1)[-1].lower(), 'application/octet-stream')

    @api.model
    def _response_format(self):
        """`response_format` gửi kèm request, đọc từ CẤU HÌNH.

        ĐÂY LÀ CHỖ TỪNG LÀM CẢ TÍNH NĂNG VÔ DỤNG. Giá trị này trước đây ghi
        cứng `verbose_json` — tức là yêu cầu dịch vụ trả về từng segment kèm
        mốc thời gian. Whisper chỉ làm được điều đó nếu checkpoint được huấn
        luyện KÈM token mốc thời gian; `vinai/PhoWhisper-large` là một bản
        tinh chỉnh KHÔNG có phần đó, nên nó sinh vài token đặc biệt rồi EOS
        ngay và trả về rỗng. Đo thật ngày 05/08/2026 trên đúng một tệp audio
        (mẩu 15.084 giây của một cuộc gọi thật, giọng người thật), cùng một
        gateway vLLM, CHỈ đổi trường này:

            verbose_json -> {"text": "", "segments": []}      (0 chữ)
            json         -> {"text": "nhà trưởng nguyễn ..."} (có chữ)

        Cùng checkpoint đó chạy qua `transformers` thuần trả về 44 token
        tiếng Việt, nên model không hỏng — chỉ là câu hỏi sai.

        VÌ SAO LÀ THAM SỐ CHỨ KHÔNG PHẢI ĐỔI HẰNG SỐ: tầng AI được thiết kế
        để thay bằng dịch vụ bên thứ ba (OpenAI, Deepgram…), và những dịch
        vụ ĐÓ trả `verbose_json` đúng nghĩa — mốc thời gian theo từng lượt
        nói, mịn hơn hẳn thứ ta tự suy ra được. Ghi cứng `json` sẽ vứt bỏ
        khả năng đó đúng như ghi cứng `verbose_json` đã vứt bỏ khả năng dùng
        PhoWhisper.

        Với `json`, mốc thời gian đến từ `offset_ms`/`duration_ms` do CHÍNH
        recorder đo (xem `meeting_chunk._write_segments`): độ mịn chỉ bằng
        một mẩu (~15 giây) nhưng đáng tin hơn hẳn mốc mà PhoWhisper từng
        trả về.

        Giá trị lạ (admin gõ tay ở Tham số hệ thống) lùi về `json` kèm cảnh
        báo, không chuyển tiếp nguyên văn: `_parse()` chỉ đọc được hai khuôn
        dạng trong `RESPONSE_FORMATS`, nên gửi đi một giá trị thứ ba là chọn
        giữa 400 và một thân trả về không phân tích được — trong khi `json`
        chạy được với MỌI model.
        """
        value = (self._config('asr_response_format') or '').strip()
        if value in RESPONSE_FORMATS:
            return value
        if value:
            _logger.warning(
                'aidt_meeting.asr_response_format không hợp lệ (%r); dùng %r. '
                'Chỉ nhận: %s.',
                value, DEFAULT_RESPONSE_FORMAT, ', '.join(RESPONSE_FORMATS))
        return DEFAULT_RESPONSE_FORMAT

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
        for name, value in (('model', model),
                            ('response_format', self._response_format())):
            parts += [
                f'--{boundary}'.encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b'', value.encode('utf-8'),
            ]
        parts += [
            f'--{boundary}'.encode(),
            (f'Content-Disposition: form-data; name="file"; '
             f'filename="{filename}"').encode(),
            f'Content-Type: {self._part_content_type(filename)}'.encode(),
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
        except urllib.error.HTTPError as exc:
            if self._is_degenerate_segment_crash(exc):
                # Không phải lỗi: chunk không có nội dung để tách segment.
                # Coi như im lặng hợp lệ, giống nhánh 'text' rỗng ở _parse.
                return []
            raise AsrError(f'gọi bóc băng thất bại: {exc}') from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise AsrError(f'gọi bóc băng thất bại: {exc}') from exc
        return self._parse(data)

    @api.model
    def _is_degenerate_segment_crash(self, exc):
        """True nếu đúng lỗi 500 của vLLM tả ở _DEGENERATE_SEGMENT_CRASH.

        Không khớp signature -> lỗi tầng khác (mất kết nối, service sập vì
        lý do khác), phải ném AsrError thật để _mark_retry còn thử lại.
        """
        if exc.code != 500:
            return False
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except (ValueError, OSError, UnicodeDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        message = (payload.get('error') or {}).get('message')
        return message == _DEGENERATE_SEGMENT_CRASH

    @api.model
    def _parse(self, data):
        if not isinstance(data, dict):
            raise AsrError(f'bóc băng trả cấu trúc lạ: {data!r}')
        segments = data.get('segments')
        if isinstance(segments, list) and segments:
            parsed = []
            for seg in segments:
                try:
                    # Dùng seg['text'] (không phải .get) — thiếu khoá 'text'
                    # là lỗi cấu trúc, phải ném lỗi to chứ không âm thầm coi
                    # như im lặng. Chuỗi rỗng SAU KHI strip mới là im lặng
                    # hợp lệ, được lọc bỏ không lỗi ở dưới.
                    parsed.append({
                        'start_ms': round(float(seg['start']) * 1000),
                        'end_ms': round(float(seg['end']) * 1000),
                        'text': seg['text'].strip(),
                    })
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    raise AsrError(
                        f'segment thiếu mốc thời gian hoặc text: {seg!r}'
                    ) from exc
            return [p for p in parsed if p['text']]
        text = data.get('text')
        if text is None:
            raise AsrError(f'bóc băng không trả text: {data!r}')
        text = text.strip()
        if not text:
            return []
        # Không có segment: phủ trọn chunk. end_ms=None để bên gọi tự lấy
        # duration của chunk làm biên (`meeting_chunk._write_segments`).
        # Với `response_format=json` — mặc định kể từ 05/08/2026 — đây là
        # ĐƯỜNG ĐI CHÍNH chứ không còn là đường lùi: mỗi mẩu cho đúng một
        # đoạn phủ trọn nó, mốc thời gian lấy từ `offset_ms`/`duration_ms`
        # do recorder đo.
        return [{'start_ms': 0, 'end_ms': None, 'text': text}]
