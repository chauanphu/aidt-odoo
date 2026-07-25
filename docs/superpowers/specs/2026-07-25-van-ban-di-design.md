# Thiết kế — Luồng nghiệp vụ văn bản đi

Ngày: 2026-07-25
Nhánh: `cuong-f-documents-integration`
Nền tảng đã có: Nhóm 1 (`aidt_org`, `aidt_dms`)

## 1. Mục tiêu và phạm vi

Dựng luồng nghiệp vụ văn bản đi trọn vẹn từ soạn thảo đến lưu trữ, trên nền
tổ chức — phân quyền — kho tài liệu đã hoàn thành ở Nhóm 1.

Năm khâu trong phạm vi:

1. Soạn thảo văn bản (sinh bản thảo `.docx` từ mẫu có trường động)
2. Duyệt thể thức (engine kiểm tự động, đóng vai cổng chặn)
3. Trình ký (đường trình ký nhiều cấp, trả lại kèm lý do)
4. Đăng ký văn bản đi (cấp số, cấp ngày ban hành)
5. Ký và ban hành (ký số cá nhân, đóng số, ký số cơ quan, phát hành)

Tính năng MVP được phủ: D-01, D-02, D-03, D-07, D-08, D-09, D-13, D-14, D-15,
V-01, V-02, V-05; kế thừa nguyên vẹn N-04, N-05, N-07, N-10, V-04, V-13 từ Nhóm 1.

### Ngoài phạm vi

| Không làm | Lý do |
|---|---|
| Tích hợp ONLYOFFICE Document Server | Vòng sau; thiết kế chừa sẵn `action_edit_online()` và `aidt.doc.converter.onlyoffice` |
| Tích hợp CA thật (VNPT-CA, Viettel-CA, USB token) | Cần hợp đồng và sandbox; thiết kế chừa sẵn interface `aidt.sign.provider` |
| Soạn thảo trực tuyến (D-05) | P1; engine thể thức đã nhận cấu trúc trung gian nên cắm vào được không đập lại |
| Kiểm chính tả tiếng Việt (D-06) | Cần service AI riêng, thuộc nhóm khác |
| Auto-fix finding | Vòng sau; `Finding.expected` đã có sẵn để ánh xạ |
| Xử lý bất đồng bộ qua OCA `queue_job` | Chạy đồng bộ trước, có đo thời gian; xem quyết định QĐ-5 |
| Văn bản đến | Model dùng chung đã chừa `direction`, nhưng nghiệp vụ để vòng riêng |
| Sổ văn bản đi dạng model riêng | List view + bộ lọc là đủ; không dựng model cho một báo cáo |

## 2. Các quyết định đã chốt

| Mã | Quyết định | Lý do |
|---|---|---|
| QĐ-1 | Mở rộng `aidt.document` thay vì tạo model riêng `vanban.di` | Kế thừa nguyên vẹn `ir.rule` độ mật + phạm vi (N-04/N-05) và cầu nối `dms.directory` đã có. Model riêng buộc phải nhân bản cả hai, và tìm kiếm hợp nhất Đến+Đi sẽ phải union hai model |
| QĐ-2 | Bản thảo là file `.docx`, sinh từ mẫu có trường động; sửa bằng cách tải xuống/tải lên | Giữ thói quen soạn Word của văn thư. ONLYOFFICE sẽ thay khâu sửa tại chỗ ở vòng sau, không đổi luồng |
| QĐ-3 | Số/ký hiệu cấp **sau** khi ký, lúc văn thư đăng ký | Đúng NĐ 30/2020 Điều 18. Văn bản bị trả lại không chiếm số nên sổ không nhảy số |
| QĐ-4 | Đường trình ký sinh từ cấu hình theo đơn vị + loại VB, mỗi bước một `mail.activity` | Thực tế có ủy quyền, ký thay, ký thừa lệnh — đường cứng theo cây `hr.department` không mô hình hóa nổi |
| QĐ-5 | Engine thể thức chạy **đồng bộ**, không kéo OCA `queue_job` vào | Parse một `.docx` vài chục trang là dưới một giây. Có đo thời gian; vượt ngưỡng thì tách async sau |
| QĐ-6 | DOCX→PDF bằng LibreOffice headless, bọc sau interface `aidt.doc.converter` | Cần PDF để ký PAdES. ONLYOFFICE Conversion API cắm vào cùng interface ở vòng sau |
| QĐ-7 | Ký số: interface `aidt.sign.provider`, hiện thực đầu tiên ký PAdES thật bằng chứng thư `.p12` | Test được toàn bộ luồng offline bằng cert tự ký, không chờ CA. VNPT/Viettel/USB token cắm sau đúng interface |
| QĐ-8 | Bộ luật thể thức là bản ghi `aidt.format.ruleset` giữ nguyên YAML trong một trường | Đổi quy định không cần deploy. Bản ghi cũ không sửa — đổi luật là tạo version mới, version cũ archive, văn bản cũ truy vết được đã check bằng luật nào |
| QĐ-9 | Duyệt thể thức là **cổng chặn**, không phải state | Máy đo được thì không cần người phê duyệt. Lớp soát con người (thứ máy không đo được) nằm trong đường trình ký sẵn có. Thêm state riêng là bắt người làm lại việc máy vừa làm |
| QĐ-10 | Chuyển `doc_type` từ `Selection` sang `doc_type_id → aidt.document.type` | `Selection` không chở được ký hiệu loại VB, hệ quy chuẩn, mẫu số ký hiệu — cả ba đều cần để dựng số. Cũng là bước đầu của N-13 |

