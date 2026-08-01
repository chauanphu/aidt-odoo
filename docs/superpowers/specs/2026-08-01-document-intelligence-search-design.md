# Design Spec: Document Intelligence Search (Tìm kiếm thông minh trên kho văn bản)

Ngày: 2026-08-01
Trạng thái: đã duyệt, sẵn sàng lập kế hoạch thực thi
Nguồn yêu cầu: `docs/embedding-documents.md`, `docs/mvp.md` (V-10 → V-14, S-11, N-12, N-16)

---

## 1. Mục tiêu và phạm vi

### 1.1. Bài toán

`aidt.document` hiện lưu metadata và tệp đính kèm (qua OCA DMS), nhưng **nội dung bên trong tệp là hộp đen**. Không tìm được theo nội dung, chỉ tìm được theo trường. `aidt_dms.action_ocr_extract` là OCR giả lập hardcode, không đọc tệp thật.

Spec này xây **lát cắt dọc**: tệp đính kèm vào `aidt.document` → trích xuất nội dung → chunk → chỉ mục lai (lexical + vector) → tìm kiếm ngôn ngữ tự nhiên có lọc quyền và có trích dẫn.

### 1.2. Trong phạm vi

| Tầng (theo `docs/embedding-documents.md`) | Mức độ |
|---|---|
| T0 — Nạp & vòng đời | Rút gọn: hash chống trùng, hàng đợi, DLQ |
| T1 — Phân loại & định tuyến | Đủ: sniff MIME, rẽ nhánh docx / pdf-text / pdf-scan / ảnh |
| T2 — Trích xuất nội dung | Đủ: text + zone + trang + bbox + độ tin cậy |
| T4 — Chunking | Đủ: cấu trúc trước kích thước sau, contextual header |
| T5 — Chỉ mục | Đủ: vector + 2 kênh lexical + metadata quan hệ |
| T6 — Truy vấn | Đủ: định tuyến ý định, truy hồi song song, RRF, lọc ACL |
| T7 — Phục vụ | Rút gọn: kết quả + trích dẫn highlight + facet + nhật ký |

### 1.3. Ngoài phạm vi (nêu rõ để không trượt)

- **T3 — Làm giàu** toàn bộ: trích thực thể, gợi ý loại/lĩnh vực, liên kết văn bản, gắn bản ghi ERP. → dự án con C.
- **Bộ eval golden set**, đo Recall@10 / MRR (O-02), cảnh báo truy cập bất thường (N-08 phần cảnh báo). → dự án con D.
- **Reranker**: chỉ để khe cắm, cài đặt v1 là no-op.
- **Tách từ tiếng Việt (`ts_seg`)**: chỉ để khe cắm, tắt mặc định.
- **Overlay bbox** trên trình xem PDF (v1 chỉ nhảy tới trang).
- Định dạng `.doc` nhị phân cũ, email, xlsx.
- Sinh câu trả lời RAG — đã chốt: hệ thống trả **kết quả xếp hạng + trích dẫn**, không sinh câu trả lời.

### 1.4. Ràng buộc đã chốt

| Quyết định | Giá trị |
|---|---|
| Quy mô mục tiêu 6–12 tháng | Vài trăm văn bản (bộ test O-01), 5–10 người dùng thử |
| Đầu ra truy vấn | Kết quả xếp hạng + trích dẫn. Không RAG |
| Nguồn được chỉ mục | **Chỉ** tệp thuộc `dms.directory` gắn `res_model='aidt.document'` |
| Kiến trúc | Chỉ mục trong Postgres của Odoo (pgvector); suy luận ở container ngoài |
| Dữ liệu ra ngoài | Không. Mọi model self-host (N-15, N-18) |

---

## 2. Kiến trúc

```
┌──────────────────────── Odoo (PG16 + pgvector) ───────────────────────┐
│                                                                        │
│  dms.file ──create/write──► aidt.index.job ──ir.cron (1 phút)──┐      │
│                                                                 │      │
│  aidt.doc.chunk ◄───────────────────────────────────────────────┘      │
│    ├ embedding vector(1024)   HNSW                                     │
│    ├ ts          tsvector     GIN   (có dấu)                           │
│    ├ ts_noaccent tsvector     GIN   (không dấu)                        │
│    └ ts_seg      tsvector     GIN   (tách từ — tắt ở v1)               │
│                                                                        │
│  aidt.document ──ir.rule (đơn vị + độ mật)──► ACL cho truy vấn         │
│  aidt.search.log                                                       │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │ HTTP (OpenAI-compatible)
                    ┌────────────┴────────────┐
                    ▼                         ▼
        unlimited-ocr :8000        aidt-embed :8001
        vllm/vllm-openai           vLLM --task embed
        baidu/Unlimited-OCR        AITeamVN/Vietnamese_Embedding (1024d)
```

