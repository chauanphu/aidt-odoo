from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMenuCleanup(TransactionCase):

    def test_root_menus_deactivated(self):
        """Verify that To-Do, Project, and Website root menus are deactivated."""
        xml_ids = [
            'project_todo.menu_todo_todos',
            'project.menu_main_pm',
            'website.menu_website_configuration',
        ]
        for xml_id in xml_ids:
            menu = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(menu, f"Menu XML ID {xml_id} should exist.")
            self.assertFalse(menu.active, f"Menu XML ID {xml_id} should be deactivated (active=False).")
