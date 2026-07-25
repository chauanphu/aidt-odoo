"""Gán mỗi đoạn vào một vùng thể thức.

Quy định là 'theo vùng', không phải toàn cục: tiêu đề Đảng khác trích yếu, khác
nội dung, khác nơi nhận. Nên phải gán vùng trước khi kiểm.

Hai đường: tra tên style (chính xác tuyệt đối, dùng cho file sinh từ mẫu của hệ
thống) và heuristic vị trí + regex (cho file người dùng soạn tay). Vùng chỉ đoán
được sẽ khiến rule engine hạ finding xuống warning, tránh chặn oan.

Đường heuristic chạy hai vòng. Vòng một xét từng đoạn rời, bằng chữ trong đoạn
và vị trí tuyệt đối. Vòng hai (_zone_theo_cau_truc) xét quan hệ VỊ TRÍ giữa các
đoạn, cho những vùng mà một đoạn đứng một mình không đủ để nhận ra: tên cơ quan
ban hành và tên loại văn bản trông y hệt nhau, chỉ khác chỗ đứng so với số ký
hiệu. Vòng hai chỉ nâng cấp đoạn còn ở 'noi_dung' mặc định — style luôn thắng.
"""
import re

# Thứ tự khai theo đúng thứ tự trình bày trên trang, để đọc bảng này là hình
# dung được bố cục văn bản.
ZONES = ('ten_co_quan', 'tieu_de_dang', 'quoc_hieu', 'tieu_ngu', 'so_ky_hieu',
         'dia_danh_ngay', 'ten_loai', 'trich_yeu', 'noi_dung', 'noi_nhan',
         'chu_ky', 'ho_ten_nguoi_ky')

# Tên tiếng Việt của từng vùng, dùng cho thông điệp hiển thị cho văn thư —
# họ không biết (và không cần biết) tên khóa nội bộ 'tieu_de_dang'.
TEN_VUNG = {
    'ten_co_quan': 'tên cơ quan ban hành',
    'tieu_de_dang': 'tiêu đề Đảng',
    'quoc_hieu': 'quốc hiệu',
    'tieu_ngu': 'tiêu ngữ',
    'so_ky_hieu': 'số ký hiệu',
    'dia_danh_ngay': 'địa danh và ngày tháng',
    'ten_loai': 'tên loại văn bản',
    'trich_yeu': 'trích yếu',
    'noi_dung': 'nội dung',
    'noi_nhan': 'nơi nhận',
    'chu_ky': 'chữ ký',
    'ho_ten_nguoi_ky': 'họ tên người ký',
}

STYLE_MAP = {
    'VB_TenCoQuan': 'ten_co_quan',
    'VB_TieuDeDang': 'tieu_de_dang',
    'VB_QuocHieu': 'quoc_hieu',
    'VB_TieuNgu': 'tieu_ngu',
    'VB_SoKyHieu': 'so_ky_hieu',
    'VB_DiaDanhNgay': 'dia_danh_ngay',
    'VB_TenLoai': 'ten_loai',
    'VB_TrichYeu': 'trich_yeu',
    'VB_NoiDung': 'noi_dung',
    'VB_NoiNhan': 'noi_nhan',
    'VB_ChuKy': 'chu_ky',
    'VB_HoTenNguoiKy': 'ho_ten_nguoi_ky',
}

TIEU_DE_DANG = 'ĐẢNG CỘNG SẢN VIỆT NAM'
QUOC_HIEU = 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'

RE_SO_KY_HIEU = re.compile(r'^\s*Số\s*[:：]?\s*\d+\s*[-/]\s*[A-ZĐ]')
RE_NOI_NHAN = re.compile(r'^\s*Nơi\s+nhận\s*[:：]')
# Dòng liệt kê cơ quan nhận: '- Như trên;', '+ Lưu: VT.'. Word tự đổi '-' đầu
# dòng thành dấu đầu dòng '•' hoặc gạch dài khi bật danh sách tự động.
RE_DONG_LIET_KE = re.compile(r'^\s*[-–—+•*]\s*\S')
# 'V/v' là dạng riêng của CÔNG VĂN (văn bản không tên loại). Quyết định,
# nghị quyết, báo cáo, kế hoạch... (văn bản CÓ tên loại) ghi 'Về việc ...'
# ngay dưới tên loại thay vì 'V/v ...'. Cả hai đều là trích yếu.
RE_TRICH_YEU = re.compile(r'^\s*(V/v|Về\s+việc)\s+\S', re.IGNORECASE)

