import unittest

from aidt_search_engine._compat import fe_parser, fe_types, fe_zones
from aidt_search_engine.types import Block, Candidate, Chunk, DocMeta, ParsedQuery


class TestCompat(unittest.TestCase):
    def test_import_duoc_format_engine(self):
        self.assertTrue(hasattr(fe_parser, "parse_docx"))
        self.assertTrue(hasattr(fe_zones, "detect_zones"))
        self.assertTrue(hasattr(fe_types, "Para"))

    def test_zones_co_du_12_vung(self):
        self.assertEqual(len(fe_zones.ZONES), 12)
        self.assertIn("trich_yeu", fe_zones.ZONES)
        self.assertIn("noi_nhan", fe_zones.ZONES)


class TestTypes(unittest.TestCase):
    def test_block_mac_dinh(self):
        b = Block(text="xin chào")
        self.assertIsNone(b.zone)
        self.assertIsNone(b.bbox)

    def test_chunk_va_docmeta_khoi_tao_duoc(self):
        c = Chunk(seq=0, text="a", embed_text="b")
        self.assertEqual(c.heading_path, "")
        self.assertEqual(DocMeta().reference, None)

    def test_parsedquery_filters_khong_dung_chung(self):
        a, b = ParsedQuery(raw="x", semantic="x"), ParsedQuery(raw="y", semantic="y")
        a.filters.append("z")
        self.assertEqual(b.filters, [])

    def test_candidate_score_mac_dinh(self):
        self.assertEqual(Candidate(chunk_id=1, document_id=2).score, 0.0)


if __name__ == "__main__":
    unittest.main()
