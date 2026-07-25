"""Đọc .docx ra cấu trúc trung gian. Mọi tầng sau không đụng XML nữa."""
import io

import docx

from .resolver import StyleResolver
from .types import EffFormat, IntermediateDoc, PageSetup, Para


class UnreadableDocx(Exception):
    """File không phải .docx đọc được: PDF đổi tên, .doc cũ, hoặc hỏng."""


def parse_docx(data):
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:                       # noqa: BLE001 - mọi lỗi đọc
        raise UnreadableDocx(str(exc)) from exc
    resolver = StyleResolver(document)
    return IntermediateDoc(
        pages=_page_setup(document),
        paras=[_para(resolver, paragraph, index)
               for index, paragraph in enumerate(document.paragraphs)],
        standard_hint=None,                        # tầng zones điền
    )


def _page_setup(document):
    section = document.sections[0]

    def mm(length):
        return None if length is None else round(length.mm, 2)

    return PageSetup(
        width_mm=mm(section.page_width),
        height_mm=mm(section.page_height),
        margin_mm={
            'top': mm(section.top_margin),
            'bottom': mm(section.bottom_margin),
            'left': mm(section.left_margin),
            'right': mm(section.right_margin),
        },
    )


def _para(resolver, paragraph, index):
    runs = [run for run in paragraph.runs if run.text.strip()]
    if runs:
        # Định dạng của đoạn lấy theo run DÀI NHẤT: một từ in đậm hay một từ
        # lạc cỡ không được quyết định định dạng của cả đoạn.
        dominant = max(runs, key=lambda run: len(run.text))
        props_list = [resolver.run_props(run, paragraph) for run in runs]
        run_props = resolver.run_props(dominant, paragraph)
        conflict = len({(p['font'], p['size_pt']) for p in props_list}) > 1
    else:
        run_props = resolver.run_props(None, paragraph)
        conflict = False
    para_props = resolver.para_props(paragraph, run_props.get('size_pt'))
    return Para(
        index=index,
        text=paragraph.text,
        style_name=paragraph.style.name if paragraph.style else None,
        fmt=EffFormat(**run_props, **para_props),
        runs_conflict=conflict,
    )
