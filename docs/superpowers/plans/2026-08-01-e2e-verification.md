# Kiểm chứng đầu-cuối — Document Intelligence Search

Ngày chạy: **2026-08-02**
Database: **`aidt_demo`** (database duy nhất, theo `CLAUDE.md`)
Máy: RTX 3060 12 GB, `pgvector/pgvector:pg16` (`vector` 0.8.6 + `unaccent`), poppler 22.12.0, `soffice` trong container odoo.
Spec đối chiếu: [`docs/superpowers/specs/2026-08-01-document-intelligence-search-design.md`](../specs/2026-08-01-document-intelligence-search-design.md) §11.

> **Đây là lần đầu tiên toàn hệ thống chạy với embedding THẬT.** Mọi task
> trước đều mock service embedding. Tài liệu này ghi kết quả thật, **kể cả
> những chỗ sai**; các mục "không đạt" ở §9 quan trọng hơn các mục đạt.

---

## 0. Sai lệch của brief/kế hoạch đã phải xử lý

| Brief nói | Thực tế | Xử lý |
|---|---|---|
| `cd /home/chauanphu/projects/aidt-odoo` | Đường dẫn không tồn tại | Repo thật là `/home/aphuc/dev/aidt-odoo` — đã sửa trong mục Task 18 của kế hoạch |
| Đính kèm `docs/demo/01-dat-chuan.pdf` | `docs/demo/` **chỉ có `.docx`** | Nạp **cả hai**: `01-dat-chuan.docx` và bản PDF do `soffice` chuyển đổi, thành hai văn bản riêng, để chạy cả hai nhánh trích xuất |
| `docker compose exec odoo odoo shell ...` | `odoo` **không có trong `$PATH`** khi `exec` (chỉ có qua entrypoint của `run`) | Dùng `/opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf` |
| Expected `~112 passed` / `~60 passed` | Số thật: **125 passed, 3 skipped** / **100 tests** | Đã cập nhật trong kế hoạch |
| Truy vấn kịch bản về "hỗ trợ hộ nghèo" | **Không văn bản nào trong `aidt_demo` nói về hộ nghèo** | Vẫn chạy đủ 5 câu và ghi kết quả thật; bổ sung cặp truy vấn #6/#7 khớp nội dung đã nạp để §11.2/§11.3 có bằng chứng thật |

Dữ liệu nạp thêm (giữ lại, là demo state hợp lệ của `aidt_demo`):

| Doc id | `reference` | Tệp | `secrecy` | Đơn vị |
|---|---|---|---|---|
| 83480 | `145/KH-UBND` | `01-dat-chuan.docx` | `thuong` | Phòng Tổng hợp (id 4) |
| 83481 | `145/KH-UBND-PDF` | `01-dat-chuan.pdf` | `thuong` | Phòng Tổng hợp (id 4) |
| 83482 | `147/KH-UBND-MAT` | `01-dat-chuan-mat.pdf` (cùng bytes với 83481) | `mat` | Phòng Tổng hợp (id 4) |

Ba văn bản cùng đơn vị, cùng nội dung, chỉ khác `secrecy` — cố ý, để phép thử
phân quyền ở §6 cô lập đúng một biến.

---

## 1. Bộ test (§11.7)

Cả hai bộ chạy **trước khi `aidt-embed` tồn tại** (image còn đang tải) — nghĩa
là không có bất kỳ service GPU nào để chạm tới. Đây chính là bằng chứng cho
§11.7.

### Tầng 1 — thư viện thuần

```
$ cd /home/aphuc/dev/aidt-odoo/custom-addons && python -m pytest aidt_search_engine/tests -q
125 passed, 3 skipped in 0.56s
```

### Tầng 2 — Odoo

```
$ docker compose -f docker-compose.dev.yml run --rm odoo \
    odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search \
    --stop-after-init --addons-path=...
...
2026-08-02 03:32:40 ERROR aidt_demo odoo.sql_db: bad query: ... aidt_index_job ...
  ERROR:  duplicate key value violates unique constraint "aidt_index_job_active_file_uniq"      (×2)
2026-08-02 03:32:53 ERROR aidt_demo ...search_log: Không ghi được nhật ký tìm kiếm cho user 338 ...   (×2)
2026-08-02 03:32:53 ERROR aidt_demo ...search_service: Không ghi được nhật ký tìm kiếm; kết quả vẫn được trả về ...
2026-08-02 03:32:57 ERROR aidt_demo ...search_log: Từ chối ghi nhật ký tìm kiếm dưới quyền sudo/superuser ...
2026-08-02 03:33:08,553 INFO aidt_demo odoo.tests.result: 0 failed, 0 error(s) of 100 tests when loading database 'aidt_demo'
EXIT=0
```

Sáu dòng `ERROR` ở trên là **tiếng ồn có chủ đích của chính bộ test** (đã biết
trước, đã ghi lại trong README §4): `TestDedupRaceInFlight` cố tình đụng chỉ
mục UNIQUE riêng phần, và `TestSearchLogDoesNotBreakSearch` mock cho log ném
lỗi. `odoo.tests.result` mới là con số phải theo dõi (**không** phải
`odoo.tests.stats`, vốn đếm mục thời gian).

**Kết luận: cả hai bộ xanh. §11.7 ĐẠT.**

---

## 2. Số chiều embedding — kiểm TRƯỚC khi nạp bất cứ thứ gì (§6.2 bẫy 2)

