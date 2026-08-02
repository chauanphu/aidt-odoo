# AIDT — Tìm kiếm thông minh (`aidt_search`)

Chỉ mục lai (vector + lexical) và tìm kiếm ngôn ngữ tự nhiên tiếng Việt trên
nội dung **bên trong** tệp đính kèm của `aidt.document`.

Spec thiết kế: [`docs/superpowers/specs/2026-08-01-document-intelligence-search-design.md`](../../docs/superpowers/specs/2026-08-01-document-intelligence-search-design.md)
Kế hoạch thực thi: [`docs/superpowers/plans/2026-08-01-document-intelligence-search.md`](../../docs/superpowers/plans/2026-08-01-document-intelligence-search.md)
Bằng chứng đầu-cuối: [`docs/superpowers/plans/2026-08-01-e2e-verification.md`](../../docs/superpowers/plans/2026-08-01-e2e-verification.md)

---

## 1. Module này giải quyết gì

Trước đó `aidt.document` chỉ tìm được theo **trường metadata**; nội dung tệp
đính kèm là hộp đen. Module này mở hộp đen đó ra: trích xuất nội dung tệp →
chia đoạn theo cấu trúc văn bản hành chính → chỉ mục lai trong chính Postgres
của Odoo → truy vấn ngôn ngữ tự nhiên có **lọc quyền trước khi xếp hạng** và
có **trích đoạn highlight**.

Hệ thống trả **kết quả xếp hạng + trích dẫn**, cố ý **không sinh câu trả lời
RAG** (§1.3 của spec).

### Hai module, một khuôn quen thuộc

| Module | Loại | Nội dung |
|---|---|---|
| `aidt_search_engine/` | Thư viện Python thuần — **không** `__manifest__.py`, **không** `import odoo` | `extract/`, `chunker.py`, `header.py`, `intent.py`, `fusion.py`, `rerank.py`, `tokenize.py`, `text.py`, `types.py` |
| `aidt_search/` | Addon Odoo mỏng. `depends: aidt_dms, aidt_org, aidt_vanban_den` | models, views, security, data, static (OWL) |

Cùng khuôn `aidt_format_engine` / `aidt_format`: logic thuần kiểm thử được
bằng bảng vào-ra, không cần database.

---

## 2. Đường ống

```
dms.file.create()/write()                aidt.document.write()
  (directory_id.res_model =                (reference | name | doc_type đổi
   'aidt.document')                         → xếp lại hàng toàn bộ tệp)
        │                                            │
        └──────────────► aidt.index.job (pending) ◄───┘
                                 │
                    ir.cron mỗi 1 phút → _cron_process()
                    SELECT ... FOR UPDATE SKIP LOCKED, commit sau MỖI job
                                 │
                    ┌────────────┴─────────────┐
                    │  content_hash đã có ở    │ có → chép chunk từ "twin",
                    │  một job done?           │      không gọi GPU
                    └────────────┬─────────────┘
                                 │ không
              sniff magic bytes (KHÔNG tin đuôi tệp)
                                 │
      ┌────────────┬─────────────┴───────────┬──────────────┐
   PK\x03\x04     %PDF                     ảnh            khác
   docx           quyết định TỪNG TRANG:    Unlimited-OCR  → failed
   python-docx     ≥ scan_char_threshold     trực tiếp       permanent
   + zone style    ký tự → lớp text
                   dưới ngưỡng → pdftoppm
                   150dpi → Unlimited-OCR
                                 │
                       Block[] (text, zone, page, bbox, confidence)
                                 │
                  chunk_blocks() — cấu trúc trước, kích thước sau
                  · cứng: đổi zone, PHẦN/CHƯƠNG/MỤC/Điều
                  · mềm : "1.", "a)" — chỉ cắt khi đã chạm ngưỡng
                  · cuối: ranh giới câu
                  · so_ky_hieu / trich_yeu / noi_nhan / chu_ky LUÔN đứng riêng
                                 │
                  contextual header ghép vào TRƯỚC khi embed
                  (lưu nguyên vào `embed_text` để debug)
                                 │
              POST {embed_url}/embeddings, lô 32, kiểm số chiều
                                 │
                  aidt.doc.chunk — xoá chunk cũ + chèn mới
                  trong ĐÚNG MỘT transaction
                    ├ embedding   vector(1024)  HNSW
                    ├ ts          tsvector GIN  (có dấu, generated)
                    ├ ts_noaccent tsvector GIN  (không dấu, generated)
                    └ ts_seg      tsvector GIN  (tách từ — TẮT ở v1)
```

### Truy vấn

