# Kế hoạch triển khai — `aidt_format` (Đợt 1/3, engine thể thức)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng module `aidt_format` kiểm tra thể thức một file `.docx` theo bộ luật
cấu hình được, trả về danh sách phát hiện — chưa gắn vào nghiệp vụ nào.

**Architecture:** Bốn tầng trong một package Python thuần không import `odoo`
(Parser → Resolver → Zone detector → Rule engine), bọc bởi hai model Odoo mỏng:
`aidt.format.ruleset` giữ bộ luật dạng YAML có version, và `aidt.format.checker`
là cửa vào trả `list[dict]` mà **không ghi bản ghi nào**.

**Tech Stack:** Odoo 19, Python 3.12, `python-docx`, `PyYAML` (đã có), `pytest`
(host, đã có), `lxml` (đi kèm `python-docx`).

Spec: `docs/superpowers/specs/2026-07-25-van-ban-di-design.md` — mục 3, 6, 9, 11.

## Global Constraints

- Hai package ngang hàng: `custom-addons/aidt_format_engine/` (thư viện Python thuần) và `custom-addons/aidt_format/` (module Odoo). `addons_path` đã gồm `custom-addons`.
- `license: 'LGPL-3'`, `version: '1.0'` trong `__manifest__.py` của `aidt_format`, khớp `aidt_org`/`aidt_dms`. `aidt_format_engine` **không có** `__manifest__.py` — nó là thư viện nằm trên addons path, không phải module cài được, nên Odoo import được qua `odoo.addons.aidt_format_engine` mà không xuất hiện trong danh sách cài đặt.
- **`aidt_format_engine/` tuyệt đối không được `import odoo`**, kể cả gián tiếp. Đây là điều kiện để test engine chạy trên host. Kiểm bằng: `grep -rn "import odoo\|from odoo" custom-addons/aidt_format_engine/` phải rỗng.
- **`aidt_format_engine/__init__.py` phải rỗng.** Nó là thứ khiến pytest trên host nạp được package mà không kéo Odoo vào.
- **`aidt_format_engine/tests/` tuyệt đối không có `__init__.py`** — nhưng lý do đã đổi sau khi tách package. Trước đây là để pytest khỏi leo tới `aidt_format/__init__.py`; nay `aidt_format_engine` đã ngang hàng nên việc leo dừng ở `__init__.py` rỗng của nó. Lý do hiện tại: khi `tests/` thành package, pytest không còn chèn chính thư mục `tests/` vào `sys.path`, làm `import fixtures` (import trần) gãy với `ModuleNotFoundError: No module named 'fixtures'`. Đã kiểm bằng thực nghiệm.
- **`aidt_format/tests/` thì PHẢI CÓ `__init__.py`** — Odoo cần nó để nạp test. Hai thư mục cùng tên `tests/`, quy tắc ngược nhau.
- Trong `aidt_format_engine/tests/` dùng import **tuyệt đối**: `from aidt_format_engine.units import …`. Trong `aidt_format_engine/` các module dùng import **tương đối**: `from .units import …` — nhờ vậy chạy đúng dưới cả hai gốc. Code Odoo gọi engine qua `from odoo.addons.aidt_format_engine.X import …`.
- Mọi chuỗi hiển thị cho người dùng viết tiếng Việt và bọc `_()` ở tầng model. Trong `aidt_format_engine/` không có `_()` (không có odoo) — chuỗi tiếng Việt trần.
- Lệnh test engine (host): `PYTHONPATH=custom-addons python3 -m pytest custom-addons/aidt_format_engine/tests -v`
- Lệnh test model (container): `docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -i aidt_format --http-port=8098 --test-enable --stop-after-init --log-level=test`
- DB test là `aidt_test` (dùng một lần). **Không chạy test trên `aidt_demo`.**
- **Cờ cổng là bắt buộc** trong mọi lệnh `odoo-bin`: container dev đang chạy Odoo trên 8069, thiếu cờ này thì lệnh chết ngay với `Port 8069 is in use`. `--no-http` KHÔNG cứu được — Odoo vẫn kiểm cổng trước. Dùng `--http-port=8098`; nếu báo `Port 8098 is in use` (một lệnh nền khác đang giữ) thì đổi sang `8099`.
- Host là Python 3.12 externally-managed (PEP 668), nên `pip install` cần `--break-system-packages`.
- Commit prefix theo repo: `[ADD] aidt_format: …`, `[IMP] aidt_format: …`.
- `severity` mặc định của mọi finding là `'error'`; `severity_overrides` trong ruleset là cách duy nhất hạ xuống `'warning'`. Ngoại lệ: `doc.runs_conflict` và `file.wrong_standard` mặc định `'warning'`.
- Finding trong vùng có `zone_confidence == 'heuristic'` tự hạ từ `error` xuống `warning`, sau khi đã áp `severity_overrides`.

---

### Task 1: Scaffold module, đơn vị đo, hợp đồng dữ liệu

**Files:**
- Create: `custom-addons/aidt_format/__init__.py`
- Create: `custom-addons/aidt_format/__manifest__.py`
- Create: `custom-addons/aidt_format_engine/__init__.py`
- Create: `custom-addons/aidt_format_engine/units.py`
- Create: `custom-addons/aidt_format_engine/types.py`
- Create: `custom-addons/aidt_format_engine/findings.py`
- Modify: `requirements.txt` (thêm `python-docx`)
- Test: `custom-addons/aidt_format_engine/tests/test_units.py`

**Interfaces:**
- Consumes: không có.
- Produces:
  - `engine.units.twip_to_mm(v) -> float | None`, `twip_to_cm(v) -> float | None`, `half_point_to_pt(v) -> float | None`
  - `engine.units.line_spacing(line, line_rule, size_pt) -> tuple[float | None, bool]`
  - `engine.types.EffFormat`, `Para`, `PageSetup`, `IntermediateDoc` (dataclass, **không** frozen — tầng zones ghi vào `Para.zone`)
  - `engine.findings.Finding` (dataclass frozen, có `.as_dict()`), hằng `ERROR = 'error'`, `WARNING = 'warning'`

- [ ] **Step 1: Thêm `python-docx` vào `requirements.txt`**

Chèn ngay sau dòng `python-dateutil==2.8.2 ; python_version >= '3.11'`
(`requirements.txt:72`), trước khối `python-magic`:

```
python-docx==1.1.2
```

Cài trên host để chạy được test engine:

```bash
pip install --user --break-system-packages 'python-docx==1.1.2'
```

- [ ] **Step 2: Viết `__manifest__.py` và `__init__.py`**

`custom-addons/aidt_format/__manifest__.py`:

```python
{
    'name': 'AIDT Thể thức văn bản',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Engine kiểm tra thể thức văn bản theo bộ luật cấu hình được (D-03/D-07/D-09)',
    'depends': ['base'],
    'data': [],
    'license': 'LGPL-3',
}
```

`custom-addons/aidt_format/__init__.py`: để **rỗng** ở task này. Chưa có `models/`
nên `from . import models` sẽ lỗi; Task 8 mới thêm dòng đó.

`custom-addons/aidt_format_engine/__init__.py`: để rỗng.

- [ ] **Step 3: Viết `engine/units.py`**

```python
"""Đổi đơn vị của OOXML sang đơn vị người đọc được.

OOXML dùng ba đơn vị khó nhớ:
  - twip (twentieth of a point): 1pt = 20 twip, 1cm = 567 twip
  - half-point cho cỡ chữ: giá trị 28 nghĩa là 14pt
  - w:spacing/@w:line: khi lineRule="auto" thì 240 là một dòng đơn
"""

TWIP_PER_PT = 20.0
TWIP_PER_CM = 567.0
TWIP_PER_MM = 56.7
LINE_AUTO_SINGLE = 240.0

# Word tính "một dòng đơn" bằng chiều cao dòng của phông, không bằng cỡ chữ —
# với Times New Roman xấp xỉ 1.15 lần cỡ chữ. Hệ số này chỉ dùng để quy dãn dòng
# tuyệt đối (lineRule exact/atLeast) về "số lần dòng" cho dễ đọc; rule nên bám
# vào cờ `fixed` chứ không bám vào con số quy đổi này.
SINGLE_LINE_FACTOR = 1.15


def twip_to_mm(value):
    return None if value is None else value / TWIP_PER_MM


def twip_to_cm(value):
    return None if value is None else value / TWIP_PER_CM


def half_point_to_pt(value):
    return None if value is None else value / 2.0


def line_spacing(line, line_rule, size_pt):
    """Quy mọi cách khai dãn dòng về 'số lần dòng'.

    Trả (multiple, fixed):
      multiple -- số lần dòng, None nếu không khai được
      fixed    -- True khi khai bằng chiều cao tuyệt đối (exact/atLeast)
    """
    if line is None:
        return None, False
    if line_rule in (None, 'auto'):
        return line / LINE_AUTO_SINGLE, False
    if not size_pt:
        return None, True
    return (line / TWIP_PER_PT) / (size_pt * SINGLE_LINE_FACTOR), True
```

- [ ] **Step 4: Viết `engine/types.py`**

```python
from dataclasses import dataclass, field


@dataclass
class EffFormat:
    """Định dạng hiệu lực của một đoạn, đã flatten hết chuỗi kế thừa."""
    font: str | None = None
    size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    align: str | None = None                    # left|center|right|justify
    line_spacing: float | None = None           # đã quy về số lần dòng
    line_spacing_fixed: bool = False            # True nếu lineRule exact/atLeast
    first_line_indent_cm: float | None = None


@dataclass
class Para:
    index: int
    text: str
    style_name: str | None
    fmt: EffFormat
    runs_conflict: bool = False
    zone: str | None = None                     # tầng zones điền
    zone_confidence: str | None = None          # 'style' | 'heuristic'


@dataclass
class PageSetup:
    width_mm: float | None = None
    height_mm: float | None = None
    margin_mm: dict = field(default_factory=dict)   # top/bottom/left/right


@dataclass
class IntermediateDoc:
    pages: PageSetup
    paras: list
    standard_hint: str | None = None            # 'dang' | 'hanh_chinh'
```

- [ ] **Step 5: Viết `engine/findings.py`**

```python
from dataclasses import asdict, dataclass

ERROR = 'error'
WARNING = 'warning'


@dataclass(frozen=True)
class Finding:
    rule_id: str            # 'noi_dung.line_spacing'
    severity: str           # ERROR | WARNING
    zone: str
    location: str           # 'Đoạn 14'
    expected: str
    actual: str
    suggestion: str = ''

    def as_dict(self):
        return asdict(self)
```

