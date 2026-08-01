import unittest

from aidt_search_engine.tokenize import MODE_SYLLABLE, MODE_WORD, tokenize


def fake_segmenter(text):
    """Giả lập underthesea/pyvi: nối âm tiết cùng từ bằng '_'."""
    return text.replace("hộ nghèo", "hộ_nghèo").replace("an toàn", "an_toàn")


class TestTokenize(unittest.TestCase):
    def test_syllable_tra_nguyen_van(self):
        self.assertEqual(tokenize("hỗ trợ hộ nghèo", MODE_SYLLABLE), "hỗ trợ hộ nghèo")

    def test_word_dung_segmenter_duoc_truyen_vao(self):
        self.assertEqual(
            tokenize("hỗ trợ hộ nghèo", MODE_WORD, segmenter=fake_segmenter),
            "hỗ trợ hộ_nghèo",
        )

    def test_word_lui_ve_syllable_khi_khong_co_thu_vien(self):
        # segmenter=False mô phỏng "không cài underthesea lẫn pyvi".
        # Phải lùi êm chứ không được ném lỗi: v1 mặc định chạy không có
        # thư viện tách từ nào.
        self.assertEqual(
            tokenize("hỗ trợ hộ nghèo", MODE_WORD, segmenter=False),
            "hỗ trợ hộ nghèo",
        )

    def test_mode_la_gi_khac_thi_coi_nhu_syllable(self):
        self.assertEqual(tokenize("abc", "linh tinh"), "abc")

    def test_chuoi_rong(self):
        self.assertEqual(tokenize("", MODE_WORD, segmenter=fake_segmenter), "")


if __name__ == "__main__":
    unittest.main()