```
parse_query()  ──► reference (145/KH-UBND)  ─► nhánh SQL, KHÔNG qua vector
               ──► filters (date / doc_type / department_id / do_khan)
               ──► semantic (phần còn lại)

  tập được phép đọc = aidt.document._search(domain)   ← ir.rule của aidt_org
  nhúng làm SUBQUERY, lọc TRONG SQL, TRƯỚC khi xếp hạng

  kênh A  vector   cosine trên embedding      top-50 ─┐
  kênh B  lexical  ts + ts_rank_cd            top-50 ─┼─► RRF ─► rerank()
  kênh C  lexical  ts_noaccent + f_unaccent   top-50 ─┘        (no-op ở v1)
                                                          │
                              ts_headline() ──► gom về document_id
                                                (≤3 đoạn/văn bản)
                                                          │
                                     facet đếm trên tập ĐÃ LỌC QUYỀN
                                                          │
                                              aidt.search.log
```

**Kênh A hỏng thì không hỏng cả tính năng**: `embed()` ném lỗi → `degraded=True`,
chạy tiếp bằng hai kênh lexical, giao diện hiện dải cảnh báo *"Tìm kiếm ngữ
nghĩa tạm ngưng — đang tìm bằng từ khoá."* RRF nhận số kênh bất kỳ nên điều
này gần như miễn phí.

---

## 3. Tham số `ir.config_parameter`

Đặt trong `data/ir_config_parameter.xml` với `noupdate="1"` — sửa được từ
**Cài đặt → Kỹ thuật → Tham số hệ thống**, không phải deploy lại.

| Khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `aidt_search.ocr_url` | `http://unlimited-ocr:8000/v1` | Base URL service OCR (chỉ dùng cho ảnh và trang PDF scan) |
| `aidt_search.embed_url` | `http://aidt-embed:8001/v1` | Base URL service embedding (OpenAI-compatible) |
| `aidt_search.embed_model` | `AITeamVN/Vietnamese_Embedding` | Tên model gửi trong body |
| `aidt_search.embed_dim` | `1024` | **Chỉ để đối chiếu**, không đổi được kích thước cột |
| `aidt_search.tokenize_mode` | `syllable` | `syllable` (v1) / `word` (khe cắm `ts_seg`) |
| `aidt_search.scan_char_threshold` | `50` | Số ký tự tối thiểu/trang để coi là trang có lớp text |

> `embed_dim` **không** đổi được cột `vector(1024)` đã tạo. Nó tồn tại để
> `embed()` nổ ngay (`EmbedDimensionError`) khi model trả về số chiều khác —
> ghi bừa vector 768 chiều vào cột 1024 sẽ hỏng chỉ mục theo cách rất khó
> truy. Đổi model sang số chiều khác là một **migration có chủ đích**:
> `ALTER COLUMN` + nạp lại toàn bộ, không phải đổi một tham số.

---

## 4. Chạy test

Hai tầng, **cả hai đều chạy được trên máy không có GPU** — mọi service ngoài
đều được mock.

### Tầng 1 — thư viện thuần (pytest, không cần Odoo, không cần DB)

```bash
cd custom-addons && python -m pytest aidt_search_engine/tests -q
```

### Tầng 2 — Odoo (`TransactionCase`)

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search \
  --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Theo dõi dòng `odoo.tests.result: N failed, M error(s) of K tests`.
**Không** dùng `odoo.tests.stats` — nó đếm mục thời gian, không đếm test.

Ba dòng `ERROR` dưới đây là **tiếng ồn có chủ đích của chính bộ test**, không
phải hỏng:

- `duplicate key ... aidt_index_job_active_file_uniq` (×2) — `TestDedupRaceInFlight`
  cố tình đụng chỉ mục UNIQUE riêng phần.
- `Không ghi được nhật ký tìm kiếm ...` — `TestSearchLogDoesNotBreakSearch`
  mock cho `_log_search` ném `RuntimeError`/`KeyError`.
- `Từ chối ghi nhật ký ... dưới quyền sudo/superuser` — bất biến no-sudo được
  test khẳng định.

---

## 5. Vận hành

### Hàng đợi và DLQ

Menu **Văn bản → Hàng đợi chỉ mục** (chỉ nhóm `aidt_org.group_aidt_admin`).
Trạng thái `failed` **chính là dead letter queue** — không có hạ tầng riêng.

