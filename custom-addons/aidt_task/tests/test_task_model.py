from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestTaskModel(TransactionCase):
    """Computes, kế thừa độ mật, và quan hệ báo cáo kết quả."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create(
            {'name': 'ĐV Test NV', 'unit_type': 'ban'})
        cls.doc = cls.env['aidt.document'].create({
            'name': 'VB nguồn', 'department_id': cls.dept.id,
            'secrecy': 'mat'})

    def _task(self, **vals):
        base = {'name': 'NV test', 'department_id': self.dept.id}
        base.update(vals)
        return self.env['aidt.task'].create(base)

    def test_secrecy_level_map(self):
        self.assertEqual(self._task(secrecy='thuong').secrecy_level, 0)
        self.assertEqual(self._task(secrecy='toi_mat').secrecy_level, 2)
        self.assertEqual(self._task(secrecy='tuyet_mat').secrecy_level, 3)

    def test_overdue_true_when_past_and_not_done(self):
        task = self._task(deadline=date.today() - timedelta(days=1))
        self.assertTrue(task.is_overdue)

    def test_overdue_false_when_done(self):
        task = self._task(
            deadline=date.today() - timedelta(days=1), state='done')
        self.assertFalse(task.is_overdue)

    def test_overdue_false_when_future_or_none(self):
        self.assertFalse(
            self._task(deadline=date.today() + timedelta(days=5)).is_overdue)
        self.assertFalse(self._task().is_overdue)

    def test_secrecy_inherited_from_document_on_create(self):
        """Tạo bằng ORM (không qua onchange) vẫn kế thừa độ mật + đơn vị."""
        task = self.env['aidt.task'].create(
            {'name': 'NV từ VB', 'document_id': self.doc.id})
        self.assertEqual(task.secrecy, 'mat')
        self.assertEqual(task.secrecy_level, 1)
        self.assertEqual(task.department_id, self.dept)

    def test_explicit_secrecy_overrides_document(self):
        task = self.env['aidt.task'].create({
            'name': 'NV ghi đè', 'document_id': self.doc.id,
            'department_id': self.dept.id, 'secrecy': 'thuong'})
        self.assertEqual(task.secrecy, 'thuong')

    def test_result_count_and_cascade(self):
        task = self._task()
        self.assertEqual(task.result_count, 0)
        r1 = self.env['aidt.task.result'].create(
            {'task_id': task.id, 'report': 'xong 50%'})
        self.env['aidt.task.result'].create(
            {'task_id': task.id, 'report': 'xong 100%'})
        self.assertEqual(task.result_count, 2)
        # kế thừa mức mật của nhiệm vụ
        task.secrecy = 'toi_mat'
        self.assertEqual(r1.secrecy_level, 2)
        # cascade khi xóa nhiệm vụ
        result_ids = task.result_ids.ids
        task.unlink()
        self.assertFalse(
            self.env['aidt.task.result'].search([('id', 'in', result_ids)]))
