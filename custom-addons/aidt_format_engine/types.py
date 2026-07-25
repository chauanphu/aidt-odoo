from dataclasses import dataclass, field


@dataclass
class EffFormat:
    """Định dạng hiệu lực của một đoạn, đã flatten hết chuỗi kế thừa."""
    font: str | None = None
    size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    align: str | None = None                    # left|center|right|justify
    line_spacing: float | None = None           # đã quy về số lần dòng
    line_spacing_fixed: bool = False            # True nếu lineRule exact/atLeast
    first_line_indent_cm: float | None = None


@dataclass
class Para:
    index: int
    text: str
    style_name: str | None
    fmt: EffFormat
    runs_conflict: bool = False
    zone: str | None = None                     # tầng zones điền
    zone_confidence: str | None = None          # 'style' | 'heuristic'


@dataclass
class PageSetup:
    width_mm: float | None = None
    height_mm: float | None = None
    margin_mm: dict = field(default_factory=dict)   # top/bottom/left/right


@dataclass
class IntermediateDoc:
    pages: PageSetup
    paras: list
    standard_hint: str | None = None            # 'dang' | 'hanh_chinh'