`aidt.doc.chunk.embedding` là `vector(1024)`; `aidt_search.embed_dim = 1024`.
`embed()` ném `EmbedDimensionError` nếu lệch. Kiểm ngay khi service lên, trước
khi nạp tài liệu:

```
$ curl -s http://localhost:8001/v1/embeddings -H 'Content-Type: application/json' \
    -d '{"model":"AITeamVN/Vietnamese_Embedding","input":["hỗ trợ hộ nghèo","kế hoạch 145/KH-UBND"]}'
n rows: 2
 index 0 dim 1024
 index 1 dim 1024
model: AITeamVN/Vietnamese_Embedding
usage: {'prompt_tokens': 16, 'total_tokens': 16, ...}
```

**`AITeamVN/Vietnamese_Embedding` trả đúng 1024 chiều. KHỚP cột. ĐẠT.**

Ghi chú vận hành: vLLM 0.26.0, `XLMRobertaModel`, `seq_pooling_type='CLS'`,
`--runner=pooling --convert=embed`, `--gpu-memory-utilization=0.15`. VRAM thực
đo sau khi nạp: **2241 MiB** trên tổng 12288 MiB. Thời gian từ `Started` tới
`Application startup complete`: ~2 phút (weights 5.6 GB tải mới về
`~/.cache/huggingface`); image `vllm/vllm-openai:latest` 18.9 GB tải mất ~35
phút.

---

## 3. Nạp tài liệu và soi chunk (§11.1)

Tắt `ir.cron` trong lúc chuẩn bị (để job không bị đốt `attempt` khi service
chưa lên), tạo văn bản, rồi chạy tay `_cron_process()`:

```
cron elapsed 0.6s
JOB 873 doc 83480 01-dat-chuan.docx     -> done | attempt 0 | stage_ms {'chunk': 0, 'embed': 138, 'extract': 53}
JOB 874 doc 83481 01-dat-chuan.pdf      -> done | attempt 0 | stage_ms {'chunk': 0, 'embed': 99,  'extract': 28}
JOB 875 doc 83482 01-dat-chuan-mat.pdf  -> done | attempt 0 | stage_ms {'dedup': 0}
```

`stage_ms` của job 875 là `{'dedup': 0}` → **chống trùng theo `content_hash`
chạy đúng**: tệp thứ ba có cùng bytes với tệp thứ hai nên chunk được chép
sang, không gọi GPU lần nữa (§4.3). Xem thêm phát hiện **F-6** ở §9.

```
doc_id | chunks | with_embedding | with_ts
(83480, 13, 13, 13)     ← DOCX
(83481, 11, 11, 11)     ← PDF
(83482, 11, 11, 11)     ← PDF, chép từ twin
```

Mọi chunk đều có vector thật và tsvector.

### 3.1. Nhánh DOCX (83480, 13 chunk, `zone_confidence='style'`)

| seq | zone | text |
|---|---|---|
| 0 | `ten_co_quan` | `ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG` |
| 1 | `quoc_hieu` | `CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM` |
| 2 | `tieu_ngu` | `Độc lập - Tự do - Hạnh phúc` |
| 3 | **`so_ky_hieu`** | **`Số: 145/KH-UBND`** |
| 4 | `dia_danh_ngay` | `Bình Dương, ngày 25 tháng 7 năm 2026` |
| 5 | `ten_loai` | `KẾ HOẠCH` |
| 6 | `trich_yeu` | `Về việc triển khai nhiệm vụ quý III năm 2026` |
| 7 | `noi_dung` | `Thực hiện chương trình công tác năm 2026, Văn phòng đề nghị các đơn vị…` |
| 8 | **`noi_nhan`** | `Nơi nhận:` |
| 9 | **`noi_nhan`** | `- Các ban, phòng trực thuộc;` |
| 10 | **`noi_nhan`** | `- Lưu: VT.` |
| 11 | **`chu_ky`** | `CHỦ TỊCH` |
| 12 | `ho_ten_nguoi_ky` | `Nguyễn Văn A` |

Contextual header đúng định dạng §4.6 và lưu nguyên vào `embed_text`:

```
Kế hoạch 145/KH-UBND — E2E DOCX — Kế hoạch triển khai nhiệm vụ quý III năm 2026
---
Số: 145/KH-UBND
```

Đối chiếu ba điều brief yêu cầu kiểm:

- ✅ `so_ky_hieu` bắt được `145/KH-UBND` — chunk seq 3, **đứng riêng**.
- ⚠️ `noi_nhan` **KHÔNG** gọn trong một chunk: bị tách thành **ba** chunk
  (seq 8/9/10). `chu_ky` thì đúng một chunk (seq 11) — nhưng tên người ký nằm
  ở zone khác (`ho_ten_nguoi_ky`, seq 12) nên khối chữ ký vẫn bị chẻ đôi.
  Xem **F-1** ở §9.
- ✅ `heading_path` rỗng ở mọi chunk — **hợp lý**: văn bản mẫu không có
  `PHẦN`/`CHƯƠNG`/`MỤC`/`Điều` nào. Không có tài liệu nào trong `aidt_demo`
  đủ dài để kiểm `heading_path` khác rỗng ⇒ **nhánh đó chưa được kiểm chứng
  đầu-cuối** (chỉ có test tầng 1 phủ).

### 3.2. Nhánh PDF (83481, 11 chunk, `zone_confidence='heuristic'`)

