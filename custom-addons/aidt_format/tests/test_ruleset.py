from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

YAML_HOP_LE = """
ruleset: "TEST"
version: "1.0"
ap_dung: dang
so_ky_hieu:
  format: "{n}-{type_code}/{org_code}"
  stamp_box_mm: {x: 30, y: 52, w: 60, h: 8}
page:
  size: A4
  margins_mm: {top: [20, 25], bottom: [20, 25], left: [30, 35], right: [15, 20]}
zones:
  noi_dung:
    font: "Times New Roman"
    size_pt: [14, 15]
"""


class TestFormatRuleset(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ruleset = cls.env['aidt.format.ruleset']

    def _create(self, **overrides):
        values = {'code': 'TEST', 'version': '1.0', 'ap_dung': 'dang',
                  'spec_yaml': YAML_HOP_LE}
        values.update(overrides)
        return self.Ruleset.create(values)

    def test_tao_duoc_bo_luat_hop_le(self):
        ruleset = self._create()
        self.assertTrue(ruleset.active)

    def test_spec_tra_ve_dict_da_parse(self):
        spec = self._create().spec()
        self.assertEqual(spec['ap_dung'], 'dang')
        self.assertEqual(spec['zones']['noi_dung']['size_pt'], [14, 15])

    def test_display_name_gom_code_va_version(self):
        ruleset = self._create()
        self.assertIn('TEST', ruleset.display_name)
        self.assertIn('1.0', ruleset.display_name)

    def test_yaml_sai_cu_phap_bi_chan(self):
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml='zones: [khong dong ngoac')
        self.assertIn('YAML', str(ctx.exception))

    def test_yaml_sai_cau_truc_bi_chan_va_neu_duong_dan(self):
        yaml_sai = YAML_HOP_LE.replace('size: A4', 'size: Letter')
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml=yaml_sai)
        self.assertIn('page.size', str(ctx.exception))

    def test_ap_dung_lech_voi_yaml_bi_chan(self):
        with self.assertRaises(ValidationError) as ctx:
            self._create(ap_dung='hanh_chinh')
        self.assertIn('ap_dung', str(ctx.exception))

    def test_yaml_khong_phai_tu_dien_bi_chan(self):
        with self.assertRaises(ValidationError):
            self._create(spec_yaml='- mot\n- hai\n')

    @mute_logger('odoo.sql_db')
    def test_trung_code_va_version_bi_chan(self):
        self._create()
        # Bọc trong savepoint: IntegrityError làm hỏng cursor, không có savepoint
        # thì teardown của TransactionCase cũng chết theo.
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self._create()
            self.env.flush_all()

    def test_cung_code_khac_version_thi_duoc(self):
        self._create(version='1.0')
        self._create(version='2.0')
        self.assertEqual(
            self.Ruleset.search_count([('code', '=', 'TEST')]), 2)

    def test_sua_yaml_thanh_sai_cung_bi_chan(self):
        ruleset = self._create()
        with self.assertRaises(ValidationError):
            ruleset.spec_yaml = 'ruleset: chi co mot khoa\n'


class TestSeedRuleset(TransactionCase):
    def test_hai_bo_luat_duoc_seed(self):
        for xml_id, ap_dung in (('aidt_format.ruleset_66_qd_tw', 'dang'),
                                ('aidt_format.ruleset_nd_30_2020', 'hanh_chinh')):
            with self.subTest(xml_id=xml_id):
                ruleset = self.env.ref(xml_id)
                self.assertEqual(ruleset.ap_dung, ap_dung)
                self.assertTrue(ruleset.active)

    def test_bo_luat_seed_parse_duoc_va_hop_le(self):
        """Seed đi qua đúng constraint như dữ liệu người dùng nhập."""
        for xml_id in ('aidt_format.ruleset_66_qd_tw',
                       'aidt_format.ruleset_nd_30_2020'):
            with self.subTest(xml_id=xml_id):
                spec = self.env.ref(xml_id).spec()
                self.assertIn('zones', spec)
                self.assertIn('noi_dung', spec['zones'])

    def test_so_ky_hieu_hai_chuan_khac_thu_tu(self):
        dang = self.env.ref('aidt_format.ruleset_66_qd_tw').spec()
        hanh_chinh = self.env.ref('aidt_format.ruleset_nd_30_2020').spec()
        self.assertEqual(dang['so_ky_hieu']['format'],
                         '{n}-{type_code}/{org_code}')
        self.assertEqual(hanh_chinh['so_ky_hieu']['format'],
                         '{n}/{type_code}-{org_code}')
