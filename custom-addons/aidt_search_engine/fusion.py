"""Reciprocal Rank Fusion.

Hợp nhất N danh sách đã xếp hạng mà không cần chuẩn hoá thang điểm giữa
chúng — cosine và ts_rank_cd không cùng đơn vị, so trực tiếp là vô nghĩa.
RRF chỉ nhìn THỨ HẠNG nên tránh được hẳn vấn đề đó, và không có tham số
nào phải tinh chỉnh ngoài k.

Nhận số kênh bất kỳ: thêm/bớt kênh (ts_seg bật lên, kênh vector chết) không
phải sửa hàm này.
"""

RRF_K = 60


def reciprocal_rank_fusion(channels, k=RRF_K):
    """channels: list các danh sách id đã xếp hạng (tốt nhất đứng đầu).

    Trả list[(id, score)] giảm dần theo điểm. Điểm bằng nhau phá hoà theo
    repr(id) để kết quả tất định giữa các lần chạy — sort() trong Python ổn
    định (stable) nên nếu không phá hoà tường minh, thứ tự khi bằng điểm chỉ
    tình cờ trùng với thứ tự chèn vào dict, phụ thuộc thứ tự các kênh được
    truyền vào chứ không phải một quy tắc rõ ràng.
    """
    scores = {}
    for ranked in channels or []:
        for rank, item in enumerate(ranked or [], start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], repr(kv[0])))
