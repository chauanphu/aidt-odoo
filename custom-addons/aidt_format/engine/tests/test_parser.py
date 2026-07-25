import unittest

import fixtures
from engine.parser import UnreadableDocx, parse_docx


class TestParser(unittest.TestCase):
    def test_le_trang_doc_dung(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertAlmostEqual(doc.pages.margin_mm['top'], 22.0, places=1)
        self.assertAlmostEqual(doc.pages.margin_mm['left'], 32.0, places=1)
        self.assertAlmostEqual(doc.pages.width_mm, 210.0, places=1)
        self.assertAlmostEqual(doc.pages.height_mm, 297.0, places=1)

    def test_le_sai_doc_ra_gia_tri_sai(self):
        doc = parse_docx(fixtures.sai_le_trang())
        self.assertAlmostEqual(doc.pages.margin_mm['top'], 10.0, places=1)

    def test_moi_doan_co_style_name_va_dinh_dang(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertGreater(len(doc.paras), 5)
        noi_dung = [p for p in doc.paras if p.style_name == 'VB_NoiDung']
        self.assertTrue(noi_dung)
        self.assertEqual(noi_dung[0].fmt.font, 'Times New Roman')
        self.assertEqual(noi_dung[0].fmt.size_pt, 14.0)
        self.assertEqual(noi_dung[0].fmt.align, 'justify')

    def test_index_bat_dau_tu_0_va_lien_tuc(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual([p.index for p in doc.paras],
                         list(range(len(doc.paras))))

    def test_runs_conflict_bat_dung_cho(self):
        doc = parse_docx(fixtures.run_lech_nhau())
        lech = [p for p in doc.paras if p.runs_conflict]
        self.assertEqual(len(lech), 1, 'chỉ đúng một đoạn được đánh dấu lệch')
        self.assertIn('cỡ 11', lech[0].text)

    def test_runs_conflict_khong_bat_oan(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual([p for p in doc.paras if p.runs_conflict], [])

    def test_dinh_dang_lay_tu_run_dai_nhat(self):
        """Một từ lạc cỡ không được quyết định định dạng của cả đoạn."""
        doc = parse_docx(fixtures.run_lech_nhau())
        lech = [p for p in doc.paras if p.runs_conflict][0]
        self.assertEqual(lech.fmt.size_pt, 14.0)

    def test_standard_hint_chua_duoc_dien_o_tang_parser(self):
        self.assertIsNone(parse_docx(fixtures.chuan_66()).standard_hint)

    def test_zone_chua_duoc_dien_o_tang_parser(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual({p.zone for p in doc.paras}, {None})

    def test_file_hong_bao_UnreadableDocx(self):
        with self.assertRaises(UnreadableDocx):
            parse_docx(fixtures.hong())


if __name__ == '__main__':
    unittest.main()