# Tiêu ngữ là chuỗi cố định do luật định, chỉ có dấu nối là thay đổi: Word tự
# đổi '-' thành '–' khi gõ, và một số bản mẫu dùng '—'. Neo cả hai đầu chuỗi
# (^...$) vì đây là một dòng riêng — không neo thì mọi câu văn có nhắc tới cụm
# từ này đều bị nhận nhầm.
RE_TIEU_NGU = re.compile(
    r'^\s*Độc\s*lập\s*[-–—]\s*Tự\s*do\s*[-–—]\s*Hạnh\s*phúc\s*$',
    re.IGNORECASE)

# 'Hà Nội, ngày 25 tháng 7 năm 2026'. Ngày và tháng cho phép để trống vì mẫu in
# sẵn thường chừa chỗ điền tay. Cũng neo cả hai đầu: câu văn có nhắc ngày tháng
# ('... báo cáo, ngày 30 tháng 9 năm 2026 là hạn cuối ...') không phải vùng này.
RE_DIA_DANH_NGAY = re.compile(
    r'^\s*[^,]{1,40},\s*ngày\s+\d{0,2}\s*tháng\s+\d{0,2}\s*năm\s+\d{4}\s*[.]?\s*$',
    re.IGNORECASE)

# Khối chữ ký nằm ở phần cuối văn bản; 0.6 nới rộng để văn bản ngắn vẫn bắt được.
CHU_KY_TU_PHAN = 0.6

# Họ tên người ký là một dòng ngắn. Ngưỡng nới rộng để chứa cả tên dài kèm học
# hàm học vị ('PGS.TS. Nguyễn Thị Minh Khai'), vẫn đủ chặt để loại một câu văn.
HO_TEN_TOI_DA = 50


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
    _zone_theo_cau_truc(doc.paras)
    doc.standard_hint = _standard_hint(doc)
    return doc


def _zone_theo_cau_truc(paras):
    """Vòng hai: các vùng chỉ nhận ra được bằng VỊ TRÍ so với vùng khác.

    Tên cơ quan ban hành và tên loại văn bản trông giống hệt nhau khi đứng một
    mình — cùng in hoa, đậm, căn giữa, cùng là danh từ ngắn. Thứ phân biệt
    chúng là chỗ đứng so với số ký hiệu: tên cơ quan ở TRÊN, tên loại ở DƯỚI
    và ngay trước trích yếu. Họ tên người ký cũng vậy: một dòng căn phải cuối
    văn bản chỉ là họ tên khi có chức vụ đứng trên nó. Vòng một không biết
    được điều đó vì nó xét từng đoạn rời.

    Chỉ nâng cấp đoạn đang ở 'noi_dung' mặc định và do heuristic gán. Style
    vẫn luôn thắng, y như vòng một — đây là nơi dễ vô tình phá vỡ giao ước đó
    nhất, vì vòng này chạy sau và ghi đè được mọi thứ nếu không có guard.

    Không có mốc thì KHÔNG đoán: văn bản không có số ký hiệu thì không suy ra
    tên cơ quan, không có chức vụ thì không suy ra họ tên. Đoán bừa ở đây
    nghĩa là đem thước của một vùng đo một đoạn không thuộc vùng đó — đúng
    thứ mà cả I4 sinh ra để sửa.
    """
    moc = {}
    for index, para in enumerate(paras):
        moc.setdefault(para.zone, index)
    for index, para in enumerate(paras):
        if para.zone != 'noi_dung' or para.zone_confidence != 'heuristic':
            continue
        text = (para.text or '').strip()
        if not text:
            continue
        zone = _zone_vi_tri(para, index, text, paras, moc)
        if zone:
            para.zone = zone


