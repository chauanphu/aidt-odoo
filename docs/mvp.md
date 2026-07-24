# DANH MỤC TÍNH NĂNG MUST-HAVE — MVP

---

## NHÓM 1: NỀN TẢNG & BẢO MẬT (WBS 1.3, 1.4, 12.1)

### 1.1. Quản lý người dùng & phân quyền
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| N-01 | Đăng nhập SSO | Tích hợp SSO tỉnh / LDAP; fallback user-password + OTP | P0 |
| N-02 | Cây tổ chức | Mô hình hóa cấp ủy → ban → phòng → cán bộ; | P0 |
| N-03 | RBAC theo vai trò | Bí thư / Phó BT / Chánh VP / Chuyên viên / Văn thư / Admin | P0 |
| N-04 | Phân quyền theo độ mật | 4 mức: Thường / Mật / Tối mật / Tuyệt mật — chặn ở tầng dữ liệu, không chỉ tầng UI | P0 |
| N-05 | Phân quyền theo phạm vi | Cán bộ chỉ thấy văn bản của đơn vị mình + văn bản được chia sẻ | P0 |
| N-06 | Ủy quyền tạm thời | Ủy quyền có thời hạn khi lãnh đạo đi công tác | P1 |

### 1.2. Nhật ký & kiểm toán
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| N-07 | Audit log toàn hệ thống | Ghi ai-làm gì-lúc nào-trên bản ghi nào; log không sửa được | P0 |
| N-08 | Nhật ký truy cập tài liệu mật | Log riêng, cảnh báo khi truy cập bất thường (số lượng lớn, ngoài giờ) | P0 |
| N-09 | Nhật ký gọi AI | Lưu prompt + output + người duyệt cho mọi lần gọi model — phục vụ truy vết trách nhiệm | P0 |

### 1.3. Kho dữ liệu dùng chung
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| N-10 | Object storage | Lưu file gốc (PDF, DOCX, ảnh scan), có versioning | P0 |
| N-11 | CSDL quan hệ | Metadata văn bản, người dùng, nhiệm vụ, quy trình | P0 |
| N-12 | Vector database | Lưu embedding phục vụ semantic search | P0 |
| N-13 | Từ điển dữ liệu chuẩn | Danh mục dùng chung: loại văn bản, lĩnh vực, cơ quan ban hành, độ mật | P0 |
| N-14 | Sao lưu & phục hồi | Backup tự động, có kịch bản restore đã diễn tập | P0 |

### 1.4. Hạ tầng AI
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| N-15 | Self-host LLM | Model chạy nội bộ cho dữ liệu mật — **không gửi ra API bên ngoài** | P0 |
| N-16 | Embedding model tiếng Việt | Phục vụ semantic search | P0 |
| N-17 | Cổng AI tập trung | Một điểm vào duy nhất: routing, rate limit, logging, lọc dữ liệu nhạy cảm | P0 |
| N-18 | Chính sách chống rò rỉ | Chặn văn bản Mật trở lên đi vào bất kỳ model ngoài nào | P0 |

---

## NHÓM 2: QUẢN LÝ VĂN BẢN & TÌM KIẾM NGỮ NGHĨA (WBS 2.2, 2.3, 2.4)

### 2.1. Quản lý văn bản
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| V-01 | Đăng ký văn bản đến/đi | Sổ văn bản điện tử, cấp số tự động theo quy định | P0 |
| V-02 | Metadata chuẩn | Số/ký hiệu, ngày ban hành, cơ quan, loại, lĩnh vực, độ mật, độ khẩn, người ký | P0 |
| V-03 | Gán độ mật thủ công | **Bắt buộc do người nhập chọn**, AI không tự quyết ở MVP | P0 |
| V-04 | Đính kèm & xem trước | Xem PDF/DOCX ngay trên trình duyệt, không cần tải về | P0 |
| V-05 | Vòng đời văn bản | Dự thảo → Trình ký → Đã ban hành → Lưu trữ | P0 |

