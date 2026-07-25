"""Gán mỗi đoạn vào một vùng thể thức.

Quy định là 'theo vùng', không phải toàn cục: tiêu đề Đảng khác trích yếu, khác
nội dung, khác nơi nhận. Nên phải gán vùng trước khi kiểm.

Hai đường: tra tên style (chính xác tuyệt đối, dùng cho file sinh từ mẫu của hệ
thống) và heuristic vị trí + regex (cho file người dùng soạn tay). Vùng chỉ đoán
được sẽ khiến rule engine hạ finding xuống warning, tránh chặn oan.
"""
import re

ZONES = ('tieu_de_dang', 'quoc_hieu', 'so_ky_hieu', 'trich_yeu', 'noi_dung',
         'noi_nhan', 'chu_ky')

STYLE_MAP = {
    'VB_TieuDeDang': 'tieu_de_dang',
    'VB_QuocHieu': 'quoc_hieu',
    'VB_SoKyHieu': 'so_ky_hieu',
    'VB_TrichYeu': 'trich_yeu',
    'VB_NoiDung': 'noi_dung',
    'VB_NoiNhan': 'noi_nhan',
    'VB_ChuKy': 'chu_ky',
}

TIEU_DE_DANG = 'ĐẢNG CỘNG SẢN VIỆT NAM'
QUOC_HIEU = 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'

RE_SO_KY_HIEU = re.compile(r'^\s*Số\s*[:：]?\s*\d+\s*[-/]\s*[A-ZĐ]')
RE_NOI_NHAN = re.compile(r'^\s*Nơi\s+nhận\s*[:：]')
RE_TRICH_YEU = re.compile(r'^\s*V/v\s+\S', re.IGNORECASE)

# Khối chữ ký nằm ở phần cuối văn bản; 0.6 nới rộng để văn bản ngắn vẫn bắt được.
CHU_KY_TU_PHAN = 0.6


def detect_zones(doc):
    """Điền zone + zone_confidence cho từng đoạn, và standard_hint cho văn bản.

    Sửa `doc` tại chỗ rồi trả về chính nó.
    """
    total = len(doc.paras)
    for para in doc.paras:
        # Một vòng, không hai: bản hai vòng (style rồi heuristic có guard
        # `if para.zone: continue`) gợi ý rằng thứ tự quan trọng, trong khi
        # vòng style ghi đè vô điều kiện nên đảo thứ tự cho đúng cùng kết quả.
        # Cấu trúc đánh lừa người đọc, và sẽ thành bug thật nếu ai đó thêm
        # guard vào vòng style.
        zone = STYLE_MAP.get(para.style_name)
        if zone:
            para.zone, para.zone_confidence = zone, 'style'
        else:
            para.zone, para.zone_confidence = _heuristic_zone(para, total), 'heuristic'
    doc.standard_hint = _standard_hint(doc)
    return doc


def _heuristic_zone(para, total):
    text = (para.text or '').strip()
    if not text:
        return 'noi_dung'
    upper = text.upper()
    if para.index <= 2 and para.fmt.align in ('center', 'right'):
        if TIEU_DE_DANG in upper:
            return 'tieu_de_dang'
        if QUOC_HIEU in upper:
            return 'quoc_hieu'
    if RE_SO_KY_HIEU.match(text):
        return 'so_ky_hieu'
    if RE_NOI_NHAN.match(text):
        return 'noi_nhan'
    if RE_TRICH_YEU.match(text):
        return 'trich_yeu'
    if (total and para.index >= total * CHU_KY_TU_PHAN
            and para.fmt.align == 'right' and text == upper):
        return 'chu_ky'
    return 'noi_dung'


def _standard_hint(doc):
    zones = {para.zone for para in doc.paras}
    if 'tieu_de_dang' in zones:
        return 'dang'
    if 'quoc_hieu' in zones:
        return 'hanh_chinh'
    return None
