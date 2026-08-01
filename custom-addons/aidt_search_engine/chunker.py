"""Chunking: cấu trúc trước, kích thước sau.

Ba bậc ranh giới:
  cứng  — zone đổi, hoặc gặp Phần/Chương/Mục/Điều. Luôn cắt.
  mềm   — '1.', 'a)'. Chỉ cắt khi đã chạm ngưỡng, nếu không một danh sách
          20 gạch đầu dòng sẽ thành 20 chunk tí hon làm loãng chỉ mục.
  cuối  — ranh giới câu, dùng khi một khối đơn lẻ dài quá ngưỡng.
"""

import re

from .header import build_embed_text
from .text import estimate_tokens
from .types import Chunk

TARGET_TOKENS = 400

# Bốn vùng thể thức này luôn đứng riêng một chunk: đây là thứ văn thư tra
# cứu trực tiếp ('ai ký?', 'gửi cho ai?'), nhấn chìm chúng vào một chunk
# nội dung 400 token là ném đi tín hiệu mạnh nhất.
STANDALONE_ZONES = ("so_ky_hieu", "trich_yeu", "noi_nhan", "chu_ky")

# \A neo đầu chuỗi — 'Căn cứ Điều 7' giữa câu không được tính là tiêu đề.
_HEADINGS = (
    (1, re.compile(r"\A\s*(PHẦN|Phần)\s+([IVXLC]+)\b")),
    (2, re.compile(r"\A\s*(CHƯƠNG|Chương)\s+([IVXLC]+)\b")),
    (3, re.compile(r"\A\s*(MỤC|Mục)\s+(\d+)\b")),
    (4, re.compile(r"\A\s*(Điều)\s+(\d+)\b")),
)

_SOFT = re.compile(r"\A\s*(?:\d+\.|[a-zđ]\))\s")

_SENT_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n+")


def detect_heading(text):
    """(bậc, nhãn) nếu đoạn mở đầu một mục cấu trúc, ngược lại None."""
    for level, pattern in _HEADINGS:
        m = pattern.match(text or "")
        if m:
            return level, f"{m.group(1)} {m.group(2)}"
    return None


def is_soft_boundary(text):
    """Đoạn mở đầu bằng '1.' hoặc 'a)' — chỗ ưu tiên cắt khi đã đủ dài."""
    return bool(_SOFT.match(text or ""))


def split_long_text(text, target_tokens, overlap_sentences=1):
    """Cắt một khối dài theo ranh giới câu, có chồng lấn."""
    if not text or not text.strip():
        return []
    if estimate_tokens(text) <= target_tokens:
        return [text]
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]
    if len(sentences) <= 1:
        return [text]                       # một câu dài hơn ngưỡng: để nguyên
    pieces, cur = [], []
    for s in sentences:
        cur.append(s)
        if estimate_tokens(" ".join(cur)) >= target_tokens:
            pieces.append(" ".join(cur))
            cur = cur[-overlap_sentences:] if overlap_sentences else []
    tail = " ".join(cur)
    if tail and (not pieces or tail != pieces[-1]):
        pieces.append(tail)
    return pieces


def chunk_blocks(blocks, meta, target_tokens=TARGET_TOKENS):
    """list[Block] -> list[Chunk], gán heading_path và embed_text."""
    out, stack, buf = [], {}, []

    def heading_path():
        return " › ".join(stack[k] for k in sorted(stack))

    def flush():
        nonlocal buf
        if not buf:
            return
        joined = "\n".join(b.text for b in buf).strip()
        if not joined:
            buf = []
            return
        first, path = buf[0], heading_path()
        for piece in split_long_text(joined, target_tokens):
            out.append(Chunk(
                seq=len(out),
                text=piece,
                embed_text=build_embed_text(meta, path, piece),
                heading_path=path,
                zone=first.zone,
                zone_confidence=first.zone_confidence,
                page=first.page,
                bbox=first.bbox,
                token_count=estimate_tokens(piece),
            ))
        buf = []

    for b in blocks:
        if not (b.text or "").strip():
            continue
        heading = detect_heading(b.text)
        zone_changed = bool(buf) and buf[-1].zone != b.zone
        standalone = b.zone in STANDALONE_ZONES or (bool(buf) and buf[0].zone in STANDALONE_ZONES)
        if heading or zone_changed or standalone:
            flush()
        if heading:
            level, label = heading
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = label
        buf.append(b)
        if estimate_tokens("\n".join(x.text for x in buf)) >= target_tokens:
            tail = buf[-1] if len(buf) > 1 and not is_soft_boundary(buf[-1].text) else None
            flush()
            if tail is not None:
                buf = [tail]                # chồng lấn một đoạn

    flush()
    return out
