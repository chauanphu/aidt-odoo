"""Gán vùng thể thức cho khối OCR bằng chính bộ nhận vùng của aidt_format_engine.

Heuristic của zones.py là regex + vị trí ('Số: 145/KH-UBND', 'Nơi nhận:',
kiểm tra in hoa) — chạy trên text thuần được, không cần biết text đến từ
DOCX hay từ ảnh scan. Ta dựng Para giả từ Block, suy align từ tâm bbox, rồi
gọi detect_zones. Một bộ luật, hai nguồn đầu vào.

Nhánh OCR không có style đặt tên nên luôn dừng ở zone_confidence='heuristic';
nhánh DOCX vẫn đạt 'style' và chính xác 100% khi văn bản soạn từ template.
"""

import dataclasses

from .._compat import fe_types, fe_zones

# Ngưỡng theo tỷ lệ chiều rộng trang, không theo pixel tuyệt đối: ảnh scan
# 150dpi và 300dpi phải cho cùng kết quả.
_EDGE = 0.12          # coi là sát mép khi cách mép dưới 12% chiều rộng
_CENTER_TOL = 0.06    # lệch tâm dưới 6% thì coi là căn giữa
_FULL_WIDTH = 0.80    # phủ trên 80% chiều rộng thì coi là justify


def align_from_bbox(bbox, page_width):
    """left | center | right | justify, suy từ vị trí ngang của khối."""
    if not bbox or not page_width:
        return None
    x0, _, x1, _ = bbox
    left_gap, right_gap = x0 / page_width, (page_width - x1) / page_width
    if (x1 - x0) / page_width >= _FULL_WIDTH:
        return "justify"
    if abs(left_gap - right_gap) <= _CENTER_TOL:
        return "center"
    if right_gap <= _EDGE < left_gap:
        return "right"
    return "left"


def assign_zones(blocks, page_width):
    """Trả danh sách Block MỚI đã gán zone. Không đụng vào danh sách gốc."""
    if not blocks:
        return []
    paras = [
        fe_types.Para(
            index=i,
            text=b.text,
            style_name=None,
            fmt=fe_types.EffFormat(align=align_from_bbox(b.bbox, page_width)),
        )
        for i, b in enumerate(blocks)
    ]
    doc = fe_types.IntermediateDoc(
        pages=fe_types.PageSetup(width_mm=210.0, height_mm=297.0, margin_mm={}),
        paras=paras,
    )
    fe_zones.detect_zones(doc)
    return [
        dataclasses.replace(b, zone=p.zone or "noi_dung", zone_confidence="heuristic")
        for b, p in zip(blocks, doc.paras)
    ]
