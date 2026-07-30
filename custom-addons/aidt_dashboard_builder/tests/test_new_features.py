from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardNewFeatures(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Dashboard = self.env['dynamic.dashboard']
        self.Widget = self.env['dynamic.dashboard.widget']
        self.doc_model = self.env['ir.model'].search([('model', '=', 'aidt.document')], limit=1)

        self.test_dashboard = self.Dashboard.create({
            'name': 'Test New Features Dashboard',
            'state': 'published',
        })

        if self.doc_model:
            self.kpi_widget = self.Widget.create({
                'name': 'Test KPI MoM',
                'dashboard_id': self.test_dashboard.id,
                'widget_type': 'kpi',
                'provider_type': 'odoo_model',
                'model_id': self.doc_model.id,
                'enable_comparison': True,
                'comparison_type': 'previous_period',
            })

    def test_kpi_comparison_data(self):
        """Test QueryEngine computes comparison dictionary and 7 sparkline points."""
        if not self.doc_model:
            return

        from odoo.addons.aidt_dashboard_builder.services.query_engine import QueryEngine
        res = QueryEngine.execute_widget_query(self.env, self.kpi_widget)

        self.assertEqual(res.get('widget_type'), 'kpi')
        self.assertIn('comparison', res)
        comp = res['comparison']
        self.assertTrue(comp.get('enable'))
        self.assertIn('percentage', comp)
        self.assertIn('sparkline', comp)
        self.assertEqual(len(comp['sparkline']), 7)

    def test_domain_compiler_date_pills(self):
        """Test DomainCompiler resolves date_pill filters."""
        from odoo.addons.aidt_dashboard_builder.services.domain_compiler import DomainCompiler

        domain = DomainCompiler.compile_domain(self.env, [], filter_values={'date_pill': 'this_month'})
        self.assertTrue(len(domain) > 0)
        self.assertEqual(domain[0][0], 'create_date')
        self.assertEqual(domain[0][1], '>=')

    def test_excel_export_all_widgets(self):
        """Test Excel Export Controller generates multi-sheet file for all widget types."""
        from odoo.addons.aidt_dashboard_builder.controllers.dashboard_controller import DashboardController
        controller = DashboardController()

        if self.doc_model:
            self.Widget.create({
                'name': 'Test Chart Widget',
                'dashboard_id': self.test_dashboard.id,
                'widget_type': 'bar_chart',
                'provider_type': 'odoo_model',
                'model_id': self.doc_model.id,
            })
            self.Widget.create({
                'name': 'Test Table Widget',
                'dashboard_id': self.test_dashboard.id,
                'widget_type': 'table',
                'provider_type': 'odoo_model',
                'model_id': self.doc_model.id,
            })

        res = controller.export_dashboard_excel(self.test_dashboard.id)
        self.assertEqual(res.get('status'), 'success')
        self.assertTrue(res.get('file_base64'))
        self.assertTrue(res.get('filename').endswith('.xlsx'))