| Cột | Đọc thế nào |
|---|---|
| `state` | `pending` → `extracting` → `chunking` → `embedding` → `done` / `failed` |
| `error_kind` | `transient` (service chết, timeout, OOM) / `permanent` (tệp hỏng, MIME không hỗ trợ) |
| `attempt` | Trần `MAX_ATTEMPT = 3`, **chỉ áp cho `transient`** |
| `next_retry_at` | Lùi lịch cấp số nhân `RETRY_BACKOFF_MINUTES = (1, 4, 16)` phút |
| `stage_ms` | `{"extract": 5400, "chunk": 12, "embed": 830}` — trả lời "chặng nào chậm" |

### Xử lý một job `failed`

1. Mở job, đọc `error` và `error_kind`.
2. **`permanent`** — tệp không bao giờ xử lý được bằng đường hiện tại. Bấm
   **Nạp lại** chỉ có ích sau khi đã sửa nguyên nhân gốc:

   | Thông điệp | Nguyên nhân | Xử lý |
   |---|---|---|
   | `định dạng chưa hỗ trợ: <tên tệp>` | MIME ngoài docx/pdf/ảnh (vd. `.txt`, `.doc` cũ, `.xlsx`) | Chuyển đổi sang `.docx`/`.pdf` rồi đính kèm lại. **Ngoài phạm vi v1** |
   | `DOCX không đọc được: ...` | Tệp hỏng, hoặc `.doc` nhị phân đổi đuôi | Mở bằng Word/LibreOffice, lưu lại đúng `.docx` |
   | `PDF không đọc được: ...` | PDF hỏng hoặc có mật khẩu | Gỡ mật khẩu / xuất lại PDF |
   | `OCR trả rỗng — kiểm tra prompt ...` | **Sai công thức gọi OCR** (§4.5 spec), không phải trang giấy trắng | Kiểm `aidt_search.ocr_url` và service OCR, rồi **Nạp lại** |
   | `không trích xuất được nội dung nào` / `nội dung trích được rỗng sau khi chia đoạn` | Tệp rỗng thật, hoặc chỉ có ảnh mà OCR không nhận ra chữ | Kiểm tệp gốc |

3. **`transient`** — job đã tự thử lại 3 lần. Đọc `error`, thường là:
   - `gọi embedding thất bại: ...` → container `aidt-embed` chết hoặc sai
     `aidt_search.embed_url`. `docker compose -f docker-compose.dev.yml ps aidt-embed`.
   - `model trả vector N chiều nhưng cột là vector(1024)` → **đã đổi model
     embedding**. Đây là migration, không phải sự cố: hoặc trả lại model cũ,
     hoặc `ALTER COLUMN` + nạp lại toàn bộ chunk.
   - `embedding trả về tập index ... không khớp N văn bản gửi đi` /
     `... trả về K vector cho N văn bản` → service embedding trả về phản hồi
     không hợp lệ. Không được "tự sửa" — kiểm service.

   Sau khi hạ tầng lành, bấm **Nạp lại** (đặt lại `attempt = 0`).

### Trên form văn bản

Badge **Trạng thái chỉ mục** (`none` / `pending` / `indexed` / `failed`),
**Số đoạn** (`chunk_count`), và nút **Chỉ mục lại** (`action_reindex`) —
xếp lại hàng toàn bộ tệp của văn bản.

### Nhật ký truy cập

`aidt.search.log` ghi mỗi lượt tìm kiếm: ai tìm gì, thấy văn bản nào, mở cái
nào, hết bao lâu, có chạy giảm cấp không. Đây là **yêu cầu tuân thủ N-08**,
không phải tính năng phụ. Chuyên viên chỉ đọc log của chính mình; nhóm quản
trị đọc toàn bộ để kiểm toán.

Bảng này **chưa có chính sách lưu trữ/dọn dẹp tự động** — nợ vận hành đã ghi
nhận, cần xử lý trước khi bảng lớn tới mức ảnh hưởng sao lưu.

---

## 6. Giới hạn đã biết ở v1

- **`ts_seg` (tách từ tiếng Việt) tắt** — cột và chỉ mục đã sẵn, kênh D chưa bật.
- **Reranker là no-op** — `rerank.py` trả nguyên thứ tự RRF. Bật khi bộ eval
  của dự án con D cho thấy nDCG@10 dưới ngưỡng; chỉ thay thân hàm.
- **Chỉ nhảy tới trang**, chưa overlay `bbox` trên trình xem PDF (dữ liệu đã
  lưu sẵn nên không phải làm lại).
- **Không chỉ mục `.txt`, `.doc` nhị phân cũ, email, `.xlsx`** — rơi vào
  `permanent`.
- **Không sinh câu trả lời RAG** — cố ý.
- `aidt_dms.action_ocr_extract` vẫn là **OCR giả lập hardcode** (nợ kỹ thuật
  §10 của spec), đứng cạnh một đường ống OCR thật.