## 3. Kiến trúc — ba module

Nguyên tắc phân chia: **service thuần không biết nghiệp vụ**.

```
custom-addons/
  aidt_format/          Engine thể thức. Không biết "văn bản đi" là gì.
    engine/             ← Python thuần, KHÔNG import odoo
      parser.py         docx → IntermediateDoc
      resolver.py       flatten kế thừa định dạng → giá trị hiệu lực
      zones.py          gán mỗi đoạn vào một vùng thể thức
      rules.py          IntermediateDoc + ruleset → list[Finding]
      findings.py       @dataclass Finding
      schema.py         validate cấu trúc ruleset
      tests/            ← KHÔNG có __init__.py, chạy bằng pytest trên host
    models/
      format_ruleset.py aidt.format.ruleset
      format_checker.py aidt.format.checker   (AbstractModel, cửa vào từ Odoo)
    data/               seed hai ruleset khởi đầu
    tests/              TransactionCase, chạy bằng odoo-bin trong container

  aidt_sign/            Chuyển đổi + ký số. Không biết "văn bản đi" là gì.
    models/
      converter.py      aidt.doc.converter    (abstract) + aidt.doc.converter.soffice
      sign_provider.py  aidt.sign.provider    (abstract) + aidt.sign.provider.p12
    tests/              + fixtures/test-ca.p12

  aidt_vanban_di/       Nghiệp vụ. Gọi hai module trên qua interface.
    depends: aidt_org, aidt_dms, aidt_format, aidt_sign
```

`addons_path` là `addons, extra-addons/dms, custom-addons` nên cả ba vào `custom-addons/`.

**Vì sao `engine/` là Python thuần, không phải model Odoo.** Parser và resolver là
phần khó nhất và cần nhiều test nhất (chuỗi kế thừa font sáu tầng, twip,
half-point, `lineRule`). Tách khỏi ORM thì test chạy trên fixture `.docx` không
cần DB, không cần khởi động Odoo. Tầng model Odoo chỉ làm ba việc: đọc
`spec_yaml`, gọi engine, trả `list[dict]` cho phía gọi.

Ranh giới phải giữ: `aidt.format.checker.check(docx_bytes, ruleset) → list[dict]`
**không ghi bản ghi nào**. Việc biến kết quả thành `aidt.document.finding` là của
`aidt_vanban_di` — nhờ vậy engine không cần biết finding được lưu ở model nào, và
văn bản đến hay editor online về sau dùng lại được cùng cửa vào đó.

**Vì sao tách `aidt_format` khỏi `aidt_vanban_di`.** Engine sẽ còn dùng cho văn
bản đến và cho soạn thảo trực tuyến (D-05). Nó không được biết gì về `state` hay
đường trình ký.

**Vì sao `aidt_sign` gộp cả converter và provider.** Cả hai là "biến file thành
PDF đã ký", cùng chuỗi phụ thuộc hạ tầng ngoài (`soffice`, chứng thư), cùng chỗ
để về sau cắm ONLYOFFICE và VNPT-CA. Tách thành hai module chỉ để có hai module.

### Phụ thuộc mới

| Nơi | Thêm gì | Ghi chú |
|---|---|---|
| `requirements.txt` | `python-docx` | Chưa có |
| `requirements.txt` | `pyhanko` | Chưa có |
| `Dockerfile` | `libreoffice-writer` | `--no-install-recommends`, khoảng 400–500MB |
| — | `PyYAML` 6.0.1 | Đã có |
| — | `PyPDF2` 2.12.1 | Đã có, thiết kế không dùng đến (xem mục 7) |

Dọn kèm: xóa `addons/dms_libreoffice_preview/` — chỉ còn `.pyc` mồ côi, mã nguồn
đã bị xóa từ trước.

## 4. Vòng đời

```
                 ┌──── action_run_format_check()  (lặp tùy ý, state không nhúc nhích)
                 ▼
   draft ══[GATE]══► to_sign ──► signed ──► registered ──► issued ──► archived
     ▲                  │
     └── action_reject(reason) ─┘

   GATE mở khi:  không còn finding severity='error'
             VÀ  sha256(bản thảo hiện tại) == format_checked_hash
```

Sáu state, mỗi state là một sự kiện nghiệp vụ có người chịu trách nhiệm. "Đạt
thể thức" không có mặt vì nó là **điều kiện tiên quyết** của sự kiện "trình",
không phải một sự kiện.

Điều kiện thứ hai của gate là điểm tinh tế nhất: không có nó, người dùng check
bản A đạt rồi tải bản B lên trình ký, kết quả check cũ dán lên file mới. Cụ thể
hóa bằng `format_ok` là compute **không store**, so `format_checked_hash` với
hash của `draft_file_id` hiện hành — tải file mới lên là gate tự đóng, không cần
trigger nào.

