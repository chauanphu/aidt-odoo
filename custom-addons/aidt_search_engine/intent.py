"""Định tuyến ý định truy vấn.

Bóc số hiệu và các filter cứng (thời gian, đơn vị, loại, độ khẩn) ra khỏi
câu hỏi; phần còn lại mới đem đi tìm ngữ nghĩa. 'Các văn bản về hỗ trợ hộ
nghèo năm 2025' phải thành filter date=2025 CỘNG truy vấn 'hỗ trợ hộ nghèo'
— ném cả câu vào embedding thì 'năm 2025' trở thành nhiễu ngữ nghĩa.

Danh mục (loại văn bản, đơn vị, độ khẩn) được truyền vào chứ không hardcode:
thư viện này không được biết gì về selection của Odoo.
"""

import calendar
import datetime as dt
import re

from .text import normalize_ws, strip_accents
from .types import ParsedQuery, QueryFilter

# Số hiệu: '145/KH-UBND', '12/NQ-TW-BCT'. Phần sau '/' phải là chữ IN HOA
# nên '25/7/2026' không lọt.
REFERENCE_RE = re.compile(r"\b(\d+\s*/\s*[A-ZĐ]{2,}(?:[-–][A-ZĐ]+)*)\b")

_YEAR_RE = re.compile(r"\bnăm\s+(\d{4})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bquý\s+(I{1,3}V?|IV)\b(?:\s*(?:năm|/)?\s*(\d{4}))?", re.IGNORECASE)
_MONTH_RE = re.compile(r"\btháng\s+(\d{1,2})\s*[/-]\s*(\d{4})\b", re.IGNORECASE)

_QUARTER_MONTHS = {"I": (1, 3), "II": (4, 6), "III": (7, 9), "IV": (10, 12)}


def _month_range(year, first_month, last_month):
    last_day = calendar.monthrange(year, last_month)[1]
    return dt.date(year, first_month, 1), dt.date(year, last_month, last_day)


# Nhãn danh mục "nuốt nhầm" vào một từ/cụm từ tiếng Việt thông thường khác
# nghĩa — vd. nhãn độ khẩn 'Khẩn' khớp đúng ranh giới từ bên trong 'khẩn cấp'
# (tính từ thường, không phải nhãn "Khẩn"). Ranh giới từ không phân biệt được
# vì cả hai đều có khoảng trắng ngăn cách; đây là danh sách chắp vá (ad-hoc)
# các âm tiết nối tiếp biết trước sẽ đổi nghĩa, không phải quy tắc ngôn ngữ
# tổng quát. Khoá là nhãn đã bỏ dấu + thường hoá.
_FALSE_FRIEND_CONTINUATIONS = {
    "khan": {"cap"},  # 'khẩn cấp' — tính từ, không phải nhãn độ khẩn
}


def _next_token(haystack_folded, pos):
    """Âm tiết liền sau vị trí `pos` (đã bỏ dấu + thường hoá), dùng để phát
    hiện các cụm bị nuốt nhầm kiểu 'khẩn cấp'."""
    m = re.match(r"\s*([a-z0-9]+)", haystack_folded[pos:])
    return m.group(1) if m else ""


def _find_ci(haystack_folded, needle):
    """Vị trí của `needle` trong chuỗi đã bỏ dấu + thường hoá, khớp trên
    ranh giới từ (không khớp vào giữa một từ khác); -1 nếu không có khớp
    hợp lệ.

    Khớp đúng ranh giới từ vẫn có thể sai nghĩa — xem `_FALSE_FRIEND_CONTINUATIONS`.
    """
    needle_folded = strip_accents(needle).lower()
    poison = _FALSE_FRIEND_CONTINUATIONS.get(needle_folded, ())
    pattern = re.compile(r"(?<![a-z0-9])" + re.escape(needle_folded) + r"(?![a-z0-9])")
    for m in pattern.finditer(haystack_folded):
        if _next_token(haystack_folded, m.end()) in poison:
            continue
        return m.start()
    return -1


