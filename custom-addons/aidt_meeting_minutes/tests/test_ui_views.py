from odoo.tests.common import TransactionCase

class TestUIViews(TransactionCase):
    def test_dashboard_classes_in_view(self):
        """Ensure dashboard classes are present in the form view"""
        view = self.env.ref('aidt_meeting_minutes.view_meeting_recording_form')
        arch = view.arch
        self.assertIn('o_dashboard_viewer_container', arch)
        self.assertIn('o_dashboard_card', arch)
