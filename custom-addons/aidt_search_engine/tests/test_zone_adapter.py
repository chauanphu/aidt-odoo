import unittest

from aidt_search_engine.extract.zone_adapter import align_from_bbox, assign_zones
from aidt_search_engine.types import Block

W = 1000.0


class TestAlignFromBbox(unittest.TestCase):
    def test_giua_trang(self):
        self.assertEqual(align_from_bbox((300, 0, 700, 20), W), "center")

    def test_sat_trai(self):
        self.assertEqual(align_from_bbox((20, 0, 300, 20), W), "left")

    def test_sat_phai(self):
        self.assertEqual(align_from_bbox((700, 0, 980, 20), W), "right")

    def test_trai_dai_het_dong_la_justify(self):
        self.assertEqual(align_from_bbox((20, 0, 980, 20), W), "justify")

    def test_khong_co_bbox(self):
        self.assertIsNone(align_from_bbox(None, W))

    def test_khong_biet_chieu_rong(self):
        self.assertIsNone(align_from_bbox((300, 0, 700, 20), 0))


class TestAssignZones(unittest.TestCase):
    def _ocr_page(self):
        return [
            Block(text="ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG", bbox=(300, 60, 700, 85), page=1),
            Block(text="CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", bbox=(300, 95, 760, 120), page=1),
            Block(text="Độc lập - Tự do - Hạnh phúc", bbox=(360, 125, 700, 145), page=1),
            Block(text="Số: 145/KH-UBND", bbox=(60, 160, 300, 180), page=1),
            Block(text="Bình Dương, ngày 25 tháng 7 năm 2026", bbox=(560, 160, 950, 180), page=1),
            Block(text="KẾ HOẠCH", bbox=(430, 210, 570, 235), page=1),
            Block(text="Căn cứ Luật An toàn thông tin mạng năm 2015;", bbox=(60, 280, 940, 300), page=1),
            Block(text="Nơi nhận:", bbox=(60, 700, 200, 720), page=1),
            Block(text="Nguyễn Văn A", bbox=(700, 800, 940, 820), page=1),
        ]

    def test_khong_nem_loi_khi_thieu_thuoc_tinh_docx(self):
        # Đây là R1: detect_zones vốn viết cho Para có fmt đầy đủ.
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(len(blocks), 9)

    def test_gan_zone_cho_moi_khoi(self):
        for b in assign_zones(self._ocr_page(), W):
            self.assertIsNotNone(b.zone)

    def test_nhan_dien_so_ky_hieu(self):
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(blocks[3].zone, "so_ky_hieu")

    def test_nhan_dien_noi_nhan(self):
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(blocks[7].zone, "noi_nhan")

    def test_do_tin_cay_luon_la_heuristic(self):
        # Nhánh OCR không có style đặt tên nên không bao giờ đạt 'style'.
        for b in assign_zones(self._ocr_page(), W):
            self.assertEqual(b.zone_confidence, "heuristic")

    def test_khong_sua_danh_sach_goc(self):
        original = self._ocr_page()
        assign_zones(original, W)
        self.assertTrue(all(b.zone is None for b in original))

    def test_danh_sach_rong(self):
        self.assertEqual(assign_zones([], W), [])

    def test_giu_nguyen_page_va_bbox(self):
        out = assign_zones(self._ocr_page(), W)
        self.assertEqual(out[3].page, 1)
        self.assertEqual(out[3].bbox, (60, 160, 300, 180))


if __name__ == "__main__":
    unittest.main()
