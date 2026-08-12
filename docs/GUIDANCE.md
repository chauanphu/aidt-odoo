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
| Ghi âm và biên bản cuộc họp | Mới — ⚠️ đọc [2.1](#21-trước-khi-đọc-tiếp) và [2.7](#27-tắt-micro-không-dừng-việc-ghi-biên-bản) trước khi dùng | [2](#2-ghi-âm-và-biên-bản-cuộc-họp) |
| Phòng họp trực tuyến — mục **Họp** và nút **Họp ngay** | Mới | [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp) |
| Trang **Quản lý cuộc họp** (Discuss) | Mới — ⚠️ hiện lịch họp của cả cơ quan | [2.4](#24-trang-quản-lý-cuộc-họp) |
| Quản lý Lịch chung & Lịch công tác tuần | Mới | [3](#3-quản-lý-lịch-chung--lịch-công-tác-tuần) |

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

# 2. Ghi âm và biên bản cuộc họp

> **Tên menu bằng tiếng Anh.** Tài khoản người dùng ở đây đang đặt ngôn ngữ
> `en_US`, nên các menu và nhãn có sẵn của Odoo giữ nguyên tiếng Anh: ứng dụng
> **Discuss** (tức "Thảo luận"), mục **Channels** ("Kênh"), **Direct messages**
> ("Tin nhắn trực tiếp"), **Configuration** ("Cấu hình"), thẻ **Options**
> ("Tùy chọn") trên form cuộc họp, ô **Organizer** ("Nhà Tổ chức"). Những chỗ
> do hệ thống AIDT làm ra thì là tiếng Việt: **Quản lý cuộc họp**, **Lịch sử
> cuộc họp**, mục **Họp**, nút **Họp ngay**, **Bật ghi âm biên bản**… Tài liệu
> này chép đúng chữ hiện trên màn hình, nên bạn tìm theo là thấy.
>
> Nếu tài khoản của bạn được đổi sang tiếng Việt thì các nhãn của Odoo chuyển
> sang bản dịch trong ngoặc ở trên, còn **tên menu vẫn là tiếng Anh** (chúng
> không có bản dịch trong cơ sở dữ liệu). Nhãn **Video Link** thì không đổi ở
> cả hai ngôn ngữ.

## 2.1. Trước khi đọc tiếp

> ### ⚠️ Hãy ĐỌC LẠI mọi câu trong biên bản trước khi dùng
>
> Biên bản do máy dựng ra là **bản nháp**, không phải văn bản chính thức.
> Ba điều dưới đây bạn phải biết trước khi tin nội dung của nó:
>
> #### 1. Máy vẫn có thể "nghe ra" những câu KHÔNG AI TỪNG NÓI
>
> Khi một đoạn ghi âm gần như im lặng — người dự đang nghe, đang suy nghĩ,
> hoặc micro để xa — bộ bóc băng có xu hướng **tự bịa ra một câu trôi chảy,
> đúng ngữ pháp, nghe rất thuyết phục**. Đây là đặc tính của loại công nghệ
> này, không phải trục trặc nhất thời.
>
> Đã gặp thật: trong một cuộc gọi thử, hai người chỉ **đếm "một… hai… ba…
> bốn"**, còn lại là im lặng. Biên bản nhận được là một câu hoàn chỉnh về một
> chuyện **hoàn toàn khác**, có cả tên riêng của một người không hề có mặt.
>
> Hệ thống nay **chặn được phần lớn** loại này: đoạn quá nhỏ tiếng bị bỏ
> trước khi bóc băng, và một số câu bịa quen thuộc bị lọc khỏi kết quả. Nhưng
> **không chặn được hết** — bộ chặn hoạt động theo **độ to**, nên một tiếng ồn
> *to mà vô nghĩa* (tiếng quạt, tiếng máy, tiếng rít) vẫn lọt qua và vẫn có
> thể sinh ra một câu bịa.
>
> #### 2. Chưa ai đo được máy nghe tiếng Việt đúng tới đâu
>
> Chưa có phép đo nào trên một cuộc họp thật của cơ quan. Điều đã kiểm chứng
> chỉ là máy **trả về chữ có dấu câu và có viết hoa** — đẹp hơn, **không**
> đồng nghĩa với **đúng hơn**.
>
> #### 3. Vì vậy, cách dùng an toàn không đổi
>
> * **Luôn đọc lại và sửa biên bản trước khi gửi đi hoặc lưu hồ sơ.** Lưu ý:
>   phần chữ trên phiếu là **chỉ đọc**, không sửa tại chỗ được — bạn phải chép
>   ra một văn bản khác rồi sửa ở đó (xem
>   [2.8](#28-kết-quả-xuất-hiện-ở-đâu)).
> * **Cảnh giác nhất với những dòng nằm ở đoạn ít người nói** — đầu buổi,
>   cuối buổi, lúc chờ nhau.
> * **Tên người, con số, số hiệu văn bản phải kiểm lại bằng nguồn khác.** Đây
>   đúng là loại chi tiết mà máy hay bịa nhất.

Ngoài ra, những điểm sau **chưa được kiểm chứng** và có thể khác với mô tả:

* Chuỗi thao tác đầy đủ của một cuộc họp thật — bật ghi âm, tạm dừng, ghi
  tiếp, kết thúc, rồi đọc kết quả — **chưa ai bấm tay từ đầu đến cuối** trong
  đợt phát triển gần nhất. Phần giao diện đã được kiểm bằng test tự động;
  phần bóc băng và tóm tắt thì **chưa có lượt chạy thật nào**.
* **Độ chính xác tiếng Việt vẫn chưa đo được** (xem điểm 2 ở trên).
* Mốc thời gian `[phút:giây]` lấy từ **chính đồng hồ của máy đã ghi âm**, nên
  thứ tự trước/sau là đáng tin. Đổi lại, nó chỉ **chính xác tới khoảng nửa
  phút**: mỗi lượt nói được ghi mốc theo đoạn ghi âm chứa nó.
* Ngưỡng của bộ chặn khoảng lặng và bộ lọc câu bịa **chưa hiệu chỉnh trên dữ
  liệu thật** — chúng được đặt bằng vài tệp âm thanh thử nghiệm, chưa phải
  bằng bản ghi của một phòng họp thật với micro thật. Nếu bạn thấy một đoạn
  mình có nói mà biên bản để trống, hãy báo quản trị viên.
* Với cuộc họp dài, **chưa ai đo** phần tóm tắt mất bao lâu. Một cuộc họp hai
  tiếng có thể mất rất lâu.
* Một cuộc họp **định kỳ** thật (lặp lại hàng tuần) và trường hợp **hai cuộc
  họp cùng một phòng chồng giờ nhau** mới chỉ được kiểm bằng test tự động,
  chưa chạy thật qua nhiều tuần.

## 2.2. Tính năng này làm gì

Khi một cuộc họp trực tuyến đang diễn ra trong **phòng họp** (xem
[2.3](#23-phòng-họp-trực-tuyến-và-mục-họp)), hệ thống có thể:

1. **Thu tiếng của từng người dự** — mỗi máy tự thu micro của chính người
   ngồi trước máy đó. Nhờ vậy biên bản biết **ai** nói câu nào, chứ không
   phải đoán từ một luồng tiếng đã trộn.
2. **Bóc băng** thành văn bản có gán tên và mốc thời gian.
3. **Tóm tắt** thành các mục **Tổng quan**, **Biên bản chi tiết**, **Ý
   chính**, **Rủi ro**, cùng hai bảng **Công việc** và **Quyết định**.
4. **Ghi kết quả vào một phiếu riêng** tên là *Bản ghi cuộc họp*. Kết quả
   **không** được đăng vào phần trao đổi (chatter) của cuộc họp, và **không**
   hiện lại trong cửa sổ cuộc gọi — xem
   [2.8](#28-kết-quả-xuất-hiện-ở-đâu) để biết đường tới nó.

## 2.3. Phòng họp trực tuyến và mục "Họp"

**Ghi âm chỉ tồn tại trong phòng họp.** Phòng họp là một kênh trong Discuss
được gắn với một cuộc họp trong Lịch. Kênh chat thường và tin nhắn trực tiếp
**không bao giờ** ghi âm được, kể cả khi đang có một cuộc gọi diễn ra trong
đó — nút *Bật ghi âm biên bản* đơn giản là không xuất hiện.

### Phòng họp nằm ở đâu trong thanh bên

Mở ứng dụng **Discuss**. Thanh bên trái nay có **ba** mục, theo thứ tự:

| Thứ tự | Mục | Chứa gì |
|---|---|---|
| 1 | **Channels** | Kênh chat thường của cơ quan, phòng ban |
| 2 | **Họp** | **Phòng họp trực tuyến** |
| 3 | **Direct messages** | Tin nhắn trực tiếp giữa hai người / nhóm nhỏ |

Trước đây phòng họp nằm lẫn trong **Direct messages**; nay chúng có mục riêng.
Mục **Họp** **luôn hiện, kể cả khi bạn chưa có phòng nào** — vì lối tạo phòng
nhanh nằm ngay trong tiêu đề của nó.

### Tạo phòng họp — ba cách

**Cách 1 — nút "Họp ngay" (dấu +) ở tiêu đề mục "Họp".**

> ⚠️ **Nút này CHỈ HIỆN KHI BẠN RÊ CHUỘT vào hàng chữ "Họp".** Không rê chuột
> thì hàng đó trông như không có nút nào. Đây là cách bày trí chung của
> Discuss — bánh răng của mục **Channels** cũng chỉ hiện khi rê chuột — chứ
> không phải lỗi. Nút cũng **không có** khi thanh bên đang ở chế độ thu gọn.

Bấm dấu **+** mở ra một hộp thoại tên **Họp ngay**, đã điền sẵn:

* **Tên** cuộc họp: *Họp ngay* (sửa lại được ngay tại chỗ);
* **Bắt đầu**: đúng thời điểm hiện tại;
* **Kết thúc**: một giờ sau;
* ô **Phòng họp trực tuyến**: **đã tích sẵn**.

Bấm lưu là có phòng. Nếu bạn không dùng được chuột để rê (hoặc chỉ đơn giản
là không tìm thấy nút), hãy dùng cách 2 — nó tới được hoàn toàn bằng bàn phím.

**Cách 2 — trang "Quản lý cuộc họp".** Vào **Discuss → Quản lý cuộc họp**,
bấm **New**, điền thông tin cuộc họp và tích ô **Phòng họp trực tuyến**. Xem
mục [2.4](#24-trang-quản-lý-cuộc-họp).

**Cách 3 — ứng dụng Lịch.** Tạo hoặc mở một cuộc họp như bình thường. Trên
form cuộc họp, tìm hàng có nhãn **Video Link**. Ngay **bên phải ô nhập đường
dẫn** của hàng đó là dòng chữ **Phòng họp trực tuyến** kèm một **ô vuông tích
được** — bấm vào chính dòng chữ đó cũng tích được ô.

> Nhãn của hàng là **Video Link**. Nếu bạn từng đọc tài liệu cũ ghi *Meeting
> URL* thì đó là tên trong cơ sở dữ liệu, không phải chữ hiện trên form.

Tích ô đó rồi lưu. Hệ thống tạo phòng trong Discuss và tự đưa vào đó những
người có tên trong danh sách dự của cuộc họp.

> **Cuộc họp định kỳ dùng CHUNG một phòng cho cả chuỗi.** Tạo phòng cho một
> buổi trong chuỗi họp lặp lại thì mọi buổi khác của chuỗi dùng đúng phòng đó.
> Vì vậy trong phòng của một cuộc giao ban hàng tuần, bạn sẽ thấy **lịch sử
> ghi âm của nhiều buổi khác nhau** nằm chung — đó là bình thường. Hệ thống
> tự chọn đúng buổi **đang diễn ra** khi bạn bật ghi âm.

### ⚠️ Bỏ tích ô "Phòng họp trực tuyến" KHÔNG xoá phòng

Đây là điểm dễ hiểu nhầm nhất của mục này, nên nói thẳng:

* Ô này **chỉ có tác dụng một chiều: tích để TẠO.**
* Khi phòng đã tồn tại, ô trở thành **chỉ đọc** — bạn sẽ thấy nó bị mờ, không
  bỏ tích được. Đó là chủ ý: nếu để bỏ tích mà phòng vẫn còn, ô sẽ tự bật lại
  ở lần mở sau và giao diện thành ra nói dối.
* Lý do không cho gỡ phòng bằng một cái tích: **phòng giữ toàn bộ lịch sử ghi
  âm và biên bản** của những lần họp trước. Gỡ nó đi là bỏ rơi cả đống bản ghi
  trỏ vào một kênh không còn ai dùng, mà không có cảnh báo nào.

**Muốn bỏ phòng thật sự thì xoá cuộc họp** trong Lịch hoặc ở trang *Quản lý
cuộc họp* — đường đó rõ ràng hơn và hệ thống có hỏi xác nhận sẵn. Đọc tiếp
mục [2.4](#24-trang-quản-lý-cuộc-họp) về việc bản ghi cũ ra sao sau khi xoá.

### ⚠️ Trước đây ghi âm được ở kênh thường — nay thì không. Chuyển thế nào

Đây là thay đổi ảnh hưởng tới **cách làm hàng ngày**, nên nói rõ:

* **Trước bản này:** đang gọi nhau trong bất kỳ kênh nào — kênh phòng ban,
  kênh `general`, tin nhắn trực tiếp — là bấm được *Bật ghi âm biên bản*.
* **Từ bản này:** nút đó **chỉ có trong phòng họp**. Ở kênh thường nó không
  xuất hiện, kể cả khi cuộc gọi đang diễn ra.

**Không có cách nào biến một cuộc gọi đang diễn ra thành phòng họp.** Tích ô
*Phòng họp trực tuyến* trên một cuộc họp bao giờ cũng tạo ra một **kênh mới**;
nó không nhận cuộc gọi đang chạy ở kênh cũ về mình. Vì vậy khi năm người đang
gọi trong `general` mà muốn có biên bản, trình tự đúng là:

1. **Một người tạo cuộc họp** — nhanh nhất là nút **Họp ngay**, hoặc vào
   **Discuss → Quản lý cuộc họp** rồi bấm **New**.
2. **Mời đủ người dự** (xem cảnh báo ngay dưới) và **lưu**.
3. **Mọi người thoát cuộc gọi cũ** và vào cuộc gọi trong phòng vừa tạo.
4. Người **chủ trì** bấm *Bật ghi âm biên bản* — xem
   [2.5](#25-bật-ghi-âm).

> ⚠️ **Phòng tạo bằng "Họp ngay" lúc đầu CHỈ CÓ MÌNH BẠN.** Hộp thoại *Họp
> ngay* điền sẵn tên, giờ và ô phòng họp, nhưng **không** điền sẵn người dự
> nào ngoài chính bạn. Lưu xong mà không làm gì thêm thì bạn có một phòng
> họp rỗng và mọi người vẫn đang ở kênh cũ.
>
> **Cách thêm người:** mở cuộc họp ra, ở **cột bên phải** của form có dòng
> đếm dạng **`1 guests`** và ngay dưới là ô nhập người dự (khi trống nó gợi ý
> *Select attendees…*). Gõ tên từng người rồi **lưu** — hệ thống tự đưa họ
> vào phòng trong Discuss. Người được thêm sẽ thấy phòng xuất hiện trong mục
> **Họp** của họ.

**Bản ghi cũ không mất gì.** Những biên bản đã tạo hồi còn ghi âm được ở kênh
thường vẫn nằm nguyên ở *Lịch sử cuộc họp*; cột **Cuộc họp** của chúng để
trống, và đó là bình thường — xem [2.4](#24-trang-quản-lý-cuộc-họp).

## 2.4. Trang "Quản lý cuộc họp"

Vào **Discuss → Quản lý cuộc họp**. Trang này để **tra cứu, tạo và sửa cuộc
họp** mà không phải rời ứng dụng Discuss. Nó mở ở **danh sách** trước (khác
với ứng dụng Lịch, nơi lịch mở trước), và có sẵn các chế độ xem *danh sách /
lịch / kanban*.

**Mọi người dùng nội bộ đều vào được trang này** — không cần quyền đặc biệt.

### ⚠️ Trang này hiển thị lịch họp của CẢ CƠ QUAN, không riêng của bạn

Đây là thay đổi thật về thứ bạn **tìm thấy được**, nên nói rõ để văn phòng
khỏi bất ngờ:

* Menu **Lịch công tác tuần** (trong ứng dụng Calendar) **đã lọc sẵn**, chỉ
  hiện những cuộc họp được đánh dấu là lịch công tác tuần.
* **Quản lý cuộc họp** thì **không lọc gì cả**. Bạn thấy mọi cuộc họp trong hệ
  thống mà **độ mật của bạn cho phép xem**.

Việc chặn theo độ mật vẫn nguyên như cũ: cuộc họp ở mức cao hơn mức được cấp
của bạn thì bạn không thấy dòng nào cả. Nhưng những cuộc họp mức **Thường**
của đơn vị khác — trước đây bạn không có menu nào dẫn tới — nay nằm ngay
trong danh sách này. Nếu một cuộc họp không nên để người ngoài đơn vị đọc
tiêu đề, **hãy đặt độ mật cho nó**, đừng trông cậy vào việc không ai tìm ra.

### Cuộc họp đánh dấu "riêng tư" hiện thành "Busy"

Cuộc họp mà người khác đặt ở chế độ riêng tư (*Private*) và bạn **không** có
tên trong danh sách dự thì:

* cột tiêu đề hiện đúng chữ **`Busy`**, không phải tên thật của cuộc họp;
* các cột **Độ mật**, **Phòng họp**, **Đơn vị chủ trì** để **trống**.

Bạn vẫn thấy **có một cuộc họp ở khung giờ đó** — đây là hành vi sẵn có của
Odoo, để người khác biết người ta đang bận mà không đọc được nội dung. Dòng
`Busy` **không phải lỗi dữ liệu**, đừng đi hỏi văn thư vì sao cuộc họp mất
tên.

### ⚠️ Trang này KHÔNG sửa hàng loạt được — và đó là chủ ý

Chọn nhiều dòng rồi sửa một ô để áp cho tất cả (multi-edit) **đã bị tắt** ở
trang này. Muốn đổi gì thì **mở từng cuộc họp ra sửa trên form**.

Lý do: đây là cửa vào của **mọi** người dùng nội bộ, và sửa hàng loạt ở đây là
một cái bẫy hai cú click. Chọn-tất-cả 40 cuộc họp rồi sửa một ô:

* đổi **Độ mật** thành *Tuyệt mật* → cả 40 cuộc họp **biến mất khỏi tầm nhìn
  của chính người vừa bấm**, và không có nút hoàn tác;
* đổi **Bắt đầu** / **Kết thúc** / **Phòng họp** → dời lịch 40 cuộc họp của
  người khác bằng một ô nhập.

Riêng cột **Độ mật** còn được khoá **chỉ đọc** ngay trên danh sách, thêm một
lớp nữa cho đúng thứ nguy hiểm nhất.

### Xoá cuộc họp: bản ghi và biên bản KHÔNG mất

Xoá một cuộc họp khỏi Lịch **không xoá** các bản ghi đã tạo trong phòng của
nó. Bản ghi và biên bản vẫn còn nguyên ở trang *Lịch sử cuộc họp*; chỉ có cột
**Cuộc họp** của chúng trở thành **trống**.

> **Cột "Cuộc họp" trống là bình thường, không phải lỗi.** Có hai đường dẫn
> tới nó: (a) bản ghi được tạo từ trước bản này, khi ghi âm còn làm được ở
> cuộc gọi không có lịch; (b) cuộc họp đã bị xoá khỏi Lịch sau khi họp xong.
> Trong cả hai trường hợp, cột **Kênh** vẫn cho biết bản ghi thuộc phòng nào.

## 2.5. Bật ghi âm

Trong cửa sổ cuộc gọi của một **phòng họp**, khi chưa có ai ghi âm, người
được phép sẽ thấy nút:

> **Bật ghi âm biên bản**

**Chỉ người chủ trì cuộc họp trong Lịch mới thấy và bấm được nút này.** Người
dự khác không thấy nút — hệ thống cố ý không mời họ bấm một nút sẽ báo lỗi.

Nếu bạn không phải người chủ trì mà vẫn gọi được tới máy chủ, hệ thống báo:

> *Chỉ chủ phòng mới bật được ghi âm.*

**"Chủ phòng" là ai.** Ngay khi người đầu tiên vào cuộc gọi trong một phòng
họp, hệ thống chốt chủ phòng vào **người chủ trì ghi trong Lịch** — bất kể ai
vào trước. Một chuyên viên vào sớm hai phút **không** trở thành chủ phòng.

> ⚠️ Chủ phòng được chốt **một lần** lúc cuộc gọi bắt đầu và chỉ được xoá khi
> mọi người rời hết. Nếu người chủ trì của cuộc họp **bị đổi trong lúc cuộc
> gọi đang diễn ra**, hệ thống **không** tính lại — và kết quả là **không ai
> bật được ghi âm** cho tới khi cuộc gọi kết thúc rồi bắt đầu lại. Đây là
> hướng an toàn (thà không ghi còn hơn ghi nhầm quyền), nhưng nếu bạn vừa đổi
> người chủ trì thì hãy để mọi người thoát cuộc gọi rồi vào lại.

Nếu cuộc họp trong Lịch bị **xoá trắng ô người chủ trì**, hệ thống lùi về
người vào cuộc gọi đầu tiên, và người đó cũng **không** bật được ghi âm — báo
*Chỉ người chủ trì cuộc họp mới bật được ghi âm.* Hãy điền lại người chủ trì.

### ⚠️ Người chủ trì phải có tên trong danh sách dự, nếu không cả phòng tắc

Đây là cái bẫy hay gặp nhất khi **văn thư đặt lịch hộ lãnh đạo**, nên nói
trước:

Khi bạn tạo cuộc họp và đặt ô **Organizer** (thẻ **Options**) là một người
khác, hệ thống **không** tự thêm người đó vào danh sách dự. Danh sách dự mặc
định chỉ có **chính bạn**. Mà thành viên phòng họp trong Discuss lấy đúng từ
danh sách dự — nên phòng sinh ra **không có mặt người chủ trì**.

Lúc đó, ngay khi có người vào cuộc gọi, quyền bật ghi âm được chốt vào người
chủ trì — người đang **không ở trong phòng**. Kết quả là **không ai bật được
ghi âm**, và hai bên nhận hai thông báo trông chẳng liên quan gì nhau:

| Ai bấm | Thông báo nhận được |
|---|---|
| **Người chủ trì** (lãnh đạo) | *Bạn không thuộc cuộc gọi này.* — và thường thì họ còn **không nhìn thấy phòng** trong mục **Họp**, vì họ không phải thành viên. |
| **Người đặt lịch** (văn thư) đang ở trong phòng | *Chỉ chủ phòng mới bật được ghi âm.* |

Không màn hình nào nói ra nguyên nhân thật. Nếu gặp đúng cặp thông báo này,
đừng đi tìm lỗi ở chỗ khác.

**Cách gỡ:** mở cuộc họp ra, **thêm người chủ trì vào danh sách dự** (ô nhập
người dự ở cột phải, xem [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp)) rồi
**lưu**. Hệ thống đưa họ vào phòng ngay, và họ bật được ghi âm mà không cần
ai thoát cuộc gọi.

**Cách tránh:** hễ đặt **Organizer** là người khác thì **thêm luôn người đó
vào danh sách dự** trong cùng lần lưu.

Các thông báo khác có thể gặp:

| Thông báo | Nghĩa là |
|---|---|
| *Chỉ ghi âm được trong phòng họp.* | Kênh này không đứng sau cuộc họp nào trong lịch — không cách nào bật ghi âm ở đây, kể cả khi đang có người gọi cho nhau trong kênh. |
| *Chưa có cuộc gọi nào đang diễn ra trên kênh này.* | Phòng họp đúng, nhưng **chưa ai bấm vào cuộc gọi**. Vào cuộc gọi trước rồi mới bật ghi âm được. |
| *Cuộc gọi này đang được ghi âm rồi.* | Đã có người bật trước bạn. Mỗi cuộc gọi chỉ có một bản ghi tại một thời điểm. |
| *Bạn không thuộc cuộc gọi này.* | Bạn không có trong kênh của cuộc gọi. |
| *Cuộc họp ở mức "…" vượt ngưỡng cho phép ghi âm. Liên hệ quản trị viên nếu cần thay đổi.* | Độ mật của cuộc họp cao hơn mức quản trị viên cho phép ghi âm. Mặc định chỉ cho phép mức **Thường**. |

## 2.6. Băng thông báo và các nút điều khiển

Ngay khi ghi âm bắt đầu, **mọi người đang trong cuộc gọi** đều thấy một băng
thông báo có chấm đỏ. Chữ trên băng **khác nhau tuỳ bạn là ai**:

| Bạn là | Đang ghi | Đang tạm dừng |
|---|---|---|
| **Chủ phòng** | *Đang ghi âm biên bản.* | *Ghi âm đang tạm dừng.* |
| **Người dự** | *Cuộc họp đang được ghi âm để tạo biên bản.* | *Ghi âm đang tạm dừng. Cuộc họp vẫn tiếp tục.* |

**Băng này không tắt được và không ẩn được.** Đó là chủ ý: nó chính là cách hệ
thống bảo đảm mọi người biết mình đang bị ghi âm. Không có nút "×" nào, và
**người dự không có nút nào cả** — ghi âm là bắt buộc, việc điều khiển thuộc
về chủ phòng.

**Chủ phòng** thấy thêm các nút ngay trên băng:

| Nút | Làm gì |
|---|---|
| **Tạm dừng** | Ngừng thu biên bản. **Cuộc gọi không bị đụng tới** — mọi người vẫn nghe và nói với nhau bình thường, chỉ là phần này không vào biên bản. |
| **Ghi tiếp** | Thu trở lại (thay chỗ nút *Tạm dừng* khi đang dừng). |
| **Kết thúc** | Kết thúc ghi âm **cho cả cuộc họp** và bắt đầu bóc băng, tóm tắt. |

Ghi âm cũng **tự kết thúc** khi người cuối cùng rời cuộc gọi — không có ai
trong phòng thì cũng không còn ai bấm được nút *Kết thúc*.

Băng cũng hiện với người **vào họp muộn** và với người **tải lại trang giữa
cuộc họp**: khi vào cuộc gọi, máy tự hỏi lại máy chủ xem cuộc gọi này có đang
được ghi hay không. Nói cách khác, **hễ bạn đang trong một cuộc gọi đang được
ghi thì bạn luôn thấy băng này**, bất kể bạn vào lúc nào. Người đã **rời cuộc
gọi** thì không thấy nữa.

Ngược lại, băng **chỉ nói về cuộc gọi bạn đang mở**. Nếu một cuộc họp khác —
ở một phòng khác mà bạn cũng là thành viên — đang được ghi âm, cuộc gọi hiện
tại của bạn **không** hiện băng và micro của bạn **không** bị thu cho cuộc họp
đó.

### Các đoạn tạm dừng được ghi lại thành số

Mỗi lần chủ phòng bấm *Tạm dừng* rồi *Ghi tiếp*, hệ thống ghi lại khoảng đó.
Trên phiếu *Bản ghi cuộc họp* (mục [2.8](#28-kết-quả-xuất-hiện-ở-đâu)) sẽ có
dòng **Đoạn không được ghi**, ví dụ:

> *2 đoạn không được ghi · tổng 3 phút 28 giây*

Nếu cuộc họp **kết thúc trong lúc đang tạm dừng**, dòng đó nói riêng ra:

> *1 đoạn không được ghi tới hết cuộc họp (đang tạm dừng lúc kết thúc)*

Câu thứ hai **không phải** một khoảng dừng 0 giây — nó nghĩa là **toàn bộ phần
đuôi cuộc họp không hề được ghi**. Đây đúng là hai câu trông giống nhau mà
nghĩa ngược nhau, nên đọc kỹ trước khi kết luận biên bản đã đầy đủ.

## 2.7. Tắt micro KHÔNG dừng việc ghi biên bản

> ⚠️ **Đọc kỹ mục này trước khi tin rằng tắt micro là đủ để nói riêng.**
> Bản hướng dẫn trước đây nói ngược lại. Câu đó **sai**, và đây là chỗ sửa.

Nút **tắt tiếng** của cuộc gọi và **máy ghi biên bản** là hai thứ riêng biệt:

* Nút tắt tiếng chỉ ngắt tiếng của bạn **tới tai người khác trong cuộc gọi**.
* Máy ghi biên bản **mở một đường thu micro riêng của nó**, không dùng chung
  đường tiếng của cuộc gọi. Đường riêng đó **không** bị nút tắt tiếng đụng
  tới.

Hậu quả, nói thẳng: **bạn tắt micro rồi quay sang nói riêng với người ngồi
cạnh, câu đó vẫn được thu, vẫn được bóc băng, vẫn vào biên bản dưới tên bạn.**
Trên màn hình không có gì báo cho bạn biết điều đó — băng thông báo chấm đỏ
vẫn hiện y như trước, vì nó nói về cuộc họp chứ không nói về micro của bạn.

Thứ duy nhất còn lọc là **ngưỡng độ to**: một mẩu tiếng 30 giây mà **hoàn
toàn không có âm thanh nào vượt ngưỡng** thì bị bỏ, không gửi đi. Chỉ cần
trong 30 giây đó có tiếng nói — kể cả nói nhỏ, kể cả đang tắt micro — là cả
mẩu được gửi đi bóc băng.

**Muốn chắc chắn không bị thu thì có đúng hai cách:**

| Bạn là | Cách chắc chắn |
|---|---|
| **Chủ phòng** | Bấm **Tạm dừng** trên băng thông báo. Cuộc gọi không bị đụng tới, mọi người vẫn nghe nói bình thường, chỉ là phần đó không vào biên bản. Bấm **Ghi tiếp** khi xong. |
| **Người dự** | **Rời cuộc gọi.** Người dự **không có nút nào** trên băng thông báo — không có *Tạm dừng*, không có *Kết thúc*. Vào lại khi xong việc riêng. |

Nói cách khác: việc tạm ngưng ghi âm nằm trong tay **chủ phòng**, không nằm
trong tay từng người. Nếu bạn cần một khoảng không vào biên bản, hãy **đề
nghị chủ phòng bấm *Tạm dừng*** — mọi khoảng dừng đều được ghi lại thành số
trên phiếu bản ghi (xem
[2.6](#26-băng-thông-báo-và-các-nút-điều-khiển)), nên đây là cách minh bạch
với cả cuộc họp chứ không phải cách lén lút.

Những đoạn quá nhỏ tiếng bị bỏ qua, không gửi đi bóc băng — và chúng **không
để lại dấu vết nào** trong biên bản. Đọc mục
[2.9](#29-vì-sao-biên-bản-có-chỗ-nhảy-cóc) trước khi kết luận là hệ thống bị
lỗi.

## 2.8. Kết quả xuất hiện ở đâu

Sau khi chủ phòng bấm **Kết thúc**, hệ thống cần **vài phút** để bóc băng và
tóm tắt. Đừng chờ kết quả xuất hiện ngay lập tức.

Kết quả **không** hiện lại trong cửa sổ cuộc gọi, và **không** được đăng vào
phần trao đổi (chatter) của cuộc họp trong Lịch — **đừng đi tìm ở đó.** Toàn
bộ kết quả được ghi thẳng vào một phiếu riêng: **Bản ghi cuộc họp**.

**Đường tới phiếu:** menu **Discuss → Lịch sử cuộc họp**, rồi chọn dòng tương
ứng để mở.

> ⚠️ Menu **Lịch sử cuộc họp** chỉ hiện cho người thuộc nhóm **Quản lý biên
> bản cuộc họp**. Người dự họp bình thường vẫn có quyền **đọc** phiếu của
> cuộc họp mình dự (mục [2.11](#211-ai-xem-được-bản-ghi)) nhưng **không có
> menu nào dẫn tới** — hãy nhờ quản trị viên gửi đường dẫn tới phiếu.

### Danh sách "Lịch sử cuộc họp"

Mỗi dòng là một lần ghi âm, với các cột **Kênh**, **Cuộc họp**, **Bắt đầu**,
**Kết thúc**, **Độ mật lúc bắt đầu**, **Trạng thái**.

**Trạng thái** có sáu giá trị, đọc theo đúng nghĩa đen:

| Trạng thái | Nghĩa là |
|---|---|
| **Đang ghi** | Cuộc họp đang diễn ra và đang được thu. |
| **Tạm dừng** | Chủ phòng đã bấm *Tạm dừng*; cuộc gọi vẫn tiếp tục. |
| **Đang xử lý** | Đã kết thúc, máy đang bóc băng và tóm tắt. Chờ. |
| **Xong** | Đã có biên bản. Mở ra đọc được. |
| **Lỗi** | Bóc băng hoặc tóm tắt hỏng. **Không tự chạy lại** — báo quản trị viên. |
| **Đã huỷ** | Bản ghi bị huỷ. |

Cột **Độ mật lúc bắt đầu** là **bản chụp tại thời điểm bật ghi âm**, không đổi
theo cuộc họp về sau. Đổi độ mật của cuộc họp sau khi đã ghi **không** làm cột
này đổi theo — nó ghi lại điều kiện thật lúc việc ghi âm được cho phép.

### Trên phiếu có gì

Đầu phiếu là ba thẻ: **BẮT ĐẦU**, **ĐỘ MẬT**, **NGƯỜI TẠO**. Dưới đó là
**Cuộc họp**, **Kênh**, **Kết thúc**, **Chủ phòng**, và dòng **Đoạn không được
ghi** nếu có tạm dừng.

Khối **Nội dung AI phân tích** chứa toàn bộ kết quả:

| Nhãn trên màn hình | Là gì |
|---|---|
| (dòng tiêu đề in đậm) | Câu tóm tắt ngắn **do máy viết**. |
| Trình phát âm thanh | Nghe lại cuộc họp — xem [2.10](#210-nghe-lại-âm-thanh-cuộc-họp). |
| **Tổng quan** | Vài dòng tóm lược, **do máy viết**. |
| **Biên bản chi tiết** | Biên bản đã được máy **viết lại và sắp xếp**. |
| **Ý chính**, **Rủi ro** | Các gạch đầu dòng **do máy rút ra**. |
| **Công việc** (bảng bên phải) | Cột **Công việc**, **Người phụ trách**, **Thời hạn**, **Mức độ**, **Thời gian trong file**. |
| **Quyết định** (bảng bên phải) | Cột **Quyết định** và **Thời gian trong file**. |

> ### ⚠️ "Biên bản chi tiết" KHÔNG phải bản bóc băng nguyên văn
>
> Đây là điều dễ hiểu nhầm nhất trên phiếu. **Mọi thứ bạn nhìn thấy trong
> khối "Nội dung AI phân tích" đều là chữ do máy viết lại**, kể cả mục mang
> tên "Biên bản chi tiết" — không có mục nào trong đó là lời nói nguyên văn.
>
> **Bản bóc băng nguyên văn có tồn tại**, nhưng nó **chỉ hiện ở chế độ nhà
> phát triển**, dưới nhãn *Nội dung cuộc họp gốc*. Người dùng thường **không
> có đường nào** tới nó. Đây là chủ ý — bản gốc bị giấu đi có mục đích.
>
> **Toàn bộ phần chữ trên phiếu là CHỈ ĐỌC.** Bạn không sửa được *Tổng quan*
> hay *Biên bản chi tiết* ngay tại chỗ — muốn hoàn thiện thành văn bản chính
> thức thì **bôi đen, sao chép ra Word** rồi sửa ở đó. Riêng hai bảng **Công
> việc** và **Quyết định** thì người thuộc nhóm *Quản lý biên bản cuộc họp*
> sửa được trực tiếp trên bảng.
>
> Hệ quả thực tế bạn phải chấp nhận: **bạn không tự đối chiếu được biên bản
> với lời nói gốc.** Cách kiểm chứng còn lại là **nghe lại âm thanh** trên
> chính phiếu này ([2.10](#210-nghe-lại-âm-thanh-cuộc-họp)), hoặc hỏi lại
> người dự. Nếu bạn cần bản nguyên văn cho hồ sơ, phải nhờ quản trị viên lấy
> ra.

### Trong lúc chờ

Khi bản ghi còn ở trạng thái **Đang xử lý**, phần kết quả được thay bằng dòng:

> **AI đang phân tích cuộc họp...**
> *Hệ thống đang bóc băng âm thanh và tóm tắt nội dung. Quá trình này có thể
> mất vài phút.*

**Nếu bạn đang mở đúng phiếu đó**, trang **tự nạp lại** khi kết quả về — bạn
không phải bấm gì. Còn nếu bạn đang ở **danh sách** *Lịch sử cuộc họp* thì
danh sách **không** tự cập nhật; bấm nút nạp lại của trình duyệt để thấy
trạng thái mới.

### ⚠️ Mẩu tiếng về muộn thì bị bỏ, KHÔNG được ghép thêm vào sau

Nếu máy của một người dự có mạng chậm, mẩu tiếng cuối cùng của họ có thể về
tới nơi **sau khi** hệ thống đã bắt đầu bóc băng. Khi đó:

* mẩu đó **không** được đưa vào biên bản;
* hệ thống **không** dựng lại biên bản, **không** đăng thêm bản nào;
* trên màn hình **không có dấu hiệu gì cả** — biên bản trông liền mạch.

Hệ thống đợi **10 giây** sau khi bấm *Kết thúc* rồi mới chốt, nên chuyện này
chỉ xảy ra với máy chậm hơn thế. Nhưng đã xảy ra thì phần cuối lời của người
đó **mất luôn**, và cách duy nhất để biết là **đọc lại đoạn cuối biên bản**
hoặc hỏi chính người đó. Nhật ký hệ thống chỉ ghi lại **một phần** các trường
hợp này, nên đừng trông cậy vào việc quản trị viên sẽ tự phát hiện ra.

Vì vậy: **đừng bấm *Kết thúc* ngay khi câu cuối vừa dứt.** Chờ vài giây.

## 2.9. Vì sao biên bản có chỗ nhảy cóc

Trước khi đưa một đoạn ghi âm đi bóc băng, hệ thống **nghe thử** đoạn đó. Nếu
đoạn đó gần như không có tiếng người — người dự đang nghe, đang suy nghĩ,
micro để xa, hoặc phòng chỉ có tiếng nền — hệ thống **bỏ hẳn**.

**Đoạn bị bỏ như vậy không để lại gì cả trong biên bản:** không có dòng chữ
nào, và **cũng không** có ghi chú nào báo là có chỗ bị bỏ. Nhìn vào biên bản
bạn chỉ thấy một khoảng **nhảy cóc** về thời gian, mà không có lời giải thích
nào ở giữa.

### Vì sao cố ý làm như vậy

| Nếu làm khác đi | Hậu quả |
|---|---|
| In một dòng cáo lỗi cho mỗi đoạn im lặng | Một cuộc họp bình thường có **rất nhiều** quãng lặng. Biên bản sẽ đầy những lời cáo lỗi ở đúng những chỗ **không có gì để cáo lỗi cả**. |
| Cứ đưa đoạn im lặng đi bóc băng | Đây chính là cách chắc chắn nhất khiến máy **bịa ra một câu không ai nói** (xem [2.1](#21-trước-khi-đọc-tiếp)). |

### Khi nào điều này ĐÁNG lo

Nếu bạn nhớ rõ mình **có nói** trong khoảng thời gian bị nhảy cóc mà biên bản
không có dòng nào, thì đó là dấu hiệu hệ thống **nghe hụt** — thường vì micro
để quá xa, âm lượng micro đặt quá thấp, hoặc phòng quá ồn.

Việc cần làm:

1. Kiểm tra lại micro (khoảng cách, âm lượng đầu vào).
2. **Báo quản trị viên**, nói rõ khoảng thời gian nào và của ai. Ngưỡng "thế
   nào là có tiếng người" hiện được đặt bằng **âm thanh thử nghiệm chứ chưa
   phải phòng họp thật**, nên chính những báo cáo kiểu này là thứ dùng để
   chỉnh nó.
3. Trong lúc chờ, **nghe lại âm thanh** trên phiếu để lấy đúng nội dung đoạn
   đó ([2.10](#210-nghe-lại-âm-thanh-cuộc-họp)).

## 2.10. Nghe lại âm thanh cuộc họp

Trên phiếu *Bản ghi cuộc họp*, ngay dưới dòng tiêu đề, có một **trình phát âm
thanh**. Bấm nút phát là nghe lại được **toàn bộ cuộc họp đã được ghi**, đã
trộn tiếng của mọi người theo đúng mốc thời gian.

Đây là cách kiểm chứng đáng tin nhất khi bạn nghi biên bản ghi sai — vì bản
bóc băng nguyên văn thì bạn không xem được
([2.8](#28-kết-quả-xuất-hiện-ở-đâu)).

> ### ⚠️ Âm thanh cuộc họp được GIỮ LẠI, không tự xoá
>
> Trong bản hiện tại, **tệp âm thanh của cuộc họp nằm lại trên máy chủ vô thời
> hạn**. Không có tác vụ nào tự xoá nó, kể cả khi ô cấu hình *Giữ audio
> (ngày)* của quản trị viên đang để **0** — ô đó hiện **không điều khiển gì
> cả** (xem phần dành cho quản trị viên).
>
> Nói cách khác: **mọi lời nói trong một cuộc họp đã ghi âm đều còn nghe lại
> được**, bởi bất kỳ ai có quyền đọc bản ghi đó
> ([2.11](#211-ai-xem-được-bản-ghi)). Hãy cân nhắc điều này **trước khi bật
> ghi âm**, không phải sau.
>
> Nếu cơ quan cần chính sách xoá âm thanh sau N ngày, đó là việc phải **yêu
> cầu quản trị viên dọn thủ công** — hiện chưa có cơ chế tự động.

## 2.11. Ai xem được bản ghi

Bạn xem được biên bản của một cuộc họp nếu bạn **là thành viên của kênh (phòng
họp)** đó, **hoặc** là **người dự** cuộc họp trong Lịch.

Điều kiện "thành viên của kênh" là **rộng hơn** "có tên trong danh sách mời":
nếu phòng họp được tạo từ một kênh phòng ban đông người, mọi thành viên kênh
đó đều đọc được biên bản, kể cả người không dự họp. Hãy tính tới điều này khi
chọn nơi tổ chức cuộc họp.

Ngoài ra, người thuộc nhóm **Quản lý biên bản cuộc họp** xem được tất cả, và
là những người duy nhất **sửa hoặc xoá** được bản ghi. Người dùng thường chỉ
có quyền **đọc**.

## 2.12. Xử lý nhanh

| Hiện tượng | Nên làm |
|---|---|
| Không thấy mục **Họp** trong thanh bên | Mục này luôn hiện, kể cả khi rỗng. Nếu không thấy, kiểm tra xem thanh bên có đang **thu gọn** không, và tải lại trang. |
| Không thấy nút **+ Họp ngay** | **Rê chuột vào hàng chữ "Họp"** — nút chỉ hiện khi rê. Ở thanh bên thu gọn thì không có nút; dùng **Discuss → Quản lý cuộc họp** thay thế. Xem [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp). |
| Bỏ tích **Phòng họp trực tuyến** mà phòng vẫn còn | **Đúng như thiết kế** — ô chỉ tạo, không xoá. Muốn bỏ phòng thì xoá cuộc họp. Xem [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp). |
| Trong danh sách cuộc họp có dòng tên **`Busy`** | Cuộc họp riêng tư của người khác. **Không phải lỗi.** Xem [2.4](#24-trang-quản-lý-cuộc-họp). |
| Không sửa được nhiều cuộc họp cùng lúc | **Đúng như thiết kế.** Mở từng cuộc họp ra sửa. Xem [2.4](#24-trang-quản-lý-cuộc-họp). |
| Không xoá được nhiều cuộc họp cùng lúc | **Đúng như thiết kế.** Mở từng cuộc họp ra rồi xoá trên form. Xem [2.4](#24-trang-quản-lý-cuộc-họp). |
| Đang gọi ở kênh thường, muốn ghi biên bản | Không có nút, và **không chuyển được cuộc gọi đó thành phòng họp**. Phải tạo cuộc họp, mời người, rồi cả nhóm sang phòng mới. Xem [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp). |
| Vừa tạo phòng bằng **Họp ngay** mà không ai vào | Phòng mới **chỉ có mình bạn**. Mở cuộc họp, thêm người vào danh sách dự rồi lưu. Xem [2.3](#23-phòng-họp-trực-tuyến-và-mục-họp). |
| Cột **Cuộc họp** của một bản ghi để trống | Bình thường: bản ghi cũ, hoặc cuộc họp đã bị xoá khỏi Lịch. Biên bản **không** mất. Xem [2.4](#24-trang-quản-lý-cuộc-họp). |
| Không thấy nút **Bật ghi âm biên bản** | Kênh này không phải phòng họp; hoặc bạn không phải người chủ trì; hoặc cuộc gọi đã được ghi rồi (băng thông báo đang hiện); hoặc bạn chưa vào cuộc gọi. Xem [2.5](#25-bật-ghi-âm). |
| Bấm bật, báo *Chỉ chủ phòng…* | Bạn không phải người chủ trì cuộc họp trong Lịch — nhờ người chủ trì bật. Nếu người chủ trì vừa được đổi, hãy để mọi người thoát cuộc gọi rồi vào lại. Xem [2.5](#25-bật-ghi-âm). |
| Người chủ trì báo *Bạn không thuộc cuộc gọi này.* còn người đặt lịch báo *Chỉ chủ phòng…* | Người chủ trì **không có tên trong danh sách dự** nên không ở trong phòng. Thêm họ vào danh sách dự rồi lưu. Xem [2.5](#25-bật-ghi-âm). |
| Tắt micro để nói riêng — có vào biên bản không | **CÓ.** Tắt micro **không** dừng máy ghi. Nhờ chủ phòng bấm **Tạm dừng**, hoặc rời cuộc gọi. Xem [2.7](#27-tắt-micro-không-dừng-việc-ghi-biên-bản). |
| Là chủ phòng nhưng không thấy nút **Tạm dừng** / **Kết thúc** | Bạn đang xem băng ở tư cách người dự — kiểm tra lại xem cuộc gọi có đúng là phòng họp bạn chủ trì không. |
| Họp xong lâu rồi mà bản ghi vẫn **Đang xử lý** | Chờ thêm vài phút. Nếu vẫn vậy, báo quản trị viên — hệ thống **không tự thử lại**. |
| Bản ghi ở trạng thái **Lỗi** | Bóc băng hoặc tóm tắt hỏng. Trên giao diện **không có nút chạy lại** — báo quản trị viên. Âm thanh vẫn còn nguyên nên việc chạy lại là làm được, chỉ là phải làm từ phía kỹ thuật. |
| Muốn đối chiếu với lời nói gốc | Bản bóc băng nguyên văn **không xem được**. **Nghe lại âm thanh** trên phiếu. Xem [2.8](#28-kết-quả-xuất-hiện-ở-đâu) và [2.10](#210-nghe-lại-âm-thanh-cuộc-họp). |
| Trong biên bản có câu **không ai từng nói** | Đây là điều **đã biết trước**: máy bịa chữ ở đoạn gần im lặng. Xoá câu đó đi và sửa lại biên bản — xem [2.1](#21-trước-khi-đọc-tiếp). |
| Biên bản **nhảy cóc thời gian** | Hệ thống nghe thấy đoạn đó **không có tiếng người** nên đã bỏ. Xem [2.9](#29-vì-sao-biên-bản-có-chỗ-nhảy-cóc). |
| Bạn **chắc chắn mình có nói** mà đoạn đó không có dòng nào | Micro có thể để quá xa hoặc âm lượng quá thấp. Báo quản trị viên kèm khoảng thời gian — xem [2.9](#29-vì-sao-biên-bản-có-chỗ-nhảy-cóc). |
| Phần cuối cuộc họp bị thiếu trong biên bản | Có thể một mẩu tiếng về muộn và đã bị bỏ. Lần sau chờ vài giây rồi mới bấm **Kết thúc** — xem [2.8](#28-kết-quả-xuất-hiện-ở-đâu). |
| Biên bản viết sai từ chuyên môn | Báo quản trị viên **kèm từ đúng**. Xem phần dành cho quản trị viên. |

---

# 3. Quản lý Lịch chung & Lịch công tác tuần

## 3.1. Quản lý Lịch tập trung & Phân loại trực quan
Giao diện Lịch chung (`Calendar`) cho phép theo dõi toàn bộ các hoạt động, cuộc họp và lịch hẹn của cơ quan trên một màn hình duy nhất:
- **Lịch công tác tuần / Cấp ủy**: Được hiển thị với màu nổi bật, mặc định mở giao diện **Lịch (Calendar view)** khi vào menu *Lịch công tác tuần*.
- **Lịch tiếp công dân**: Các lịch tiếp dân đã phê duyệt tự động chuyển thành sự kiện màu xanh lá trên Lịch chung.
- **Trùng khung giờ**: Khi có nhiều cuộc họp diễn ra cùng thời điểm, thẻ sự kiện tự động hiển thị thông tin Phòng họp, Đơn vị chủ trì và Mức độ mật để cán bộ dễ dàng phân biệt.

## 3.2. Bộ lọc & Nhóm theo
Tại màn hình Lịch chung, cán bộ có thể dùng thanh Tìm kiếm (Search Bar) để:
- Lọc nhanh: **Lịch công tác tuần**, **Lịch tiếp công dân**, **Lịch Cấp ủy**.
- Nhóm theo: **Loại lịch**, **Phòng họp**, **Đơn vị chủ trì**.

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

### Ghi âm và biên bản cuộc họp

Hai menu, hai mức quyền — **đây là chủ ý, đừng gộp**:

| Menu | Ai thấy | Để làm gì |
|---|---|---|
| **`Discuss` → `Quản lý cuộc họp`** | **Mọi người dùng nội bộ** | Tạo, sửa, tra cứu cuộc họp. Không lọc theo người dùng; chỉ record rule độ mật của `aidt_calendar` chặn. |
| **`Discuss` → `Lịch sử cuộc họp`** | Chỉ nhóm **Quản lý biên bản cuộc họp** | Danh sách mọi bản ghi, kèm kênh, cuộc họp, thời điểm bắt đầu/kết thúc, độ mật lúc bắt đầu và trạng thái. |

> Menu cha hiển thị là **`Discuss`** (tiếng Anh) chứ không phải "Thảo luận":
> bản cài hiện tại chỉ bật ngôn ngữ `en_US`, nên các menu lõi của Odoo giữ
> nguyên tiếng Anh, còn chuỗi của module này là tiếng Việt cố định. Thứ tự
> thật dưới `Discuss`: **1** Discuss · **2** Channels · **3** Quản lý cuộc
> họp · **4** Lịch sử cuộc họp · **5** Configuration.

> ⚠️ **Ai tạo cuộc họp thì ai cũng được, ai đọc biên bản thì không.** Nếu bạn
> gắn nhóm quyền vào *Quản lý cuộc họp*, người dùng thường mất luôn lối tạo
> phòng họp bằng bàn phím. Ngược lại, nếu bạn **gỡ** nhóm quyền khỏi *Lịch sử
> cuộc họp*, toàn bộ biên bản của cơ quan lộ ra cho mọi người dùng nội bộ.
> Cả hai chiều đều có test phủ (`tests/test_ui_views.py`).

**Trên form một bản ghi** chỉ có đúng một nút: **Dừng ghi âm**, và nó chỉ
hiện khi bản ghi đang ở trạng thái *Đang ghi*. **Không còn** nút *Tạo lại tóm
tắt*, *Bóc băng lại*, và **không còn** danh sách *Người từ chối ghi âm* —
cơ chế "Từ chối ghi âm" đã bị gỡ khỏi sản phẩm (ghi âm trong phòng họp là bắt
buộc, xem mục [2.6](#26-băng-thông-báo-và-các-nút-điều-khiển)).

**Hai thứ chỉ hiện ở chế độ nhà phát triển:**

* Khối **Nội dung cuộc họp gốc** trên form bản ghi — bản bóc băng nguyên văn.
  Đây là lý do người dùng thường không đối chiếu được biên bản với lời nói
  gốc; nếu ai cần bản nguyên văn cho hồ sơ, bạn bật chế độ nhà phát triển rồi
  lấy ra hộ.
  > ⚠️ Nó chỉ **giấu trên giao diện**, **không chặn dữ liệu** — nội dung vẫn
  > nằm trong gói dữ liệu gửi về trình duyệt của bất kỳ ai đọc được bản ghi.
  > Muốn thật sự không cho đọc thì phải chặn ở tầng quyền, không phải ở view.
* Nút **Mock Audio (Dev)** trên băng thông báo — nạp thẳng một tệp audio vào
  bản ghi để thử chặng worker. Với người dùng thật đó là một đường **giả mạo
  lời phát biểu**, nên đừng để ai họp thật trong phiên đang bật debug.

**Thiết lập: `Settings` → `Biên bản cuộc họp`**

| Khối | Trường | Mặc định | Ghi chú |
|---|---|---|---|
| Dịch vụ AI → *Dịch vụ xử lý* | **URL dịch vụ xử lý cuộc họp** | `http://ai-worker:8000` | Worker nhận job hậu kỳ (ghép audio, bóc băng, tóm tắt). Odoo chỉ đẩy job rồi trả về ngay; kết quả quay lại bằng webhook. |
| Dịch vụ AI → *Chất lượng bóc băng* | **Model bóc băng** | `large-v3` | Tên theo cách gọi của **faster-whisper** (`large-v3`, `medium`, `small`…), **KHÔNG** phải repo Hugging Face. Điền `openai/whisper-large-v3` vào đây là lỗi *Invalid model size* và cuộc họp chuyển sang **Lỗi**. |
| Dịch vụ AI → *Chất lượng bóc băng* | **Ngôn ngữ bóc băng** | `vi` | Để **trống** = để model tự nhận dạng; chỉ dùng cho họp song ngữ. |
| Dịch vụ AI → *Chất lượng bóc băng* | **Mồi vốn từ (prompt)** | **rỗng** | **Giữ rỗng** — xem cảnh báo dưới. |
| Dịch vụ AI → *Tóm tắt* | **Model tóm tắt** | `gemma3:12b-it-qat` | Phải khớp **nguyên văn** tag của Ollama. Lệch một ký tự là 404 âm thầm. |
| Chính sách → *Độ mật tối đa* | Độ mật tối đa được ghi âm | **Thường** | Cuộc họp vượt mức này không bật được ghi âm. |
| Chính sách → *Lưu trữ audio* | **Giữ audio (ngày)** | `0` | ⚠️ **Ô này hiện KHÔNG điều khiển gì cả** — xem cảnh báo dưới. |

> ### ⚠️ "Giữ audio (ngày)" là ô CHẾT — audio KHÔNG bao giờ tự xoá
>
> Tham số `aidt_meeting.audio_retention_days` tồn tại và sửa được, nhưng
> **không có dòng mã nào trong module đọc nó để xoá audio**, và **module này
> không có tác vụ theo lịch nào** (`data/ir_cron.xml` rỗng). Đừng suy ra có
> một cron dọn dẹp chỉ vì có ô cấu hình cho nó.
>
> Hệ quả thật, đo trên `aidt_demo` ngày **12/08/2026**: `/var/lib/odoo/meetings/`
> giữ **105 thư mục cuộc họp, 898 MB**, trong đó 38 tệp `full_audio.wav` —
> mọi mẩu audio thô của mọi cuộc họp từng chạy vẫn còn nguyên. Tệp
> `full_audio.wav` còn được phục vụ qua tuyến `/aidt_meeting/audio/<id>` và
> phát thẳng trên form bản ghi, nên **bất kỳ ai đọc được bản ghi đều nghe lại
> được toàn bộ cuộc họp**, không giới hạn thời gian.
>
> **Đây là hai vấn đề, phải xử lý cả hai:**
> 1. **Quyền riêng tư / lưu trữ:** chưa có chính sách xoá. Dọn là **thao tác
>    thủ công** trên `/var/lib/odoo/meetings/` cộng các `ir.attachment` của
>    `aidt.meeting.chunk`.
> 2. **Dung lượng đĩa:** 898 MB cho một cơ sở dữ liệu demo. Trên hệ thật, hãy
>    theo dõi thư mục này.
>
> Tài liệu người dùng ([2.10](#210-nghe-lại-âm-thanh-cuộc-họp)) đã nói thẳng
> điều này với người dùng cuối. Nếu bạn dựng cơ chế xoá, hãy cập nhật cả hai
> chỗ.

> ### ⚠️ Ô "Mồi vốn từ (prompt)": để RỖNG, và đây là kết luận từ phép ĐO
>
> Model coi đoạn này như văn bản đứng ngay **trước** audio. Gặp một khoảng
> không rõ tiếng, nó **đọc tiếp đoạn văn đó thay vì phiên âm** — và nó không
> chỉ chèn thêm một dòng rác mà **nuốt luôn phần lời nói thật ở đó**.
>
> Đo ngày **10/08/2026** trên cùng một luồng audio, chỉ đổi mỗi ô này:
>
> * Bật prompt → **một đoạn duy nhất dài 44 giây mang nguyên văn câu prompt**.
>   Tắt prompt → đúng 44 giây đó ra **8 câu thật**. Tức là bật prompt làm
>   **mất trắng 44 giây phát biểu** của một người.
> * Trên một bản ghi khác, có/không prompt cho từ vựng **giống hệt nhau** —
>   `PDF`, `OCR` bóc đúng như nhau. Lợi ích đo được: **0**.
>
> Lọc theo "độ tự tin" của model **không cứu được**: đoạn nhả ngược prompt có
> chỉ số tự tin **đẹp hơn hẳn** lời nói thật.
>
> Chỉ bật nếu bạn có bộ ghi âm mẫu và **tự đo được** là nó giúp; khi đó phải
> viết thành **văn xuôi**, tuyệt đối không viết kiểu liệt kê "a, b, c".

> ### ⚠️ Bốn việc phải biết trước khi tin tính năng này
>
> 1. **Máy vẫn bịa chữ trên đoạn gần im lặng.** Có hai lưới chặn — bộ chặn
>    khoảng lặng và một danh sách chặn các câu bịa quen thuộc — nhưng **cả hai
>    chỉ chặn được một nửa lớp lỗi:** chúng hoạt động theo **độ to**, nên tiếng
>    ồn *to mà vô nghĩa* (tông đơn, tiếng quạt) vẫn lọt qua và vẫn sinh câu
>    bịa — đã đo thật với một âm 440 Hz to hơn cả tiếng người. Hãy tiếp tục
>    dặn người dùng đọc lại biên bản (mục [2.1](#21-trước-khi-đọc-tiếp)).
>
>    ⚠️ **Ngưỡng chưa hiệu chỉnh trên phòng họp thật** — nó được đặt bằng âm
>    thanh tổng hợp. Hệ quả cần theo dõi: một người nói nhỏ hoặc để micro xa
>    có thể bị bỏ **im lặng**, và biên bản sẽ **không có dòng nào** cho đoạn
>    đó, cũng **không có ghi chú nào** báo là có chỗ bị bỏ (mục
>    [2.9](#29-vì-sao-biên-bản-có-chỗ-nhảy-cóc)). Hãy thu thập báo cáo của
>    người dùng — đó là dữ liệu duy nhất để chỉnh ngưỡng.
> 2. **Không có cơ chế thử lại, và mẩu về muộn thì mất.** Bản ghi vào trạng
>    thái **Lỗi** thì nằm đó — không cron nào nhặt lại, không nút nào trên
>    giao diện chạy lại được. Mẩu audio tới **sau** khi worker đã nhận job
>    (hệ thống chờ 10 giây sau khi bấm *Kết thúc*) được lưu vào CSDL nhưng
>    **không bao giờ** được đưa vào biên bản; dấu vết duy nhất là một dòng
>    **WARNING** trong log, và chỉ cho một phần các trường hợp. Xem
>    [`README.md`](../custom-addons/aidt_meeting_minutes/README.md) §3.
> 3. **Container Odoo phải nằm trên mạng `aidt-ai-net`.**
>    `docker-compose.yml` (production) đã khai báo sẵn. Với dev chỉ cần tạo
>    network một lần trước khi `up`: `docker network create aidt-ai-net`.
>    Thiếu mạng thì lời gọi hỏng thành "Connection refused" và bản ghi chuyển
>    sang **Lỗi** — không có thông báo nào nổi lên giao diện người dùng.
> 4. **Kiểm tra lại tham số sau mỗi lần nâng cấp.** Các tham số
>    `aidt_meeting.*` được cài với cờ `noupdate`, nên **nâng cấp module không
>    ghi đè giá trị đã có** — một CSDL cài từ trước có thể giữ nguyên tên model
>    cũ (đã sai) sau khi bản mới sửa mặc định, và hậu quả là mọi lượt bóc băng
>    hỏng âm thầm. Tham số **mới** thì vẫn được tạo bình thường khi nâng cấp.
>    Sau mỗi lần nâng cấp, hãy mở `Settings` → `Biên bản cuộc họp` và xác nhận
>    **Model bóc băng** và **Model tóm tắt** đúng là thứ bạn muốn.

**Không có tác vụ theo lịch nào** cho tính năng này. Toàn bộ xử lý hậu kỳ chạy
**một lần cho cả cuộc họp**, kích hoạt lúc chủ phòng bấm **Kết thúc**, và kết
quả quay về bằng webhook.

Tham số hệ thống nằm ở **`Settings` → Kỹ thuật → Tham số hệ thống**, tiền tố
`aidt_meeting.`. Chi tiết kỹ thuật — kiến trúc, giao thức mẩu audio, ngân
sách GPU, mô hình phân quyền, và danh sách đầy đủ những gì đã/chưa kiểm chứng
— xem
[`custom-addons/aidt_meeting_minutes/README.md`](../custom-addons/aidt_meeting_minutes/README.md).
