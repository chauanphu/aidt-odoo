import copy
import unittest

from aidt_format_engine.schema import RulesetError, ZONE_ATTRS, validate_ruleset

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

    def test_moi_nhanh_phong_thu_neu_dung_duong_dan(self):
        """Các nhánh kiểm kiểu và thiếu khóa: mỗi cái phải nêu ĐÚNG path.

        Gộp bằng subTest vì chúng cùng một hình dạng. Trước bản này, 18 nhánh
        trong schema.py chưa có test nào đi qua — branch coverage 80%.
        """
        truong_hop = [
            (_with(['version'], '   '), 'version'),
            (_without(['so_ky_hieu']), 'so_ky_hieu'),
            (_with(['so_ky_hieu'], 'khong phai dict'), 'so_ky_hieu'),
            (_with(['so_ky_hieu', 'format'], 123), 'so_ky_hieu.format'),
            (_with(['so_ky_hieu', 'stamp_box_mm'], 'khong phai dict'),
             'so_ky_hieu.stamp_box_mm'),
            (_with(['so_ky_hieu', 'stamp_box_mm'],
                   {'x': 'a', 'y': 52, 'w': 60, 'h': 8}),
             'so_ky_hieu.stamp_box_mm.x'),
            (_without(['page']), 'page'),
            (_with(['page'], 'khong phai dict'), 'page'),
            (_with(['page', 'margins_mm'], 'khong phai dict'), 'page.margins_mm'),
            (_without(['page', 'margins_mm', 'left']), 'page.margins_mm.left'),
            (_without(['zones']), 'zones'),
            (_with(['zones'], {}), 'zones'),
            (_with(['zones', 'noi_dung'], 'khong phai dict'), 'zones.noi_dung'),
            (_with(['zones', 'noi_dung', 'font'], '   '), 'zones.noi_dung.font'),
            (_with(['zones', 'noi_dung', 'size_pt'], ['a', 15]),
             'zones.noi_dung.size_pt'),
            (_with(['severity_overrides'], 'khong phai dict'), 'severity_overrides'),
            (_with(['severity_overrides'], {'khong_co_cham': 'warning'}),
             'severity_overrides.khong_co_cham'),
            (_with(['severity_overrides'], {'noi_dung.mau_chu': 'warning'}),
             'severity_overrides.noi_dung.mau_chu'),
        ]
        for spec, path in truong_hop:
            with self.subTest(path=path):
                with self.assertRaises(RulesetError) as ctx:
                    validate_ruleset(spec)
                self.assertEqual(ctx.exception.path, path)

    def test_bool_khong_duoc_tinh_la_so(self):
        """Trong Python isinstance(True, int) là True, nên _is_number phải
        loại bool ra bằng tay. Không có test này thì chủ ý đó không được bảo vệ."""
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung', 'size_pt'], [True, 15]))
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.size_pt')

    def test_severity_override_cho_page_duoc_cho_qua(self):
        """'page' không thuộc ZONES nhưng vẫn là khóa override hợp lệ.

        Ngoại lệ có chủ ý. Không có test thì ai đó xóa nhánh continue mà
        không ai biết.
        """
        validate_ruleset(_with(['severity_overrides'], {'page.margin_top': 'warning'}))

    def test_thieu_severity_overrides_van_hop_le(self):
        """severity_overrides là khóa tùy chọn."""
        validate_ruleset(_without(['severity_overrides']))

    def test_severity_override_page_hop_le_theo_danh_sach(self):
        for attr in ('size', 'margin_top', 'margin_bottom',
                     'margin_left', 'margin_right'):
            with self.subTest(attr=attr):
                validate_ruleset(_with(['severity_overrides'],
                                       {'page.%s' % attr: 'warning'}))

    def test_severity_override_page_go_sai_bi_tu_choi(self):
        """M3: 'page.margin_topp' (gõ sai) trước đây được cho qua im lặng,
        không có tác dụng gì trong rule engine."""
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['severity_overrides'],
                                   {'page.margin_topp': 'warning'}))
        self.assertEqual(ctx.exception.path,
                         'severity_overrides.page.margin_topp')

    def test_severity_override_page_thuoc_tinh_khong_ton_tai_bi_tu_choi(self):
        """M3: 'page.gibberish' — khóa không tồn tại trong rule engine —
        trước đây cũng được cho qua im lặng."""
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['severity_overrides'],
                                   {'page.gibberish': 'warning'}))
        self.assertEqual(ctx.exception.path,
                         'severity_overrides.page.gibberish')

    def test_ZONE_ATTRS_dung_bo_thuoc_tinh_rule_engine_doc(self):
        """Thừa một tên: ruleset sai được cho qua rồi rule engine lặng lẽ bỏ
        qua thuộc tính đó — cơ quan tưởng đã cấu hình một quy định mà thực tế
        nó không bao giờ được kiểm. Thiếu một tên: ruleset hợp lệ bị từ chối.
        """
        self.assertEqual(set(ZONE_ATTRS), {
            'required', 'font', 'size_pt', 'bold', 'italic', 'uppercase',
            'align', 'line_spacing', 'line_spacing_fixed_allowed',
            'first_line_indent_cm'})

    def test_moi_rule_id_engine_phat_ra_deu_ghi_de_duoc_muc_do(self):
        """Tên thuộc tính cấu hình và rule_id không phải lúc nào cũng trùng.

        `line_spacing_fixed_allowed` là cờ bật/tắt trong ruleset, còn vi phạm
        sinh ra mang rule_id `<vùng>.line_spacing_fixed`. Schema chỉ kiểm theo
        ZONE_ATTRS thì có một quy định engine phát hiện được mà không ai chỉnh
        được mức nghiêm trọng của nó — seed ND-30 đã vấp đúng lỗi này khi cần
        hạ line_spacing_fixed xuống cảnh báo.
        """
        for attr in ('required', 'font', 'size_pt', 'bold', 'italic',
                     'uppercase', 'align', 'line_spacing',
                     'line_spacing_fixed', 'first_line_indent_cm'):
            with self.subTest(attr=attr):
                validate_ruleset(
                    _with(['severity_overrides'],
                          {'noi_dung.%s' % attr: 'warning'}))


if __name__ == '__main__':
    unittest.main()