| seq | zone | text |
|---|---|---|
| 0 | `ten_co_quan` | `ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM` |
| 1 | `tieu_ngu` | `Độc lập - Tự do - Hạnh phúc` |
| 2 | **`so_ky_hieu`** | **`Số: 145/KH-UBND`** |
| 3 | `dia_danh_ngay` | `Bình Dương, ngày 25 tháng 7 năm 2026` |
| 4 | `noi_dung` | `KẾ HOẠCH` |
| 5 | `trich_yeu` | `Về việc triển khai nhiệm vụ quý III năm 2026` |
| 6 | `noi_dung` | `Thực hiện chương trình công tác năm 2026, Văn phòng đề ngh ị các đ ơn\nvị trực thuộc … báo cáo kết qu ả\nvề Văn phòng trước ngày 30 tháng 9 năm 2026.` |
| 7 | `noi_nhan` | `Nơi nhận:` |
| 8 | `noi_nhan` | `- Các ban, phòng trực thuộc;` |
| 9 | `noi_nhan` | `- Lưu: VT.` |
| 10 | `noi_dung` | `CHỦ TỊCH\nNguyễn Văn A` |

`page = 1` đúng; `bbox = False` (đúng thiết kế — chỉ nhánh OCR có bbox).

### 3.3. Khác biệt DOCX ↔ PDF — đây mới là phần đáng giá

| # | Điều | DOCX | PDF | Ảnh hưởng |
|---|---|---|---|---|
| 1 | `zone_confidence` | `style` (100 % chính xác) | `heuristic` | Đúng như spec §4.5 dự đoán |
| 2 | `quoc_hieu` | có, chunk riêng | **MẤT** — bị gộp vào `ten_co_quan` (seq 0) | Hai dòng nằm cạnh nhau trên cùng hàng của bảng đầu trang; `pdftotext -layout` xuất thành hai dòng liền kề, heuristic gán cả cụm cho zone đầu |
| 3 | `ten_loai` (`KẾ HOẠCH`) | `ten_loai` | **`noi_dung`** (sai) | Mất tín hiệu "đây là Kế hoạch" trong chỉ mục |
| 4 | `chu_ky` + `ho_ten_nguoi_ky` | hai chunk, đúng zone | **gộp thành một chunk `noi_dung`** | Vùng chữ ký — thứ §4.6 nói "luôn đứng riêng" — biến mất hoàn toàn trên nhánh PDF |
| 5 | Chất lượng text | sạch | **`đề ngh ị`, `đ ơn`, `kết qu ả`** — `pdftotext` chèn khoảng trắng giữa âm tiết | `to_tsvector('simple')` sinh token `ngh`, `ị`, `qu`, `ả`; kênh lexical **không tìm được `nghị`, `quả`** trên văn bản PDF |
| 6 | Số chunk | 13 | 11 | Hệ quả của 2 + 4 |

**Kết luận §11.1 (docx + pdf-có-lớp-text): ĐẠT về mặt "được chỉ mục tự động,
thấy tiến trình/lỗi trên UI"** — `index_state` = `indexed`, `chunk_count` =
13/11/11, màn hình *Hàng đợi chỉ mục* hiển thị `state`/`error_kind`/`stage_ms`
và có nút *Nạp lại*.
**KHÔNG kiểm chứng được nhánh `pdf` scan / ảnh** — xem **F-7**.

---

## 4. Năm truy vấn kịch bản (§11.2 → §11.4)

Chạy qua `env['aidt.search.service'].with_user(2)` (admin, `env.su = False`).
Bổ sung #6/#7 vì #1/#2/#5 không khớp nội dung nào trong kho.

### #1 `hỗ trợ hộ nghèo` — **KHÔNG ĐẠT như kỳ vọng**

```
reference     : None
filters       : []
channels_used : ['vector', 'lexical', 'lexical_noaccent']
degraded      : False
total         : 3 | truncated: False | indexing: 0 | log_id: 942
facets        : {"doc_type": [["ke_hoach", 3]], "department_id": [[4, 3]],
                 "secrecy": [["mat", 1], ["thuong", 2]]}
documents:
  [83481] E2E PDF …   snippets: "Nơi nhận:" / "Thực hiện chương trình công tác năm 2026, Văn phòng đề ngh" / "- Lưu: VT."
  [83482] E2E MẬT …   snippets: (như trên)
  [83480] E2E DOCX …  snippets: "Nơi nhận:" / "Thực hiện chương trình công tác năm 2026, Văn phòng đề nghị" / "- Lưu: VT."
```

Kỳ vọng của brief: *"Ra văn bản, có trích đoạn highlight"*. Thực tế: **ra 3
văn bản không hề nói về hộ nghèo, và trích đoạn KHÔNG có `<mark>` nào**.
Nguyên nhân đã xác định (không phải suy đoán): §7 dưới đây cho thấy khi tắt
`aidt-embed`, đúng câu này trả **0 kết quả** — nghĩa là cả 3 kết quả đến
100 % từ kênh vector. Hệ thống **không có ngưỡng liên quan tối thiểu**: kênh
vector luôn trả về láng giềng gần nhất dù xa đến đâu. Xem **F-2**.

### #2 `ho tro ho ngheo` — **ĐẠT MỘT PHẦN**

```
channels_used : ['vector', 'lexical', 'lexical_noaccent']
total         : 3
documents     : [83480], [83481], [83482]     ← #1 là [83481], [83482], [83480]
```