def _zone_vi_tri(para, index, text, paras, moc):
    # I1: các dòng liệt kê cơ quan nhận nằm DƯỚI nhãn 'Nơi nhận:' — chỉ nhãn
    # mới khớp RE_NOI_NHAN, nên trước đây cả danh sách rơi vào vùng nội dung và
    # bị đo bằng thước phần thân (căn đều hai bên, thụt đầu dòng). Nhìn ngược
    # lên đoạn liền trước là đủ, và dây chuyền tự nối: dòng thứ hai thấy dòng
    # thứ nhất đã được nâng cấp vì vòng này chạy theo thứ tự và sửa tại chỗ.
    if RE_DONG_LIET_KE.match(text) and _vung_lien_truoc(paras, index) == 'noi_nhan':
        return 'noi_nhan'
    in_hoa = _la_in_hoa(text)
    so_ky_hieu = moc.get('so_ky_hieu')
    chu_ky = moc.get('chu_ky')
    if in_hoa and so_ky_hieu is not None and index < so_ky_hieu:
        return 'ten_co_quan'
    if (in_hoa and para.fmt.align == 'center'
            and _vung_ke_tiep(paras, index) == 'trich_yeu'):
        return 'ten_loai'
    if (not in_hoa and para.fmt.align == 'right' and len(text) <= HO_TEN_TOI_DA
            and chu_ky is not None and index > chu_ky):
        return 'ho_ten_nguoi_ky'
    return None


def _la_in_hoa(text):
    """Toàn chữ in hoa VÀ có ít nhất một chữ cái.

    Một đoạn toàn số và dấu ('145/2026', '-----') bằng đúng chính nó viết hoa,
    nên chỉ so text == text.upper() là nhận nhầm nó thành chữ in hoa. Vế thứ
    hai đòi phải có ít nhất một chữ cái mới tính.
    """
    return text == text.upper() and text != text.lower()


def _vung_ke_tiep(paras, index):
    """Vùng của đoạn có chữ đứng ngay sau — giá trị của VÒNG MỘT.

    Nhìn tới trước thì vòng hai chưa chạy tới, nên đọc được kết quả vòng một.
    Đó đúng là thứ cần cho tên loại: trích yếu do vòng một nhận ra bằng regex.
    Ngược lại _vung_lien_truoc() đọc được kết quả đã tinh chỉnh của vòng hai —
    hai hàm bất đối xứng có chủ ý, không phải sơ suất.
    """
    for para in paras[index + 1:]:
        if (para.text or '').strip():
            return para.zone
    return None


def _vung_lien_truoc(paras, index):
    for para in reversed(paras[:index]):
        if (para.text or '').strip():
            return para.zone
    return None


def _heuristic_zone(para, total):
    text = (para.text or '').strip()
    if not text:
        return 'noi_dung'
    upper = text.upper()
    # I6: chỉ nhận align=='center' — đúng bằng điều kiện mà bộ luật (seed)
    # đòi hỏi cho cả tieu_de_dang lẫn quoc_hieu. Trước đây heuristic cũng
    # nhận 'right', nên một đoạn căn phải bị TỰ heuristic gán zone rồi TỰ
    # rule engine phạt lỗi align — tự phát hiện rồi tự phạt. Seed là dữ liệu
    # pháp lý, không được tự sửa; thu hẹp điều kiện nhận diện là hướng không
    # đụng seed.
    if para.index <= 2 and para.fmt.align == 'center':
        if TIEU_DE_DANG in upper:
            return 'tieu_de_dang'
        if QUOC_HIEU in upper:
            return 'quoc_hieu'
    if RE_TIEU_NGU.match(text):
        return 'tieu_ngu'
    if RE_DIA_DANH_NGAY.match(text):
        return 'dia_danh_ngay'
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