| Chuyển | Ai | Điều kiện |
|---|---|---|
| `draft → to_sign` | người soạn | gate mở; sinh `approval_ids`; snapshot `gate_evidence`; khóa `draft_file_id` |
| trong `to_sign` | từng cấp duyệt | duyệt bước mình → activity cho bước sau |
| `to_sign → draft` | bất kỳ cấp duyệt | trả lại kèm lý do (D-14) |
| `to_sign → signed` | `signer_id` | mọi `approval_ids` đã `approved` |
| `signed → registered` | Văn thư | cấp số + ngày; đóng số lên PDF; ký số cơ quan |
| `registered → issued` | Văn thư | phát hành tới `recipient_ids` |
| `issued → archived` | Văn thư | — |

## 5. Mô hình dữ liệu

### Mở rộng `aidt.document`

```python
# aidt_vanban_di/models/aidt_document.py
state = fields.Selection(selection_add=[
    ('to_sign', 'Trình ký'), ('signed', 'Đã ký'),
    ('registered', 'Đã đăng ký'),
    ('issued',), ('archived',),        # khóa cũ làm mốc để chèn đúng vị trí
], ondelete={'to_sign': 'set default', 'signed': 'set default',
             'registered': 'set default'})

direction        = Selection([('di','Đi'), ('den','Đến')], default='di', index=True)
doc_type_id      = Many2one('aidt.document.type', required=True)
urgency          = Selection([('thuong','Thường'), ('khan','Khẩn'),
                              ('thuong_khan','Thượng khẩn'), ('hoa_toc','Hỏa tốc')],
                             default='thuong')
recipient_ids    = Many2many('res.partner', string='Nơi nhận')

# soạn thảo
template_id      = Many2one('aidt.document.template')
draft_file_id    = Many2one('dms.file', string='Bản thảo')

# gate thể thức
ruleset_id       = Many2one('aidt.format.ruleset', compute='_compute_ruleset_id',
                            store=True, readonly=False)
finding_ids      = One2many('aidt.document.finding', 'document_id')
format_checked_hash = Char(readonly=True)
format_check_date   = Datetime(readonly=True)
format_ok        = Boolean(compute='_compute_format_ok')       # KHÔNG store
gate_evidence    = Json(readonly=True)

# trình ký
approval_ids     = One2many('aidt.document.approval', 'document_id')
signer_id        = Many2one('res.users', string='Người ký')

# ký & ban hành
signed_file_id   = Many2one('dms.file', string='Bản đã ký')
issued_file_id   = Many2one('dms.file', string='Bản ban hành')
signed_by_id     = Many2one('res.users', readonly=True)
signed_date      = Datetime(readonly=True)
```

`ruleset_id` compute: chọn `aidt.format.ruleset` đang `active` có `ap_dung` khớp
`doc_type_id.standard`, `version` cao nhất. Khai `store=True, readonly=False` để
admin ghi đè được cho trường hợp ngoại lệ, và để văn bản cũ giữ nguyên ruleset đã
dùng khi có version mới ra.

### Sửa đổi chạm vào Nhóm 1

**QĐ-10 — `doc_type` thành `doc_type_id`.** `aidt_org` hiện khai `doc_type` là
`Selection` bốn giá trị cứng. Luồng văn bản đi cần loại VB mang theo dữ liệu:
ký hiệu để dựng số, hệ quy chuẩn để chọn ruleset, mẫu số ký hiệu — vì hai chuẩn
đánh số khác thứ tự:

```
66-QĐ/TW      123-CV/TU        số - ký hiệu loại / ký hiệu cơ quan
NĐ 30/2020    123/CV-VPTU      số / ký hiệu loại - ký hiệu cơ quan
```

Việc phải làm: bỏ `Selection doc_type` khỏi `aidt_org/models/aidt_document.py`,
bỏ khỏi `views/aidt_document_views.xml`, thêm `doc_type_id` trong
`aidt_vanban_di`, và một migration script ánh xạ bốn giá trị cũ
(`cong_van, bao_cao, ke_hoach, quyet_dinh`) sang bản ghi
`aidt.document.type` tương ứng. `aidt_org_demo/data/org_documents.xml` cũng phải
sửa theo.

**`doc_code` trên `hr.department`.** Cần ký hiệu cơ quan (`TU`, `VPTU`) để dựng
`{org_code}` trong số ký hiệu. Thêm trong `aidt_vanban_di` vì hiện chỉ văn bản đi
dùng.

**Chặn sửa nội dung sau khi rời `draft`.** Rule `rule_aidt_document_scope_write`
hiện cho Chuyên viên ghi mọi văn bản trong đơn vị mình **không phân biệt state**
— nghĩa là sửa được cả văn bản đã ban hành. Bổ sung `write()` guard: các trường
nội dung/thể thức (`name, doc_type_id, secrecy, draft_file_id, template_id,
recipient_ids, urgency, signer_id`) chỉ ghi được khi `state == 'draft'`. Ngoài
`draft`, chỉ các action nghiệp vụ được đổi trường của riêng chúng qua `sudo()`.

