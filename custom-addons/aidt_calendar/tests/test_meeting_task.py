from datetime import datetime
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMeetingTask(TransactionCase):

    def test_create_task_from_meeting(self):
        department = self.env['hr.department'].create({'name': 'Phòng CNTT'})
        event = self.env['calendar.event'].create({
            'name': 'Họp chỉ đạo Kế hoạch 2026',
            'start': datetime.now(),
            'stop': datetime.now(),
            'department_id': department.id,
        })
        action = event.action_create_followup_task()
        self.assertEqual(action['res_model'], 'project.task')
        self.assertEqual(action['context']['default_meeting_id'], event.id)
        self.assertEqual(action['context']['default_department_id'], department.id)
        self.assertEqual(action['context']['default_name'], f'Thực hiện kết luận cuộc họp: {event.name}')
