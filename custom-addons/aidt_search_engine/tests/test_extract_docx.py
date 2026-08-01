import io
import unittest

import docx

from aidt_search_engine.extract.docx import extract_docx


def _build(lines):
    d = docx.Document()
    for text in lines:
        d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class TestExtractDocx(unittest.TestCase):
    def test_tra_ve_block_cho_moi_doan_co_chu(self):
        blob = _build(["ĐẢNG CỘNG SẢN VIỆT NAM", "Số: 145-KH/TU", "Nội dung."])
        blocks = extract_docx(blob)
        self.assertEqual([b.text for b in blocks],
                         ["ĐẢNG CỘNG SẢN VIỆT NAM", "Số: 145-KH/TU", "Nội dung."])

    def test_bo_qua_doan_rong(self):
        self.assertEqual(len(extract_docx(_build(["Có chữ.", "", "   "]))), 1)

    def test_co_gan_zone(self):
        blocks = extract_docx(_build(["Số: 145-KH/TU", "Nơi nhận:"]))
        self.assertTrue(all(b.zone for b in blocks))

    def test_docx_khong_co_bbox_va_page(self):
        # DOCX không có toạ độ; highlight cho nhánh này dựa vào ts_headline.
        for b in extract_docx(_build(["Nội dung."])):
            self.assertIsNone(b.bbox)
            self.assertIsNone(b.page)

    def test_tep_hong_nem_loi(self):
        from aidt_search_engine.extract.docx import UnreadableDocx
        with self.assertRaises(UnreadableDocx):
            extract_docx(b"khong phai docx")


if __name__ == "__main__":
    unittest.main()