### Model mới

| Model | Module | Trường chính |
|---|---|---|
| `aidt.document.type` | `aidt_vanban_di` | `name, code` (`CV`,`BC`,`KH`,`QĐ`), `standard` (`dang`\|`hanh_chinh`), `active` |
| `aidt.document.template` | `aidt_vanban_di` | `name, doc_type_id, docx_file` (Binary), `field_map` (Json), `version, active` |
| `aidt.document.finding` | `aidt_vanban_di` | `document_id, rule_id, severity, zone, zone_confidence, location, expected, actual, suggestion, waived, waive_reason` |
| `aidt.approval.route` | `aidt_vanban_di` | `name, department_id, doc_type_id, secrecy_max, sequence, active, step_ids` |
| `aidt.approval.route.step` | `aidt_vanban_di` | `route_id, sequence, name, approver_type, approver_id` |
| `aidt.document.approval` | `aidt_vanban_di` | `document_id, sequence, name, approver_id, state, note, date` |
| `aidt.format.ruleset` | `aidt_format` | `code, version, ap_dung, spec_yaml, active`; unique(`code`,`version`) |

`approver_type` gồm **hai** giá trị: `user` (người cụ thể) và `dept_manager`
(`manager_id` của đơn vị soạn). Cố ý không có `group`: `mail.activity` chỉ nhận
một `user_id`, nên "bất kỳ ai trong nhóm" sẽ buộc phải chọn bừa một người để giao
activity — mơ hồ mà không thêm khả năng gì, vì người soạn đã sửa được người duyệt
trước khi trình.

`secrecy_max` là `Selection` cùng bốn giá trị với `aidt.document.secrecy`, so sánh
qua cùng bảng ánh xạ `_SECRECY_LEVEL` mà `aidt_org` đã dùng — không khai lại số.

`spec_yaml` chuyển readonly khi ruleset đã được văn bản nào tham chiếu, thực thi
QĐ-8: đổi luật là tạo version mới rồi archive version cũ, không sửa tại chỗ, để
`gate_evidence` của văn bản cũ còn đối chiếu được với đúng bộ luật ngày đó.

## 6. Engine thể thức

Bốn tầng theo `docs/engine-the-thuc.md`: Parser → Resolver → Zone detector →
Rule engine.

### Hợp đồng dữ liệu

Mọi tầng sau tầng 2 chỉ thấy cấu trúc này, không đụng XML:

```python
@dataclass
class EffFormat:                    # định dạng hiệu lực, đã flatten
    font: str; size_pt: float; bold: bool; italic: bool
    align: str                      # left|center|right|justify
    line_spacing: float | None      # đã quy về "số lần dòng"
    line_spacing_fixed: bool        # True nếu lineRule là exact/atLeast
    first_line_indent_cm: float | None

@dataclass
class Para:
    index: int                      # số đoạn, 0-based; KHÔNG có số trang —
                                    # python-docx không phân trang được, muốn
                                    # biết trang phải render, để vòng sau
    text: str; style_name: str | None
    fmt: EffFormat                  # hợp nhất từ các run, lấy theo run dài nhất
    runs_conflict: bool             # các run trong đoạn lệch font/cỡ nhau
    zone: str | None                # tầng 3 điền
    zone_confidence: str | None     # 'style' | 'heuristic'

@dataclass
class PageSetup:
    width_mm: float; height_mm: float
    margin_mm: dict                 # top/bottom/left/right

@dataclass
class IntermediateDoc:
    pages: PageSetup; paras: list[Para]
    standard_hint: str | None       # 'dang' | 'hanh_chinh'

@dataclass
class Finding:
    rule_id: str                    # "noi_dung.line_spacing"
    severity: str                   # error | warning
    zone: str; location: str        # "Đoạn 14" | "Thiết lập trang" | "Toàn văn bản"
    expected: str; actual: str; suggestion: str
```

### Tầng 2 — Resolver, chỗ dễ sai nhất

Ba việc bắt buộc làm đúng:

1. **Chuỗi kế thừa** font/cỡ theo thứ tự `run.rPr → character style →
   paragraph style → chuỗi base_style → docDefaults → theme`. `python-docx`
   không cho đọc `docDefaults` và `theme1.xml`, phải mở qua
   `document.part.package` và đọc XML tay. Có cache theo `style_id` để không leo
   lại chuỗi cho mỗi run.
2. **Đơn vị**: cỡ chữ half-point (`28` = 14pt); lề twip (`567` twip = 1cm =
   10mm); dãn dòng `w:spacing` phân biệt `lineRule="auto"` (`240` = 1.0,
   `360` = 1.5) với `lineRule="exact"`/`"atLeast"` (twip tuyệt đối, quy về số lần
   dòng bằng cách chia cỡ chữ hiệu lực và đặt `line_spacing_fixed=True` vì rule
   có thể muốn cấm).
3. **`runs_conflict`**: một đoạn có các run khác cỡ/khác font thì không được
   lặng lẽ lấy run đầu — đánh dấu và sinh finding riêng, vì đó chính là lỗi văn
   thư hay gặp khi dán từ nguồn khác vào.