### 2.2. Gắn nhãn & liên kết (AI hỗ trợ)
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| V-06 | Gợi ý lĩnh vực & loại VB | AI đề xuất, người dùng xác nhận — hiển thị độ tin cậy | P0 |
| V-07 | Trích xuất từ khóa | Tự động sinh keyword, cho phép sửa | P0 |
| V-08 | Nhận diện thực thể | Tên cơ quan, chức danh, địa danh, ngày tháng, số hiệu VB | P1 |
| V-09 | Liên kết văn bản | Phát hiện quan hệ: căn cứ / sửa đổi / thay thế / hết hiệu lực | P1 |

### 2.3. Tìm kiếm
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| V-10 | Tìm kiếm ngôn ngữ tự nhiên | "Các văn bản về hỗ trợ hộ nghèo năm 2025" → trả kết quả đúng ngữ nghĩa | P0 |
| V-11 | Tìm kiếm lai (hybrid) | Kết hợp keyword (BM25) + vector — chính xác hơn hẳn dùng riêng lẻ | P0 |
| V-12 | Lọc đa tiêu chí | Thời gian, cơ quan, loại, lĩnh vực, độ mật, trạng thái | P0 |
| V-13 | Lọc theo quyền | **Kết quả tìm kiếm phải lọc theo quyền trước khi trả về** — không lộ cả tiêu đề VB mật | P0 |
| V-14 | Trích đoạn kết quả | Highlight đoạn văn bản khớp truy vấn | P0 |
| V-15 | Gợi ý VB liên quan | Khi mở một văn bản, gợi ý 5 văn bản liên quan nhất | P1 |

---

## NHÓM 3: SỐ HÓA — OCR & LẬP CHỈ MỤC (WBS 9.1–9.4)

### 3.1. Thu nhận & OCR
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| S-01 | Nạp hàng loạt | Upload nhiều file / quét từ thư mục máy scan | P0 |
| S-02 | OCR tiếng Việt | Có dấu, độ chính xác ≥95% với văn bản in | P0 |
| S-03 | Xử lý ảnh trước OCR | Xoay thẳng, khử nhiễu, cắt viền, chuẩn hóa độ tương phản | P0 |
| S-04 | Nhận dạng cấu trúc | Tách vùng: quốc hiệu, số ký hiệu, trích yếu, nội dung, nơi nhận, chữ ký | P1 |
| S-05 | Nhận dạng bảng | Trích bảng biểu trong văn bản | P1 |
| S-06 | Trích metadata tự động | Tự điền số/ký hiệu, ngày, cơ quan từ kết quả OCR | P0 |
| S-07 | Màn hình soát lỗi OCR | Hiển thị ảnh gốc + text nhận dạng cạnh nhau, đánh dấu vùng độ tin cậy thấp | P0 |
| S-08 | Chữ viết tay | **Hoãn v2** — độ chính xác chưa đạt ngưỡng dùng được | — |

### 3.2. Kho lưu trữ & chỉ mục
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| S-09 | Cây hồ sơ lưu trữ | Phông → Mục lục → Hồ sơ → Văn bản (theo nghiệp vụ lưu trữ) | P0 |
| S-10 | PDF/A có lớp text | Xuất file lưu trữ chuẩn, tìm kiếm được | P0 |
| S-11 | Pipeline chỉ mục tự động | OCR xong → chunk → embed → nạp vector DB | P0 |
| S-12 | Chống trùng lặp | Phát hiện file trùng qua hash + độ tương đồng nội dung | P1 |
| S-13 | Theo dõi tiến độ số hóa | Dashboard: đã scan / đã OCR / đã soát / đã chỉ mục | P1 |

---

## NHÓM 4: TRỢ LÝ SOẠN THẢO (WBS 4.1, 4.2)

