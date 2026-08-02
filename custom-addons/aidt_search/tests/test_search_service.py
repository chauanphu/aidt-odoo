from unittest.mock import patch

from odoo.tests.common import TransactionCase

DIM = 1024


class TestSearchService(TransactionCase):
    """Định tuyến ý định, ba kênh, RRF, gom về văn bản và giảm cấp mềm.

    Mọi truy vấn chạy dưới một user THẬT (không phải superuser) để ir.rule
    luôn có mặt trên đường đi — test chức năng mà chạy bằng superuser thì
    đường SQL được kiểm chính là đường không ai dùng trong thực tế.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Kiểm thử tìm kiếm', 'unit_type': 'phong'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_tk', 'login': 'canbo_tk',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_tk', 'department_id': cls.dept.id, 'user_id': cls.user.id})
        cls.user.write({'clearance_level': 3})

        cls.doc = cls._make_doc('Kế hoạch hỗ trợ hộ nghèo', 'ke_hoach', '145/KH-UBND')
        cls.other = cls._make_doc('Công văn đôn đốc tiến độ', 'cong_van', '185/CV-STTTT')
        for seq in range(5):
            cls._make_chunk(cls.doc, seq,
                            'Bố trí kinh phí hỗ trợ hộ nghèo trên địa bàn tỉnh '
                            'đợt %s theo kế hoạch đã duyệt.' % seq)
        cls._make_chunk(cls.other, 0, 'Đôn đốc tiến độ báo cáo quý.')

    @classmethod
    def _make_doc(cls, name, doc_type, reference):
        return cls.env['aidt.document'].create({
            'name': name, 'direction': 'den', 'secrecy': 'thuong',
            'department_id': cls.dept.id, 'doc_type': doc_type,
            'reference': reference,
        })

    @classmethod
    def _make_chunk(cls, doc, seq, text):
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': doc.id, 'seq': seq, 'text': text, 'embed_text': text,
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))
        return chunk

    def _service(self):
        return self.env['aidt.search.service'].with_user(self.user)

    def _search(self, query, **kwargs):
        with patch.object(type(self.env['aidt.embed.client']), '_embed',
                          return_value=[[0.01] * DIM]):
            return self._service().search(query, **kwargs)

    # ------------------------------------------------------------------ #
    # Định tuyến ý định
    # ------------------------------------------------------------------ #
    def test_tra_cuu_so_hieu_tra_thang_van_ban(self):
        result = self._search('145/KH-UBND')
        self.assertEqual(result['reference'], '145/KH-UBND')
        self.assertEqual([d['id'] for d in result['documents']], [self.doc.id])
        # Nhánh số hiệu bỏ qua tầng ngữ nghĩa nên không kênh nào chạy.
        self.assertEqual(result['channels_used'], [])

    def test_so_hieu_khong_ton_tai_tra_rong_chu_khong_no(self):
        result = self._search('777/QD-XYZ')
        self.assertEqual(result['documents'], [])
        self.assertEqual(result['total'], 0)

    def test_boc_filter_cung_ra_khoi_cau(self):
        result = self._search('văn bản kế hoạch về hỗ trợ hộ nghèo năm 2025')
        fields_ = {f['field'] for f in result['filters']}
        self.assertIn('date', fields_)
        self.assertIn('doc_type', fields_)

    def test_cau_chi_gom_filter_van_tra_ket_qua(self):
        """'kế hoạch' bị bóc sạch thành filter, phần ngữ nghĩa còn rỗng —
        không được vì thế mà trả về không có gì."""
        result = self._search('kế hoạch')
        self.assertEqual([f['field'] for f in result['filters']], ['doc_type'])
        self.assertEqual([d['id'] for d in result['documents']], [self.doc.id])

    def test_o_tim_kiem_rong_khong_do_ca_kho_ra(self):
        for query in ('', '   ', None):
            result = self._search(query)
            self.assertEqual(result['documents'], [])
            self.assertEqual(result['total'], 0)

    def test_truy_van_toan_ky_tu_la_khong_lam_no_sql(self):
        for query in ("' OR 1=1 --", '((', 'a & | !', '%s', '100%'):
            result = self._search(query)
            self.assertIsInstance(result['total'], int)

    # ------------------------------------------------------------------ #
    # Ba kênh, RRF, gom về văn bản
    # ------------------------------------------------------------------ #
    def test_ba_kenh_deu_chay(self):
        result = self._search('hỗ trợ hộ nghèo')
        self.assertEqual(result['channels_used'],
                         ['vector', 'lexical', 'lexical_noaccent'])
        self.assertFalse(result['degraded'])

    def test_go_khong_dau_van_ra_ket_qua(self):
        with patch.object(type(self.env['aidt.embed.client']), '_embed',
                          side_effect=OSError('service tắt')):
            result = self._service().search('ho ngheo')
        self.assertIn(self.doc.id, [d['id'] for d in result['documents']])

    def test_gom_theo_van_ban_toi_da_ba_doan(self):
        result = self._search('hỗ trợ hộ nghèo')
        target = [d for d in result['documents'] if d['id'] == self.doc.id]
        self.assertEqual(len(target), 1, 'không được trả danh sách chunk rời')
        self.assertGreaterEqual(len(target[0]['snippets']), 1)
        self.assertLessEqual(len(target[0]['snippets']), 3)

    def test_trich_doan_co_highlight(self):
        result = self._search('hộ nghèo')
        snippet = result['documents'][0]['snippets'][0]['snippet']
        self.assertIn('<mark>', snippet)

    def test_limit_chi_cat_trang_khong_cat_tong(self):
        result = self._search('kinh phí đôn đốc tiến độ hỗ trợ hộ nghèo', limit=1)
        self.assertEqual(len(result['documents']), 1)
        self.assertEqual(result['total'], 2)

    def test_extra_domain_thu_hep_ket_qua(self):
        result = self._search('hỗ trợ hộ nghèo đôn đốc tiến độ',
                              extra_domain=[('doc_type', '=', 'cong_van')])
        self.assertEqual([d['id'] for d in result['documents']], [self.other.id])

    # ------------------------------------------------------------------ #
    # Giảm cấp mềm và facet
    # ------------------------------------------------------------------ #
    def test_embed_chet_van_tim_duoc_bang_lexical(self):
        with patch.object(type(self.env['aidt.embed.client']), '_embed',
                          side_effect=OSError('không gọi được embedding')):
            result = self._service().search('hỗ trợ hộ nghèo')
        self.assertTrue(result['degraded'])
        self.assertEqual(result['channels_used'], ['lexical', 'lexical_noaccent'])
        self.assertIn('tạm ngưng', result['warning'])
        self.assertIn(self.doc.id, [d['id'] for d in result['documents']])

    def test_facet_dem_tren_toan_bo_ket_qua_khong_phai_trang_hien_tai(self):
        result = self._search('kinh phí đôn đốc tiến độ hỗ trợ hộ nghèo', limit=1)
        counts = dict(result['facets']['doc_type'])
        self.assertEqual(counts.get('ke_hoach'), 1)
        self.assertEqual(counts.get('cong_van'), 1)

    def test_limit_sai_kieu_lui_ve_mac_dinh_chu_khong_no(self):
        for bad in ('abc', None, '', {}, [], 'nan'):
            result = self._search('hỗ trợ hộ nghèo', limit=bad)
            self.assertIsInstance(result['total'], int)
        # Giá trị hợp lệ dạng chuỗi vẫn phải hiểu được.
        self.assertEqual(
            len(self._search('kinh phí đôn đốc tiến độ hỗ trợ hộ nghèo',
                             limit='1')['documents']), 1)

    def test_total_cung_mot_nghia_o_ca_hai_nhanh(self):
        """`total` = số văn bản trong tập ứng viên đã trả về, ở CẢ hai nhánh,
        và `truncated` cho biết tập đó đã chạm trần hay chưa."""
        channel = self._search('kinh phí đôn đốc tiến độ hỗ trợ hộ nghèo')
        metadata = self._search('kế hoạch')
        for result in (channel, metadata):
            self.assertEqual(
                result['total'],
                sum(c for _, c in result['facets']['doc_type']),
                'facet phải phủ đúng tập ứng viên mà total đang đếm')
            self.assertFalse(result['truncated'])

    def test_nhanh_metadata_bi_chan_tran(self):
        """Câu chỉ-có-filter không được nạp cả kho về Python."""
        from odoo.addons.aidt_search.models.search_service import CANDIDATE_MAX_DOCS
        self.env['aidt.document'].create([{
            'name': 'Công văn hàng loạt %s' % i, 'direction': 'den',
            'secrecy': 'thuong', 'department_id': self.dept.id,
            'doc_type': 'cong_van',
        } for i in range(CANDIDATE_MAX_DOCS + 5)])
        result = self._search('công văn')
        self.assertEqual(result['total'], CANDIDATE_MAX_DOCS)
        self.assertTrue(result['truncated'])

    def test_bao_so_tep_dang_cho_chi_muc(self):
        """§6.2: 'kho đang xử lý N tệp' phải phân biệt được với 'không có
        kết quả'."""
        self.env['aidt.index.job'].create(
            {'document_id': self.doc.id, 'state': 'pending'})
        self.assertGreaterEqual(self._search('không khớp gì cả')['indexing'], 1)


