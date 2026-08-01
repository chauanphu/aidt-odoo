"""Contextual chunk header.

Nối tiêu đề văn bản và đường dẫn mục vào đầu mỗi chunk trước khi embed, để
một đoạn tách rời vẫn mang đủ ngữ cảnh biết nó thuộc văn bản nào, mục nào.
"""

SEP = "\n---\n"


def build_header(meta, heading_path):
    """Dựng phần header hai dòng.

    Dòng 1: '{loại} {số ký hiệu} — {trích yếu}', bỏ qua phần nào thiếu.
    Dòng 2: đường dẫn mục ('Phần II › Mục 3'), bỏ hẳn nếu rỗng.
    """
    left = " ".join(p for p in (meta.doc_type_label, meta.reference) if p)
    if meta.title:
        line1 = f"{left} — {meta.title}" if left else meta.title
    else:
        line1 = left
    return "\n".join(line for line in (line1, heading_path) if line)


def build_embed_text(meta, heading_path, text):
    """Chuỗi thực sự đem đi embed. Lưu nguyên vào cột embed_text để về sau
    tái lập được: khi kết quả sai, câu hỏi đầu tiên luôn là 'nó đã embed gì'."""
    header = build_header(meta, heading_path)
    return f"{header}{SEP}{text}" if header else text
