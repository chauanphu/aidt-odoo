"""Đối chiếu định dạng hiệu lực với bộ luật, sinh danh sách phát hiện.

Đây là vòng lặp generic: KHÔNG có nhánh nào cho từng quy định cụ thể. Thấy mình
viết `if ruleset == '66-QD/TW'` là thiết kế đã sai — quy định nằm trong dữ liệu.
"""
from dataclasses import replace

from .findings import ERROR, WARNING, Finding
from .zones import TEN_VUNG

_A4_MM = (210.0, 297.0)
_A4_SAI_SO_MM = 2.0

# Tên tiếng Việt cho các giá trị hiển thị trong thông điệp — người đọc là
# văn thư, không phải lập trình viên, nên không được thấy 'center' hay 'top'.
_TEN_CAN = {'left': 'căn trái', 'center': 'căn giữa', 'right': 'căn phải',
            'justify': 'căn đều hai bên'}
_TEN_LE = {'top': 'lề trên', 'bottom': 'lề dưới', 'left': 'lề trái',
           'right': 'lề phải'}


def run_rules(doc, spec):
    zones_spec = spec.get('zones') or {}
    overrides = spec.get('severity_overrides') or {}
    findings = []
    findings += _apply_overrides(_page_rules(doc, spec), overrides)
    findings += _apply_overrides(_required_rules(doc, zones_spec), overrides)
    for para in doc.paras:
        rules = zones_spec.get(para.zone)
        if rules:
            # Hạ mức theo zone_confidence của CHÍNH đoạn sinh ra finding
            # (quyết ngay tại đây, nơi có `para`) — không phải theo cả vùng.
            # Xem _para_rules để biết vì sao và severity_overrides áp trước.
            findings += _para_rules(para, rules, overrides)
    findings += _apply_overrides(_conflict_rules(doc), overrides)
    findings += _apply_overrides(_standard_rules(doc, spec), overrides)
    return findings


# -- trang -----------------------------------------------------------------

def _page_rules(doc, spec):
    page = spec.get('page') or {}
    out = []
    if page.get('size') == 'A4':
        for value, expected, name in ((doc.pages.width_mm, _A4_MM[0], 'rộng'),
                                      (doc.pages.height_mm, _A4_MM[1], 'cao')):
            if value is not None and abs(value - expected) > _A4_SAI_SO_MM:
                out.append(Finding(
                    rule_id='page.size', severity=ERROR, zone='page',
                    location='Thiết lập trang',
                    expected='A4 (%gmm × %gmm)' % _A4_MM,
                    actual='%s %gmm' % (name, value),
                    suggestion='Đặt khổ giấy A4 trong Layout > Size'))
                break
    for side, bounds in (page.get('margins_mm') or {}).items():
        actual = doc.pages.margin_mm.get(side)
        if actual is None:
            continue
        low, high = bounds
        if not low <= actual <= high:
            out.append(Finding(
                rule_id='page.margin_%s' % side, severity=ERROR, zone='page',
                location='Thiết lập trang',
                expected=_range_text(low, high, 'mm'),
                actual='%gmm' % round(actual, 1),
                suggestion='Đặt %s trong khoảng %s'
                           % (_TEN_LE.get(side, side),
                              _range_text(low, high, 'mm'))))
    return out


# -- vùng bắt buộc ---------------------------------------------------------

def _required_rules(doc, zones_spec):
    present = {para.zone for para in doc.paras if (para.text or '').strip()}
    out = []
    for zone, rules in zones_spec.items():
        if rules.get('required') and zone not in present:
            ten = TEN_VUNG.get(zone, zone)
            out.append(Finding(
                rule_id='%s.required' % zone, severity=ERROR, zone=zone,
                location='Toàn văn bản',
                expected='Văn bản phải có vùng "%s"' % ten,
                actual='Không tìm thấy',
                suggestion='Bổ sung vùng "%s" theo mẫu của hệ thống' % ten))
    return out


# -- thuộc tính từng đoạn --------------------------------------------------

