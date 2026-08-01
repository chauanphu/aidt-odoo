"""Tiện ích xử lý chuỗi dùng chung, không phụ thuộc Odoo."""

import re
import unicodedata

# Ước lượng thô: tiếng Việt khoảng 3 ký tự một token với tokenizer XLM-R.
# Chỉ dùng để quyết định chỗ cắt chunk (ngưỡng 400), cách xa giới hạn 8192
# của model nên sai số không gây tràn — không đáng gọi tokenizer thật.
CHARS_PER_TOKEN = 3

_WS = re.compile(r"\s+")


def strip_accents(s):
    """Bỏ dấu tiếng Việt.

    Phải khớp hành vi unaccent() của Postgres, vì kênh tìm kiếm không dấu
    so khớp chuỗi sinh ở Python với cột tsvector sinh ở SQL. NFD không phân
    rã 'đ'/'Đ' nên hai ký tự này xử lý riêng.
    """
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def estimate_tokens(s):
    """Số token ước lượng, luôn ≥ 1 để không có chunk 'không tốn gì'."""
    return max(1, len(s or "") // CHARS_PER_TOKEN)


def normalize_ws(s):
    """Gộp mọi chuỗi khoảng trắng thành một dấu cách, cắt hai đầu."""
    return _WS.sub(" ", s or "").strip()
