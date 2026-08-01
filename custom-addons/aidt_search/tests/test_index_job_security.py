from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestIndexJobSecurity(TransactionCase):
    """aidt.index.job không mang department_id/secrecy_level riêng — như
    aidt.doc.chunk ở Task 12, nó phải kế thừa phạm vi của aidt.document cha
    qua ir.rule, nếu không ACL đọc (perm_read=1 cho Chuyên viên) sẽ lộ sự
    tồn tại/trạng thái/thông điệp lỗi của job thuộc mọi đơn vị/độ mật qua
    model con này, dù aidt.document cha đã bị chặn đúng."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'Đơn vị A (index job)', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'Đơn vị B (index job)', 'unit_type': 'ban'})
        group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        cls.user_a = cls._make_user('index_job_sec_a', group_cv, cls.dept_a)

        Doc = cls.env['aidt.document']
        cls.doc_b = Doc.create({
            'name': 'VB Đơn vị B (index job)', 'department_id': cls.dept_b.id,
            'secrecy': 'tuyet_mat',
        })
        cls.job_b = cls.env['aidt.index.job'].create({
            'document_id': cls.doc_b.id, 'state': 'pending',
            'error': 'lộ thông tin nếu không có rule',
        })

    @classmethod
    def _make_user(cls, login, group, department):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, group.id)],
        })
        cls.env['hr.employee'].create(
            {'name': login, 'user_id': user.id, 'department_id': department.id})
        return user

    def test_job_ngoai_pham_vi_don_vi_khong_doc_duoc(self):
        with self.assertRaises(AccessError):
            self.env['aidt.index.job'].with_user(self.user_a).browse(
                self.job_b.id).error

    def test_job_khong_xuat_hien_trong_search(self):
        ids = self.env['aidt.index.job'].with_user(self.user_a).search([]).ids
        self.assertNotIn(self.job_b.id, ids)

    def test_admin_van_doc_duoc_moi_job(self):
        admin_user = self.env.ref('base.user_admin')
        self.assertEqual(
            self.env['aidt.index.job'].with_user(admin_user).browse(
                self.job_b.id).error,
            'lộ thông tin nếu không có rule')
