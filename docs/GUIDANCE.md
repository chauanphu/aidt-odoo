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
| Ghi âm và biên bản cuộc họp | ⚠️ Chưa dùng được — xem [2.1](#21-trước-khi-đọc-tiếp) | [2](#2-ghi-âm-và-biên-bản-cuộc-họp) |
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

## 2.1. Trước khi đọc tiếp

> ### ⚠️ Tính năng này CHƯA DÙNG ĐƯỢC cho công việc thật
>
> Toàn bộ đường đi kỹ thuật đã chạy thông (ngày 05/08/2026), nhưng **bộ bóc
> băng hiện không nhận ra chữ nào từ tiếng Việt**. Trong lần chạy thử với
> giọng nói tiếng Việt rõ ràng, bản bóc băng thu được chỉ là một dấu chấm:
>
> ```
> [00:00] Administrator: . .
> ```
>
> Nghĩa là: hôm nay bạn có thể bật ghi âm, dừng ghi âm, và sẽ thấy hai bài
> đăng xuất hiện trong cuộc họp — nhưng **nội dung trong đó chưa dùng được**.
>
> **Đừng dựa vào tính năng này để thay cho việc ghi biên bản thủ công.**
> Tài liệu dưới đây mô tả cách tính năng vận hành để bạn nhận ra đúng những
> gì mình nhìn thấy trên màn hình; hãy hỏi quản trị viên xem việc bóc băng đã
> được khắc phục chưa trước khi dùng thật.

Ngoài ra, những điểm sau **chưa được kiểm chứng** và có thể khác với mô tả:

* Chưa có cuộc họp thật nào được ghi qua micro của trình duyệt từ đầu đến
  cuối. Mọi kiểm thử đều dùng tệp âm thanh nạp sẵn.
* Độ chính xác của việc bóc băng tiếng Việt **chưa đo được**.
* Mốc thời gian `[phút:giây]` do bộ bóc băng trả về **hiện không đáng tin**
  (có đoạn cho ra thời điểm kết thúc sớm hơn thời điểm bắt đầu).
* Cách hệ thống cắt bỏ chữ lặp ở chỗ nối giữa hai đoạn ghi âm được đặt theo
  ước lượng, **chưa hiệu chỉnh** trên dữ liệu thật.
* Với cuộc họp dài, **chưa ai đo** phần tóm tắt mất bao lâu. Một cuộc họp
  hai tiếng có thể mất rất lâu.

## 2.2. Tính năng này làm gì

Khi một cuộc họp trực tuyến (Discuss Meet) đang diễn ra, hệ thống có thể:

1. **Thu tiếng của từng người dự** — mỗi máy tự thu micro của chính người
   ngồi trước máy đó. Nhờ vậy biên bản biết **ai** nói câu nào, chứ không
   phải đoán từ một luồng tiếng đã trộn.
2. **Bóc băng** thành văn bản có gán tên và mốc thời gian.
3. **Tóm tắt** thành ba mục: **NỘI DUNG CHÍNH**, **KẾT LUẬN**, **VIỆC CẦN
   LÀM**.
4. Đăng cả hai vào phần trao đổi (chatter) của cuộc họp.

Sau khi bóc băng xong, **tệp âm thanh bị xoá**, chỉ giữ lại phần chữ (xem
[2.9](#29-âm-thanh-bị-xoá-chữ-được-giữ)).

## 2.3. Bật ghi âm

Trong cửa sổ cuộc gọi, khi chưa có ai ghi âm, bạn sẽ thấy nút:

> **Bật ghi âm biên bản**

**Ai bấm được nút này:**

| Loại cuộc gọi | Ai được bật |
|---|---|
| Cuộc họp **có trong lịch** | **Chỉ người chủ trì** (người tạo cuộc họp) |
| Cuộc gọi **tự phát** (gọi thẳng trong kênh, không có lịch) | **Bất kỳ ai** đang trong cuộc gọi |

Nếu bạn không phải người chủ trì của một cuộc họp có lịch, hệ thống báo:

> *Chỉ người chủ trì cuộc họp mới bật được ghi âm.*

Các thông báo khác có thể gặp:

| Thông báo | Nghĩa là |
|---|---|
| *Cuộc gọi này đang được ghi âm rồi.* | Đã có người bật trước bạn. Mỗi cuộc gọi chỉ có một bản ghi tại một thời điểm. |
| *Bạn không thuộc cuộc gọi này.* | Bạn không có trong kênh của cuộc gọi. |
| *Cuộc họp ở mức "…" vượt ngưỡng cho phép ghi âm. Liên hệ quản trị viên nếu cần thay đổi.* | Độ mật của cuộc họp cao hơn mức quản trị viên cho phép ghi âm. Mặc định chỉ cho phép mức **Thường**. |

## 2.4. Băng thông báo khi đang ghi âm

Ngay khi ghi âm bắt đầu, **mọi người đang trong cuộc gọi** đều thấy một băng
thông báo với dòng chữ:

> 🔴 **Cuộc họp đang được ghi âm để tạo biên bản.**

kèm hai nút: **Từ chối** và **Dừng ghi âm**.

**Băng này không tắt được và không ẩn được.** Đó là chủ ý: nó chính là cách
hệ thống bảo đảm mọi người biết mình đang bị ghi âm. Không có nút "×" nào.

Người đã **rời cuộc gọi** thì không thấy băng này nữa, kể cả khi cuộc họp vẫn
đang được ghi.

## 2.5. ⚠️ "Từ chối" và "Dừng ghi âm" KHÔNG giống nhau

Hai nút này nằm cạnh nhau và tên gần giống nhau, nhưng làm hai việc **khác
hẳn**. Đọc kỹ mục này.

| | **Từ chối** | **Dừng ghi âm** |
|---|---|---|
| Ảnh hưởng tới | **Chỉ mình bạn** | **Cả cuộc họp** |
| Sau khi bấm | Micro của **bạn** ngừng được gửi lên. Cuộc họp **vẫn tiếp tục được ghi âm** với tất cả những người khác. | Việc ghi âm **kết thúc cho tất cả mọi người**. |
| Ai bấm được | Bất kỳ ai trong cuộc gọi | Bất kỳ ai trong cuộc gọi — **không cần** là người chủ trì, cũng không cần là người đã bật |

### Vì sao băng thông báo VẪN CÒN sau khi bạn bấm "Từ chối"

Đây là điểm dễ hiểu nhầm nhất của toàn bộ tính năng.

Sau khi bạn bấm **Từ chối**, băng thông báo **không biến mất**. Nút **Từ
chối** biến mất (bạn đã từ chối rồi, không còn gì để từ chối thêm), nhưng
băng vẫn nằm đó và **đổi chữ** thành:

> 🔴 **Bạn đã từ chối; cuộc họp vẫn đang được ghi âm.**

**Băng còn đó KHÔNG có nghĩa là việc từ chối của bạn thất bại.** Ngược lại:
nó còn đó chính là để nói cho bạn biết sự thật — **giọng của bạn đã ngừng
được ghi, nhưng cuộc họp thì chưa dừng**, những người khác vẫn đang được ghi
âm bình thường. Nếu băng biến mất, bạn sẽ tưởng cả cuộc họp đã ngừng ghi và
có thể nói ra điều mà bạn không định cho vào biên bản của người khác.

Nút **Dừng ghi âm** vẫn còn đó cho bạn. Muốn dừng hẳn cho cả cuộc họp thì bấm
tiếp nút đó.

Băng chỉ biến mất khi việc ghi âm **thực sự kết thúc** cho cả cuộc họp — do
ai đó bấm **Dừng ghi âm**, hoặc do mọi người đã rời hết cuộc gọi.

### Nếu bạn đã từ chối, biên bản ghi nhận điều đó

Đầu bản bóc băng sẽ có một dòng nêu rõ tên:

> *Không ghi âm giọng của: Nguyễn Văn A (đã từ chối ghi âm).*

Dòng này có mặt để người đọc biết **thiếu giọng của ai**, thay vì tưởng những
người đó ngồi im suốt cuộc họp.

## 2.6. Tắt micro giữa chừng

Khi bạn bấm **tắt micro** bằng nút tắt tiếng thông thường của cuộc gọi, phần
đó **không được ghi âm**. Hệ thống dừng hẳn việc thu ngay lúc bạn tắt tiếng,
chứ không thu tiếp rồi bỏ đi — nên những gì bạn nói riêng trong lúc tắt micro
không lọt vào biên bản.

Bật micro lại thì việc thu tiếp tục từ thời điểm đó.

Những đoạn quá nhỏ tiếng cũng bị bỏ qua, không gửi đi bóc băng.

## 2.7. Kết quả xuất hiện ở đâu

Sau khi cuộc họp kết thúc, hệ thống cần **vài phút** để bóc băng và tóm tắt
(việc này chạy theo lịch, mỗi phút một lượt). Đừng chờ kết quả xuất hiện ngay
lập tức.

| Loại cuộc gọi | Kết quả đăng vào |
|---|---|
| Cuộc họp **có trong lịch** | Phần trao đổi (chatter) của **cuộc họp trong Lịch** |
| Cuộc gọi **tự phát** | Đăng thẳng vào **kênh** nơi cuộc gọi đã diễn ra |

### ⚠️ Hai bài đăng, hai ý nghĩa khác nhau

Bạn sẽ thấy **hai** bài đăng riêng biệt. Đừng nhầm chúng với nhau:

| Tiêu đề bài đăng | Là gì | Dùng để làm gì |
|---|---|---|
| **Bản bóc băng cuộc họp** | **Nguyên văn** lời nói, từng dòng có mốc `[phút:giây]` và tên người nói. Máy **không** diễn giải, **không** rút gọn. | Đây là **bản gốc**. Khi cần đối chiếu ai đã nói gì, đọc bài này. |
| **Tóm tắt cuộc họp** | **Bản do máy viết lại** theo ba mục NỘI DUNG CHÍNH / KẾT LUẬN / VIỆC CẦN LÀM. | Đọc nhanh. **Không phải văn bản gốc.** |

**Bản tóm tắt do máy sinh ra và có thể sai hoặc thiếu.** Trước khi dùng nó
làm cơ sở cho một văn bản hành chính, hãy đối chiếu với **Bản bóc băng cuộc
họp**. Nguyên tắc chung của hệ thống vẫn là: người dùng đọc bản gốc, không
đọc thay bằng bản máy tóm tắt.

Bài **Tóm tắt cuộc họp** có thể **không xuất hiện** nếu bộ tóm tắt gặp sự cố.
Khi đó bài **Bản bóc băng cuộc họp** vẫn được đăng bình thường — bản gốc
không bị mất vì phần tóm tắt hỏng. Báo quản trị viên nếu bạn cần bản tóm tắt.

Nếu không thu được gì, nội dung bài đăng sẽ là *(không có nội dung)*.

## 2.8. Dòng "[thiếu âm thanh …]" nghĩa là gì

Trong bản bóc băng có thể xuất hiện những dòng như:

```
[thiếu âm thanh 12:30–12:45: Nguyễn Văn A]
```

Nghĩa là: trong khoảng **12 phút 30 giây đến 12 phút 45 giây**, có một đoạn
tiếng của **Nguyễn Văn A** mà hệ thống **không bóc băng được** — thường do
mạng của máy đó bị đứt, hoặc dịch vụ bóc băng lỗi và đã thử lại vài lần
không thành.

**Đây là dấu hiệu tốt, không phải lỗi hiển thị.** Hệ thống cố ý ghi lại chỗ
khuyết thay vì lặng lẽ bỏ qua, để người đọc biết biên bản **có một khoảng
trống** đúng ở chỗ nào và của ai — thay vì đọc một bản trông có vẻ liền mạch
nhưng thực ra đã mất nội dung.

Phần tóm tắt cũng được yêu cầu nêu rõ khi bản bóc băng có đánh dấu này.

Nếu đoạn đó quan trọng, hãy hỏi lại người có tên trong dòng đó.

## 2.9. Âm thanh bị xoá, chữ được giữ

Theo thiết lập mặc định, **tệp âm thanh bị xoá ngay sau khi bóc băng xong**.
Chỉ **bản bóc băng** và **bản tóm tắt** được giữ lại.

Nghĩa là **không nghe lại được** cuộc họp. Nếu bản bóc băng ghi sai, không có
bản ghi tiếng nào để đối chiếu.

Quản trị viên có thể đổi thiết lập này để giữ âm thanh thêm một số ngày.

## 2.10. Ai xem được bản ghi

Bạn xem được bản bóc băng và bản tóm tắt của một cuộc họp nếu bạn **là thành
viên của kênh** cuộc gọi đó, **hoặc** là **người dự** cuộc họp trong Lịch.

Ngoài ra, người có quyền quản trị tính năng này xem được tất cả.

## 2.11. Xử lý nhanh

| Hiện tượng | Nên làm |
|---|---|
| Không thấy nút **Bật ghi âm biên bản** | Cuộc gọi đã được ghi rồi (băng thông báo đang hiện), hoặc bạn không ở trong cuộc gọi. |
| Bấm bật, báo *Chỉ người chủ trì…* | Cuộc họp có trong lịch — nhờ người chủ trì bật. |
| Đã bấm **Từ chối** mà băng vẫn còn | **Đúng như thiết kế.** Xem [2.5](#25--từ-chối-và-dừng-ghi-âm-không-giống-nhau). Giọng của bạn đã ngừng được ghi. |
| Họp xong lâu rồi mà chưa thấy bài đăng | Chờ thêm vài phút. Nếu vẫn không có, báo quản trị viên. |
| Có bài **Bản bóc băng** nhưng không có bài **Tóm tắt** | Bộ tóm tắt gặp sự cố. Bản gốc vẫn còn. Báo quản trị viên. |
| Bản bóc băng chỉ có dấu chấm hoặc trống rỗng | Đây là **lỗi đã biết** của bộ bóc băng hiện tại — xem [2.1](#21-trước-khi-đọc-tiếp). Báo quản trị viên. |
| Có dòng `[thiếu âm thanh …]` | Một đoạn không bóc băng được. Hỏi lại người có tên trong dòng đó. |

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

**Menu `Calendar` → `Bản ghi cuộc họp`** liệt kê mọi bản ghi, kèm kênh, cuộc
họp, thời điểm bắt đầu/kết thúc, độ mật lúc bắt đầu và trạng thái. Menu này
chỉ hiện cho nhóm **Quản lý biên bản cuộc họp**.

> Menu cha hiển thị là **`Calendar`** (tiếng Anh) chứ không phải "Lịch": bản
> cài hiện tại chỉ bật ngôn ngữ `en_US`, nên các menu lõi của Odoo giữ nguyên
> tiếng Anh, còn chuỗi của module này là tiếng Việt cố định.

Trên form một bản ghi:

* Nút **Dừng ghi âm** (chỉ hiện khi đang ghi).
* Nút **Tạo lại tóm tắt** (chỉ hiện khi có lỗi tóm tắt) — chạy lại phần tóm
  tắt mà không đụng tới bản bóc băng.
* Thẻ **Tóm tắt** (kèm ô lỗi nếu có) và thẻ **Bản bóc băng**.
* **Người từ chối ghi âm** — danh sách người đã bấm *Từ chối*.

**Thiết lập: `Settings` → `Biên bản cuộc họp`**

| Khối | Trường | Ghi chú |
|---|---|---|
| Dịch vụ AI → *Bóc băng* | URL / Model / API key dịch vụ bóc băng | Trỏ được sang dịch vụ ngoài tương thích OpenAI |
| Dịch vụ AI → *Tóm tắt* | URL / Model / API key dịch vụ tóm tắt | " |
| Chính sách → *Độ mật tối đa* | Độ mật tối đa được ghi âm | Mặc định **Thường** |
| Chính sách → *Lưu trữ audio* | Giữ audio (ngày) | **0 = xoá ngay sau khi bóc băng xong** |

> ### ⚠️ Ba việc phải làm trước khi tin tính năng này
>
> 1. **Bộ bóc băng hiện không trả về chữ.** Dịch vụ `aidt-asr`
>    (`vinai/PhoWhisper-large` trên vLLM 0.26.0) nhận audio tiếng Việt hợp lệ
>    và trả về `"."` hoặc chuỗi rỗng. Đã loại trừ: audio hỏng, định dạng
>    MP3/WAV, nhận nhầm ngôn ngữ, service chết. Đây là lỗi tầng phục vụ
>    model, **không** phải mã Python của module. Chưa khắc phục ⇒ tính năng
>    chưa dùng được.
> 2. **Container Odoo phải được nối vào mạng `aidt-ai-net`.**
>    `docker-compose.dev.yml` không khai báo mạng này, nên mặc định Odoo
>    **không** phân giải được `aidt-asr` / `aidt-llm`:
>    `docker network connect aidt-ai-net aidt-odoo-dev-odoo-1`.
> 3. **Kiểm tra lại tham số sau mỗi lần nâng cấp.** Các tham số
>    `aidt_meeting.*` được cài với cờ `noupdate`, nên **nâng cấp module không
>    ghi đè giá trị đã có**. Một CSDL cài từ trước từng giữ nguyên địa chỉ và
>    tên model tóm tắt cũ (đã sai) sau khi bản mới sửa mặc định — hậu quả là
>    mọi lần tóm tắt hỏng âm thầm. Bản `19.0.1.0.1` có script sửa đúng hai
>    giá trị sai đã biết đó.

Ba tác vụ nền chạy tự động (**`Settings` → Kỹ thuật → Tác vụ theo lịch**,
tiền tố **AIDT**): bóc băng mẩu audio (1 phút), đóng và hoàn tất bản ghi
(1 phút), xoá audio theo chính sách (1 ngày).

Tham số hệ thống nằm ở **`Settings` → Kỹ thuật → Tham số hệ thống**, tiền tố
`aidt_meeting.`. Chi tiết kỹ thuật — kiến trúc, giao thức mẩu audio, ngân
sách GPU, mô hình phân quyền, và danh sách đầy đủ những gì đã/chưa kiểm chứng
— xem
[`custom-addons/aidt_meeting_minutes/README.md`](../custom-addons/aidt_meeting_minutes/README.md).
