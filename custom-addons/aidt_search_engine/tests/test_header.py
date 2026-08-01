import unittest

from aidt_search_engine.header import build_embed_text, build_header
from aidt_search_engine.types import DocMeta

FULL = DocMeta(
    doc_type_label="Kế hoạch",
    reference="145/KH-UBND",
    title="Kế hoạch bảo đảm an toàn thông tin năm 2026",
)


class TestBuildHeader(unittest.TestCase):
    def test_day_du_hai_dong(self):
        self.assertEqual(
            build_header(FULL, "Phần II › Mục 3"),
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026\n"
            "Phần II › Mục 3",
        )

    def test_khong_co_duong_dan_muc_thi_chi_mot_dong(self):
        self.assertEqual(
            build_header(FULL, ""),
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026",
        )

    def test_thieu_so_ky_hieu(self):
        meta = DocMeta(doc_type_label="Công văn", title="Về việc phối hợp")
        self.assertEqual(build_header(meta, ""), "Công văn — Về việc phối hợp")

    def test_chi_co_trich_yeu(self):
        self.assertEqual(build_header(DocMeta(title="Về việc phối hợp"), ""),
                         "Về việc phối hợp")

    def test_metadata_rong_tra_chuoi_rong(self):
        self.assertEqual(build_header(DocMeta(), ""), "")


class TestBuildEmbedText(unittest.TestCase):
    def test_ghep_header_va_noi_dung(self):
        out = build_embed_text(FULL, "Điều 7", "Các sở, ban, ngành có trách nhiệm...")
        self.assertEqual(
            out,
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026\n"
            "Điều 7\n---\nCác sở, ban, ngành có trách nhiệm...",
        )

    def test_khong_co_header_thi_khong_co_dau_phan_cach(self):
        # Không được để chunk mở đầu bằng '---' trơ trọi: nó sẽ được embed
        # như một token vô nghĩa ở vị trí quan trọng nhất của chuỗi.
        self.assertEqual(build_embed_text(DocMeta(), "", "nội dung"), "nội dung")


if __name__ == "__main__":
    unittest.main()
