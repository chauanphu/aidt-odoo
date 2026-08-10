from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConfig(TransactionCase):
    """Tham số cấu hình của đường xử lý theo lô (docker/ai_worker).

    19.0.1.2.0 — các test về `asr_url`, `asr_api_key`, `asr_response_format`,
    `asr_temperature`, `llm_url`, `llm_api_key` đã bị gỡ cùng chính các tham
    số đó: chúng phục vụ models/asr_client.py và models/summary_client.py,
    cả hai đã bị xoá khi chuyển sang xử lý theo lô. Giữ lại test cho một
    tham số không ai đọc chỉ tạo cảm giác an toàn giả.
    """

    def _param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    def test_co_gia_tri_mac_dinh_cho_moi_tham_so(self):
        self.assertTrue(self._param('aidt_meeting.ai_service_url'))
        self.assertTrue(self._param('aidt_meeting.asr_ct2_model'))
        self.assertTrue(self._param('aidt_meeting.llm_model'))

    def test_model_boc_bang_dung_cach_goi_cua_faster_whisper(self):
        """`large-v3`, KHÔNG phải `openai/whisper-large-v3`.

        Hai đường nói hai ngôn ngữ khác nhau: tham số `asr_model` cũ mang
        tên repo Hugging Face (hợp lệ với vLLM), còn worker chạy
        faster-whisper/CTranslate2 vốn chỉ nhận tên kích cỡ hoặc một repo đã
        chuyển sang CTranslate2. Đưa nhầm giá trị kia sang là
        `ValueError: Invalid model size` ngay lúc nạp model — đã xảy ra thật
        trong log worker với `PhoWhisper-large-ct2`.

        Test canh riêng dạng SAI chứ không chỉ canh dạng đúng, vì lỗi đáng
        sợ ở đây là điền một chuỗi trông rất hợp lý mà worker không nhận.
        """
        model = self._param('aidt_meeting.asr_ct2_model')
        self.assertEqual(model, 'large-v3')
        self.assertNotIn('/', model)

    def test_mac_dinh_khong_con_la_phowhisper(self):
        """PhoWhisper được tinh chỉnh trên tiếng Việt ĐỌC (kiểu VLSP): nghe
        đúng nhưng CHỌN SAI TỪ trên hội thoại kỹ thuật, không xuất dấu câu.
        Bản ghi 1140 (05/08/2026): "lô cồ" = local, "hỗn hợp" = cuộc họp.
        Bản ghi 2797 (10/08/2026, PhoWhisper-small): "bê đét" = PDF,
        "ô sơ rờ" = OCR."""
        self.assertNotIn(
            'phowhisper',
            (self._param('aidt_meeting.asr_ct2_model') or '').lower())

    def test_mac_dinh_ngon_ngu_boc_bang_la_tieng_viet(self):
        """Không gửi `language`, Whisper tự nhận dạng và có thể lật sang
        tiếng Anh giữa cuộc họp. Mặc định phải là ngôn ngữ của người dùng
        thật."""
        self.assertEqual(self._param('aidt_meeting.asr_language'), 'vi')

    def test_prompt_mac_dinh_co_von_tu_da_tung_boc_sai(self):
        """Prompt ship sẵn phải chứa ĐÚNG những từ đã bóc sai thật, nếu
        không nó chỉ là một câu trang trí. Đây là bản dịch ngược của các lỗi
        quan sát được: "lô cồ" -> local, "con ngôi đồ" -> model, "ghim" ->
        ghi âm, "hỗn hợp" -> cuộc họp, "vương bị trần quyền" -> phân quyền."""
        prompt = self._param('aidt_meeting.asr_prompt') or ''
        for tu in ('local', 'model', 'ghi âm', 'cuộc họp', 'phân quyền'):
            self.assertIn(tu, prompt, f'prompt mặc định thiếu {tu!r}')

    def test_prompt_mac_dinh_viet_thanh_van_xuoi(self):
        """Prompt kiểu liệt kê đã gây sự cố thật HAI lần: bản ghi 1141 phía
        Odoo (model nhả ngược prompt rồi lặp 18 lần), và bản đầu của
        docker/ai_worker với "Odoo, PDF, OCR, tờ trình, phụ lục.".

        Whisper tiếp nối VĂN PHONG của prompt; khuôn "nhãn: a, b, c" là một
        danh sách đang dở nên tiếp nối nó nghĩa là đẻ thêm mục, và trên đoạn
        audio nghèo tín hiệu thì nó đẻ mãi. Dấu hiệu nhận biết rẻ nhất của
        khuôn đó: một dấu hai chấm rồi tới chuỗi phần tử ngăn bằng phẩy."""
        prompt = self._param('aidt_meeting.asr_prompt') or ''
        self.assertNotIn(':', prompt,
                         'prompt mặc định đang có khuôn liệt kê "nhãn: a, b, c"')
        self.assertTrue(prompt.rstrip().endswith('.'),
                        'prompt mặc định phải là câu hoàn chỉnh, kết bằng dấu chấm')

    def test_doi_duoc_tham_so_giai_ma_tu_settings(self):
        """Tinh chỉnh vốn từ là việc lặp lại của người vận hành — phải làm
        được từ UI, không phải sửa code rồi deploy lại."""
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_language': 'en',
            'aidt_meeting_asr_prompt': 'Quarterly meeting minutes.',
            'aidt_meeting_asr_ct2_model': 'medium',
        })
        settings.execute()
        self.assertEqual(self._param('aidt_meeting.asr_language'), 'en')
        self.assertEqual(self._param('aidt_meeting.asr_prompt'),
                         'Quarterly meeting minutes.')
        self.assertEqual(self._param('aidt_meeting.asr_ct2_model'), 'medium')

    def test_xoa_trang_ngon_ngu_thi_giu_nguyen_trang(self):
        """Để trống = "model tự nhận dạng", một lựa chọn thật cho cuộc họp
        song ngữ. Nếu tầng cấu hình âm thầm khôi phục 'vi' thì lựa chọn đó
        không tồn tại."""
        settings = self.env['res.config.settings'].create({
            'aidt_meeting_asr_language': '',
        })
        settings.execute()
        self.assertFalse(self._param('aidt_meeting.asr_language'))

    def test_khong_con_tham_so_cua_duong_vllm_da_go(self):
        """Sáu tham số này thuộc models/asr_client.py và
        models/summary_client.py — cả hai đã bị xoá. Còn sót lại thì trang
        Cấu hình lại hiện những ô đổi bao nhiêu cũng không có tác dụng, đúng
        loại lỗi đã tốn cả buổi truy: cấu hình ghi `openai/whisper-large-v3`
        trong khi thứ thực sự chạy là `PhoWhisper-small`."""
        for key in ('asr_url', 'asr_api_key', 'asr_response_format',
                    'asr_temperature', 'llm_url', 'llm_api_key'):
            self.assertFalse(
                self._param(f'aidt_meeting.{key}'),
                f'aidt_meeting.{key} vẫn còn — đường vLLM đã gỡ')

    def test_mac_dinh_chi_cho_ghi_am_muc_thuong(self):
        """Mặc định phải là mức thấp nhất: bật rộng hơn phải là quyết định
        có ý thức của quản trị viên, không phải thứ có sẵn khi cài."""
        self.assertEqual(self._param('aidt_meeting.max_secrecy'), 'thuong')

    def test_mac_dinh_xoa_audio_ngay_sau_khi_boc_bang(self):
        """0 ngày = xoá ngay. Audio thô là rủi ro lớn hơn transcript."""
        self.assertEqual(self._param('aidt_meeting.audio_retention_days'), '0')
