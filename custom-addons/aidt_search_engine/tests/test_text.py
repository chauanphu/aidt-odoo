import unittest

from aidt_search_engine.text import estimate_tokens, normalize_ws, strip_accents


class TestStripAccents(unittest.TestCase):
    def test_bo_dau_tieng_viet(self):
        self.assertEqual(strip_accents("hỗ trợ hộ nghèo"), "ho tro ho ngheo")

    def test_chu_d_gach_ngang(self):
        # NFD không phân rã 'đ' — phải xử lý riêng, nếu không kênh
        # không dấu sẽ lệch với unaccent() phía Postgres.
        self.assertEqual(strip_accents("Đảng đoàn"), "Dang doan")

    def test_giu_nguyen_chu_khong_dau(self):
        self.assertEqual(strip_accents("145/KH-UBND"), "145/KH-UBND")

    def test_chuoi_rong(self):
        self.assertEqual(strip_accents(""), "")


class TestEstimateTokens(unittest.TestCase):
    def test_uoc_luong_theo_do_dai(self):
        self.assertEqual(estimate_tokens("abcdef"), 2)

    def test_chuoi_rong_van_tra_it_nhat_1(self):
        self.assertEqual(estimate_tokens(""), 1)


class TestNormalizeWs(unittest.TestCase):
    def test_gop_khoang_trang(self):
        self.assertEqual(normalize_ws("  hỗ   trợ \n\n hộ nghèo "), "hỗ trợ hộ nghèo")


if __name__ == "__main__":
    unittest.main()
