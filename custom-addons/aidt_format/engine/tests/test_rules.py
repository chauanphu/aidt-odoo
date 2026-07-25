import copy
import unittest

import fixtures
from engine.parser import parse_docx
from engine.rules import run_rules
from engine.types import EffFormat, IntermediateDoc, PageSetup, Para
from engine.zones import detect_zones

RULESET_66 = {
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
        'so_ky_hieu': {'required': True, 'size_pt': [14, 14]},
        'trich_yeu': {'required': True, 'font': 'Times New Roman',
                      'size_pt': [14, 14], 'bold': True, 'align': 'center'},
        'noi_dung': {'font': 'Times New Roman', 'size_pt': [14, 15],
                     'line_spacing': [1.0, 1.5],
                     'line_spacing_fixed_allowed': False,
                     'first_line_indent_cm': [1.0, 1.27],
                     'align': ['justify']},
        'noi_nhan': {'required': True, 'size_pt': [12, 12]},
        'chu_ky': {'required': True, 'uppercase': True, 'align': 'right'},
    },
    'severity_overrides': {},
}


def _check(blob, spec=None):
    doc = detect_zones(parse_docx(blob))
    return run_rules(doc, spec or copy.deepcopy(RULESET_66))


def _ids(findings):
    return {finding.rule_id for finding in findings}


def _by_id(findings, rule_id):
    return [f for f in findings if f.rule_id == rule_id]


class TestFileDat(unittest.TestCase):
    def test_chuan_66_khong_co_finding(self):
        findings = _check(fixtures.chuan_66())
        self.assertEqual(findings, [], _ids(findings))


class TestPage(unittest.TestCase):
    def test_le_tren_ngoai_khoang(self):
        findings = _check(fixtures.sai_le_trang())
        self.assertIn('page.margin_top', _ids(findings))

    def test_finding_le_neu_ro_mong_doi_va_thuc_te(self):
        finding = _by_id(_check(fixtures.sai_le_trang()),
                         'page.margin_top')[0]
        self.assertIn('20', finding.expected)
        self.assertIn('25', finding.expected)
        self.assertIn('10', finding.actual)

    def test_le_khac_khong_bao_oan(self):
        ids = _ids(_check(fixtures.sai_le_trang()))
        self.assertNotIn('page.margin_left', ids)
        self.assertNotIn('page.margin_bottom', ids)


class TestVungBatBuoc(unittest.TestCase):
    def test_thieu_noi_nhan(self):
        findings = _check(fixtures.thieu_noi_nhan())
        self.assertIn('noi_nhan.required', _ids(findings))

    def test_thieu_vung_la_loi_chan(self):
        finding = _by_id(_check(fixtures.thieu_noi_nhan()),
                         'noi_nhan.required')[0]
        self.assertEqual(finding.severity, 'error')


class TestThuocTinhVung(unittest.TestCase):
    def test_sai_font_bat_duoc_qua_chuoi_ke_thua(self):
        findings = _check(fixtures.sai_font())
        self.assertIn('noi_dung.font', _ids(findings))
        finding = _by_id(findings, 'noi_dung.font')[0]
        self.assertEqual(finding.actual, 'Arial')
        self.assertEqual(finding.expected, 'Times New Roman')

    def test_dan_dong_tuyet_doi_bi_cam(self):
        findings = _check(fixtures.sai_dan_dong_exact())
        self.assertIn('noi_dung.line_spacing_fixed', _ids(findings))

    def test_location_neu_so_doan(self):
        finding = _by_id(_check(fixtures.sai_font()), 'noi_dung.font')[0]
        self.assertRegex(finding.location, r'Đoạn \d+')


class TestRunLechNhau(unittest.TestCase):
    def test_bao_runs_conflict(self):
        findings = _check(fixtures.run_lech_nhau())
        self.assertIn('doc.runs_conflict', _ids(findings))

    def test_runs_conflict_chi_la_canh_bao(self):
        finding = _by_id(_check(fixtures.run_lech_nhau()),
                         'doc.runs_conflict')[0]
        self.assertEqual(finding.severity, 'warning')


class TestSeverityOverrides(unittest.TestCase):
    def test_override_ha_xuong_warning(self):
        spec = copy.deepcopy(RULESET_66)
        spec['severity_overrides'] = {'noi_dung.font': 'warning'}
        finding = _by_id(_check(fixtures.sai_font(), spec), 'noi_dung.font')[0]
        self.assertEqual(finding.severity, 'warning')

    def test_khong_override_thi_la_error(self):
        finding = _by_id(_check(fixtures.sai_font()), 'noi_dung.font')[0]
        self.assertEqual(finding.severity, 'error')


