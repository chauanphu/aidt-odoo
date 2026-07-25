"""Đổi đơn vị của OOXML sang đơn vị người đọc được.

OOXML dùng ba đơn vị khó nhớ:
  - twip (twentieth of a point): 1pt = 20 twip, 1cm = 567 twip
  - half-point cho cỡ chữ: giá trị 28 nghĩa là 14pt
  - w:spacing/@w:line: khi lineRule="auto" thì 240 là một dòng đơn
"""

TWIP_PER_PT = 20.0
TWIP_PER_CM = 567.0
TWIP_PER_MM = 56.7
LINE_AUTO_SINGLE = 240.0

# Word tính "một dòng đơn" bằng chiều cao dòng của phông, không bằng cỡ chữ —
# với Times New Roman xấp xỉ 1.15 lần cỡ chữ. Hệ số này chỉ dùng để quy dãn dòng
# tuyệt đối (lineRule exact/atLeast) về "số lần dòng" cho dễ đọc; rule nên bám
# vào cờ `fixed` chứ không bám vào con số quy đổi này.
SINGLE_LINE_FACTOR = 1.15


def twip_to_mm(value):
    return None if value is None else value / TWIP_PER_MM


def twip_to_cm(value):
    return None if value is None else value / TWIP_PER_CM


def half_point_to_pt(value):
    return None if value is None else value / 2.0


def line_spacing(line, line_rule, size_pt):
    """Quy mọi cách khai dãn dòng về 'số lần dòng'.

    Trả (multiple, fixed):
      multiple -- số lần dòng, None nếu không khai được
      fixed    -- True khi khai bằng chiều cao tuyệt đối (exact/atLeast)
    """
    if line is None:
        return None, False
    if line_rule in (None, 'auto'):
        return line / LINE_AUTO_SINGLE, False
    if not size_pt:
        return None, True
    return (line / TWIP_PER_PT) / (size_pt * SINGLE_LINE_FACTOR), True
