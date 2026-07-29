"""Sinh file .docx cho test engine. Mỗi hàm trả bytes.

Cố ý sinh bằng code chứ không commit binary: rule sẽ đổi, và một diff YAML/Python
đọc được còn một diff .docx thì không.
"""
import io

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

TIEU_DE_DANG = 'ĐẢNG CỘNG SẢN VIỆT NAM'
QUOC_HIEU = 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'

# Bảy style thể thức mà mẫu của hệ thống gắn sẵn, để zone detector tra bảng
# thay vì đoán. font/size khai ở STYLE, không khai ở run — đúng như file thật.
STYLE_NAMES = {
    'VB_TieuDeDang': {'font': 'Times New Roman', 'size': 15, 'bold': True,
                      'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_QuocHieu': {'font': 'Times New Roman', 'size': 13, 'bold': True,
                    'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_SoKyHieu': {'font': 'Times New Roman', 'size': 14, 'bold': False,
                    'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_TrichYeu': {'font': 'Times New Roman', 'size': 14, 'bold': True,
                    'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_NoiDung': {'font': 'Times New Roman', 'size': 14, 'bold': False,
                   'align': WD_ALIGN_PARAGRAPH.JUSTIFY},
    'VB_NoiNhan': {'font': 'Times New Roman', 'size': 12, 'bold': False,
                   'align': WD_ALIGN_PARAGRAPH.LEFT},
    'VB_ChuKy': {'font': 'Times New Roman', 'size': 14, 'bold': True,
                 'align': WD_ALIGN_PARAGRAPH.RIGHT},
    # Năm vùng bổ sung (I4). Chỉ KHAI BÁO ở đây; các fixture cũ không dùng tới
    # nên không đoạn nào của chúng đổi vùng — style khai mà không đoạn nào mang
    # thì không ảnh hưởng gì tới văn bản.
    'VB_TieuNgu': {'font': 'Times New Roman', 'size': 14, 'bold': True,
                   'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_TenCoQuan': {'font': 'Times New Roman', 'size': 13, 'bold': True,
                     'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_DiaDanhNgay': {'font': 'Times New Roman', 'size': 14, 'bold': False,
                       'italic': True, 'align': WD_ALIGN_PARAGRAPH.RIGHT},
    'VB_TenLoai': {'font': 'Times New Roman', 'size': 14, 'bold': True,
                   'align': WD_ALIGN_PARAGRAPH.CENTER},
    'VB_HoTenNguoiKy': {'font': 'Times New Roman', 'size': 14, 'bold': True,
                        'align': WD_ALIGN_PARAGRAPH.RIGHT},
}

TIEU_NGU = 'Độc lập - Tự do - Hạnh phúc'

# NĐ 30/2020 quy định cỡ chữ khác 66-QĐ/TW ở ba vùng. Fixture chuan_nd30() phải
# đạt theo ND-30 thật, nếu dùng cỡ của chuẩn Đảng thì nó không còn là "chuẩn".
ND30_SIZES = {'VB_SoKyHieu': 13, 'VB_NoiNhan': 11, 'VB_QuocHieu': 13}


def _nd30_styles():
    styles = {name: dict(spec) for name, spec in STYLE_NAMES.items()}
    for name, size in ND30_SIZES.items():
        styles[name]['size'] = size
    return styles


def _blob(document):
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _new_document(margins_mm=(22, 22, 32, 17), styles=STYLE_NAMES):
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    top, bottom, left, right = margins_mm
    section.top_margin, section.bottom_margin = Mm(top), Mm(bottom)
    section.left_margin, section.right_margin = Mm(left), Mm(right)
    for name, spec in (styles or {}).items():
        style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = spec['font']
        style.font.size = Pt(spec['size'])
        style.font.bold = spec['bold']
        # Chỉ đặt italic khi spec khai — đặt False tường minh cho mọi style sẽ
        # đổi giá trị hiệu lực từ None (kế thừa) sang False ở các fixture cũ.
        if 'italic' in spec:
            style.font.italic = spec['italic']
        style.paragraph_format.alignment = spec['align']
        if name == 'VB_NoiDung':
            style.paragraph_format.line_spacing = 1.5
            style.paragraph_format.first_line_indent = Mm(12.7)
    return document


def _body(document, header_style, header_text, with_noi_nhan=True,
          so_text='Số: 123-CV/TU'):
    """Bộ khung bảy vùng. Chỉ đặt style, KHÔNG đặt định dạng ở run — để
    resolver buộc phải leo chuỗi kế thừa mới ra được giá trị hiệu lực."""
    document.add_paragraph(header_text, style=header_style)
    document.add_paragraph(so_text, style='VB_SoKyHieu')
    document.add_paragraph('V/v triển khai nhiệm vụ quý III', style='VB_TrichYeu')
    document.add_paragraph(
        'Thực hiện chương trình công tác năm 2026, Ban Thường vụ yêu cầu các '
        'đơn vị nghiêm túc triển khai các nội dung sau đây.', style='VB_NoiDung')
    if with_noi_nhan:
        document.add_paragraph('Nơi nhận:', style='VB_NoiNhan')
        document.add_paragraph('- Các ban, phòng trực thuộc;', style='VB_NoiNhan')
    document.add_paragraph('T/M BAN THƯỜNG VỤ', style='VB_ChuKy')
    document.add_paragraph('BÍ THƯ', style='VB_ChuKy')
    return document


def chuan_66():
    """Đạt sạch theo 66-QĐ/TW, mọi vùng dùng style VB_*."""
    return _blob(_body(_new_document(), 'VB_TieuDeDang', TIEU_DE_DANG))


def chuan_nd30():
    """Đạt sạch theo NĐ 30/2020: khác tiêu đề, khác cỡ chữ, khác thứ tự số."""
    return _blob(_body(_new_document(styles=_nd30_styles()),
                       'VB_QuocHieu', QUOC_HIEU,
                       so_text='Số: 123/CV-VPTU'))


def sai_font():
    """Bẫy quan trọng nhất: font Arial khai ở STYLE, run không khai gì.

    Đọc naive `run.font.name` sẽ ra None và engine sẽ bỏ qua lỗi. Resolver phải
    leo chuỗi kế thừa và ra 'Arial'.
    """
    styles = {name: dict(spec) for name, spec in STYLE_NAMES.items()}
    styles['VB_NoiDung']['font'] = 'Arial'
    return _blob(_body(_new_document(styles=styles), 'VB_TieuDeDang', TIEU_DE_DANG))


def sai_dan_dong_exact():
    """Dãn dòng khai bằng chiều cao tuyệt đối (lineRule="exact")."""
    document = _new_document()
    document.styles['VB_NoiDung'].paragraph_format.line_spacing = Pt(12)
    return _blob(_body(document, 'VB_TieuDeDang', TIEU_DE_DANG))


def sai_le_trang():
    """Lề trên 10mm, ngoài khoảng 20-25mm."""
    return _blob(_body(_new_document(margins_mm=(10, 22, 32, 17)),
                       'VB_TieuDeDang', TIEU_DE_DANG))


def thieu_noi_nhan():
    """Thiếu hẳn vùng nơi nhận — vùng required."""
    return _blob(_body(_new_document(), 'VB_TieuDeDang', TIEU_DE_DANG,
                       with_noi_nhan=False))


def run_lech_nhau():
    """Một đoạn nội dung có hai cỡ chữ — lỗi dán từ nguồn khác vào.

    Mẩu lạc cỡ cố ý NGẮN hơn hẳn phần thân: nó mô hình hóa một mẩu dán vào
    giữa câu. Nếu nó dài hơn phần thân thì quy tắc "run dài nhất thắng" của
    parser sẽ chọn đúng nó, và fixture mất sạch ý nghĩa.
    """
    document = _body(_new_document(), 'VB_TieuDeDang', TIEU_DE_DANG)
    paragraph = document.add_paragraph(style='VB_NoiDung')
    paragraph.add_run(
        'Các đơn vị nghiêm túc triển khai những nội dung nêu trên, báo cáo '
        'kết quả về Văn phòng trước ngày 30 tháng 9 năm 2026. ')
    lech = paragraph.add_run('cỡ 11')
    lech.font.size = Pt(11)
    return _blob(document)


def in_dam_giua_cau():
    """Đoạn có một cụm in đậm giữa câu — HỢP LỆ, không được đánh dấu lệch.

    runs_conflict so (font, size_pt) chứ không so bold, vì nhấn mạnh giữa câu
    là cách viết bình thường của văn bản hành chính. Fixture này là cái bắt
    được nếu ai đó đưa bold vào tiêu chí so sánh.
    """
    document = _body(_new_document(), 'VB_TieuDeDang', TIEU_DE_DANG)
    paragraph = document.add_paragraph(style='VB_NoiDung')
    paragraph.add_run('Các đơn vị hoàn thành trước ')
    nhan_manh = paragraph.add_run('ngày 30 tháng 9')
    nhan_manh.font.bold = True
    paragraph.add_run(' và báo cáo về Văn phòng.')
    return _blob(document)


def sai_nhieu_thuoc_tinh():
    """Vi phạm cùng lúc bold, uppercase, align và thụt đầu dòng.

    Bốn quy định thật trong bộ luật đã seed. Trước fixture này, không quy định
    nào trong số đó có test nào chạm tới — vô hiệu hóa cả bốn bộ phát hiện mà
    suite vẫn xanh.
    """
    styles = {name: dict(spec) for name, spec in STYLE_NAMES.items()}
    styles['VB_TieuDeDang']['bold'] = False          # bộ luật đòi bold
    styles['VB_TrichYeu']['align'] = WD_ALIGN_PARAGRAPH.LEFT  # bộ luật đòi center
    document = _new_document(styles=styles)
    document.styles['VB_NoiDung'].paragraph_format.first_line_indent = Mm(30)
    # tiêu đề không viết hoa -> vi phạm uppercase
    return _blob(_body(document, 'VB_TieuDeDang', 'Đảng Cộng sản Việt Nam'))


def khong_phai_a4():
    """Khổ giấy Letter thay vì A4."""
    document = _new_document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(216), Mm(279)
    return _blob(_body(document, 'VB_TieuDeDang', TIEU_DE_DANG))


def _set_para(paragraph, style_name, text):
    paragraph.text = text
    paragraph.style = style_name
    return paragraph


def vb_that_dau_trang_bang():
    """Khối đầu trang dựng bằng bảng 2 cột, như văn bản hành chính thật.

    Văn bản thật hầu như luôn dựng khối đầu trang (tên cơ quan/tiêu đề Đảng,
    số ký hiệu/địa danh-ngày tháng) bằng một bảng 2 cột ẩn viền, KHÔNG phải
    bằng paragraph rời như mọi fixture khác của bộ này. `document.paragraphs`
    (thuộc tính python-docx) bỏ qua hẳn các đoạn nằm trong ô bảng — đây là
    fixture tái hiện đúng lỗ hổng C1 của parser.

    Cột trái: tên cơ quan ban hành (Số ký hiệu ở hàng dưới). Cột phải: tiêu
    đề Đảng (địa danh/ngày tháng ở hàng dưới). Phần thân — trích yếu, nội
    dung, nơi nhận, chữ ký — vẫn là paragraph thường, NGOÀI bảng.
    """
    document = _new_document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).paragraphs[0].text = 'BAN THƯỜNG VỤ TỈNH ỦY'
    _set_para(table.cell(0, 1).paragraphs[0], 'VB_TieuDeDang', TIEU_DE_DANG)
    _set_para(table.cell(1, 0).paragraphs[0], 'VB_SoKyHieu', 'Số: 123-CV/TU')
    table.cell(1, 1).paragraphs[0].text = 'Hà Nội, ngày 25 tháng 7 năm 2026'
    document.add_paragraph('V/v triển khai nhiệm vụ quý III', style='VB_TrichYeu')
    document.add_paragraph(
        'Thực hiện chương trình công tác năm 2026, Ban Thường vụ yêu cầu các '
        'đơn vị nghiêm túc triển khai các nội dung sau đây.', style='VB_NoiDung')
    document.add_paragraph('Nơi nhận:', style='VB_NoiNhan')
    document.add_paragraph('- Các ban, phòng trực thuộc;', style='VB_NoiNhan')
    document.add_paragraph('T/M BAN THƯỜNG VỤ', style='VB_ChuKy')
    document.add_paragraph('BÍ THƯ', style='VB_ChuKy')
    return _blob(document)


def vb_that_co_ten_loai():
    """Văn bản NĐ 30/2020 có TÊN LOẠI (QUYẾT ĐỊNH) và trích yếu ghi
    'Về việc ...' — không phải 'V/v ...' như công văn.

    'V/v' là dạng riêng của CÔNG VĂN (văn bản không tên loại). Quyết định,
    nghị quyết, báo cáo, kế hoạch... ghi 'Về việc ...' ngay dưới tên loại.
    Cố tình KHÔNG dùng style VB_* (giống khong_co_style()) để buộc đường
    heuristic của zones.py phải tự nhận diện — đây là fixture tái hiện lỗ
    hổng C2 (RE_TRICH_YEU trước đây chỉ khớp 'V/v').
    """
    document = _new_document(styles=None)
    normal = document.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(14)

    def add(text, align=None, bold=False):
        paragraph = document.add_paragraph(text)
        if align is not None:
            paragraph.paragraph_format.alignment = align
        if bold:
            for run in paragraph.runs:
                run.font.bold = True
        return paragraph

    add(QUOC_HIEU, WD_ALIGN_PARAGRAPH.CENTER)
    add('Số: 45/QĐ-UBND', WD_ALIGN_PARAGRAPH.CENTER)
    add('QUYẾT ĐỊNH', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    add('Về việc ban hành quy chế làm việc của cơ quan',
        WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    add('Nội dung quyết định được trình bày dưới đây.',
        WD_ALIGN_PARAGRAPH.JUSTIFY)
    add('Nơi nhận:')
    add('- Như trên;')
    add('CHỦ TỊCH', WD_ALIGN_PARAGRAPH.RIGHT)
    return _blob(document)


def chuan_66_co_doan_trong():
    """Y hệt chuan_66() nhưng thêm một đoạn trống style Normal ở cuối.

    Word luôn để lại ít nhất một đoạn trống dạng này khi người dùng lưu
    file; fixture sinh bằng code trước đây không mô phỏng chuyện đó. Đoạn
    trống này rơi vào zone 'noi_dung' với zone_confidence='heuristic' (style
    Normal không có trong STYLE_MAP) — tái hiện lỗ hổng C3: hạ mức đã tính
    theo cả VÙNG thay vì theo từng ĐOẠN.
    """
    document = _body(_new_document(), 'VB_TieuDeDang', TIEU_DE_DANG)
    document.add_paragraph('', style='Normal')
    return _blob(document)


def sai_font_co_doan_trong():
    """sai_font() cộng thêm một đoạn trống style Normal ở cuối.

    Đây là phép thử trực tiếp cho C3: đoạn nội dung thật (style VB_NoiDung,
    zone_confidence='style') mang lỗi font Arial phải vẫn là 'error', dù
    cùng vùng 'noi_dung' có thêm một đoạn trống heuristic. Bản lỗi cũ hạ
    CẢ VÙNG xuống warning một khi vùng đó có bất kỳ đoạn heuristic nào, nên
    lỗi Arial thật cũng bị xóa dấu — sai lặng lẽ vì suite vẫn xanh.
    """
    styles = {name: dict(spec) for name, spec in STYLE_NAMES.items()}
    styles['VB_NoiDung']['font'] = 'Arial'
    document = _body(_new_document(styles=styles), 'VB_TieuDeDang', TIEU_DE_DANG)
    document.add_paragraph('', style='Normal')
    return _blob(document)


def khong_co_style():
    """Chỉ dùng style Normal — buộc zone detector chạy heuristic."""
    document = _new_document(styles=None)
    normal = document.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(14)

    def add(text, align=None):
        paragraph = document.add_paragraph(text)
        if align is not None:
            paragraph.paragraph_format.alignment = align
        return paragraph

    add(TIEU_DE_DANG, WD_ALIGN_PARAGRAPH.CENTER)
    add('Số: 456-BC/TU', WD_ALIGN_PARAGRAPH.CENTER)
    add('V/v báo cáo kết quả thực hiện', WD_ALIGN_PARAGRAPH.CENTER)
    add('Nội dung báo cáo được trình bày dưới đây.', WD_ALIGN_PARAGRAPH.JUSTIFY)
    add('Nơi nhận:')
    add('BÍ THƯ', WD_ALIGN_PARAGRAPH.RIGHT)
    return _blob(document)


_DAY_DU = (
    ('ten_co_quan', 'VB_TenCoQuan', 'ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG'),
    ('quoc_hieu', 'VB_QuocHieu', QUOC_HIEU),
    ('tieu_ngu', 'VB_TieuNgu', TIEU_NGU),
    ('so_ky_hieu', 'VB_SoKyHieu', 'Số: 145/QĐ-UBND'),
    ('dia_danh_ngay', 'VB_DiaDanhNgay', 'Bình Dương, ngày 25 tháng 7 năm 2026'),
    ('ten_loai', 'VB_TenLoai', 'QUYẾT ĐỊNH'),
    ('trich_yeu', 'VB_TrichYeu', 'Về việc ban hành quy chế làm việc'),
    ('noi_dung', 'VB_NoiDung',
     'Ban hành kèm theo Quyết định này Quy chế làm việc của cơ quan, các đơn '
     'vị trực thuộc có trách nhiệm thi hành kể từ ngày ký.'),
    ('noi_nhan', 'VB_NoiNhan', 'Nơi nhận:'),
    ('noi_nhan', 'VB_NoiNhan', '- Như trên;'),
    ('chu_ky', 'VB_ChuKy', 'CHỦ TỊCH'),
    ('ho_ten_nguoi_ky', 'VB_HoTenNguoiKy', 'Nguyễn Văn A'),
)

# Vùng mong đợi cho hai fixture đầy đủ dưới đây, dùng chung cho cả đường style
# lẫn đường heuristic — hai đường phải cho CÙNG một kết quả, đó là điều kiện để
# heuristic có ích trên văn bản soạn tay.
VUNG_DAY_DU = [zone for zone, _, _ in _DAY_DU]


def vb_day_du_theo_style():
    """Văn bản hành chính đủ 12 vùng thể thức, mọi đoạn gắn style VB_*.

    Mười hai vùng của NĐ 30/2020 theo đúng thứ tự trình bày. Bảy fixture cũ chỉ
    phủ bảy vùng; năm vùng còn lại (tiêu ngữ, tên cơ quan ban hành, địa danh và
    ngày tháng, tên loại văn bản, họ tên người ký) trước đây rơi hết vào
    'noi_dung' và bị đo bằng thước của phần thân.
    """
    document = _new_document(styles=_nd30_styles())
    for _, style_name, text in _DAY_DU:
        document.add_paragraph(text, style=style_name)
    return _blob(document)


def vb_day_du_khong_style():
    """Y hệt vb_day_du_theo_style() nhưng KHÔNG style nào — buộc chạy heuristic.

    Đây mới là hình dạng của văn bản soạn tay ngoài mẫu, thứ mà engine sẽ gặp
    trên thực tế. Định dạng đặt thẳng vào đoạn, đúng cách người dùng bấm nút
    trên thanh công cụ Word.
    """
    document = _new_document(styles=None)
    normal = document.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(14)
    for _, style_name, text in _DAY_DU:
        spec = _nd30_styles()[style_name]
        paragraph = document.add_paragraph(text)
        paragraph.paragraph_format.alignment = spec['align']
        for run in paragraph.runs:
            run.font.size = Pt(spec['size'])
            run.font.bold = spec['bold']
            if 'italic' in spec:
                run.font.italic = spec['italic']
    return _blob(document)


def hong():
    """Không unzip được — PDF đổi tên, .doc cũ, hoặc file hỏng."""
    return b'khong phai zip'
