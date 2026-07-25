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
}

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


def hong():
    """Không unzip được — PDF đổi tên, .doc cũ, hoặc file hỏng."""
    return b'khong phai zip'
