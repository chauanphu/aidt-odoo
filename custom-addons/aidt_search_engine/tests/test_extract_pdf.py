import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidt_search_engine.extract.pdf import (
    DEFAULT_DPI,
    PdfToolError,
    page_count,
    page_text,
    render_page_png,
)

HAS_POPPLER = all(shutil.which(t) for t in ("pdfinfo", "pdftotext", "pdftoppm"))


def _make_pdf(path, pages_text):
    """Dựng PDF nhiều trang bằng LibreOffice nếu có, không thì bỏ qua test."""
    src = path.with_suffix(".txt")
    src.write_text("\f".join(pages_text), encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(path.parent), str(src)],
        check=True, capture_output=True, timeout=120,
    )
    return src.with_suffix(".pdf")


@unittest.skipUnless(HAS_POPPLER, "cần poppler-utils")
@unittest.skipUnless(shutil.which("soffice"), "cần libreoffice để dựng PDF mẫu")
class TestPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = _make_pdf(Path(cls.tmp.name) / "mau.txt",
                            ["Trang một hỗ trợ hộ nghèo", "Trang hai an toàn thông tin"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_dem_so_trang(self):
        self.assertEqual(page_count(str(self.pdf)), 2)

    def test_doc_text_dung_trang(self):
        self.assertIn("hộ nghèo", page_text(str(self.pdf), 1))
        self.assertNotIn("hộ nghèo", page_text(str(self.pdf), 2))

    def test_render_ra_png(self):
        data = render_page_png(str(self.pdf), 1, dpi=DEFAULT_DPI)
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertGreater(len(data), 1000)


class TestPdfErrors(unittest.TestCase):
    def test_tep_khong_ton_tai_nem_pdftoolerror(self):
        with self.assertRaises(PdfToolError):
            page_count("/khong/co/tep.pdf")


if __name__ == "__main__":
    unittest.main()