### Tầng 3 — Zone detector, hai đường

Ưu tiên **tra tên style**: file sinh từ mẫu của hệ thống mang style đặt tên
`VB_TieuDeDang`, `VB_QuocHieu`, `VB_SoKyHieu`, `VB_TrichYeu`, `VB_NoiDung`,
`VB_NoiNhan`, `VB_ChuKy` → chính xác tuyệt đối, `zone_confidence='style'`.

Không có style thì rơi về **heuristic** vị trí + regex:

| Vùng | Dấu hiệu |
|---|---|
| `tieu_de_dang` | đoạn đầu, căn giữa/phải, in hoa, khớp `ĐẢNG CỘNG SẢN VIỆT NAM` |
| `quoc_hieu` | tương tự, khớp `CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM` |
| `so_ky_hieu` | khớp `Số\s*[:：]?\s*\d+[-/][A-ZĐ]+` |
| `trich_yeu` | khớp `V/v\s+…` hoặc đoạn in đậm ngay dưới tên loại |
| `noi_nhan` | khớp `Nơi nhận\s*:` |
| `chu_ky` | khối căn phải cuối văn bản có chức danh in hoa |
| `noi_dung` | còn lại |

`standard_hint` suy ra từ việc gặp `tieu_de_dang` hay `quoc_hieu` — dùng để cảnh
báo khi ruleset được chọn không khớp hệ quy chuẩn của file.

Zone chỉ đoán được (`zone_confidence='heuristic'`) thì mọi finding trong vùng đó
**tự hạ xuống `warning`**, tránh chặn oan người soạn tay ngoài mẫu.

### Tầng 4 — Rule engine

Vòng lặp generic, không có `if` nào cho từng quy định. Với mỗi zone, lấy rule
tương ứng, so giá trị hiệu lực với khoảng cho phép, sinh `Finding`.

Ruleset YAML mở rộng hai khóa so với ví dụ trong `docs/engine-the-thuc.md`:

```yaml
ruleset: "66-QD/TW"
version: "2025.1"
ap_dung: dang                                  # dang | hanh_chinh, khớp doc_type.standard
so_ky_hieu:
  format: "{n}-{type_code}/{org_code}"       # 123-CV/TU
  stamp_box_mm: {x: 30, y: 52, w: 60, h: 8}  # nơi đóng số/ngày lên PDF khi đăng ký
page:
  size: A4
  margins_mm: {top: [20,25], bottom: [20,25], left: [30,35], right: [15,20]}
zones:
  tieu_de_dang:
    required: true
    font: "Times New Roman"
    size_pt: [15, 15]
    bold: true
    uppercase: true
    align: center
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
    size_pt: [12, 12]
  chu_ky:
    required: true
    uppercase: true
severity_overrides:
  noi_dung.size_pt: warning
  tieu_de_dang.required: error
```

`format` và `stamp_box_mm` là thuộc tính **của chuẩn thể thức**, nên nằm đúng chỗ
trong ruleset chứ không trong code.

Vòng đầu phủ 7 vùng, khoảng 25 kiểm tra — nhưng tất cả là dữ liệu trong YAML nên
con số này không phải cam kết trong code. Chọn theo lời khuyên trong
`engine-the-thuc.md`: các rule hay sai nhất và dễ đo nhất trước.

Hai ruleset được seed: `66-QD/TW` version `2025.1` và `ND-30/2020` version
`2025.1`.

## 7. Trình ký, ký, cấp số, ban hành

### Chọn route

Cho một văn bản, chấm điểm từng `aidt.approval.route` đang `active`:

```
loại bỏ  nếu doc_type_id đã đặt và khác
         hoặc secrecy_max < doc.secrecy_level
         hoặc department_id không phải chính nó / tổ tiên của đơn vị soạn
điểm     khớp đơn vị chính xác 100, tổ tiên 100 − khoảng_cách × 10
       + doc_type_id có đặt: +5      (route cụ thể thắng route bao trùm)
tie      sequence, rồi id
không route nào khớp → UserError nêu rõ thiếu cấu hình cho đơn vị/loại nào
```

Người soạn thấy trước danh sách bước duyệt đã giải ra và **sửa được người duyệt**
trước khi bấm trình — thực tế có ủy quyền, ký thay, người đi công tác.

### `action_submit()`

Năm việc trong một transaction: kiểm gate → giải route thành `approval_ids` →
ghi `gate_evidence` → `state='to_sign'` → tạo `mail.activity` cho bước 1, đồng
thời khóa `draft_file_id` readonly.

`gate_evidence` là JSON **đóng băng**, không phải liên kết động:

```json
{"ruleset": "66-QD/TW", "version": "2025.1",
 "file_hash": "sha256:…", "checked_at": "2026-07-25T10:24:00",
 "findings": [{"rule_id": "noi_dung.line_spacing", "severity": "warning"}],
 "waived": [{"rule_id": "…", "by": 7, "reason": "…"}]}
```

