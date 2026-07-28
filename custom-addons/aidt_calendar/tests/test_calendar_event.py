from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestCalendarEvent(TransactionCase):

    def setUp(self):
        super().setUp()
        self.room1 = self.env['resource.resource'].create({'name': 'Phòng họp A'})
        self.room2 = self.env['resource.resource'].create({'name': 'Phòng họp B'})

    def test_room_booking_conflict(self):
        now = datetime.now()
        start1 = now
        stop1 = now + timedelta(hours=1)

        # Create first meeting in room1
        event1 = self.env['calendar.event'].create({
            'name': 'Cuộc họp 1',
            'start': start1,
            'stop': stop1,
            'room_id': self.room1.id,
        })
        self.assertTrue(event1)

        # Overlapping meeting in same room should raise ValidationError
        with self.assertRaises(ValidationError):
            self.env['calendar.event'].create({
                'name': 'Cuộc họp 2 trùng giờ',
                'start': start1 + timedelta(minutes=30),
                'stop': stop1 + timedelta(minutes=30),
                'room_id': self.room1.id,
            })

        # Meeting in different room at same time should succeed
        event3 = self.env['calendar.event'].create({
            'name': 'Cuộc họp 3 khác phòng',
            'start': start1,
            'stop': stop1,
            'room_id': self.room2.id,
        })
        self.assertTrue(event3)

        # Meeting in same room at non-overlapping time should succeed
        event4 = self.env['calendar.event'].create({
            'name': 'Cuộc họp 4 khác giờ',
            'start': stop1 + timedelta(minutes=10),
            'stop': stop1 + timedelta(hours=2),
            'room_id': self.room1.id,
        })
        self.assertTrue(event4)

    def test_secrecy_level_compute(self):
        event = self.env['calendar.event'].create({
            'name': 'Cuộc họp thử nghiệm độ mật',
            'secrecy': 'thuong',
        })
        self.assertEqual(event.secrecy_level, 0)

        event.write({'secrecy': 'mat'})
        self.assertEqual(event.secrecy_level, 1)

        event.write({'secrecy': 'toi_mat'})
        self.assertEqual(event.secrecy_level, 2)

        event.write({'secrecy': 'tuyet_mat'})
        self.assertEqual(event.secrecy_level, 3)

    def test_calendar_event_fields(self):
        event = self.env['calendar.event'].create({
            'name': 'Lịch Cấp ủy hàng tuần',
            'is_weekly_schedule': True,
            'appointment_type': 'leadership',
        })
        self.assertTrue(event.is_weekly_schedule)
        self.assertEqual(event.appointment_type, 'leadership')
