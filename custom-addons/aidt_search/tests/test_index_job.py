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
        with patch.object(type(self.env['aidt.index.pipeline']), '_run') as run:
            job2._cron_process()
            run.assert_not_called()
        self.assertEqual(job2.state, 'done')
        self.assertEqual(
            self.env['aidt.doc.chunk'].search_count([('file_id', '=', f2.id)]), 1)


class TestDedupRaceInFlight(IndexJobCase):
    """Đua enqueue khi job hiện có đã bị claim (qua khỏi 'pending'). Trước
    khi sửa: `_enqueue_file` ghi đè content_hash vô điều kiện, nên job vẫn
    hoàn tất với chunk của nội dung CŨ nhưng lại mang hash của nội dung
    MỚI — hậu quả không cục bộ: một tệp khác thực sự có nội dung trùng hash
    mới sẽ bị `_copy_chunks_from_twin` gán NHẦM chunk cũ đó."""

    def test_dua_noi_dung_khi_dang_xu_ly_dua_job_ve_pending_voi_hash_moi(self):
        f = self._add_file('a.docx', b'noi dung cu')
        Job = self.env['aidt.index.job']
        job = Job.search([('file_id', '=', f.id)])
        old_hash = job.content_hash
        # Giả lập: worker khác đã claim job này và đang xử lý dở.
        job.write({'state': 'extracting'})

        # Đua: nội dung tệp đổi trong lúc job còn dở dang.
        f.write({'content': base64.b64encode(b'noi dung moi khac han')})

        # Không được sinh job thứ hai — vẫn đúng một job đang hoạt động.
        self.assertEqual(
            self.env['aidt.index.job'].search_count([('file_id', '=', f.id)]), 1)
        # Job phải bị đưa lại 'pending' để xử lý đúng nội dung mới, KHÔNG
        # được âm thầm mang hash mới trong khi vẫn coi như đang xử lý dở
        # nội dung cũ — nếu không, nó sẽ _mark_done với chunk của nội dung
        # cũ dưới cái tên (hash) của nội dung mới.
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempt, 0)
        self.assertNotEqual(job.content_hash, old_hash)

    def test_dua_khi_dang_xu_ly_khong_lam_twin_copy_gan_nham_chunk_cu(self):
        Job = self.env['aidt.index.job']
        Chunk = self.env['aidt.doc.chunk']

        # job1: đã done, có chunk thật, cùng nội dung với job2 bên dưới.
        f1 = self._add_file('cu.docx', b'noi dung cu')
        job1 = Job.search([('file_id', '=', f1.id)])
        Chunk.create({
            'document_id': self.doc.id, 'file_id': f1.id, 'seq': 0,
            'text': 'chunk cu', 'embed_text': 'chunk cu',
        })
        job1.write({'state': 'done'})

        # job2: cùng nội dung CŨ với job1 (trùng hash), đang xử lý dở.
        f2 = self._add_file('dang_xu_ly.docx', b'noi dung cu')
        job2 = Job.search([('file_id', '=', f2.id)])
        job2.write({'state': 'extracting'})

        # Đua: nội dung f2 đổi sang nội dung MỚI trong lúc job2 còn dở dang.
        f2.write({'content': base64.b64encode(b'noi dung moi')})
        self.assertEqual(job2.state, 'pending')

        # job2 hoàn tất (giả lập) với chunk ĐÚNG của nội dung MỚI.
        Chunk.create({
            'document_id': self.doc.id, 'file_id': f2.id, 'seq': 0,
            'text': 'chunk moi', 'embed_text': 'chunk moi',
        })
        job2.write({'state': 'done'})

        # f3 có nội dung thật sự trùng với nội dung MỚI — phải được chép
        # đúng chunk 'chunk moi' của job2, KHÔNG phải 'chunk cu' của job1.
        f3 = self._add_file('ba.docx', b'noi dung moi')
        job3 = Job.search([('file_id', '=', f3.id)])
        self.assertTrue(job3._copy_chunks_from_twin())
        copied = Chunk.search([('file_id', '=', f3.id)])
        self.assertEqual(copied.text, 'chunk moi')


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
