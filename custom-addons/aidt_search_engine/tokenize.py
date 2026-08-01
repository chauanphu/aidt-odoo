"""Khe cắm tách từ tiếng Việt.

v1 chạy ở chế độ 'syllable' (trả nguyên văn) — kênh ts_seg tắt. Bật lên
'word' khi bộ eval của dự án con D cho thấy độ chính xác trên truy vấn cụm
nhiều âm tiết thấp hơn ngưỡng. Xem §5.1 và §1.3 của spec.

Thư viện tách từ được import MỀM: không cài thì lùi về syllable chứ không
ném lỗi, vì môi trường mặc định không có chúng.
"""

MODE_SYLLABLE = "syllable"
MODE_WORD = "word"

_CACHED = None                              # None = chưa dò, False = không có


def _load_segmenter():
    """Dò underthesea trước (chính xác hơn), rồi pyvi (nhẹ hơn, không tải model)."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    try:
        from underthesea import word_tokenize

        _CACHED = lambda t: word_tokenize(t, format="text")  # noqa: E731
        return _CACHED
    except ImportError:
        pass
    try:
        from pyvi import ViTokenizer

        _CACHED = ViTokenizer.tokenize
        return _CACHED
    except ImportError:
        _CACHED = False
    return _CACHED


def tokenize(text, mode=MODE_SYLLABLE, segmenter=None):
    """Chuẩn bị chuỗi cho to_tsvector.

    mode='syllable': trả nguyên văn — Postgres tự tách theo khoảng trắng.
    mode='word': nối âm tiết cùng từ bằng '_' để mỗi từ thành một token.

    `segmenter` cho phép test tiêm hàm giả; truyền False để mô phỏng môi
    trường không có thư viện nào.
    """
    if not text or mode != MODE_WORD:
        return text or ""
    seg = _load_segmenter() if segmenter is None else segmenter
    if not seg:
        return text
    return seg(text)
