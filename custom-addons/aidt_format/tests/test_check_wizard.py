import base64
import pathlib
import sys

from odoo.tests.common import TransactionCase

# Xem giải thích đầy đủ ở tests/test_checker.py — thư mục
# aidt_format_engine/tests/ cố ý không có __init__.py nên phải nạp fixture
# bằng đường dẫn tệp thay vì import qua odoo.addons.
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


class TestFormatCheckWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fixtures = _load_fixtures()
        cls.Wizard = cls.env['aidt.format.check.wizard']
        cls.ruleset_dang = cls.env.ref('aidt_format.ruleset_66_qd_tw')

    def _wizard(self, docx_bytes):
        return self.Wizard.create({
            'docx_file': base64.b64encode(docx_bytes),
            'filename': 'test.docx',
            'ruleset_id': self.ruleset_dang.id,
        })

    def test_file_sai_ra_dong_va_so_loi_duong(self):
        wizard = self._wizard(self.fixtures.sai_nhieu_thuoc_tinh())
        wizard.action_kiem_tra()
        self.assertTrue(wizard.line_ids)
        self.assertGreater(wizard.so_loi, 0)
        self.assertTrue(wizard.da_kiem)
        # sai_nhieu_thuoc_tinh() dưới bộ luật 66-QD/TW cho đúng 3 lỗi chặn và
        # 1 cảnh báo — khoá cứng con số này để so_loi không âm thầm đếm luôn
        # cả cảnh báo (severity != 'error') vào số lỗi chặn.
        self.assertEqual(len(wizard.line_ids), 4)
        self.assertEqual(wizard.so_loi, 3)
        self.assertEqual(wizard.so_canh_bao, 1)

    def test_file_dat_khong_co_dong_nao(self):
        wizard = self._wizard(self.fixtures.chuan_66())
        wizard.action_kiem_tra()
        self.assertFalse(wizard.line_ids)
        self.assertEqual(wizard.so_loi, 0)
        self.assertEqual(wizard.so_canh_bao, 0)
        self.assertTrue(wizard.da_kiem)

    def test_file_rong_ra_dung_mot_dong_file_unreadable(self):
        wizard = self._wizard(b'')
        wizard.action_kiem_tra()
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.rule_id, 'file.unreadable')
        self.assertEqual(wizard.line_ids.severity, 'error')
        self.assertEqual(wizard.so_loi, 1)

    def test_kiem_hai_lan_khong_cong_don(self):
        wizard = self._wizard(self.fixtures.sai_nhieu_thuoc_tinh())
        wizard.action_kiem_tra()
        so_dong_lan_dau = len(wizard.line_ids)
        self.assertTrue(so_dong_lan_dau)

        wizard.action_kiem_tra()
        self.assertEqual(len(wizard.line_ids), so_dong_lan_dau)