### 2.1. Hai module mới

Theo đúng khuôn `aidt_format_engine` (thư viện thuần) / `aidt_format` (addon mỏng) đã có trong repo:

| Module | Loại | Nội dung |
|---|---|---|
| `custom-addons/aidt_search_engine/` | Thư viện Python thuần. Có `__init__.py`, **không** có `__manifest__.py`. Không import `odoo` | `extract/`, `chunker.py`, `header.py`, `intent.py`, `fusion.py`, `tokenize.py`, `types.py`, `tests/` |
| `custom-addons/aidt_search/` | Addon Odoo. `depends: ['aidt_dms', 'aidt_org']` | models, wizards, views, static (OWL), security, data (cron) |

Lý do tách: chunker, phân tích ý định và RRF là logic thuần, kiểm thử được bằng bảng vào-ra không cần database. `aidt_format_engine` đã chứng minh khuôn này hiệu quả (7 file test, chạy nhanh).

**Không sửa `extra-addons/`.** Không sửa `aidt_format_engine` — nếu cần thích ứng thì viết adapter trong `aidt_search_engine`.

### 2.2. Hai thay đổi hạ tầng

1. `docker-compose.dev.yml`: `postgres:16-alpine` → `pgvector/pgvector:pg16`. Volume `db-data-dev` giữ nguyên; `aidt_demo` không mất dữ liệu.
2. Thêm service `aidt-embed`; khởi động lại `unlimited-ocr` với `--gpu-memory-utilization 0.55` để nhường VRAM (GPU 16GB, OCR đang chiếm 13.6GB).

URL service lưu ở `ir.config_parameter`, **không hardcode**:

| Khoá | Mặc định |
|---|---|
| `aidt_search.ocr_url` | `http://unlimited-ocr:8000/v1` |
| `aidt_search.embed_url` | `http://aidt-embed:8001/v1` |
| `aidt_search.embed_model` | `AITeamVN/Vietnamese_Embedding` |
| `aidt_search.embed_dim` | `1024` |
| `aidt_search.tokenize_mode` | `syllable` |
| `aidt_search.scan_char_threshold` | `50` |

`embed_dim` **không đổi được kích thước cột** `vector(1024)` đã tạo — nó tồn tại để code **đối chiếu** vector service trả về với cột thực tế và nổ ngay khi lệch (§6.2 bẫy 2). Đổi model sang số chiều khác là một migration có chủ đích: `ALTER COLUMN` + nạp lại toàn bộ, không phải đổi một tham số.

---

## 3. Mô hình dữ liệu

### 3.1. `aidt.doc.chunk`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `document_id` | m2o `aidt.document`, `ondelete='cascade'`, index | Nguồn suy quyền |
| `file_id` | m2o `dms.file`, `ondelete='cascade'`, index | |
| `seq` | Integer | Thứ tự trong tệp |
| `zone` | Char | Một trong 12 vùng của `aidt_format_engine.zones.ZONES` |
| `zone_confidence` | Selection `style` / `heuristic` | |
| `heading_path` | Char | `Phần II › Mục 3` |
| `text` | Text | Nội dung sạch, **không** kèm header |
| `embed_text` | Text | Chuỗi thực sự đã đem đi embed. Giữ để tái lập & debug |
| `page` | Integer | Số trang (PDF/ảnh) |
| `bbox` | Char | JSON `[x0,y0,x1,y1]` từ OCR |
| `ocr_confidence` | Float | Chỉ nhánh OCR |
| `token_count` | Integer | Ước lượng |

Ba cột không phải `fields.*`, tạo bằng SQL thuần trong `_auto_init()`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- unaccent() không IMMUTABLE nên không dùng thẳng trong generated column.
-- Bọc lại là thủ thuật chuẩn của Postgres:
CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
  $$ SELECT public.unaccent('public.unaccent', $1) $$;