### 4.1. Mẫu & thể thức
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| D-01 | Thư viện mẫu văn bản | Tối thiểu 20 mẫu: công văn, báo cáo, thông báo, kế hoạch, quyết định, tờ trình, giấy mời | P0 |
| D-02 | Trường động trong mẫu | Tự điền số, ngày, cơ quan, người ký từ hồ sơ người dùng | P0 |
| D-03 | Engine thể thức | Chuẩn hóa theo quy định về thể thức văn bản của Đảng: font, cỡ chữ, căn lề, vị trí quốc hiệu, số ký hiệu | P0 |
| D-04 | Quản lý mẫu | Admin thêm/sửa/vô hiệu hóa mẫu, có phiên bản | P0 |
| D-05 | Soạn thảo trực tuyến | Trình soạn thảo trong hệ thống, không cần Word | P1 |

### 4.2. Kiểm tra & hỗ trợ
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| D-06 | Kiểm tra chính tả tiếng Việt | Bao gồm lỗi dấu, lỗi gõ tắt phổ biến | P0 |
| D-07 | Kiểm tra thể thức | Cảnh báo sai lề, sai vị trí số ký hiệu, thiếu nơi nhận, sai cỡ chữ | P0 |
| D-08 | Kiểm tra tính nhất quán | Tên cơ quan/chức danh/số liệu dùng khác nhau trong cùng văn bản | P0 |
| D-09 | Kiểm tra checklist bắt buộc | Đủ căn cứ, đủ nơi nhận, đủ chữ ký, đủ phụ lục được viện dẫn | P0 |
| D-10 | Gợi ý viết lại câu | Diễn đạt rõ ràng hơn, đúng văn phong hành chính | P1 |
| D-11 | So sánh phiên bản | Diff giữa các bản dự thảo | P1 |
| D-12 | Gợi ý căn cứ pháp lý | **Hoãn v2** — rủi ro AI bịa văn bản pháp luật | — |

### 4.3. Trình ký
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| D-13 | Luồng trình ký | Chuyên viên → Trưởng phòng → Chánh VP → Lãnh đạo | P0 |
| D-14 | Góp ý & yêu cầu sửa | Comment theo đoạn, trả lại kèm lý do | P0 |
| D-15 | Ký số | Tích hợp chữ ký số / USB token theo quy định | P0 |

---

## NHÓM 5: BÓC TÁCH & THEO DÕI NHIỆM VỤ (WBS 6.1–6.3)

### 5.1. Bóc tách nhiệm vụ
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| T-01 | Trích nhiệm vụ từ văn bản | Từ nghị quyết / kết luận / thông báo / biên bản | P0 |
| T-02 | Nhận diện đơn vị chủ trì | AI đề xuất, cán bộ xác nhận | P0 |
| T-03 | Nhận diện đơn vị phối hợp | Tương tự, cho phép nhiều đơn vị | P0 |
| T-04 | Nhận diện thời hạn | Xử lý cả mốc tuyệt đối ("trước 30/6") và tương đối ("trong quý II", "trong 15 ngày") | P0 |
| T-05 | Màn hình duyệt bóc tách | **Bắt buộc**: hiển thị nhiệm vụ đề xuất + trích dẫn đoạn nguồn để đối chiếu | P0 |
| T-06 | Sửa & bổ sung thủ công | Sửa mọi trường, thêm nhiệm vụ AI bỏ sót, xóa nhiệm vụ sai | P0 |
| T-07 | Liên kết nguồn | Mỗi nhiệm vụ luôn trỏ về văn bản + vị trí đoạn gốc | P0 |

