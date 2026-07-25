import pathlib
import sys

from odoo.tests.common import TransactionCase

# Fixture nằm trong aidt_format_engine/tests/ — thư mục cố ý không có
# __init__.py để pytest trên host không nạp Odoo, nên nó KHÔNG import được
# qua odoo.addons. Nạp bằng đường dẫn tệp.
# parents: [0]=tests, [1]=aidt_format, [2]=custom-addons
_FIXTURES_PATH = str(
    pathlib.Path(__file__).resolve().parents[2]
    / 'aidt_format_engine' / 'tests' / 'fixtures.py')


def _load_fixtures():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'aidt_format_fixtures', _FIXTURES_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestFormatChecker(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fixtures = _load_fixtures()
        cls.checker = cls.env['aidt.format.checker']
        cls.ruleset_dang = cls.env.ref('aidt_format.ruleset_66_qd_tw')
        cls.ruleset_hc = cls.env.ref('aidt_format.ruleset_nd_30_2020')

    def test_file_dat_tra_ve_danh_sach_rong(self):
        self.assertEqual(
            self.checker.check(self.fixtures.chuan_66(), self.ruleset_dang), [])

    def test_file_hanh_chinh_dat_theo_bo_luat_hanh_chinh(self):
        findings = self.checker.check(
            self.fixtures.chuan_nd30(), self.ruleset_hc)
        chan = [f for f in findings if f['severity'] == 'error']
        self.assertEqual(chan, [], 'không được có lỗi chặn: %s' % chan)

    def test_tra_ve_list_dict_dung_bay_khoa(self):
        findings = self.checker.check(
            self.fixtures.sai_le_trang(), self.ruleset_dang)
        self.assertTrue(findings)
        for finding in findings:
            self.assertIsInstance(finding, dict)
            self.assertEqual(
                set(finding),
                {'rule_id', 'severity', 'zone', 'location', 'expected',
                 'actual', 'suggestion'})

    def test_khong_ghi_ban_ghi_nao(self):
        """Ranh giới của module: check() là hàm thuần, không tạo bản ghi."""
        before = self.env['ir.attachment'].search_count([])
        self.checker.check(self.fixtures.sai_font(), self.ruleset_dang)
        self.assertEqual(self.env['ir.attachment'].search_count([]), before)

    def test_file_hong_tra_ve_finding_khong_no_traceback(self):
        findings = self.checker.check(
            self.fixtures.hong(), self.ruleset_dang)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['rule_id'], 'file.unreadable')
        self.assertEqual(findings[0]['severity'], 'error')

    def test_sai_font_bat_duoc_qua_tang_Odoo(self):
        findings = self.checker.check(
            self.fixtures.sai_font(), self.ruleset_dang)
        ids = {f['rule_id'] for f in findings}
        self.assertIn('noi_dung.font', ids)

    def test_severity_overrides_cua_seed_co_hieu_luc(self):
        """Seed hạ noi_dung.size_pt xuống warning; font vẫn là error."""
        findings = self.checker.check(
            self.fixtures.sai_font(), self.ruleset_dang)
        font = [f for f in findings if f['rule_id'] == 'noi_dung.font'][0]
        self.assertEqual(font['severity'], 'error')

    def test_thieu_noi_nhan_la_loi_chan(self):
        findings = self.checker.check(
            self.fixtures.thieu_noi_nhan(), self.ruleset_dang)
        thieu = [f for f in findings if f['rule_id'] == 'noi_nhan.required']
        self.assertEqual(len(thieu), 1)
        self.assertEqual(thieu[0]['severity'], 'error')

    def test_bo_luat_lech_he_quy_chuan_chi_canh_bao(self):
        findings = self.checker.check(
            self.fixtures.chuan_nd30(), self.ruleset_dang)
        lech = [f for f in findings if f['rule_id'] == 'file.wrong_standard']
        self.assertEqual(len(lech), 1)
        self.assertEqual(lech[0]['severity'], 'warning')
