1. Mục tiêu của project

Xây dựng hệ thống quản lý văn bản điện tử và trợ lý AI nội bộ cho cơ quan Đảng/Tỉnh ủy, hỗ trợ toàn bộ vòng đời:

Tiếp nhận văn bản
→ Số hóa/OCR
→ Đăng ký và phân loại
→ Tìm kiếm
→ Soạn thảo
→ Kiểm tra thể thức
→ Trình duyệt
→ Ký số
→ Phát hành
→ Lưu trữ
→ Bóc tách và theo dõi nhiệm vụ

Hệ thống phải bảo đảm:

Quản lý đúng quy trình văn bản đến và văn bản đi.
Phân quyền theo vai trò, đơn vị, phạm vi và độ mật.
Không làm lộ tên, nội dung hoặc file của văn bản mật.
AI chỉ hỗ trợ trích xuất, kiểm tra và gợi ý; người dùng phải xác nhận.
Mọi thao tác, lần duyệt và lần gọi AI đều được ghi nhật ký.
Hỗ trợ OCR, tìm kiếm hybrid, kiểm tra thể thức, trình ký và theo dõi nhiệm vụ.
2. Kết quả cần đạt

Sau khi hoàn thành, hệ thống cho phép:

1. Quản lý cây tổ chức, người dùng và vai trò.

2. Tiếp nhận, đăng ký, trình và chuyển xử lý văn bản đến.

3. Tạo phiếu soạn thảo, chọn mẫu và tải file DOCX.

4. Upload DOCX, trích xuất metadata và kiểm tra thể thức.

5. Quản lý nhiều phiên bản của một văn bản.

6. Duyệt nội dung, duyệt thể thức và lưu hash bản đã duyệt.

7. Convert bản chốt từ DOCX sang PDF.

8. Ký số, cấp số ký hiệu và phát hành văn bản.

9. OCR tài liệu giấy và lập chỉ mục tìm kiếm.

10. Tìm kiếm văn bản bằng từ khóa hoặc ngôn ngữ tự nhiên.

11. Bóc tách nhiệm vụ, đơn vị phụ trách và thời hạn từ văn bản.

12. Theo dõi tiến độ, nhắc hạn và báo cáo kết quả.

13. Kiểm soát truy cập tài liệu mật và lưu audit log.

AI phải là cơ chế human-in-the-loop: kết quả do AI sinh ra chỉ là đề xuất và phải cho phép người dùng sửa, duyệt hoặc từ chối.

3. Use case tổng quát
+-------------------+                         +-----------------------------------+
|     LÃNH ĐẠO      |                         |      HỆ THỐNG QUẢN LÝ VĂN BẢN    |
| Bí thư / Phó BT   |                         |                                   |
+-------------------+                         |  (UC01) Xem dashboard             |
          |                                   |  (UC02) Tìm kiếm văn bản          |
          |---------------------------------->|  (UC03) Xem văn bản theo quyền    |
          |---------------------------------->|  (UC04) Cho ý kiến chỉ đạo        |
          |---------------------------------->|  (UC05) Duyệt nội dung            |
          |---------------------------------->|  (UC06) Ký ban hành               |
                                              |                                   |
+-------------------+                         |                                   |
| CHÁNH VĂN PHÒNG   |                         |  (UC07) Kiểm tra thể thức         |
+-------------------+                         |  (UC08) Ký nháy                    |
          |---------------------------------->|  (UC09) Duyệt trình ký            |
          |---------------------------------->|  (UC10) Theo dõi nhiệm vụ         |
                                              |                                   |
+-------------------+                         |                                   |
|     VĂN THƯ       |                         |  (UC11) Tiếp nhận văn bản đến     |
+-------------------+                         |  (UC12) Đăng ký văn bản đến       |
          |---------------------------------->|  (UC13) Trình văn bản đến         |
          |---------------------------------->|  (UC14) Chuyển giao xử lý         |
          |---------------------------------->|  (UC15) Đăng ký văn bản đi        |
          |---------------------------------->|  (UC16) Cấp số và ký hiệu         |
          |---------------------------------->|  (UC17) Phát hành văn bản         |
          |---------------------------------->|  (UC18) Lưu trữ văn bản           |
                                              |                                   |
+-------------------+                         |                                   |
|   CHUYÊN VIÊN     |                         |  (UC19) Tạo phiếu soạn thảo       |
+-------------------+                         |  (UC20) Chọn và tải mẫu DOCX      |
          |---------------------------------->|  (UC21) Upload bản thảo           |
          |---------------------------------->|  (UC22) Đối chiếu metadata        |
          |---------------------------------->|  (UC23) Xem lỗi thể thức          |
          |---------------------------------->|  (UC24) Trình duyệt bản thảo      |
          |---------------------------------->|  (UC25) Xử lý nhiệm vụ            |
          |---------------------------------->|  (UC26) Báo cáo kết quả           |
                                              |                                   |
