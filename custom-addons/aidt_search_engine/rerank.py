"""Khe cắm reranker — chưa bật ở v1.

Cross-encoder chỉ tỏa sáng khi tập ứng viên lớn và nhiễu. Ở quy mô vài trăm
văn bản, RRF cộng contextual header đã gần chạm trần, trong khi model tốn
thêm ~1.2GB VRAM và ~300ms mỗi truy vấn.

Điều kiện bật: bộ eval của dự án con D cho thấy nDCG@10 của RRF thuần thấp
hơn ngưỡng. Khi đó chỉ thay thân hàm — chỗ gọi không đổi.
"""


def rerank(query, candidates):
    """v1: giữ nguyên thứ tự RRF."""
    return candidates
