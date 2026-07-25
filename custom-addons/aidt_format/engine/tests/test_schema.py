import copy
import unittest

from engine.schema import RulesetError, validate_ruleset

HOP_LE = {
    'ruleset': '66-QD/TW',
    'version': '2025.1',
    'ap_dung': 'dang',
    'so_ky_hieu': {
        'format': '{n}-{type_code}/{org_code}',
        'stamp_box_mm': {'x': 30, 'y': 52, 'w': 60, 'h': 8},
    },
    'page': {
        'size': 'A4',
        'margins_mm': {'top': [20, 25], 'bottom': [20, 25],
                       'left': [30, 35], 'right': [15, 20]},
    },
    'zones': {
        'tieu_de_dang': {'required': True, 'font': 'Times New Roman',
                         'size_pt': [15, 15], 'bold': True,
                         'uppercase': True, 'align': 'center'},
        'noi_dung': {'font': 'Times New Roman', 'size_pt': [14, 15],
                     'line_spacing': [1.0, 1.5],
                     'line_spacing_fixed_allowed': False,
                     'first_line_indent_cm': [1.0, 1.27],
                     'align': ['justify']},
    },
    'severity_overrides': {'noi_dung.size_pt': 'warning'},
}


def _without(path):
    spec = copy.deepcopy(HOP_LE)
    target, key = spec, path[-1]
    for part in path[:-1]:
        target = target[part]
    del target[key]
    return spec


def _with(path, value):
    spec = copy.deepcopy(HOP_LE)
    target = spec
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return spec


class TestSchema(unittest.TestCase):
    def test_bo_luat_hop_le_khong_bao_loi(self):
        validate_ruleset(copy.deepcopy(HOP_LE))

    def test_khong_phai_dict(self):
        with self.assertRaises(RulesetError):
            validate_ruleset(['khong', 'phai', 'dict'])

    def test_thieu_khoa_bat_buoc(self):
        for key in ('ruleset', 'version', 'ap_dung'):
            with self.subTest(key=key), self.assertRaises(RulesetError) as ctx:
                validate_ruleset(_without([key]))
            self.assertEqual(ctx.exception.path, key)

    def test_ap_dung_sai_gia_tri(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['ap_dung'], 'van_ban_dang'))
        self.assertEqual(ctx.exception.path, 'ap_dung')

    def test_format_thieu_bien(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['so_ky_hieu', 'format'], '{n}/{type_code}'))
        self.assertEqual(ctx.exception.path, 'so_ky_hieu.format')

    def test_stamp_box_thieu_chieu(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['so_ky_hieu', 'stamp_box_mm'], {'x': 30, 'y': 52}))
        self.assertEqual(ctx.exception.path, 'so_ky_hieu.stamp_box_mm.w')

    def test_page_size_khong_phai_A4(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'size'], 'Letter'))
        self.assertEqual(ctx.exception.path, 'page.size')

    def test_khoang_khong_phai_cap(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'margins_mm', 'top'], 20))
        self.assertEqual(ctx.exception.path, 'page.margins_mm.top')

    def test_khoang_min_lon_hon_max(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung', 'size_pt'], [15, 14]))
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.size_pt')

    def test_ten_vung_khong_hop_le(self):
        spec = copy.deepcopy(HOP_LE)
        spec['zones']['vung_bia_ra'] = {'required': True}
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(spec)
        self.assertEqual(ctx.exception.path, 'zones.vung_bia_ra')

    def test_thuoc_tinh_vung_khong_hop_le(self):
        spec = copy.deepcopy(HOP_LE)
        spec['zones']['noi_dung']['mau_chu'] = 'do'
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(spec)
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.mau_chu')

    def test_bool_khong_phai_bool(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung',
                                    'line_spacing_fixed_allowed'], 'khong'))
        self.assertEqual(
            ctx.exception.path, 'zones.noi_dung.line_spacing_fixed_allowed')

    def test_align_sai_gia_tri(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung', 'align'], ['giua']))
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.align')

    def test_severity_override_sai_muc(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['severity_overrides'], {'noi_dung.size_pt': 'nghiem'}))
        self.assertEqual(
            ctx.exception.path, 'severity_overrides.noi_dung.size_pt')

    def test_severity_override_tro_toi_vung_khong_ton_tai(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['severity_overrides'], {'vung_la.size_pt': 'warning'}))
        self.assertEqual(ctx.exception.path, 'severity_overrides.vung_la.size_pt')

    def test_loi_co_duong_dan_trong_thong_diep(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'size'], 'Letter'))
        self.assertIn('page.size', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
