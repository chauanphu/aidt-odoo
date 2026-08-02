"""Kiểu dữ liệu dùng chung giữa các tầng của đường ống tìm kiếm."""

from dataclasses import dataclass, field


@dataclass
class Block:
    """Một khối nội dung đã trích xuất, chung cho cả nhánh DOCX lẫn OCR."""
    text: str
    zone: str | None = None
    zone_confidence: str | None = None      # 'style' | 'heuristic'
    page: int | None = None
    bbox: tuple | None = None               # (x0, y0, x1, y1)
    confidence: float | None = None         # chỉ nhánh OCR


@dataclass
class DocMeta:
    """Metadata cấp văn bản, dùng dựng contextual header."""
    doc_type_label: str | None = None       # 'Kế hoạch'
    reference: str | None = None            # '145/KH-UBND'
    title: str | None = None                # trích yếu


@dataclass
class Chunk:
    seq: int
    text: str
    embed_text: str
    heading_path: str = ""
    zone: str | None = None
    zone_confidence: str | None = None
    page: int | None = None
    bbox: tuple | None = None
    token_count: int = 0


@dataclass
class QueryFilter:
    """Một điều kiện bóc ra khỏi câu truy vấn.

    `hard=True` (mặc định): điều kiện được AND thẳng vào domain và đoạn text
    sinh ra nó bị cắt khỏi phần ngữ nghĩa. `hard=False`: chỉ là GỢI Ý — hiện
    trên chip "Đã hiểu" để người dùng biết hệ thống đọc được gì, nhưng KHÔNG
    lọc và KHÔNG bị cắt khỏi phần ngữ nghĩa. Xem `intent._doc_type_is_hard`:
    một nhãn loại văn bản khớp giữa câu ('Xin gửi báo cáo tổng kết') là danh
    từ thường, biến nó thành filter cứng sẽ làm rỗng kết quả một cách im lặng.
    """
    field: str                              # 'date' | 'department_id' | 'doc_type' | 'do_khan'
    op: str                                 # 'between' | '='
    value: object
    label: str                              # chữ hiển thị trên chip "Đã hiểu"
    span: tuple                             # (start, end) trong chuỗi raw
    hard: bool = True


@dataclass
class ParsedQuery:
    raw: str
    semantic: str
    reference: str | None = None
    filters: list = field(default_factory=list)


@dataclass
class Candidate:
    chunk_id: int
    document_id: int
    score: float = 0.0