def _para_rules(para, rules, overrides):
    """Sinh finding cho một đoạn cụ thể.

    C3: mức nghiêm trọng quyết NGAY TẠI ĐÂY, theo `para.zone_confidence` của
    chính đoạn này — không hậu xử lý theo cả vùng. Trước đây `_apply_severity`
    hạ mọi finding thuộc một VÙNG xuống warning hễ vùng đó có BẤT KỲ đoạn nào
    heuristic, kể cả khi finding đang xét lại sinh ra từ một đoạn khác có
    zone_confidence='style'. Word luôn để lại đoạn trống (heuristic, mặc
    định rơi vào 'noi_dung') nên cổng chặn ở vùng nội dung trên thực tế
    không bao giờ chặn — lỗi im lặng, test vẫn xanh, chỉ severity sai.

    Thứ tự giữ nguyên: severity_overrides áp TRƯỚC, hạ theo confidence áp
    SAU — hạ theo confidence là tiếng nói cuối cùng, override không thắng
    được nó (bảo vệ người soạn tay ngoài mẫu khỏi bị chặn oan).
    """
    # Đoạn không có chữ thì không có gì để kiểm thể thức: phông, cỡ chữ, căn lề
    # của một đoạn rỗng không nói lên điều gì. Word để lại đoạn rỗng khắp nơi —
    # ô bảng chưa điền, dòng cách, đoạn cuối file — và mỗi cái vốn sinh ra hai
    # phát hiện vô nghĩa (phông + cỡ chữ) ngay trên văn bản đúng chuẩn. Bắt
    # được nhờ chạy thử trên văn bản mẫu thật, không test nào trong 128 test thấy.
    if not (para.text or '').strip():
        return []

    fmt = para.fmt
    location = 'Đoạn %d' % (para.index + 1)
    out = []

    def add(attr, expected, actual, suggestion):
        rule_id = '%s.%s' % (para.zone, attr)
        severity = overrides.get(rule_id, ERROR)
        if para.zone_confidence == 'heuristic':
            severity = WARNING
        out.append(Finding(
            rule_id=rule_id, severity=severity,
            zone=para.zone, location=location, expected=expected,
            actual=actual, suggestion=suggestion))

    if 'font' in rules and fmt.font and fmt.font != rules['font']:
        add('font', rules['font'], fmt.font,
            'Đặt phông chữ %s cho đoạn này' % rules['font'])

    if 'size_pt' in rules and fmt.size_pt is not None:
        low, high = rules['size_pt']
        if not low <= fmt.size_pt <= high:
            add('size_pt', _range_text(low, high, 'pt'), '%gpt' % fmt.size_pt,
                'Đặt cỡ chữ %s' % _range_text(low, high, 'pt'))

    for attr, nhan in (('bold', 'in đậm'), ('italic', 'in nghiêng')):
        if attr in rules and getattr(fmt, attr) is not None \
                and bool(getattr(fmt, attr)) != bool(rules[attr]):
            add(attr, 'có %s' % nhan if rules[attr] else 'không %s' % nhan,
                'có %s' % nhan if getattr(fmt, attr) else 'không %s' % nhan,
                '%s chữ cho đoạn này' % ('Bật ' + nhan if rules[attr]
                                         else 'Tắt ' + nhan))

    text = (para.text or '').strip()
    if rules.get('uppercase') and text and text != text.upper():
        add('uppercase', 'Viết hoa toàn bộ', text[:40],
            'Chuyển đoạn này sang chữ in hoa')

    if 'align' in rules and fmt.align:
        allowed = rules['align'] if isinstance(rules['align'], list) \
            else [rules['align']]
        if fmt.align not in allowed:
            ten_allowed = ' hoặc '.join(_TEN_CAN.get(a, a) for a in allowed)
            add('align', ten_allowed, _TEN_CAN.get(fmt.align, fmt.align),
                'Đặt căn lề đoạn này: %s' % ten_allowed)

    if 'line_spacing' in rules and fmt.line_spacing is not None:
        low, high = rules['line_spacing']
        if not low <= fmt.line_spacing <= high:
            add('line_spacing', _range_text(low, high, ' lần dòng'),
                '%.2f lần dòng' % fmt.line_spacing,
                'Đặt dãn dòng Multiple trong khoảng %s'
                % _range_text(low, high, ''))

    if rules.get('line_spacing_fixed_allowed') is False and fmt.line_spacing_fixed:
        add('line_spacing_fixed', 'Dãn dòng khai theo số lần dòng (Multiple)',
            'Dãn dòng khai theo chiều cao tuyệt đối (Exactly/At least)',
            'Đổi Line spacing sang Multiple')

    if 'first_line_indent_cm' in rules and fmt.first_line_indent_cm is not None:
        low, high = rules['first_line_indent_cm']
        if not low <= fmt.first_line_indent_cm <= high:
            add('first_line_indent_cm', _range_text(low, high, 'cm'),
                '%.2fcm' % fmt.first_line_indent_cm,
                'Đặt thụt đầu dòng %s' % _range_text(low, high, 'cm'))

    return out


# -- run lệch nhau ---------------------------------------------------------

def _conflict_rules(doc):
    return [
        Finding(
            rule_id='doc.runs_conflict', severity=WARNING,
            zone=para.zone or '', location='Đoạn %d' % (para.index + 1),
            expected='Cả đoạn dùng một phông và một cỡ chữ',
            actual='Trong đoạn có nhiều phông hoặc cỡ chữ khác nhau',
            suggestion='Chọn cả đoạn rồi đặt lại phông và cỡ chữ')
        for para in doc.paras if para.runs_conflict
    ]


# -- hệ quy chuẩn ----------------------------------------------------------

_TEN_CHUAN = {'dang': 'văn bản Đảng', 'hanh_chinh': 'văn bản hành chính'}


def _standard_rules(doc, spec):
    ap_dung = spec.get('ap_dung')
    if not doc.standard_hint or not ap_dung or doc.standard_hint == ap_dung:
        return []
    return [Finding(
        rule_id='file.wrong_standard', severity=WARNING, zone='',
        location='Toàn văn bản',
        expected='Bộ luật đang dùng cho %s' % _TEN_CHUAN.get(ap_dung, ap_dung),
        actual='Văn bản trông như %s'
               % _TEN_CHUAN.get(doc.standard_hint, doc.standard_hint),
        suggestion='Kiểm tra lại loại văn bản đã chọn')]


# -- mức nghiêm trọng ------------------------------------------------------

def _apply_overrides(findings, overrides):
    """Áp severity_overrides cho finding KHÔNG gắn với một đoạn cụ thể
    (page.*, <zone>.required, doc.runs_conflict, file.*).

    Các finding này không có zone_confidence để tra (không sinh ra từ một
    `para` cụ thể — required là vì vùng VẮNG MẶT, conflict/standard là mức
    toàn văn bản), nên không có gì để hạ theo confidence — giữ nguyên hành
    vi cũ, chỉ override mới đổi severity. Finding từ _para_rules KHÔNG đi
    qua đây vì severity của chúng đã quyết xong (override + hạ confidence)
    ngay lúc tạo.
    """
    out = []
    for finding in findings:
        severity = overrides.get(finding.rule_id, finding.severity)
        out.append(finding if severity == finding.severity
                   else replace(finding, severity=severity))
    return out


def _range_text(low, high, unit):
    if low == high:
        return '%g%s' % (low, unit)
    return '%g–%g%s' % (low, high, unit)
