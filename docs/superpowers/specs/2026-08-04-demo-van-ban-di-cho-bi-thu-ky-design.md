# Thiết kế văn bản đi demo chờ Bí thư ký

## Mục tiêu

Tạo một văn bản đi trong database `aidt_demo` để kiểm thử thao tác ký số của Bí thư. Tiêu đề bắt đầu bằng `[DEMO]` để người dùng nhận dạng và tìm kiếm dễ dàng.

## Dữ liệu

- Tên: `[DEMO] Công văn chỉ đạo tăng cường bảo đảm an toàn thông tin`
- Chiều văn bản: đi (`di`)
- Loại: công văn (`cong_van`)
- Trạng thái: chờ ký (`cho_ky`)
- Độ mật: thường (`thuong`)
- Đơn vị soạn: Văn phòng Tỉnh ủy
- Người soạn: chuyên viên tổng hợp demo
- Người duyệt Trưởng phòng: Trưởng phòng tổng hợp demo
- Người duyệt Chánh Văn phòng: Chánh Văn phòng demo
- Lãnh đạo duyệt và người ký: Bí thư Nguyễn Văn An
- Nơi nhận: các cơ quan, đơn vị trực thuộc

Các trường ý kiến và thời điểm duyệt được điền để thể hiện văn bản đã đi hết các bước trước khi ký.

## Tệp đính kèm

Gắn `sample_document.docx` từ module `aidt_sign`. Tệp là đầu vào cho luồng chuyển PDF và ký số.

## Cách tạo và tính lặp lại

Tạo trực tiếp trong database `aidt_demo` qua ORM của Odoo. Dùng tiêu đề chính xác để kiểm tra tồn tại; chạy lại không tạo bản sao. Nếu bản ghi đã tồn tại, chuẩn hóa lại các trường nêu trên và bảo đảm có đúng tệp đính kèm demo cần thiết.

## Xác minh

Sau khi tạo, đọc lại bản ghi và kiểm tra: tiêu đề có tiền tố `[DEMO]`, trạng thái là `cho_ky`, người ký là Bí thư và có tệp Word đính kèm không rỗng. Không bấm ký trong bước này để văn bản vẫn nằm tại hàng đợi của Bí thư.
