from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCalendarScaffold(TransactionCase):
    def test_module_installed(self):
        module = self.env['ir.module.module'].search([('name', '=', 'aidt_calendar')])
        self.assertTrue(module, "Module aidt_calendar must exist")
        self.assertEqual(module.state, 'installed', "Module aidt_calendar must be installed")
