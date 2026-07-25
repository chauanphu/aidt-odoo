Đây là bài toán rất hợp để làm đúng ngay từ MVP, vì sai lầm phổ biến nhất — **hardcode quy định vào code** — sẽ khiến bạn khổ sở khi quy định đổi hoặc khi phải hỗ trợ song song hai hệ quy chuẩn (66-QĐ/TW cho văn bản Đảng, NĐ 30/2020 cho văn bản hành chính nhà nước). Nguyên lý cốt lõi: **tách "luật" ra khỏi "máy kiểm tra"**.

## Kiến trúc 4 tầng

```
DOCX upload
   │
   ▼
[1] Parser ─ đọc DOCX ra cấu trúc trung gian
   ▼
[2] Resolver ─ tính định dạng "hiệu lực" thực tế của từng đoạn
   ▼
[3] Zone detector ─ nhận diện vùng thể thức (quốc hiệu/tiêu đề Đảng, số ký hiệu, trích yếu, chữ ký...)
   ▼
[4] Rule engine ─ đối chiếu từng vùng với bộ luật (file cấu hình) → báo cáo lỗi
```

## Tầng 1-2: Parser + Resolver — phần khó nhất về kỹ thuật

DOCX là ZIP chứa XML. Dùng `python-docx` đọc được paragraph, run, style, section. Nhưng có một cái bẫy chết người mà mọi engine check thể thức ngây thơ đều dính: **định dạng trong DOCX là kế thừa nhiều tầng**. Font của một chữ được quyết định theo thứ tự ưu tiên:

```
run properties trực tiếp  >  character style  >  paragraph style  >  style cha  >  docDefaults  >  theme font
```

Nghĩa là một đoạn nhìn thấy Times New Roman 14pt nhưng `run.font.name` trả về `None` — vì nó thừa hưởng từ style. Nếu engine chỉ đọc thuộc tính trực tiếp, nó sẽ báo sai hàng loạt. Nên Resolver phải làm việc "flatten": với mỗi run, leo ngược chuỗi kế thừa để ra **giá trị hiệu lực**:

```python
def effective_font(run, paragraph, doc):
    # 1. Run trực tiếp
    if run.font.name: return run.font.name
    # 2. Character style của run
    if run.style and run.style.font.name: return run.style.font.name
    # 3. Paragraph style, leo lên style cha
    style = paragraph.style
    while style:
        if style.font.name: return style.font.name
        style = style.base_style
    # 4. docDefaults / theme (đọc từ styles.xml, theme1.xml)
    return doc_defaults_font(doc)
```

Tương tự cho cỡ chữ (đơn vị nội bộ là half-point: 28 = 14pt), dãn dòng (`w:spacing` — phân biệt `lineRule="auto"` giá trị 240=single, 360=1.5 lines, với `lineRule="exact"` tính bằng twip), lề trang (section properties, đơn vị twip: 1cm = 567 twip), thụt đầu dòng, căn lề.

Output của tầng này là một cấu trúc trung gian sạch — mỗi đoạn kèm định dạng hiệu lực đầy đủ — mọi tầng sau chỉ làm việc trên cấu trúc này, không đụng XML nữa.

## Tầng 3: Zone detector — vì quy định là "theo vùng", không phải toàn cục

66-QĐ/TW và NĐ 30 không quy định một cỡ chữ cho cả văn bản — mỗi thành phần thể thức có quy tắc riêng (tiêu đề "ĐẢNG CỘNG SẢN VIỆT NAM" khác trích yếu, khác nội dung, khác nơi nhận). Nên trước khi check phải gán mỗi đoạn vào một vùng.

MVP làm bằng **heuristic vị trí + pattern**, đủ chính xác vì văn bản hành chính có cấu trúc cực kỳ ổn định:

- Đoạn đầu tiên, căn giữa/phải, chữ in hoa khớp `ĐẢNG CỘNG SẢN VIỆT NAM` → vùng tiêu đề Đảng (hoặc `CỘNG HÒA XÃ HỘI...` → quốc hiệu, phân biệt luôn văn bản thuộc hệ nào)
- Dòng khớp regex `Số\s*[:：]?\s*\d+[-/][A-ZĐ]+` → vùng số ký hiệu
- `V/v\s+...` hoặc dòng in đậm ngay dưới tên loại → trích yếu
- `Nơi nhận\s*:` → vùng nơi nhận
- Khối căn phải cuối văn bản có chức danh in hoa → vùng chữ ký
- Còn lại → vùng nội dung

