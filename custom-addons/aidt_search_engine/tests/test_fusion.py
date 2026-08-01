import unittest

from aidt_search_engine.fusion import RRF_K, reciprocal_rank_fusion
from aidt_search_engine.rerank import rerank


class TestRRF(unittest.TestCase):
    def test_khong_co_kenh_nao(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    def test_kenh_rong_khong_lam_do(self):
        self.assertEqual(reciprocal_rank_fusion([[], []]), [])

    def test_mot_kenh_giu_nguyen_thu_tu(self):
        out = reciprocal_rank_fusion([["a", "b", "c"]])
        self.assertEqual([i for i, _ in out], ["a", "b", "c"])

    def test_item_xuat_hien_nhieu_kenh_duoc_cong_diem(self):
        out = dict(reciprocal_rank_fusion([["a", "b"], ["a", "c"]]))
        self.assertAlmostEqual(out["a"], 2 / (RRF_K + 1))
        self.assertAlmostEqual(out["b"], 1 / (RRF_K + 2))

    def test_dong_thuan_thang_hang_cao_don_le(self):
        # 'b' đứng nhất ở một kênh, 'a' đứng nhì ở cả ba kênh -> 'a' thắng.
        out = reciprocal_rank_fusion([["b", "a"], ["c", "a"], ["d", "a"]])
        self.assertEqual(out[0][0], "a")

    def test_them_kenh_rac_khong_truat_ngoi_item_dong_thuan(self):
        # Tính chất quan trọng nhất: RRF phải chịu được một kênh kém.
        # Đây là cái cho phép bật/tắt kênh ts_seg và giảm cấp mềm mà an toàn.
        clean = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
        self.assertEqual(reciprocal_rank_fusion(clean)[0][0], "a")
        noisy = clean + [["z", "y", "x"]]
        self.assertEqual(reciprocal_rank_fusion(noisy)[0][0], "a")

    def test_ket_qua_on_dinh_khi_diem_bang_nhau(self):
        # Điểm bằng nhau phải phá hoà tất định, nếu không thứ tự kết quả
        # nhảy giữa hai lần chạy giống hệt.
        a = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
        b = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
        self.assertEqual(a, b)

    def test_k_lon_lam_phang_chenh_lech(self):
        gap_small_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
        gap_large_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
        self.assertGreater(gap_small_k["a"] - gap_small_k["b"],
                           gap_large_k["a"] - gap_large_k["b"])


class TestRerankSeam(unittest.TestCase):
    def test_v1_tra_nguyen_danh_sach(self):
        items = [("a", 0.9), ("b", 0.5)]
        self.assertEqual(rerank("truy vấn bất kỳ", items), items)

    def test_danh_sach_rong(self):
        self.assertEqual(rerank("q", []), [])


if __name__ == "__main__":
    unittest.main()
