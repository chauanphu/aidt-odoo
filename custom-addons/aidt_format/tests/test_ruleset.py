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

    def test_display_name_dung_thu_tu_code_truoc_version(self):
        # assertIn ở test trên không phân biệt được 'TEST 1.0' với '1.0 TEST':
        # đảo thứ tự hai trường trong _compute_display_name vẫn cho qua. Test
        # này khóa đúng thứ tự hiển thị.
        ruleset = self._create()
        self.assertEqual(ruleset.display_name, 'TEST 1.0')

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

    def test_ap_dung_lech_sau_khi_sua_rieng_bi_chan(self):
        # Test trên chỉ đi qua create(). @api.constrains chạy lại khi write()
        # đổi MỘT MÌNH ap_dung (không đụng spec_yaml) — nếu 'ap_dung' rơi khỏi
        # danh sách trường của decorator, write() này sẽ lọt qua êm re.
        ruleset = self._create()
        with self.assertRaises(ValidationError) as ctx:
            ruleset.ap_dung = 'hanh_chinh'
        self.assertIn('ap_dung', str(ctx.exception))

    def test_ruleset_khong_khop_code_bi_chan(self):
        # code='TEST' nhưng YAML tự khai ruleset khác — nếu lọt qua, ba năm
        # sau ai tra gate_evidence của văn bản cũ sẽ mở nhầm bộ luật.
        yaml_lech = YAML_HOP_LE.replace('ruleset: "TEST"',
                                        'ruleset: "KHONG-KHOP"')
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml=yaml_lech)
        self.assertIn('ruleset', str(ctx.exception))

    def test_version_khong_khop_yaml_bi_chan(self):
        yaml_lech = YAML_HOP_LE.replace('version: "1.0"',
                                        'version: "0.1-khong-khop"')
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml=yaml_lech)
        self.assertIn('version', str(ctx.exception))

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
        # spec_yaml phải tự khai đúng version='2.0' — kể từ khi thêm guard đối
        # chiếu code/version với YAML, không thể tái dùng YAML_HOP_LE nguyên
        # văn (khai version="1.0") cho bản ghi version='2.0'.
        self._create(version='2.0',
                     spec_yaml=YAML_HOP_LE.replace('version: "1.0"',
                                                   'version: "2.0"'))
        self.assertEqual(
            self.Ruleset.search_count([('code', '=', 'TEST')]), 2)

    def test_sua_yaml_thanh_sai_cung_bi_chan(self):
        ruleset = self._create()
        with self.assertRaises(ValidationError):
            ruleset.spec_yaml = 'ruleset: chi co mot khoa\n'

    def test_spec_tren_recordset_rong_bao_loi_ro_rang(self):
        # spec()/_parse_yaml() không có test nào gọi trên recordset rỗng.
        # Với >1 bản ghi, chính field getter của Odoo đã tự ensure_one() nên
        # self.ensure_one() ở _parse_yaml là thừa cho trường hợp đó — đã kiểm
        # bằng thực nghiệm (xoá dòng đó, recordset 2 bản ghi vẫn báo lỗi y hệt).
        # Nhưng với recordset RỖNG thì field getter trả giá trị null (không
        # raise), nên nếu thiếu self.ensure_one() thì spec() sẽ rơi xuống
        # nhánh "không phải từ điển" với thông điệp vô nghĩa ("Bộ luật False
        # phải là...") thay vì báo rõ ràng là gọi sai trên recordset rỗng.
        rong = self.Ruleset.browse([])
        with self.assertRaises(ValueError):
            rong.spec()


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