ALTER TABLE aidt_doc_chunk
  ADD COLUMN IF NOT EXISTS embedding   vector(1024),
  ADD COLUMN IF NOT EXISTS ts          tsvector GENERATED ALWAYS AS
                                       (to_tsvector('simple', text)) STORED,
  ADD COLUMN IF NOT EXISTS ts_noaccent tsvector GENERATED ALWAYS AS
                                       (to_tsvector('simple', f_unaccent(text))) STORED,
  ADD COLUMN IF NOT EXISTS ts_seg      tsvector;   -- Python điền, tắt ở v1

CREATE INDEX IF NOT EXISTS aidt_doc_chunk_embedding_idx
  ON aidt_doc_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_idx          ON aidt_doc_chunk USING gin (ts);
CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_noaccent_idx ON aidt_doc_chunk USING gin (ts_noaccent);
CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_seg_idx      ON aidt_doc_chunk USING gin (ts_seg);
```

`ts` và `ts_noaccent` là **generated column** — Postgres tự tính, không có đường nào cho code quên cập nhật. `ts_seg` phải là cột thường vì tách từ là thao tác Python, không biểu diễn được bằng hàm SQL IMMUTABLE.

Config `simple` vì Postgres không có stemmer tiếng Việt — và ta cũng không muốn: tiếng Việt không biến hình.

### 3.2. `aidt.index.job`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `document_id`, `file_id` | m2o | |
| `content_hash` | Char(64), index | sha256 nội dung tệp |
| `state` | Selection | `pending` / `extracting` / `chunking` / `embedding` / `done` / `failed` |
| `error_kind` | Selection | `transient` / `permanent` |
| `attempt` | Integer | Trần 3, **chỉ áp cho `transient`** |
| `next_retry_at` | Datetime | Lùi lịch cấp số nhân: 1, 4, 16 phút |
| `error` | Text | Thông điệp cho người vận hành |
| `stage_ms` | Json | `{"extract": 5400, "chunk": 12, "embed": 830}` |

Trạng thái `failed` **chính là dead letter queue** — có màn hình lọc và nút nạp lại thủ công, không cần hạ tầng riêng.

### 3.3. Mở rộng `aidt.document`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `index_state` | Selection compute, store | `none` / `pending` / `indexed` / `failed`. Suy từ job của các tệp |
| `chunk_count` | Integer compute | |

### 3.4. `aidt.search.log`

`user_id`, `query_raw`, `query_semantic`, `filters_json`, `channels_used`, `result_document_ids`, `clicked_document_id`, `duration_ms`, `create_date`.

Một bảng, hai nghĩa vụ: **nhật ký truy cập N-08** (P0, tuân thủ bắt buộc) và dữ liệu nuôi bộ eval của dự án con D.

---

## 4. Đường ống nạp (T0 → T5)

### 4.1. Kích hoạt

- `dms.file.create()` / `write()`: lọc tệp có `directory_id.res_model == 'aidt.document'` → tạo `aidt.index.job` trạng thái `pending`.
- `aidt.document.write()`: đổi `reference`, `name` hoặc `doc_type` → **xếp lại hàng chỉ mục cho toàn bộ tệp của văn bản**. Ba trường này nằm trong contextual header nên đã được embed vào vector; không nạp lại thì header lệch thực tế.

### 4.2. Worker

`ir.cron` mỗi phút → `aidt.index.job._cron_process()`:

- Nhận việc bằng `SELECT ... FOR UPDATE SKIP LOCKED` — an toàn khi sau này chạy nhiều worker.
- **Commit sau mỗi job**, không phải sau cả lô. Một tệp hỏng không được kéo đổ những tệp tốt.
- Ngân sách đồng hồ ~5 phút mỗi lượt; hết giờ dừng nhận việc mới. Văn bản 20 trang scan mất ~54s ở tốc độ 2.7s/trang đã đo được.
- Chỉ nhận job có `next_retry_at` đã tới hạn.

### 4.3. T0 — Chống trùng

Băm sha256 nội dung tệp trước tiên. Nếu hash đã tồn tại ở một job `done`, **chép chunk sang, không gọi OCR**. Trong ERP cùng một công văn bị đính kèm lại liên tục.

### 4.4. T1 — Cây định tuyến

Sniff MIME bằng magic bytes, **không tin đuôi tệp**:

```
docx  → aidt_format_engine.parse_docx()       (có zone sẵn, chính xác nhất)
pdf   → quyết định TỪNG TRANG:
          text ≥ scan_char_threshold ký tự → đọc lớp text + toạ độ
          dưới ngưỡng                      → pdftoppm 150dpi → Unlimited-OCR
