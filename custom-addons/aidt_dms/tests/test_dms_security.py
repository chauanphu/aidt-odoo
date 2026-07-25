import base64

from odoo.tests.common import TransactionCase


class TestDmsSecurity(TransactionCase):
    """V-13/N-04: quyền tệp kế thừa từ văn bản, lọc ở tầng ORM."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'ĐV A sec', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'ĐV B sec', 'unit_type': 'ban'})
        cls.group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        # CV đơn vị A, clearance 0 (chỉ Thường)
        cls.user_a0 = cls._make_user('dsec_a0', cls.dept_a, 0)
        # CV đơn vị A, clearance 3 (mọi mức)
        cls.user_a3 = cls._make_user('dsec_a3', cls.dept_a, 3)
        # CV đơn vị B, clearance 3
        cls.user_b3 = cls._make_user('dsec_b3', cls.dept_b, 3)

        Doc = cls.env['aidt.document']
        cls.doc_secret = Doc.create({
            'name': 'VB Tuyệt mật A', 'department_id': cls.dept_a.id,
            'secrecy': 'tuyet_mat'})
        cls.file_secret = cls.env['dms.file'].create({
            'name': 'tuyet-mat.txt',
            'directory_id': cls.doc_secret.directory_id.id,
            'content': base64.b64encode(b'bi mat'),
        })

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

    def _visible_file_ids(self, user):
        return self.env['dms.file'].with_user(user).search([]).ids

    def test_low_clearance_cannot_see_file(self):
        """Đúng đơn vị nhưng thiếu clearance → tệp vắng mặt khỏi search."""
        self.assertNotIn(self.file_secret.id, self._visible_file_ids(self.user_a0))

    def test_cleared_same_unit_sees_file(self):
        self.assertIn(self.file_secret.id, self._visible_file_ids(self.user_a3))

    def test_other_unit_cannot_see_file(self):
        """Clearance đủ nhưng khác đơn vị → vẫn vô hình (AND phạm vi)."""
        self.assertNotIn(self.file_secret.id, self._visible_file_ids(self.user_b3))

    def test_share_does_not_bypass_clearance(self):
        """Chia sẻ VB Tối mật cho user clearance 0 → tệp vẫn vô hình."""
        doc = self.env['aidt.document'].create({
            'name': 'VB Tối mật chia sẻ', 'department_id': self.dept_b.id,
            'secrecy': 'toi_mat', 'shared_user_ids': [(4, self.user_a0.id)]})
        f = self.env['dms.file'].create({
            'name': 'toi-mat.txt', 'directory_id': doc.directory_id.id,
            'content': base64.b64encode(b'x')})
        self.assertNotIn(f.id, self._visible_file_ids(self.user_a0))

    def test_root_directory_not_leaked(self):
        """Thư mục gốc (root) KHÔNG lộ cho user thường.

        Trước fix, root mang res_model='aidt.document' nhưng res_id=False;
        _get_domain_by_inheritance() nới lỏng domain thành
        [('res_model','=','aidt.document'),('res_id','=',False)] cho bất kỳ
        ai có quyền đọc model aidt.document — khớp đúng root, làm lộ nó bất
        kể phòng ban/độ mật. Ghi chú: không thể tái hiện lỗ hổng bằng một
        dms.file đặt thẳng trong root, vì storage attachment buộc file phải
        có cả res_model VÀ res_id (root không có res_id) — ràng buộc ORM này
        áp dụng độc lập với fix, nên bản thân thư mục root là đối tượng bị
        lộ cần kiểm tra.
        """
        root = self.env.ref('aidt_dms.directory_root_aidt')
        visible_dirs = self.env['dms.directory'].with_user(
            self.user_a3).search([]).ids
        self.assertNotIn(root.id, visible_dirs)
