from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestDocChunkSecurity(TransactionCase):
    """aidt.doc.chunk không có ô mật/đơn vị riêng — nó phải kế thừa phạm vi
    của aidt.document cha qua ir.rule, nếu không ACL đọc (perm_read=1 cho
    Chuyên viên) sẽ lộ toàn bộ nội dung mọi đơn vị/độ mật qua model con này,
    dù aidt.document cha đã bị chặn đúng."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'Đơn vị A (search)', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'Đơn vị B (search)', 'unit_type': 'ban'})
        group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        cls.user_a = cls._make_user('search_sec_a', group_cv, cls.dept_a)

        Doc = cls.env['aidt.document']
        cls.doc_b = Doc.create({
            'name': 'VB Đơn vị B (search)', 'department_id': cls.dept_b.id,
            'secrecy': 'tuyet_mat',
        })
        cls.chunk_b = cls.env['aidt.doc.chunk'].create({
            'document_id': cls.doc_b.id, 'seq': 0, 'text': 'nội dung mật của B',
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

    def test_chunk_ngoai_pham_vi_don_vi_khong_doc_duoc(self):
        with self.assertRaises(AccessError):
            self.env['aidt.doc.chunk'].with_user(self.user_a).browse(
                self.chunk_b.id).text

    def test_chunk_khong_xuat_hien_trong_search(self):
        ids = self.env['aidt.doc.chunk'].with_user(self.user_a).search([]).ids
        self.assertNotIn(self.chunk_b.id, ids)

    def test_admin_van_doc_duoc_moi_chunk(self):
        admin_user = self.env.ref('base.user_admin')
        self.assertEqual(
            self.env['aidt.doc.chunk'].with_user(admin_user).browse(
                self.chunk_b.id).text,
            'nội dung mật của B')
