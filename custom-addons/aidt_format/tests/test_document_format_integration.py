import base64
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestDocumentFormatIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create({
            'name': 'Phong Thuc Thi Test',
            'unit_type': 'ban',
        })
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Văn bản test thể thức',
            'reference': '123/QD-TU',
            'department_id': cls.dept.id,
        })

    def test_action_check_format_without_attachment_raises_error(self):
        """Verify calling action_check_format without docx attachment raises UserError."""
        with self.assertRaises(UserError):
            self.doc.action_check_format()

    def test_action_check_format_with_attachment_returns_action(self):
        """Verify calling action_check_format with docx attachment returns wizard action."""
        self.env['ir.attachment'].create({
            'name': 'test_doc.docx',
            'datas': base64.b64encode(b"dummy docx content"),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        action = self.doc.action_check_format()
        self.assertEqual(action['res_model'], 'aidt.format.check.wizard')
        self.assertEqual(action['target'], 'new')
