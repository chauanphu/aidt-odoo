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

    def test_prompt_mac_dinh_de_trong(self):
        """ĐO ĐƯỢC, không phải sở thích — và là lần ĐẢO HƯỚNG so với
        19.0.1.1.1.

        Whisper coi `initial_prompt` như văn bản đứng ngay TRƯỚC audio, nên
        gặp cửa sổ nghèo tín hiệu nó ĐỌC TIẾP prompt thay vì phiên âm. Bản
        19.0.1.1.1 tưởng lỗi nằm ở KIỂU VIẾT (liệt kê -> văn xuôi); sai —
        văn xuôi chỉ làm hỏng hóc bớt lộ liễu.

        Đo 10/08/2026, cùng một luồng audio, chỉ đổi mỗi prompt:
          * Bản ghi 2858 luồng Nguyễn Văn An — CÓ prompt: một segment DUY
            NHẤT trải 44 giây mang nguyên văn prompt, avg_logprob -0.06.
            KHÔNG prompt: đúng 44 giây đó ra 8 câu thật. Prompt không chèn
            thêm rác, nó XOÁ MẤT nửa phần phát biểu của một người.
          * Bản ghi 2797: có prompt 51 segment, không prompt 53 segment;
            "PDF", "OCR", "tàu trình" giống hệt nhau -> lợi ích bằng 0.

        Lọc theo độ tự tin KHÔNG cứu được: đoạn nhả ngược prompt có logprob
        ĐẸP HƠN lời nói thật (-0.06 so với -0.43).
        """
        self.assertFalse(self._param('aidt_meeting.asr_prompt'))

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