ảnh   → Unlimited-OCR trực tiếp
khác  → failed, error_kind='permanent'
```

Quyết định **theo từng trang** chứ không theo cả tệp: văn bản thật rất hay lai — vài trang soạn máy, vài trang scan chèn vào.

### 4.5. T2 — Cấu trúc trung gian chung

Cả hai nhánh đổ về một kiểu trong `aidt_search_engine/types.py`:

```python
@dataclass
class Block:
    text: str
    zone: str | None = None            # 12 vùng của aidt_format_engine
    zone_confidence: str | None = None # 'style' | 'heuristic'
    page: int | None = None
    bbox: tuple | None = None
    confidence: float | None = None    # chỉ nhánh OCR
```

**Một bộ zone detector cho cả hai nguồn.** Heuristic của `aidt_format_engine.zones` là regex + vị trí (`Số\s*[:：]?\s*\d+[-/][A-ZĐ]+`, `Nơi nhận\s*:`, kiểm tra in hoa) — chạy trên text thuần được. Với nhánh OCR: dựng `Para` từ `Block`, suy `align` từ tâm bbox so với chiều ngang trang, gọi `detect_zones`.

Nhánh DOCX giữ lợi thế sẵn có: văn bản soạn từ template hệ thống có style đặt tên → `zone_confidence='style'`, chính xác 100%. Nhánh OCR luôn là `'heuristic'`.

> **Rủi ro R1** — xem §7.

Gọi Unlimited-OCR **bắt buộc** theo công thức đã kiểm chứng, sai một trong ba thì trả rỗng:
- Prompt bắt đầu bằng literal `<image>` (`<image>document parsing.`)
- `"skip_special_tokens": false`
- `"vllm_xargs": {"ngram_size": 35, "window_size": N}` — `N=128` cho ảnh rời, `N=1024` cho trang thuộc PDF nhiều trang

### 4.6. T4 — Chunking

**Cấu trúc trước, kích thước sau.** Ba bậc ranh giới:

| Bậc | Gồm | Hành vi |
|---|---|---|
| **Cứng** | `zone` thay đổi; `PHẦN\|Phần [IVX]+`, `CHƯƠNG\|Chương [IVX]+`, `MỤC\|Mục \d+`, `Điều \d+` | Luôn cắt. Bốn mẫu sau còn nối vào `heading_path` |
| **Mềm** | `^\d+\.`, `^[a-zđ]\)` | Chỉ cắt khi chunk đã chạm ngưỡng |
| **Cuối** | Ranh giới câu | Dùng khi một khối đơn lẻ dài quá ngưỡng |

`\d+.` và `[a-zđ])` **không** phải ranh giới cứng: coi chúng là cứng thì một danh sách 20 gạch đầu dòng ngắn thành 20 chunk tí hon, làm loãng chỉ mục và mất ngữ cảnh của chính cái danh sách đó.

Trong một khối: gộp đoạn tới ~400 token, chồng lấn một đoạn.

Bốn vùng **luôn đứng riêng một chunk**, không gộp vào nội dung: `so_ky_hieu`, `trich_yeu`, `noi_nhan`, `chu_ky`. Đây là thứ người ta tra cứu trực tiếp ("văn bản nào gửi Sở Tài chính?", "ai ký?"); nhấn chìm vào một chunk 400 token là ném đi tín hiệu mạnh nhất.

> **Giả định A2** — xem §7.

**Contextual header** ghép vào đầu mỗi chunk *trước khi embed*:

```
{tên loại} {số ký hiệu} — {trích yếu}
{heading_path}
---
{text}
```

Ví dụ:
```
Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026
Phần II › Mục 3
---
Các sở, ban, ngành có trách nhiệm bố trí kinh phí...
```

Lưu nguyên chuỗi này vào `embed_text`. Khi kết quả sai, câu hỏi đầu tiên luôn là "nó đã embed cái gì".

Đếm token bằng ước lượng (`len(text)/3`), không gọi tokenizer — ngưỡng 400 cách xa giới hạn 8192 của model nên sai số không gây tràn.

### 4.7. T5 — Ghi chỉ mục

- Embedding: gọi `/v1/embeddings`, lô 32.
- Nạp lại: **xoá hết chunk cũ của tệp rồi chèn mới, trong một transaction**.
- Xoá `dms.file` → chunk cascade theo. Ở quy mô này không cần tombstone.

---

## 5. Truy vấn (T6) và phục vụ (T7)

### 5.1. Định tuyến ý định

**Nhánh 1 — tra cứu số hiệu → SQL thẳng.** Regex `\d+\s*/\s*[A-ZĐ]{2,}(-[A-ZĐ]+)*` bắt `145/KH-UBND`, `185/CV-STTTT`. Khớp chính xác trên `reference` và `so_ky_hieu_gui`, trả ngay, bỏ qua tầng ngữ nghĩa. Đây là truy vấn phổ biến nhất của văn thư và là thứ vector làm tệ nhất.

**Nhánh 2 — bóc filter cứng ra khỏi câu:**

| Trong câu | Thành |
|---|---|
| "năm 2025", "quý II/2026", "tháng 3" | filter `date` |
| tên khớp `hr.department.name` | filter `department_id` |
| "kế hoạch", "quyết định", "công văn"… | filter `doc_type` |
| "khẩn", "hoả tốc" | filter `do_khan` |

*"Các văn bản về hỗ trợ hộ nghèo năm 2025"* → filter `date ∈ 2025` **+** truy vấn ngữ nghĩa `"hỗ trợ hộ nghèo"`. Ném cả câu vào embedding thì "năm 2025" thành nhiễu ngữ nghĩa.

**Nhánh 3 — phần còn lại → truy hồi song song, mỗi kênh top-50:**

| Kênh | Cách | Bắt được gì |
|---|---|---|
| A — vector | cosine trên `embedding` | Diễn đạt khác chữ |
| B — lexical có dấu | `websearch_to_tsquery` + `ts_rank_cd` trên `ts` | Từ hiếm, tên riêng |
| C — lexical không dấu | như trên, trên `ts_noaccent`, truy vấn qua `f_unaccent` | Người gõ "ho ngheo" |
| D — tách từ | `ts_seg` | **Tắt ở v1** |

`ts_rank_cd` là cover density — đã tính khoảng cách giữa các từ khớp, nên "hộ nghèo" đứng cạnh nhau ăn điểm cao hơn "hộ" và "nghèo" nằm rải rác. Đây là cách vá rẻ cho vấn đề âm tiết viết rời của tiếng Việt.

### 5.2. Hợp nhất

RRF: `score(d) = Σᵢ 1/(60 + rankᵢ(d))`.

Không tham số phải tinh chỉnh, không cần chuẩn hoá thang điểm giữa cosine và `ts_rank_cd`. Cài đặt **nhận số kênh bất kỳ** — thêm/bớt kênh không sửa code hợp nhất. Đây cũng là cái làm cho §5.6 và §6.3 gần như miễn phí.

### 5.3. Khe cắm reranker (chưa bật ở v1)

Sau RRF, trước khi gom về văn bản, danh sách đi qua:

```python
# aidt_search_engine/rerank.py
def rerank(query: str, candidates: list[Candidate]) -> list[Candidate]:
    """v1: trả nguyên danh sách, giữ thứ tự RRF."""
    return candidates
