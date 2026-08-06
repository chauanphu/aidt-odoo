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

# Trần KÝ TỰ cho `prompt`. Xem `_prompt()` để hiểu vì sao đây là bắt buộc chứ
# không phải một phép làm đẹp — prompt quá dài làm HỎNG request, không phải
# làm nó kém đi.
#
# Vì sao 400: Whisper giới hạn `initial_prompt` ở 224 token (nửa ngữ cảnh
# 448 token; bản gốc openai/whisper chỉ giữ `n_ctx // 2 - 1` = 223 token
# CUỐI rồi vứt phần đầu). Container Odoo KHÔNG có tokenizer của Whisper nên
# ta không đếm token được — phải quy đổi ra ký tự. Đo thật ngày 05/08/2026
# bằng tokenizer `openai/whisper-large-v3` chạy trong container `aidt-asr`,
# trên ba mẫu tiếng Việt thật (câu họp hành, danh sách thuật ngữ, chuỗi tên
# riêng + tên cơ quan): 2.18 – 2.45 ký tự/token. Lấy sàn 2.18 thì 400 ký tự
# ≈ 183 token, còn dư dưới trần 224.
#
# Đây là quy đổi THỰC NGHIỆM chứ không phải bảo đảm toán học: một chuỗi bịa
# toàn dấu phụ hiếm ('ựỡễỷữ…') đo được 0.81 ký tự/token, tức 400 ký tự có
# thể thành ~490 token. Chấp nhận: ô cấu hình này để gõ vốn từ tiếng Việt
# bình thường, và ngay cả trường hợp bệnh lý đó cũng chỉ làm ASR trả 400 —
# tức mẩu đó lỗi và thấy được — chứ không làm hỏng dữ liệu âm thầm.
ASR_PROMPT_MAX_CHARS = 400

# Prompt MẶC ĐỊNH cố ý KHÔNG có bản sao ở đây. Nó chỉ nằm ở
# data/ir_config_parameter.xml (`param_asr_prompt`) — một đoạn văn tiếng
# Việt dài ~300 ký tự để ở hai nơi thì chắc chắn sẽ lệch nhau, và bản trong
# code sẽ là bản KHÔNG chạy (`_prompt()` chỉ đọc cấu hình). Rỗng ở đây có
# nghĩa thật là "không mồi gì cả", nên không có mặc định dự phòng ở tầng
# code như `_response_format`.
#
# Vốn từ trong prompt đó nhắm thẳng vào các từ đã bóc SAI thật trong bản ghi
# 1140 ngày 05/08/2026 (bằng chứng đầy đủ ở docs/superpowers/specs/
# 2026-08-05-asr-quality-preprocessing-design.md §1):
#   `lô cồ`               -> local
#   `con ngôi đồ`/`mua đồ` -> con model
#   `ghim`/`găm`          -> ghi âm
#   `hỗn hợp`             -> cuộc họp
#   `vương bị trần quyền`  -> vấn đề phân quyền
# Âm thanh đã được NGHE đúng — chỉ có TỪ là sai, tức lỗi mô hình ngôn ngữ,
# và prompt là cần gạt duy nhất sửa đúng tầng đó mà không huấn luyện lại.

# Trần `temperature` mà dịch vụ chấp nhận. Đo thật 05/08/2026 trên gateway
# vLLM đang chạy: `temperature=5` -> HTTP 400 'temperature must be in
# [0, 2]'; `temperature=-1` -> HTTP 400 'temperature must be non-negative'.
# Tức trường này ĐƯỢC PHÂN TÍCH và KIỂM TRA ở server, không phải bị bỏ qua.
ASR_TEMPERATURE_MAX = 2.0

