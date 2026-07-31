import base64
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAutoFormatCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create({
            'name': 'Phong Format Test',
            'unit_type': 'ban',
        })
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Văn bản kiểm tra tự động thể thức',
            'reference': '999/QD-TU',
            'department_id': cls.dept.id,
        })
        cls.ruleset = cls.env['aidt.format.ruleset'].create({
            'name': 'Bộ luật Test Auto',
            'code': 'TEST-AUTO-01',
            'active': True,
        })

    def test_auto_check_format_without_attachment(self):
        """Verify _auto_check_format sets format_ok=False when no docx attachment is present."""
        self.doc._auto_check_format()
        self.assertFalse(self.doc.format_ok)
        self.assertIn("Chưa có tệp đính kèm .docx", self.doc.format_note or "")

    def test_attachment_create_triggers_auto_format_check(self):
        """Verify uploading a docx attachment automatically triggers format check and updates document status."""
        attachment = self.env['ir.attachment'].create({
            'name': 'van_ban_test.docx',
            'datas': base64.b64encode(b"dummy docx content"),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        self.assertTrue(self.doc.format_note, "Document format_note should be updated after docx upload")
