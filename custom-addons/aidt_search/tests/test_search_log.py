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
        phải là số ĐO ĐƯỢC thật, không phải giá trị mặc định 0 bị bỏ quên.

        `assertGreaterEqual(..., 0)` (bản trước round review) xanh ngay cả
        khi việc truyền `started` giữa hai đầu `search()`/`_log_search()` bị
        đứt gãy và `duration_ms` luôn là 0 — test đó không phân biệt được
        "đo đúng" với "quên đo". `assertGreater(..., 0)` buộc phải có một
        khoảng thời gian THẬT trôi qua (nhiều truy vấn SQL thật chạy trong
        `search()`), nên không thể xanh giả."""
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertGreater(log.duration_ms, 0)

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

    def test_loi_o_lop_ngoai_cung_cua_search_service_khong_lam_hong_search(self):
        """Minor (round review): hai test ở trên chỉ chạm lớp try/except BÊN
        TRONG `aidt.search.log._log_search()`. Lớp try/except THỨ HAI, bọc
        quanh cả lời gọi lẫn phép tính `duration_ms`/tra `result[...]` trong
        `search_service._log_search()`, chưa từng bị ép lỗi. Giả lập một
        `result` thiếu khoá (như `_build_result` đổi shape trong tương lai
        mà quên cập nhật `_log_search`) để ép KeyError xảy ra Ở LỚP NGOÀI,
        trước khi `aidt.search.log._log_search()` được gọi tới — nghĩa là
        không có bản ghi log nào được tạo, nhưng `search()` vẫn phải trả về
        bình thường, không ném lỗi."""
        from odoo.addons.aidt_search.models.search_service import AidtSearchService

        before = self.env['aidt.search.log'].search_count([])
        malformed = {'documents': [{'id': self.doc.id}]}  # thiếu channels_used/degraded
        with patch.object(AidtSearchService, '_build_result',
                          return_value=malformed):
            result = self._search('hỗ trợ hộ nghèo')
        self.assertEqual(result, malformed)
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

        # Văn bản KHÔNG nằm trong kết quả của lượt tìm kiếm dùng trong các
        # test dưới đây (không chunk nào khớp câu hỏi) — dùng để chốt Finding
        # 2: chủ sở hữu hợp lệ vẫn không được tự khai đã mở một văn bản bất
        # kỳ, chỉ những gì THẬT SỰ nằm trong `result_document_ids`.
        cls.doc_ngoai_ket_qua = cls.env['aidt.document'].create({
            'name': 'Văn bản không khớp truy vấn test', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })
        # Văn bản tuyệt mật NGOÀI độ mật của user1/user2 (clearance_level mặc
        # định 0) — biến thể "vượt độ mật" cụ thể của cùng lỗ hổng: nó không
        # bao giờ lọt vào result_document_ids ngay từ lúc tìm kiếm, nên phép
        # kiểm tra thành viên ở action_click() cũng chặn được trường hợp này
        # mà không cần logic riêng.
        cls.doc_vuot_do_mat = cls.env['aidt.document'].create({
            'name': 'Văn bản tuyệt mật vượt độ mật test', 'direction': 'den',
            'secrecy': 'tuyet_mat', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })

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
        """Lối ghi DUY NHẤT là `_log_search()` (private, qua `sudo()` nội
        bộ) — CRUD trực tiếp từ một Chuyên viên thường phải bị ACL chặn, để
        chính người bị ghi lại không tự sửa được bằng chứng kiểm toán của
        mình."""
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

    # -- Finding 2 của vòng review: action_click() phải kiểm tra GIÁ TRỊ --
    def test_khong_the_khai_da_mo_van_ban_ngoai_ket_qua(self):
        """Chủ sở hữu hợp lệ (đúng người, gọi đúng bản ghi của mình) vẫn
        không được tự khai đã mở một văn bản KHÔNG nằm trong kết quả của
        chính lượt tìm kiếm đó — `document_id` là một int trần, RPC gọi
        được, không có gì ràng buộc nó với kết quả thật nếu không tự kiểm
        tra thành viên trong `action_click()`."""
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        log1 = self.env['aidt.search.log'].sudo().search(
            [('user_id', '=', self.user1.id)], order='id desc', limit=1)
        self.assertNotIn(self.doc_ngoai_ket_qua.id, log1.result_document_ids.ids)
        with self.assertRaises(AccessError):
            log1.with_user(self.user1).action_click(self.doc_ngoai_ket_qua.id)
        self.assertFalse(log1.clicked_document_id)

    def test_khong_the_khai_da_mo_van_ban_vuot_do_mat(self):
        """Biến thể cụ thể-về-tuân-thủ của test trên: văn bản tuyệt mật
        vượt độ mật của user1 không bao giờ lọt vào `result_document_ids`
        (đã bị lọc quyền ngay từ lúc tìm kiếm), nên tự nó cũng bị chặn bởi
        cùng phép kiểm tra thành viên — không cần logic "độ mật" riêng
        trong action_click(), chỉ cần không tin document_id do RPC đưa
        vào."""
        self._search_as(self.user1, 'nội dung dùng để test nhật ký tìm kiếm')
        log1 = self.env['aidt.search.log'].sudo().search(
            [('user_id', '=', self.user1.id)], order='id desc', limit=1)
        self.assertNotIn(self.doc_vuot_do_mat.id, log1.result_document_ids.ids)
        with self.assertRaises(AccessError):
            log1.with_user(self.user1).action_click(self.doc_vuot_do_mat.id)
        self.assertFalse(log1.clicked_document_id)


class _FakeParsed:
    """Đủ hình dạng của `intent.parse_query()`'s để `_log_search()` đọc
    được — `raw`/`semantic`/`filters` — mà không cần chạy cả bộ phân tích ý
    định thật. `filters` bỏ trống để bỏ qua chi tiết không liên quan tới
    Finding 1."""
    raw = 'câu hỏi giả lập cho test input validation'
    semantic = 'câu hỏi giả lập cho test input validation'
    filters = []


class TestSearchLogInputValidation(TransactionCase):
    """Finding 1 của vòng review: `aidt.search.log._log_search()` không
    được tin thẳng `document_ids` do người gọi đưa vào. Hôm nay người gọi
    DUY NHẤT là `search_service._log_search()`, vốn luôn tự tính
    `document_ids` từ kết quả đã lọc quyền — nhưng bản thân model không
    được PHÉP dựa vào việc "người gọi hôm nay tử tế" để an toàn; một người
    gọi nội bộ trong tương lai (Task 17, một module khác) có thể đưa vào
    một danh sách id bất kỳ. Test dưới đây gọi thẳng `_log_search()` — vẫn
    gọi được từ Python nội bộ dù đã đổi tên riêng (`_`) để rời khỏi bề mặt
    RPC — đúng như một người gọi nội bộ tương lai sẽ làm, với `document_ids`
    cố tình "bẩn"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng Kiểm tra input log', 'unit_type': 'phong'})
        cls.other_dept = cls.env['hr.department'].create(
            {'name': 'Phòng Khác (input log)', 'unit_type': 'ban'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_validate_log', 'login': 'canbo_validate_log',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_validate_log', 'department_id': cls.dept.id,
            'user_id': cls.user.id})
        cls.doc_ok = cls.env['aidt.document'].create({
            'name': 'Văn bản người dùng được đọc', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })
        # Ngoài phạm vi đơn vị của user (khác phòng, không chia sẻ) — bị
        # rule_aidt_document_scope chặn bất kể độ mật.
        cls.doc_ngoai_don_vi = cls.env['aidt.document'].create({
            'name': 'Văn bản đơn vị khác (input log)', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.other_dept.id,
        })

    def test_log_search_loc_bo_id_ngoai_quyen_doc_cua_nguoi_goi(self):
        log = self.env['aidt.search.log'].with_user(self.user)._log_search(
            parsed=_FakeParsed(),
            document_ids=[self.doc_ok.id, self.doc_ngoai_don_vi.id],
            channels=['lexical'], degraded=False, duration_ms=5)
        self.assertIn(self.doc_ok.id, log.result_document_ids.ids)
        self.assertNotIn(
            self.doc_ngoai_don_vi.id, log.result_document_ids.ids,
            '_log_search() đã ghi id văn bản ngoài quyền đọc của người gọi '
            '— bằng chứng kiểm toán bị làm giả được')

    def test_log_search_khong_ghi_gi_khi_id_gia_mao_toan_bo(self):
        """Nếu TOÀN BỘ `document_ids` đưa vào đều ngoài quyền đọc, bản ghi
        vẫn được tạo (nhật ký của một truy vấn hợp lệ, chỉ là không có kết
        quả) nhưng `result_document_ids` phải rỗng, không phải chứa id giả."""
        log = self.env['aidt.search.log'].with_user(self.user)._log_search(
            parsed=_FakeParsed(), document_ids=[self.doc_ngoai_don_vi.id],
            channels=['lexical'], degraded=False, duration_ms=5)
        self.assertTrue(log)
        self.assertFalse(log.result_document_ids)

    def test_log_search_tu_choi_ghi_khi_bi_goi_duoi_sudo(self):
        """`env.su` làm vô nghĩa phép lọc quyền ở trên — thà không ghi còn
        hơn ghi một bản ghi tưởng đã lọc mà thực ra chưa lọc gì cả (cùng
        tinh thần `_check_not_sudo()` của `aidt.search.service`)."""
        before = self.env['aidt.search.log'].sudo().search_count([])
        log = self.env['aidt.search.log'].sudo()._log_search(
            parsed=_FakeParsed(), document_ids=[self.doc_ok.id],
            channels=['lexical'], degraded=False, duration_ms=5)
        self.assertFalse(log)
        self.assertEqual(
            self.env['aidt.search.log'].sudo().search_count([]), before)