Vì sao đóng băng: `finding_ids` sẽ bị xóa và ghi lại ở lần check sau, còn câu hỏi
cần trả lời ba năm nữa là "văn bản này qua gate với bộ luật nào, còn cảnh báo gì,
ai cho qua" (N-07, D-09).

### Duyệt và trả lại

`action_approve()` đóng bước hiện tại, mở bước sau, tạo activity.
`action_reject(reason)` đưa về `draft`, reset mọi bước `pending`, ghi lý do vào
chatter và tạo activity cho người soạn (D-14).

Ở `to_sign`, tab findings vẫn hiện — finding mức `warning` phải đến được mắt
Trưởng phòng/Chánh VP, không chết trong `draft`.

### Ký, đóng số, ký cơ quan

NĐ 30/2020 quy định số/ngày cấp **sau** khi người có thẩm quyền ký, và với văn
bản điện tử thì văn thư cấp số/ngày rồi **ký số của cơ quan** (con dấu điện tử).
Nghĩa là bản ban hành phải mang **hai chữ ký**, với số/ngày được thêm vào **giữa**
hai chữ ký. Bình thường sửa PDF sau khi ký sẽ làm chữ ký thứ nhất mất hiệu lực.

Cách giải — dùng đúng cơ chế PAdES có sẵn cho việc này:

```
action_sign()              (signer_id, khi mọi approval đã approved)
  draft_file .docx
    → aidt.doc.converter.to_pdf()                  soffice --headless
    → aidt.sign.provider.sign_pdf(certify=True,
          docmdp=ANNOTATE)                         ← cho phép thêm annotation về sau
    → dms.file 'da-ky.pdf' → signed_file_id        chữ ký 1: cá nhân người ký
  state = 'signed'                                 PDF này CHƯA có số/ngày

action_register()          (Văn thư)
  cấp số qua ir.sequence → reference, date
    → pyhanko stamp số/ngày vào stamp_box_mm của ruleset,
      dạng annotation, incremental update           ← chữ ký 1 vẫn hợp lệ
    → aidt.sign.provider.sign_pdf(chứng thư cơ quan)  chữ ký 2: con dấu cơ quan
    → dms.file 'ban-hanh.pdf' → issued_file_id
  state = 'registered'
```

Điểm khiến nó chạy được: chữ ký thứ nhất ký với DocMDP mức `ANNOTATE`, tức là
**tự nó tuyên bố** cho phép thêm annotation về sau mà không coi là giả mạo.
Số/ngày đóng đúng khung `stamp_box_mm` khai trong ruleset — không phải dò text
trong PDF (đó là lý do không cần `PyPDF2`), vì bản thân quy định thể thức đã chỉ
rõ số ký hiệu nằm ở đâu trên trang.

**Rủi ro kỹ thuật và đường lùi.** Đây là phần duy nhất trong thiết kế có rủi ro
thật: hành vi của DocMDP + annotation khác nhau giữa các trình kiểm tra chữ ký.
`aidt_sign/tests/test_two_signatures.py` xác minh cả hai chữ ký còn hợp lệ sau
khi stamp. Test không đạt thì đường lùi là giữ hai file — `da-ky.pdf` (chữ ký cá
nhân, chưa số) làm bằng chứng người ký đã ký nội dung nào, và `ban-hanh.pdf` sinh
lại từ DOCX đã chèn số rồi chỉ ký cơ quan. Đường lùi **kém hơn về pháp lý** vì
bản ban hành không mang chữ ký số của người ký, nên chỉ dùng khi buộc phải, và
phải báo lại thay vì âm thầm lùi.

### Cấp số

`ir.sequence` với `implementation='no_gap'` và `use_date_range=True`. `no_gap`
khóa dòng sequence bằng `SELECT FOR UPDATE` nên hai văn thư cấp số đồng thời bị
xếp hàng, và transaction rollback thì số được trả lại — đúng yêu cầu "sổ không
được nhảy số".

Sổ tách theo độ mật: mã sequence là `aidt.vanban.di.{thuong|mat}.{type_code}`,
tạo theo yêu cầu bằng `sudo()`. Văn bản Mật trở lên vào sổ riêng; rule độ mật của
Nhóm 1 vốn đã che luôn sự tồn tại của chúng với người không đủ clearance.

Số ký hiệu dựng từ `ruleset.so_ky_hieu.format` với ba biến `{n}` (số thứ tự),
`{type_code}` (`doc_type_id.code`), `{org_code}` (`department_id.doc_code`).

### Interface cho vòng sau

```python
aidt.doc.converter        (AbstractModel)
  to_pdf(docx_bytes) → pdf_bytes
    .soffice     soffice --headless --convert-to pdf     ← vòng này
    .onlyoffice  POST /ConvertService.ashx               ← vòng sau

aidt.sign.provider        (AbstractModel)
  sign_pdf(pdf_bytes, signer, reason, certify=False, docmdp=None) → pdf_bytes
  verify(pdf_bytes) → info
    .p12    pyhanko + chứng thư cục bộ                   ← vòng này
    .vnpt   API nhà cung cấp CKS                         ← vòng sau
    .token  ký phía client bằng USB token                ← vòng sau

aidt.document.action_edit_online()
  vòng này raise UserError "chưa cấu hình Document Server"
```

