from datetime import datetime
from odoo.tests.common import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestCalendarSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_low = new_test_user(
            cls.env,
            login='user_low_cal',
            groups='base.group_user',
            clearance_level=0,
            name='User Low Clearance',
            email='low@test.com',
        )
        cls.user_mid = new_test_user(
            cls.env,
            login='user_mid_cal',
            groups='base.group_user',
            clearance_level=1,
            name='User Mid Clearance',
            email='mid@test.com',
        )
        cls.user_high = new_test_user(
            cls.env,
            login='user_high_cal',
            groups='base.group_user',
            clearance_level=3,
            name='User High Clearance',
            email='high@test.com',
        )

        cls.event_thuong = cls.env['calendar.event'].create({
            'name': 'Cuộc họp Thường',
            'start': datetime.now(),
            'stop': datetime.now(),
            'secrecy': 'thuong',
        })
        cls.event_mat = cls.env['calendar.event'].create({
            'name': 'Cuộc họp Mật',
            'start': datetime.now(),
            'stop': datetime.now(),
            'secrecy': 'mat',
        })
        cls.event_toi_mat = cls.env['calendar.event'].create({
            'name': 'Cuộc họp Tối mật',
            'start': datetime.now(),
            'stop': datetime.now(),
            'secrecy': 'toi_mat',
        })
        cls.event_tuyet_mat = cls.env['calendar.event'].create({
            'name': 'Cuộc họp Tuyệt mật',
            'start': datetime.now(),
            'stop': datetime.now(),
            'secrecy': 'tuyet_mat',
        })

    def test_user_low_access(self):
        """User with clearance level 0 can only see thuong events."""
        events_low = self.env['calendar.event'].with_user(self.user_low).search([
            ('id', 'in', [
                self.event_thuong.id,
                self.event_mat.id,
                self.event_toi_mat.id,
                self.event_tuyet_mat.id,
            ])
        ])
        self.assertIn(self.event_thuong, events_low)
        self.assertNotIn(self.event_mat, events_low)
        self.assertNotIn(self.event_toi_mat, events_low)
        self.assertNotIn(self.event_tuyet_mat, events_low)

    def test_user_mid_access(self):
        """User with clearance level 1 can see thuong and mat events."""
        events_mid = self.env['calendar.event'].with_user(self.user_mid).search([
            ('id', 'in', [
                self.event_thuong.id,
                self.event_mat.id,
                self.event_toi_mat.id,
                self.event_tuyet_mat.id,
            ])
        ])
        self.assertIn(self.event_thuong, events_mid)
        self.assertIn(self.event_mat, events_mid)
        self.assertNotIn(self.event_toi_mat, events_mid)
        self.assertNotIn(self.event_tuyet_mat, events_mid)

    def test_user_high_access(self):
        """User with clearance level 3 can see all secrecy levels."""
        events_high = self.env['calendar.event'].with_user(self.user_high).search([
            ('id', 'in', [
                self.event_thuong.id,
                self.event_mat.id,
                self.event_toi_mat.id,
                self.event_tuyet_mat.id,
            ])
        ])
        self.assertIn(self.event_thuong, events_high)
        self.assertIn(self.event_mat, events_high)
        self.assertIn(self.event_toi_mat, events_high)
        self.assertIn(self.event_tuyet_mat, events_high)

    def test_user_cannot_read_secret_meeting(self):
        """Step 1 requirement test: user with clearance level 0 cannot see secret meeting."""
        events = self.env['calendar.event'].with_user(self.user_low).search([
            ('id', '=', self.event_tuyet_mat.id)
        ])
        self.assertFalse(events, "User with clearance level 0 must not see secret meeting")
