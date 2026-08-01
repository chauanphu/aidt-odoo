# Spike findings — R1 & R3 (Task 1, Document Intelligence Search)

Kiểm chứng trước khi viết code, theo `.superpowers/sdd/2026-08-01-document-intelligence-search/task-1-brief.md`.
Chi tiết đầy đủ (log, số đo, quá trình gỡ lỗi) ở `task-1-report.md` cùng thư
mục sdd. File này chỉ tóm bốn mục brief yêu cầu.

## 1. Kết cục R1 (output thật)

Script (`Para` giả kiểu OCR: chỉ có `text` + `align`, không font/size/style)
chạy qua `detect_zones` không lỗi:

```
ten_co_quan          heuristic  ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG
quoc_hieu            heuristic  CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
tieu_ngu             heuristic  Độc lập - Tự do - Hạnh phúc
so_ky_hieu           heuristic  Số: 145/KH-UBND
dia_danh_ngay        heuristic  Bình Dương, ngày 25 tháng 7 năm 2026
noi_dung             heuristic  KẾ HOẠCH
noi_dung             heuristic  Bảo đảm an toàn hệ thống thông tin năm 2026
noi_dung             heuristic  Căn cứ Luật An toàn thông tin mạng năm 2015;
noi_nhan             heuristic  Nơi nhận:
chu_ky               heuristic  TM. ỦY BAN NHÂN DÂN
ho_ten_nguoi_ky      heuristic  Nguyễn Văn A
```

9/11 dòng đúng. Hai dòng sai (`KẾ HOẠCH` lẽ ra `ten_loai`, dòng trích yếu lẽ
ra `trich_yeu`) đã truy nguồn: `RE_TRICH_YEU` trong `zones.py` chỉ nhận
`V/v`/`Về việc` ở đầu dòng, mà dòng trích yếu mẫu không có tiền tố đó. Kiểm
chứng bằng đối chứng — chỉ đổi chữ (giữ nguyên không font/size/style) thành
`"Về việc bảo đảm..."` thì cả 11/11 đúng. Vậy hai lỗi này **không phải** do
thiếu `font`/`size_pt`/`bold`/`style_name` — đúng thứ R1 cần kiểm — mà là một
khoảng hở regex có sẵn trong `aidt_format_engine`, ảnh hưởng như nhau lên cả
nhánh DOCX soạn tay (cũng không có style). Không sửa `aidt_format_engine` để
đi tới kết luận này.

**Xếp loại: Kết cục 1 — chạy xong, zone gán hợp lý. R1 đóng.**

## 2. Quyết định cho Task 9

`detect_zones` dùng lại được nguyên vẹn. `zone_adapter.py` chỉ cần là một hàm
dựng `Para`/`EffFormat`/`IntermediateDoc` từ text + `align` suy ra từ bbox của
OCR, rồi gọi thẳng `detect_zones` đã có — không cần suy `bold`/`size_pt` từ
chiều cao bbox. Khoảng hở `RE_TRICH_YEU` phát hiện ở trên là vấn đề có sẵn
của `aidt_format_engine`, nên ghi nhận riêng cho một ticket sau này, không xử
lý trong Task 9.

## 3. Số đo R3

Container `unlimited-ocr` gỡ và dựng lại 3 lần với `--gpu-memory-utilization`
khác nhau:

| utilization | Kết quả | Lỗi |
|---|---|---|
| 0.55 (theo brief) | **Không chạy được** — crash loop | `ValueError: No available memory for the cache blocks` (`Available KV cache memory: -0.87 GiB`) |
| 0.65 (bậc kế theo brief) | **Không chạy được** — crash loop | `ValueError: ... 1.88 GiB KV cache is needed ... available KV cache memory (0.68 GiB)` |
| 0.75 (vượt brief, thử thêm vì cả hai mức trên đều không khởi động được) | **Chạy được**, healthy | — |

VRAM còn trống ở mức chạy được (0.75), đo 2 lần cách nhau vài giây:
`5270 MiB` rồi `4886 MiB` free trên tổng `16311 MiB` (tức ~10.6–11.0 GB đang
dùng). So với trạng thái cũ không giới hạn (`13656 MiB` dùng / `2187 MiB`
free), khoảng trống tăng thêm ~2.7–3.1 GB — có tăng, nhưng chỉ bằng khoảng
một nửa mức brief kỳ vọng khi chọn 0.55.

Tốc độ OCR 1 trang thật (`docs/demo/01-dat-chuan.pdf`, 150dpi) ở mức 0.75, 3
lần đo:

