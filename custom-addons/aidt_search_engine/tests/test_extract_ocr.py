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


class FakeTransport:
    """Bắt lại request body để kiểm công thức gọi, trả nội dung dựng sẵn."""

    def __init__(self, content=SAMPLE, exc=None):
        self.content, self.exc, self.body = content, exc, None

    def __call__(self, url, body, timeout):
        if self.exc:
            raise self.exc
        self.body = body
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


if __name__ == "__main__":
    unittest.main()
