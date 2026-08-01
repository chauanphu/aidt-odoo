"""Round-1 review Finding 3: `openDocument()` (search_view.js) là điểm mở
văn bản DUY NHẤT trong toàn bộ giao diện, nhưng `aidt.search.log.action_click()`
(Task 16, đã được review/siết bảo mật) không có cách nào được gọi tới nếu
`search()` không lộ ra id của bản ghi log vừa ghi. Không có test này thì việc
thêm `result['log_id']` (search_service.py) không được chốt lại bằng gì cả.

Test này KHÔNG lặp lại các test đã có ở `test_search_log.py` (bị khoá, không
được sửa) — nó chỉ chốt đúng một việc: `search()` trả `log_id` DÙNG ĐƯỢC
ngay để gọi `action_click()`, và toàn bộ hai lớp kiểm tra bảo mật của
`action_click()` (chủ sở hữu + thành viên trong `result_document_ids`) vẫn
nguyên vẹn khi đi qua đường này.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

DIM = 1024


class TestSearchClickWiring(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create(
            {'name': 'Phòng click wiring', 'unit_type': 'phong'})
        cls.user = cls.env['res.users'].create({
            'name': 'canbo_click', 'login': 'canbo_click',
            'group_ids': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'canbo_click', 'department_id': cls.dept.id,
            'user_id': cls.user.id})
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Văn bản click wiring', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': cls.doc.id, 'seq': 0,
            'text': 'noi dung click wiring test',
            'embed_text': 'noi dung click wiring test',
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))
        # Không nằm trong kết quả của lượt tìm dưới đây (không chunk nào
        # khớp) — dùng để chốt lại rằng log_id không mở lối "khai bừa".
        cls.doc_ngoai_ket_qua = cls.env['aidt.document'].create({
            'name': 'Văn bản ngoài kết quả click wiring', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'department_id': cls.dept.id,
        })

    def _search(self, query):
        service = self.env['aidt.search.service'].with_user(self.user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return service.search(query)

    def test_search_tra_log_id_va_action_click_ghi_nhan_duoc(self):
        """`search()` phải trả `log_id` dùng được ngay để `action_click()`
        (không lên bề mặt RPC ở dạng khác) ghi nhận đúng văn bản đã mở."""
        result = self._search('click wiring test')
        self.assertTrue(
            result['log_id'],
            'search() phải trả log_id để client khai được lượt click')
        log = self.env['aidt.search.log'].sudo().browse(result['log_id'])
        log.with_user(self.user).action_click(self.doc.id)
        self.assertEqual(log.clicked_document_id, self.doc)

    def test_khong_khai_duoc_van_ban_ngoai_ket_qua_qua_log_id(self):
        """Đi qua đúng đường mà giao diện dùng (log_id từ search()), phép
        kiểm tra thành viên trong result_document_ids của action_click() vẫn
        chặn — không có logic nào bị nới lỏng khi nối dây log_id."""
        result = self._search('click wiring test')
        log = self.env['aidt.search.log'].sudo().browse(result['log_id'])
        self.assertNotIn(
            self.doc_ngoai_ket_qua.id, log.result_document_ids.ids)
        with self.assertRaises(AccessError):
            log.with_user(self.user).action_click(self.doc_ngoai_ket_qua.id)
        self.assertFalse(log.clicked_document_id)
