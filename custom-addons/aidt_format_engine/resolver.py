"""Tính định dạng 'hiệu lực' của từng đoạn, sau khi flatten chuỗi kế thừa.

Bẫy chết người của DOCX: định dạng kế thừa nhiều tầng. Một đoạn nhìn thấy
Times New Roman 14pt nhưng `run.font.name` trả None vì nó thừa hưởng từ style.
Engine chỉ đọc thuộc tính trực tiếp sẽ báo sai hàng loạt.

Thứ tự ưu tiên:
    run.rPr > character style > paragraph style > chuỗi base_style
            > docDefaults > theme
"""
from lxml import etree

from .units import half_point_to_pt, line_spacing, twip_to_cm

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

# w:jc dùng nhiều tên cho cùng một cách căn; quy về bốn giá trị.
_ALIGN = {
    'left': 'left', 'start': 'left',
    'right': 'right', 'end': 'right',
    'center': 'center',
    'both': 'justify', 'distribute': 'justify',
}

_RUN_KEYS = ('font', 'size_pt', 'bold', 'italic')


class StyleResolver:
    def __init__(self, document):
        self._document = document
        self._run_cache = {}
        self._para_cache = {}
        # Theme phải đọc trước vì _read_rpr tra bảng theme khi gặp w:asciiTheme.
        self._theme = self._read_theme_fonts()
        self._run_defaults, self._para_defaults = self._read_doc_defaults()

    # -- đọc XML thô ------------------------------------------------------

    def _read_theme_fonts(self):
        """{'majorHAnsi': 'Cambria', 'minorHAnsi': 'Calibri'} hoặc {}."""
        for part in self._document.part.package.iter_parts():
            if not part.content_type.endswith('theme+xml'):
                continue
            scheme = etree.fromstring(part.blob).find(
                f'{A}themeElements/{A}fontScheme')
            if scheme is None:
                return {}
            out = {}
            for tag, key in (('majorFont', 'majorHAnsi'),
                             ('minorFont', 'minorHAnsi')):
                latin = scheme.find(f'{A}{tag}/{A}latin')
                if latin is not None and latin.get('typeface'):
                    out[key] = latin.get('typeface')
            return out
        return {}

    def _read_doc_defaults(self):
        run_props = dict.fromkeys(_RUN_KEYS)
        para_props = {}
        element = self._document.styles.element.find(f'{W}docDefaults')
        if element is None:
            return run_props, para_props
        rpr = element.find(f'{W}rPrDefault/{W}rPr')
        if rpr is not None:
            run_props.update(self._read_rpr(rpr))
        ppr = element.find(f'{W}pPrDefault/{W}pPr')
        if ppr is not None:
            para_props.update(self._read_ppr(ppr))
        return run_props, para_props

    def _read_rpr(self, rpr):
        """Chỉ trả các khóa được khai TƯỜNG MINH trong w:rPr này.

        Khóa vắng mặt nghĩa là 'không khai ở tầng này' — để tầng dưới còn chỗ
        điền. Trả None cho một khóa sẽ xóa mất giá trị thừa hưởng.
        """
        out = {}
        fonts = rpr.find(f'{W}rFonts')
        if fonts is not None:
            # ascii chi phối U+0000-U+007F, hAnsi chi phối Latin mở rộng — tức
            # là toàn bộ chữ có dấu tiếng Việt. File Word/LibreOffice thật có
            # thể chỉ khai một trong hai, nên phải thử cả bốn thuộc tính.
            for attr in (f'{W}ascii', f'{W}hAnsi'):
                if fonts.get(attr):
                    out['font'] = fonts.get(attr)
                    break
            else:
                for attr in (f'{W}asciiTheme', f'{W}hAnsiTheme'):
                    theme_key = fonts.get(attr)
                    if theme_key and theme_key in self._theme:
                        out['font'] = self._theme[theme_key]
                        break
        size = rpr.find(f'{W}sz')
        if size is not None and size.get(f'{W}val'):
            out['size_pt'] = half_point_to_pt(float(size.get(f'{W}val')))
        for tag, key in ((f'{W}b', 'bold'), (f'{W}i', 'italic')):
            element = rpr.find(tag)
            if element is not None:
                out[key] = element.get(f'{W}val') not in ('0', 'false', 'off')
        return out

    def _read_ppr(self, ppr):
        out = {}
        jc = ppr.find(f'{W}jc')
        if jc is not None and jc.get(f'{W}val'):
            value = jc.get(f'{W}val')
            out['align'] = _ALIGN.get(value, value)
        indent = ppr.find(f'{W}ind')
        if indent is not None and indent.get(f'{W}firstLine'):
            out['first_line_indent_cm'] = twip_to_cm(
                float(indent.get(f'{W}firstLine')))
        spacing = ppr.find(f'{W}spacing')
        if spacing is not None and spacing.get(f'{W}line'):
            out['_line'] = float(spacing.get(f'{W}line'))
            out['_line_rule'] = spacing.get(f'{W}lineRule')
        return out

    # -- leo chuỗi style --------------------------------------------------

    def _style_run_props(self, style):
        if style is None:
            return {}
        key = style.style_id
        if key not in self._run_cache:
            # base trước, con ghi đè lên
            props = dict(self._style_run_props(style.base_style))
            rpr = style.element.find(f'{W}rPr')
            if rpr is not None:
                props.update(self._read_rpr(rpr))
            self._run_cache[key] = props
        return self._run_cache[key]

    def _style_para_props(self, style):
        if style is None:
            return {}
        key = style.style_id
        if key not in self._para_cache:
            props = dict(self._style_para_props(style.base_style))
            ppr = style.element.find(f'{W}pPr')
            if ppr is not None:
                props.update(self._read_ppr(ppr))
            self._para_cache[key] = props
        return self._para_cache[key]

    # -- API --------------------------------------------------------------

    def run_props(self, run, paragraph):
        """Định dạng chữ hiệu lực của một run. `run` được phép là None."""
        props = dict(self._run_defaults)
        props.update(self._style_run_props(paragraph.style))
        if run is not None:
            props.update(self._style_run_props(run.style))
            rpr = run.element.find(f'{W}rPr')
            if rpr is not None:
                props.update(self._read_rpr(rpr))
        return {key: props.get(key) for key in _RUN_KEYS}

    def para_props(self, paragraph, size_pt):
        """Định dạng đoạn hiệu lực. `size_pt` để quy dãn dòng tuyệt đối."""
        props = dict(self._para_defaults)
        props.update(self._style_para_props(paragraph.style))
        ppr = paragraph._p.find(f'{W}pPr')
        if ppr is not None:
            props.update(self._read_ppr(ppr))
        multiple, fixed = line_spacing(
            props.get('_line'), props.get('_line_rule'), size_pt)
        return {
            'align': props.get('align'),
            'line_spacing': multiple,
            'line_spacing_fixed': fixed,
            'first_line_indent_cm': props.get('first_line_indent_cm'),
        }
