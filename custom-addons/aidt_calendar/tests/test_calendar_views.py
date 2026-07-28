from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCalendarViews(TransactionCase):

    def test_calendar_views_exist(self):
        view = self.env.ref('aidt_calendar.calendar_event_view_form_inherit')
        self.assertTrue(view, "Inherited form view must exist")

        action = self.env.ref('aidt_calendar.action_weekly_schedule')
        self.assertTrue(action, "Weekly schedule action must exist")

        menu = self.env.ref('aidt_calendar.menu_weekly_schedule')
        self.assertTrue(menu, "Weekly schedule menu must exist")
