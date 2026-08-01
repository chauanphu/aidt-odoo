import base64

from odoo.tests.common import TransactionCase


class TestDocumentBadges(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Văn bản thử', 'direction': 'den', 'secrecy': 'thuong'})

    def _file(self):
        return self.env['dms.file'].sudo().create({
            'name': 'a.docx', 'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(b'x'),
            'res_model': 'aidt.document', 'res_id': self.doc.id})

    def test_chua_co_tep_thi_none(self):
        self.assertEqual(self.doc.index_state, 'none')

    def test_co_job_pending_thi_pending(self):
        self._file()
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'pending')

    def test_job_done_thi_indexed(self):
        f = self._file()
        self.env['aidt.index.job'].search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'indexed')

    def test_job_failed_thi_failed(self):
        f = self._file()
        self.env['aidt.index.job'].search([('file_id', '=', f.id)]).write({'state': 'failed'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'failed')

    def test_dem_chunk(self):
        f = self._file()
        self.env['aidt.doc.chunk'].create({
            'document_id': self.doc.id, 'file_id': f.id, 'seq': 0,
            'text': 'a', 'embed_text': 'a'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.chunk_count, 1)

    def test_action_reindex_xep_lai_hang(self):
        f = self._file()
        Job = self.env['aidt.index.job']
        Job.search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.action_reindex()
        self.assertTrue(Job.search([('file_id', '=', f.id), ('state', '=', 'pending')]))
