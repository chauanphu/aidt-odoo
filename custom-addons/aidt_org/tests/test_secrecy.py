from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSecrecy(TransactionCase):
    """N-04: độ mật chặn ở tầng dữ liệu, AND với phạm vi đơn vị."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'Đơn vị A', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'Đơn vị B', 'unit_type': 'ban'})
        cls.group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        # CV đơn vị A, clearance 1 (đọc tới 'mat')
        cls.user_a = cls._make_user('sec_a', cls.dept_a, clearance=1)
        # CV đơn vị A, clearance 3 (đọc mọi mức) — dùng cho bẫy OR-nới-rộng
        cls.user_a3 = cls._make_user('sec_a3', cls.dept_a, clearance=3)

        Doc = cls.env['aidt.document']
        cls.doc_mat = Doc.create({
            'name': 'VB Mật A', 'department_id': cls.dept_a.id, 'secrecy': 'mat'})
        cls.doc_tuyetmat = Doc.create({
            'name': 'VB Tuyệt mật A', 'department_id': cls.dept_a.id,
            'secrecy': 'tuyet_mat'})
        cls.doc_b_thuong = Doc.create({
            'name': 'VB Thường B', 'department_id': cls.dept_b.id, 'secrecy': 'thuong'})

    @classmethod
    def _make_user(cls, login, dept, clearance):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, cls.group_cv.id)],
            'clearance_level': clearance,
        })
        cls.env['hr.employee'].create(
            {'name': login, 'user_id': user.id, 'department_id': dept.id})
        return user

    def test_level_mapping(self):
        self.assertEqual(self.doc_mat.secrecy_level, 1)
        self.assertEqual(self.doc_tuyetmat.secrecy_level, 3)

    def test_clearance_blocks_above_level(self):
        """clearance 1 đọc được Mật, KHÔNG đọc được Tuyệt mật."""
        Doc = self.env['aidt.document'].with_user(self.user_a)
        self.assertTrue(Doc.browse(self.doc_mat.id).name)
        with self.assertRaises(AccessError):
            self.assertTrue(Doc.browse(self.doc_tuyetmat.id).name)

    def test_search_hides_above_level(self):
        """VB vượt mức mật vắng mặt khỏi search (không lộ tiêu đề)."""
        ids = self.env['aidt.document'].with_user(self.user_a).search([]).ids
        self.assertIn(self.doc_mat.id, ids)
        self.assertNotIn(self.doc_tuyetmat.id, ids)

    def test_clearance_does_not_widen_department(self):
        """clearance 3 KHÔNG cho thấy VB đơn vị khác — regression OR-nới-rộng."""
        ids = self.env['aidt.document'].with_user(self.user_a3).search([]).ids
        self.assertNotIn(self.doc_b_thuong.id, ids)

    def test_clearance_not_self_writeable(self):
        """User không tự nâng clearance của mình."""
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(self.user_a).browse(
                self.user_a.id).write({'clearance_level': 3})