**Cùng TẬP kết quả với #1, KHÁC THỨ TỰ.** Tập giống nhau vì kho chỉ có 3 văn
bản chỉ mục được; thứ tự khác vì chuỗi có dấu và chuỗi không dấu embed ra hai
vector khác nhau nên kênh vector xếp hạng khác. Kênh `lexical_noaccent` có
chạy (`channels_used` liệt kê đủ) nhưng ở câu này nó cũng không khớp gì.
Bằng chứng thật cho §11.3 nằm ở #6, không nằm ở đây.

### #3 `145/KH-UBND` — **ĐẠT**

```
reference     : 145/KH-UBND
filters       : []
channels_used : []            ← KHÔNG có kênh nào chạy: đi thẳng nhánh SQL
degraded      : False
total         : 1
documents:
  [83480] E2E DOCX — … | ref='145/KH-UBND' type=ke_hoach secrecy=thuong dept=Phòng Tổng hợp
facets        : {"doc_type": [["ke_hoach", 1]], "department_id": [[4, 1]], "secrecy": [["thuong", 1]]}
```

Đúng một văn bản, `reference` khác `null`, `channels_used == []` chứng minh
**không đi qua kênh vector**. Khớp lại qua RPC HTTP thật (§8): kết quả y hệt.
**§11.4 ĐẠT.**

### #4 `kế hoạch năm 2026` — **ĐẠT**

```
filters: [('date', 'Năm 2026', ['2026-01-01', '2026-12-31'], span=[9, 17]),
          ('doc_type', 'Kế hoạch', 'ke_hoach', span=[0, 8])]
channels_used : []            ← phần ngữ nghĩa rỗng → nhánh metadata
total: 7 | truncated: False
  [83480] 2026-07-25  [83481] 2026-07-25  [83482] 2026-07-25
  [5] Dự thảo kế hoạch công tác tháng 5 (2026-04-25)
  [7] Kế hoạch luân chuyển cán bộ năm 2026 (2026-02-20)
  [10] Kế hoạch tuyên truyền kỷ niệm các ngày lễ lớn (2026-01-25)
  [14] Kế hoạch kiểm tra tổ chức đảng cấp dưới năm 2026 (2026-02-10)
```

Chip *"Đã hiểu"* hiện **cả `Năm 2026` lẫn `Kế hoạch`**, đúng yêu cầu. Cả 7 kết
quả đều `doc_type = ke_hoach` và `date` trong 2026. `span` được trả ra để giao
diện xoá chip một cách thật (cắt đúng đoạn khỏi câu rồi tìm lại).

### #5 `an toàn thông tin quý III năm 2026` — **ĐẠT MỘT PHẦN**

```
filters: [('date', 'Quý III/2026', ['2026-07-01', '2026-09-30'], span=[18, 34])]
channels_used : ['vector', 'lexical', 'lexical_noaccent']
total : 3   → [83480], [83481], [83482]   (đều date = 2026-07-25 ✓ nằm trong khoảng)
snippets: "Nơi nhận:", "Độc lập - Tự do - Hạnh phúc", "Nguyễn Văn A"  ← không <mark> nào
```

- ✅ Chip hiện **`Quý III/2026`**, khoảng ngày bóc đúng `2026-07-01 … 2026-09-30`.
- ✅ Kết quả lọc đúng khoảng — cả 3 văn bản đều ban hành 2026-07-25.
- ❌ Nhưng cả 3 **không liên quan gì tới "an toàn thông tin"**, và trích đoạn
  vô nghĩa (`Độc lập - Tự do - Hạnh phúc`, `Nguyễn Văn A`). Lại là **F-2**.

### #6 (bổ sung) cặp có dấu / không dấu KHỚP nội dung thật

`#6a triển khai nhiệm vụ quý III năm 2026`:

```
filters: [('date', 'Quý III/2026', ['2026-07-01','2026-09-30'], span=[20, 36])]
total: 3 → [83480], [83481], [83482]
[83480] zone=trich_yeu: "Về việc <mark>triển</mark> <mark>khai</mark> <mark>nhiệm</mark> <mark>vụ</mark> quý III năm"
```

`#6b trien khai nhiem vu quy III nam 2026`:

```
filters: []                     ← KHÔNG bóc được filter ngày nào
total: 3 → [83480], [83481], [83482]
[83480] zone=trich_yeu: "Về việc triển <mark>khai</mark> nhiệm vụ quý <mark>III</mark> năm <mark>2026</mark>"
```

- ✅ **Cùng tập văn bản, cùng thứ tự** — kênh `ts_noaccent` + `f_unaccent`
  chạy đúng. Đây là bằng chứng thật cho **§11.3**.
- ✅ **§11.2**: trả về văn bản đúng, **có trích đoạn `<mark>`**, có `zone` và
  `page`; `heading_path` rỗng vì tài liệu không có mục.
- ❌ Hai lệch thật lộ ra: (a) truy vấn không dấu **mất toàn bộ filter cứng**
  (`quy III nam 2026` không khớp regex có dấu) — **F-3**; (b) `ts_headline`
  tính trên `parsed.semantic` **không dấu** đối chiếu text **có dấu**, nên chỉ
  `khai`/`III`/`2026` được highlight, `trien`/`nhiem`/`vu` thì không —
  **F-4**.

### #7 (bổ sung) `báo cáo kết quả về Văn phòng` — **KHÔNG ĐẠT**