class TestHeuristicHaMucDo(unittest.TestCase):
    def test_vung_chi_doan_duoc_thi_khong_chan(self):
        """khong_co_style() chạy heuristic hết, nên không finding nào là error."""
        findings = _check(fixtures.khong_co_style())
        self.assertTrue(findings, 'phải có ít nhất một finding để test có nghĩa')
        for finding in findings:
            if finding.zone:
                self.assertEqual(finding.severity, 'warning',
                                 '%s không được chặn' % finding.rule_id)


class TestSaiHeQuyChuan(unittest.TestCase):
    def test_file_hanh_chinh_kiem_bang_bo_luat_dang(self):
        findings = _check(fixtures.chuan_nd30())
        self.assertIn('file.wrong_standard', _ids(findings))
        finding = _by_id(findings, 'file.wrong_standard')[0]
        self.assertEqual(finding.severity, 'warning')

    def test_file_dung_he_quy_chuan_khong_bao(self):
        self.assertNotIn('file.wrong_standard', _ids(_check(fixtures.chuan_66())))


# -- các test bổ sung sau mutation testing (Task 7) -------------------------
#
# Năm phép phá bắt buộc lộ ra bốn lỗ hổng thật trong bộ test do brief cung cấp:
# thứ tự áp severity, guard finding.zone, guard 'required', guard fmt.font.
# Các test dưới đây đóng từng lỗ hổng đó — xem task-7-report.md để biết chi
# tiết từng phép phá và vì sao lỗ hổng tồn tại.

class TestThuTuApSeverity(unittest.TestCase):
    def test_override_khong_thang_duoc_ha_muc_theo_heuristic(self):
        """zone_confidence hạ mức phải áp SAU severity_overrides và LÀ TIẾNG NÓI
        CUỐI CÙNG: override đặt 'error' cho một rule ở vùng chỉ đoán được
        (heuristic) vẫn phải bị hạ xuống 'warning'.

        Đảo thứ tự trong _apply_severity (hạ trước, override sau) làm override
        thắng, finding sẽ là 'error' — sai với chủ ý bảo vệ người soạn tay
        ngoài mẫu. Đây là phép phá số 1 trong yêu cầu mutation, nhưng bộ test
        gốc của brief không có test nào bắt được — không dùng khả năng
        override lẫn heuristic zone cùng lúc.
        """
        spec = copy.deepcopy(RULESET_66)
        spec['severity_overrides'] = {'tieu_de_dang.size_pt': 'error'}
        findings = _check(fixtures.khong_co_style(), spec)
        finding = _by_id(findings, 'tieu_de_dang.size_pt')[0]
        self.assertEqual(finding.severity, 'warning')


class TestFindingZoneRong(unittest.TestCase):
    def test_zone_rong_khong_bi_ha_theo_heuristic(self):
        """Finding zone='' (như file.wrong_standard) không thuộc vùng cụ thể
        nào, nên không được hạ mức theo zone_confidence dù có đoạn heuristic
        nào đó trùng chuỗi rỗng.

        Bỏ điều kiện `finding.zone and` trong _apply_severity (phép phá số 2)
        khiến '' in doan_duoc trở thành phép so sánh thật khi có para với
        zone='' — dựng thủ công para này để buộc code đi qua nhánh đó, vì
        pipeline parser/zones thật không bao giờ sinh ra zone=''.
        """
        para = Para(index=0, text='noi dung', style_name=None,
                    fmt=EffFormat(), zone='', zone_confidence='heuristic')
        doc = IntermediateDoc(pages=PageSetup(), paras=[para],
                              standard_hint='hanh_chinh')
        spec = copy.deepcopy(RULESET_66)
        spec['zones'] = {}
        spec['severity_overrides'] = {'file.wrong_standard': 'error'}
        findings = run_rules(doc, spec)
        finding = _by_id(findings, 'file.wrong_standard')[0]
        self.assertEqual(finding.severity, 'error')


class TestVungKhongRequired(unittest.TestCase):
    def test_zone_khong_required_thi_khong_bao_khi_thieu(self):
        """Vùng không khai required:True thì thiếu cũng không phải lỗi.

        Bỏ kiểm `rules.get('required')` trong _required_rules (phép phá số 3)
        báo thiếu cho MỌI vùng vắng mặt, kể cả vùng không bắt buộc. Không
        fixture nào của brief có vùng required=False mà lại thiếu, nên phải
        đổi spec ngay tại test này.
        """
        spec = copy.deepcopy(RULESET_66)
        spec['zones']['noi_nhan'] = {'size_pt': [12, 12]}  # bỏ required: True
        findings = _check(fixtures.thieu_noi_nhan(), spec)
        self.assertNotIn('noi_nhan.required', _ids(findings))


