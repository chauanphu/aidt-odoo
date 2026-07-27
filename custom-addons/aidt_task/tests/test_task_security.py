from odoo.tests.common import TransactionCase, new_test_user


class TestTaskSecurity(TransactionCase):
    """N-04/N-05/O-03: chặn theo độ mật + phạm vi ở TẦNG DỮ LIỆU (ir.rule)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept_a = cls.env['hr.department'].create(
            {'name': 'Ban A', 'unit_type': 'ban'})
        cls.dept_b = cls.env['hr.department'].create(
            {'name': 'Ban B', 'unit_type': 'ban'})
        # clearance thấp (0), thuộc Ban A
        cls.low = new_test_user(
            cls.env, login='low_sec',
            groups='aidt_org.group_chuyen_vien', clearance_level=0)
        cls.env['hr.employee'].create(
            {'name': 'Low', 'user_id': cls.low.id,
             'department_id': cls.dept_a.id})
        # clearance cao (3), thuộc Ban A
        cls.high = new_test_user(
            cls.env, login='high_sec',
            groups='aidt_org.group_chuyen_vien', clearance_level=3)
        cls.env['hr.employee'].create(
            {'name': 'High', 'user_id': cls.high.id,
             'department_id': cls.dept_a.id})

    def _task(self, dept, secrecy='thuong', **vals):
        base = {'name': 'NV sec', 'department_id': dept.id, 'secrecy': secrecy}
        base.update(vals)
        return self.env['aidt.task'].create(base)

    def _can_see(self, user, task):
        return bool(self.env['aidt.task'].with_user(user).search(
            [('id', '=', task.id)]))

    def test_low_clearance_cannot_see_secret(self):
        """O-03: người thanh khoản thấp KHÔNG thấy nhiệm vụ mật."""
        task = self._task(self.dept_a, secrecy='mat')
        self.assertFalse(self._can_see(self.low, task))

    def test_high_clearance_sees_secret(self):
        task = self._task(self.dept_a, secrecy='mat')
        self.assertTrue(self._can_see(self.high, task))

    def test_toi_mat_blocked_for_mid_clearance(self):
        mid = new_test_user(
            self.env, login='mid_sec',
            groups='aidt_org.group_chuyen_vien', clearance_level=1)
        self.env['hr.employee'].create(
            {'name': 'Mid', 'user_id': mid.id,
             'department_id': self.dept_a.id})
        task = self._task(self.dept_a, secrecy='toi_mat')  # level 2 > 1
        self.assertFalse(self._can_see(mid, task))

    def test_other_department_not_visible(self):
        """N-05: đúng độ mật nhưng khác đơn vị → không thấy."""
        task = self._task(self.dept_b, secrecy='thuong')
        self.assertFalse(self._can_see(self.high, task))

    def test_assignee_sees_across_department(self):
        task = self._task(
            self.dept_b, secrecy='thuong', assignee_id=self.high.id)
        self.assertTrue(self._can_see(self.high, task))

    def test_result_inherits_secrecy_block(self):
        """Báo cáo của nhiệm vụ mật cũng bị chặn với clearance thấp."""
        task = self._task(self.dept_a, secrecy='mat', assignee_id=self.low.id)
        result = self.env['aidt.task.result'].create(
            {'task_id': task.id, 'report': 'bí mật'})
        found = self.env['aidt.task.result'].with_user(self.low).search(
            [('id', '=', result.id)])
        self.assertFalse(found)
