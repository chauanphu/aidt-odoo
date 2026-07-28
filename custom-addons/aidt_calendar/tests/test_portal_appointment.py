from datetime import datetime
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPortalAppointment(TransactionCase):
    def test_approve_appointment_registration(self):
        reg = self.env['aidt.appointment.registration'].create({
            'name': 'Nguyễn Văn A',
            'phone': '0912345678',
            'content': 'Xin tiếp làm việc về đơn thư đất đai',
            'preferred_date': datetime.now(),
        })
        reg.action_approve()
        self.assertEqual(reg.state, 'approved')
        self.assertTrue(reg.event_id, "Event must be created on approval")
        self.assertEqual(reg.event_id.appointment_type, 'citizen')
        self.assertIn('Nguyễn Văn A', reg.event_id.name)

    def test_reject_appointment_registration(self):
        reg = self.env['aidt.appointment.registration'].create({
            'name': 'Trần Văn B',
            'phone': '0987654321',
            'content': 'Đăng ký trùng lặp',
            'preferred_date': datetime.now(),
        })
        reg.action_reject()
        self.assertEqual(reg.state, 'rejected')
        self.assertFalse(reg.event_id, "Event must not be created on rejection")
