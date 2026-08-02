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
import unicodedata

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
#
# Danh sách này KHÔNG BAO GIỜ đầy đủ được và không được coi là hàng phòng thủ
# chính: nhãn LOẠI VĂN BẢN ('báo cáo', 'kế hoạch', 'thông báo', 'quyết định')
# là danh từ/động từ tiếng Việt tần suất cao, muốn chặn hết bằng blacklist thì
# phải liệt kê cả ngữ pháp tiếng Việt. Hàng phòng thủ thật cho nhóm doc_type là
# `_doc_type_is_hard()` phía dưới — chỉ AND vào domain khi nhãn đứng ĐẦU câu và
# câu không còn nội dung ngữ nghĩa nào khác.
_FALSE_FRIEND_CONTINUATIONS = {
    "khan": {"cap"},        # 'khẩn cấp' — tính từ, không phải nhãn độ khẩn
    "bao cao": {"vien"},    # 'báo cáo viên' — chức danh
    "ke hoach": {"hoa"},    # 'kế hoạch hoá' — 'kế hoạch hoá gia đình'
    "ket luan": {"rang"},   # 'kết luận rằng' — động từ
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
    'Sở Thông tin và Truyền thông' không được dừng ở một tiền tố ngắn hơn.

    `spans=None`: không ghi span vào danh sách xoá — bên gọi tự quyết định
    (nhánh doc_type còn phải xét cứng/mềm trước, xem `_doc_type_is_hard`).
    """
    best = None
    for key, label in sorted(catalog or [], key=lambda kv: -len(kv[1])):
        pos = _find_ci(folded, label)
        if pos >= 0:
            best = QueryFilter(field, "=", key, label, (pos, pos + len(label)))
            break
    if best and spans is not None:
        spans.append(best.span)
    return best


# Hư từ / từ nối tiếng Việt (đã bỏ dấu + thường hoá). CHỈ dùng để quyết định
# nhãn loại văn bản là filter cứng hay gợi ý mềm — không bao giờ bị xoá khỏi
# chuỗi ngữ nghĩa. 'Báo cáo quý II của Sở Tài chính năm 2026' còn đúng một chữ
# 'của' sau khi bóc hết mốc: đó vẫn là ý định duyệt theo loại, không phải một
# câu hỏi nội dung.
_FUNCTION_WORDS = frozenset("""
    cua ve cho cac nhung va voi trong tai theo tu den o la co mot nay do
    van ban tai lieu toi xem tim kiem giup danh sach moi hay
""".split())


def _is_only_function_words(text):
    tokens = re.findall(r"[a-z0-9]+", strip_accents(text).lower())
    return all(t in _FUNCTION_WORDS for t in tokens)


def _doc_type_is_hard(raw, span, other_spans):
    """Một nhãn loại văn bản chỉ được thành FILTER CỨNG khi câu hỏi thực chất
    chỉ là chính nhãn đó (cộng các mốc đã bóc thành filter khác).

    Lý do: khớp chuỗi con được nâng thẳng lên thành điều kiện AND là một phép
    suy diễn rất mạnh từ một bằng chứng rất yếu. 'Xin gửi báo cáo tổng kết' là
    câu tiếng Việt bình thường, không phải biểu thức lọc — biến 'báo cáo' thành
    `doc_type='bao_cao'` sẽ trả về RỖNG cho nội dung chắc chắn có trong kho, mà
    người dùng không hề thấy vì sao. Ngược lại 'kế hoạch' (gõ đúng một cụm, hết
    câu) hay 'công văn quý III năm 2026' rõ ràng là ý định duyệt theo loại.

    Điều kiện: (1) trước nhãn không có gì ngoài hư từ ('văn bản kế hoạch' vẫn
    tính là ở đầu), (2) sau khi xoá nhãn này và mọi span đã bóc khác thì phần
    còn lại cũng chỉ toàn hư từ. Không thoả -> giữ làm gợi ý mềm
    (`hard=False`): vẫn hiện chip "Đã hiểu" nhưng KHÔNG lọc, và cụm đó ở lại
    trong phần ngữ nghĩa để đem đi tìm.
    """
    if not _is_only_function_words(raw[:span[0]]):
        return False
    remainder = raw
    for start, end in sorted(_merge_spans(list(other_spans) + [span]),
                             key=lambda s: -s[0]):
        remainder = remainder[:start] + " " + remainder[end:]
    return _is_only_function_words(remainder)


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
    # Chuẩn hoá NFC TRƯỚC MỌI THỨ. Toàn bộ tệp này tính offset trên chuỗi đã
    # bỏ dấu (`folded`) rồi CẮT trên `raw` — chỉ đúng nếu `strip_accents` giữ
    # nguyên độ dài. Với NFC đúng là vậy (mỗi ký tự có dấu là một code point,
    # bỏ dấu thành một code point khác). Với NFD thì KHÔNG: dấu là code point
    # rời hạng Mn, bỏ đi làm chuỗi NGẮN lại đúng một ký tự mỗi dấu, mọi span
    # sau đó lệch dần và phần ngữ nghĩa bị cắt giữa từ — rồi vẫn im lặng đi
    # tiếp vào embedding và websearch_to_tsquery. Tiếng Việt dạng NFD đến rất
    # thường xuyên: tên tệp macOS, một số bộ gõ, và copy-paste.
    raw = unicodedata.normalize("NFC", raw or "")
    if not raw.strip():
        return ParsedQuery(raw=raw, semantic="", reference=None, filters=[])

    folded = strip_accents(raw).lower()
    spans, filters = [], []

    ref_match = REFERENCE_RE.search(raw)
    reference = None
    if ref_match:
        reference = normalize_ws(ref_match.group(1)).replace(" ", "")
        spans.append(ref_match.span())

    # doc_type bóc riêng, KHÔNG ghi span ngay: còn phải biết toàn bộ span khác
    # mới quyết định được nó là filter cứng hay chỉ là gợi ý mềm.
    doc_type_filter = _extract_by_catalog(raw, folded, doc_types, "doc_type", None)

    for extracted in (
        _extract_date(raw, spans),
        _extract_by_catalog(raw, folded, departments, "department_id", spans),
        _extract_by_catalog(raw, folded, urgencies, "do_khan", spans),
    ):
        if extracted:
            filters.append(extracted)

    if doc_type_filter:
        doc_type_filter.hard = _doc_type_is_hard(raw, doc_type_filter.span, spans)
        if doc_type_filter.hard:
            spans.append(doc_type_filter.span)
        filters.append(doc_type_filter)
    # Thứ tự chip theo thứ tự xuất hiện trong câu hỏi, không theo thứ tự
    # extractor chạy — người dùng đọc chip đối chiếu với câu mình vừa gõ.
    filters.sort(key=lambda f: f.span)

    remainder = raw
    for start, end in sorted(_merge_spans(spans), key=lambda s: -s[0]):
        remainder = remainder[:start] + " " + remainder[end:]

    return ParsedQuery(raw=raw, semantic=normalize_ws(remainder),
                       reference=reference, filters=filters)
