import io
import unittest

import docx
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH

import fixtures
from aidt_format_engine.parser import parse_docx
from aidt_format_engine.zones import ZONES, detect_zones


def _prepare(blob):
    return detect_zones(parse_docx(blob))


def _zones_of(doc):
    return {p.zone for p in doc.paras if p.text.strip()}


class TestZoneTheoStyle(unittest.TestCase):
    def test_moi_vung_nhan_dien_qua_style(self):
        doc = _prepare(fixtures.chuan_66())
        self.assertEqual(
            _zones_of(doc),
            {'tieu_de_dang', 'so_ky_hieu', 'trich_yeu', 'noi_dung',
             'noi_nhan', 'chu_ky'})

    def test_confidence_la_style_cho_moi_doan_co_chu(self):
        doc = _prepare(fixtures.chuan_66())
        for para in doc.paras:
            if para.text.strip():
                self.assertEqual(para.zone_confidence, 'style',
                                 'đoạn %d' % para.index)

    def test_moi_zone_deu_nam_trong_ZONES(self):
        doc = _prepare(fixtures.chuan_66())
        for para in doc.paras:
            self.assertIn(para.zone, ZONES)

    def test_style_thang_ca_khi_heuristic_noi_khac(self):
        """Đoạn mang style VB_NoiNhan nhưng chữ khớp mẫu số ký hiệu.

        Heuristic sẽ đoán 'so_ky_hieu'; style phải thắng. Đây là chỗ duy nhất
        hai đường cho câu trả lời khác nhau, nên là chỗ duy nhất chứng minh
        được đường nào có quyền cao hơn.
        """
        document = docx.Document()
        style = document.styles.add_style('VB_NoiNhan', WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = 'Times New Roman'
        document.add_paragraph('Số: 99-CV/TU', style='VB_NoiNhan')

        buffer = io.BytesIO()
        document.save(buffer)
        doc = detect_zones(parse_docx(buffer.getvalue()))

        khop = [p for p in doc.paras if p.text.strip() == 'Số: 99-CV/TU']
        self.assertEqual(len(khop), 1)
        self.assertEqual(khop[0].zone, 'noi_nhan',
                         'style phải thắng heuristic khi hai bên nói khác nhau')
        self.assertEqual(khop[0].zone_confidence, 'style')


class TestZoneHeuristic(unittest.TestCase):
    def test_gan_dung_khi_khong_co_style(self):
        doc = _prepare(fixtures.khong_co_style())
        by_zone = {}
        for para in doc.paras:
            if para.text.strip():
                by_zone.setdefault(para.zone, []).append(para.text)
        self.assertIn('tieu_de_dang', by_zone)
        self.assertIn('so_ky_hieu', by_zone)
        self.assertIn('trich_yeu', by_zone)
        self.assertIn('noi_nhan', by_zone)
        self.assertIn('chu_ky', by_zone)

    def test_confidence_la_heuristic(self):
        doc = _prepare(fixtures.khong_co_style())
        for para in doc.paras:
            if para.text.strip():
                self.assertEqual(para.zone_confidence, 'heuristic')

    def test_so_ky_hieu_khop_ca_dau_gach_va_gach_cheo(self):
        doc = _prepare(fixtures.khong_co_style())
        so = [p for p in doc.paras if p.zone == 'so_ky_hieu']
        self.assertEqual(len(so), 1)
        self.assertIn('456-BC/TU', so[0].text)


class TestZoneTrongBang(unittest.TestCase):
    def test_tieu_de_dang_va_so_ky_hieu_nhan_dien_du_nam_trong_bang(self):
        """C1: khối đầu trang dựng bằng bảng — style vẫn phải thắng, dù đoạn
        nằm trong ô bảng chứ không phải paragraph rời của body."""
        doc = _prepare(fixtures.vb_that_dau_trang_bang())
        zones = _zones_of(doc)
        self.assertIn('tieu_de_dang', zones)
        self.assertIn('so_ky_hieu', zones)


class TestTrichYeuVeViec(unittest.TestCase):
    def test_ve_viec_nhan_dien_la_trich_yeu(self):
        """C2: 'Về việc ...' (văn bản có tên loại) phải được heuristic nhận
        là trich_yeu, y hệt 'V/v ...' (công văn)."""
        doc = _prepare(fixtures.vb_that_co_ten_loai())
        self.assertIn('trich_yeu', _zones_of(doc))
        trich_yeu = [p for p in doc.paras if p.zone == 'trich_yeu']
        self.assertEqual(len(trich_yeu), 1)
        self.assertTrue(trich_yeu[0].text.startswith('Về việc'))
        self.assertEqual(trich_yeu[0].zone_confidence, 'heuristic')


class TestTieuDeDangKhongTuMauThuan(unittest.TestCase):
    def test_can_phai_khong_con_duoc_nhan_la_tieu_de_dang(self):
        """I6: heuristic từng nhận align center HOẶC right cho tiêu đề Đảng,
        trong khi bộ luật chỉ cho phép center — tự phát hiện rồi tự phạt.
        Sau khi thu hẹp điều kiện, đoạn căn phải không còn được gán zone
        này (rơi về noi_dung mặc định), nên không còn tự mâu thuẫn."""
        document = docx.Document()
        paragraph = document.add_paragraph(fixtures.TIEU_DE_DANG)
        paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        buffer = io.BytesIO()
        document.save(buffer)
        doc = detect_zones(parse_docx(buffer.getvalue()))

        khop = [p for p in doc.paras if p.text == fixtures.TIEU_DE_DANG][0]
        self.assertNotEqual(khop.zone, 'tieu_de_dang')

    def test_can_giua_van_duoc_nhan_la_tieu_de_dang(self):
        """Đối chứng: center vẫn phải nhận diện được như trước."""
        document = docx.Document()
        paragraph = document.add_paragraph(fixtures.TIEU_DE_DANG)
        paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

        buffer = io.BytesIO()
        document.save(buffer)
        doc = detect_zones(parse_docx(buffer.getvalue()))

        khop = [p for p in doc.paras if p.text == fixtures.TIEU_DE_DANG][0]
        self.assertEqual(khop.zone, 'tieu_de_dang')


class TestStandardHint(unittest.TestCase):
    def test_tieu_de_dang_suy_ra_dang(self):
        self.assertEqual(_prepare(fixtures.chuan_66()).standard_hint, 'dang')

    def test_quoc_hieu_suy_ra_hanh_chinh(self):
        self.assertEqual(
            _prepare(fixtures.chuan_nd30()).standard_hint, 'hanh_chinh')


if __name__ == '__main__':
    unittest.main()