class TestFontKhongXacDinh(unittest.TestCase):
    def test_font_none_khong_bi_bao_sai(self):
        """fmt.font=None nghĩa là không xác định được phông (chuỗi kế thừa
        không giải được), không phải 'phông sai' — không được sinh finding.

        Bỏ điều kiện `fmt.font` (chỉ còn `'font' in rules`) trong _para_rules
        (phép phá số 4) khiến None != 'Times New Roman' vẫn đúng, sinh finding
        báo actual=None — sai. Không fixture nào của brief để fmt.font ra
        None (resolver luôn giải được font qua Normal), nên phải dựng Para
        thủ công.
        """
        para = Para(index=0, text='Nội dung', style_name=None,
                    fmt=EffFormat(font=None), zone='noi_dung',
                    zone_confidence='style')
        doc = IntermediateDoc(pages=PageSetup(), paras=[para])
        spec = copy.deepcopy(RULESET_66)
        spec['zones'] = {'noi_dung': {'font': 'Times New Roman'}}
        findings = run_rules(doc, spec)
        self.assertNotIn('noi_dung.font', _ids(findings))


class TestDanDongNgoaiKhoang(unittest.TestCase):
    def test_dan_dong_multiple_ngoai_khoang_bi_bao(self):
        """Dãn dòng kiểu Multiple (không phải Exactly/At least) nhưng ngoài
        khoảng [1.0, 1.5] vẫn phải bị báo — nhánh này chưa fixture nào của
        brief chạm tới (chỉ có sai_dan_dong_exact() kiểm dãn dòng tuyệt đối
        bị cấm, không kiểm khoảng số của dãn dòng Multiple). Tự nghĩ thêm khi
        rà lại _para_rules theo gợi ý 'nhánh nào không fixture nào chạm tới'.
        """
        para = Para(index=0, text='Nội dung', style_name=None,
                    fmt=EffFormat(line_spacing=2.0, line_spacing_fixed=False),
                    zone='noi_dung', zone_confidence='style')
        doc = IntermediateDoc(pages=PageSetup(), paras=[para])
        spec = copy.deepcopy(RULESET_66)
        spec['zones'] = {'noi_dung': {'line_spacing': [1.0, 1.5]}}
        findings = run_rules(doc, spec)
        self.assertIn('noi_dung.line_spacing', _ids(findings))


# -- phản hồi code review: 5 bộ phát hiện có 0% coverage --------------------
#
# Reviewer vô hiệu hóa CÙNG LÚC 5 nhánh sinh finding (sai khổ A4, vòng
# bold/italic, uppercase, align, first_line_indent_cm) và cả 92 test vẫn
# xanh. Đây là quy định sống trong RULESET_66, không phải trường hợp biên —
# nên bịt bằng fixture .docx thật (đi qua đúng đường resolver/parser/zones),
# không dựng Para thủ công.

class TestQuyDinhChuaTungDuocPhu(unittest.TestCase):
    """Năm bộ phát hiện từng có 0% coverage: xóa sạch chúng mà suite vẫn xanh."""

    def test_sai_bold_uppercase_align_indent(self):
        ids = _ids(_check(fixtures.sai_nhieu_thuoc_tinh()))
        self.assertIn('tieu_de_dang.bold', ids)
        self.assertIn('tieu_de_dang.uppercase', ids)
        self.assertIn('trich_yeu.align', ids)
        self.assertIn('noi_dung.first_line_indent_cm', ids)

    def test_sai_kho_giay(self):
        self.assertIn('page.size', _ids(_check(fixtures.khong_phai_a4())))

    def test_italic_bat_duoc(self):
        """italic không nằm trong RULESET_66 của bộ test (không zone nào khai
        thuộc tính này) nên fixture .docx không kích hoạt được nó — vòng
        bold/italic dùng chung một khối code, nhưng nhánh cho riêng 'italic'
        (rules.py:99) cần một spec cục bộ có khai 'italic' mới thật sự chạy
        qua nhánh tạo finding. Dựng Para thủ công ở đây là hợp lý vì mục tiêu
        chỉ là chạm đúng nhánh, không phải kiểm đường đi resolver/parser."""
        para = Para(index=0, text='Nội dung', style_name=None,
                    fmt=EffFormat(italic=True), zone='noi_dung',
                    zone_confidence='style')
        doc = IntermediateDoc(pages=PageSetup(), paras=[para])
        spec = copy.deepcopy(RULESET_66)
        spec['zones'] = {'noi_dung': {'italic': False}}
        findings = run_rules(doc, spec)
        self.assertIn('noi_dung.italic', _ids(findings))


