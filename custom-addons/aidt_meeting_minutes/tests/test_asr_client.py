import json
import urllib.error
import io
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.aidt_meeting_minutes.models.asr_client import AsrError


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AsrCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['aidt.meeting.asr.client']
        cls.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_url', 'http://asr:8002/v1/')

    def _call(self, payload, api_key=''):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_api_key', api_key)
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['url'] = req.full_url
            captured['headers'] = dict(req.headers)
            captured['body'] = req.data
            return FakeResponse(payload)

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            result = self.client._transcribe(b'AUDIO', 'a.mp3')
        return result, captured


class TestAsrClient(AsrCase):
    def test_ghep_dung_duong_dan_va_bo_gach_cheo_thua(self):
        _, captured = self._call({'text': 'xin chào'})
        self.assertEqual(captured['url'],
                         'http://asr:8002/v1/audio/transcriptions')

    def test_co_api_key_thi_gui_bearer(self):
        _, captured = self._call({'text': 'a'}, api_key='sk-abc')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertEqual(header['authorization'], 'Bearer sk-abc')

    def test_khong_co_api_key_thi_bo_han_header(self):
        """Dịch vụ nội bộ không cần key; gửi 'Bearer ' rỗng làm một số
        gateway trả 401 thay vì bỏ qua."""
        _, captured = self._call({'text': 'a'}, api_key='')
        header = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertNotIn('authorization', header)

    def test_doc_duoc_segment_co_moc_thoi_gian(self):
        payload = {'segments': [
            {'start': 0.0, 'end': 1.5, 'text': 'câu một'},
            {'start': 1.5, 'end': 3.0, 'text': 'câu hai'},
        ]}
        result, _ = self._call(payload)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertEqual(result[1]['end_ms'], 3000)
        self.assertEqual(result[1]['text'], 'câu hai')

    def test_khong_co_segment_thi_lui_ve_mot_doan_duy_nhat(self):
        """Timestamp bên trong Whisper là thứ dễ suy giảm nhất ở một bản
        fine-tune. Thiết kế lấy mốc từ offset của chunk nên vẫn dùng được:
        chỉ cần trả một đoạn phủ trọn chunk."""
        result, _ = self._call({'text': 'toàn bộ nội dung'})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start_ms'], 0)
        self.assertIsNone(result[0]['end_ms'])
        self.assertEqual(result[0]['text'], 'toàn bộ nội dung')

    def test_phan_hoi_la_khong_nem_asr_error(self):
        with self.assertRaises(AsrError):
            self._call({'khong_biet': 1})

    def test_phan_hoi_khong_phai_dict_thi_nem_asr_error(self):
        """Payload cấp cao nhất là mảng (không phải dict) cũng là cấu trúc
        lạ — phải ném AsrError, không được đoán mò."""
        with self.assertRaises(AsrError):
            self._call([1, 2, 3])

    def test_segment_thieu_khoa_text_thi_nem_asr_error(self):
        """Thiếu hẳn khoá 'text' là lỗi cấu trúc — khác với text rỗng sau
        strip (im lặng hợp lệ). Không được âm thầm coi như im lặng rồi lọc
        bỏ, vì như vậy sẽ không phân biệt được với một đoạn thực sự im
        lặng."""
        payload = {'segments': [{'start': 0.0, 'end': 1.0}]}
        with self.assertRaises(AsrError):
            self._call(payload)

    def _call_raising(self, http_error):
        """Giống `_call` nhưng urlopen ném `http_error` thay vì trả kết quả."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_api_key', '')
        with patch('urllib.request.urlopen', side_effect=http_error):
            return self.client._transcribe(b'AUDIO', 'chunk-1.mp3')

    def _http_500(self, body):
        payload = json.dumps(body).encode('utf-8')
        return urllib.error.HTTPError(
            'http://asr:8002/v1/audio/transcriptions', 500,
            'Internal Server Error', {}, io.BytesIO(payload))

    def test_500_tuple_index_out_of_range_tra_ve_rong_khong_nem_loi(self):
        """Chữ ký lỗi cụ thể của vLLM khi audio quá ít nội dung để tách
        segment (đã tái hiện thật trên PhoWhisper-large + vLLM 0.26.0 bằng
        một tông đơn — RMS cao, qua lọt cổng loudness của recorder, nhưng
        nội dung suy biến). Đây không phải lỗi ASR: phải coi như im lặng
        hợp lệ, không đốt hết lượt retry rồi báo lỗi bóc băng cho người
        dùng trong khi sự thật là đoạn đó không có tiếng nói."""
        result = self._call_raising(self._http_500({
            'error': {'message': 'tuple index out of range',
                      'type': 'InternalServerError', 'param': None,
                      'code': 500},
        }))
        self.assertEqual(result, [])

    def test_500_khac_chu_ky_van_nem_asr_error(self):
        """500 vì lý do khác (service sập, OOM, lỗi thật) vẫn phải ném
        AsrError để `_mark_retry` còn thử lại — không được nuốt mọi 500."""
        with self.assertRaises(AsrError):
            self._call_raising(self._http_500({
                'error': {'message': 'CUDA out of memory',
                          'type': 'InternalServerError', 'param': None,
                          'code': 500},
            }))

    def test_500_khong_phai_json_van_nem_asr_error(self):
        with self.assertRaises(AsrError):
            self._call_raising(urllib.error.HTTPError(
                'http://asr:8002/v1/audio/transcriptions', 500,
                'Internal Server Error', {}, io.BytesIO(b'not json')))


class TestResponseFormat(AsrCase):
    """`response_format` là THAM SỐ, không phải hằng số.

    Ghi cứng `verbose_json` là lỗi đã làm cả tính năng vô dụng: nó bắt dịch
    vụ trả segment kèm mốc thời gian, điều mà `vinai/PhoWhisper-large` —
    bản tinh chỉnh KHÔNG có token mốc thời gian — không làm được, nên nó trả
    về RỖNG. Đo thật 05/08/2026 trên cùng một tệp 15.084 giây, cùng gateway
    vLLM, chỉ đổi trường này: `verbose_json` -> 0 chữ; `json` -> có chữ.
    Nhưng ghi cứng `json` cũng sai: dịch vụ bên thứ ba (OpenAI, Deepgram…)
    trả `verbose_json` đúng nghĩa và mịn hơn hẳn.
    """

    def _format_da_gui(self, body):
        """Giá trị của phần form-data `response_format` trong thân multipart."""
        marker = b'Content-Disposition: form-data; name="response_format"'
        self.assertIn(marker, body)
        # Sau dòng Content-Disposition là một dòng trống rồi tới giá trị.
        return body.split(marker)[1].split(b'\r\n')[2].decode('utf-8')

    def test_mac_dinh_la_json(self):
        """Giá trị SHIP SẴN phải đi tới tận dây, không chỉ nằm trong file dữ
        liệu — cố tình KHÔNG đặt tham số ở đây."""
        _, captured = self._call({'text': 'a'})
        self.assertEqual(self._format_da_gui(captured['body']), 'json')

    def test_gui_dung_gia_tri_verbose_json_khi_cau_hinh_yeu_cau(self):
        """Không được âm thầm ép về `json`: người trỏ sang OpenAI Whisper
        cần đúng `verbose_json` để có mốc thời gian theo từng lượt nói."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_response_format', 'verbose_json')
        _, captured = self._call({'segments': [
            {'start': 0.0, 'end': 1.0, 'text': 'a'}]})
        self.assertEqual(self._format_da_gui(captured['body']), 'verbose_json')

    def test_gia_tri_la_thi_lui_ve_json_chu_khong_gui_di(self):
        """Tham số hệ thống là ô admin gõ tay. `_parse()` chỉ đọc được hai
        khuôn dạng, nên gửi nguyên văn một giá trị thứ ba chỉ chọn giữa HTTP
        400 và một thân trả về không phân tích được — trong khi `json` chạy
        được với mọi model."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_response_format', 'srt')
        with mute_logger('odoo.addons.aidt_meeting_minutes.models.asr_client'):
            _, captured = self._call({'text': 'a'})
        self.assertEqual(self._format_da_gui(captured['body']), 'json')

    def test_khong_dat_tham_so_thi_van_la_json(self):
        """Rỗng/chưa cài đặt cũng phải ra `json` — mặc định an toàn nằm
        trong code chứ không chỉ nằm trong file dữ liệu."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_response_format', '')
        self.assertEqual(self.client._response_format(), 'json')

    def test_duong_di_json_cho_dung_mot_doan_phu_tron_mau(self):
        """Đường đi THẬT sau bản sửa: dịch vụ chỉ trả `text`, không có
        `segments`. Kết quả phải là ĐÚNG MỘT đoạn, `end_ms=None` để bên gọi
        lấy độ dài mẩu làm biên (xem `meeting_chunk._write_segments`)."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_response_format', 'json')
        result, captured = self._call({
            'text': 'nhà trưởng nguyễn ngọc thịnh nhận tiền',
            'usage': {'type': 'duration', 'seconds': 16},
        })
        self.assertEqual(self._format_da_gui(captured['body']), 'json')
        self.assertEqual(result, [{
            'start_ms': 0, 'end_ms': None,
            'text': 'nhà trưởng nguyễn ngọc thịnh nhận tiền'}])

    def test_duong_di_verbose_json_van_doc_dung_segment_that(self):
        """Không được làm hỏng hỗ trợ bên thứ ba: khi dịch vụ THỰC SỰ trả
        segment có mốc thời gian, mốc đó vẫn phải được đọc nguyên vẹn."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_meeting.asr_response_format', 'verbose_json')
        result, _ = self._call({'segments': [
            {'start': 0.4, 'end': 2.6, 'text': 'câu một'},
            {'start': 2.6, 'end': 5.0, 'text': 'câu hai'},
        ]})
        self.assertEqual(result, [
            {'start_ms': 400, 'end_ms': 2600, 'text': 'câu một'},
            {'start_ms': 2600, 'end_ms': 5000, 'text': 'câu hai'},
        ])


