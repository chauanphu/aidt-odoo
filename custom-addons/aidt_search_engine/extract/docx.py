"""Nhánh DOCX: dùng thẳng parser + zone detector của aidt_format_engine.

Đây là lý do không cần `unstructured`: aidt_format_engine đã tách đúng 12
vùng thể thức văn bản Đảng / NĐ-30, chính xác hơn hẳn một parser tổng quát.
Văn bản soạn từ template hệ thống còn có style đặt tên nên đạt
zone_confidence='style' — chính xác 100%.
"""

from .._compat import fe_parser, fe_zones
from ..types import Block

UnreadableDocx = fe_parser.UnreadableDocx


def extract_docx(blob):
    """bytes DOCX -> list[Block]. Ném UnreadableDocx nếu tệp hỏng."""
    doc = fe_parser.parse_docx(blob)
    fe_zones.detect_zones(doc)
    return [
        Block(
            text=p.text,
            zone=p.zone or "noi_dung",
            zone_confidence=p.zone_confidence,
        )
        for p in doc.paras
        if (p.text or "").strip()
    ]
