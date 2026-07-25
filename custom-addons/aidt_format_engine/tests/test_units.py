import unittest

from aidt_format_engine.units import half_point_to_pt, line_spacing, twip_to_cm, twip_to_mm


class TestUnits(unittest.TestCase):
    def test_twip_to_mm(self):
        self.assertAlmostEqual(twip_to_mm(567), 10.0, places=2)
        self.assertIsNone(twip_to_mm(None))

    def test_twip_to_cm(self):
        self.assertAlmostEqual(twip_to_cm(567), 1.0, places=3)
        self.assertAlmostEqual(twip_to_cm(720), 1.27, places=2)

    def test_half_point_to_pt(self):
        self.assertEqual(half_point_to_pt(28), 14.0)
        self.assertEqual(half_point_to_pt(30), 15.0)

    def test_line_spacing_auto(self):
        self.assertEqual(line_spacing(240, 'auto', 14), (1.0, False))
        self.assertEqual(line_spacing(360, 'auto', 14), (1.5, False))

    def test_line_spacing_khong_khai(self):
        self.assertEqual(line_spacing(None, None, 14), (None, False))

    def test_line_spacing_thieu_lineRule_coi_nhu_auto(self):
        # w:line có mà w:lineRule không có: Word hiểu là auto
        self.assertEqual(line_spacing(240, None, 14), (1.0, False))

    def test_line_spacing_exact_danh_dau_fixed(self):
        multiple, fixed = line_spacing(240, 'exact', 14)
        self.assertTrue(fixed)
        # 240 twip = 12pt; một dòng đơn của cỡ 14pt xấp xỉ 16.1pt
        self.assertAlmostEqual(multiple, 12 / (14 * 1.15), places=4)

    def test_line_spacing_exact_khong_biet_co_chu(self):
        self.assertEqual(line_spacing(240, 'exact', None), (None, True))