@tagged('post_install', '-at_install')
class TestDecodeParams(AsrCase):
    """`language`, `prompt`, `temperature` — ba tham số giải mã.

    VÌ SAO TEST Ở TẦNG THÂN MULTIPART chứ không phải chỉ test resolver: cả
    ba trường này gửi đi mà SAI TÊN thì gateway vLLM BỎ QUA IM LẶNG, trả
    HTTP 200 với kết quả y hệt. Đo thật 05/08/2026: bốn tên bịa
    (`khong_ton_tai`, `foo`, `initial_prompt`, `temperatur`) đều 200. Một
    test chỉ gọi `_prompt()` sẽ xanh hoàn hảo trong khi trường đó không bao
    giờ tới được model. Phải khẳng định đúng cái BYTE đi ra dây.

    Bằng chứng ba trường này có tác dụng thật (cùng ngày, cùng tệp audio,
    cùng model, mỗi lần chỉ đổi một thứ):
      - `language=en` đổi kết quả từ "n." thành " (tone ringing)";
        `language=khong-phai-ma` -> HTTP 400 kèm danh sách mã hợp lệ.
      - thêm `prompt` đổi " (tone ringing)" thành " [phone ringing]".
      - `temperature=5` -> HTTP 400 'must be in [0, 2]'; `-1` -> HTTP 400.
    """

    def setUp(self):
        super().setUp()
        # Đặt tường minh cả ba: giá trị mặc định đến từ file dữ liệu, mà
        # từng test dưới đây muốn kiểm soát chính xác đầu vào của mình.
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('aidt_meeting.asr_language', 'vi')
        icp.set_param('aidt_meeting.asr_prompt', '')
        icp.set_param('aidt_meeting.asr_temperature', '0')

    def _set(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param(
            f'aidt_meeting.{key}', value)

    def _field(self, body, name):
        """Giá trị của phần form-data `name`, hoặc None nếu không có."""
        marker = (f'Content-Disposition: form-data; name="{name}"'
                  .encode('utf-8'))
        if marker not in body:
            return None
        return body.split(marker)[1].split(b'\r\n')[2].decode('utf-8')

    def _body(self):
        _, captured = self._call({'text': 'a'})
        return captured['body']

    # --- language ---------------------------------------------------------

    def test_gui_language_khi_co_cau_hinh(self):
        self.assertEqual(self._field(self._body(), 'language'), 'vi')

    def test_language_rong_thi_BO_HAN_truong_chu_khong_gui_chuoi_rong(self):
        """Rỗng = "để dịch vụ tự nhận dạng", và cách nói điều đó là VẮNG
        MẶT. Gửi `language=''` không phải là im lặng — đó là một mã ngôn ngữ
        không hợp lệ, và dịch vụ trả HTTP 400 kèm danh sách mã hợp lệ (đo
        thật 05/08/2026 với `language=khong-phai-ma`)."""
        self._set('asr_language', '')
        self.assertIsNone(self._field(self._body(), 'language'))

    def test_language_giu_nguyen_gia_tri_khac_vi(self):
        """Không được ép về 'vi': họp bằng tiếng khác là cấu hình hợp lệ."""
        self._set('asr_language', 'en')
        self.assertEqual(self._field(self._body(), 'language'), 'en')

    def test_language_bo_khoang_trang_thua(self):
        """Ô nhập tay: ' vi ' phải thành 'vi', vì ' vi ' KHÔNG phải mã hợp
        lệ và sẽ cho HTTP 400 — nhưng nó lại nhìn y hệt giá trị đúng khi
        đọc trên màn hình cấu hình."""
        self._set('asr_language', '  vi  ')
        self.assertEqual(self._field(self._body(), 'language'), 'vi')

    # --- prompt -----------------------------------------------------------

    def test_gui_prompt_khi_co_cau_hinh(self):
        self._set('asr_prompt', 'Cuộc họp, ghi âm, phân quyền, local, model.')
        self.assertEqual(self._field(self._body(), 'prompt'),
                         'Cuộc họp, ghi âm, phân quyền, local, model.')

    def test_prompt_rong_thi_bo_han_truong(self):
        """Không mồi gì là lựa chọn hợp lệ; gửi `prompt=''` chỉ tốn một
        trường vô nghĩa."""
        self._set('asr_prompt', '')
        self.assertIsNone(self._field(self._body(), 'prompt'))

    def test_prompt_chi_toan_khoang_trang_cung_bi_bo(self):
        self._set('asr_prompt', '   \n  ')
        self.assertIsNone(self._field(self._body(), 'prompt'))

    def test_prompt_qua_dai_bi_cat_dung_tran(self):
        """CẮT LÀ BẮT BUỘC, KHÔNG PHẢI LÀM ĐẸP. Dịch vụ KHÔNG tự cắt bớt —
        nó TỪ CHỐI cả yêu cầu: prompt 1000 ký tự tiếng Việt trả HTTP 400
        "maximum context length is 448 tokens" (đo thật 05/08/2026; 400,
        500, 600, 800 ký tự đều 200). Qua `_transcribe` thì 400 đó thành
        AsrError và đốt sạch lượt retry — tức một quản trị viên dán nguyên
        bảng thuật ngữ vào ô cấu hình sẽ làm CHẾT toàn bộ việc bóc băng."""
        self._set('asr_prompt', 'ạ' * 900)
        sent = self._field(self._body(), 'prompt')
        self.assertEqual(len(sent), 400)
        self.assertEqual(sent, 'ạ' * 400)

    def test_prompt_vua_du_tran_thi_khong_bi_dong_toi(self):
        """Ranh giới phải chính xác: đúng 400 ký tự là hợp lệ, không cắt."""
        self._set('asr_prompt', 'ạ' * 400)
        self.assertEqual(len(self._field(self._body(), 'prompt')), 400)

    # Giá trị prompt SHIP SẴN được canh ở tests/test_config.py, không phải ở
    # đây: `setUp` của lớp này cố tình xoá trắng tham số để mỗi test tự kiểm
    # soát đầu vào, nên đọc lại "mặc định" ở đây chỉ đọc được chuỗi rỗng do
    # chính nó vừa ghi.

    # --- temperature ------------------------------------------------------

    def test_mac_dinh_temperature_la_0(self):
        self.assertEqual(self._field(self._body(), 'temperature'), '0')

    def test_luon_gui_temperature_ke_ca_khi_cau_hinh_rong(self):
        """Khác `language`/`prompt`: rỗng ở đây không có nghĩa gì cả. Bỏ
        trường đi nghĩa là nhận mặc định của dịch vụ, mà mặc định đó khác
        nhau tuỳ backend — gửi 0 tường minh thì mọi backend hành xử giống
        nhau."""
        self._set('asr_temperature', '')
        self.assertEqual(self._field(self._body(), 'temperature'), '0')

    def test_gui_dung_gia_tri_hop_le_khac_0(self):
        self._set('asr_temperature', '0.4')
        self.assertEqual(self._field(self._body(), 'temperature'), '0.4')

    def test_gia_tri_khong_phai_so_thi_lui_ve_0_kem_canh_bao(self):
        """Ô admin gõ tay. Chuyển tiếp nguyên văn 'cao' sẽ cho HTTP 400 ở
        MỌI mẩu cho tới khi có người phát hiện."""
        self._set('asr_temperature', 'cao')
        with self.assertLogs(
                'odoo.addons.aidt_meeting_minutes.models.asr_client',
                level='WARNING') as logs:
            body = self._body()
        self.assertEqual(self._field(body, 'temperature'), '0')
        self.assertTrue(any('asr_temperature' in m for m in logs.output))

    def test_gia_tri_ngoai_khoang_cung_lui_ve_0_kem_canh_bao(self):
        """Chặn cả số hợp lệ nhưng ngoài khoảng, không chỉ chặn chữ: '5' qua
        được `float()` nhưng dịch vụ trả HTTP 400 'temperature must be in
        [0, 2]' (đo thật 05/08/2026), và '-1' trả 'must be non-negative'."""
        for bad in ('5', '-1', '1e9'):
            self._set('asr_temperature', bad)
            with self.assertLogs(
                    'odoo.addons.aidt_meeting_minutes.models.asr_client',
                    level='WARNING'):
                body = self._body()
            self.assertEqual(self._field(body, 'temperature'), '0',
                             f'temperature={bad!r} phải lùi về 0')

    def test_gia_tri_bien_2_van_duoc_chap_nhan(self):
        """Biên trên là 2 chứ không phải 1 — đó là khoảng mà dịch vụ thật
        nhận, đọc ra từ chính thông báo lỗi của nó."""
        self._set('asr_temperature', '2')
        self.assertEqual(self._field(self._body(), 'temperature'), '2')

    # --- toàn thân --------------------------------------------------------

    def test_than_multipart_van_dung_khuon_khi_co_du_moi_truong(self):
        """Thân multipart được ghép TAY. Thêm trường vào giữa là lúc dễ làm
        hỏng ranh giới nhất, mà hỏng ranh giới thì phần `file` không đọc
        được — và triệu chứng sẽ là "bóc băng ra rỗng", không phải một lỗi
        rõ ràng."""
        self._set('asr_prompt', 'Cuộc họp.')
        body = self._body()
        self.assertEqual(self._field(body, 'language'), 'vi')
        self.assertEqual(self._field(body, 'prompt'), 'Cuộc họp.')
        self.assertEqual(self._field(body, 'temperature'), '0')
        self.assertEqual(self._field(body, 'response_format'), 'json')
        # Phần file phải còn nguyên vẹn và ranh giới phải đóng đúng.
        self.assertIn(b'name="file"; filename="a.mp3"', body)
        self.assertIn(b'Content-Type: audio/mpeg', body)
        boundary = body.split(b'\r\n')[0]
        self.assertTrue(body.rstrip().endswith(boundary + b'--'))

    def test_prompt_tieng_viet_di_ra_dung_utf8(self):
        """Prompt là tiếng Việt có dấu. Thân multipart ghép bằng bytes, nên
        một lỗi mã hoá ở đây sẽ biến mồi vốn từ thành rác — mà request vẫn
        thành công, nên sẽ không ai thấy."""
        self._set('asr_prompt', 'phân quyền, độ mật')
        self.assertIn('phân quyền, độ mật'.encode('utf-8'), self._body())


class TestPartContentType(TransactionCase):
    """MINOR 7 của review Task 12: kiểu MIME của phần `file` từng bị ghi
    cứng `audio/mpeg` cho mọi payload, khiến các phép thử chẩn đoán bằng
    định dạng khác bị gắn nhãn sai."""

    def test_suy_kieu_mime_tu_duoi_tep(self):
        client = self.env['aidt.meeting.asr.client']
        self.assertEqual(client._part_content_type('chunk-1.mp3'), 'audio/mpeg')
        self.assertEqual(client._part_content_type('chunk-1.wav'), 'audio/wav')
        self.assertEqual(client._part_content_type('CHUNK.WAV'), 'audio/wav')
        self.assertEqual(
            client._part_content_type('la'), 'application/octet-stream')

    def test_than_multipart_dung_kieu_mime_theo_ten_tep(self):
        client = self.env['aidt.meeting.asr.client']
        _, body = client._build_multipart(b'RAW', 'chunk-1.wav', 'm')
        self.assertIn(b'Content-Type: audio/wav', body)
        self.assertNotIn(b'Content-Type: audio/mpeg', body)
        # Đường đi thật của module vẫn phải giữ nguyên hành vi cũ.
        _, body = client._build_multipart(b'RAW', 'chunk-1.mp3', 'm')
        self.assertIn(b'Content-Type: audio/mpeg', body)
