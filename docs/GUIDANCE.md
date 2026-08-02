# Hướng dẫn sử dụng hệ thống AIDT

Tài liệu này dành cho **người dùng cuối** — cán bộ văn thư, chuyên viên, lãnh
đạo — không dành cho người quản trị kỹ thuật. Mọi thao tác mô tả ở đây đều
thực hiện trên trình duyệt, không cần cài đặt gì thêm.

Mỗi khi hệ thống có tính năng mới, tính năng đó sẽ được bổ sung thành một mục
riêng trong tài liệu này.

## Mục lục

| Tính năng | Trạng thái | Mục |
|---|---|---|
| Tìm kiếm thông minh (Document Intelligence) | Mới | [1](#1-tìm-kiếm-thông-minh) |

---

# 1. Tìm kiếm thông minh

## 1.1. Tính năng này giúp gì cho bạn

Trước đây bạn chỉ tìm được văn bản theo **thông tin ngoài bìa**: số hiệu,
trích yếu, ngày ban hành, đơn vị. Nếu không nhớ số hiệu và trích yếu ghi chữ
khác với chữ bạn nghĩ, coi như không tìm ra.

Tìm kiếm thông minh đọc **nội dung bên trong tệp đính kèm** (Word, PDF, kể cả
bản scan) và cho phép bạn hỏi bằng **câu tiếng Việt bình thường**:

> *văn bản nào về hỗ trợ hộ nghèo năm 2025*

Hệ thống hiểu "năm 2025" là mốc thời gian, còn "hỗ trợ hộ nghèo" là nội dung
cần tìm — kể cả khi văn bản viết là *"trợ giúp các hộ có hoàn cảnh khó khăn"*,
không hề có đúng chữ "hộ nghèo".

**Lưu ý quan trọng:** hệ thống **trả về danh sách văn bản kèm trích đoạn**,
chứ **không tự viết câu trả lời**. Bạn luôn nhìn thấy đoạn văn gốc và mở được
văn bản gốc để kiểm chứng. Đây là chủ ý thiết kế: với văn bản hành chính,
người dùng phải đọc bản gốc, không đọc bản tóm tắt do máy sinh ra.

## 1.2. Mở màn hình tìm kiếm

Vào menu **Văn bản → Tìm kiếm thông minh**.

Bạn sẽ thấy một ô nhập lớn với gợi ý *"Ví dụ: văn bản nào về hỗ trợ hộ nghèo
năm 2025"* và nút **Tìm**. Gõ câu hỏi rồi bấm **Tìm** hoặc nhấn **Enter**.

## 1.3. Cách đặt câu hỏi

Gõ như đang nói với đồng nghiệp. Không cần cú pháp, không cần dấu ngoặc, không
cần toán tử.

### Hệ thống tự hiểu những gì

Khi tìm xong, ngay dưới ô nhập sẽ hiện dòng **"Đã hiểu:"** kèm các thẻ nhỏ.
Mỗi thẻ là một điều kiện lọc mà hệ thống bóc được ra từ câu hỏi của bạn:

| Bạn gõ | Hệ thống hiểu |
|---|---|
| `năm 2026` | Toàn bộ năm 2026 |
| `quý II năm 2026` | 01/04/2026 → 30/06/2026 |
| `quý III` | Quý III của năm hiện tại |
| `tháng 3/2026` | 01/03/2026 → 31/03/2026 |
| `145/KH-UBND` | Đúng số hiệu đó |
| `Sở Tài chính` | Đơn vị ban hành |
| `Thượng khẩn`, `Hỏa tốc` | Độ khẩn |
| `kế hoạch`, `báo cáo`, `công văn`… | Loại văn bản |

**Bỏ một điều kiện đã hiểu sai:** bấm dấu **×** trên thẻ đó. Cụm từ sinh ra
điều kiện đó được **xoá khỏi ô câu hỏi** và hệ thống tìm lại ngay — điều kiện
biến mất thật sự, không phải chỉ ẩn thẻ đi rồi lượt sau lại hiểu sai như cũ.

### Tìm theo số hiệu

Gõ thẳng số hiệu là đủ:

```
145/KH-UBND
```

Hệ thống nhận ra đây là số hiệu và đi thẳng vào tra cứu chính xác, không đoán
theo nội dung. Gõ thừa cũng không sao — `cho tôi xem 145/KH-UBND` cho kết quả
như nhau.

### Vì sao đôi khi "kế hoạch" lọc, đôi khi không

Đây là điểm dễ gây thắc mắc nhất, nên nói rõ:

- Gõ **`kế hoạch quý II năm 2026`** → hệ thống hiểu bạn muốn **duyệt theo
  loại**, nên lọc chỉ còn văn bản loại Kế hoạch.
- Gõ **`kế hoạch hỗ trợ hộ nghèo`** → hệ thống **không lọc** theo loại. Thẻ
  "Đã hiểu" vẫn hiện để bạn biết máy đã nhận ra chữ đó, nhưng cụm "kế hoạch"
  được giữ lại trong phần nội dung đem đi tìm.

Lý do: nếu lọc cứng ở trường hợp thứ hai, một Công văn có nội dung đúng về
hỗ trợ hộ nghèo sẽ bị loại khỏi kết quả và **bạn không hề biết vì sao**. Hệ
thống chỉ lọc cứng khi câu hỏi thực chất *chỉ là* tên loại văn bản cộng các
mốc thời gian.

Nguyên tắc chung: **thà trả về thừa một chút còn hơn giấu mất văn bản đúng.**

### Từ dễ hiểu nhầm

Vài chữ tiếng Việt vừa là nhãn phân loại vừa là từ thông thường. Hệ thống đã
được dạy phân biệt các trường hợp phổ biến:

- `hỗ trợ **khẩn cấp**` → "khẩn cấp" là tính từ, **không** bị hiểu thành độ
  khẩn "Khẩn".
- `**báo cáo viên**` → chức danh, không phải loại văn bản "Báo cáo".
- `**kế hoạch hoá** gia đình` → không phải loại văn bản "Kế hoạch".

Danh sách này không thể đầy đủ. Nếu gặp trường hợp máy hiểu sai, cách xử lý
ngay là bấm **×** trên thẻ "Đã hiểu" — và báo cho quản trị để bổ sung.

## 1.4. Đọc kết quả

### Cột trái — Lọc thêm

Ba nhóm bộ lọc, mỗi dòng kèm số lượng văn bản:

- **Loại văn bản** — Công văn, Báo cáo, Kế hoạch, Quyết định, Thông báo, Kết
  luận, Nghị quyết, Tờ trình, Giấy mời
- **Đơn vị** — đơn vị ban hành
- **Độ mật** — Thường, Mật, Tối mật, Tuyệt mật

Bấm một dòng để lọc, bấm lại để bỏ lọc.

Các con số này **chỉ đếm trên những văn bản bạn có quyền xem**. Nếu hệ thống
có 40 kế hoạch nhưng bạn chỉ được xem 12, bạn sẽ thấy số 12. Con số ở đây
không làm lộ sự tồn tại của văn bản bạn không được đọc.

### Cột phải — Danh sách văn bản

Mỗi kết quả gồm:

- **Tiêu đề** (loại + số hiệu, hoặc tên văn bản) — bấm vào để mở văn bản gốc
- **Nhãn độ mật**
- **Trích yếu**
- **Tối đa 3 trích đoạn** lấy từ trong tệp, phần khớp với câu hỏi được **tô
  vàng**. Trước mỗi trích đoạn thường có đường dẫn cấu trúc và số trang, ví dụ
  *"Điều 3 · trang 2 —"*, để bạn biết đoạn đó nằm ở đâu trong văn bản.

Trên đầu danh sách là tổng số, ví dụ *"12 văn bản phù hợp"*. Nếu hiện *"Hơn
150 văn bản phù hợp"* nghĩa là kết quả quá rộng — hãy thêm mốc thời gian, đơn
vị, hoặc mô tả nội dung cụ thể hơn.

## 1.5. Các thông báo bạn có thể gặp

Hệ thống cố ý phân biệt rõ các tình huống dưới đây, vì chúng có ý nghĩa rất
khác nhau đối với bạn.

### Dải vàng — "Tìm kiếm ngữ nghĩa tạm ngưng — đang tìm bằng từ khoá."

Bộ phận hiểu-ngữ-nghĩa đang gặp sự cố. Hệ thống **vẫn tìm được** bằng từ khoá,
nhưng lúc này bạn cần gõ **đúng chữ có trong văn bản** — hỏi "hỗ trợ hộ nghèo"
sẽ không còn tìm ra văn bản viết "trợ giúp hộ khó khăn".

Trong tình huống này hệ thống **không hiện tổng số** — vì nó biết mình đang
thiếu kết quả nhưng không biết thiếu bao nhiêu, và hiện một con số sai còn tệ
hơn không hiện. Báo quản trị viên; kết quả tìm được vẫn dùng được bình thường.

### Dải xanh — "Kho chỉ mục đang xử lý N tệp…"

Có tệp mới tải lên và hệ thống **chưa đọc xong**. Văn bản bạn tìm có thể nằm
trong số đó. Thường chỉ mất vài phút — chờ rồi tìm lại.

### "Không có kết quả phù hợp." / "Chưa thấy văn bản phù hợp trong phần đã nạp xong của kho chỉ mục."

Hai câu này khác nhau và **đừng đọc lướt qua**:

- Câu thứ nhất: kho đã đọc xong hết, thực sự không có gì khớp.
- Câu thứ hai: kho **vẫn đang đọc dở**. Chưa thấy ≠ không có. Chờ vài phút rồi
  tìm lại.

### Dải đỏ

Lỗi kỹ thuật khi gọi máy chủ. Thử lại; nếu lặp lại, báo quản trị viên kèm nội
dung dòng chữ đỏ.

## 1.6. Đưa văn bản vào tìm kiếm

**Bạn không cần làm gì thêm.** Cứ đính kèm tệp vào văn bản như bình thường —
hệ thống tự phát hiện và đưa vào hàng đợi. Cứ mỗi phút hàng đợi được xử lý một
lượt.

### Định dạng đọc được

| Loại tệp | Cách xử lý |
|---|---|
| Word (`.docx`) | Đọc trực tiếp |
| PDF có chữ | Đọc trực tiếp |
| PDF scan | Nhận dạng ảnh (OCR), từng trang một |
| Ảnh (chụp, scan) | Nhận dạng ảnh (OCR) |

Hệ thống nhận diện tệp theo **nội dung thật**, không theo phần mở rộng — đổi
tên `.pdf` thành `.docx` không đánh lừa được nó.

PDF được xét **theo từng trang**: một tệp vừa có trang đánh máy vừa có trang
scan chèn giữa sẽ được xử lý đúng cho từng trang.

> ⚠️ **Lưu ý cho giai đoạn hiện tại:** nhánh nhận dạng ảnh (OCR) chưa được
> chạy kiểm chứng trên hệ thống thật. Với văn bản scan và ảnh, hãy kiểm tra
> lại kết quả trước khi tin tưởng hoàn toàn.

### Theo dõi trạng thái của một văn bản

Mở văn bản, nhìn hai chỗ:

- **Nút "Đoạn đã chỉ mục"** ở cụm nút trên đầu — số đoạn nội dung đã được nạp.
  Bằng 0 nghĩa là chưa nạp được gì.
- **Trạng thái chỉ mục** trong phần thông tin:

| Nhãn | Ý nghĩa |
|---|---|
| **Chưa nạp** | Chưa có tệp, hoặc chưa được đưa vào hàng đợi |
| **Đang xử lý** | Trong hàng đợi hoặc đang đọc |
| **Đã chỉ mục** | Tìm kiếm được |
| **Lỗi chỉ mục** | Đọc thất bại — báo quản trị viên |

### Nạp lại thủ công

Bấm nút **"Đoạn đã chỉ mục"** để buộc hệ thống đọc lại toàn bộ tệp của văn bản
đó. Dùng khi bạn vừa thay tệp đính kèm mà trạng thái không tự cập nhật, hoặc
sau khi quản trị viên đã khắc phục một lỗi chỉ mục.

Sửa **số hiệu**, **tên**, hoặc **loại văn bản** thì hệ thống tự nạp lại — vì
những thông tin này được ghép vào nội dung để tăng độ chính xác khi tìm.

## 1.7. Quyền xem

**Tìm kiếm không bao giờ mở rộng quyền của bạn.** Bạn chỉ thấy được đúng những
văn bản mà bạn vốn đã được phép mở — theo đơn vị và theo độ mật.

Điều này áp dụng cho **mọi thứ** hiển thị trên màn hình: danh sách kết quả,
trích đoạn, tổng số, và cả các con số đếm trong bộ lọc. Văn bản ngoài quyền
của bạn bị loại **trước khi** hệ thống xếp hạng, nên chúng không chiếm chỗ và
cũng không để lại dấu vết nào.

Nếu đồng nghiệp tìm ra một văn bản mà bạn tìm không ra với cùng câu hỏi, gần
như chắc chắn là do khác quyền, không phải lỗi hệ thống.

## 1.8. Xử lý nhanh khi tìm không ra

| Hiện tượng | Nên làm |
|---|---|
| Không có kết quả, mà bạn chắc chắn văn bản tồn tại | Mở văn bản đó, xem **Trạng thái chỉ mục**. "Chưa nạp"/"Lỗi chỉ mục" là nguyên nhân. |
| Kết quả quá ít so với dự đoán | Xem thẻ **"Đã hiểu"** — có thể một mốc bị hiểu sai. Bấm **×** để bỏ. |
| Kết quả quá nhiều ("Hơn N…") | Thêm năm/quý, đơn vị, hoặc dùng bộ lọc cột trái. |
| Kết quả không liên quan | Mô tả nội dung cụ thể hơn thay vì dùng từ chung chung. |
| Có dải vàng | Hệ thống đang chạy chế độ hạn chế — gõ đúng chữ trong văn bản, và báo quản trị. |
| Có dải xanh | Chờ vài phút, tìm lại. |

---

## Dành cho quản trị viên

Phần này chỉ liên quan đến người có quyền quản trị.

**Menu Văn bản → Hàng đợi chỉ mục** liệt kê toàn bộ công việc đọc tệp, kèm
trạng thái, số lần thử, thời điểm thử lại và thông điệp lỗi. Với công việc ở
trạng thái **Lỗi**, dùng nút **Nạp lại**.

Lỗi tạm thời (mạng chập chờn, service bận) được **tự động thử lại**. Lỗi vĩnh
viễn (tệp hỏng, định dạng không đọc được) dừng lại và chờ can thiệp — nạp lại
mà không sửa gì thì kết quả vẫn như cũ.

Tham số hệ thống nằm ở **Cài đặt → Kỹ thuật → Tham số hệ thống**, tiền tố
`aidt_search.` (địa chỉ service, ngưỡng liên quan…). Chi tiết kỹ thuật xem
[`custom-addons/aidt_search/README.md`](../custom-addons/aidt_search/README.md).

> ⚠️ Ngưỡng liên quan (`aidt_search.vector_max_distance`) hiện được đặt dựa
> trên một tập dữ liệu thử rất nhỏ. Cần hiệu chỉnh lại trên kho văn bản thật
> trước khi đưa vào sử dụng chính thức.
