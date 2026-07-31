from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLoginLayout(HttpCase):

    def test_01_custom_login_page_renders_2column(self):
        """Verify that opening /web/login renders the 2-column layout with system title."""
        res = self.url_open('/web/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn('aidt-login-split-view', res.text)
        self.assertIn('HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY', res.text)
