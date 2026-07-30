from odoo.tests.common import TransactionCase
from ..services.domain_compiler import DomainCompiler


class TestDashboardFilters(TransactionCase):

    def test_dynamic_domain_compilation(self):
        """Kiểm tra dịch biến động $user_id, $today sang giá trị thực tế trong Domain Compiler."""
        raw_domain = [
            ['create_uid', '=', '$user_id'],
            ['date', '>=', '$start_of_month']
        ]

        compiled = DomainCompiler.compile_domain(self.env, raw_domain)
        self.assertEqual(len(compiled), 2)
        self.assertEqual(compiled[0][2], self.env.user.id)
        self.assertIsNotNone(compiled[1][2])

    def test_filter_values_merging(self):
        """Kiểm tra hòa trộn giá trị filter từ UI vào Domain."""
        raw_domain = [['state', '=', 'issued']]
        filter_vals = {'department_id': 5}

        compiled = DomainCompiler.compile_domain(self.env, raw_domain, filter_values=filter_vals)
        self.assertEqual(len(compiled), 2)
        self.assertEqual(compiled[1], ('department_id', '=', 5))
