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

    def test_secrecy_can_be_raised_above_document(self):
        """Được đặt độ mật CAO hơn văn bản nguồn (sàn, không phải trần)."""
        task = self.env['aidt.task'].create({
            'name': 'NV nâng mật', 'document_id': self.doc.id,  # doc = mat (1)
            'department_id': self.dept.id, 'secrecy': 'toi_mat'})  # 2 >= 1 OK
        self.assertEqual(task.secrecy, 'toi_mat')

    def test_secrecy_floor_blocks_lower_on_create(self):
        """Không được tạo nhiệm vụ kém mật hơn văn bản nguồn (chống rò rỉ)."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['aidt.task'].create({
                'name': 'NV rò rỉ', 'document_id': self.doc.id,  # doc = mat
                'department_id': self.dept.id, 'secrecy': 'thuong'})

    def test_secrecy_floor_blocks_lowering_on_write(self):
        from odoo.exceptions import ValidationError
        task = self.env['aidt.task'].create(
            {'name': 'NV', 'document_id': self.doc.id})  # kế thừa mat
        with self.assertRaises(ValidationError):
            task.write({'secrecy': 'thuong'})

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
