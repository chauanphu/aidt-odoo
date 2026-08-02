import base64
from unittest.mock import patch

import psycopg2

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


class TestDedupKhongVuotRanhGioiBaoMat(TransactionCase):
    """C-1: dedup không được chép danh tính văn bản qua ranh giới độ mật.

    `_copy_chunks_from_twin` từng gọi `chunk.copy()`, mà `embed_text` là một
    `fields.Text` bình thường nên `copy=True` mặc định. `embed_text` có dạng
    '{loại} {số hiệu} — {trích yếu}\\n{mục}\\n---\\n{text}': chép nguyên là
    chép cả TRÍCH YẾU và SỐ HIỆU của văn bản nguồn.

    Kịch bản: cùng một tệp (trùng byte -> trùng content_hash) đính vào văn bản
    'thường' và văn bản 'tuyệt mật' — đúng ca lặp mà dedup sinh ra để phục vụ.
    Văn bản mật chỉ mục trước, văn bản thường dedup từ nó. `aidt.doc.chunk` cho
    Chuyên viên quyền đọc và `rule_aidt_doc_chunk_secrecy` giới hạn theo độ mật
    của văn bản THƯỜNG, nên một `read()` RPC tầm thường là lấy được tên + số
    hiệu của văn bản vượt clearance.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Dedup', 'unit_type': 'phong'})
        cls.user_thuong = cls.env['res.users'].create({
            'name': 'canbo_dedup', 'login': 'canbo_dedup',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_dedup', 'department_id': cls.dept.id,
            'user_id': cls.user_thuong.id})
        cls.user_thuong.write({'clearance_level': 0})

        cls.SECRET_TITLE = 'Phương án bảo vệ mục tiêu trọng yếu'
        cls.SECRET_REF = '777/PA-BCA'
        cls.doc_mat = cls.env['aidt.document'].create({
            'name': cls.SECRET_TITLE, 'direction': 'den', 'secrecy': 'tuyet_mat',
            'department_id': cls.dept.id, 'doc_type': 'ke_hoach',
            'reference': cls.SECRET_REF,
        })
        cls.doc_thuong = cls.env['aidt.document'].create({
            'name': 'Kế hoạch công khai', 'direction': 'den', 'secrecy': 'thuong',
            'department_id': cls.dept.id, 'doc_type': 'ke_hoach',
            'reference': '100/KH-UBND',
        })

    def _add_file(self, doc, name, content):
        return self.env['dms.file'].sudo().create({
            'name': name, 'directory_id': doc.directory_id.id,
            'content': base64.b64encode(content),
            'res_model': 'aidt.document', 'res_id': doc.id,
        })

    def test_khong_dedup_qua_ranh_gioi_do_mat(self):
        Job = self.env['aidt.index.job']
        Chunk = self.env['aidt.doc.chunk']
        same_bytes = b'noi dung trung byte giua hai van ban'

        f_mat = self._add_file(self.doc_mat, 'mat.docx', same_bytes)
        job_mat = Job.search([('file_id', '=', f_mat.id)])
        Chunk.create({
            'document_id': self.doc_mat.id, 'file_id': f_mat.id, 'seq': 0,
            'text': 'nội dung thân bài hoàn toàn giống nhau',
            'embed_text': 'Kế hoạch %s — %s\n---\nnội dung thân bài hoàn '
                          'toàn giống nhau' % (self.SECRET_REF, self.SECRET_TITLE),
        })
        job_mat.write({'state': 'done'})

        f_thuong = self._add_file(self.doc_thuong, 'thuong.docx', same_bytes)
        job_thuong = Job.search([('file_id', '=', f_thuong.id)])
        self.assertEqual(job_thuong.content_hash, job_mat.content_hash,
                         'điều kiện tiên quyết của test: hai tệp phải trùng hash')

        self.assertFalse(
            job_thuong._copy_chunks_from_twin(),
            'dedup phải TỪ CHỐI khi văn bản nguồn khác độ mật')

    def test_khong_the_lay_lai_tieu_de_hay_so_hieu_mat_tu_bat_ky_truong_nao(self):
        """Khẳng định thật sự quan trọng: đọc MỌI trường đọc được của
        aidt.doc.chunk dưới quyền người chỉ được xem văn bản 'thường' cũng
        không moi ra được trích yếu hay số hiệu của văn bản 'tuyệt mật'."""
        Job = self.env['aidt.index.job']
        Chunk = self.env['aidt.doc.chunk']
        same_bytes = b'noi dung trung byte giua hai van ban'

        f_mat = self._add_file(self.doc_mat, 'mat2.docx', same_bytes)
        job_mat = Job.search([('file_id', '=', f_mat.id)])
        Chunk.create({
            'document_id': self.doc_mat.id, 'file_id': f_mat.id, 'seq': 0,
            'text': 'nội dung thân bài hoàn toàn giống nhau',
            'embed_text': 'Kế hoạch %s — %s\n---\nnội dung thân bài hoàn '
                          'toàn giống nhau' % (self.SECRET_REF, self.SECRET_TITLE),
        })
        job_mat.write({'state': 'done'})

        f_thuong = self._add_file(self.doc_thuong, 'thuong2.docx', same_bytes)
        job_thuong = Job.search([('file_id', '=', f_thuong.id)])
        job_thuong._process_one()

        ChunkAsUser = self.env['aidt.doc.chunk'].with_user(self.user_thuong)
        readable = [name for name, field in ChunkAsUser._fields.items()
                    if field.store and not field.compute]
        leaked = []
        for row in ChunkAsUser.search_read([], readable):
            blob = ' '.join(str(v) for v in row.values())
            if self.SECRET_TITLE in blob or self.SECRET_REF in blob:
                leaked.append(row.get('id'))
        self.assertFalse(
            leaked,
            'chunk %s để lộ trích yếu/số hiệu của văn bản tuyệt mật cho người '
            'chỉ có clearance đọc văn bản thường' % leaked)

    def test_cung_do_mat_khac_header_thi_dung_lai_embed_text_cua_chinh_minh(self):
        """Cùng độ mật + cùng đơn vị nhưng khác trích yếu/số hiệu: vẫn được
        dedup (tiết kiệm bước trích xuất), nhưng `embed_text` phải dựng lại từ
        metadata của CHÍNH văn bản này rồi embed lại — không chép của văn bản
        kia."""
        Job = self.env['aidt.index.job']
        Chunk = self.env['aidt.doc.chunk']
        other = self.env['aidt.document'].create({
            'name': 'Kế hoạch khác hẳn tên', 'direction': 'den',
            'secrecy': 'thuong', 'department_id': self.dept.id,
            'doc_type': 'ke_hoach', 'reference': '200/KH-UBND',
        })
        same_bytes = b'noi dung trung byte khac header'

        f1 = self._add_file(other, 'a.docx', same_bytes)
        job1 = Job.search([('file_id', '=', f1.id)])
        Chunk.create({
            'document_id': other.id, 'file_id': f1.id, 'seq': 0,
            'text': 'thân bài dùng chung',
            'embed_text': 'Kế hoạch 200/KH-UBND — Kế hoạch khác hẳn tên\n---\n'
                          'thân bài dùng chung',
        })
        job1.write({'state': 'done'})

        f2 = self._add_file(self.doc_thuong, 'b.docx', same_bytes)
        job2 = Job.search([('file_id', '=', f2.id)])
        with patch.object(type(self.env['aidt.embed.client']), '_embed',
                          return_value=[[0.01] * 1024]) as embed:
            self.assertTrue(job2._copy_chunks_from_twin())
            embed.assert_called_once()

        copied = Chunk.search([('file_id', '=', f2.id)])
        self.assertEqual(copied.text, 'thân bài dùng chung',
                         'phần nội dung vẫn phải được tái sử dụng')
        self.assertNotIn('Kế hoạch khác hẳn tên', copied.embed_text)
        self.assertNotIn('200/KH-UBND', copied.embed_text)
        self.assertIn('Kế hoạch công khai', copied.embed_text)
        self.assertIn('100/KH-UBND', copied.embed_text)


class TestJobHongKhongKetHangDoi(IndexJobCase):
    """I-1: một job hỏng ở TẦNG CSDL từng làm kẹt vĩnh viễn cả hàng đợi.

    Không có savepoint, cursor rơi vào InFailedSqlTransaction, nên chính
    `_mark_transient` cũng ném tiếp — lỗi thứ hai thoát khỏi `_process_one`
    lẫn vòng `while` của `_cron_process`. State ở lại 'pending', attempt ở lại
    0 (trần retry không bao giờ chạm), và `_claim()` sắp theo `id` nên đúng job
    đó lại được nhận đầu tiên ở mọi nhịp cron — mọi job phía sau chết đói.
    """

    def _db_error(self, *args, **kwargs):
        # Lỗi TẦNG CSDL thật: cursor hỏng sau câu này, không phải một
        # Exception Python vô hại.
        self.env.cr.execute("SELECT 1 FROM bang_khong_ton_tai_bao_gio")

    def test_loi_csdl_van_ghi_duoc_trang_thai_that_bai(self):
        f = self._add_file('hong.docx', b'noi dung hong')
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        with patch.object(type(self.env['aidt.index.pipeline']), '_run',
                          side_effect=self._db_error):
            job._process_one()
        self.assertEqual(job.attempt, 1, 'phải ghi nhận được một lần thử hỏng')
        self.assertEqual(job.error_kind, 'transient')
        self.assertTrue(job.error)

    def test_job_hong_khong_chan_job_phia_sau(self):
        f_bad = self._add_file('hong.docx', b'noi dung hong')
        f_ok = self._add_file('tot.docx', b'noi dung tot')
        Job = self.env['aidt.index.job']
        job_bad = Job.search([('file_id', '=', f_bad.id)])
        job_ok = Job.search([('file_id', '=', f_ok.id)])
        self.assertLess(job_bad.id, job_ok.id,
                        'điều kiện tiên quyết: job hỏng phải được _claim trước')

        calls = []

        def run(pipeline, job):
            if job.id == job_bad.id:
                self.env.cr.execute("SELECT 1 FROM bang_khong_ton_tai_bao_gio")
            calls.append(job.id)
            job._mark_done({})

        with patch.object(type(self.env['aidt.index.pipeline']), '_run',
                          autospec=True, side_effect=run):
            Job._cron_process(limit=5)

        self.assertIn(job_ok.id, calls,
                      'job phía sau vẫn phải được xử lý dù job trước hỏng')
        self.assertEqual(job_ok.state, 'done')
        self.assertNotEqual(
            (job_bad.state, job_bad.attempt), ('pending', 0),
            'job hỏng phải để lại dấu vết (attempt tăng hoặc failed), nếu không '
            '_claim() sẽ nhận lại nó mãi mãi')


class TestEnqueueRaceVaFkViolation(IndexJobCase):
    def test_fk_violation_khong_bi_doc_nham_thanh_dua_dedup(self):
        """M-2: chỉ cú va đúng chỉ mục UNIQUE riêng phần mới được nuốt."""
        f = self._add_file()
        Job = self.env['aidt.index.job']
        with self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                Job.sudo().create({
                    'document_id': 0x7FFFFFF0,   # không tồn tại -> vi phạm FK
                    'file_id': f.id, 'state': 'pending',
                })

    def test_job_hoat_dong_kip_ve_done_thi_tao_lai_chu_khong_danh_roi(self):
        """M-1: job đang hoạt động về 'done' giữa lúc create hỏng và lúc tìm
        lại -> phải tạo job mới, không được im lặng đánh rơi nội dung mới."""
        f = self._add_file('doi.docx', b'noi dung mot')
        Job = self.env['aidt.index.job']
        Job.search([('file_id', '=', f.id)]).write({'state': 'done'})
        job = Job._enqueue_file(f)
        self.assertTrue(job, '_enqueue_file phải trả về job, không phải rỗng')
        self.assertEqual(job.state, 'pending')
