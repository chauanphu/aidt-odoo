# Kịch bản trình diễn — Engine kiểm tra thể thức văn bản

Trình diễn khoảng 10–12 phút. Thứ cần chứng minh: **máy đọc được file `.docx`
thật, đối chiếu với quy định thể thức, và trả về danh sách sửa được** — chứ
không phải một bản mô tả tính năng.

## Chuẩn bị (làm trước, 5 phút)

```bash
cd /home/aphuc/dev/aidt-odoo

# 1. Sinh bốn văn bản mẫu (chưa có sẵn trong git, cố ý)
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
- Bốn file mẫu nằm ở `docs/demo/*.docx`, mở sẵn thư mục đó trong trình chọn tệp

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

## Phần 3 — Văn bản soạn tay, không theo mẫu (2 phút)

Tải `04-soan-tay.docx`. Cùng bộ luật. Bấm **Kiểm tra**.

Kết quả: **0 lỗi chặn, 0 cảnh báo.**

Đây là phần đáng nói nhất và dễ bị lướt qua nhất. Ba file trên đều sinh từ mẫu
của hệ thống, mỗi đoạn gắn sẵn một nhãn cho máy biết đoạn đó là vùng gì — máy
chỉ việc tra bảng. File này thì không có nhãn nào: định dạng bấm thẳng trên
thanh công cụ Word, đúng cách văn thư soạn khi không dùng mẫu. Máy phải tự
nhận ra mười ba đoạn thuộc mười ba vùng nào, bằng chữ và bằng vị trí — tên cơ
quan vì nó viết hoa và đứng trên số ký hiệu, tên loại vì nó viết hoa và đứng
ngay trước trích yếu, họ tên người ký vì nó căn phải và đứng dưới chức vụ.

Con số đáng nêu: chính file này, trước đợt sửa gần nhất, sinh ra **9 cảnh báo**
— tất cả đều sai. Tiêu ngữ, địa danh, tên loại, chức vụ, họ tên đều bị xếp
nhầm vào vùng nội dung rồi đem thước phần thân ra đo: "cần căn đều hai bên,
đang căn giữa". Văn bản không có lỗi nào. Một danh sách mà 9/9 dòng là báo oan
thì văn thư sẽ bỏ qua cả danh sách, kể cả khi trong đó có lỗi thật.

Khi vùng chỉ đoán được chứ không tra được, mọi phát hiện đều hạ xuống mức cảnh
báo, không bao giờ chặn. Máy không đủ chắc thì máy không được khoá nút Trình ký.

## Phần 4 — Quy định nằm trong dữ liệu, không trong mã nguồn (3 phút)

Vào **Thể thức văn bản → Cấu hình → Bộ luật thể thức**, mở bản ghi
**ND-30/2020**.

Cho xem khối YAML: mỗi vùng thể thức một khối, cỡ chữ khai thành khoảng
`[min, max]`. Sửa `noi_dung.size_pt` từ `[13, 14]` thành `[13, 13]`, lưu, rồi
kiểm lại `01-dat-chuan.docx` — giờ nó báo lỗi cỡ chữ.

Nói: đổi quy định là **sửa dữ liệu, không phải sửa phần mềm**. Không cần lập
trình viên, không cần triển khai bản mới. Có hai bộ luật song song — văn bản
Đảng và văn bản hành chính — chạy trên cùng một máy kiểm.

Nhớ hoàn tác lại `[13, 14]` sau khi trình diễn xong.

Nếu còn thời gian, mở `03-dau-trang-bang.docx`: khối đầu trang dựng bằng bảng
2 cột, đúng cách văn bản hành chính thật được soạn — năm vùng thể thức đầu
trang nằm gọn trong bốn ô bảng. Thư viện đọc `.docx` bỏ qua đoạn nằm trong ô
bảng nếu gọi theo đường mặc định, nên trước bản sửa thì gần như mọi văn bản
thật đều bị báo "thiếu quốc hiệu". Máy vẫn đọc ra đủ.

## Phải nói thẳng, đừng để người ta tự phát hiện

**Bộ luật văn bản Đảng chưa được thẩm định.** Các con số trong bộ `66-QD/TW`
chưa ai đối chiếu với văn bản quy định gốc — số typography của văn bản Đảng
nằm ở Hướng dẫn 36-HD/VPTW, không ở Quy định 66. Cảnh báo này ghi ngay đầu bộ
luật, ai mở ra cũng thấy. **Vì vậy buổi này trình diễn bằng bộ NĐ 30/2020**,
là bộ đã đối chiếu với Phụ lục I của nghị định.

Việc cần người của cơ quan làm: một văn thư có bản Hướng dẫn 36 đọc qua hai
file YAML, ước chừng 20 phút.

**Vùng nhận diện bằng suy đoán thì chỉ đúng trong khuôn nó được dựng.** Năm
vùng bổ sung gần đây nhận ra bằng vị trí tương đối: tên cơ quan vì đứng trên
số ký hiệu, tên loại vì đứng ngay trước trích yếu, họ tên vì đứng dưới chức
vụ. Văn bản nào không có số ký hiệu, hoặc xếp khác thứ tự thông thường, thì
máy cố ý **không đoán** — thà bỏ qua còn hơn đem nhầm thước ra đo. Hệ quả là
với những văn bản đó, phần thể thức đầu trang không được kiểm.

**Tên cơ quan chủ quản và tên cơ quan ban hành chưa tách được.** NĐ 30 bắt cơ
quan ban hành in đậm, cơ quan chủ quản thì không; máy nhìn cả hai như nhau nên
bỏ hẳn quy định in đậm ở vùng này thay vì báo oan một nửa số văn bản.

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

## Nạp lại bộ luật gốc vào một DB đã cài (việc của người vận hành)

Bộ luật seed khai `noupdate="1"` đúng theo chủ ý ở trên: nâng cấp module
KHÔNG được đè lên bộ luật mà cơ quan đã chỉnh. Hệ quả là khi bản thân file
seed trong mã nguồn đổi, DB cũ vẫn giữ bản cũ.

Đổi cờ `noupdate` trong bảng `ir_model_data` **không có tác dụng** — Odoo đọc
thuộc tính ghi trong file XML, không đọc cờ trong DB. Cách chạy được là xóa
hẳn bản ghi rồi nâng cấp cho nó sinh lại:

```bash
docker compose -f docker-compose.dev.yml exec -T odoo \
  /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d aidt_poc --no-http <<'PY'
data = env['ir.model.data'].search([('module','=','aidt_format'),
                                    ('model','=','aidt.format.ruleset')])
recs = env['aidt.format.ruleset'].browse(data.mapped('res_id')).exists()
data.unlink(); recs.unlink(); env.cr.commit()
PY

docker compose -f docker-compose.dev.yml exec -T odoo /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_poc -u aidt_format --http-port=8102 \
  --stop-after-init
```

Thao tác này **xóa mọi chỉnh sửa** người dùng đã làm trên hai bộ luật đó. Trên
DB thật thì đừng làm thế: tạo phiên bản mới bên cạnh.
