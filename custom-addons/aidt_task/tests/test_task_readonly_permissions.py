from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestTaskReadonlyPermissions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept_tonghop = cls.env['hr.department'].create({'name': 'Phòng Tổng hợp Test'})
        cls.user_cv = cls.env['res.users'].create({
            'name': 'Chuyên viên Test',
            'login': 'cv.test.readonly',
            'email': 'cv.test@example.com',
            'group_ids': [(6, 0, [cls.env.ref('aidt_org.group_chuyen_vien').id])],
        })
        cls.user_tp = cls.env['res.users'].create({
            'name': 'Trưởng phòng Test',
            'login': 'tp.test.readonly',
            'email': 'tp.test@example.com',
            'group_ids': [(6, 0, [cls.env.ref('aidt_org.group_truong_phong').id])],
        })
        
        cls.task = cls.env['aidt.task'].create({
            'name': 'Nhiệm vụ Test Readonly Protection',
            'department_id': cls.dept_tonghop.id,
            'assignee_id': cls.user_cv.id,
            'assigner_id': cls.user_tp.id,
            'state': 'new',
        })

    def test_01_submit_review_requires_result_report(self):
        """Test submitting review without result_ids raises UserError."""
        self.task.action_start()
        self.assertEqual(self.task.state, 'in_progress')
        
        with self.assertRaises(UserError):
            self.task.with_user(self.user_cv).action_submit_review()
            
        # Add result report
        self.env['aidt.task.result'].create({
            'task_id': self.task.id,
            'report': 'Báo cáo kết quả công việc hoàn thành 100%',
        })
        
        # Submit review succeeds
        self.task.with_user(self.user_cv).action_submit_review()
        self.assertEqual(self.task.state, 'pending_review')

    def test_02_only_assigner_can_approve(self):
        """Test non-assigner user cannot approve task closure."""
        self.task.action_start()
        self.env['aidt.task.result'].create({
            'task_id': self.task.id,
            'report': 'Báo cáo kết quả',
        })
        self.task.action_submit_review()
        
        # Specialist (non-assigner) attempts approval -> raises UserError
        with self.assertRaises(UserError):
            self.task.with_user(self.user_cv).action_approve()
            
        # Assigner approves -> succeeds
        self.task.with_user(self.user_tp).action_approve()
        self.assertEqual(self.task.state, 'done')
