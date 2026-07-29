Luồng trong ảnh trả lời câu hỏi theo hướng thứ hai: **duyệt thể thức không phải là một trạng thái trong vòng đời văn bản, mà là một cổng chặn (gate) đặt tại ranh giới draft → to_sign**. Phân tích từng phần:

## Cơ chế hoạt động

**1. Check là hành động lặp tùy ý trong draft, không phải bước bắt buộc phải "đi qua":**

```
draft ──┐ action_run_format_check()  (chạy bao nhiêu lần cũng được)
        └→ findings hiển thị trên form
```

Người soạn ở trạng thái `draft` cứ sửa file → upload → bấm check → xem finding → sửa tiếp. Vòng đời văn bản **không nhúc nhích** trong suốt quá trình này. So với phương án "duyệt thể thức là một state" (`draft → cho_duyet_the_thuc → dat → to_sign`), khác biệt căn bản: không có ai phải *phê duyệt* việc đạt thể thức — máy đo, kết quả là dữ liệu, không phải quyết định của con người.

**2. Cổng chặn nằm ở nút Trình ký:**

```python
# Nút "Trình ký" bị khóa khi:
invisible = có finding severity == 'error'
         hoặc file hiện tại chưa được check   # ← điểm tinh tế nhất
```

Điều kiện thứ hai quan trọng hơn vẻ ngoài của nó: nếu chỉ check "không còn error", người dùng có thể check bản A đạt, rồi **upload bản B khác và trình ký luôn** — kết quả check cũ dán lên file mới. Vì vậy gate phải ràng buộc **kết quả check với đúng phiên bản file** (thực thi bằng cách lưu hash/checksum của file lúc check; upload file mới → hash đổi → trạng thái "đã check" tự vô hiệu → nút khóa lại). Không có điều kiện này, cả cơ chế gate là hình thức.

**3. Vòng đời chỉ còn các trạng thái nghiệp vụ thật:**

```
draft → to_sign → signed → registered → issued → archived
```

Sáu state, mỗi state ứng với một sự kiện nghiệp vụ có người chịu trách nhiệm (trình, ký, cấp số, ban hành, lưu). "Đạt thể thức" không có mặt vì nó không phải sự kiện nghiệp vụ — nó là **điều kiện tiên quyết** của sự kiện "trình".

## Ba dòng trade-off cuối ảnh — đọc cho đúng

Hai dòng đầu là cái được, dòng thứ ba là cái giá phải trả:

- **"Ít state, người dùng đỡ phải đợi ai duyệt"** — bỏ được một chặng chờ trong quy trình. Nếu duyệt thể thức là state riêng có người duyệt (thường là văn thư), mỗi văn bản tốn thêm một lượt chờ + một người bị làm phiền, trong khi 80% việc đó máy đã đo được.

- **"Trách nhiệm thể thức thuộc người soạn"** — rõ ràng về mặt trách nhiệm: anh không trình được khi chưa đạt, nên văn bản lên tới lãnh đạo mặc nhiên đã qua chuẩn máy đo. Trách nhiệm gắn đúng người tạo ra lỗi.

- **"Không có người thứ hai soát trước khi lên lãnh đạo"** ⚠️ — đây là rủi ro thật, vì engine chỉ đo được thứ **đo được**: font, cỡ, lề, dãn dòng, thiếu vùng. Nó không đo được sai tên loại văn bản so với nội dung, trích yếu không khớp nội dung, sai thẩm quyền ký, viện dẫn căn cứ sai. Trong nghiệp vụ văn thư truyền thống, văn thư/Chánh VP chính là lớp soát này.

## Vì sao thiết kế này vẫn đúng cho MVP của bạn

Điểm mấu chốt: **gate không xóa lớp soát con người — nó chuyển lớp soát đó vào luồng trình ký có sẵn**. Nhìn lại D-13 của bạn: Chuyên viên → Trưởng phòng → Chánh VP → Lãnh đạo. Trưởng phòng và Chánh VP nằm *sau* gate và *trước* chữ ký lãnh đạo — họ chính là "người thứ hai" soát nội dung và những thứ máy không đo được, với quyền trả lại kèm lý do (D-14). Tức là:

```
[máy chặn lỗi đo được]  →  [người soát lỗi không đo được]  →  [ký]
        gate                    to_sign (nhiều cấp)            signed
```

Nếu thêm state "duyệt thể thức" có người duyệt riêng, bạn đang bắt một con người làm lại việc máy vừa làm, còn việc con người thực sự cần làm (soát nội dung) thì đằng nào cũng nằm trong luồng trình ký. Trùng lặp, không thêm an toàn.

Thiết kế này cũng khớp nguyên tắc xuyên suốt trong MVP của bạn: output máy (findings) là **dữ liệu hỗ trợ quyết định**, còn quyết định và trách nhiệm (trình, trả lại, ký) luôn thuộc con người ở các bước có tên người rõ ràng.

## Hai điều nên chốt khi triển khai

1. **Lưu bằng chứng gate**: mỗi lần trình ký, snapshot kết quả check (ruleset version + danh sách finding + hash file) vào bản ghi — sau này truy vết được "văn bản này qua gate với bộ luật nào, còn warning gì" (khớp N-07, D-09).
2. **Warning không chặn nhưng phải hiển thị cho người duyệt**: finding mức `warning` cho qua gate, nhưng hiện trên màn hình của Trưởng phòng/Chánh VP lúc duyệt — để lớp người soát nhìn thấy máy đã nghi ngờ gì, thay vì thông tin đó chết trong draft.

Tóm gọn: **gate cho máy, state cho người** — trạng thái chỉ dành cho những bước có con người chịu trách nhiệm ra quyết định; kiểm tra tự động là điều kiện gác cổng giữa các trạng thái, không bao giờ tự đứng thành một trạng thái.