```
#7a 'báo cáo kết quả về Văn phòng'
  filters: [('doc_type', 'Báo cáo', 'bao_cao', span=[0, 7])]
  total: 0 | facets: {"doc_type": [], "department_id": [], "secrecy": []}

#7b 'bao cao ket qua ve Van phong'
  filters: [('doc_type', 'Báo cáo', 'bao_cao', span=[0, 7])]
  total: 0
```

Cụm **"báo cáo kết quả về Văn phòng" nằm nguyên văn trong thân cả 3 văn bản**,
vậy mà kết quả rỗng: `báo cáo` bị bóc thành filter cứng `doc_type = bao_cao`,
loại sạch mọi văn bản loại Kế hoạch. Đây là đúng loại lỗi mà
`_FALSE_FRIEND_CONTINUATIONS` (`khẩn cấp`) đã chặn cho một trường hợp, nhưng
`báo cáo`/`kế hoạch`/`thông báo` dùng làm động từ/danh từ thường trong câu thì
chưa. Xem **F-5**.

---

## 5. Bảng tổng hợp 5 truy vấn của brief

| # | Truy vấn | Kỳ vọng của brief | Thực tế | Kết luận |
|---|---|---|---|---|
| 1 | `hỗ trợ hộ nghèo` | Ra văn bản, có highlight | Ra 3 văn bản **không liên quan**, **không highlight** | ❌ |
| 2 | `ho tro ho ngheo` | Cùng kết quả với #1 | Cùng **tập**, **khác thứ tự** | ⚠️ |
| 3 | `145/KH-UBND` | Đúng 1 VB, `reference` ≠ null, không qua vector | Đúng 1 VB, `reference='145/KH-UBND'`, `channels_used=[]` | ✅ |
| 4 | `kế hoạch năm 2026` | Chip `Năm 2026` **và** `Kế hoạch` | Đúng cả hai chip, 7 VB đều khớp | ✅ |
| 5 | `an toàn thông tin quý III năm 2026` | Chip `Quý III/2026`, lọc đúng khoảng | Chip + khoảng đúng; **kết quả không liên quan, không highlight** | ⚠️ |

**2/5 đạt hoàn toàn, 2/5 đạt một phần, 1/5 không đạt.** Hai câu bổ sung #6a/#6b
đạt đầy đủ tiêu chí §11.2 và §11.3 trên nội dung thật.

---

## 6. Phân quyền, kiểm bằng tay (§11.5)

Cùng một truy vấn `triển khai nhiệm vụ quý III năm 2026`, ba người dùng thật:

```
uid=2  admin        dept=Administration                     clearance=3
   total=3  ids=[83480, 83481, 83482]
   facets={"doc_type": [["ke_hoach",3]], "department_id": [[4,3]],
           "secrecy": [["mat",1],["thuong",2]]}

uid=10 cv.tonghop1  dept=…/Văn phòng Tỉnh ủy/Phòng Tổng hợp clearance=0
   total=2  ids=[83480, 83481]
   facets={"doc_type": [["ke_hoach",2]], "department_id": [[4,2]],
           "secrecy": [["thuong",2]]}          ← KHÔNG có mục "mat"
   E2E MẬT visible=False
   aidt.doc.chunk của 83482 đếm được: 0

uid=21 cv.lyluan    dept=…/Ban Tuyên giáo/Phòng Lý luận CT  clearance=0
   total=0  ids=[]
   facets={"doc_type": [], "department_id": [], "secrecy": []}
   E2E DOCX / E2E PDF / E2E MẬT đều visible=False
   aidt.doc.chunk của 83482 đếm được: 0
```

- **Không rò tiêu đề**: `cv.tonghop1` (cùng phòng, `clearance=0`) không thấy
  văn bản `mat`; `cv.lyluan` (phòng khác) không thấy văn bản nào trong ba.
- **Không rò số đếm facet**: facet `secrecy` của `cv.tonghop1` chỉ có
  `[["thuong", 2]]` — mục `mat` **biến mất hoàn toàn**, không phải hiện với
  số 0.
- **Chunk cũng bị chặn** ở tầng model: `aidt.doc.chunk.search_count` = 0.

Đọc thẳng bản ghi mật (sau `env.invalidate_all()`):

```
uid=10 cv.tonghop1  browse(83482).name -> AccessError: … doesn't have 'read' access to: - Văn bản (aidt.document)
       search_count(id=83482) = 0
uid=21 cv.lyluan    browse(83482).name -> AccessError: … doesn't have 'read' access to: - Văn bản (aidt.document)
       search_count(id=83482) = 0
```

> **Cảnh báo phương pháp, ghi lại để người sau không bị lừa:** ở lần chạy đầu
> tiên, `browse(83482).name` trả về **tên văn bản mật cho cả ba user** — trông
> như một lỗ hổng. Không phải: `env.cache` dùng chung giữa các `with_user()`
> trong cùng một `Environment`, và vòng lặp admin ở ngay trên đã nạp sẵn giá
> trị vào cache. Phải `env.invalidate_all()` giữa các user thì phép thử mới có
> nghĩa. **Bất kỳ kiểm chứng ACL nào bằng `odoo shell` mà không invalidate
> cache đều cho kết quả sai.**

Nhật ký N-08 cũng chỉ ghi những gì người dùng thật sự thấy:

```
LOG user=cv.tonghop1 raw='triển khai nhiệm vụ quý III năm 2026' sem='triển khai nhiệm vụ'
    ch='vector,lexical,lexical_noaccent' degr=False ms=142 results=[83481, 83480]
    filters_json: [{'field': 'date', 'label': 'Quý III/2026'}]

owner click 83481               -> True ;  clicked_document_id = 83481
người khác (uid 21)             -> AccessError: Không được sửa nhật ký tìm kiếm của người khác.
văn bản không có trong kết quả  -> AccessError: Văn bản này không nằm trong kết quả của chính lượt tìm kiếm này…
```

**§11.5 ĐẠT** (test tự động V-13/O-03 đã phủ; đây là lần nhìn tận mắt).

---

## 7. Giảm cấp mềm — kiểm cả HAI chiều (§11.6)

Chiều **bật → tắt** (`docker compose … stop aidt-embed`):

```
=== 'hỗ trợ hộ nghèo'
  channels_used: ['lexical', 'lexical_noaccent']
  degraded     : True
  warning      : Tìm kiếm ngữ nghĩa tạm ngưng — đang tìm bằng từ khoá.
  total        : 0 | ids: []

WARNING …search_service: Kênh vector không dùng được, chạy tiếp lexical:
  gọi embedding thất bại: <urlopen error [Errno -3] Temporary failure in name resolution>

=== 'triển khai nhiệm vụ quý III năm 2026'
  channels_used: ['lexical', 'lexical_noaccent']
  degraded     : True
  warning      : Tìm kiếm ngữ nghĩa tạm ngưng — đang tìm bằng từ khoá.
  total        : 3 | ids: [83480, 83481, 83482]
  facets       : {"doc_type": [["ke_hoach",3]], "department_id": [[4,3]], "secrecy": [["mat",1],["thuong",2]]}
    [83480] Về việc <mark>triển</mark> <mark>khai</mark> <mark>nhiệm</mark> <mark>vụ</mark> quý III nă
```

Chiều **tắt → bật** (`docker compose … start aidt-embed`, chờ `/health` = 200):

```
=== 'hỗ trợ hộ nghèo'
  channels_used: ['vector', 'lexical', 'lexical_noaccent']
  degraded     : False | warning: False
  total        : 3 | ids: [83481, 83482, 83480]        ← y hệt lần chạy đầu, cùng thứ tự

=== 'triển khai nhiệm vụ quý III năm 2026'
  channels_used: ['vector', 'lexical', 'lexical_noaccent']
  degraded     : False | warning: False
  total        : 3 | ids: [83480, 83481, 83482]
```

- ✅ Tắt service → **vẫn ra kết quả** cho truy vấn có từ khoá khớp, `degraded`
  = `True`, `warning` đúng chuỗi giao diện hiển thị trong dải vàng
  (`alert-warning` trong `search_view.xml`), không có ngoại lệ nào lọt ra.
- ✅ Bật lại → tự phục hồi ở lượt tìm kế tiếp, `degraded` về `False`, không
  cần khởi động lại Odoo, không cần xoá cache.
- ✅ Thứ tự kết quả **tất định** giữa hai lần chạy có vector (nhờ tiebreaker
  `, c.id`).
- ⚠️ Đồng thời phơi ra **F-2**: `hỗ trợ hộ nghèo` cho **0 kết quả** khi tắt
  vector và **3 kết quả** khi bật — chứng minh 3 kết quả đó thuần tuý là láng
  giềng gần nhất, không có ngưỡng liên quan nào.

**§11.6 ĐẠT.**

---

## 8. Kiểm qua RPC HTTP thật (bề mặt mà client OWL dùng)

Không chỉ qua `odoo shell` — gọi đúng `call_kw` mà `search_view.js` gọi:

```
$ curl -c cookies -X POST /web/session/authenticate  -> uid = 2
$ curl -b cookies -X POST /web/dataset/call_kw \
    -d '{"params":{"model":"aidt.search.service","method":"search","args":["145/KH-UBND",[]]}}'
reference: 145/KH-UBND | channels: [] | degraded: False | total: 1 | log_id: 959
   83480 145/KH-UBND E2E DOCX — Kế hoạch triển khai nhiệm vụ quý III nă
facets: {"doc_type": [["ke_hoach",1]], "department_id": [[4,1]], "secrecy": [["thuong",1]]}

$ … args: ["triển khai nhiệm vụ", []]
channels: ['vector','lexical','lexical_noaccent'] | total: 3 | log_id: 960 | indexing: 0
   83480 …  "Về việc <mark>triển</mark> <mark>khai</mark> <mark>nhiệm</mark> <mark>vụ</mark> quý III năm"
```

`log_id` có mặt trong payload ⇒ `action_click()` gọi được từ client (không
phải dead code). `indexing: 0` ⇒ phân biệt được "kho đang xử lý N tệp" với
"không có kết quả" (§6.2 bẫy 3).

---

## 9. Danh sách những gì KHÔNG đúng như spec/kế hoạch dự đoán

