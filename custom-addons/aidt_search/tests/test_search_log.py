from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

DIM = 1024


class SearchLogCase(TransactionCase):
    """Cùng bối cảnh với `test_search_service.py`: một văn bản, một chunk,
    truy hồi được bằng cả ba kênh — và cùng lý do phải chạy dưới một user
    THẬT (không phải superuser mặc định của `TransactionCase`):
    `_check_not_sudo()` của Task 15 chặn `env.su` một cách cưỡng chế, nên
    gọi thẳng `self.env['aidt.search.service'].search(...)` dưới env gốc
    (superuser) luôn ném `AccessError` — bài học này áp dụng cho MỌI test
    gọi `search()`, kể cả test của bảng nhật ký."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Sở Tài chính', 'unit_type': 'phong'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_log', 'login': 'canbo_log',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_log', 'department_id': cls.dept.id, 'user_id': cls.user.id})
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch hỗ trợ hộ nghèo', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'reference': '145/KH-UBND', 'department_id': cls.dept.id,
            'date': '2025-06-15',
        })
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': cls.doc.id, 'seq': 0,
            'text': 'Bố trí kinh phí hỗ trợ hộ nghèo trên địa bàn tỉnh.',
            'embed_text': 'Bố trí kinh phí hỗ trợ hộ nghèo trên địa bàn tỉnh.',
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))

    def _search(self, query, **kwargs):
        service = self.env['aidt.search.service'].with_user(self.user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return service.search(query, **kwargs)


class TestSearchLog(SearchLogCase):
    """Đối chiếu Step 1 của brief Task 16, phần `TestSearchLog` — bốn test
    hành vi cơ bản của `aidt.search.log`."""

    def test_moi_truy_van_sinh_mot_ban_ghi(self):
        before = self.env['aidt.search.log'].search_count([])
        self._search('hỗ trợ hộ nghèo')
        self.assertEqual(self.env['aidt.search.log'].search_count([]), before + 1)

    def test_ghi_lai_truy_van_goc_va_nguoi_dung(self):
        self._search('hỗ trợ hộ nghèo năm 2025')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertEqual(log.query_raw, 'hỗ trợ hộ nghèo năm 2025')
        self.assertEqual(log.user_id, self.user)

    def test_ghi_lai_ket_qua_va_kenh(self):
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertIn(self.doc.id, log.result_document_ids.ids)
        self.assertIn('lexical', log.channels_used)

    def test_ghi_lai_luot_click(self):
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        # Gọi với đúng người tìm — action_click tự kiểm tra chủ sở hữu
        # trước khi sudo(), nên gọi dưới env khác chủ (kể cả superuser) là
        # một tình huống KHÁC (xem TestSearchLogPrivacy) chứ không phải
        # đường đi bình thường mà test này đang chốt.
        log.with_user(self.user).action_click(self.doc.id)
        self.assertEqual(log.clicked_document_id, self.doc)

    # -- Hành vi ngoài Step 1 của brief: bọc quanh những gì Step 1 không nói --
    def test_ghi_lai_filter_da_boc_va_co_giam_cap(self):
        """`filters_json` và `degraded` không nằm trong bốn test mẫu của
        brief nhưng là trường thật của model — chốt cả hai không bị rơi."""
        self._search('hỗ trợ hộ nghèo năm 2025')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertTrue(log.filters_json)
        self.assertEqual(log.filters_json[0]['field'], 'date')
        self.assertFalse(log.degraded)

        service = self.env['aidt.search.service'].with_user(self.user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          side_effect=RuntimeError('service down')):
            service.search('hỗ trợ hộ nghèo')
        log2 = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertTrue(log2.degraded)

    def test_thoi_gian_thuc_hien_duoc_ghi_lai(self):
        """`duration_ms` là lý do bảng này tồn tại cho mục đích vận hành —
        phải là số dương thật, không phải giá trị mặc định bỏ quên."""
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertGreaterEqual(log.duration_ms, 0)

    def test_truy_van_rong_van_duoc_ghi_lai(self):
        """Nhánh sớm (ô tìm kiếm rỗng) là một trong ba điểm return của
        search() — phải đi qua _log_search() giống hai nhánh kia."""
        before = self.env['aidt.search.log'].search_count([])
        self._search('')
        self.assertEqual(self.env['aidt.search.log'].search_count([]), before + 1)


class TestSearchLogDoesNotBreakSearch(SearchLogCase):
    """Ghi log là nghĩa vụ PHỤ: một lỗi ở tầng ghi log không được phép làm
    hỏng hoặc làm chậm-tới-mức-lỗi một tìm kiếm hợp lệ."""

    def test_loi_ghi_log_khong_lam_hong_ket_qua_tim_kiem(self):
        with patch.object(type(self.env['aidt.search.log']), 'create',
                          side_effect=RuntimeError('CSDL nhật ký tạm hỏng')):
            result = self._search('hỗ trợ hộ nghèo')
        self.assertTrue(result['documents'])
        self.assertEqual(result['documents'][0]['id'], self.doc.id)

    def test_loi_ghi_log_khong_de_lai_ban_ghi_rac(self):
        before = self.env['aidt.search.log'].search_count([])
        with patch.object(type(self.env['aidt.search.log']), 'create',
                          side_effect=RuntimeError('CSDL nhật ký tạm hỏng')):
            self._search('hỗ trợ hộ nghèo')
        self.assertEqual(self.env['aidt.search.log'].search_count([]), before)


class TestSearchLogPrivacy(TransactionCase):
    """Người dùng không được đọc truy vấn của người khác — N-08 tự nó là
    một tài sản nhạy cảm cần bảo vệ, không chỉ tài liệu nó trỏ tới."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Nhật ký tìm kiếm', 'unit_type': 'phong'})
        cls.user1 = cls._make_user('canbo_log_1', cls.dept)
        cls.user2 = cls._make_user('canbo_log_2', cls.dept)
        cls.admin = cls.env['res.users'].create({
            'name': 'quantri_log', 'login': 'quantri_log',
            'group_ids': [(4, cls.env.ref('aidt_org.group_aidt_admin').id)],
        })
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch dùng cho test nhật ký', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': cls.doc.id, 'seq': 0,
            'text': 'nội dung dùng để test nhật ký tìm kiếm',
            'embed_text': 'nội dung dùng để test nhật ký tìm kiếm',
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))

    @classmethod
    def _make_user(cls, login, department):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create(
            {'name': login, 'department_id': department.id, 'user_id': user.id})
        return user

    def _search_as(self, user, query):
        service = self.env['aidt.search.service'].with_user(user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return service.search(query)

    def test_nguoi_dung_khong_doc_duoc_truy_van_cua_nguoi_khac(self):
        secret_query = 'truy vấn riêng tư của user1 nội dung tìm kiếm'
        self._search_as(self.user1, secret_query)
        self._search_as(self.user2, 'nội dung dùng để test nhật ký tìm kiếm')

        visible_to_2 = self.env['aidt.search.log'].with_user(self.user2).search([])
        self.assertNotIn(secret_query, visible_to_2.mapped('query_raw'))

    def test_nguoi_dung_chi_thay_dung_nhat_ky_cua_chinh_minh(self):
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        self._search_as(self.user2, 'nội dung dùng để test nhật ký tìm kiếm')

        logs_1 = self.env['aidt.search.log'].with_user(self.user1).search([])
        logs_2 = self.env['aidt.search.log'].with_user(self.user2).search([])
        self.assertTrue(logs_1)
        self.assertTrue(logs_2)
        self.assertTrue(all(u == self.user1 for u in logs_1.mapped('user_id')))
        self.assertTrue(all(u == self.user2 for u in logs_2.mapped('user_id')))

    def test_admin_doc_duoc_nhat_ky_cua_moi_nguoi_de_kiem_toan(self):
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        self._search_as(self.user2, 'nội dung dùng để test nhật ký tìm kiếm')

        logs_admin = self.env['aidt.search.log'].with_user(self.admin).search([])
        seen_users = logs_admin.mapped('user_id')
        self.assertIn(self.user1, seen_users)
        self.assertIn(self.user2, seen_users)

    def test_chuyen_vien_khong_tao_duoc_log_bang_create_truc_tiep(self):
        """Lối ghi DUY NHẤT là `log_search()` (qua `sudo()` nội bộ) — CRUD
        trực tiếp từ một Chuyên viên thường phải bị ACL chặn, để chính người
        bị ghi lại không tự sửa được bằng chứng kiểm toán của mình."""
        with self.assertRaises(AccessError):
            self.env['aidt.search.log'].with_user(self.user1).create({
                'query_raw': 'giả mạo nhật ký', 'user_id': self.user1.id,
            })

    def test_khong_the_click_ho_nguoi_khac(self):
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        log1 = self.env['aidt.search.log'].sudo().search(
            [('user_id', '=', self.user1.id)], order='id desc', limit=1)
        with self.assertRaises(AccessError):
            log1.with_user(self.user2).action_click(self.doc.id)

    def test_admin_click_ho_duoc_vi_phuc_vu_kiem_toan(self):
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        log1 = self.env['aidt.search.log'].sudo().search(
            [('user_id', '=', self.user1.id)], order='id desc', limit=1)
        log1.with_user(self.admin).action_click(self.doc.id)
        self.assertEqual(log1.clicked_document_id, self.doc)