def _extract_date(raw, spans):
    m = _MONTH_RE.search(raw)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            spans.append(m.span())
            return QueryFilter("date", "between", _month_range(year, month, month),
                               f"Tháng {month}/{year}", m.span())
    m = _QUARTER_RE.search(raw)
    if m:
        roman = m.group(1).upper()
        if roman in _QUARTER_MONTHS:
            own_year = m.group(2)
            quarter_span = m.span()
            year_span = None
            if own_year:
                year = int(own_year)
            else:
                year_m = _YEAR_RE.search(raw)
                year = int(year_m.group(1)) if year_m else None
                year_span = year_m.span() if year_m else None
            if year:
                first, last = _QUARTER_MONTHS[roman]
                # Quý và năm được bóc thành hai span RỜI NHAU thay vì một span
                # bắc cầu — nếu không, mọi nội dung ngữ nghĩa nằm giữa hai mốc
                # này (vd. tên đơn vị, mô tả) sẽ bị xoá theo.
                spans.append(quarter_span)
                if year_span:
                    spans.append(year_span)
                overall_span = (quarter_span[0],
                                 year_span[1] if year_span else quarter_span[1])
                return QueryFilter("date", "between", _month_range(year, first, last),
                                   f"Quý {roman}/{year}", overall_span)
    m = _YEAR_RE.search(raw)
    if m:
        year = int(m.group(1))
        spans.append(m.span())
        return QueryFilter("date", "between",
                           (dt.date(year, 1, 1), dt.date(year, 12, 31)),
                           f"Năm {year}", m.span())
    return None


def _extract_by_catalog(raw, folded, catalog, field, spans):
    """Khớp nhãn dài nhất trước — 'Thượng khẩn' phải thắng 'Khẩn', và
    'Sở Thông tin và Truyền thông' không được dừng ở một tiền tố ngắn hơn."""
    best = None
    for key, label in sorted(catalog or [], key=lambda kv: -len(kv[1])):
        pos = _find_ci(folded, label)
        if pos >= 0:
            best = QueryFilter(field, "=", key, label, (pos, pos + len(label)))
            break
    if best:
        spans.append(best.span)
    return best


def _merge_spans(spans):
    """Gộp các khoảng chồng lấn/liền kề thành các khoảng rời nhau.

    Các extractor có thể sinh ra span lồng nhau hoặc đè lên nhau (vd. span
    ngày tháng và span đơn vị nằm giữa nó). Vòng lặp xoá text ở `parse_query`
    chỉ đúng khi các span rời nhau — gộp trước để không lệch offset và cắt
    nhầm giữa từ, bất kể extractor phía trên có tự đảm bảo rời nhau hay không.
    """
    if not spans:
        return []
    ordered = sorted(tuple(s) for s in spans)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [tuple(s) for s in merged]


def parse_query(raw, doc_types=None, departments=None, urgencies=None):
    raw = raw or ""
    if not raw.strip():
        return ParsedQuery(raw=raw, semantic="", reference=None, filters=[])

    folded = strip_accents(raw).lower()
    spans, filters = [], []

    ref_match = REFERENCE_RE.search(raw)
    reference = None
    if ref_match:
        reference = normalize_ws(ref_match.group(1)).replace(" ", "")
        spans.append(ref_match.span())

    for extracted in (
        _extract_date(raw, spans),
        _extract_by_catalog(raw, folded, doc_types, "doc_type", spans),
        _extract_by_catalog(raw, folded, departments, "department_id", spans),
        _extract_by_catalog(raw, folded, urgencies, "do_khan", spans),
    ):
        if extracted:
            filters.append(extracted)

    remainder = raw
    for start, end in sorted(_merge_spans(spans), key=lambda s: -s[0]):
        remainder = remainder[:start] + " " + remainder[end:]

    return ParsedQuery(raw=raw, semantic=normalize_ws(remainder),
                       reference=reference, filters=filters)