| Mã | Mức | Phát hiện |
|---|---|---|
| **F-1** | Trung bình | §4.6 nói `noi_nhan` và `chu_ky` "luôn đứng riêng một chunk". Thực tế mỗi **block** của zone thành một chunk: `noi_nhan` ra **3 chunk** rời (`Nơi nhận:` / `- Các ban…` / `- Lưu: VT.`), và khối chữ ký bị chẻ đôi giữa `chu_ky` và `ho_ten_nguoi_ky`. Câu trả lời cho "văn bản này gửi ai?" bị phân mảnh đúng ở chỗ spec muốn nó nguyên vẹn. Sửa: gộp các block liên tiếp cùng zone của bốn vùng đó thành một chunk. |
| **F-2** | **Cao** | **Không có ngưỡng liên quan tối thiểu trên kênh vector.** `hỗ trợ hộ nghèo` và `an toàn thông tin` — hai chủ đề hoàn toàn vắng mặt trong kho — vẫn trả về đủ 3 văn bản, không highlight. Chứng minh trực tiếp: tắt `aidt-embed` thì đúng câu đó trả **0**. Với kho vài trăm văn bản, người dùng sẽ luôn nhận được "kết quả" cho mọi câu hỏi, kể cả câu không có đáp án — đây là kiểu đánh lừa mà §6.2 muốn chặn, chỉ khác đường. Sửa: thêm ngưỡng cosine (hoặc ngưỡng điểm RRF) cấu hình được, dưới ngưỡng thì loại khỏi kênh vector. |
| **F-3** | Trung bình | **`intent.parse_query()` phụ thuộc dấu.** `quy III nam 2026` (không dấu) không khớp `_QUARTER_RE`/`_YEAR_RE` (đều viết `quý`, `năm` có dấu) nên **mất sạch filter cứng**, trong khi chính spec §5.1 lấy người gõ không dấu làm ca dùng chính. `#6a` bóc được `Quý III/2026`, `#6b` bóc được `[]`. Sửa: chạy regex trên chuỗi đã `strip_accents()` rồi ánh xạ span ngược về `raw`. |
| **F-4** | Thấp | **Highlight lệch với kênh không dấu.** `ts_headline` nhận `parsed.semantic` nguyên trạng (không dấu) đối chiếu `c.text` (có dấu) ⇒ chỉ token vốn không dấu (`khai`, `III`, `2026`) được `<mark>`. Người gõ không dấu tìm ra đúng văn bản nhưng trích đoạn highlight sai chỗ. |
| **F-5** | **Cao** | **Nhãn danh mục nuốt nhầm từ thông thường.** `báo cáo kết quả về Văn phòng` → filter cứng `doc_type = bao_cao` → **0 kết quả**, dù cụm đó nằm nguyên văn trong cả 3 văn bản. `_FALSE_FRIEND_CONTINUATIONS` mới chặn được `khẩn cấp`; `báo cáo`, `kế hoạch`, `thông báo`, `quyết định` dùng làm động từ/danh từ thường vẫn lọt. Sửa: chỉ coi nhãn `doc_type` là filter khi nó đứng ở đầu câu hoặc sau từ dẫn ("loại", "các"), hoặc hạ thành filter mềm (boost) thay vì filter cứng. |
| **F-6** | Trung bình | **`_copy_chunks_from_twin` chép cả `embed_text` và `embedding` của văn bản nguồn.** Chunk của doc 83482 (`147/KH-UBND-MAT`) mang header `Kế hoạch 145/KH-UBND-PDF — E2E PDF — …` của doc 83481. Vector của văn bản mật vì thế mã hoá số ký hiệu và trích yếu của **một văn bản khác**. Ở đây bằng chứng là contextual header chứ không phải nội dung, nên không rò quyền (ACL vẫn chặn ở `document_id`), nhưng chất lượng truy hồi sai và `embed_text` — trường tồn tại riêng để trả lời "nó đã embed cái gì" — đang **nói dối**. Sửa: sau khi chép, tính lại `embed_text` theo `DocMeta` của văn bản đích và re-embed (hoặc chỉ dedup khi cả ba trường header trùng nhau). |
| **F-7** | Trung bình | **Nhánh PDF-scan và nhánh ảnh CHƯA được kiểm chứng đầu-cuối.** `docker-compose.dev.yml` **không có service `unlimited-ocr`** — chỉ có `db`, `odoo`, `aidt-embed`. `aidt_search.ocr_url` trỏ tới một host không tồn tại. §11.1 nói rõ "cả có lớp text lẫn scan", nên tiêu chí này chỉ đạt **một nửa**. Trong `aidt_demo` có sẵn một `dms.file` ảnh (id 13, `image/jpeg`, doc 68) chưa hề có job — cố tình không xếp hàng nó để không tạo job `failed` giả trong demo state. |
| **F-8** | Thấp | **`pdftotext -layout` chèn khoảng trắng giữa âm tiết** (`đề ngh ị`, `kết qu ả`), làm hỏng token cho kênh lexical trên chính nội dung PDF. Chỉ ảnh hưởng nhánh PDF; DOCX sạch. Có thể vá bằng bước hậu xử lý gộp lại âm tiết bị chẻ, nhưng cần cẩn thận để không phá tiếng Việt hợp lệ. |
| **F-9** | Thấp | **`zone` trên nhánh PDF kém hơn hẳn**: mất `quoc_hieu`, `ten_loai` bị gán `noi_dung`, `chu_ky`/`ho_ten_nguoi_ky` bị gộp vào `noi_dung`. Đúng như R1/§4.5 cảnh báo heuristic yếu hơn style, nhưng mức độ mất mát (4/12 vùng) lớn hơn kỳ vọng khi khối đầu trang là bảng 2 cột. |
| **F-10** | Thấp | **`.txt` không chỉ mục được.** `aidt_demo` có 7 `dms.file` `text/plain` gắn vào `aidt.document`; nếu xếp hàng, chúng sẽ `failed` với `permanent: định dạng chưa hỗ trợ`. Đúng thiết kế (§4.4) nhưng dữ liệu demo hiện có lại chủ yếu là `.txt` — người demo sẽ đụng ngay. |
| **F-11** | Rất thấp | Chunk sinh từ DOCX có `page = 0` (không phải `False`/`NULL`). Giao diện có thể hiển thị "trang 0". |