```
3.56s  usage={'prompt_tokens': 907, 'total_tokens': 1348, 'completion_tokens': 441, ...}
2.62s  usage={'prompt_tokens': 907, 'total_tokens': 1348, 'completion_tokens': 441, ...}
2.62s  usage={'prompt_tokens': 907, 'total_tokens': 1348, 'completion_tokens': 441, ...}
```

Lần đầu (3.56s) là cold-start sau khi model vừa nạp/compile; ổn định ở
2.62s/trang — nhanh hơn nhẹ so với mốc **2.7s/trang** đo được ở cấu hình cũ
không giới hạn VRAM, tức không có suy giảm tốc độ đáng kể ở 0.75. Không cần
áp dụng nhánh "embedding phải chạy CPU" của brief vì tốc độ đạt yêu cầu (dưới
2×); vấn đề thật là **mức 0.55/0.65 mà brief nêu không khởi động được**,
không phải chuyện chậm.

Container hiện đang chạy ở `--gpu-memory-utilization 0.75` (mức duy nhất
trong 3 mức chạy được), để lại ở trạng thái hoạt động thay vì trạng thái
crash loop của 0.55.

## 4. Quyết định cho Task 2

Giả định trong plan Task 2 ("OCR ở 0.55 + embed ở 0.15 vẫn còn dư") sai:
OCR không khởi động được dưới ~0.75. Đề xuất sửa Task 2:

- Đổi `--gpu-memory-utilization` của service OCR trong `docker-compose.dev.yml`
  từ `0.55` thành `0.75`.
- Ngân sách VRAM cộng dồn trở thành `0.75 + 0.15 = 0.90` trên tổng 16.3GB,
  còn dư lý thuyết ~1.6GB — hẹp hơn nhiều so với ~4.9GB plan giả định.
- Task 2 nên dựng cả hai service cùng lúc và đo `nvidia-smi` thật trước khi
  tin số trên giấy; nếu không cùng tồn tại được, dùng đúng nhánh dự phòng của
  brief: embedding chạy CPU.

## 5. Bổ sung từ Task 2 (thực thi hạ tầng)

Đo thật lúc cả hai service cùng chạy: **12532 MiB dùng / 3310 MiB trống**
trên tổng 16311 MiB — dư hơn ước tính lý thuyết ~1.6GB ở mục 4, vì cả OCR
(0.75) lẫn embedding (0.15) đều dùng ít VRAM thực tế hơn phần dành riêng.
Không cần dùng nhánh CPU cho embedding.

**vLLM CLI: cờ `--task` không còn tồn tại.** Image `vllm/vllm-openai:latest`
kéo về ở thời điểm Task 2 chạy là vLLM **0.26.0**. Cờ `--task=embed` (dùng
trong bản kế hoạch gốc và trong brief Task 2) bị từ chối: `vllm: error:
unrecognized arguments: --task=embed`, container crash-loop
(`Exited (2)`). Thay thế đúng ở vLLM 0.26 là hai cờ tách riêng:
`--runner=pooling` (chọn loại model runner: generate/pooling/draft/auto)
và `--convert=embed` (áp adapter chuyển model sinh văn bản thành model
pooling: classify/embed/none/auto). Đã sửa trong
`docker-compose.dev.yml`, service `aidt-embed`, kèm comment tại chỗ. Bất kỳ
task nào sau này viết lại lệnh `vllm serve` cho một service mới (không chỉ
sao chép từ compose file này) cần dùng `--runner`/`--convert`, không phải
`--task`.

**`aidt_demo` hiện chỉ có extension, chưa có schema Odoo.** Task 2 phát
hiện database `aidt_demo` không tồn tại từ trước trong môi trường thực thi
(không có volume `db-data-dev`, không có container `aidt-odoo-dev-db-1`/
`aidt-odoo-dev-odoo-1` nào chạy trước đó) — tạo mới, chỉ cài `vector` +
`unaccent`, không chạy `-i base` hay bất kỳ module nào (ngoài phạm vi file
Task 2 được phép sửa). Kết quả: không có bảng `ir_module_module` (hay bất kỳ
bảng model Odoo nào khác), chỉ có các bảng `orm_signaling_*` do Odoo tự tạo
khi kết nối registry lần đầu. Task tiếp theo cần cài module vào `aidt_demo`
nên tính đây là **bootstrap từ đầu** (`-i base` rồi mới `-i <module>`), không
phải một lần `-u`/thêm module gia tăng vào một CSDL đã có sẵn dữ liệu demo.
