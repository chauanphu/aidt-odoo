from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

DIM = 1024


class TestSearchAcl(TransactionCase):
    """V-13 và O-03: kết quả phải lọc theo quyền TRƯỚC khi trả về.

    Lọc sau khi xếp hạng là lỗ hổng: top-50 có thể toàn văn bản mật user
    không được xem, lọc xong còn rỗng, trong khi kết quả hợp lệ nằm ở hạng 51.

    Cây đơn vị: Phòng A là đơn vị CON của Phòng B. Nhờ vậy user_b và user_mat
    (cùng ở Phòng B) nhìn thấy đúng cùng một phạm vi đơn vị, chỉ khác nhau ở
    clearance_level — cô lập được đúng một biến là độ mật, và user_b vẫn có
    kết quả hợp lệ (văn bản công khai của phòng con) chứ không bị chặn sạch,
    nên khẳng định "không thấy văn bản tuyệt mật" mới thực sự có sức nặng.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        Dept = cls.env['hr.department']
        cls.dept_b = Dept.create({'name': 'Phòng B', 'unit_type': 'ban'})
        cls.dept_a = Dept.create({
            'name': 'Phòng A', 'unit_type': 'phong', 'parent_id': cls.dept_b.id})

        # clearance_level là số nguyên (0=Thường … 3=Tuyệt mật) — đây chính là
        # vế phải của ir.rule secrecy_level <= clearance_level.
        cls.user_a = cls._make_user('canbo_a', cls.dept_a, 0)
        cls.user_b = cls._make_user('canbo_b', cls.dept_b, 0)
        cls.user_mat = cls._make_user('canbo_mat', cls.dept_b, 3)

        cls.doc_public_a = cls._make_doc('Kế hoạch công khai phòng A', cls.dept_a, 'thuong')
        cls.doc_secret_b = cls._make_doc('Kế hoạch tuyệt mật phòng B', cls.dept_b, 'tuyet_mat')
        for doc in (cls.doc_public_a, cls.doc_secret_b):
            cls._make_chunk(doc, 'kế hoạch bảo đảm an toàn thông tin')

    @classmethod
    def _make_user(cls, login, department, clearance_level):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': login, 'department_id': department.id, 'user_id': user.id})
        user.write({'clearance_level': clearance_level})
        return user

    @classmethod
    def _make_doc(cls, name, department, secrecy):
        return cls.env['aidt.document'].create({
            'name': name, 'direction': 'den', 'secrecy': secrecy,
            'department_id': department.id, 'doc_type': 'ke_hoach',
        })

    @classmethod
    def _make_chunk(cls, doc, text):
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': doc.id, 'seq': 0, 'text': text, 'embed_text': text,
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))
        return chunk

    def _search_as(self, user, query='an toàn thông tin'):
        service = self.env['aidt.search.service'].with_user(user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return service.search(query)

    def test_khong_tra_van_ban_ngoai_don_vi(self):
        names = [d['name'] for d in self._search_as(self.user_a)['documents']]
        self.assertIn('Kế hoạch công khai phòng A', names)
        self.assertNotIn('Kế hoạch tuyệt mật phòng B', names)

    def test_khong_lo_ca_tieu_de_van_ban_vuot_do_mat(self):
        # user_b cùng phòng B nhưng clearance 'thường' -> không được thấy gì.
        result = self._search_as(self.user_b)
        # Chốt tính KHÔNG RỖNG: cây đơn vị được dựng đúng như vậy để user_b vẫn
        # có kết quả hợp lệ (văn bản công khai của phòng con). Không có dòng
        # này, một thay đổi fixture sau này khiến user_b bị chặn sạch sẽ làm
        # khẳng định dưới đây đúng một cách vô nghĩa mà không test nào đỏ.
        self.assertTrue(result['documents'])
        for doc in result['documents']:
            self.assertNotIn('tuyệt mật', doc['name'].lower())

    def test_du_clearance_thi_thay(self):
        names = [d['name'] for d in self._search_as(self.user_mat)['documents']]
        self.assertIn('Kế hoạch tuyệt mật phòng B', names)

    def test_facet_khong_dem_van_ban_ngoai_quyen(self):
        # Con số trên facet cũng không được lộ sự tồn tại của văn bản mật.
        total_a = sum(c for _, c in self._search_as(self.user_a)['facets']['doc_type'])
        total_mat = sum(c for _, c in self._search_as(self.user_mat)['facets']['doc_type'])
        self.assertEqual(total_a, 1)
        self.assertEqual(total_mat, 2)

    def test_tong_so_ket_qua_cung_bi_loc(self):
        self.assertEqual(self._search_as(self.user_a)['total'], 1)
        self.assertEqual(self._search_as(self.user_mat)['total'], 2)

    def test_tra_cuu_so_hieu_cung_phai_loc_quyen(self):
        # Nhánh SQL đi đường riêng nên rất dễ quên áp ir.rule ở đây.
        self.doc_secret_b.write({'reference': '999/KH-UBND'})
        result = self._search_as(self.user_a, '999/KH-UBND')
        self.assertEqual(result['documents'], [])

    # ------------------------------------------------------------------ #
    # Từng kênh một: một kênh quên join quyền là đủ để lộ văn bản.
    # ------------------------------------------------------------------ #
    def _allowed_sql_for(self, user):
        service = self.env['aidt.search.service'].with_user(user)
        return service._allowed_document_query([]).subselect()

    def test_kenh_vector_khong_tra_chunk_ngoai_quyen(self):
        service = self.env['aidt.search.service'].with_user(self.user_a)
        chunk_ids = service._channel_vector(
            [0.01] * DIM, self._allowed_sql_for(self.user_a))
        self.assertTrue(chunk_ids, 'kênh vector phải trả được chunk hợp lệ')
        self.assertEqual(
            self.env['aidt.doc.chunk'].sudo().browse(chunk_ids).document_id
            & self.doc_secret_b,
            self.env['aidt.document'])

    def test_kenh_lexical_khong_tra_chunk_ngoai_quyen(self):
        service = self.env['aidt.search.service'].with_user(self.user_a)
        allowed_sql = self._allowed_sql_for(self.user_a)
        for column, text, unaccent in (
            ('ts', 'an toàn thông tin', False),
            ('ts_noaccent', 'an toan thong tin', True),
        ):
            chunk_ids = service._channel_lexical(
                text, column, allowed_sql, unaccent=unaccent)
            self.assertTrue(chunk_ids, 'kênh %s phải trả được chunk hợp lệ' % column)
            self.assertEqual(
                self.env['aidt.doc.chunk'].sudo().browse(chunk_ids).document_id
                & self.doc_secret_b,
                self.env['aidt.document'],
                'kênh %s trả chunk của văn bản ngoài quyền' % column)

    def test_goi_duoi_sudo_bi_tu_choi(self):
        """Toàn bộ phân quyền của dịch vụ dựa vào ir.rule, mà ir.rule bị bỏ
        qua khi `env.su`. Một controller với tay lấy `.sudo()` sẽ tắt lặng lẽ
        mọi thứ, nên bất biến này phải cưỡng chế được chứ không chỉ ghi chú."""
        service = self.env['aidt.search.service'].with_user(self.user_a)
        with self.assertRaises(AccessError):
            service.sudo().search('an toàn thông tin')
        with self.assertRaises(AccessError):
            service.sudo()._allowed_document_query([])
        # env gốc của TransactionCase chạy superuser -> cũng phải bị chặn.
        with self.assertRaises(AccessError):
            self.env['aidt.search.service'].search('an toàn thông tin')

    def test_subquery_khong_keo_id_ve_python(self):
        """Tập được phép phải nhúng làm SUBSELECT, không phải danh sách id
        nội suy — vừa là yêu cầu §5.4 vừa là điều kiện để không có id nào bị
        ghép chuỗi vào SQL."""
        sql = self._allowed_sql_for(self.user_a)
        self.assertIn('SELECT', sql.code.upper())
        self.assertIn('aidt_document', sql.code)


class TestVectorChannelRecall(TransactionCase):
    """Lọc quyền TRƯỚC không được đánh đổi bằng độ triệu hồi của kênh vector.

    Quét HNSW cho tối đa `hnsw.ef_search` (mặc định 40) ứng viên rồi mới áp
    điều kiện lọc; nếu kế hoạch chạy như vậy thì một user quyền hẹp có thể
    nhận về ÍT hơn CHANNEL_TOP_K hàng — hoặc không hàng nào — trong khi chunk
    hợp lệ vẫn tồn tại. Đó là đúng tác hại §5.4 muốn chặn, chỉ dời xuống tầng
    ANN. Test này chốt: có 60 chunk hợp lệ thì phải nhận đủ 50, không phải 40.
    """

    CHUNKS_PER_DOC = 60

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Triệu hồi', 'unit_type': 'phong'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_recall', 'login': 'canbo_recall',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_recall', 'department_id': cls.dept.id,
            'user_id': cls.user.id})
        cls.user.write({'clearance_level': 0})

        cls.doc_ok = cls._make_doc('Kế hoạch công khai', 'thuong')
        cls.doc_mat = cls._make_doc('Kế hoạch tuyệt mật', 'tuyet_mat')
        chunks = cls.env['aidt.doc.chunk'].create([
            {'document_id': doc.id, 'seq': seq,
             'text': 'đoạn %s bảo đảm an toàn thông tin' % seq,
             'embed_text': 'đoạn %s' % seq}
            for doc in (cls.doc_ok, cls.doc_mat)
            for seq in range(cls.CHUNKS_PER_DOC)
        ])
        # Vector khác nhau theo id (tất định, không dùng random) để có một thứ
        # tự khoảng cách thật chứ không phải toàn hoà.
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk "
            "   SET embedding = array_fill(((id %% 97) + 1)::float8 / 100.0, "
            "                              ARRAY[%s])::vector "
            " WHERE id IN %s",
            (DIM, tuple(chunks.ids)))

    @classmethod
    def _make_doc(cls, name, secrecy):
        return cls.env['aidt.document'].create({
            'name': name, 'direction': 'den', 'secrecy': secrecy,
            'department_id': cls.dept.id, 'doc_type': 'ke_hoach',
        })

    def test_kenh_vector_khong_bi_cat_cut_o_ef_search(self):
        service = self.env['aidt.search.service'].with_user(self.user)
        allowed_sql = service._allowed_document_query([]).subselect()
        chunk_ids = service._channel_vector([0.01] * DIM, allowed_sql)

        self.assertEqual(
            len(chunk_ids), 50,
            'kênh vector chỉ trả %s hàng trong khi có %s chunk hợp lệ — dấu '
            'hiệu quét ANN bị cắt ở ef_search trước khi áp lọc quyền'
            % (len(chunk_ids), self.CHUNKS_PER_DOC))
        self.assertEqual(
            self.env['aidt.doc.chunk'].sudo().browse(chunk_ids).document_id,
            self.doc_ok,
            'kênh vector trả chunk của văn bản ngoài quyền')
