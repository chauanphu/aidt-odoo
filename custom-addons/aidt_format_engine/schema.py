"""Kiểm cấu trúc bộ luật thể thức.

Bộ luật là dữ liệu do người dùng sửa, nên sai cú pháp là chuyện thường. Lỗi phải
nêu ĐÚNG ĐƯỜNG DẪN khóa sai, không phải 'ruleset không hợp lệ' — người sửa YAML
cần biết sửa ở dòng nào.
"""
from .zones import ZONES

ALIGN_VALUES = ('left', 'center', 'right', 'justify')
SEVERITIES = ('error', 'warning')
FORMAT_VARS = ('{n}', '{type_code}', '{org_code}')
STAMP_DIMS = ('x', 'y', 'w', 'h')

# Khóa hợp lệ cho severity_overrides.page.* — khớp đúng các rule_id mà
# _page_rules() trong rules.py thật sự sinh ra. Trước đây MỌI khóa
# 'page.<bất cứ gì>' đều được cho qua không kiểm, nên lỗi gõ (vd
# 'page.margin_topp') hay khóa không tồn tại (vd 'page.gibberish') lọt vào
# ruleset và im lặng không có tác dụng gì.
PAGE_OVERRIDE_ATTRS = ('size', 'margin_top', 'margin_bottom',
                       'margin_left', 'margin_right')

# tên thuộc tính vùng -> kiểu kiểm
ZONE_ATTRS = {
    'required': 'bool',
    'font': 'str',
    'size_pt': 'range',
    'bold': 'bool',
    'italic': 'bool',
    'uppercase': 'bool',
    'align': 'align',
    'line_spacing': 'range',
    'line_spacing_fixed_allowed': 'bool',
    'first_line_indent_cm': 'range',
}


class RulesetError(ValueError):
    def __init__(self, path, message):
        self.path = path
        super().__init__('%s: %s' % (path, message))


def validate_ruleset(spec):
    """Raise RulesetError nếu bộ luật sai cấu trúc. Trả None nếu hợp lệ."""
    if not isinstance(spec, dict):
        raise RulesetError('<gốc>', 'bộ luật phải là một từ điển khóa-giá trị')
    for key in ('ruleset', 'version', 'ap_dung'):
        if key not in spec:
            raise RulesetError(key, 'thiếu khóa bắt buộc')
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise RulesetError(key, 'phải là chuỗi không rỗng')
    if spec['ap_dung'] not in ('dang', 'hanh_chinh'):
        raise RulesetError('ap_dung', "phải là 'dang' hoặc 'hanh_chinh'")
    _check_so_ky_hieu(spec.get('so_ky_hieu'))
    _check_page(spec.get('page'))
    zones = _check_zones(spec.get('zones'))
    _check_severity_overrides(spec.get('severity_overrides'), zones)


def _check_so_ky_hieu(block):
    if block is None:
        raise RulesetError('so_ky_hieu', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict):
        raise RulesetError('so_ky_hieu', 'phải là từ điển')
    fmt = block.get('format')
    if not isinstance(fmt, str):
        raise RulesetError('so_ky_hieu.format', 'phải là chuỗi')
    thieu = [var for var in FORMAT_VARS if var not in fmt]
    if thieu:
        raise RulesetError('so_ky_hieu.format',
                           'thiếu biến %s' % ', '.join(thieu))
    box = block.get('stamp_box_mm')
    if not isinstance(box, dict):
        raise RulesetError('so_ky_hieu.stamp_box_mm', 'phải là từ điển')
    for dim in STAMP_DIMS:
        if dim not in box:
            raise RulesetError('so_ky_hieu.stamp_box_mm.%s' % dim,
                               'thiếu khóa bắt buộc')
        if not _is_number(box[dim]):
            raise RulesetError('so_ky_hieu.stamp_box_mm.%s' % dim,
                               'phải là số (mm)')


def _check_page(block):
    if block is None:
        raise RulesetError('page', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict):
        raise RulesetError('page', 'phải là từ điển')
    if block.get('size') != 'A4':
        raise RulesetError('page.size', "vòng này chỉ hỗ trợ 'A4'")
    margins = block.get('margins_mm')
    if not isinstance(margins, dict):
        raise RulesetError('page.margins_mm', 'phải là từ điển')
    for side in ('top', 'bottom', 'left', 'right'):
        if side not in margins:
            raise RulesetError('page.margins_mm.%s' % side,
                               'thiếu khóa bắt buộc')
        _check_range(margins[side], 'page.margins_mm.%s' % side)


def _check_zones(block):
    if block is None:
        raise RulesetError('zones', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict) or not block:
        raise RulesetError('zones', 'phải là từ điển không rỗng')
    for zone, rules in block.items():
        if zone not in ZONES:
            raise RulesetError('zones.%s' % zone,
                               'tên vùng không hợp lệ, phải thuộc %s'
                               % ', '.join(ZONES))
        if not isinstance(rules, dict):
            raise RulesetError('zones.%s' % zone, 'phải là từ điển')
        for attr, value in rules.items():
            path = 'zones.%s.%s' % (zone, attr)
            kind = ZONE_ATTRS.get(attr)
            if kind is None:
                raise RulesetError(
                    path, 'thuộc tính không hợp lệ, phải thuộc %s'
                    % ', '.join(sorted(ZONE_ATTRS)))
            _check_value(value, kind, path)
    return set(block)


def _check_value(value, kind, path):
    if kind == 'bool':
        if not isinstance(value, bool):
            raise RulesetError(path, 'phải là true hoặc false')
    elif kind == 'str':
        if not isinstance(value, str) or not value.strip():
            raise RulesetError(path, 'phải là chuỗi không rỗng')
    elif kind == 'range':
        _check_range(value, path)
    elif kind == 'align':
        values = value if isinstance(value, list) else [value]
        sai = [v for v in values if v not in ALIGN_VALUES]
        if sai:
            raise RulesetError(path, 'giá trị %s không hợp lệ, phải thuộc %s'
                               % (', '.join(map(str, sai)),
                                  ', '.join(ALIGN_VALUES)))


def _check_range(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise RulesetError(path, 'phải là cặp [min, max]')
    if not all(_is_number(item) for item in value):
        raise RulesetError(path, 'min và max phải là số')
    if value[0] > value[1]:
        raise RulesetError(path, 'min không được lớn hơn max')


def _check_severity_overrides(block, zones):
    if block is None:
        return
    if not isinstance(block, dict):
        raise RulesetError('severity_overrides', 'phải là từ điển')
    for rule_id, severity in block.items():
        path = 'severity_overrides.%s' % rule_id
        if severity not in SEVERITIES:
            raise RulesetError(path, "phải là 'error' hoặc 'warning'")
        zone, _, attr = str(rule_id).partition('.')
        if not attr:
            raise RulesetError(path, "phải có dạng '<vùng>.<thuộc tính>'")
        if zone == 'page':
            if attr not in PAGE_OVERRIDE_ATTRS:
                raise RulesetError(
                    path, "thuộc tính trang không hợp lệ, phải thuộc %s"
                    % ', '.join(PAGE_OVERRIDE_ATTRS))
            continue
        if zone not in zones:
            raise RulesetError(path, "vùng '%s' không có trong zones" % zone)
        if attr not in ZONE_ATTRS:
            raise RulesetError(path,
                               "thuộc tính '%s' không hợp lệ" % attr)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