**Không có phát hiện nào là lỗi bảo mật.** F-6 là lỗi chất lượng/truy vết, không phải rò quyền.

---

## 10. Đối chiếu 7 tiêu chí hoàn thành (§11)

| # | Tiêu chí | Kết luận | Bằng chứng |
|---|---|---|---|
| 1 | `.docx` và `.pdf` (text **lẫn scan**) chỉ mục tự động, thấy tiến trình/lỗi trên UI | ⚠️ **ĐẠT MỘT PHẦN** | §3 — docx + pdf-text đạt đủ (`index_state=indexed`, `chunk_count` 13/11/11, màn hình hàng đợi + `stage_ms` + nút Nạp lại). **Nhánh scan/ảnh không kiểm được: không có service OCR** (F-7) |
| 2 | Truy vấn tiếng Việt trả văn bản đúng, có highlight và đường dẫn mục | ⚠️ **ĐẠT MỘT PHẦN** | §4 #6a/#6b: đúng văn bản, `<mark>` đầy đủ, có `zone`/`page`. Nhưng #1/#5 trả văn bản **sai** không highlight (F-2); `heading_path` chưa kiểm được với tài liệu có mục |
| 3 | Truy vấn không dấu trả cùng kết quả với có dấu | ✅ **ĐẠT** (có lưu ý) | §4 #6a vs #6b: cùng tập, cùng thứ tự. #1 vs #2: cùng tập, khác thứ tự. Lưu ý F-3: không dấu **mất filter cứng** |
| 4 | Truy vấn số hiệu đi nhánh SQL, trả chính xác | ✅ **ĐẠT** | §4 #3 và §8: `channels_used == []`, `total == 1`, đúng văn bản; khớp lại qua RPC HTTP |
| 5 | Phân quyền: không rò tiêu đề lẫn số đếm facet | ✅ **ĐẠT** | §6: `cv.tonghop1` thấy 2/3, facet `secrecy` không có mục `mat`; `cv.lyluan` thấy 0; `AccessError` khi đọc thẳng; chunk cũng bị chặn |
| 6 | Tắt embed service → vẫn tìm được, có cảnh báo | ✅ **ĐẠT** | §7: cả hai chiều, `degraded` + `warning` đúng, tự phục hồi |
| 7 | Toàn bộ test xanh trên máy không có GPU | ✅ **ĐẠT** | §1: cả hai bộ chạy xong **trước khi `aidt-embed` tồn tại**; 125 passed / 3 skipped và 0 failed, 0 error of 100 tests |

**5/7 đạt, 2/7 đạt một phần.** Hai mục đạt một phần đều do hạ tầng/thiết kế
chưa đủ (thiếu service OCR; thiếu ngưỡng liên quan), không do lỗi cài đặt.

---

## 11. Dọn dẹp

```
$ psql -U odoo -d postgres -c "\l"
   Name    | Owner | ...
 aidt_demo | odoo
 postgres  | odoo
 template0 | odoo
 template1 | odoo
(4 rows)

$ ls -la /var/lib/odoo/filestore/
drwxr-xr-x 221 odoo odoo  aidt_demo          ← chỉ một thư mục

$ ls -A /tmp    (trong container odoo)
[trống]
```

- **Không có database scratch nào.** Không tạo `aidt_test`; bộ test Odoo chạy
  thẳng trên `aidt_demo` với `-u aidt_search` (TransactionCase tự rollback).
- Đã xoá `/tmp/conv` (PDF trung gian của `soffice`) và `/tmp/verify_dedup_race.py`
  (sót lại từ một task trước) trong container odoo.
- `ir.cron` "AIDT: xử lý hàng đợi chỉ mục" đã **bật lại** (tạm tắt trong lúc
  `aidt-embed` chưa lên để job không đốt `attempt`).

Đếm cuối cùng trong `aidt_demo`:

| Bảng | Trước | Sau |
|---|---|---|
| `aidt_document` | 32 | **35** (+3 văn bản kiểm chứng) |
| `aidt_doc_chunk` | 0 | **35** (13 DOCX + 11 PDF + 11 chép từ twin) |
| `aidt_index_job` | 0 | **3** (`pending: 0, done: 3, failed: 0`) |
| `aidt_search_log` | 0 | **3** (N-08 — bằng chứng kiểm toán, giữ lại) |

### `aidt-embed`: **để CHẠY**

Lý do: (1) nó là service đã khai báo của `docker-compose.dev.yml`, không phải
thứ tạm; (2) kênh vector là tính năng đầu bảng, người demo tiếp theo cần nó
sẵn sàng; (3) chi phí thấp — **2241 MiB / 12288 MiB VRAM**, còn 9,9 GB trống
cho các container GPU khác. Muốn tắt thì
`docker compose -f docker-compose.dev.yml stop aidt-embed`; tìm kiếm sẽ tự
giảm cấp mềm đúng như §7 đã chứng minh, không hỏng gì.