### 5.2. Quản lý & nhắc việc
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| T-08 | Danh mục nhiệm vụ | Lọc theo đơn vị, người, trạng thái, hạn, văn bản nguồn | P0 |
| T-09 | Trạng thái nhiệm vụ | Mới → Đang thực hiện → Chờ duyệt → Hoàn thành / Quá hạn / Tạm dừng | P0 |
| T-10 | Nhiệm vụ con | Chia nhỏ nhiệm vụ lớn, tính % hoàn thành theo con | P1 |
| T-11 | Nhắc việc tự động | Trước hạn 7/3/1 ngày và khi quá hạn — qua email + thông báo trong app | P0 |
| T-12 | Báo cáo kết quả | Đơn vị báo cáo kèm file minh chứng | P0 |
| T-13 | Duyệt hoàn thành | Người giao xác nhận đóng nhiệm vụ | P0 |
| T-14 | Cảnh báo lãnh đạo | Danh sách nhiệm vụ quá hạn gửi Chánh VP hàng tuần | P0 |
| T-15 | Bảng theo dõi tổng hợp | Số nhiệm vụ theo đơn vị / trạng thái — bản đơn giản, chưa cần dashboard đầy đủ | P1 |

---

## NHÓM 6: VẬN HÀNH, KIỂM THỬ & CHUYỂN GIAO (WBS 12.3, 12.4)

### 6.1. Kiểm thử
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| O-01 | Bộ dữ liệu kiểm thử | Tối thiểu 500 văn bản thật đã ẩn danh, có nhãn chuẩn | P0 |
| O-02 | Đo chất lượng AI | Chỉ số cho OCR (CER/WER), tìm kiếm (Recall@10, MRR), bóc tách nhiệm vụ (P/R/F1) | P0 |
| O-03 | Kiểm thử phân quyền | Kịch bản đóng vai từng vai trò, xác nhận không rò rỉ dữ liệu mật | P0 |
| O-04 | Kiểm thử hiệu năng | Tìm kiếm <3s, OCR 1 trang <10s, 200 người dùng đồng thời | P0 |
| O-05 | UAT có kịch bản | Kịch bản theo đúng quy trình nghiệp vụ thật, có tiêu chí đạt/không đạt | P0 |
| O-06 | Đánh giá human-in-the-loop | Đo tỷ lệ người dùng sửa output AI — chỉ số quan trọng nhất để biết model có dùng được không | P0 |

### 6.2. Chuyển giao & đào tạo
| Mã | Tính năng | Mô tả | Ưu tiên |
|---|---|---|---|
| O-07 | Tài liệu HDSD theo vai trò | Riêng cho lãnh đạo / chuyên viên / văn thư / admin | P0 |
| O-08 | Hướng dẫn trong ứng dụng | Tooltip, tour lần đầu đăng nhập | P0 |
| O-09 | Đào tạo trực tiếp | Tối thiểu 2 buổi/đơn vị, có bài thực hành | P0 |
| O-10 | Đào tạo quản trị viên | Vận hành, phân quyền, xử lý sự cố cơ bản | P0 |
| O-11 | Tài liệu vận hành | Cài đặt, backup/restore, giám sát, quy trình xử lý sự cố | P0 |
| O-12 | Kênh hỗ trợ | Hotline + kênh ghi nhận lỗi trong ứng dụng | P0 |
| O-13 | Giám sát hệ thống | Uptime, lỗi, thời gian phản hồi, dung lượng — có cảnh báo | P0 |

---

## Tổng hợp

| Nhóm | Số tính năng P0 | Số P1 |
|---|---|---|
| 1. Nền tảng & bảo mật | 17 | 1 |
| 2. Văn bản & tìm kiếm | 12 | 3 |
| 3. Số hóa & OCR | 8 | 4 |
| 4. Soạn thảo | 11 | 3 |
| 5. Nhiệm vụ | 13 | 2 |
| 6. Vận hành | 13 | 0 |
| **Tổng** | **74** | **13** |

**Nguyên tắc xuyên suốt:** mọi output AI (V-06, V-07, S-06, D-06→D-09, T-01→T-04) đều là **đề xuất có thể sửa**, không phải kết quả cuối. Màn hình duyệt (S-07, T-05) là bắt buộc, không phải tùy chọn.

**Đường găng (critical path):** N-10→N-12 → S-01→S-03 → S-11 → V-10. Nhóm 3 và nhóm 1 phải xong trước thì nhóm 2 mới chạy được — nên bố trí song song ngay từ đầu, không làm tuần tự.