```

Lý do chưa bật: cross-encoder chỉ tỏa sáng khi tập ứng viên lớn và nhiễu. Với vài trăm văn bản, RRF + contextual header đã gần chạm trần, trong khi model tốn thêm ~1.2GB VRAM (đang chỉ còn ~2.2GB trống) và ~300ms mỗi truy vấn.

**Điều kiện bật**: bộ eval của dự án con D cho thấy nDCG@10 của RRF thuần thấp hơn ngưỡng. Khi đó chỉ thay thân hàm, không đổi chỗ gọi.

### 5.4. Lọc quyền — thứ tự quyết định đúng/sai

```python
# ĐÚNG: lấy tập được phép TRƯỚC, truy hồi TRONG tập đó
allowed = self.env['aidt.document']._search(metadata_domain)   # ir.rule tự áp
# nhúng làm subquery, không kéo id về Python:
#   WHERE chunk.document_id IN (<subselect của allowed>)
```

Lọc **sau** khi xếp hạng là lỗ hổng: top-50 có thể toàn văn bản mật user không được xem, lọc xong còn rỗng — trong khi kết quả hợp lệ nằm ở hạng 51. Người dùng thấy "không có kết quả" cho thứ họ có quyền đọc.

Vì `_search()` đã áp `ir.rule` của `aidt_org` (`department_id child_of` + `secrecy_level <= user.clearance_level`), **không viết một dòng luật quyền nào**. Không có bản sao ACL để lệch. Đây là toàn bộ lý do chọn kiến trúc này.

Ngân sách so với O-04 (<3s): embed truy vấn ~40ms + 3 truy vấn SQL ~50ms + RRF không đáng kể.

### 5.5. Kết quả

Gom chunk theo `document_id`; mỗi văn bản lấy 1–3 đoạn khớp tốt nhất. **Không trả danh sách chunk rời** — người dùng nghĩ theo văn bản.

Trích đoạn highlight bằng `ts_headline('simple', text, query)`.

### 5.6. Giảm cấp mềm

Embed service chết lúc truy vấn → **vẫn tìm kiếm được**: chạy tiếp với hai kênh lexical, hiện dải cảnh báo *"tìm kiếm ngữ nghĩa tạm ngưng"*. Một container chết không được làm chết cả tính năng. Vì RRF nhận số kênh bất kỳ nên chỉ cần không viết code giả định luôn đủ ba kênh.

### 5.7. Giao diện

Search view chuẩn của Odoo không làm được (không xếp hạng theo độ liên quan, không trích đoạn) → **client action OWL**, menu "Tìm kiếm thông minh" trong app Văn bản.

```
┌──────────────────────────────────────────────────────────┐
│ [ văn bản nào về hỗ trợ hộ nghèo năm 2025 ]      [Tìm]   │
│ Đã hiểu:  (năm 2025 ×)                                   │
├───────────┬──────────────────────────────────────────────┤
│ Loại VB   │ ▸ Kế hoạch 145/KH-UBND            [Mật]      │
│  Kế hoạch3│   Phần II › Mục 3 · trang 2                  │
│  Công văn7│   "...bố trí kinh phí **hỗ trợ hộ nghèo**    │
│ Đơn vị    │    trên địa bàn tỉnh..."          [Mở tệp]   │
│ Thời gian │ ─────────────────────────────────────────    │
│ Độ mật    │ ▸ Công văn 185/CV-STTTT                      │
└───────────┴──────────────────────────────────────────────┘
```

Chip **"Đã hiểu"** hiển thị đúng những filter hệ thống tự bóc ra và **xoá được**. Người dùng luôn thấy hệ thống đã diễn giải câu hỏi thế nào và sửa được khi nó hiểu sai — cùng nguyên tắc "AI đề xuất, người dùng quyết" mà `mvp.md` đặt cho toàn hệ thống.

Facet đếm bằng `read_group` trên tập **đã lọc quyền**: con số trên facet cũng không được lộ sự tồn tại của văn bản mật.

Với PDF scan có `bbox` nhưng **v1 chỉ nhảy tới trang + highlight trong trích đoạn**; overlay để v2 (dữ liệu đã lưu sẵn nên không phải làm lại).

---

## 6. Xử lý lỗi

### 6.1. Hai loại lỗi, không được gộp

| | `transient` | `permanent` |
|---|---|---|
| Ví dụ | Service không phản hồi, timeout, 5xx, GPU OOM | Tệp hỏng, PDF có mật khẩu, `.doc` cũ, tệp rỗng, MIME không hỗ trợ |
| Xử lý | Giữ `pending`, lùi lịch 1/4/16 phút, `attempt` trần 3 | `failed` **ngay**, không retry |

Gộp hai loại là cách chắc chắn nhất để vừa bỏ sót tệp cứu được, vừa đốt GPU cho tệp không cứu được.

### 6.2. Ba cái bẫy im lặng phải làm cho nó kêu

1. **OCR trả rỗng** — Unlimited-OCR trả chuỗi rỗng khi sai công thức gọi ở §4.5. Đây là **lỗi cấu hình**, không phải trang giấy trắng. Ghi chunk rỗng thì tài liệu "đã chỉ mục" mà tìm mãi không ra. Kiểm tra: trang trả 0 ký tự trong khi ảnh không trắng → `failed` kèm thông điệp rõ.
2. **Embedding sai số chiều** — đổi model mà quên `embed_dim` phải nổ ngay lúc chèn, tuyệt đối không ghi bừa.
3. **Truy vấn trên kho rỗng** — phân biệt *"kho chỉ mục đang xử lý N tệp"* với *"không có kết quả"*. Trả nhầm là đánh lừa người dùng.

### 6.3. Vận hành

- Màn hình `aidt.index.job` lọc theo trạng thái — hàng đợi và DLQ nhìn thấy được, nút **Nạp lại** cho job `failed`.
- Form văn bản: badge `index_state` + `chunk_count` + nút **Chỉ mục lại**.
- `stage_ms` trả lời "chặng nào chậm" mà không cần hạ tầng quan trắc riêng.
- Nút kiểm tra sức khoẻ ở Settings: OCR service, embed service, extension `vector` / `unaccent`.

---

## 7. Rủi ro và giả định

| Mã | Nội dung | Xử lý |
|---|---|---|
| **R1** | `aidt_format_engine.detect_zones` được viết cho `Para` có `fmt` đầy đủ; đường heuristic có thể vấp `None` khi dùng cho nhánh OCR | **Kiểm chứng ở bước thực thi đầu tiên** — nó ảnh hưởng thiết kế chunking. Phương án lùi: adapter mỏng trong `aidt_search_engine`, không sửa `aidt_format_engine` |
| **R2** | Chưa xác minh `unaccent.rules` mặc định có ánh xạ `đ → d` | Kiểm bằng một câu SQL. Không có thì dùng file rules riêng (cấu hình Postgres, không phải code) |
| **R3** | Hạ `--gpu-memory-utilization` xuống 0.55 làm KV cache nhỏ lại | Đo lại tốc độ 2.7s/trang sau khi hạ. Không đạt thì cân lại tỷ lệ hoặc chạy embedding trên CPU |
| **A1** | Ngưỡng 50 ký tự/trang để phân biệt trang scan | **Giả định cần xác nhận** với văn bản thật của đơn vị. Đã tham số hoá ở `aidt_search.scan_char_threshold` |
| **A2** | Tách riêng `so_ky_hieu` / `trich_yeu` / `noi_nhan` / `chu_ky` thành chunk độc lập khớp với cách văn thư tra cứu | **Giả định cần xác nhận**. Sai thì chỉ cần đổi danh sách vùng trong chunker rồi nạp lại |

---

## 8. Kiểm thử

### 8.1. Tầng 1 — thư viện thuần (`aidt_search_engine/tests/`)

pytest, không cần Odoo, không cần DB. Phần lớn test nằm ở đây.

- **Chunker**: bảng vào-ra. Ca biên là chỗ đáng tiền — `Điều` dài 2000 token (phải cắt), `Điều` một dòng (phải gộp), zone đổi giữa chừng, tài liệu chỉ một đoạn, tài liệu rỗng.
- **Contextual header**: đúng định dạng, đúng thứ tự, xử lý được trường thiếu.
- **Phân tích ý định**: bảng truy vấn → (filter bóc ra, chuỗi còn lại). Ca biên: `145/KH-UBND`, "quý II năm 2025", "Sở Tài chính", và câu **không** có filter nào (không được bóc nhầm).
- **RRF**: kiểm **tính chất** chứ không kiểm số — thêm một kênh rác không được đẩy tụt item đứng đầu ở cả ba kênh kia; kênh rỗng không làm đổ hàm.
- **`tokenize()`**: cả hai mode + đường lùi khi không cài `underthesea` / `pyvi`.

### 8.2. Tầng 2 — Odoo (`aidt_search/tests/`, `TransactionCase`)

**Viết test phân quyền trước tiên, trước cả khi có giao diện.**

- **Phân quyền (O-03, V-13)**: hai phòng ban, ba user khác `clearance_level`, một văn bản `tuyet_mat` ở phòng khác → tìm kiếm **không trả về, kể cả tiêu đề**, và **con số trên facet cũng không đếm nó**. Đây là thứ duy nhất trong spec mà sai thì hỏng chuyện thật.
- **Vòng đời job**: tạo `dms.file` → `pending`; chạy cron với service mock → `done` + có chunk; xoá file → chunk biến mất.
- **Chống trùng**: upload cùng tệp hai lần → lần hai **không gọi OCR** (đếm số lần gọi mock).
- **Nạp lại**: đổi `reference` → job được xếp hàng.
- **Giảm cấp mềm**: mock embed lỗi → vẫn có kết quả lexical.
- **Phân loại lỗi**: mock timeout → `transient` + `attempt` tăng; mock file hỏng → `failed` ngay, `attempt` không tăng.

**Service ngoài luôn được mock.** Không test nào chạm GPU — bộ test phải chạy được trên máy không có card.

### 8.3. Tầng 3 — kịch bản thủ công trên `aidt_demo`

Bằng chứng đầu-cuối, không phải test tự động:
1. Nạp `docs/demo/01-dat-chuan.pdf` (đã OCR sạch, có kết quả để đối chiếu) → soi chunk sinh ra, kiểm zone gán đúng chưa.
2. Truy vấn có dấu → "hỗ trợ hộ nghèo".
3. Truy vấn không dấu → "ho ngheo".
4. Truy vấn số hiệu → "145/KH-UBND" (phải đi nhánh SQL).
5. Truy vấn có mốc thời gian → kiểm chip "Đã hiểu" bóc đúng.

### 8.4. Quy ước database

Theo `CLAUDE.md`: chỉ tồn tại **một** database `aidt_demo`. Test tự động dùng DB tạm thì **drop cả database lẫn thư mục filestore dưới `/var/lib/odoo/filestore/`** khi chạy xong. Trước khi kết thúc phiên, xác minh chỉ còn `aidt_demo`.

---

## 9. Thứ tự thực thi đề xuất

| Bước | Nội dung | Vì sao ở vị trí này |
|---|---|---|
| 0 | Kiểm chứng **R1** và **R3** | Có thể đổi thiết kế — phải biết trước khi viết nhiều |
| 1 | Hạ tầng: image pgvector, container `aidt-embed`, chỉnh VRAM OCR | Mọi thứ sau đều dựa vào |
| 2 | `aidt_search_engine`: chunker, header, intent, fusion, tokenize + toàn bộ test | Không cần Odoo, không cần DB → làm được song song, phản hồi nhanh |
| 3 | `aidt_search`: schema SQL, `aidt.index.job`, cron, extractor | |
| 4 | Truy vấn + ACL, **test phân quyền trước UI** | Sai ở đây là lỗi bảo mật, không phải lỗi tính năng |
| 5 | Client action OWL, facet, chip "Đã hiểu", `aidt.search.log` | |

---

## 10. Nợ kỹ thuật ghi nhận

`aidt_dms.action_ocr_extract` hiện là **OCR giả lập hardcode** — điền cứng `185/CV-STTTT`, `Sở Thông tin và Truyền thông` cho mọi văn bản. Thay nó bằng trích metadata thật thuộc T3 (dự án con C), **ngoài phạm vi spec này**. Nhưng để nguyên thì hệ thống sẽ có một nút OCR nói dối đứng cạnh một đường ống OCR thật. Ghi ở đây để không ai quên; xử lý ở dự án con C hoặc bằng một thay đổi riêng.

---

## 11. Tiêu chí hoàn thành

1. Tệp `.docx` và `.pdf` (cả có lớp text lẫn scan) đính kèm vào `aidt.document` được chỉ mục tự động, thấy được tiến trình và lỗi trên UI.
2. Truy vấn ngôn ngữ tự nhiên tiếng Việt trả về văn bản đúng, có trích đoạn highlight và đường dẫn mục (V-10, V-14).
3. Truy vấn không dấu trả cùng kết quả với truy vấn có dấu.
4. Truy vấn theo số hiệu đi nhánh SQL, trả chính xác.
5. Bộ test phân quyền chứng minh **không rò rỉ tiêu đề lẫn số đếm facet** của văn bản ngoài quyền (V-13, O-03).
6. Embed service tắt → tìm kiếm vẫn hoạt động ở chế độ lexical, có cảnh báo.
7. Toàn bộ test chạy xanh trên máy không có GPU.
