# Kịch bản trình diễn — Engine kiểm tra thể thức văn bản

Trình diễn khoảng 8–10 phút. Thứ cần chứng minh: **máy đọc được file `.docx`
thật, đối chiếu với quy định thể thức, và trả về danh sách sửa được** — chứ
không phải một bản mô tả tính năng.

## Chuẩn bị (làm trước, 5 phút)

```bash
cd /home/aphuc/dev/aidt-odoo

# 1. Sinh ba văn bản mẫu (chưa có sẵn trong git, cố ý)
python3 docs/demo/sinh-van-ban-mau.py

# 2. Dựng lại DB trình diễn nếu cần làm lại từ đầu
docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_poc -i aidt_format --http-port=8102 \
  --stop-after-init
```

- Mở `http://localhost:8069`, chọn cơ sở dữ liệu **`aidt_poc`**
- Đăng nhập **admin / demo**
- Màn hình chính có ô ứng dụng **Thể thức văn bản**, bên trong là:
  - **Kiểm tra thể thức** — việc hằng ngày của văn thư
  - **Cấu hình → Bộ luật thể thức** — chỉ quản trị viên thấy
- Ba file mẫu nằm ở `docs/demo/*.docx`, mở sẵn thư mục đó trong trình chọn tệp

> DB `aidt_poc` là DB riêng cho buổi này. `aidt_demo` không bị đụng tới.

## Phần 1 — Máy không bắt lỗi bừa (2 phút)

Vào **Kiểm tra thể thức**, tải `01-dat-chuan.docx`, chọn bộ luật **ND-30/2020**,
bấm **Kiểm tra**.

Kết quả: **0 lỗi chặn, 0 cảnh báo.**

Nói: đây là văn bản soạn đúng Nghị định 30 — lề 22mm, Times New Roman, quốc
hiệu 13pt in đậm, nội dung 14pt căn đều hai bên, dãn dòng 1,5. Máy im lặng.

Phần này quan trọng hơn vẻ ngoài của nó: nếu bắt đầu bằng văn bản sai, người
xem sẽ nghi máy báo lỗi bừa để trông có việc.

## Phần 2 — Máy chỉ đúng chỗ sai, và nói cách sửa (4 phút)

Tải `02-sai-the-thuc.docx`. Cùng bộ luật. Bấm **Kiểm tra**.

Kết quả: **3 lỗi chặn, 1 cảnh báo.**

| Mức | Ở đâu | Cần | Đang |
|---|---|---|---|
| Lỗi chặn | Thiết lập trang | 20–25mm | 15mm |
| Lỗi chặn | Đoạn 3 | có in đậm | không in đậm |
| Lỗi chặn | Đoạn 4 | căn đều hai bên | căn trái |
| Cảnh báo | Đoạn 4 | 1–1,27cm | 3,00cm |

Ba điểm nên nói khi màn hình đang mở:

1. **Mỗi dòng nêu đủ ba thứ**: cần gì, đang gì, sửa thế nào. Văn thư đọc xong
   biết mở Word lên làm gì, không phải đoán.
2. **Phân biệt lỗi chặn với cảnh báo.** Ở vòng sau, còn lỗi chặn thì nút Trình
   ký khoá lại; cảnh báo thì cho qua nhưng phải ghi lý do. Mức nghiêm trọng
   của từng quy định do cơ quan tự chỉnh, không nằm cứng trong mã nguồn.
3. **Máy chỉ đo được thứ đo được**: phông, cỡ, lề, căn lề. Nó không thay lãnh
   đạo soát nội dung. Lớp soát người vẫn nằm trong đường trình ký.

## Phần 3 — Quy định nằm trong dữ liệu, không trong mã nguồn (3 phút)

Vào **Settings → Bộ luật thể thức**, mở bản ghi **ND-30/2020**.

Cho xem khối YAML: mỗi vùng thể thức một khối, cỡ chữ khai thành khoảng
`[min, max]`. Sửa `noi_dung.size_pt` từ `[13, 14]` thành `[13, 13]`, lưu, rồi
kiểm lại `01-dat-chuan.docx` — giờ nó báo lỗi cỡ chữ.

Nói: đổi quy định là **sửa dữ liệu, không phải sửa phần mềm**. Không cần lập
trình viên, không cần triển khai bản mới. Có hai bộ luật song song — văn bản
Đảng và văn bản hành chính — chạy trên cùng một máy kiểm.

Nhớ hoàn tác lại `[13, 14]` sau khi trình diễn xong.

Nếu còn thời gian, mở `03-dau-trang-bang.docx`: khối đầu trang dựng bằng bảng
2 cột, đúng cách văn bản hành chính thật được soạn. Máy vẫn đọc ra tiêu đề nằm
trong ô bảng.

## Phải nói thẳng, đừng để người ta tự phát hiện

**Bộ luật văn bản Đảng chưa được thẩm định.** Các con số trong bộ `66-QD/TW`
chưa ai đối chiếu với văn bản quy định gốc — số typography của văn bản Đảng
nằm ở Hướng dẫn 36-HD/VPTW, không ở Quy định 66. Cảnh báo này ghi ngay đầu bộ
luật, ai mở ra cũng thấy. **Vì vậy buổi này trình diễn bằng bộ NĐ 30/2020**,
là bộ đã đối chiếu với Phụ lục I của nghị định.

Việc cần người của cơ quan làm: một văn thư có bản Hướng dẫn 36 đọc qua hai
file YAML, ước chừng 20 phút.

**Mô hình vùng còn thiếu năm vùng thể thức**: tiêu ngữ, tên cơ quan ban hành,
địa danh và ngày tháng, tên loại văn bản, họ tên người ký. Những đoạn đó hiện
bị xếp vào vùng nội dung và đo bằng thước của phần thân, nên văn bản soạn tay
ngoài mẫu sẽ sinh thêm vài cảnh báo không phải vi phạm thật. Chúng là cảnh
báo, không chặn — nhưng đây là việc lớn nhất còn lại trước khi dùng thật.

## Nếu bị hỏi

**"Máy có tự sửa văn bản không?"** Chưa. Cấu trúc phát hiện đã mang sẵn giá
trị mong đợi nên thêm nút *Sửa tự động* về sau là ánh xạ thẳng, không phải
viết lại.

**"Chạy có lâu không?"** Khoảng 30 mili giây một văn bản. Đo và ghi log mỗi
lần kiểm.

**"Sao không dùng AI cho phần này?"** Thể thức là quy định đo đếm được: cỡ chữ
14 thì đúng hoặc sai, không có vùng xám. Máy đo cho kết quả xác định và giải
thích được bằng đúng điều khoản. AI để dành cho phần không đo đếm được — tóm
tắt, bóc tách nhiệm vụ, tìm kiếm ngữ nghĩa.

**"Sửa quy định thì mất bao lâu?"** Sửa YAML rồi lưu. Cần lưu ý: bộ luật đã
cài vào cơ sở dữ liệu sẽ không tự cập nhật khi nâng cấp phần mềm — đổi quy
định là tạo phiên bản mới, để văn bản cũ còn truy được nó đã kiểm bằng luật
nào.
