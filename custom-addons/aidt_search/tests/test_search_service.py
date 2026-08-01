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
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
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
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
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
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
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