## 8. Xử lý lỗi

Nguyên tắc: **hỏng thì không đổi state, và không để lại file rác**. `dms.file`
chỉ tạo sau khi đã có bytes trong tay.

| Tình huống | Xử lý |
|---|---|
| `soffice` chết hoặc treo | `subprocess` có `timeout`, `-env:UserInstallation` riêng mỗi lần gọi (nhiều worker dùng chung profile thì LibreOffice tự khóa nhau); lỗi → `UserError` kèm đuôi stderr, log đầy đủ |
| File không phải `.docx` thật (`.doc` cũ, PDF đổi tên, file hỏng) | Không cho traceback nổ ra — sinh finding `file.unreadable` mức `error`; gate tự đóng, người dùng thấy lý do trên form |
| `spec_yaml` sai cú pháp hoặc sai schema | `ValidationError` ngay khi lưu ruleset, nêu đúng đường dẫn khóa sai (`zones.trich_yeu.size_pt: cần [min, max]`) |
| Không có ruleset `active` cho hệ quy chuẩn của loại VB | `UserError` khi bấm kiểm tra, nói rõ thiếu bộ luật nào |
| `standard_hint` của file khác `ruleset.ap_dung` | Finding `file.wrong_standard` mức `warning` — có thể là chọn sai loại VB |
| Chưa cấu hình chứng thư số | Hai `UserError` riêng: thiếu chứng thư người ký, thiếu chứng thư cơ quan |
| `pyhanko` ký thất bại | `UserError`, state không đổi |
| Duyệt bước không phải của mình | `UserError` (không phải `AccessError`) — người dùng cần biết bước nào đang chờ ai |
| Cấp số đồng thời | `no_gap` xếp hàng bằng khóa dòng; rollback thì số trả lại |
| Bản thảo bị đổi giữa `to_sign` và `signed` | Không xảy ra được vì `action_submit()` khóa `draft_file_id`. Vẫn assert hash trước khi ký — lệch thì có lỗ hổng ở chỗ khác, phải nổ chứ không được ký |

## 9. Kiểm thử

Ba tầng, tách theo cái gì cần DB và cái gì không.

### `aidt_format/engine/tests/` — thuần Python, không DB

Chạy bằng `pytest` trên host, không nạp Odoo. Phần lớn test nằm ở đây vì phần lớn
lỗi sẽ ở đây.

Hai điều kiện để giữ được tính chất "không cần Odoo", đã xác minh bằng thực nghiệm:
`engine/tests/` **không có** `__init__.py` (pytest leo lên tìm `__init__.py` để
đặt tên module; có nó thì `aidt_format/__init__.py` bị nạp, kéo theo `import odoo`),
và test import tuyệt đối `from engine.X import …` với
`PYTHONPATH=custom-addons/aidt_format`. Bên trong `engine/` các module import
tương đối nên chạy đúng dưới cả hai gốc.

```
PYTHONPATH=custom-addons/aidt_format python3 -m pytest custom-addons/aidt_format/engine/tests -v
```

Fixture là **hàm sinh `.docx` bằng `python-docx`**, không phải file binary commit
vào git — để review được bằng diff và sửa được khi rule đổi.

```
fixtures.py   chuan_66()            đạt sạch, mọi zone dùng style VB_*
              chuan_nd30()          đạt sạch, hệ quy chuẩn khác
              sai_font()            font khai ở STYLE là Arial, run không khai gì
              sai_dan_dong_exact()  lineRule="exact" thay vì auto
              sai_le_trang()        lề trên 10mm, ngoài khoảng cho phép
              thieu_noi_nhan()      thiếu hẳn một vùng required
              run_lech_nhau()       một đoạn có hai cỡ chữ
              khong_co_style()      chỉ dùng style Normal, buộc chạy heuristic
              hong()                b'khong phai zip'

test_units.py       twip↔mm/cm, half-point↔pt, lineRule auto vs exact
test_resolver.py    bẫy quan trọng nhất: sai_font() phải ra "Arial" qua chuỗi kế
                    thừa, KHÔNG ra None
test_parser.py      lề trang đọc đúng; runs_conflict bật đúng chỗ; hong() →
                    UnreadableDocx
test_zones.py       chuan_66 → zone_confidence='style' hết;
                    khong_co_style → heuristic gán đúng, confidence='heuristic';
                    standard_hint suy đúng cho cả hai chuẩn
test_schema.py      YAML thiếu khóa / sai kiểu → RulesetError nêu đúng đường dẫn
test_rules.py       mỗi fixture sai → đúng bộ finding mong đợi (golden list);
                    chuan_* → rỗng; zone chỉ đoán được → finding hạ xuống warning
```

### `aidt_sign/tests/` — có một test quyết định cả thiết kế

```
fixtures/test-ca.p12    chứng thư tự ký, chỉ dùng cho test
test_converter.py       docx → pdf, có trang, có lớp text
test_sign.py            ký rồi verify hợp lệ; sửa 1 byte → verify thất bại
test_two_signatures.py  ký cá nhân (DocMDP=ANNOTATE) → stamp số/ngày →
                        ký cơ quan → verify CẢ HAI chữ ký còn hợp lệ
```

