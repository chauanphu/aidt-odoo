"""Đối chiếu định dạng hiệu lực với bộ luật, sinh danh sách phát hiện.

Đây là vòng lặp generic: KHÔNG có nhánh nào cho từng quy định cụ thể. Thấy mình
viết `if ruleset == '66-QD/TW'` là thiết kế đã sai — quy định nằm trong dữ liệu.
"""
from dataclasses import replace

from .findings import ERROR, WARNING, Finding

_A4_MM = (210.0, 297.0)
_A4_SAI_SO_MM = 2.0


def run_rules(doc, spec):
    zones_spec = spec.get('zones') or {}
    findings = []
    findings += _page_rules(doc, spec)
    findings += _required_rules(doc, zones_spec)
    for para in doc.paras:
        rules = zones_spec.get(para.zone)
        if rules:
            findings += _para_rules(para, rules)
    findings += _conflict_rules(doc)
    findings += _standard_rules(doc, spec)
    return _apply_severity(findings, doc, spec)


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
                suggestion='Đặt lề %s trong khoảng %s'
                           % (side, _range_text(low, high, 'mm'))))
    return out


# -- vùng bắt buộc ---------------------------------------------------------

def _required_rules(doc, zones_spec):
    present = {para.zone for para in doc.paras if (para.text or '').strip()}
    out = []
    for zone, rules in zones_spec.items():
        if rules.get('required') and zone not in present:
            out.append(Finding(
                rule_id='%s.required' % zone, severity=ERROR, zone=zone,
                location='Toàn văn bản',
                expected='Văn bản phải có vùng "%s"' % zone,
                actual='Không tìm thấy',
                suggestion='Bổ sung vùng "%s" theo mẫu của hệ thống' % zone))
    return out


# -- thuộc tính từng đoạn --------------------------------------------------

def _para_rules(para, rules):
    fmt = para.fmt
    location = 'Đoạn %d' % (para.index + 1)
    out = []

    def add(attr, expected, actual, suggestion):
        out.append(Finding(
            rule_id='%s.%s' % (para.zone, attr), severity=ERROR,
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
            add('align', ' hoặc '.join(allowed), fmt.align,
                'Căn đoạn này theo %s' % ' hoặc '.join(allowed))

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

def _apply_severity(findings, doc, spec):
    overrides = spec.get('severity_overrides') or {}
    doan_duoc = {para.zone for para in doc.paras
                 if para.zone_confidence == 'heuristic'}
    out = []
    for finding in findings:
        severity = overrides.get(finding.rule_id, finding.severity)
        # Vùng chỉ đoán được thì không chặn — tránh chặn oan người soạn tay
        # ngoài mẫu. Áp SAU overrides để override không bị bỏ qua.
        if severity == ERROR and finding.zone and finding.zone in doan_duoc:
            severity = WARNING
        out.append(finding if severity == finding.severity
                   else replace(finding, severity=severity))
    return out


def _range_text(low, high, unit):
    if low == high:
        return '%g%s' % (low, unit)
    return '%g–%g%s' % (low, high, unit)