+-------------------+                         |                                   |
| QUẢN TRỊ HỆ THỐNG |                         |  (UC27) Quản lý cây tổ chức       |
+-------------------+                         |  (UC28) Quản lý người dùng        |
          |---------------------------------->|  (UC29) Quản lý vai trò, quyền    |
          |---------------------------------->|  (UC30) Quản lý mẫu văn bản      |
          |---------------------------------->|  (UC31) Cấu hình rule thể thức    |
          |---------------------------------->|  (UC32) Xem audit log             |
                                              |                                   |
                                              +-----------------------------------+
4. Use case văn bản đến
+-------------+       +--------------------------------------+
|   VĂN THƯ   |------>| Tiếp nhận và kiểm tra văn bản        |
|             |------>| Đăng ký văn bản đến                  |
|             |------>| Kiểm tra/trích xuất metadata         |
|             |------>| Trình văn bản cho lãnh đạo           |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
|  LÃNH ĐẠO   |------>| Xem văn bản                          |
|             |------>| Cho ý kiến chỉ đạo                   |
|             |------>| Chọn đơn vị chủ trì/phối hợp         |
|             |------>| Giao thời hạn xử lý                  |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
| CHUYÊN VIÊN |------>| Tiếp nhận nhiệm vụ                   |
| / ĐƠN VỊ    |------>| Xử lý văn bản                        |
|             |------>| Cập nhật tiến độ                     |
|             |------>| Báo cáo kết quả                      |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
| CHÁNH VP    |------>| Theo dõi và đôn đốc                  |
| / LÃNH ĐẠO  |------>| Xem nhiệm vụ sắp hạn/quá hạn         |
|             |------>| Duyệt kết quả hoàn thành             |
+-------------+       +--------------------------------------+
5. Use case văn bản đi
+-------------+       +--------------------------------------+
| CHUYÊN VIÊN |------>| Tạo phiếu soạn thảo                  |
|             |------>| Chọn mẫu văn bản                     |
|             |------>| Tải mẫu DOCX                         |
|             |------>| Upload bản thảo DOCX                 |
|             |------>| Đối chiếu metadata                   |
|             |------>| Xem kết quả kiểm tra thể thức        |
|             |------>| Trình duyệt bản thảo                 |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
| TRƯỞNG PHÒNG|------>| Duyệt bản thảo                       |
| / NGƯỜI DUYỆT       | Trả lại và yêu cầu chỉnh sửa         |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
| THỦ TRƯỞNG  |------>| Kiểm tra và duyệt nội dung           |
| ĐƠN VỊ      |------>| Trả lại nội dung cần sửa             |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
| CHÁNH VP    |------>| Kiểm tra thể thức lần cuối           |
|             |------>| Ký nháy                              |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
|  LÃNH ĐẠO   |------>| Xem bản PDF đã chốt                  |
|             |------>| Ký số ban hành                       |
+-------------+       +--------------------------------------+
                                  |
                                  v
+-------------+       +--------------------------------------+
|   VĂN THƯ   |------>| Cấp số và ký hiệu                    |
|             |------>| Đăng ký văn bản đi                   |
|             |------>| Phát hành tới nơi nhận               |
|             |------>| Theo dõi trạng thái gửi              |
|             |------>| Lưu trữ bản chính thức               |
+-------------+       +--------------------------------------+
6. Use case AI và tìm kiếm
+----------------+       +-----------------------------------+
| NGƯỜI SỬ DỤNG  |------>| Tìm kiếm bằng ngôn ngữ tự nhiên  |
|                |------>| Lọc theo metadata                 |
|                |------>| Xem văn bản liên quan             |
+----------------+       +-----------------------------------+
                                   |
                                   v
                         +-----------------------------------+
                         | Kiểm tra quyền truy cập           |
                         | Keyword Search + Vector Search    |
                         | Xếp hạng kết quả                  |
                         | Trích đoạn phù hợp                |
                         +-----------------------------------+

+----------------+       +-----------------------------------+
| CHUYÊN VIÊN /  |------>| Gợi ý loại văn bản và lĩnh vực   |
| VĂN THƯ        |------>| Trích xuất metadata              |
|                |------>| Trích xuất từ khóa và thực thể    |
|                |------>| Kiểm tra chính tả                |
|                |------>| Kiểm tra thể thức                |
|                |------>| Trích xuất nhiệm vụ              |
+----------------+       +-----------------------------------+
                                   |
                                   v
                         +-----------------------------------+
                         | Người dùng kiểm tra               |
                         | Chỉnh sửa kết quả AI              |
                         | Xác nhận hoặc từ chối             |
                         | Lưu người duyệt và audit log      |
                         +-----------------------------------+