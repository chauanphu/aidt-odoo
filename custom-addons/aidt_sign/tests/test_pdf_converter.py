import unittest
from odoo.addons.aidt_sign.services.pdf_converter import convert_to_pdf

class TestPdfConverter(unittest.TestCase):
    def test_pdf_already_returns_same(self):
        content = b"%PDF-1.4 sample content"
        res = convert_to_pdf(content, "document.pdf")
        self.assertEqual(res, content)

    def test_empty_content_raises_value_error(self):
        with self.assertRaises(ValueError):
            convert_to_pdf(b"", "test.docx")

if __name__ == '__main__':
    unittest.main()
