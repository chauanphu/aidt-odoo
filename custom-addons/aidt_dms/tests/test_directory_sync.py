from odoo.tests.common import TransactionCase


class TestDirectorySync(TransactionCase):
    """Mỗi văn bản tự sinh 1 dms.directory link theo record."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create(
            {'name': 'ĐV Test DMS', 'unit_type': 'ban'})

    def _new_doc(self, **vals):
        base = {'name': 'VB test', 'department_id': self.dept.id}
        base.update(vals)
        return self.env['aidt.document'].create(base)

    def test_directory_created_and_linked(self):
        doc = self._new_doc()
        self.assertTrue(doc.directory_id)
        self.assertEqual(doc.directory_id.res_model, 'aidt.document')
        self.assertEqual(doc.directory_id.res_id, doc.id)
        root = self.env.ref('aidt_dms.directory_root_aidt')
        self.assertEqual(doc.directory_id.parent_id, root)

    def test_slash_in_reference_is_sanitized(self):
        """Số ký hiệu có '/' không được lọt vào tên directory (check_name)."""
        doc = self._new_doc(reference='01-NQ/TU')
        self.assertNotIn('/', doc.directory_id.name)
        self.assertIn('01-NQ-TU', doc.directory_id.name)

    def _add_file(self, doc, name='tep.txt'):
        import base64
        return self.env['dms.file'].create({
            'name': name,
            'directory_id': doc.directory_id.id,
            'content': base64.b64encode(b'noi dung'),
        })

    def test_file_ids_related(self):
        doc = self._new_doc()
        f = self._add_file(doc)
        self.assertIn(f, doc.file_ids)

    def test_upload_via_content_binary(self):
        """Regression: tạo tệp bằng content_binary (đường của controller upload
        hàng loạt /web/binary/upload_dms_file) trong thư mục attachment-inherit
        của văn bản. Trước fix: KeyError('content') vì _create_model_attachment
        chỉ đọc key 'content'. Sau fix: tạo được + gắn đúng attachment/res_id."""
        doc = self._new_doc(reference='99-CV/VP')
        f = self.env['dms.file'].create({
            'name': 'upload.txt',
            'directory_id': doc.directory_id.id,
            'content_binary': b'noi dung upload',
        })
        self.assertTrue(f.attachment_id)
        self.assertEqual(f.res_model, 'aidt.document')
        self.assertEqual(f.res_id, doc.id)
        self.assertIn(f, doc.file_ids)

    def test_rename_syncs_directory(self):
        doc = self._new_doc(reference='10-BC/VP')
        doc.write({'reference': '11-BC/VP'})
        self.assertIn('11-BC-VP', doc.directory_id.name)

    def test_delete_blocked_when_files_exist(self):
        from odoo.exceptions import UserError
        doc = self._new_doc()
        self._add_file(doc)
        with self.assertRaises(UserError):
            doc.unlink()

    def test_delete_removes_empty_directory(self):
        doc = self._new_doc()
        directory = doc.directory_id
        doc.unlink()
        self.assertFalse(directory.exists())
