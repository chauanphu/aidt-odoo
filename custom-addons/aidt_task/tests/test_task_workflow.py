from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user


class TestTaskWorkflow(TransactionCase):
    """Vòng đời trạng thái + duyệt đóng chỉ bởi người giao (T-09/T-13)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create(
            {'name': 'ĐV WF', 'unit_type': 'ban'})
        cls.assigner = new_test_user(
            cls.env, login='giao_wf', groups='aidt_org.group_chanh_vp')
        cls.other = new_test_user(
            cls.env, login='khac_wf', groups='aidt_org.group_chuyen_vien')

    def _task(self):
        # other là assignee: đọc được nhiệm vụ (kể cả khi có ir.rule phạm vi)
        # nhưng vẫn không phải người giao nên không được duyệt đóng.
        return self.env['aidt.task'].create({
            'name': 'NV WF', 'department_id': self.dept.id,
            'assigner_id': self.assigner.id, 'assignee_id': self.other.id})

    def test_state_transitions(self):
        task = self._task()
        self.assertEqual(task.state, 'new')
        task.action_start()
        self.assertEqual(task.state, 'in_progress')
        task.action_submit_review()
        self.assertEqual(task.state, 'pending_review')

    def test_approve_by_assigner_closes(self):
        task = self._task()
        task.action_submit_review()
        task.with_user(self.assigner).action_approve()
        self.assertEqual(task.state, 'done')

    def test_approve_by_other_raises(self):
        task = self._task()
        task.action_submit_review()
        with self.assertRaises(UserError):
            task.with_user(self.other).action_approve()

    def test_approve_blocked_when_no_assigner(self):
        """assigner_id rỗng → KHÔNG ai được duyệt đóng (đóng lỗ hổng bỏ trống)."""
        task = self.env['aidt.task'].create({
            'name': 'NV không người giao', 'department_id': self.dept.id,
            'assigner_id': False})
        task.action_submit_review()
        with self.assertRaises(UserError):
            task.action_approve()

    def test_reject_and_hold(self):
        task = self._task()
        task.action_submit_review()
        task.action_reject()
        self.assertEqual(task.state, 'in_progress')
        task.action_hold()
        self.assertEqual(task.state, 'on_hold')
