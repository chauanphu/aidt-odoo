from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestDocumentScope(TransactionCase):
    """Kịch bản O-03: đóng vai từng vai trò, xác nhận phạm vi N-05."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Department = cls.env['hr.department']
        cls.dept_root = Department.create({'name': 'Tỉnh ủy Test', 'unit_type': 'cap_uy'})
        cls.dept_vp = Department.create(
            {'name': 'Văn phòng', 'unit_type': 'ban', 'parent_id': cls.dept_root.id})
        cls.dept_th = Department.create(
            {'name': 'Phòng Tổng hợp', 'unit_type': 'phong', 'parent_id': cls.dept_vp.id})
        cls.dept_tc = Department.create(
            {'name': 'Ban Tổ chức', 'unit_type': 'ban', 'parent_id': cls.dept_root.id})

        group_cv = cls.env.ref('aidt_org.group_chuyen_vien')
        group_cvp = cls.env.ref('aidt_org.group_chanh_vp')
        group_bt = cls.env.ref('aidt_org.group_bi_thu')

        cls.user_cv = cls._make_user('test_cv', group_cv, cls.dept_th)
        cls.user_cvp = cls._make_user('test_cvp', group_cvp, cls.dept_vp)
        cls.user_bt = cls._make_user('test_bt', group_bt, cls.dept_root)
        cls.user_tc = cls._make_user('test_tc', group_cv, cls.dept_tc)

        Doc = cls.env['aidt.document']
        cls.doc_th = Doc.create({'name': 'VB Tổng hợp', 'department_id': cls.dept_th.id})
        cls.doc_vp = Doc.create({'name': 'VB Văn phòng', 'department_id': cls.dept_vp.id})
        cls.doc_tc = Doc.create({'name': 'VB Ban TC', 'department_id': cls.dept_tc.id})
        cls.doc_shared = Doc.create({
            'name': 'VB chia sẻ chéo', 'department_id': cls.dept_tc.id,
            'shared_user_ids': [(4, cls.user_cv.id)],
        })

    @classmethod
    def _make_user(cls, login, group, department):
        user = cls.env['res.users'].create({
            'name': login,
            'login': login,
            'group_ids': [(4, group.id)],
        })
        cls.env['hr.employee'].create({
            'name': login,
            'user_id': user.id,
            'department_id': department.id,
        })
        return user

    def test_cv_sees_own_department_and_shared_only(self):
        """CV Phòng Tổng hợp: chỉ VB phòng mình + VB được chia sẻ."""
        docs = self.env['aidt.document'].with_user(self.user_cv).search([])
        self.assertEqual(set(docs.ids), {self.doc_th.id, self.doc_shared.id})

    def test_chanh_vp_sees_whole_branch(self):
        """Chánh VP: toàn nhánh Văn phòng (child_of), không thấy Ban TC."""
        docs = self.env['aidt.document'].with_user(self.user_cvp).search([])
        self.assertEqual(set(docs.ids), {self.doc_th.id, self.doc_vp.id})

    def test_bi_thu_sees_all(self):
        """Bí thư ở root: thấy toàn bộ."""
        docs = self.env['aidt.document'].with_user(self.user_bt).search([])
        self.assertEqual(set(docs.ids), {
            self.doc_th.id, self.doc_vp.id, self.doc_tc.id, self.doc_shared.id})

    def test_create_outside_scope_raises(self):
        """CV Ban TC tạo VB gán cho Phòng Tổng hợp → AccessError."""
        with self.assertRaises(AccessError):
            self.env['aidt.document'].with_user(self.user_tc).create({
                'name': 'VB lấn sân', 'department_id': self.dept_th.id,
            })

    def test_shared_recipient_cannot_write(self):
        """Người được chia sẻ chỉ đọc — không sửa được VB ngoài đơn vị."""
        doc = self.doc_shared.with_user(self.user_cv)
        self.assertEqual(doc.name, 'VB chia sẻ chéo')  # đọc được
        with self.assertRaises(AccessError):
            doc.write({'name': 'Bị sửa trái phép'})

    def test_no_employee_user_sees_shared_only(self):
        """User không có employee/đơn vị: chỉ thấy VB được chia sẻ đích danh."""
        user = self.env['res.users'].create({
            'name': 'test_no_emp', 'login': 'test_no_emp',
            'group_ids': [(4, self.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        self.doc_vp.write({'shared_user_ids': [(4, user.id)]})
        docs = self.env['aidt.document'].with_user(user).search([])
        self.assertEqual(docs.ids, [self.doc_vp.id])

    def test_admin_without_employee_sees_all(self):
        """Admin không có employee vẫn thấy tất cả (rule bypass)."""
        user = self.env['res.users'].create({
            'name': 'test_admin', 'login': 'test_admin',
            'group_ids': [(4, self.env.ref('aidt_org.group_aidt_admin').id)],
        })
        docs = self.env['aidt.document'].with_user(user).search([])
        self.assertEqual(len(docs), 4)