`aidt_sign` cần `soffice`, chỉ có trong container, nên test module này chạy bằng
`odoo-bin` như tầng dưới.

`test_two_signatures.py` xác minh chỗ rủi ro ở mục 7. Đạt thì đường chính chạy;
không đạt thì lùi sang phương án hai file và phải báo lại.

### `aidt_vanban_di/tests/` — `TransactionCase`, theo mẫu `test_secrecy.py`

Chạy trong container trên một DB dùng một lần (`aidt_test`), không chạm
`aidt_demo`:

```
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_test -i <module> \
  --test-enable --stop-after-init --log-level=test
```


```
test_gate.py        còn error → không trình được;
                    check đạt rồi TẢI FILE MỚI → gate đóng lại;
                    bỏ qua warning không ghi lý do → chặn
test_route.py       chấm điểm chọn route đúng: đơn vị chính xác thắng tổ tiên,
                    route có doc_type thắng route bao trùm, secrecy_max loại route;
                    không route nào khớp → UserError nêu rõ thiếu gì
test_approval.py    duyệt tuần tự, không nhảy bước;
                    trả lại → về draft + lý do vào chatter + activity cho người soạn
test_sequence.py    số đúng format cả hai chuẩn (123-CV/TU và 123/CV-VPTU);
                    no_gap giữ số sau rollback; sổ mật tách khỏi sổ thường
test_lifecycle.py   từng chuyển state sai vai trò → UserError;
                    ký khi chưa duyệt hết → chặn; đăng ký khi chưa ký → chặn
test_write_guard.py sửa trích yếu/độ mật/bản thảo khi đã rời draft → chặn
test_security.py    Chuyên viên không đăng ký được; Văn thư không ký được;
                    rule độ mật vẫn lọc; route không lộ qua đơn vị khác
test_migration.py   bốn giá trị doc_type cũ ánh xạ đúng sang doc_type_id
```

### Không có test cho

Engine phủ 100% quy định (vòng đầu cố ý chỉ khoảng 25 kiểm tra), tích hợp
ONLYOFFICE, tích hợp CA thật, hiệu năng — ba thứ sau chưa có gì để test.

## 10. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| DocMDP + annotation không được mọi trình kiểm tra chữ ký chấp nhận | Cao | `test_two_signatures.py`; đường lùi hai file đã thiết kế sẵn ở mục 7 |
| Resolver đọc sai chuỗi kế thừa → báo lỗi thể thức hàng loạt sai | Cao | Fixture `sai-font.docx` đặt riêng cho bẫy này; zone chỉ đoán được thì tự hạ xuống warning |
| `selection_add` chèn state không đúng vị trí trên statusbar | Thấp | Kiểm tra thứ tự selection cuối cùng khi triển khai; nếu cơ chế mốc không hoạt động thì khai lại `state` trọn vẹn trong `aidt_vanban_di` |
| Migration `doc_type` làm lệch dữ liệu demo | Thấp | `test_migration.py`; sửa `aidt_org_demo/data/org_documents.xml` cùng lúc |
| LibreOffice làm image phình 400–500MB | Thấp | `--no-install-recommends`, chỉ `libreoffice-writer` |
| Engine chạy đồng bộ làm nghẽn worker với file lớn | Trung bình | Đo thời gian mỗi lần check và ghi log; vượt ngưỡng thì tách async (QĐ-5) |

## 11. Trình tự triển khai

Spec này lớn hơn một chặng làm việc, nên kế hoạch triển khai chia thành ba đợt
theo đúng chiều phụ thuộc. Mỗi đợt tự đứng được và có test riêng, nên đợt sau
không phải chờ đợt trước xong mới bắt đầu review.

| Đợt | Nội dung | Xong là có gì |
|---|---|---|
| 1 | `aidt_format` trọn vẹn: `engine/`, `aidt.format.ruleset`, `aidt.format.checker`, seed hai ruleset, toàn bộ test thuần Python | Kiểm được thể thức một file `.docx` bất kỳ, chưa gắn vào nghiệp vụ nào |
| 2 | `aidt_sign`: converter + provider + `test_two_signatures.py`. Thêm `libreoffice-writer` vào `Dockerfile`, `python-docx`/`pyhanko` vào `requirements.txt` | Biết chắc đường ký hai chữ ký chạy được hay phải lùi — trả lời câu hỏi rủi ro cao nhất **trước** khi viết nghiệp vụ |
| 3 | `aidt_vanban_di`: migration `doc_type`, sáu model, vòng đời, gate, route, cấp số, view, quyền, test | Luồng văn bản đi hoàn chỉnh |

Đặt `aidt_sign` ở đợt 2 chứ không phải cuối là có chủ ý: rủi ro DocMDP + annotation
là rủi ro cao nhất trong thiết kế, và nó chỉ cần một test để trả lời. Biết câu trả
lời trước khi dựng `action_sign`/`action_register` thì nếu phải lùi sang phương án
hai file, chỗ phải sửa là một hàm chứ không phải cả vòng đời.