- [ ] **Step 6: Viết test cho `units.py` (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_units.py` — **không tạo `__init__.py`
trong thư mục này**:

```python
import unittest

from aidt_format_engine.units import half_point_to_pt, line_spacing, twip_to_cm, twip_to_mm


class TestUnits(unittest.TestCase):
    def test_twip_to_mm(self):
        self.assertAlmostEqual(twip_to_mm(567), 10.0, places=2)
        self.assertIsNone(twip_to_mm(None))

    def test_twip_to_cm(self):
        self.assertAlmostEqual(twip_to_cm(567), 1.0, places=3)
        self.assertAlmostEqual(twip_to_cm(720), 1.27, places=2)

    def test_half_point_to_pt(self):
        self.assertEqual(half_point_to_pt(28), 14.0)
        self.assertEqual(half_point_to_pt(30), 15.0)

    def test_line_spacing_auto(self):
        self.assertEqual(line_spacing(240, 'auto', 14), (1.0, False))
        self.assertEqual(line_spacing(360, 'auto', 14), (1.5, False))

    def test_line_spacing_khong_khai(self):
        self.assertEqual(line_spacing(None, None, 14), (None, False))

    def test_line_spacing_thieu_lineRule_coi_nhu_auto(self):
        # w:line có mà w:lineRule không có: Word hiểu là auto
        self.assertEqual(line_spacing(240, None, 14), (1.0, False))

    def test_line_spacing_exact_danh_dau_fixed(self):
        multiple, fixed = line_spacing(240, 'exact', 14)
        self.assertTrue(fixed)
        # 240 twip = 12pt; một dòng đơn của cỡ 14pt xấp xỉ 16.1pt
        self.assertAlmostEqual(multiple, 12 / (14 * 1.15), places=4)

    def test_line_spacing_exact_khong_biet_co_chu(self):
        self.assertEqual(line_spacing(240, 'exact', None), (None, True))
```

- [ ] **Step 7: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest custom-addons/aidt_format_engine/tests -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine'`.

Để thấy được vòng đỏ này, làm Step 6 **trước** Step 3: viết test, chạy thấy đỏ,
rồi mới viết `units.py`. Thứ tự các step trong task này xếp theo file cho dễ đọc,
không phải theo thứ tự thực hiện.

- [ ] **Step 8: Chạy lại, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest custom-addons/aidt_format_engine/tests -v
```

Expected: toàn bộ test trong file pass.

- [ ] **Step 9: Xác nhận module nạp được trong Odoo**

```bash
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -i aidt_format --stop-after-init --log-level=warn
```

Expected: không có traceback. DB `aidt_test` được tạo mới ở lần chạy này.

- [ ] **Step 10: Commit**

```bash
git add custom-addons/aidt_format requirements.txt
git commit -m "[ADD] aidt_format: scaffold, đơn vị đo OOXML, hợp đồng dữ liệu

engine/ là package Python thuần, không import odoo, để test chạy trên host
không cần Odoo. engine/tests/ cố ý không có __init__.py: pytest leo lên tìm
__init__.py để đặt tên module, có nó thì aidt_format/__init__.py bị nạp và
kéo theo import odoo."
```

---

### Task 2: Fixture sinh `.docx` bằng code

**Files:**
- Create: `custom-addons/aidt_format_engine/tests/fixtures.py`
- Test: `custom-addons/aidt_format_engine/tests/test_fixtures.py`

**Interfaces:**
- Consumes: không có (chỉ dùng `python-docx`).
- Produces: chín hàm không tham số, mỗi hàm trả `bytes` của một file `.docx`:
  `chuan_66()`, `chuan_nd30()`, `sai_font()`, `sai_dan_dong_exact()`,
  `sai_le_trang()`, `thieu_noi_nhan()`, `run_lech_nhau()`, `khong_co_style()`,
  `hong()`. Cùng hằng `STYLE_NAMES: dict[str, dict]` mô tả bảy style `VB_*`.

Fixture là **hàm sinh file**, không phải binary commit vào git — để review được
bằng diff và sửa được khi rule đổi.

- [ ] **Step 1: Viết `fixtures.py`**

```python
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
```

- [ ] **Step 2: Viết test cho fixtures (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_fixtures.py`:

```python
import io
import unittest

import zipfile

import docx
from docx.opc.exceptions import PackageNotFoundError

import fixtures

DOCX_HOP_LE = (
    'chuan_66', 'chuan_nd30', 'sai_font', 'sai_dan_dong_exact', 'sai_le_trang',
    'thieu_noi_nhan', 'run_lech_nhau', 'khong_co_style',
)


class TestFixtures(unittest.TestCase):
    def test_moi_fixture_mo_duoc_bang_python_docx(self):
        for name in DOCX_HOP_LE:
            with self.subTest(fixture=name):
                blob = getattr(fixtures, name)()
                document = docx.Document(io.BytesIO(blob))
                self.assertGreater(len(document.paragraphs), 0)

    def test_hong_khong_mo_duoc(self):
        # python-docx 1.1.2 chỉ dịch lỗi sang PackageNotFoundError khi nhận
        # ĐƯỜNG DẪN; với stream (BytesIO — cách engine luôn dùng) nó để
        # zipfile.BadZipFile lọt thẳng ra. Chấp nhận cả hai để test không vỡ
        # khi đổi phiên bản thư viện. Hợp đồng thật là parse_docx phải ném
        # UnreadableDocx, và Task 4 kiểm điều đó.
        with self.assertRaises((PackageNotFoundError, zipfile.BadZipFile)):
            docx.Document(io.BytesIO(fixtures.hong()))

    def test_chuan_nd30_dung_co_chu_cua_ND30(self):
        """chuan_nd30 phải đạt theo ND-30 thật, không dùng cỡ của chuẩn Đảng."""
        document = docx.Document(io.BytesIO(fixtures.chuan_nd30()))
        self.assertEqual(document.styles['VB_SoKyHieu'].font.size.pt, 13)
        self.assertEqual(document.styles['VB_NoiNhan'].font.size.pt, 11)

    def test_sai_font_khai_o_style_khong_khai_o_run(self):
        """Chốt cái bẫy: run.font.name là None, còn style mới giữ 'Arial'."""
        document = docx.Document(io.BytesIO(fixtures.sai_font()))
        noi_dung = [p for p in document.paragraphs if p.style.name == 'VB_NoiDung']
        self.assertTrue(noi_dung)
        for run in noi_dung[0].runs:
            self.assertIsNone(run.font.name)
        self.assertEqual(document.styles['VB_NoiDung'].font.name, 'Arial')

    def test_thieu_noi_nhan_thi_thieu_that(self):
        document = docx.Document(io.BytesIO(fixtures.thieu_noi_nhan()))
        self.assertFalse(
            [p for p in document.paragraphs if p.style.name == 'VB_NoiNhan'])

    def test_khong_co_style_khong_dung_VB(self):
        document = docx.Document(io.BytesIO(fixtures.khong_co_style()))
        for paragraph in document.paragraphs:
            self.assertFalse(paragraph.style.name.startswith('VB_'))
```

- [ ] **Step 3: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_fixtures.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'fixtures'`.

- [ ] **Step 4: Chạy lại sau khi có `fixtures.py`, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_fixtures.py -v
```

Expected: toàn bộ test trong file pass (7 test).

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/tests
git commit -m "[ADD] aidt_format: fixture sinh .docx bằng code

Sinh bằng python-docx thay vì commit binary: rule sẽ đổi, và diff Python
đọc được còn diff .docx thì không. test_fixtures chốt sẵn cái bẫy của
sai_font(): run.font.name là None, chỉ style mới giữ 'Arial'."
```

---

### Task 3: Resolver — chuỗi kế thừa định dạng

**Files:**
- Create: `custom-addons/aidt_format_engine/resolver.py`
- Test: `custom-addons/aidt_format_engine/tests/test_resolver.py`

**Interfaces:**
- Consumes: `engine.units.half_point_to_pt`, `twip_to_cm`, `line_spacing`.
- Produces:
  - `engine.resolver.StyleResolver(document)` với hai phương thức:
    - `run_props(run, paragraph) -> dict` — khóa `font`, `size_pt`, `bold`, `italic` (giá trị có thể `None`); `run` được phép là `None` (đoạn trống).
    - `para_props(paragraph, size_pt) -> dict` — khóa `align`, `line_spacing`, `line_spacing_fixed`, `first_line_indent_cm`.

Đây là tầng dễ sai nhất của cả module. Thứ tự ưu tiên phải đúng:

```
run.rPr > character style > paragraph style > chuỗi base_style > docDefaults > theme
```

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_resolver.py`:

```python
import io
import unittest

import docx

import fixtures
from aidt_format_engine.resolver import StyleResolver


def _load(blob):
    document = docx.Document(io.BytesIO(blob))
    return document, StyleResolver(document)


def _first(document, style_name):
    for paragraph in document.paragraphs:
        if paragraph.style.name == style_name:
            return paragraph
    raise AssertionError('không có đoạn nào dùng style %s' % style_name)


class TestRunProps(unittest.TestCase):
    def test_font_thua_huong_tu_style(self):
        """Bẫy chính: run không khai font, phải ra 'Arial' của style."""
        document, resolver = _load(fixtures.sai_font())
        paragraph = _first(document, 'VB_NoiDung')
        run = paragraph.runs[0]
        self.assertIsNone(run.font.name, 'fixture sai: run không được khai font')
        props = resolver.run_props(run, paragraph)
        self.assertEqual(props['font'], 'Arial')

    def test_co_chu_thua_huong_tu_style(self):
        document, resolver = _load(fixtures.chuan_66())
        paragraph = _first(document, 'VB_TieuDeDang')
        props = resolver.run_props(paragraph.runs[0], paragraph)
        self.assertEqual(props['size_pt'], 15.0)
        self.assertEqual(props['font'], 'Times New Roman')

    def test_bold_thua_huong_tu_style(self):
        document, resolver = _load(fixtures.chuan_66())
        dam = resolver.run_props(*_run_and_para(document, 'VB_TrichYeu'))
        thuong = resolver.run_props(*_run_and_para(document, 'VB_NoiDung'))
        self.assertTrue(dam['bold'])
        self.assertFalse(thuong['bold'])

    def test_run_khai_truc_tiep_thang_style(self):
        document, resolver = _load(fixtures.run_lech_nhau())
        paragraph = document.paragraphs[-1]
        self.assertEqual(len(paragraph.runs), 2)
        thua_huong = resolver.run_props(paragraph.runs[0], paragraph)
        khai_truc_tiep = resolver.run_props(paragraph.runs[1], paragraph)
        self.assertEqual(thua_huong['size_pt'], 14.0)
        self.assertEqual(khai_truc_tiep['size_pt'], 11.0)

    def test_run_none_van_ra_dinh_dang_cua_style(self):
        document, resolver = _load(fixtures.chuan_66())
        paragraph = _first(document, 'VB_NoiDung')
        props = resolver.run_props(None, paragraph)
        self.assertEqual(props['size_pt'], 14.0)

    def test_khong_co_style_thi_lay_tu_Normal(self):
        document, resolver = _load(fixtures.khong_co_style())
        paragraph = document.paragraphs[0]
        props = resolver.run_props(paragraph.runs[0], paragraph)
        self.assertEqual(props['font'], 'Times New Roman')
        self.assertEqual(props['size_pt'], 14.0)


class TestParaProps(unittest.TestCase):
    def test_can_le_thua_huong_tu_style(self):
        document, resolver = _load(fixtures.chuan_66())
        self.assertEqual(
            resolver.para_props(_first(document, 'VB_NoiDung'), 14.0)['align'],
            'justify')
        self.assertEqual(
            resolver.para_props(_first(document, 'VB_TieuDeDang'), 15.0)['align'],
            'center')
        self.assertEqual(
            resolver.para_props(_first(document, 'VB_ChuKy'), 14.0)['align'],
            'right')

    def test_dan_dong_auto(self):
        document, resolver = _load(fixtures.chuan_66())
        props = resolver.para_props(_first(document, 'VB_NoiDung'), 14.0)
        self.assertAlmostEqual(props['line_spacing'], 1.5, places=3)
        self.assertFalse(props['line_spacing_fixed'])

    def test_dan_dong_exact_danh_dau_fixed(self):
        document, resolver = _load(fixtures.sai_dan_dong_exact())
        props = resolver.para_props(_first(document, 'VB_NoiDung'), 14.0)
        self.assertTrue(props['line_spacing_fixed'])

    def test_thut_dau_dong_thua_huong_tu_style(self):
        document, resolver = _load(fixtures.chuan_66())
        props = resolver.para_props(_first(document, 'VB_NoiDung'), 14.0)
        self.assertAlmostEqual(props['first_line_indent_cm'], 1.27, places=2)


def _run_and_para(document, style_name):
    paragraph = _first(document, style_name)
    return paragraph.runs[0], paragraph


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_resolver.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine.resolver'`.

- [ ] **Step 3: Viết `engine/resolver.py`**

```python
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
            ascii_font = fonts.get(f'{W}ascii')
            theme_key = fonts.get(f'{W}asciiTheme')
            if ascii_font:
                out['font'] = ascii_font
            elif theme_key and theme_key in self._theme:
                out['font'] = self._theme[theme_key]
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_resolver.py -v
```

Expected: toàn bộ test trong file pass. Nếu `test_font_thua_huong_tu_style` fail thì **dừng lại** —
đó là bẫy trung tâm của cả module, không được bỏ qua bằng cách sửa test.

> **Cập nhật sau review Task 3.** Bộ test ở Step 1 để lọt bốn kiểu sai:
> reviewer dựng resolver lỗi mô phỏng từng kiểu và cả bốn đều không làm test đỏ.
> Bản đã merge bổ sung bốn test (`test_font_giai_duoc_qua_theme_khi_khong_tang_nao_khai`,
> `test_character_style_thang_paragraph_style`, `test_leo_chuoi_base_style_va_cache_khong_lan`,
> `test_font_khai_o_hAnsi_ma_khong_co_ascii`) và hai assert vào
> `test_run_khai_truc_tiep_thang_style`. `_read_rpr` cũng đọc thêm `w:hAnsi`/`w:hAnsiTheme`
> — `ascii` chi phối U+0000–U+007F còn `hAnsi` chi phối Latin mở rộng, tức toàn bộ chữ có
> dấu tiếng Việt; `python-docx` luôn ghi cả hai nên fixture không lộ, file Word thật thì có.
> `ascii` vẫn được ưu tiên khi có, nên đây chỉ là nới. Xem `git show d3039b71fbe`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/resolver.py \
        custom-addons/aidt_format_engine/tests/test_resolver.py
git commit -m "[ADD] aidt_format: resolver flatten chuỗi kế thừa định dạng

run.rPr > char style > para style > chuỗi base_style > docDefaults > theme.
_read_rpr chỉ trả khóa được khai tường minh — trả None sẽ xóa mất giá trị
thừa hưởng của tầng dưới. Có cache theo style_id."
```

---

### Task 4: Parser — `.docx` thành `IntermediateDoc`

**Files:**
- Create: `custom-addons/aidt_format_engine/parser.py`
- Test: `custom-addons/aidt_format_engine/tests/test_parser.py`

**Interfaces:**
- Consumes: `engine.resolver.StyleResolver`, `engine.types.{EffFormat, Para, PageSetup, IntermediateDoc}`.
- Produces:
  - `engine.parser.parse_docx(data: bytes) -> IntermediateDoc`
  - `engine.parser.UnreadableDocx(Exception)`

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_parser.py`:

```python
import unittest

import fixtures
from aidt_format_engine.parser import UnreadableDocx, parse_docx


class TestParser(unittest.TestCase):
    def test_le_trang_doc_dung(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertAlmostEqual(doc.pages.margin_mm['top'], 22.0, places=1)
        self.assertAlmostEqual(doc.pages.margin_mm['left'], 32.0, places=1)
        self.assertAlmostEqual(doc.pages.width_mm, 210.0, places=1)
        self.assertAlmostEqual(doc.pages.height_mm, 297.0, places=1)

    def test_le_sai_doc_ra_gia_tri_sai(self):
        doc = parse_docx(fixtures.sai_le_trang())
        self.assertAlmostEqual(doc.pages.margin_mm['top'], 10.0, places=1)

    def test_moi_doan_co_style_name_va_dinh_dang(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertGreater(len(doc.paras), 5)
        noi_dung = [p for p in doc.paras if p.style_name == 'VB_NoiDung']
        self.assertTrue(noi_dung)
        self.assertEqual(noi_dung[0].fmt.font, 'Times New Roman')
        self.assertEqual(noi_dung[0].fmt.size_pt, 14.0)
        self.assertEqual(noi_dung[0].fmt.align, 'justify')

    def test_index_bat_dau_tu_0_va_lien_tuc(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual([p.index for p in doc.paras],
                         list(range(len(doc.paras))))

    def test_runs_conflict_bat_dung_cho(self):
        doc = parse_docx(fixtures.run_lech_nhau())
        lech = [p for p in doc.paras if p.runs_conflict]
        self.assertEqual(len(lech), 1, 'chỉ đúng một đoạn được đánh dấu lệch')
        self.assertIn('cỡ 11', lech[0].text)

    def test_runs_conflict_khong_bat_oan(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual([p for p in doc.paras if p.runs_conflict], [])

    def test_dinh_dang_lay_tu_run_dai_nhat(self):
        """Một từ lạc cỡ không được quyết định định dạng của cả đoạn."""
        doc = parse_docx(fixtures.run_lech_nhau())
        lech = [p for p in doc.paras if p.runs_conflict][0]
        self.assertEqual(lech.fmt.size_pt, 14.0)

    def test_standard_hint_chua_duoc_dien_o_tang_parser(self):
        self.assertIsNone(parse_docx(fixtures.chuan_66()).standard_hint)

    def test_zone_chua_duoc_dien_o_tang_parser(self):
        doc = parse_docx(fixtures.chuan_66())
        self.assertEqual({p.zone for p in doc.paras}, {None})

    def test_file_hong_bao_UnreadableDocx(self):
        with self.assertRaises(UnreadableDocx):
            parse_docx(fixtures.hong())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_parser.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine.parser'`.

- [ ] **Step 3: Viết `engine/parser.py`**

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_parser.py -v
```

Expected: toàn bộ test trong file pass.

> **Cập nhật sau review Task 4.** Bộ test ở Step 1 để lọt ba nhánh: quy tắc
> `runs_conflict` không so `bold` (đưa `bold` vào tiêu chí mà suite vẫn xanh), guard
> `None` cho lề kế thừa, và nhánh đoạn trống. Bản đã merge thêm fixture
> `in_dam_giua_cau()` cùng ba test, mỗi test đã được mutation-test xác nhận là đỏ khi
> phá đúng nhánh nó bảo vệ. Fixture `run_lech_nhau()` cũng phải sửa: mẩu lạc cỡ ban đầu
> dài hơn phần thân nên quy tắc "run dài nhất thắng" chọn đúng nó.
> Xem `git show fc8ae229acb 9b6b5d6a69c 7d79306d102`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/parser.py \
        custom-addons/aidt_format_engine/tests/test_parser.py
git commit -m "[ADD] aidt_format: parser docx thành cấu trúc trung gian

Định dạng của đoạn lấy theo run dài nhất, không lấy run đầu — một từ in đậm
không được quyết định định dạng cả đoạn. runs_conflict so (font, size_pt)
chứ không so bold, vì in đậm giữa câu là hợp lệ."
```

---

### Task 5: Zone detector

**Files:**
- Create: `custom-addons/aidt_format_engine/zones.py`
- Test: `custom-addons/aidt_format_engine/tests/test_zones.py`

**Interfaces:**
- Consumes: `IntermediateDoc` từ `engine.parser.parse_docx`.
- Produces:
  - `engine.zones.detect_zones(doc) -> IntermediateDoc` — sửa `doc` tại chỗ rồi trả về chính nó: điền `Para.zone`, `Para.zone_confidence`, `doc.standard_hint`.
  - `engine.zones.ZONES: tuple[str, ...]` — bảy tên vùng hợp lệ, dùng cho `schema.py`.
  - `engine.zones.STYLE_MAP: dict[str, str]`

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_zones.py`:

```python
import unittest

import fixtures
from aidt_format_engine.parser import parse_docx
from aidt_format_engine.zones import ZONES, detect_zones


def _prepare(blob):
    return detect_zones(parse_docx(blob))


def _zones_of(doc):
    return {p.zone for p in doc.paras if p.text.strip()}


class TestZoneTheoStyle(unittest.TestCase):
    def test_moi_vung_nhan_dien_qua_style(self):
        doc = _prepare(fixtures.chuan_66())
        self.assertEqual(
            _zones_of(doc),
            {'tieu_de_dang', 'so_ky_hieu', 'trich_yeu', 'noi_dung',
             'noi_nhan', 'chu_ky'})

    def test_confidence_la_style_cho_moi_doan_co_chu(self):
        doc = _prepare(fixtures.chuan_66())
        for para in doc.paras:
            if para.text.strip():
                self.assertEqual(para.zone_confidence, 'style',
                                 'đoạn %d' % para.index)

    def test_moi_zone_deu_nam_trong_ZONES(self):
        doc = _prepare(fixtures.chuan_66())
        for para in doc.paras:
            self.assertIn(para.zone, ZONES)


class TestZoneHeuristic(unittest.TestCase):
    def test_gan_dung_khi_khong_co_style(self):
        doc = _prepare(fixtures.khong_co_style())
        by_zone = {}
        for para in doc.paras:
            if para.text.strip():
                by_zone.setdefault(para.zone, []).append(para.text)
        self.assertIn('tieu_de_dang', by_zone)
        self.assertIn('so_ky_hieu', by_zone)
        self.assertIn('trich_yeu', by_zone)
        self.assertIn('noi_nhan', by_zone)
        self.assertIn('chu_ky', by_zone)

    def test_confidence_la_heuristic(self):
        doc = _prepare(fixtures.khong_co_style())
        for para in doc.paras:
            if para.text.strip():
                self.assertEqual(para.zone_confidence, 'heuristic')

    def test_so_ky_hieu_khop_ca_dau_gach_va_gach_cheo(self):
        doc = _prepare(fixtures.khong_co_style())
        so = [p for p in doc.paras if p.zone == 'so_ky_hieu']
        self.assertEqual(len(so), 1)
        self.assertIn('456-BC/TU', so[0].text)


class TestStandardHint(unittest.TestCase):
    def test_tieu_de_dang_suy_ra_dang(self):
        self.assertEqual(_prepare(fixtures.chuan_66()).standard_hint, 'dang')

    def test_quoc_hieu_suy_ra_hanh_chinh(self):
        self.assertEqual(
            _prepare(fixtures.chuan_nd30()).standard_hint, 'hanh_chinh')


if __name__ == '__main__':
    unittest.main()
```

Xóa class rỗng `TestStandardHint` khi dán vào — nó không có tác dụng gì.

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_zones.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine.zones'`.

(Không dán class rỗng nào vào file test — mọi class trong đoạn trên đều có test thật.)

- [ ] **Step 3: Viết `engine/zones.py`**

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_zones.py -v
```

Expected: toàn bộ test trong file pass.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/zones.py \
        custom-addons/aidt_format_engine/tests/test_zones.py
git commit -m "[ADD] aidt_format: zone detector hai đường

Tra tên style trước (file sinh từ mẫu, chính xác tuyệt đối), heuristic sau
(file soạn tay). Gán theo từng đoạn nên file trộn cũng xử lý được, không cần
ngưỡng 'bao nhiêu style thì coi là template'."
```

---

### Task 6: Schema validate ruleset

**Files:**
- Create: `custom-addons/aidt_format_engine/schema.py`
- Test: `custom-addons/aidt_format_engine/tests/test_schema.py`

**Interfaces:**
- Consumes: `engine.zones.ZONES`.
- Produces:
  - `engine.schema.validate_ruleset(spec: dict) -> None` — raise khi sai.
  - `engine.schema.RulesetError(ValueError)` với thuộc tính `.path`.
  - `engine.schema.ZONE_ATTRS: dict[str, str]` — tên thuộc tính vùng hợp lệ và kiểu kiểm.

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_schema.py`:

```python
import copy
import unittest

from aidt_format_engine.schema import RulesetError, validate_ruleset

HOP_LE = {
    'ruleset': '66-QD/TW',
    'version': '2025.1',
    'ap_dung': 'dang',
    'so_ky_hieu': {
        'format': '{n}-{type_code}/{org_code}',
        'stamp_box_mm': {'x': 30, 'y': 52, 'w': 60, 'h': 8},
    },
    'page': {
        'size': 'A4',
        'margins_mm': {'top': [20, 25], 'bottom': [20, 25],
                       'left': [30, 35], 'right': [15, 20]},
    },
    'zones': {
        'tieu_de_dang': {'required': True, 'font': 'Times New Roman',
                         'size_pt': [15, 15], 'bold': True,
                         'uppercase': True, 'align': 'center'},
        'noi_dung': {'font': 'Times New Roman', 'size_pt': [14, 15],
                     'line_spacing': [1.0, 1.5],
                     'line_spacing_fixed_allowed': False,
                     'first_line_indent_cm': [1.0, 1.27],
                     'align': ['justify']},
    },
    'severity_overrides': {'noi_dung.size_pt': 'warning'},
}


def _without(path):
    spec = copy.deepcopy(HOP_LE)
    target, key = spec, path[-1]
    for part in path[:-1]:
        target = target[part]
    del target[key]
    return spec


def _with(path, value):
    spec = copy.deepcopy(HOP_LE)
    target = spec
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return spec


class TestSchema(unittest.TestCase):
    def test_bo_luat_hop_le_khong_bao_loi(self):
        validate_ruleset(copy.deepcopy(HOP_LE))

    def test_khong_phai_dict(self):
        with self.assertRaises(RulesetError):
            validate_ruleset(['khong', 'phai', 'dict'])

    def test_thieu_khoa_bat_buoc(self):
        for key in ('ruleset', 'version', 'ap_dung'):
            with self.subTest(key=key), self.assertRaises(RulesetError) as ctx:
                validate_ruleset(_without([key]))
            self.assertEqual(ctx.exception.path, key)

    def test_ap_dung_sai_gia_tri(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['ap_dung'], 'van_ban_dang'))
        self.assertEqual(ctx.exception.path, 'ap_dung')

    def test_format_thieu_bien(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['so_ky_hieu', 'format'], '{n}/{type_code}'))
        self.assertEqual(ctx.exception.path, 'so_ky_hieu.format')

    def test_stamp_box_thieu_chieu(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['so_ky_hieu', 'stamp_box_mm'], {'x': 30, 'y': 52}))
        self.assertEqual(ctx.exception.path, 'so_ky_hieu.stamp_box_mm.w')

    def test_page_size_khong_phai_A4(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'size'], 'Letter'))
        self.assertEqual(ctx.exception.path, 'page.size')

    def test_khoang_khong_phai_cap(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'margins_mm', 'top'], 20))
        self.assertEqual(ctx.exception.path, 'page.margins_mm.top')

    def test_khoang_min_lon_hon_max(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung', 'size_pt'], [15, 14]))
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.size_pt')

    def test_ten_vung_khong_hop_le(self):
        spec = copy.deepcopy(HOP_LE)
        spec['zones']['vung_bia_ra'] = {'required': True}
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(spec)
        self.assertEqual(ctx.exception.path, 'zones.vung_bia_ra')

    def test_thuoc_tinh_vung_khong_hop_le(self):
        spec = copy.deepcopy(HOP_LE)
        spec['zones']['noi_dung']['mau_chu'] = 'do'
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(spec)
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.mau_chu')

    def test_bool_khong_phai_bool(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung',
                                    'line_spacing_fixed_allowed'], 'khong'))
        self.assertEqual(
            ctx.exception.path, 'zones.noi_dung.line_spacing_fixed_allowed')

    def test_align_sai_gia_tri(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['zones', 'noi_dung', 'align'], ['giua']))
        self.assertEqual(ctx.exception.path, 'zones.noi_dung.align')

    def test_severity_override_sai_muc(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['severity_overrides'], {'noi_dung.size_pt': 'nghiem'}))
        self.assertEqual(
            ctx.exception.path, 'severity_overrides.noi_dung.size_pt')

    def test_severity_override_tro_toi_vung_khong_ton_tai(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(
                _with(['severity_overrides'], {'vung_la.size_pt': 'warning'}))
        self.assertEqual(ctx.exception.path, 'severity_overrides.vung_la.size_pt')

    def test_loi_co_duong_dan_trong_thong_diep(self):
        with self.assertRaises(RulesetError) as ctx:
            validate_ruleset(_with(['page', 'size'], 'Letter'))
        self.assertIn('page.size', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_schema.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine.schema'`.

- [ ] **Step 3: Viết `engine/schema.py`**

```python
"""Kiểm cấu trúc bộ luật thể thức.

Bộ luật là dữ liệu do người dùng sửa, nên sai cú pháp là chuyện thường. Lỗi phải
nêu ĐÚNG ĐƯỜNG DẪN khóa sai, không phải 'ruleset không hợp lệ' — người sửa YAML
cần biết sửa ở dòng nào.
"""
from .zones import ZONES

ALIGN_VALUES = ('left', 'center', 'right', 'justify')
SEVERITIES = ('error', 'warning')
FORMAT_VARS = ('{n}', '{type_code}', '{org_code}')
STAMP_DIMS = ('x', 'y', 'w', 'h')

# tên thuộc tính vùng -> kiểu kiểm
ZONE_ATTRS = {
    'required': 'bool',
    'font': 'str',
    'size_pt': 'range',
    'bold': 'bool',
    'italic': 'bool',
    'uppercase': 'bool',
    'align': 'align',
    'line_spacing': 'range',
    'line_spacing_fixed_allowed': 'bool',
    'first_line_indent_cm': 'range',
}


class RulesetError(ValueError):
    def __init__(self, path, message):
        self.path = path
        super().__init__('%s: %s' % (path, message))


def validate_ruleset(spec):
    """Raise RulesetError nếu bộ luật sai cấu trúc. Trả None nếu hợp lệ."""
    if not isinstance(spec, dict):
        raise RulesetError('<gốc>', 'bộ luật phải là một từ điển khóa-giá trị')
    for key in ('ruleset', 'version', 'ap_dung'):
        if key not in spec:
            raise RulesetError(key, 'thiếu khóa bắt buộc')
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise RulesetError(key, 'phải là chuỗi không rỗng')
    if spec['ap_dung'] not in ('dang', 'hanh_chinh'):
        raise RulesetError('ap_dung', "phải là 'dang' hoặc 'hanh_chinh'")
    _check_so_ky_hieu(spec.get('so_ky_hieu'))
    _check_page(spec.get('page'))
    zones = _check_zones(spec.get('zones'))
    _check_severity_overrides(spec.get('severity_overrides'), zones)


def _check_so_ky_hieu(block):
    if block is None:
        raise RulesetError('so_ky_hieu', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict):
        raise RulesetError('so_ky_hieu', 'phải là từ điển')
    fmt = block.get('format')
    if not isinstance(fmt, str):
        raise RulesetError('so_ky_hieu.format', 'phải là chuỗi')
    thieu = [var for var in FORMAT_VARS if var not in fmt]
    if thieu:
        raise RulesetError('so_ky_hieu.format',
                           'thiếu biến %s' % ', '.join(thieu))
    box = block.get('stamp_box_mm')
    if not isinstance(box, dict):
        raise RulesetError('so_ky_hieu.stamp_box_mm', 'phải là từ điển')
    for dim in STAMP_DIMS:
        if dim not in box:
            raise RulesetError('so_ky_hieu.stamp_box_mm.%s' % dim,
                               'thiếu khóa bắt buộc')
        if not _is_number(box[dim]):
            raise RulesetError('so_ky_hieu.stamp_box_mm.%s' % dim,
                               'phải là số (mm)')


def _check_page(block):
    if block is None:
        raise RulesetError('page', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict):
        raise RulesetError('page', 'phải là từ điển')
    if block.get('size') != 'A4':
        raise RulesetError('page.size', "vòng này chỉ hỗ trợ 'A4'")
    margins = block.get('margins_mm')
    if not isinstance(margins, dict):
        raise RulesetError('page.margins_mm', 'phải là từ điển')
    for side in ('top', 'bottom', 'left', 'right'):
        if side not in margins:
            raise RulesetError('page.margins_mm.%s' % side,
                               'thiếu khóa bắt buộc')
        _check_range(margins[side], 'page.margins_mm.%s' % side)


def _check_zones(block):
    if block is None:
        raise RulesetError('zones', 'thiếu khóa bắt buộc')
    if not isinstance(block, dict) or not block:
        raise RulesetError('zones', 'phải là từ điển không rỗng')
    for zone, rules in block.items():
        if zone not in ZONES:
            raise RulesetError('zones.%s' % zone,
                               'tên vùng không hợp lệ, phải thuộc %s'
                               % ', '.join(ZONES))
        if not isinstance(rules, dict):
            raise RulesetError('zones.%s' % zone, 'phải là từ điển')
        for attr, value in rules.items():
            path = 'zones.%s.%s' % (zone, attr)
            kind = ZONE_ATTRS.get(attr)
            if kind is None:
                raise RulesetError(
                    path, 'thuộc tính không hợp lệ, phải thuộc %s'
                    % ', '.join(sorted(ZONE_ATTRS)))
            _check_value(value, kind, path)
    return set(block)


def _check_value(value, kind, path):
    if kind == 'bool':
        if not isinstance(value, bool):
            raise RulesetError(path, 'phải là true hoặc false')
    elif kind == 'str':
        if not isinstance(value, str) or not value.strip():
            raise RulesetError(path, 'phải là chuỗi không rỗng')
    elif kind == 'range':
        _check_range(value, path)
    elif kind == 'align':
        values = value if isinstance(value, list) else [value]
        sai = [v for v in values if v not in ALIGN_VALUES]
        if sai:
            raise RulesetError(path, 'giá trị %s không hợp lệ, phải thuộc %s'
                               % (', '.join(map(str, sai)),
                                  ', '.join(ALIGN_VALUES)))


def _check_range(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise RulesetError(path, 'phải là cặp [min, max]')
    if not all(_is_number(item) for item in value):
        raise RulesetError(path, 'min và max phải là số')
    if value[0] > value[1]:
        raise RulesetError(path, 'min không được lớn hơn max')


def _check_severity_overrides(block, zones):
    if block is None:
        return
    if not isinstance(block, dict):
        raise RulesetError('severity_overrides', 'phải là từ điển')
    for rule_id, severity in block.items():
        path = 'severity_overrides.%s' % rule_id
        if severity not in SEVERITIES:
            raise RulesetError(path, "phải là 'error' hoặc 'warning'")
        zone, _, attr = str(rule_id).partition('.')
        if not attr:
            raise RulesetError(path, "phải có dạng '<vùng>.<thuộc tính>'")
        if zone == 'page':
            continue
        if zone not in zones:
            raise RulesetError(path, "vùng '%s' không có trong zones" % zone)
        if attr not in ZONE_ATTRS:
            raise RulesetError(path,
                               "thuộc tính '%s' không hợp lệ" % attr)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_schema.py -v
```

Expected: toàn bộ test trong file pass.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/schema.py \
        custom-addons/aidt_format_engine/tests/test_schema.py
git commit -m "[ADD] aidt_format: validate cấu trúc bộ luật thể thức

Lỗi mang theo .path để nêu đúng khóa sai — người sửa YAML cần biết sửa ở
dòng nào, không phải 'ruleset không hợp lệ'."
```

---

### Task 7: Rule engine

**Files:**
- Create: `custom-addons/aidt_format_engine/rules.py`
- Test: `custom-addons/aidt_format_engine/tests/test_rules.py`

**Interfaces:**
- Consumes: `engine.findings.{Finding, ERROR, WARNING}`, `IntermediateDoc` đã qua `detect_zones`.
- Produces: `engine.rules.run_rules(doc, spec) -> list[Finding]`

Vòng lặp generic, **không có `if` nào cho từng quy định cụ thể**. Nếu thấy mình
viết `if ruleset == '66-QD/TW'` thì thiết kế đã sai.

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format_engine/tests/test_rules.py`:

```python
import copy
import unittest

import fixtures
from aidt_format_engine.parser import parse_docx
from aidt_format_engine.rules import run_rules
from aidt_format_engine.zones import detect_zones

RULESET_66 = {
    'ruleset': '66-QD/TW',
    'version': '2025.1',
    'ap_dung': 'dang',
    'so_ky_hieu': {
        'format': '{n}-{type_code}/{org_code}',
        'stamp_box_mm': {'x': 30, 'y': 52, 'w': 60, 'h': 8},
    },
    'page': {
        'size': 'A4',
        'margins_mm': {'top': [20, 25], 'bottom': [20, 25],
                       'left': [30, 35], 'right': [15, 20]},
    },
    'zones': {
        'tieu_de_dang': {'required': True, 'font': 'Times New Roman',
                         'size_pt': [15, 15], 'bold': True,
                         'uppercase': True, 'align': 'center'},
        'so_ky_hieu': {'required': True, 'size_pt': [14, 14]},
        'trich_yeu': {'required': True, 'font': 'Times New Roman',
                      'size_pt': [14, 14], 'bold': True, 'align': 'center'},
        'noi_dung': {'font': 'Times New Roman', 'size_pt': [14, 15],
                     'line_spacing': [1.0, 1.5],
                     'line_spacing_fixed_allowed': False,
                     'first_line_indent_cm': [1.0, 1.27],
                     'align': ['justify']},
        'noi_nhan': {'required': True, 'size_pt': [12, 12]},
        'chu_ky': {'required': True, 'uppercase': True, 'align': 'right'},
    },
    'severity_overrides': {},
}


def _check(blob, spec=None):
    doc = detect_zones(parse_docx(blob))
    return run_rules(doc, spec or copy.deepcopy(RULESET_66))


def _ids(findings):
    return {finding.rule_id for finding in findings}


def _by_id(findings, rule_id):
    return [f for f in findings if f.rule_id == rule_id]


class TestFileDat(unittest.TestCase):
    def test_chuan_66_khong_co_finding(self):
        findings = _check(fixtures.chuan_66())
        self.assertEqual(findings, [], _ids(findings))


class TestPage(unittest.TestCase):
    def test_le_tren_ngoai_khoang(self):
        findings = _check(fixtures.sai_le_trang())
        self.assertIn('page.margin_top', _ids(findings))

    def test_finding_le_neu_ro_mong_doi_va_thuc_te(self):
        finding = _by_id(_check(fixtures.sai_le_trang()),
                         'page.margin_top')[0]
        self.assertIn('20', finding.expected)
        self.assertIn('25', finding.expected)
        self.assertIn('10', finding.actual)

    def test_le_khac_khong_bao_oan(self):
        ids = _ids(_check(fixtures.sai_le_trang()))
        self.assertNotIn('page.margin_left', ids)
        self.assertNotIn('page.margin_bottom', ids)


class TestVungBatBuoc(unittest.TestCase):
    def test_thieu_noi_nhan(self):
        findings = _check(fixtures.thieu_noi_nhan())
        self.assertIn('noi_nhan.required', _ids(findings))

    def test_thieu_vung_la_loi_chan(self):
        finding = _by_id(_check(fixtures.thieu_noi_nhan()),
                         'noi_nhan.required')[0]
        self.assertEqual(finding.severity, 'error')


class TestThuocTinhVung(unittest.TestCase):
    def test_sai_font_bat_duoc_qua_chuoi_ke_thua(self):
        findings = _check(fixtures.sai_font())
        self.assertIn('noi_dung.font', _ids(findings))
        finding = _by_id(findings, 'noi_dung.font')[0]
        self.assertEqual(finding.actual, 'Arial')
        self.assertEqual(finding.expected, 'Times New Roman')

    def test_dan_dong_tuyet_doi_bi_cam(self):
        findings = _check(fixtures.sai_dan_dong_exact())
        self.assertIn('noi_dung.line_spacing_fixed', _ids(findings))

    def test_location_neu_so_doan(self):
        finding = _by_id(_check(fixtures.sai_font()), 'noi_dung.font')[0]
        self.assertRegex(finding.location, r'Đoạn \d+')


class TestRunLechNhau(unittest.TestCase):
    def test_bao_runs_conflict(self):
        findings = _check(fixtures.run_lech_nhau())
        self.assertIn('doc.runs_conflict', _ids(findings))

    def test_runs_conflict_chi_la_canh_bao(self):
        finding = _by_id(_check(fixtures.run_lech_nhau()),
                         'doc.runs_conflict')[0]
        self.assertEqual(finding.severity, 'warning')


class TestSeverityOverrides(unittest.TestCase):
    def test_override_ha_xuong_warning(self):
        spec = copy.deepcopy(RULESET_66)
        spec['severity_overrides'] = {'noi_dung.font': 'warning'}
        finding = _by_id(_check(fixtures.sai_font(), spec), 'noi_dung.font')[0]
        self.assertEqual(finding.severity, 'warning')

    def test_khong_override_thi_la_error(self):
        finding = _by_id(_check(fixtures.sai_font()), 'noi_dung.font')[0]
        self.assertEqual(finding.severity, 'error')


class TestHeuristicHaMucDo(unittest.TestCase):
    def test_vung_chi_doan_duoc_thi_khong_chan(self):
        """khong_co_style() chạy heuristic hết, nên không finding nào là error."""
        findings = _check(fixtures.khong_co_style())
        self.assertTrue(findings, 'phải có ít nhất một finding để test có nghĩa')
        for finding in findings:
            if finding.zone:
                self.assertEqual(finding.severity, 'warning',
                                 '%s không được chặn' % finding.rule_id)


class TestSaiHeQuyChuan(unittest.TestCase):
    def test_file_hanh_chinh_kiem_bang_bo_luat_dang(self):
        findings = _check(fixtures.chuan_nd30())
        self.assertIn('file.wrong_standard', _ids(findings))
        finding = _by_id(findings, 'file.wrong_standard')[0]
        self.assertEqual(finding.severity, 'warning')

    def test_file_dung_he_quy_chuan_khong_bao(self):
        self.assertNotIn('file.wrong_standard', _ids(_check(fixtures.chuan_66())))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests/test_rules.py -v
```

Expected: FAIL với `ModuleNotFoundError: No module named 'engine.rules'`.

- [ ] **Step 3: Viết `engine/rules.py`**

```python
"""Đối chiếu định dạng hiệu lực với bộ luật, sinh danh sách phát hiện.

Đây là vòng lặp generic: KHÔNG có nhánh nào cho từng quy định cụ thể. Thấy mình
viết `if ruleset == '66-QD/TW'` là thiết kế đã sai — quy định nằm trong dữ liệu.
"""
from dataclasses import replace

from .findings import ERROR, WARNING, Finding

_A4_MM = (210.0, 297.0)
_A4_SAI_SO_MM = 2.0


def run_rules(doc, spec):
    zones_spec = spec.get('zones') or {}
    findings = []
    findings += _page_rules(doc, spec)
    findings += _required_rules(doc, zones_spec)
    for para in doc.paras:
        rules = zones_spec.get(para.zone)
        if rules:
            findings += _para_rules(para, rules)
    findings += _conflict_rules(doc)
    findings += _standard_rules(doc, spec)
    return _apply_severity(findings, doc, spec)


# -- trang -----------------------------------------------------------------

def _page_rules(doc, spec):
    page = spec.get('page') or {}
    out = []
    if page.get('size') == 'A4':
        for value, expected, name in ((doc.pages.width_mm, _A4_MM[0], 'rộng'),
                                      (doc.pages.height_mm, _A4_MM[1], 'cao')):
            if value is not None and abs(value - expected) > _A4_SAI_SO_MM:
                out.append(Finding(
                    rule_id='page.size', severity=ERROR, zone='page',
                    location='Thiết lập trang',
                    expected='A4 (%gmm × %gmm)' % _A4_MM,
                    actual='%s %gmm' % (name, value),
                    suggestion='Đặt khổ giấy A4 trong Layout > Size'))
                break
    for side, bounds in (page.get('margins_mm') or {}).items():
        actual = doc.pages.margin_mm.get(side)
        if actual is None:
            continue
        low, high = bounds
        if not low <= actual <= high:
            out.append(Finding(
                rule_id='page.margin_%s' % side, severity=ERROR, zone='page',
                location='Thiết lập trang',
                expected=_range_text(low, high, 'mm'),
                actual='%gmm' % round(actual, 1),
                suggestion='Đặt lề %s trong khoảng %s'
                           % (side, _range_text(low, high, 'mm'))))
    return out


# -- vùng bắt buộc ---------------------------------------------------------

def _required_rules(doc, zones_spec):
    present = {para.zone for para in doc.paras if (para.text or '').strip()}
    out = []
    for zone, rules in zones_spec.items():
        if rules.get('required') and zone not in present:
            out.append(Finding(
                rule_id='%s.required' % zone, severity=ERROR, zone=zone,
                location='Toàn văn bản',
                expected='Văn bản phải có vùng "%s"' % zone,
                actual='Không tìm thấy',
                suggestion='Bổ sung vùng "%s" theo mẫu của hệ thống' % zone))
    return out


# -- thuộc tính từng đoạn --------------------------------------------------

def _para_rules(para, rules):
    fmt = para.fmt
    location = 'Đoạn %d' % (para.index + 1)
    out = []

    def add(attr, expected, actual, suggestion):
        out.append(Finding(
            rule_id='%s.%s' % (para.zone, attr), severity=ERROR,
            zone=para.zone, location=location, expected=expected,
            actual=actual, suggestion=suggestion))

    if 'font' in rules and fmt.font and fmt.font != rules['font']:
        add('font', rules['font'], fmt.font,
            'Đặt phông chữ %s cho đoạn này' % rules['font'])

    if 'size_pt' in rules and fmt.size_pt is not None:
        low, high = rules['size_pt']
        if not low <= fmt.size_pt <= high:
            add('size_pt', _range_text(low, high, 'pt'), '%gpt' % fmt.size_pt,
                'Đặt cỡ chữ %s' % _range_text(low, high, 'pt'))

    for attr, nhan in (('bold', 'in đậm'), ('italic', 'in nghiêng')):
        if attr in rules and getattr(fmt, attr) is not None \
                and bool(getattr(fmt, attr)) != bool(rules[attr]):
            add(attr, 'có %s' % nhan if rules[attr] else 'không %s' % nhan,
                'có %s' % nhan if getattr(fmt, attr) else 'không %s' % nhan,
                '%s chữ cho đoạn này' % ('Bật ' + nhan if rules[attr]
                                         else 'Tắt ' + nhan))

    text = (para.text or '').strip()
    if rules.get('uppercase') and text and text != text.upper():
        add('uppercase', 'Viết hoa toàn bộ', text[:40],
            'Chuyển đoạn này sang chữ in hoa')

    if 'align' in rules and fmt.align:
        allowed = rules['align'] if isinstance(rules['align'], list) \
            else [rules['align']]
        if fmt.align not in allowed:
            add('align', ' hoặc '.join(allowed), fmt.align,
                'Căn đoạn này theo %s' % ' hoặc '.join(allowed))

    if 'line_spacing' in rules and fmt.line_spacing is not None:
        low, high = rules['line_spacing']
        if not low <= fmt.line_spacing <= high:
            add('line_spacing', _range_text(low, high, ' lần dòng'),
                '%.2f lần dòng' % fmt.line_spacing,
                'Đặt dãn dòng Multiple trong khoảng %s'
                % _range_text(low, high, ''))

    if rules.get('line_spacing_fixed_allowed') is False and fmt.line_spacing_fixed:
        add('line_spacing_fixed', 'Dãn dòng khai theo số lần dòng (Multiple)',
            'Dãn dòng khai theo chiều cao tuyệt đối (Exactly/At least)',
            'Đổi Line spacing sang Multiple')

    if 'first_line_indent_cm' in rules and fmt.first_line_indent_cm is not None:
        low, high = rules['first_line_indent_cm']
        if not low <= fmt.first_line_indent_cm <= high:
            add('first_line_indent_cm', _range_text(low, high, 'cm'),
                '%.2fcm' % fmt.first_line_indent_cm,
                'Đặt thụt đầu dòng %s' % _range_text(low, high, 'cm'))

    return out


# -- run lệch nhau ---------------------------------------------------------

def _conflict_rules(doc):
    return [
        Finding(
            rule_id='doc.runs_conflict', severity=WARNING,
            zone=para.zone or '', location='Đoạn %d' % (para.index + 1),
            expected='Cả đoạn dùng một phông và một cỡ chữ',
            actual='Trong đoạn có nhiều phông hoặc cỡ chữ khác nhau',
            suggestion='Chọn cả đoạn rồi đặt lại phông và cỡ chữ')
        for para in doc.paras if para.runs_conflict
    ]


# -- hệ quy chuẩn ----------------------------------------------------------

_TEN_CHUAN = {'dang': 'văn bản Đảng', 'hanh_chinh': 'văn bản hành chính'}


def _standard_rules(doc, spec):
    ap_dung = spec.get('ap_dung')
    if not doc.standard_hint or not ap_dung or doc.standard_hint == ap_dung:
        return []
    return [Finding(
        rule_id='file.wrong_standard', severity=WARNING, zone='',
        location='Toàn văn bản',
        expected='Bộ luật đang dùng cho %s' % _TEN_CHUAN.get(ap_dung, ap_dung),
        actual='Văn bản trông như %s'
               % _TEN_CHUAN.get(doc.standard_hint, doc.standard_hint),
        suggestion='Kiểm tra lại loại văn bản đã chọn')]


# -- mức nghiêm trọng ------------------------------------------------------

def _apply_severity(findings, doc, spec):
    overrides = spec.get('severity_overrides') or {}
    doan_duoc = {para.zone for para in doc.paras
                 if para.zone_confidence == 'heuristic'}
    out = []
    for finding in findings:
        severity = overrides.get(finding.rule_id, finding.severity)
        # Vùng chỉ đoán được thì không chặn — tránh chặn oan người soạn tay
        # ngoài mẫu. Áp SAU overrides để override không bị bỏ qua.
        if severity == ERROR and finding.zone and finding.zone in doan_duoc:
            severity = WARNING
        out.append(finding if severity == finding.severity
                   else replace(finding, severity=severity))
    return out


def _range_text(low, high, unit):
    if low == high:
        return '%g%s' % (low, unit)
    return '%g–%g%s' % (low, high, unit)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests -v
```

Expected: toàn bộ 7 file test trong engine/tests pass.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format_engine/rules.py \
        custom-addons/aidt_format_engine/tests/test_rules.py
git commit -m "[ADD] aidt_format: rule engine generic

Không có nhánh nào cho từng quy định — quy định nằm trong dữ liệu. Hạ mức
theo zone_confidence áp SAU severity_overrides, để override không bị bỏ qua."
```

---

### Task 8: Model `aidt.format.ruleset` + view + quyền + seed

**Files:**
- Create: `custom-addons/aidt_format/models/__init__.py`
- Create: `custom-addons/aidt_format/models/format_ruleset.py`
- Create: `custom-addons/aidt_format/security/ir.model.access.csv`
- Create: `custom-addons/aidt_format/views/format_ruleset_views.xml`
- Create: `custom-addons/aidt_format/data/format_ruleset_data.xml`
- Create: `custom-addons/aidt_format/tests/__init__.py`
- Modify: `custom-addons/aidt_format/__init__.py`
- Modify: `custom-addons/aidt_format/__manifest__.py`
- Test: `custom-addons/aidt_format/tests/test_ruleset.py`

**Interfaces:**
- Consumes: `engine.schema.{validate_ruleset, RulesetError}`.
- Produces:
  - Model `aidt.format.ruleset` với trường `code, version, ap_dung, spec_yaml, active` và phương thức `spec() -> dict`.
  - XML id `aidt_format.ruleset_66_qd_tw`, `aidt_format.ruleset_nd_30_2020`.

**Lưu ý về ranh giới:** spec (QĐ-8) yêu cầu `spec_yaml` chuyển readonly khi đã có
văn bản tham chiếu. `aidt_format` không biết model văn bản nào tham chiếu nó, nên
guard đó **thuộc đợt 3** (`aidt_vanban_di` override `write` của model này). Task
này chỉ làm phần versioning: unique(code, version) + `active`.

- [ ] **Step 1: Viết test (test này phải fail)**

`custom-addons/aidt_format/tests/__init__.py`:

```python
from . import test_ruleset
```

`custom-addons/aidt_format/tests/test_ruleset.py`:

```python
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

YAML_HOP_LE = """
ruleset: "TEST"
version: "1.0"
ap_dung: dang
so_ky_hieu:
  format: "{n}-{type_code}/{org_code}"
  stamp_box_mm: {x: 30, y: 52, w: 60, h: 8}
page:
  size: A4
  margins_mm: {top: [20, 25], bottom: [20, 25], left: [30, 35], right: [15, 20]}
zones:
  noi_dung:
    font: "Times New Roman"
    size_pt: [14, 15]
"""


class TestFormatRuleset(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ruleset = cls.env['aidt.format.ruleset']

    def _create(self, **overrides):
        values = {'code': 'TEST', 'version': '1.0', 'ap_dung': 'dang',
                  'spec_yaml': YAML_HOP_LE}
        values.update(overrides)
        return self.Ruleset.create(values)

    def test_tao_duoc_bo_luat_hop_le(self):
        ruleset = self._create()
        self.assertTrue(ruleset.active)

    def test_spec_tra_ve_dict_da_parse(self):
        spec = self._create().spec()
        self.assertEqual(spec['ap_dung'], 'dang')
        self.assertEqual(spec['zones']['noi_dung']['size_pt'], [14, 15])

    def test_display_name_gom_code_va_version(self):
        ruleset = self._create()
        self.assertIn('TEST', ruleset.display_name)
        self.assertIn('1.0', ruleset.display_name)

    def test_yaml_sai_cu_phap_bi_chan(self):
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml='zones: [khong dong ngoac')
        self.assertIn('YAML', str(ctx.exception))

    def test_yaml_sai_cau_truc_bi_chan_va_neu_duong_dan(self):
        yaml_sai = YAML_HOP_LE.replace('size: A4', 'size: Letter')
        with self.assertRaises(ValidationError) as ctx:
            self._create(spec_yaml=yaml_sai)
        self.assertIn('page.size', str(ctx.exception))

    def test_ap_dung_lech_voi_yaml_bi_chan(self):
        with self.assertRaises(ValidationError) as ctx:
            self._create(ap_dung='hanh_chinh')
        self.assertIn('ap_dung', str(ctx.exception))

    def test_yaml_khong_phai_tu_dien_bi_chan(self):
        with self.assertRaises(ValidationError):
            self._create(spec_yaml='- mot\n- hai\n')

    @mute_logger('odoo.sql_db')
    def test_trung_code_va_version_bi_chan(self):
        self._create()
        # Bọc trong savepoint: IntegrityError làm hỏng cursor, không có savepoint
        # thì teardown của TransactionCase cũng chết theo.
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self._create()
            self.env.flush_all()

    def test_cung_code_khac_version_thi_duoc(self):
        self._create(version='1.0')
        self._create(version='2.0')
        self.assertEqual(
            self.Ruleset.search_count([('code', '=', 'TEST')]), 2)

    def test_sua_yaml_thanh_sai_cung_bi_chan(self):
        ruleset = self._create()
        with self.assertRaises(ValidationError):
            ruleset.spec_yaml = 'ruleset: chi co mot khoa\n'


class TestSeedRuleset(TransactionCase):
    def test_hai_bo_luat_duoc_seed(self):
        for xml_id, ap_dung in (('aidt_format.ruleset_66_qd_tw', 'dang'),
                                ('aidt_format.ruleset_nd_30_2020', 'hanh_chinh')):
            with self.subTest(xml_id=xml_id):
                ruleset = self.env.ref(xml_id)
                self.assertEqual(ruleset.ap_dung, ap_dung)
                self.assertTrue(ruleset.active)

    def test_bo_luat_seed_parse_duoc_va_hop_le(self):
        """Seed đi qua đúng constraint như dữ liệu người dùng nhập."""
        for xml_id in ('aidt_format.ruleset_66_qd_tw',
                       'aidt_format.ruleset_nd_30_2020'):
            with self.subTest(xml_id=xml_id):
                spec = self.env.ref(xml_id).spec()
                self.assertIn('zones', spec)
                self.assertIn('noi_dung', spec['zones'])

    def test_so_ky_hieu_hai_chuan_khac_thu_tu(self):
        dang = self.env.ref('aidt_format.ruleset_66_qd_tw').spec()
        hanh_chinh = self.env.ref('aidt_format.ruleset_nd_30_2020').spec()
        self.assertEqual(dang['so_ky_hieu']['format'],
                         '{n}-{type_code}/{org_code}')
        self.assertEqual(hanh_chinh['so_ky_hieu']['format'],
                         '{n}/{type_code}-{org_code}')
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -u aidt_format --http-port=8098 \
  --test-enable --stop-after-init --log-level=test 2>&1 | tail -30
```

Expected: FAIL — `KeyError: 'aidt.format.ruleset'`.

- [ ] **Step 3: Viết `models/format_ruleset.py`**

```python
import yaml

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.aidt_format_engine.schema import RulesetError, validate_ruleset


class AidtFormatRuleset(models.Model):
    _name = 'aidt.format.ruleset'
    _description = 'Bộ luật thể thức văn bản'
    _order = 'code, version desc'

    code = fields.Char(
        string='Mã bộ luật', required=True,
        help="Ví dụ: 66-QD/TW, ND-30/2020.")
    version = fields.Char(
        string='Phiên bản', required=True,
        help="Đổi quy định thì tạo phiên bản mới rồi lưu trữ phiên bản cũ, "
             "không sửa tại chỗ — để văn bản cũ còn đối chiếu được với đúng "
             "bộ luật đã dùng ngày đó.")
    ap_dung = fields.Selection(
        [('dang', 'Văn bản Đảng'), ('hanh_chinh', 'Văn bản hành chính')],
        string='Áp dụng cho', required=True)
    spec_yaml = fields.Text(
        string='Bộ luật (YAML)', required=True,
        help="Toàn bộ quy định thể thức. Sửa ở đây, không cần cập nhật mã nguồn.")
    active = fields.Boolean(string='Đang dùng', default=True)

    # Odoo 19 dùng models.Constraint, không dùng _sql_constraints — theo đúng
    # quy ước của addons/mail/models/mail_alias_domain.py trong repo này.
    _code_version_uniq = models.Constraint(
        'UNIQUE(code, version)',
        'Mỗi bộ luật chỉ có một bản ghi cho mỗi phiên bản.',
    )

    @api.depends('code', 'version')
    def _compute_display_name(self):
        for ruleset in self:
            ruleset.display_name = '%s %s' % (ruleset.code or '',
                                              ruleset.version or '')

    @api.constrains('spec_yaml', 'ap_dung')
    def _check_spec_yaml(self):
        for ruleset in self:
            spec = ruleset._parse_yaml()
            try:
                validate_ruleset(spec)
            except RulesetError as exc:
                raise ValidationError(_(
                    "Bộ luật %(name)s sai cấu trúc — %(detail)s",
                    name=ruleset.display_name, detail=str(exc))) from exc
            if spec.get('ap_dung') != ruleset.ap_dung:
                raise ValidationError(_(
                    "Trường 'Áp dụng cho' là %(field)s nhưng khóa ap_dung "
                    "trong YAML là %(yaml)s. Hai giá trị phải khớp nhau.",
                    field=ruleset.ap_dung, yaml=spec.get('ap_dung')))

    def _parse_yaml(self):
        self.ensure_one()
        try:
            spec = yaml.safe_load(self.spec_yaml or '')
        except yaml.YAMLError as exc:
            raise ValidationError(_(
                "Bộ luật %(name)s không phải YAML hợp lệ — %(detail)s",
                name=self.display_name, detail=str(exc))) from exc
        if not isinstance(spec, dict):
            raise ValidationError(_(
                "Bộ luật %(name)s phải là một từ điển khóa-giá trị ở cấp cao nhất.",
                name=self.display_name))
        return spec

    def spec(self):
        """Bộ luật đã parse, dạng dict. Dùng bởi aidt.format.checker."""
        return self._parse_yaml()
```

- [ ] **Step 4: Viết `models/__init__.py` và sửa `__init__.py` gốc**

`custom-addons/aidt_format/models/__init__.py`:

```python
from . import format_ruleset
```

`custom-addons/aidt_format/__init__.py` (thay nội dung rỗng):

```python
from . import models
```

- [ ] **Step 5: Viết quyền truy cập**

`custom-addons/aidt_format/security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_aidt_format_ruleset_user,aidt.format.ruleset user,model_aidt_format_ruleset,base.group_user,1,0,0,0
access_aidt_format_ruleset_system,aidt.format.ruleset system,model_aidt_format_ruleset,base.group_system,1,1,1,1
```

Dùng `base.group_*` chứ không dùng group của `aidt_org`: module này cố ý không
depends `aidt_org` để còn dùng lại được cho văn bản đến. Đợt 3 sẽ thêm dòng cho
`aidt_org.group_aidt_admin`.

- [ ] **Step 6: Viết view**

`custom-addons/aidt_format/views/format_ruleset_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="format_ruleset_view_list" model="ir.ui.view">
        <field name="name">aidt.format.ruleset.list</field>
        <field name="model">aidt.format.ruleset</field>
        <field name="arch" type="xml">
            <list>
                <field name="code"/>
                <field name="version"/>
                <field name="ap_dung"/>
                <field name="active" widget="boolean_toggle"/>
            </list>
        </field>
    </record>

    <record id="format_ruleset_view_form" model="ir.ui.view">
        <field name="name">aidt.format.ruleset.form</field>
        <field name="model">aidt.format.ruleset</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <div class="oe_title">
                        <h1><field name="code" placeholder="66-QD/TW"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="version" placeholder="2025.1"/>
                            <field name="ap_dung"/>
                        </group>
                        <group>
                            <field name="active"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Bộ luật (YAML)" name="spec">
                            <field name="spec_yaml" widget="code" options="{'language': 'yaml'}"/>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="format_ruleset_action" model="ir.actions.act_window">
        <field name="name">Bộ luật thể thức</field>
        <field name="res_model">aidt.format.ruleset</field>
        <field name="view_mode">list,form</field>
        <field name="context">{'active_test': False}</field>
    </record>

    <menuitem id="menu_aidt_format_ruleset"
              name="Bộ luật thể thức"
              parent="base.menu_administration"
              action="format_ruleset_action"
              groups="base.group_system"
              sequence="90"/>

</odoo>
```

- [ ] **Step 7: Viết seed hai bộ luật**

`custom-addons/aidt_format/data/format_ruleset_data.xml` — `noupdate="1"` để bản
nâng cấp không ghi đè chỉnh sửa của quản trị viên:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <record id="ruleset_66_qd_tw" model="aidt.format.ruleset">
        <field name="code">66-QD/TW</field>
        <field name="version">2025.1</field>
        <field name="ap_dung">dang</field>
        <field name="spec_yaml">ruleset: "66-QD/TW"
version: "2025.1"
ap_dung: dang
so_ky_hieu:
  format: "{n}-{type_code}/{org_code}"
  stamp_box_mm: {x: 30, y: 52, w: 60, h: 8}
page:
  size: A4
  margins_mm: {top: [20, 25], bottom: [20, 25], left: [30, 35], right: [15, 20]}
zones:
  tieu_de_dang:
    required: true
    font: "Times New Roman"
    size_pt: [15, 15]
    bold: true
    uppercase: true
    align: center
  so_ky_hieu:
    required: true
    font: "Times New Roman"
    size_pt: [14, 14]
  trich_yeu:
    required: true
    font: "Times New Roman"
    size_pt: [14, 14]
    bold: true
    align: center
  noi_dung:
    font: "Times New Roman"
    size_pt: [14, 15]
    line_spacing: [1.0, 1.5]
    line_spacing_fixed_allowed: false
    first_line_indent_cm: [1.0, 1.27]
    align: [justify]
  noi_nhan:
    required: true
    font: "Times New Roman"
    size_pt: [12, 12]
  chu_ky:
    required: true
    uppercase: true
    align: right
severity_overrides:
  noi_dung.size_pt: warning
  noi_dung.first_line_indent_cm: warning
  noi_dung.line_spacing: warning
  chu_ky.uppercase: warning
  so_ky_hieu.font: warning
</field>
    </record>

    <record id="ruleset_nd_30_2020" model="aidt.format.ruleset">
        <field name="code">ND-30/2020</field>
        <field name="version">2025.1</field>
        <field name="ap_dung">hanh_chinh</field>
        <field name="spec_yaml">ruleset: "ND-30/2020"
version: "2025.1"
ap_dung: hanh_chinh
so_ky_hieu:
  format: "{n}/{type_code}-{org_code}"
  stamp_box_mm: {x: 20, y: 50, w: 60, h: 8}
page:
  size: A4
  margins_mm: {top: [20, 25], bottom: [20, 25], left: [30, 35], right: [15, 20]}
zones:
  quoc_hieu:
    required: true
    font: "Times New Roman"
    size_pt: [12, 13]
    bold: true
    uppercase: true
    align: center
  so_ky_hieu:
    required: true
    font: "Times New Roman"
    size_pt: [13, 13]
  trich_yeu:
    required: true
    font: "Times New Roman"
    size_pt: [14, 14]
    bold: true
    align: center
  noi_dung:
    font: "Times New Roman"
    size_pt: [13, 14]
    line_spacing: [1.0, 1.5]
    line_spacing_fixed_allowed: false
    first_line_indent_cm: [1.0, 1.27]
    align: [justify]
  noi_nhan:
    required: true
    font: "Times New Roman"
    size_pt: [11, 11]
  chu_ky:
    required: true
    uppercase: true
    align: right
severity_overrides:
  noi_dung.size_pt: warning
  noi_dung.first_line_indent_cm: warning
  noi_dung.line_spacing: warning
  chu_ky.uppercase: warning
  so_ky_hieu.font: warning
</field>
    </record>

</data>
</odoo>
```

- [ ] **Step 8: Cập nhật `__manifest__.py`**

```python
{
    'name': 'AIDT Thể thức văn bản',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Engine kiểm tra thể thức văn bản theo bộ luật cấu hình được (D-03/D-07/D-09)',
    'depends': ['base'],
    'external_dependencies': {'python': ['docx', 'yaml']},
    'data': [
        'security/ir.model.access.csv',
        'views/format_ruleset_views.xml',
        'data/format_ruleset_data.xml',
    ],
    'license': 'LGPL-3',
}
```

- [ ] **Step 9: Chạy test, xác nhận pass**

```bash
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -u aidt_format --http-port=8098 \
  --test-enable --stop-after-init --log-level=test 2>&1 | tail -30
```

Expected: toàn bộ test của aidt_format pass, `0 failed, 0 error`. Nếu báo
`Unable to find module docx` thì `python-docx` chưa vào image: dựng lại
`docker compose -f docker-compose.dev.yml build odoo` rồi `up -d`.

- [ ] **Step 10: Commit**

```bash
git add custom-addons/aidt_format
git commit -m "[ADD] aidt_format: model bộ luật thể thức + seed hai chuẩn

Luật là dữ liệu: spec_yaml giữ nguyên YAML, validate bằng engine.schema khi
lưu nên seed đi qua đúng constraint như dữ liệu người dùng nhập. Dùng
base.group_* chứ không phụ thuộc aidt_org, để dùng lại được cho văn bản đến.

Guard 'spec_yaml readonly khi đã có văn bản tham chiếu' (QĐ-8) thuộc đợt 3:
module này không biết model văn bản nào tham chiếu nó."
```

---

### Task 9: `aidt.format.checker` — cửa vào từ Odoo

**Files:**
- Create: `custom-addons/aidt_format/models/format_checker.py`
- Modify: `custom-addons/aidt_format/models/__init__.py`
- Modify: `custom-addons/aidt_format/tests/__init__.py`
- Test: `custom-addons/aidt_format/tests/test_checker.py`

**Interfaces:**
- Consumes: `odoo.addons.aidt_format_engine.parser.{parse_docx, UnreadableDocx}`, `.zones.detect_zones`, `.rules.run_rules`, `.findings.{Finding, ERROR}`, model `aidt.format.ruleset`.
- Produces: `self.env['aidt.format.checker'].check(docx_bytes, ruleset) -> list[dict]` với mỗi dict có đúng bảy khóa `rule_id, severity, zone, location, expected, actual, suggestion`.

Đây là ranh giới của module: `check()` **không ghi bản ghi nào**. Đợt 3 nhận
`list[dict]` này và biến thành `aidt.document.finding`.

- [ ] **Step 1: Viết test (test này phải fail)**

Thêm vào `custom-addons/aidt_format/tests/__init__.py`:

```python
from . import test_checker, test_ruleset
```

`custom-addons/aidt_format/tests/test_checker.py`:

```python
import pathlib
import sys

from odoo.tests.common import TransactionCase

# Fixture nằm trong aidt_format_engine/tests/ — thư mục cố ý không có
# __init__.py để pytest trên host không nạp Odoo, nên nó KHÔNG import được
# qua odoo.addons. Nạp bằng đường dẫn tệp.
# parents: [0]=tests, [1]=aidt_format, [2]=custom-addons
_FIXTURES_PATH = str(
    pathlib.Path(__file__).resolve().parents[2]
    / 'aidt_format_engine' / 'tests' / 'fixtures.py')


def _load_fixtures():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'aidt_format_fixtures', _FIXTURES_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestFormatChecker(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fixtures = _load_fixtures()
        cls.checker = cls.env['aidt.format.checker']
        cls.ruleset_dang = cls.env.ref('aidt_format.ruleset_66_qd_tw')
        cls.ruleset_hc = cls.env.ref('aidt_format.ruleset_nd_30_2020')

    def test_file_dat_tra_ve_danh_sach_rong(self):
        self.assertEqual(
            self.checker.check(self.fixtures.chuan_66(), self.ruleset_dang), [])

    def test_file_hanh_chinh_dat_theo_bo_luat_hanh_chinh(self):
        findings = self.checker.check(
            self.fixtures.chuan_nd30(), self.ruleset_hc)
        chan = [f for f in findings if f['severity'] == 'error']
        self.assertEqual(chan, [], 'không được có lỗi chặn: %s' % chan)

    def test_tra_ve_list_dict_dung_bay_khoa(self):
        findings = self.checker.check(
            self.fixtures.sai_le_trang(), self.ruleset_dang)
        self.assertTrue(findings)
        for finding in findings:
            self.assertIsInstance(finding, dict)
            self.assertEqual(
                set(finding),
                {'rule_id', 'severity', 'zone', 'location', 'expected',
                 'actual', 'suggestion'})

    def test_khong_ghi_ban_ghi_nao(self):
        """Ranh giới của module: check() là hàm thuần, không tạo bản ghi."""
        before = self.env['ir.attachment'].search_count([])
        self.checker.check(self.fixtures.sai_font(), self.ruleset_dang)
        self.assertEqual(self.env['ir.attachment'].search_count([]), before)

    def test_file_hong_tra_ve_finding_khong_no_traceback(self):
        findings = self.checker.check(
            self.fixtures.hong(), self.ruleset_dang)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['rule_id'], 'file.unreadable')
        self.assertEqual(findings[0]['severity'], 'error')

    def test_sai_font_bat_duoc_qua_tang_Odoo(self):
        findings = self.checker.check(
            self.fixtures.sai_font(), self.ruleset_dang)
        ids = {f['rule_id'] for f in findings}
        self.assertIn('noi_dung.font', ids)

    def test_severity_overrides_cua_seed_co_hieu_luc(self):
        """Seed hạ noi_dung.size_pt xuống warning; font vẫn là error."""
        findings = self.checker.check(
            self.fixtures.sai_font(), self.ruleset_dang)
        font = [f for f in findings if f['rule_id'] == 'noi_dung.font'][0]
        self.assertEqual(font['severity'], 'error')

    def test_thieu_noi_nhan_la_loi_chan(self):
        findings = self.checker.check(
            self.fixtures.thieu_noi_nhan(), self.ruleset_dang)
        thieu = [f for f in findings if f['rule_id'] == 'noi_nhan.required']
        self.assertEqual(len(thieu), 1)
        self.assertEqual(thieu[0]['severity'], 'error')

    def test_bo_luat_lech_he_quy_chuan_chi_canh_bao(self):
        findings = self.checker.check(
            self.fixtures.chuan_nd30(), self.ruleset_dang)
        lech = [f for f in findings if f['rule_id'] == 'file.wrong_standard']
        self.assertEqual(len(lech), 1)
        self.assertEqual(lech[0]['severity'], 'warning')
```

- [ ] **Step 2: Chạy test, xác nhận fail**

```bash
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -u aidt_format --http-port=8098 \
  --test-enable --stop-after-init --log-level=test 2>&1 | tail -30
```

Expected: FAIL — `KeyError: 'aidt.format.checker'`.

- [ ] **Step 3: Viết `models/format_checker.py`**

```python
import logging
import time

from odoo import api, models

from odoo.addons.aidt_format_engine.findings import ERROR, Finding
from odoo.addons.aidt_format_engine.parser import UnreadableDocx, parse_docx
from odoo.addons.aidt_format_engine.rules import run_rules
from odoo.addons.aidt_format_engine.zones import detect_zones

_logger = logging.getLogger(__name__)


class AidtFormatChecker(models.AbstractModel):
    _name = 'aidt.format.checker'
    _description = 'Cửa vào kiểm tra thể thức'

    @api.model
    def check(self, docx_bytes, ruleset):
        """Kiểm thể thức một file .docx theo một bộ luật.

        Trả list[dict], mỗi dict là một phát hiện. KHÔNG ghi bản ghi nào —
        việc lưu thành aidt.document.finding thuộc module nghiệp vụ, nhờ vậy
        engine không cần biết finding được lưu ở đâu.
        """
        spec = ruleset.spec()
        started = time.monotonic()
        try:
            doc = parse_docx(docx_bytes)
        except UnreadableDocx as exc:
            # Không cho traceback nổ ra: file sai định dạng là chuyện thường
            # (.doc cũ, PDF đổi tên), người dùng cần thấy lý do trên form.
            return [Finding(
                rule_id='file.unreadable', severity=ERROR, zone='',
                location='Toàn tệp',
                expected='Tệp .docx đọc được',
                actual=str(exc),
                suggestion='Mở bằng Word và lưu lại ở định dạng .docx '
                           '(không phải .doc hay PDF)').as_dict()]
        detect_zones(doc)
        findings = run_rules(doc, spec)
        # QĐ-5: engine chạy đồng bộ, nên phải đo được. Vượt ngưỡng thì tách async.
        _logger.info(
            'Kiểm thể thức %s: %d đoạn, %d phát hiện, %.0fms',
            ruleset.display_name, len(doc.paras), len(findings),
            (time.monotonic() - started) * 1000)
        return [finding.as_dict() for finding in findings]
```

- [ ] **Step 4: Cập nhật `models/__init__.py`**

```python
from . import format_checker, format_ruleset
```

- [ ] **Step 5: Chạy toàn bộ test, xác nhận pass**

Test model, trong container:

```bash
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -u aidt_format --http-port=8098 \
  --test-enable --stop-after-init --log-level=test 2>&1 | tail -30
```

Expected: toàn bộ test của aidt_format pass, `0 failed, 0 error`.

Test engine, trên host:

```bash
PYTHONPATH=custom-addons python3 -m pytest \
  custom-addons/aidt_format_engine/tests -v
```

Expected: toàn bộ pass.

- [ ] **Step 6: Xác nhận `engine/` không hề import odoo**

```bash
grep -rn "import odoo\|from odoo" custom-addons/aidt_format_engine/ ; echo "rc=$? (1 = sạch)"
```

Expected: `rc=1` — không có dòng nào. Đây là bất biến của module; hỏng nó là
test engine trên host chết.

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_format
git commit -m "[IMP] aidt_format: cửa vào aidt.format.checker

check() trả list[dict] và không ghi bản ghi nào — đợt 3 biến kết quả thành
aidt.document.finding. Ghi log thời gian mỗi lần kiểm để theo dõi QĐ-5
(chạy đồng bộ, vượt ngưỡng thì tách async). File hỏng trả finding
file.unreadable thay vì để traceback nổ ra."
```

---

## Xong đợt 1 — kiểm lại trước khi sang đợt 2

- [ ] `PYTHONPATH=custom-addons python3 -m pytest custom-addons/aidt_format_engine/tests -v` → all pass
- [ ] `docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -u aidt_format --http-port=8098 --test-enable --stop-after-init --log-level=test` → 0 failed, 0 error
- [ ] `grep -rn "import odoo\|from odoo" custom-addons/aidt_format_engine/` → không có kết quả
- [ ] `test custom-addons/aidt_format_engine/tests/__init__.py` không tồn tại
- [ ] Vào Settings → Bộ luật thể thức, thấy hai bản ghi, sửa `spec_yaml` thành YAML sai thì bị chặn kèm đường dẫn khóa sai
- [ ] `git log --oneline` có chín commit của đợt này

Đợt 2 (`aidt_sign`) sẽ có kế hoạch riêng, viết sau khi đợt 1 xong. Việc đầu tiên
của đợt 2 là `test_two_signatures.py` — nó trả lời rủi ro cao nhất của cả thiết
kế (DocMDP + annotation) trước khi có dòng nghiệp vụ nào được viết.
