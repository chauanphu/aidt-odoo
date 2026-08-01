import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class IndexJobCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms.field.mixin bỏ qua template khi test_enable bật, trừ khi có
        # context này — thiếu nó thì thư mục không tự sinh và test fail
        # một cách khó hiểu (xem docs/dms-integration-guide.md).
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch thử nghiệm', 'direction': 'den',
            'secrecy': 'thuong', 'reference': '145/KH-UBND',
        })

    def _add_file(self, name='mau.docx', content=b'noi dung'):
        return self.env['dms.file'].sudo().create({
            'name': name,
            'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(content),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
        })


class TestEnqueue(IndexJobCase):
    def test_tao_file_thi_sinh_job_pending(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(len(job), 1)
        self.assertEqual(job.state, 'pending')

    def test_job_gan_dung_van_ban(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(job.document_id, self.doc)

    def test_co_content_hash(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(len(job.content_hash), 64)

    def test_file_ngoai_aidt_document_khong_sinh_job(self):
        # 'database' (không phải 'attachment'): storage attachment bắt buộc
        # model_id trên thư mục (xem _check_storage_id_attachment_model_id
        # của DMS), thư mục rời ở đây cố tình không gắn với model nào.
        storage = self.env['dms.storage'].sudo().search(
            [('save_type', '=', 'database')], limit=1)
        other = self.env['dms.directory'].sudo().create({
            'name': 'Thư mục rời', 'storage_id': storage.id, 'is_root_directory': True,
        })
        f = self.env['dms.file'].sudo().create({
            'name': 'ngoai.docx', 'directory_id': other.id,
            'content': base64.b64encode(b'x'),
        })
        self.assertFalse(self.env['aidt.index.job'].search([('file_id', '=', f.id)]))

    def test_doi_reference_xep_lai_hang_chi_muc(self):
        f = self._add_file()
        Job = self.env['aidt.index.job']
        Job.search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.write({'reference': '999/KH-UBND'})
        # reference nằm trong contextual header nên đã được embed vào vector;
        # không nạp lại thì header lệch thực tế.
        self.assertTrue(Job.search([('file_id', '=', f.id), ('state', '=', 'pending')]))


class TestDedup(IndexJobCase):
    def test_cung_noi_dung_thi_chep_chunk_khong_goi_ocr(self):
        f1 = self._add_file('mot.docx', b'noi dung giong het')
        Job = self.env['aidt.index.job']
        job1 = Job.search([('file_id', '=', f1.id)])
        self.env['aidt.doc.chunk'].create({
            'document_id': self.doc.id, 'file_id': f1.id, 'seq': 0,
            'text': 'nội dung', 'embed_text': 'nội dung',
        })
        job1.write({'state': 'done'})

        f2 = self._add_file('hai.docx', b'noi dung giong het')
        job2 = Job.search([('file_id', '=', f2.id)])
        with patch.object(type(self.env['aidt.index.pipeline']), 'run') as run:
            job2._cron_process()
            run.assert_not_called()
        self.assertEqual(job2.state, 'done')
        self.assertEqual(
            self.env['aidt.doc.chunk'].search_count([('file_id', '=', f2.id)]), 1)


class TestErrorClassification(IndexJobCase):
    def test_loi_tam_thoi_giu_pending_va_tang_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_transient('service không phản hồi')
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempt, 1)
        self.assertTrue(job.next_retry_at)

    def test_loi_vinh_vien_failed_ngay_khong_tang_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_permanent('định dạng chưa hỗ trợ')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempt, 0)
        self.assertEqual(job.error_kind, 'permanent')

    def test_qua_tran_attempt_thi_thanh_failed(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        for _ in range(3):
            job._mark_transient('timeout')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempt, 3)

    def test_action_retry_dua_ve_pending_va_reset_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_permanent('hỏng')
        job.action_retry()
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempt, 0)
        self.assertFalse(job.error)


class TestClaim(IndexJobCase):
    def test_khong_nhan_job_chua_toi_han_retry(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_transient('timeout')
        self.assertNotIn(job, self.env['aidt.index.job']._claim(limit=10))

    def test_khong_nhan_job_da_done(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job.write({'state': 'done'})
        self.assertNotIn(job, self.env['aidt.index.job']._claim(limit=10))
