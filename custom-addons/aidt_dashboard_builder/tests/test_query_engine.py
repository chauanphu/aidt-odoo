from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError
from ..services.query_engine import QueryEngine
from ..services.query_validator import QueryValidator


class TestQueryEngine(TransactionCase):

    def setUp(self):
        super().setUp()
        self.doc_model = self.env['ir.model'].search([('model', '=', 'aidt.document')], limit=1)

        self.dashboard = self.env['dynamic.dashboard'].create({
            'name': 'Test Dashboard',
            'state': 'published',
        })

        self.widget_kpi = self.env['dynamic.dashboard.widget'].create({
            'name': 'Total Documents KPI',
            'dashboard_id': self.dashboard.id,
            'widget_type': 'kpi',
            'model_id': self.doc_model.id,
            'domain_json': '[["state", "=", "issued"]]',
        })

    def test_kpi_query_execution(self):
        """Kiểm tra thực thi truy vấn KPI Card."""
        res = QueryEngine.execute_widget_query(self.env, self.widget_kpi)
        self.assertEqual(res['type'], 'kpi')
        self.assertIn('value', res)
        self.assertIn('formatted_value', res)

    def test_forbidden_model_validation(self):
        """Kiểm tra chặn model nhạy cảm nằm trong forbidden list."""
        with self.assertRaises(AccessError):
            QueryValidator.validate_model_access(self.env, 'ir.config_parameter')

    def test_forbidden_field_validation(self):
        """Kiểm tra chặn truy cập trường dữ liệu nhạy cảm."""
        user_model = self.env['ir.model'].search([('model', '=', 'res.users')], limit=1)
        user_obj = self.env[user_model.model]

        with self.assertRaises(AccessError):
            QueryValidator.validate_field(user_obj, 'password')