class TestSanLienQuanKenhVector(TransactionCase):
    """F-2: không có sàn liên quan thì MỌI câu hỏi đều trả về văn bản.

    `_channel_vector` trả top-50 vô điều kiện, còn RRF xếp hạng thuần theo THỨ
    HẠNG nên đã vứt bỏ độ lớn — không tầng nào phía sau còn loại được một chunk
    đã lọt vào kênh. Hai kênh lexical tự có sàn (`@@ q` phải khớp), nên chênh
    lệch "0 kết quả khi tắt vector / 3 kết quả khi bật" cô lập đúng vào kênh này.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Sàn liên quan', 'unit_type': 'phong'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_san', 'login': 'canbo_san',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_san', 'department_id': cls.dept.id,
            'user_id': cls.user.id})
        cls.user.write({'clearance_level': 3})
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch xa lạ', 'direction': 'den', 'secrecy': 'thuong',
            'department_id': cls.dept.id, 'doc_type': 'ke_hoach',
        })
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': cls.doc.id, 'seq': 0,
            'text': 'nội dung hoàn toàn không liên quan tới câu hỏi',
            'embed_text': 'nội dung hoàn toàn không liên quan tới câu hỏi',
        })
        # Vector trực giao với vector truy vấn bên dưới -> khoảng cách cosine
        # đúng bằng 1.0, tức xa hơn mọi ngưỡng hợp lý.
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk "
            "   SET embedding = (ARRAY[0.0::float8] "
            "                    || array_fill(1.0::float8, ARRAY[%s]))::vector "
            " WHERE id = %s", (DIM - 1, chunk.id))
        cls.far_query_vector = [1.0] + [0.0] * (DIM - 1)

    def _service(self):
        return self.env['aidt.search.service'].with_user(self.user)

    def _allowed_sql(self):
        return self._service()._allowed_document_query([]).subselect()

    def test_chunk_xa_bi_loai_khoi_kenh_vector(self):
        self.assertEqual(
            self._service()._channel_vector(self.far_query_vector,
                                            self._allowed_sql()),
            [], 'chunk vượt sàn khoảng cách không được vào kênh vector')

    def test_noi_long_nguong_thi_chunk_xa_quay_lai(self):
        """Chốt rằng test trên đo đúng cái sàn, không phải một lỗi nào khác."""
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_search.vector_max_distance', '2.0')
        self.assertTrue(
            self._service()._channel_vector(self.far_query_vector,
                                            self._allowed_sql()))

    def test_cau_hoi_khong_co_cau_tra_loi_thi_tra_rong(self):
        with patch.object(type(self.env['aidt.embed.client']), '_embed',
                          return_value=[self.far_query_vector]):
            result = self._service().search('chủ đề hoàn toàn khác biệt')
        self.assertEqual(result['documents'], [])
        self.assertEqual(result['total'], 0)
        self.assertFalse(result['degraded'],
                         'đây là "không có kết quả", không phải "giảm cấp"')

    def test_nguong_sai_kieu_lui_ve_mac_dinh_chu_khong_no(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aidt_search.vector_max_distance', 'khong-phai-so')
        from odoo.addons.aidt_search.models.search_service import (
            DEFAULT_VECTOR_MAX_DISTANCE)
        self.assertEqual(self._service()._vector_max_distance(),
                         DEFAULT_VECTOR_MAX_DISTANCE)


class TestGiamCapMemKhongBiLuoiAnToanDanhSap(TestSearchService):
    """I-7: `SET LOCAL hnsw.iterative_scan` từng nằm NGOÀI mọi try/except.

    Trên pgvector < 0.8.0 GUC đó không tồn tại -> câu lệnh ném lỗi, giao dịch
    hỏng, và mọi tìm kiếm ngữ nghĩa thành 500 thay vì giảm cấp mềm về lexical
    như §5.6 đòi hỏi. Lưới an toàn tự đánh sập đúng cơ chế nó bảo vệ.
    """

    def test_khong_dat_duoc_guc_van_tim_kiem_binh_thuong(self):
        def no_such_guc(service):
            service.env.cr.execute("SET LOCAL khong.co.guc.nay = 'x'")

        with patch.object(type(self.env['aidt.search.service']),
                          '_set_hnsw_iterative_scan', autospec=True,
                          side_effect=no_such_guc):
            result = self._search('hỗ trợ hộ nghèo')
        self.assertIn(self.doc.id, [d['id'] for d in result['documents']])
        self.assertIn('vector', result['channels_used'])


class TestExtraDomainDuocChanVeFacet(TestSearchService):
    """I-3: `extra_domain` đến thẳng từ RPC. Không phải lỗ hổng bảo mật —
    `_search()` vẫn AND ir.rule nên tập kết quả không nới rộng được — nhưng là
    bề mặt CHI PHÍ không giới hạn (duyệt quan hệ nhiều tầng, `child_of` trên
    cây đơn vị) ở mỗi lượt tìm."""

    def test_leaf_hop_le_van_hoat_dong(self):
        result = self._search('hỗ trợ hộ nghèo đôn đốc tiến độ',
                              extra_domain=[('doc_type', '=', 'cong_van')])
        self.assertEqual([d['id'] for d in result['documents']], [self.other.id])

    def test_field_ngoai_danh_sach_trang_bi_bo(self):
        for bad in ([('name', 'ilike', 'Kế hoạch')],
                    [('department_id.parent_id.name', '=', 'x')],
                    [('department_id', 'child_of', 1)],
                    ['|', ('doc_type', '=', 'cong_van'), ('doc_type', '=', 'ke_hoach')],
                    [('doc_type', '=', 'cong_van', 'thua')],
                    ['rác'], [None]):
            cleaned = self._service()._sanitize_extra_domain(bad)
            self.assertEqual(
                cleaned, [], 'điều kiện %r phải bị loại khỏi extra_domain' % (bad,))

    def test_bo_dieu_kien_rac_khong_lam_no_tim_kiem(self):
        result = self._search('hỗ trợ hộ nghèo',
                              extra_domain=[('name', 'ilike', 'bất kỳ')])
        self.assertIn(self.doc.id, [d['id'] for d in result['documents']])


class TestNhanLoaiVanBanMemKhongLamRongKetQua(TestSearchService):
    """F-5: nhãn loại văn bản khớp giữa câu là danh từ tiếng Việt thường."""

    def test_bao_cao_giua_cau_khong_lam_rong_ket_qua(self):
        result = self._search('Xin gửi kế hoạch hỗ trợ hộ nghèo')
        self.assertIn(self.doc.id, [d['id'] for d in result['documents']],
                      'nhãn loại văn bản giữa câu không được biến thành filter '
                      'cứng làm rỗng kết quả')

    def test_chip_van_hien_nhung_danh_dau_la_mem(self):
        result = self._search('Xin gửi kế hoạch hỗ trợ hộ nghèo')
        chips = [f for f in result['filters'] if f['field'] == 'doc_type']
        self.assertEqual(len(chips), 1, 'vẫn phải cho người dùng thấy đã hiểu gì')
        self.assertFalse(chips[0]['hard'])

    def test_cau_chi_gom_nhan_van_la_filter_cung(self):
        result = self._search('kế hoạch')
        chips = [f for f in result['filters'] if f['field'] == 'doc_type']
        self.assertTrue(chips[0]['hard'])
        self.assertEqual([d['id'] for d in result['documents']], [self.doc.id])


class TestReindexKiemTraQuyen(TransactionCase):
    """M-3: `action_reindex` không kiểm quyền -> ai ĐỌC được văn bản là xếp
    được việc GPU cho toàn bộ tệp của nó, lặp bao nhiêu lần tuỳ thích.

    `_enqueue_document` chạy sudo bên trong (nó phải đọc dms.file) nên không có
    kiểm tra quyền nào tự xảy ra trên đường đi.

    Ca đọc-được-nhưng-không-ghi-được có thật trong aidt_org, không phải giả
    định: `rule_aidt_document_scope` cho ĐỌC văn bản ngoài đơn vị khi được chia
    sẻ qua `shared_user_ids`, còn `rule_aidt_document_scope_write` thì KHÔNG có
    vế đó — người được chia sẻ đọc được nhưng không ghi được.
    """

    def test_duoc_chia_se_doc_nhung_khong_reindex_duoc(self):
        from odoo.exceptions import AccessError
        Dept = self.env['hr.department']
        dept_minh = Dept.create({'name': 'Phòng Của Mình', 'unit_type': 'phong'})
        dept_khac = Dept.create({'name': 'Phòng Khác', 'unit_type': 'phong'})
        user = self.env['res.users'].create({
            'name': 'canbo_reindex', 'login': 'canbo_reindex',
            'group_ids': [(4, self.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        self.env['hr.employee'].create({
            'name': 'canbo_reindex', 'department_id': dept_minh.id,
            'user_id': user.id})
        user.write({'clearance_level': 3})

        doc = self.env['aidt.document'].create({
            'name': 'Kế hoạch phòng khác', 'direction': 'den', 'secrecy': 'thuong',
            'department_id': dept_khac.id, 'doc_type': 'ke_hoach',
            'shared_user_ids': [(4, user.id)],
        })
        doc_as_user = doc.with_user(user)
        self.assertEqual(doc_as_user.name, 'Kế hoạch phòng khác',
                         'điều kiện tiên quyết: được chia sẻ nên ĐỌC được')
        with self.assertRaises(AccessError):
            doc_as_user.action_reindex()

    def test_ghi_duoc_thi_van_reindex_duoc(self):
        """Không được siết tới mức chặn cả người dùng hợp lệ."""
        dept = self.env['hr.department'].create(
            {'name': 'Phòng Reindex OK', 'unit_type': 'phong'})
        user = self.env['res.users'].create({
            'name': 'canbo_reindex_ok', 'login': 'canbo_reindex_ok',
            'group_ids': [(4, self.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        self.env['hr.employee'].create({
            'name': 'canbo_reindex_ok', 'department_id': dept.id, 'user_id': user.id})
        user.write({'clearance_level': 3})
        doc = self.env['aidt.document'].create({
            'name': 'Kế hoạch reindex', 'direction': 'den', 'secrecy': 'thuong',
            'department_id': dept.id, 'doc_type': 'ke_hoach',
        })
        self.assertTrue(doc.with_user(user).action_reindex())