Lợi thế lớn của bạn: **văn bản soạn từ template của chính hệ thống (D-01)** có thể gắn sẵn style đặt tên (`VB_TrichYeu`, `VB_NoiNhan`...) — khi đó zone detection thành tra bảng style, chính xác 100%. Heuristic chỉ cần cho file người dùng soạn tay ngoài template. Đây là lý do nên khuyến khích tải mẫu từ hệ thống về sửa, thay vì soạn từ trang trắng.

## Tầng 4: Rule engine — luật là dữ liệu, không phải code

Bộ quy định biểu diễn thành file cấu hình (YAML/JSON), mỗi hệ quy chuẩn một bộ, có version:

```yaml
ruleset: "66-QD/TW"
version: "2025.1"
ap_dung: van_ban_dang
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
    ket_thuc_bang_dong_ke: true      # dòng kẻ dưới tiêu đề
  trich_yeu:
    font: "Times New Roman"
    size_pt: [14, 14]
    bold: true
    align: center
  noi_dung:
    font: "Times New Roman"
    size_pt: [14, 15]
    line_spacing: [1.0, 1.5]
    first_line_indent_cm: [1.0, 1.27]
    align: [justify]
  noi_nhan:
    required: true
    size_pt: [12, 12]
severity_overrides:
  noi_dung.size_pt: warning     # lệch cỡ chữ nội dung = cảnh báo
  tieu_de_dang.required: error  # thiếu tiêu đề Đảng = lỗi chặn
```

Engine chỉ là vòng lặp generic: với mỗi zone, lấy rule tương ứng, so sánh giá trị hiệu lực với khoảng cho phép, sinh finding:

```python
@dataclass
class Finding:
    rule_id: str          # "noi_dung.line_spacing"
    severity: str         # error | warning
    zone: str
    location: str         # "Đoạn 14, trang 2"
    expected: str         # "Dãn dòng 1.0–1.5"
    actual: str           # "Dãn dòng exact 12pt"
    goi_y: str            # "Đặt dãn dòng Multiple 1.5"
```

Cách này cho bạn đúng thứ cần cho cả MVP lẫn production:

- **Hai hệ quy chuẩn song song**: chọn ruleset theo trường `loai_van_ban` của bản ghi — văn bản Đảng chạy bộ 66-QĐ/TW, văn bản chính quyền chạy bộ NĐ 30. Cùng một engine.
- **Quy định đổi** → sửa YAML, tăng version, không release code. Văn bản cũ đã check giữ lại `ruleset_version` để truy vết vì sao ngày đó đạt.
- **Mức nghiêm trọng cấu hình được**: lỗi nào chặn trình ký (D-09), lỗi nào chỉ cảnh báo — chỉnh trong config theo mức khó tính của từng cơ quan.

## Luồng MVP hoàn chỉnh

Trên form văn bản đi: người dùng bấm **"Tải mẫu"** (DOCX sinh từ template, trường động đã điền) → sửa trên Word máy mình → **upload bản sửa** → hệ thống chạy engine (qua `queue_job`, vài giây) → hiển thị **danh sách finding trên form**, nhóm theo vùng, click finding nhảy tới đoạn lỗi (kèm trích đoạn). Đạt hết lỗi mức `error` thì nút "Trình ký" mở khóa. Kết quả check lưu vào bản ghi làm bằng chứng D-07/D-09, log audit.

## Đường mở rộng lên production (không đập lại gì)

1. **Auto-fix**: finding nào máy sửa được (font, cỡ, dãn dòng, lề) thêm nút "Sửa tự động" — cùng parser đó, ghi ngược vào XML rồi trả file đã chuẩn hóa. Cấu trúc Finding đã có `expected` nên auto-fix chỉ là ánh xạ.
2. **Soạn thảo trực tuyến (D-05)**: engine nhận cấu trúc trung gian, không quan tâm nguồn là DOCX hay editor online — cắm thẳng, check real-time khi gõ.
3. **Check PDF trước ký**: cùng rule set, thêm parser PDF (đo bằng tọa độ thay vì style) — tầng 3-4 tái sử dụng nguyên vẹn.
4. **Vùng khó dần**: bảng biểu, phụ lục, văn bản song ngữ — chỉ là thêm zone + rule mới vào config.

Một lời khuyên thực dụng cuối: đừng cố phủ 100% quy định ngay vòng đầu. Chọn ~15-20 rule "hay sai nhất, dễ đo nhất" (font, cỡ chữ từng vùng, lề trang, dãn dòng, thiếu nơi nhận, thiếu số ký hiệu, sai vị trí căn lề) — phủ được 80% lỗi thực tế văn thư gặp hàng ngày. Các rule tinh vi (khoảng cách giữa các thành phần tính bằng dòng, vị trí con dấu) để lại sau khi có số liệu từ O-06 xem người dùng thực sự vấp ở đâu.