# 0 = giải mã tham lam, không lấy mẫu ngẫu nhiên. Với biên bản họp hành
# chính thì tái lập được quan trọng hơn văn phong trôi chảy.
DEFAULT_ASR_TEMPERATURE = 0.0

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
    def _language(self):
        """`language` gửi kèm request, đọc từ CẤU HÌNH. '' = không gửi.

        VÌ SAO PHẢI GỬI. Whisper là model đa ngôn ngữ: không có `language`
        nó TỰ ĐOÁN ngôn ngữ, và nó đoán lại cho TỪNG cửa sổ 30 giây chứ
        không phải một lần cho cả cuộc họp. Vì ta cắt mẩu 15 giây và gửi
        từng mẩu thành một request riêng, mỗi mẩu là một lần đoán độc lập —
        một cuộc họp có thể lật sang tiếng Anh ở giữa chừng mà không có gì
        báo. Đã quan sát thật `vinai/PhoWhisper-large` bóc một tệp thử
        tiếng Anh ra tiếng Anh, tức lớp tự đoán này CÓ hoạt động và CÓ lật.

        Đo thật trên gateway vLLM ngày 05/08/2026, cùng một tệp audio 2
        giây, cùng model, CHỈ đổi trường này:

            (không gửi language) -> {"text": "n."}
            language=en          -> {"text": " (tone ringing)"}

        Nên đây không phải trường trang trí: nó đổi kết quả giải mã thật.
        Giá trị sai bị server bắt: `language=khong-phai-ma` -> HTTP 400 kèm
        danh sách mã hợp lệ.

        VÌ SAO RỖNG = BỎ HẲN TRƯỜNG, KHÁC `_response_format`. Ở
        `_response_format`, giá trị rỗng KHÔNG có nghĩa gì cả — `_parse()`
        bắt buộc phải biết trước khuôn dạng — nên code phải tự lấp một mặc
        định. Ở đây rỗng CÓ nghĩa thật và có ích: "để dịch vụ tự nhận
        dạng". Đó là đường thoát duy nhất cho một cuộc họp song ngữ, hoặc
        cho ai trỏ sang dịch vụ bên thứ ba không nhận mã ISO của Whisper.
        Ép 'vi' trở lại ở tầng code sẽ xoá mất lựa chọn đó. Mặc định XUẤT
        XƯỞNG 'vi' nằm ở data/ir_config_parameter.xml.
        """
        return (self._config('asr_language') or '').strip()

    @api.model
    def _prompt(self):
        """`prompt` (initial_prompt của Whisper) gửi kèm request. '' = không gửi.

        Đây là cần gạt SỬA TỪ SAI — xem `DEFAULT_ASR_PROMPT`. Whisper coi
        prompt như văn bản đứng ngay trước đoạn audio, nên nó vừa mồi vốn
        từ vừa mồi văn phong.

        Đã đo thật ngày 05/08/2026 rằng nó ĐỔI kết quả giải mã, cùng tệp
        audio, cùng model, cùng `language=en`, chỉ thêm/bớt trường này:

            (không prompt)                              -> " (tone ringing)"
            prompt='A telephone is ringing in an empty office.' -> " [phone ringing]"

        PHẢI CẮT NGẮN, VÀ ĐÂY LÀ LÝ DO CỨNG. Trước hết là trần 224 token
        của `initial_prompt` (nửa ngữ cảnh 448) — prompt được nhồi vào cùng
        cửa sổ ngữ cảnh với ĐẦU RA, nên prompt càng dài thì chỗ cho chữ bóc
        ra càng ít. Nhưng cái nguy hơn là chuyện đã đo được: gateway KHÔNG
        tự cắt bớt, nó TỪ CHỐI CẢ REQUEST. Prompt 1000 ký tự tiếng Việt ->
        HTTP 400 "This model's maximum context length is 448 tokens". Qua
        `_transcribe` thì 400 đó thành AsrError -> đốt sạch lượt retry ->
        mẩu hỏng. Nghĩa là một quản trị viên dán nguyên bảng thuật ngữ vào ô
        cấu hình sẽ làm CHẾT toàn bộ việc bóc băng, chứ không phải làm nó
        kém đi. Cắt ở tầng này biến sự cố đó thành không thể xảy ra.

        Đo ranh giới thật (tiếng Việt, 05/08/2026): 400 / 500 / 600 / 800 ký
        tự -> HTTP 200; 1000 ký tự -> HTTP 400. `ASR_PROMPT_MAX_CHARS = 400`
        nằm dưới ngưỡng gãy với biên rộng, và cũng dưới trần 224 token.

        Cắt ở ĐẦU (giữ phần đầu) là có chủ ý: bản gốc openai/whisper cắt
        ngược lại — nó giữ 223 token CUỐI — nên để mặc thì phần bị vứt là
        câu mở đầu định hình văn phong. Ta chọn phần nào sống sót, không
        phải model chọn hộ.
        """
        return (self._config('asr_prompt') or '').strip()[:ASR_PROMPT_MAX_CHARS]

    @api.model
    def _temperature(self):
        """`temperature` gửi kèm request, dạng chuỗi đã chuẩn hoá.

        0 = giải mã tham lam. Whisper mặc định có cơ chế lùi: gặp mẩu khó
        thì nâng dần temperature để thoát vòng lặp. Với biên bản họp hành
        chính, đặt 0 làm đầu ra tái lập được — chạy lại cùng audio phải ra
        cùng chữ — đó là điều kiện để `action_retranscribe` so sánh được
        các lần chỉnh cấu hình với nhau. Nhưng vẫn là THAM SỐ: người bị mẩu
        lặp chữ nặng có thể muốn nới lên.

        LUÔN GỬI, khác `language`/`prompt`: rỗng ở hai trường kia có nghĩa
        thật ("tự nhận dạng" / "không mồi"), còn rỗng ở đây không có nghĩa
        gì — nó chỉ có nghĩa là "dùng mặc định của dịch vụ", mà mặc định đó
        khác nhau tuỳ dịch vụ. Gửi 0 tường minh thì hành vi giống nhau ở
        mọi backend.

        Giá trị lạ lùi về 0 kèm cảnh báo, đúng như `_response_format`: đây
        là ô admin gõ tay ở Tham số hệ thống, và server KHÔNG bỏ qua giá trị
        hỏng mà trả 400 (đo thật 05/08/2026: `temperature=5` -> 400
        'temperature must be in [0, 2]'; `temperature=-1` -> 400
        'temperature must be non-negative'), tức chuyển tiếp nguyên văn một
        giá trị sai sẽ làm hỏng MỌI lần bóc băng cho tới khi có người phát
        hiện. Chặn cả giá trị ngoài [0, 2] chứ không chỉ chặn chữ: '1e9' là
        số hợp lệ với float() nhưng vẫn cho 400.
        """
        raw = (self._config('asr_temperature') or '').strip()
        value = DEFAULT_ASR_TEMPERATURE
        if raw:
            try:
                parsed = float(raw)
            except ValueError:
                parsed = None
            if parsed is None or not 0.0 <= parsed <= ASR_TEMPERATURE_MAX:
                _logger.warning(
                    'aidt_meeting.asr_temperature không hợp lệ (%r); dùng %s. '
                    'Cần một số trong khoảng [0, %s].',
                    raw, DEFAULT_ASR_TEMPERATURE, ASR_TEMPERATURE_MAX)
            else:
                value = parsed
        # '%g' để 0.0 đi ra thành '0' chứ không phải '0.0' — giữ đúng giá
        # trị mà file dữ liệu ship sẵn, và dễ đọc khi soi request.
        return '%g' % value

    @api.model
    def _build_multipart(self, raw, filename, model):
        """Dựng thân multipart/form-data thủ công.

        Endpoint /audio/transcriptions theo chuẩn OpenAI nhận multipart chứ
        không phải JSON, mà stdlib không có bộ mã hoá multipart — nên phải
        tự ghép. Trả (content_type, body_bytes).

        CẢNH BÁO khi thêm trường mới ở đây: gateway vLLM BỎ QUA IM LẶNG mọi
        trường form nó không biết. Đo thật 05/08/2026 — bốn tên bịa
        (`khong_ton_tai`, `foo`, `initial_prompt`, `temperatur`) đều trả
        HTTP 200 với kết quả y hệt baseline, KHÔNG có 400 nào. Nên "gửi đi
        mà không lỗi" KHÔNG chứng minh được là trường đó có tác dụng; phải
        chứng minh bằng kết quả giải mã đổi, hoặc bằng việc server bắt lỗi
        giá trị sai. Cả ba trường dưới đây đều đã có bằng chứng loại đó —
        xem docstring từng resolver. Lưu ý luôn: tên đúng là `prompt`, chứ
        `initial_prompt` (tên tham số trong thư viện whisper gốc) là một
        trong bốn tên bị nuốt im lặng.
        """
        boundary = uuid.uuid4().hex
        crlf = b'\r\n'
        fields = [('model', model),
                  ('response_format', self._response_format())]
        # Rỗng -> bỏ HẲN trường, không gửi chuỗi rỗng: `language=''` sẽ là
        # một mã ngôn ngữ không hợp lệ (HTTP 400), không phải "tự nhận
        # dạng". Vắng mặt mới là cách nói "tự nhận dạng".
        language = self._language()
        if language:
            fields.append(('language', language))
        prompt = self._prompt()
        if prompt:
            fields.append(('prompt', prompt))
        fields.append(('temperature', self._temperature()))
        parts = []
        for name, value in fields:
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
