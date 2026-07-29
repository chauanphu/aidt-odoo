from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestDashboardSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group_viewer = self.env.ref('aidt_dashboard_builder.group_dashboard_viewer')
        self.group_designer = self.env.ref('aidt_dashboard_builder.group_dashboard_designer')

        self.test_user_viewer = self.env['res.users'].create({
            'name': 'Test Viewer User',
            'login': 'test_viewer_user',
            'groups_id': [(6, 0, [self.group_viewer.id])],
        })

        self.dashboard = self.env['dynamic.dashboard'].create({
            'name': 'Private Dashboard',
            'owner_id': self.env.user.id,
            'state': 'published',
        })

    def test_viewer_access_rights(self):
        """Viewer người dùng chỉ được xem Dashboard được chia sẻ, không tạo/sửa Dashboard."""
        # Viewer reads published dashboard shared with them or owned
        dash_as_viewer = self.dashboard.with_user(self.test_user_viewer)

        # Viewer cannot write
        with self.assertRaises(AccessError):
            dash_as_viewer.write({'name': 'Hacked Dashboard Name'})
