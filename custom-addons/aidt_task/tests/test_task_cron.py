from datetime import date, timedelta

from odoo.tests.common import TransactionCase, new_test_user


class TestTaskCron(TransactionCase):
    """Nhắc việc (T-11) idempotent + cảnh báo lãnh đạo (T-14)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create(
            {'name': 'ĐV Cron', 'unit_type': 'ban'})
        cls.assignee = new_test_user(
            cls.env, login='assignee_cron',
            groups='aidt_org.group_chuyen_vien',
            clearance_level=3, email='a@x.vn')

    def test_reminder_created_and_idempotent(self):
        task = self.env['aidt.task'].create({
            'name': 'NV nhắc', 'department_id': self.dept.id,
            'assignee_id': self.assignee.id,
            'deadline': date.today() + timedelta(days=3)})
        Activity = self.env['mail.activity']
        domain = [('res_model', '=', 'aidt.task'), ('res_id', '=', task.id)]

        self.env['aidt.task']._cron_deadline_reminders()
        self.assertEqual(Activity.search_count(domain), 1)

        # chạy lại cùng mốc → KHÔNG tạo trùng
        self.env['aidt.task']._cron_deadline_reminders()
        self.assertEqual(Activity.search_count(domain), 1)

    def test_no_reminder_off_milestone(self):
        self.env['aidt.task'].create({
            'name': 'NV chưa tới mốc', 'department_id': self.dept.id,
            'assignee_id': self.assignee.id,
            'deadline': date.today() + timedelta(days=5)})  # 5 ∉ {7,3,1}
        self.env['aidt.task']._cron_deadline_reminders()
        self.assertEqual(self.env['mail.activity'].search_count(
            [('res_model', '=', 'aidt.task')]), 0)

    def test_leader_digest_emails_when_overdue(self):
        new_test_user(
            self.env, login='leader_cron',
            groups='aidt_org.group_chanh_vp',
            clearance_level=3, email='lead@x.vn')
        self.env['aidt.task'].create({
            'name': 'NV quá hạn', 'department_id': self.dept.id,
            'deadline': date.today() - timedelta(days=2)})
        before = self.env['mail.mail'].search_count([])
        self.env['aidt.task']._cron_leader_overdue_digest()
        self.assertGreater(self.env['mail.mail'].search_count([]), before)
