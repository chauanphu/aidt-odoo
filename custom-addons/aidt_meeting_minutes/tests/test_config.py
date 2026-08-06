from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConfig(TransactionCase):
    def _param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    def test_co_gia_tri_mac_dinh_cho_moi_tham_so(self):
        self.assertTrue(self._param('aidt_meeting.asr_url'))
        self.assertEqual(self._param('aidt_meeting.asr_model'),
                         'openai/whisper-large-v3')
        self.assertTrue(self._param('aidt_meeting.llm_url'))

    def test_model_mac_dinh_khong_con_la_phowhisper(self):
        """`vinai/PhoWhisper-large` được tinh chỉnh trên tiếng Việt ĐỌC
        (kiểu VLSP): xuất chữ thường, không dấu câu, và không có vốn từ cho
        hội thoại kỹ thuật — bản ghi 1140 ngày 05/08/2026 cho ra "lô cồ"
        (= local), "con ngôi đồ" (= con model), "hỗn hợp" (= cuộc họp).

        Test này canh riêng GIÁ TRỊ CŨ chứ không chỉ canh giá trị mới, vì
        thất bại đáng sợ ở đây không phải "sai model" mà là "XML nói một
        đằng, CSDL chạy một nẻo": khối dữ liệu là `noupdate="1"` nên bản ghi
        đã có KHÔNG được nâng cấp ghi đè. Trên CSDL cài mới (chính là CSDL
        chạy test này) giá trị đến từ XML; trên CSDL cũ nó đến từ
        migrations/19.0.1.1.0/post-migration.py. Hai đường phải cho cùng
        một kết quả."""
        self.assertNotEqual(self._param('aidt_meeting.asr_model'),
                            'vinai/PhoWhisper-large')

    def test_mac_dinh_ngon_ngu_boc_bang_la_tieng_viet(self):
        """Không gửi `language`, Whisper tự nhận dạng lại cho TỪNG mẩu 15
        giây và có thể lật sang tiếng Anh giữa cuộc họp. Đã quan sát
        PhoWhisper bóc một tệp thử tiếng Anh ra tiếng Anh, tức lớp tự đoán
        này có thật. Mặc định phải là ngôn ngữ của người dùng thật."""
        self.assertEqual(self._param('aidt_meeting.asr_language'), 'vi')

    def test_mac_dinh_temperature_la_0(self):
        """0 = giải mã tham lam: bóc lại cùng audio ra cùng chữ. Không có
        tính tái lập thì không so sánh được hai lần chỉnh cấu hình."""
        self.assertEqual(self._param('aidt_meeting.asr_temperature'), '0')

    def test_prompt_mac_dinh_co_von_tu_da_tung_boc_sai(self):
        """Prompt ship sẵn phải chứa ĐÚNG những từ đã bóc sai thật, nếu
        không nó chỉ là một câu trang trí. Đây là bản dịch ngược của các lỗi
        quan sát được: "lô cồ" -> local, "con ngôi đồ" -> model, "ghim" ->
        ghi âm, "hỗn hợp" -> cuộc họp, "vương bị trần quyền" -> phân quyền."""
        prompt = self._param('aidt_meeting.asr_prompt') or ''
        for tu in ('local', 'model', 'ghi âm', 'cuộc họp', 'phân quyền'):
            self.assertIn(tu, prompt, f'prompt mặc định thiếu {tu!r}')

    def test_prompt_mac_dinh_ngan_hon_tran_400_ky_tu(self):
        """Dịch vụ KHÔNG cắt bớt prompt dài — nó từ chối cả yêu cầu (HTTP
        400, ngữ cảnh 448 token; đo thật 05/08/2026 với 1000 ký tự). Code
        cắt ở 400 ký tự, nên một prompt mặc định dài hơn thế sẽ bị cụt giữa
        câu mà không ai để ý."""
        self.assertLessEqual(
            len(self._param('aidt_meeting.asr_prompt') or ''), 400)

    def test_doi_duoc_ba_tham_so_giai_ma_tu_settings(self):
        """Tinh chỉnh vốn từ là việc lặp lại của người vận hành — phải làm
        được từ UI, không phải sửa code rồi deploy lại."""
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_language': 'en',
            'aidt_meeting_asr_prompt': 'Quarterly meeting minutes.',
            'aidt_meeting_asr_temperature': '0.2',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_language'), 'en')
        self.assertEqual(self._param('aidt_meeting.asr_prompt'),
                         'Quarterly meeting minutes.')
        self.assertEqual(self._param('aidt_meeting.asr_temperature'), '0.2')

    def test_xoa_trang_ngon_ngu_thi_giu_nguyen_trang(self):
        """Để trống = "dịch vụ tự nhận dạng", một lựa chọn thật cho cuộc họp
        song ngữ. Nếu tầng cấu hình âm thầm khôi phục 'vi' thì lựa chọn đó
        không tồn tại."""
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_language': '',
        })
        settings.execute()
        self.assertFalse(self._param('aidt_meeting.asr_language'))

    def test_mac_dinh_khuon_dang_boc_bang_la_json(self):
        """`verbose_json` bắt model trả segment kèm mốc thời gian;
        `vinai/PhoWhisper-large` — model mặc định CŨ, cho tới 19.0.1.1.0 —
        là bản tinh chỉnh KHÔNG có token mốc thời gian nên nó trả về RỖNG.

        Mặc định vẫn giữ `json` sau khi đổi sang `openai/whisper-large-v3`,
        dù large-v3 CÓ token mốc thời gian: `asr_model` là ô cấu hình, người
        vận hành có thể trỏ ngược lại PhoWhisper hoặc một bản tinh chỉnh
        khác bất cứ lúc nào, và mặc định phải là thứ chạy được với MỌI model
        chứ không chỉ với model ta tình cờ đang ship. Ai đã chắc chắn model
        của mình có mốc thời gian thì bật `verbose_json` từ trang Cấu hình."""
        self.assertEqual(self._param('aidt_meeting.asr_response_format'),
                         'json')

    def test_doi_duoc_khuon_dang_sang_verbose_json_tu_settings(self):
        """Đổi được từ UI là điều kiện để trỏ sang dịch vụ bên thứ ba (OpenAI,
        Deepgram…) — nơi `verbose_json` cho mốc thời gian theo từng lượt nói."""
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_response_format': 'verbose_json',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_response_format'),
                         'verbose_json')

    def test_mac_dinh_chi_cho_ghi_am_muc_thuong(self):
        """Mặc định phải là mức thấp nhất: bật rộng hơn phải là quyết định
        có ý thức của quản trị viên, không phải thứ có sẵn khi cài."""
        self.assertEqual(self._param('aidt_meeting.max_secrecy'), 'thuong')

    def test_mac_dinh_xoa_audio_ngay_sau_khi_boc_bang(self):
        """0 ngày = xoá ngay. Audio thô là rủi ro lớn hơn transcript."""
        self.assertEqual(self._param('aidt_meeting.audio_retention_days'), '0')

    def test_settings_ghi_duoc_va_doc_lai_dung(self):
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_url': 'http://phowhisper:8002/v1',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_url'),
                         'http://phowhisper:8002/v1')