class TestBienCuaKhoang(unittest.TestCase):
    """lo <= x <= hi: đúng bằng biên phải ĐẠT, vượt một chút phải BÁO.

    Dùng Para dựng tay, không qua fixture .docx, vì cần giá trị chính xác tới
    từng số lẻ: chuan_66() không ghim được điều này, vì thụt đầu dòng của nó
    thật ra là 1.2698412698412698cm chứ không phải 1.27cm — Mm(12.7) đi qua
    EMU→twip (720 twip, tròn đúng) rồi twip→cm bằng TWIP_PER_CM=567.0 (một
    xấp xỉ của giá trị thật 566.929...), hụt ~0.0002cm. Nhìn %.2f thì tưởng
    sát biên, nhưng số thật không chạm biên nên không ghim được hành vi biên.
    """

    @staticmethod
    def _run(zone, rules, **fmt_kwargs):
        para = Para(index=0, text='Nội dung', style_name=None,
                    fmt=EffFormat(**fmt_kwargs), zone=zone,
                    zone_confidence='style')
        doc = IntermediateDoc(pages=PageSetup(), paras=[para])
        spec = {'ruleset': 'test', 'version': '1', 'ap_dung': 'dang',
                'zones': {zone: rules}, 'severity_overrides': {}}
        return _ids(run_rules(doc, spec))

    # -- size_pt --------------------------------------------------------
    def test_size_pt_dung_bang_bien_duoi_thi_dat(self):
        ids = self._run('noi_dung', {'size_pt': [14, 15]}, size_pt=14.0)
        self.assertNotIn('noi_dung.size_pt', ids)

    def test_size_pt_dung_bang_bien_tren_thi_dat(self):
        ids = self._run('noi_dung', {'size_pt': [14, 15]}, size_pt=15.0)
        self.assertNotIn('noi_dung.size_pt', ids)

    def test_size_pt_duoi_bien_duoi_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'size_pt': [14, 15]}, size_pt=13.9)
        self.assertIn('noi_dung.size_pt', ids)

    def test_size_pt_vuot_bien_tren_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'size_pt': [14, 15]}, size_pt=15.1)
        self.assertIn('noi_dung.size_pt', ids)

    # -- line_spacing -----------------------------------------------------
    def test_line_spacing_dung_bang_bien_duoi_thi_dat(self):
        ids = self._run('noi_dung', {'line_spacing': [1.0, 1.5]},
                        line_spacing=1.0)
        self.assertNotIn('noi_dung.line_spacing', ids)

    def test_line_spacing_dung_bang_bien_tren_thi_dat(self):
        ids = self._run('noi_dung', {'line_spacing': [1.0, 1.5]},
                        line_spacing=1.5)
        self.assertNotIn('noi_dung.line_spacing', ids)

    def test_line_spacing_duoi_bien_duoi_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'line_spacing': [1.0, 1.5]},
                        line_spacing=0.99)
        self.assertIn('noi_dung.line_spacing', ids)

    def test_line_spacing_vuot_bien_tren_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'line_spacing': [1.0, 1.5]},
                        line_spacing=1.51)
        self.assertIn('noi_dung.line_spacing', ids)

    # -- first_line_indent_cm ---------------------------------------------
    def test_indent_dung_bang_bien_duoi_thi_dat(self):
        ids = self._run('noi_dung', {'first_line_indent_cm': [1.0, 1.27]},
                        first_line_indent_cm=1.0)
        self.assertNotIn('noi_dung.first_line_indent_cm', ids)

    def test_indent_dung_bang_bien_tren_thi_dat(self):
        ids = self._run('noi_dung', {'first_line_indent_cm': [1.0, 1.27]},
                        first_line_indent_cm=1.27)
        self.assertNotIn('noi_dung.first_line_indent_cm', ids)

    def test_indent_duoi_bien_duoi_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'first_line_indent_cm': [1.0, 1.27]},
                        first_line_indent_cm=0.99)
        self.assertIn('noi_dung.first_line_indent_cm', ids)

    def test_indent_vuot_bien_tren_mot_chut_thi_bao(self):
        ids = self._run('noi_dung', {'first_line_indent_cm': [1.0, 1.27]},
                        first_line_indent_cm=1.28)
        self.assertIn('noi_dung.first_line_indent_cm', ids)


if __name__ == '__main__':
    unittest.main()
