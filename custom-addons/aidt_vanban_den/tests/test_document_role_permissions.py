from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestDocumentRolePermissions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group_chuyen_vien = self.env.ref('aidt_org.group_chuyen_vien')
        self.group_van_thu = self.env.ref('aidt_org.group_van_thu')
        self.group_truong_phong = self.env.ref('aidt_org.group_truong_phong')
        self.group_chanh_vp = self.env.ref('aidt_org.group_chanh_vp')
        self.group_bi_thu = self.env.ref('aidt_org.group_bi_thu')

        self.user_chuyen_vien = self.env['res.users'].create({
            'name': 'Test Chuyen Vien',
            'login': 'test_cv_user',
            'email': 'cv@test.com',
            'group_ids': [(6, 0, [self.group_chuyen_vien.id])],
        })
        self.user_van_thu = self.env['res.users'].create({
            'name': 'Test Van Thu',
            'login': 'test_vt_user',
            'email': 'vt@test.com',
            'group_ids': [(6, 0, [self.group_van_thu.id])],
        })
        self.user_bi_thu = self.env['res.users'].create({
            'name': 'Test Bi Thu',
            'login': 'test_bt_user',
            'email': 'bt@test.com',
            'group_ids': [(6, 0, [self.group_bi_thu.id])],
        })

        self.dept = self.env['hr.department'].create({'name': 'Phong Test Permissions'})

        self.env['hr.employee'].create({
            'name': 'Employee CV',
            'user_id': self.user_chuyen_vien.id,
            'department_id': self.dept.id,
        })
        self.env['hr.employee'].create({
            'name': 'Employee VT',
            'user_id': self.user_van_thu.id,
            'department_id': self.dept.id,
        })
        self.env['hr.employee'].create({
            'name': 'Employee BT',
            'user_id': self.user_bi_thu.id,
            'department_id': self.dept.id,
        })

    def test_chuyen_vien_cannot_but_phe(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Den',
            'direction': 'den',
            'state': 'trinh_lanh_dao',
            'file_count': 1,
            'department_id': self.dept.id,
            'don_vi_chu_tri_id': self.dept.id,
        })

        with self.assertRaises(UserError):
            doc.with_user(self.user_chuyen_vien).action_but_phe()

    def test_bi_thu_can_but_phe(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Den 2',
            'direction': 'den',
            'state': 'trinh_lanh_dao',
            'file_count': 1,
            'department_id': self.dept.id,
            'don_vi_chu_tri_id': self.dept.id,
        })

        doc.with_user(self.user_bi_thu).action_but_phe()
        self.assertEqual(doc.state, 'dang_xu_ly')

    def test_chuyen_vien_cannot_register(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Register Den',
            'direction': 'den',
            'state': 'tiep_nhan',
            'department_id': self.dept.id,
        })
        with self.assertRaises(UserError):
            doc.with_user(self.user_chuyen_vien).action_register()

    def test_van_thu_can_register(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Register Den 2',
            'direction': 'den',
            'state': 'tiep_nhan',
            'department_id': self.dept.id,
        })
        doc.with_user(self.user_van_thu).action_register()
        self.assertEqual(doc.state, 'da_dang_ky')

    def test_chuyen_vien_cannot_sign(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Di Sign',
            'direction': 'di',
            'state': 'cho_ky',
            'department_id': self.dept.id,
        })
        with self.assertRaises(UserError):
            doc.with_user(self.user_chuyen_vien).action_sign()

    def test_bi_thu_can_sign(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Di Sign 2',
            'direction': 'di',
            'state': 'cho_ky',
            'department_id': self.dept.id,
        })
        doc.with_user(self.user_bi_thu).action_sign()
        self.assertEqual(doc.state, 'cho_cap_so')

    def test_chuyen_vien_cannot_issue_vbd(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Di Issue',
            'direction': 'di',
            'state': 'cho_cap_so',
            'department_id': self.dept.id,
        })
        with self.assertRaises(UserError):
            doc.with_user(self.user_chuyen_vien).action_issue_vbd()

    def test_van_thu_can_issue_vbd(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Di Issue 2',
            'direction': 'di',
            'state': 'cho_cap_so',
            'department_id': self.dept.id,
        })
        doc.with_user(self.user_van_thu).action_issue_vbd()
        self.assertEqual(doc.state, 'da_ban_hanh')
