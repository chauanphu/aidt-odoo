import json
import unittest

from aidt_search_engine.extract.ocr import (
    NGRAM_SIZE,
    PROMPT,
    OcrEmptyOutput,
    OcrError,
    ocr_image,
    parse_ocr_output,
)

SAMPLE = (
    "<|det|>title [324, 72, 744, 93]<|/det|>ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG\n"
    "<|det|>title [304, 105, 766, 126]<|/det|>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
    "<|det|>text [60, 160, 300, 180]<|/det|>Số: 145/KH-UBND\n"
)


class TestParseOcrOutput(unittest.TestCase):
    def test_tach_dung_so_khoi(self):
        self.assertEqual(len(parse_ocr_output(SAMPLE)), 3)

    def test_lay_dung_text(self):
        self.assertEqual(parse_ocr_output(SAMPLE)[2].text, "Số: 145/KH-UBND")

    def test_lay_dung_bbox(self):
        self.assertEqual(parse_ocr_output(SAMPLE)[2].bbox, (60.0, 160.0, 300.0, 180.0))

    def test_dong_khong_co_the_det_van_thanh_block(self):
        # Model đôi khi trả dòng trần; mất chữ còn tệ hơn mất toạ độ.
        blocks = parse_ocr_output("Một dòng không có thẻ\n" + SAMPLE)
        self.assertEqual(blocks[0].text, "Một dòng không có thẻ")
        self.assertIsNone(blocks[0].bbox)

    def test_bo_qua_dong_rong(self):
        self.assertEqual(len(parse_ocr_output("\n\n" + SAMPLE + "\n\n")), 3)

    def test_chuoi_rong_tra_danh_sach_rong(self):
        self.assertEqual(parse_ocr_output(""), [])

    def test_toa_do_hong_khong_parse_duoc_thi_bbox_none(self):
        # box khớp regex (chỉ số, dấu phẩy, khoảng trắng) nhưng float() hỏng
        # vì có khoảng trống giữa hai dấu phẩy — vẫn phải giữ chữ, bbox=None.
        blocks = parse_ocr_output("<|det|>text [1, 2, , 4]<|/det|>vẫn giữ chữ")
        self.assertEqual(blocks[0].text, "vẫn giữ chữ")
        self.assertIsNone(blocks[0].bbox)

    def test_det_khong_co_text_thi_bo_qua(self):
        # Có toạ độ nhưng không có chữ theo sau: không tạo Block nào cả.
        self.assertEqual(
            parse_ocr_output("<|det|>title [1, 2, 3, 4]<|/det|>"), [])


class FakeTransport:
    """Bắt lại request body/url/timeout để kiểm công thức gọi.

    `response`, nếu đặt, được trả nguyên văn (bỏ qua `content`) — dùng để
    dựng các thân trả về sai cấu trúc mà `content=` không dựng được.
    """

    def __init__(self, content=SAMPLE, exc=None, response=None):
        self.content, self.exc, self.response = content, exc, response
        self.url = self.body = self.timeout = None

    def __call__(self, url, body, timeout):
        self.url, self.body, self.timeout = url, body, timeout
        if self.exc:
            raise self.exc
        if self.response is not None:
            return self.response
        return {"choices": [{"message": {"content": self.content}}]}


class TestOcrImage(unittest.TestCase):
    def test_tra_ve_block(self):
        self.assertEqual(len(ocr_image(b"\x89PNG...", "http://x/v1",
                                       transport=FakeTransport())), 3)

    def test_prompt_phai_bat_dau_bang_the_image(self):
        # Thiếu '<image>' thì model trả rỗng — đây là lỗi cấu hình im lặng
        # đã gặp thật, phải khoá bằng test.
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        texts = [c for c in t.body["messages"][0]["content"] if c["type"] == "text"]
        self.assertEqual(texts[0]["text"], PROMPT)
        self.assertTrue(texts[0]["text"].startswith("<image>"))

    def test_skip_special_tokens_phai_la_false(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        self.assertIs(t.body["skip_special_tokens"], False)

    def test_vllm_xargs_dung_cong_thuc(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", window_size=1024, transport=t)
        self.assertEqual(t.body["vllm_xargs"],
                         {"ngram_size": NGRAM_SIZE, "window_size": 1024})

    def test_anh_duoc_gui_dang_data_uri(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        images = [c for c in t.body["messages"][0]["content"] if c["type"] == "image_url"]
        self.assertTrue(images[0]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_ket_qua_rong_nem_ocrempty(self):
        # Trang trắng và lỗi cấu hình trông giống hệt nhau ở đây; tầng trên
        # phân biệt bằng cách kiểm ảnh có phải trang trắng không.
        with self.assertRaises(OcrEmptyOutput):
            ocr_image(b"png", "http://x/v1", transport=FakeTransport(content="   "))

    def test_loi_mang_nem_ocrerror(self):
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1",
                      transport=FakeTransport(exc=TimeoutError("hết giờ")))

    def test_content_khong_phai_chuoi_nem_ocrerror(self):
        # Một số backend OpenAI-compatible trả content dạng list content-part
        # thay vì str — không được rò AttributeError từ .strip() xuống đây.
        t = FakeTransport(content=[{"type": "text", "text": "abc"}])
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1", transport=t)

    def test_response_thieu_choices_nem_ocrerror(self):
        # Thiếu hẳn khoá 'choices' -> KeyError phải hoá thành OcrError.
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1", transport=FakeTransport(response={}))

    def test_response_choices_rong_nem_ocrerror(self):
        # 'choices' rỗng -> IndexError phải hoá thành OcrError.
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1",
                      transport=FakeTransport(response={"choices": []}))

    def test_response_message_khong_phai_dict_nem_ocrerror(self):
        # 'message' là chuỗi thay vì dict -> TypeError khi tra ["content"]
        # phải hoá thành OcrError, không rò ra ngoài.
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1",
                      transport=FakeTransport(response={"choices": [{"message": "x"}]}))

    def test_url_ghep_dung_duong_dan_chat_completions(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        self.assertEqual(t.url, "http://x/v1/chat/completions")

    def test_url_bo_dau_gach_cheo_thua_o_cuoi_base_url(self):
        # base_url có hay không có '/' ở cuối phải ra cùng một URL.
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1/", transport=t)
        self.assertEqual(t.url, "http://x/v1/chat/completions")

    def test_timeout_duoc_chuyen_tiep_dung(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", timeout=42, transport=t)
        self.assertEqual(t.timeout, 42)


if __name__ == "__main__":
    unittest.main()
