# Document Intelligence Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tệp đính kèm vào `aidt.document` được tự động trích xuất, chunk, chỉ mục lai (vector + lexical), và tìm được bằng câu hỏi tiếng Việt tự nhiên với kết quả có trích dẫn và lọc quyền.

**Architecture:** Chỉ mục nằm trong chính Postgres của Odoo (pgvector + tsvector) nên ACL kế thừa miễn phí từ `ir.rule` sẵn có trên `aidt.document`. Suy luận model chạy ở container ngoài qua HTTP OpenAI-compatible. Logic thuần (chunker, phân tích ý định, RRF) nằm trong thư viện `aidt_search_engine` không import `odoo`, test bằng pytest không cần database.

**Tech Stack:** Odoo 19 Community · PostgreSQL 16 + pgvector + unaccent · vLLM (Unlimited-OCR, Vietnamese_Embedding) · poppler-utils · OWL 2 · python-docx (qua `aidt_format_engine`)

**Spec:** `docs/superpowers/specs/2026-08-01-document-intelligence-search-design.md`

## Global Constraints

- **Database:** chỉ tồn tại **một** database `aidt_demo`. Test dùng DB tạm phải `DROP DATABASE` + `rm -rf` thư mục filestore tương ứng khi xong. Không tạo `aidt_poc`, `db`, `*_tmp`.
- **Không sửa `extra-addons/`** (OCA DMS vendored). Mọi tuỳ chỉnh nằm ở `custom-addons/`.
- **Không sửa `custom-addons/aidt_format_engine/`.** Cần thích ứng thì viết adapter trong `aidt_search_engine`.
- **`aidt_search_engine` không được `import odoo`** ở bất kỳ module nào ngoài `_compat.py`.
- **Không gọi dịch vụ ngoài mạng** (N-15/N-18). Mọi model self-host. Test **luôn mock** HTTP; không test nào chạm GPU.
- **Ngôn ngữ UI:** tiếng Việt. Tên trường/model bằng tiếng Việt không dấu snake_case theo lệ đang có (`so_ky_hieu`, `do_khan`).
- **License header:** các module dùng `LGPL-3` như những `aidt_*` khác.
- **Commit** sau mỗi task, message tiếng Anh theo lệ repo (`feat(search): ...`, `test(search): ...`).
- **Chạy test thư viện thuần:** `cd custom-addons && python -m pytest aidt_search_engine/tests -q`
- **Chạy test Odoo:** `docker compose -f docker-compose.dev.yml run --rm odoo odoo -d aidt_test -i aidt_search --test-enable --stop-after-init --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons` rồi dọn `aidt_test`.

---

## File Structure

### `custom-addons/aidt_search_engine/` — thư viện thuần, không import `odoo`

| Tệp | Trách nhiệm |
|---|---|
| `__init__.py` | Rỗng (theo khuôn `aidt_format_engine`) |
| `_compat.py` | Cầu import `aidt_format_engine` cho cả hai môi trường (Odoo / pytest) |
| `types.py` | `Block`, `Chunk`, `DocMeta`, `QueryFilter`, `ParsedQuery`, `Candidate` |
| `text.py` | `strip_accents()`, `estimate_tokens()`, `normalize_ws()` |
| `tokenize.py` | `tokenize(text, mode, segmenter)` — khe cắm tách từ, mặc định `syllable` |
| `header.py` | `build_header()`, `build_embed_text()` — contextual chunk header |
| `chunker.py` | `detect_heading()`, `split_long_text()`, `chunk_blocks()` |
| `intent.py` | `parse_query()` — bóc số hiệu + filter cứng khỏi câu truy vấn |
| `fusion.py` | `reciprocal_rank_fusion()` |
| `rerank.py` | `rerank()` — khe cắm, v1 trả nguyên danh sách |
| `extract/docx.py` | `extract_docx(blob) -> list[Block]` qua `aidt_format_engine` |
| `extract/pdf.py` | `page_count()`, `page_text()`, `render_page_png()` — bọc poppler-utils |
| `extract/ocr.py` | `ocr_image()` — client Unlimited-OCR, parse `<\|det\|>` |
| `extract/zone_adapter.py` | `assign_zones(blocks, page_width)` — dựng `Para` giả rồi gọi `detect_zones` |
| `tests/` | pytest, một tệp cho mỗi module trên |

### `custom-addons/aidt_search/` — addon Odoo

| Tệp | Trách nhiệm |
|---|---|
| `__manifest__.py` | `depends: ['aidt_dms', 'aidt_org']` |
| `models/doc_chunk.py` | `aidt.doc.chunk` + cột SQL thuần trong `_auto_init` |
| `models/index_job.py` | `aidt.index.job` — hàng đợi, chống trùng, phân loại lỗi, cron |
| `models/pipeline.py` | `aidt.index.pipeline` (AbstractModel) — điều phối extract→chunk→embed→store |
| `models/embed_client.py` | `aidt.embed.client` (AbstractModel) — gọi `/v1/embeddings`, kiểm số chiều |
| `models/dms_file.py` | Hook `create`/`write` → xếp hàng chỉ mục |
| `models/aidt_document.py` | `index_state`, `chunk_count`, nút chỉ mục lại, hook đổi `reference` |
| `models/search_service.py` | `aidt.search.service` (AbstractModel) — truy vấn, ACL, RRF, facet |
| `models/search_log.py` | `aidt.search.log` |
| `views/*.xml`, `security/*`, `data/ir_cron.xml`, `static/src/**` | UI, quyền, cron |
| `tests/` | `TransactionCase` |

---

## Task 1: Spike — kiểm chứng R1 và R3 trước khi viết code

Đây là task **kiểm chứng**, không phải TDD. Nó tồn tại vì hai giả định trong spec có thể làm đổi thiết kế; biết sớm rẻ hơn biết muộn.

**Files:**
- Create: `/tmp/claude-1001/-home-chauanphu-projects-aidt-odoo/*/scratchpad/spike_r1.py` (tạm, không commit)
- Create: `docs/superpowers/plans/2026-08-01-spike-findings.md`

**Interfaces:**
- Consumes: `aidt_format_engine.zones.detect_zones`, `aidt_format_engine.types.Para/EffFormat/IntermediateDoc/PageSetup`
- Produces: quyết định ghi trong `spike-findings.md` — `detect_zones` dùng lại được hay phải viết adapter riêng; con số OCR sau khi hạ VRAM

- [ ] **Step 1: Dựng `Para` giả từ dữ liệu kiểu OCR rồi gọi `detect_zones`**

Tạo script trong scratchpad:

```python
import sys
sys.path.insert(0, "/home/chauanphu/projects/aidt-odoo/custom-addons")

from aidt_format_engine.types import EffFormat, IntermediateDoc, PageSetup, Para
from aidt_format_engine.zones import detect_zones

# Mô phỏng đúng thứ nhánh OCR có: text + align suy từ bbox. Không có font,
# không có size, không có style_name — đây chính là điều kiện cần kiểm.
LINES = [
    ("ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG", "center"),
    ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "center"),
    ("Độc lập - Tự do - Hạnh phúc", "center"),
    ("Số: 145/KH-UBND", "left"),
    ("Bình Dương, ngày 25 tháng 7 năm 2026", "right"),
    ("KẾ HOẠCH", "center"),
    ("Bảo đảm an toàn hệ thống thông tin năm 2026", "center"),
    ("Căn cứ Luật An toàn thông tin mạng năm 2015;", "justify"),
    ("Nơi nhận:", "left"),
    ("TM. ỦY BAN NHÂN DÂN", "right"),
    ("Nguyễn Văn A", "right"),
]

paras = [
    Para(index=i, text=t, style_name=None, fmt=EffFormat(align=a))
    for i, (t, a) in enumerate(LINES)
]
doc = IntermediateDoc(pages=PageSetup(width_mm=210.0, height_mm=297.0, margin_mm={}), paras=paras)

detect_zones(doc)
for p in doc.paras:
    print(f"{p.zone!s:<20} {p.zone_confidence!s:<10} {p.text[:45]}")
```

- [ ] **Step 2: Chạy và ghi lại kết quả thật**

Run: `python /tmp/claude-1001/-home-chauanphu-projects-aidt-odoo/*/scratchpad/spike_r1.py`

Ba kết cục có thể, và việc phải làm cho từng cái:

| Kết cục | Nghĩa là | Việc phải làm |
|---|---|---|
| Chạy xong, zone gán hợp lý | R1 đóng, tái sử dụng được | Task 9 `zone_adapter.py` chỉ là hàm dựng `Para` |
| Chạy xong nhưng zone sai nhiều | Heuristic phụ thuộc thuộc tính DOCX | Task 9 bổ sung suy `bold`/`size_pt` từ chiều cao bbox, chạy lại |
| Ném `TypeError`/`AttributeError` vì `None` | R1 mở | Task 9 viết bộ nhận vùng riêng trong `aidt_search_engine`, dùng lại **regex** của `zones.py` bằng cách import hằng số, không import hàm |

**Không sửa `aidt_format_engine` trong bất kỳ kết cục nào.**

- [ ] **Step 3: Đo lại tốc độ OCR sau khi hạ VRAM (R3)**

```bash
docker rm -f unlimited-ocr
docker run -d --name unlimited-ocr --gpus all --ipc host --restart unless-stopped \
  -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:unlimited-ocr baidu/Unlimited-OCR \
  --served-model-name baidu/Unlimited-OCR --trust-remote-code \
  --logits_processors vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor \
  --no-enable-prefix-caching --mm-processor-cache-gb 0 \
  --gpu-memory-utilization 0.55 --host 0.0.0.0 --port 8000

# đợi sẵn sàng
until curl -sf http://localhost:8000/health; do sleep 5; done
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

- [ ] **Step 4: Đo thời gian OCR một trang thật**

```bash
cd /home/chauanphu/projects/aidt-odoo
SP=/tmp/claude-1001/-home-chauanphu-projects-aidt-odoo/*/scratchpad
pdftoppm -r 150 -png -f 1 -l 1 docs/demo/01-dat-chuan.pdf $SP/page
python - <<'PY'
import base64, glob, json, time, urllib.request
png = sorted(glob.glob("/tmp/claude-1001/-home-chauanphu-projects-aidt-odoo/*/scratchpad/page-1.png"))[0]
b64 = base64.b64encode(open(png, "rb").read()).decode()
body = {
    "model": "baidu/Unlimited-OCR",
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": "<image>document parsing."},
    ]}],
    "max_tokens": 4096, "skip_special_tokens": False,
    "vllm_xargs": {"ngram_size": 35, "window_size": 1024},
}
req = urllib.request.Request("http://localhost:8000/v1/chat/completions",
    data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
t0 = time.time()
out = json.load(urllib.request.urlopen(req, timeout=180))
print(f"{time.time()-t0:.2f}s  usage={out['usage']}")
print(out["choices"][0]["message"]["content"][:400])
PY
```

Mốc so sánh: **2.7s/trang** đo được ở cấu hình cũ (không giới hạn VRAM). Chậm hơn 2× thì nâng `--gpu-memory-utilization` lên 0.65 và đo lại; vẫn không đạt thì ghi vào findings là embedding phải chạy CPU.

- [ ] **Step 5: Ghi findings và commit**

Tạo `docs/superpowers/plans/2026-08-01-spike-findings.md` với đúng bốn mục: kết cục R1 (dán output thật), quyết định cho Task 9, số đo R3 (VRAM còn trống + s/trang), quyết định cho Task 2.

```bash
git add docs/superpowers/plans/2026-08-01-spike-findings.md
git commit -m "docs(search): record R1/R3 spike findings before implementation"
```

---

## Task 2: Hạ tầng — pgvector, poppler-utils, service embedding

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `Dockerfile:48-68` (thêm `poppler-utils` vào danh sách apt của stage `runtime`)

**Interfaces:**
- Produces: DB có extension `vector` + `unaccent` + hàm `f_unaccent`; `http://aidt-embed:8001/v1/embeddings` trả vector 1024 chiều; `pdftoppm`/`pdftotext`/`pdfinfo` có trong image Odoo

- [ ] **Step 1: Thêm `poppler-utils` vào Dockerfile**

Trong stage `runtime`, danh sách `apt-get install`, chèn theo thứ tự chữ cái giữa `nodejs`/`npm` và `postgresql-client`:

```dockerfile
        npm \
        poppler-utils \
        postgresql-client \
```

- [ ] **Step 2: Đổi image Postgres và thêm service embedding**

Trong `docker-compose.dev.yml`, đổi `image: postgres:16-alpine` thành:

```yaml
    image: pgvector/pgvector:pg16
```

Thêm service mới (cùng cấp với `db` và `odoo`):

```yaml
  aidt-embed:
    image: vllm/vllm-openai:latest
    command:
      - --model=AITeamVN/Vietnamese_Embedding
      - --served-model-name=AITeamVN/Vietnamese_Embedding
      # vLLM 0.26 bỏ --task=embed; đây là cặp cờ thay thế.
      - --runner=pooling
      - --convert=embed
      - --gpu-memory-utilization=0.15
      - --max-model-len=2048
      - --host=0.0.0.0
      - --port=8001
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ports:
      - "8001:8001"
    ipc: host
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8001/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 20
```

`--gpu-memory-utilization=0.15` là ~2447 MiB trên card 16311 MiB — đủ cho model 568M ở fp16 cộng activation.

> **Đã sửa theo Task 1 (R3).** Bản đầu của kế hoạch này ghi OCR chạy ở `0.55`. Spike đo được: **`0.55` và `0.65` đều crash-loop**, không phải chạy chậm — vLLM ném `ValueError: No available memory for the cache blocks`. Giá trị thấp nhất khởi động được là **`0.75`** (~4886–5270 MiB còn trống, OCR 2.62s/trang, **không chậm hơn** mốc 2.7s).
>
> Hệ quả: ngân sách gộp là `0.75 + 0.15 = 0.90`, chỉ còn ~1.6GB dư — chặt hơn nhiều so với dự tính ban đầu. Vì vậy **Step 6 phải xác minh hai service chạy đồng thời**, không chỉ xác minh service embedding khởi động một mình.
>
> **Container OCR đã đang chạy ở `0.75` do Task 1 để lại.** Task này **không** cần khởi động lại nó — chỉ xác minh (`docker ps`, `curl /health`) rồi đi tiếp. Chỉ khởi động lại nếu nó đã chết:
> ```bash
> docker run -d --name unlimited-ocr --gpus all --ipc host --restart unless-stopped \
>   -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
>   vllm/vllm-openai:unlimited-ocr baidu/Unlimited-OCR \
>   --served-model-name baidu/Unlimited-OCR --trust-remote-code \
>   --logits_processors vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor \
>   --no-enable-prefix-caching --mm-processor-cache-gb 0 \
>   --gpu-memory-utilization 0.75 --host 0.0.0.0 --port 8000
> ```

- [ ] **Step 3: Dựng lại stack và xác minh extension**

```bash
cd /home/chauanphu/projects/aidt-odoo
docker compose -f docker-compose.dev.yml up -d --build db odoo
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_demo -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS unaccent;"
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_demo -c "\dx" 
```

Expected: bảng liệt kê có cả `vector` và `unaccent`.

- [ ] **Step 4: Xác minh R2 — `unaccent` có xử lý `đ` không**

```bash
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_demo -c "SELECT unaccent('Đảng hộ nghèo') AS out;"
```

Expected: `Dang ho ngheo`.

Nếu ra `Đang ho ngheo` (chữ `Đ` không đổi) thì R2 mở — tạo file rules riêng:

```bash
docker compose -f docker-compose.dev.yml exec db sh -c \
  'cp "$(pg_config --sharedir)/tsearch_data/unaccent.rules" "$(pg_config --sharedir)/tsearch_data/vi.rules" \
   && printf "Đ\tD\nđ\td\n" >> "$(pg_config --sharedir)/tsearch_data/vi.rules"'
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_demo -c "CREATE TEXT SEARCH DICTIONARY vi_unaccent (TEMPLATE=unaccent, RULES='vi');"
```

Ghi kết quả thật vào `spike-findings.md`. Task 5 phụ thuộc điều này: `strip_accents()` phía Python **phải khớp** hành vi của `unaccent` phía SQL, nếu không truy vấn không dấu sẽ trượt.

- [ ] **Step 5: Xác minh poppler trong image Odoo**

```bash
docker compose -f docker-compose.dev.yml exec odoo sh -c "pdftoppm -v; pdftotext -v; pdfinfo -v"
```

Expected: cả ba in ra phiên bản poppler, exit 0.

- [ ] **Step 6: Dựng service embedding và xác minh số chiều**

```bash
docker compose -f docker-compose.dev.yml up -d aidt-embed
until curl -sf http://localhost:8001/health; do sleep 10; done
curl -s http://localhost:8001/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"AITeamVN/Vietnamese_Embedding","input":["hỗ trợ hộ nghèo"]}' \
  | python -c "import json,sys; d=json.load(sys.stdin); print('dim =', len(d['data'][0]['embedding']))"
```

Expected: `dim = 1024`.

Ra số khác thì **dừng lại và báo** — mọi thứ sau đều gắn với `vector(1024)`; đổi số chiều là đổi spec, không phải đổi một tham số.

Rồi xác minh **hai service cùng sống**, vì ngân sách gộp chỉ còn ~1.6GB dư:

```bash
docker ps --filter name=unlimited-ocr --filter name=aidt-embed --format '{{.Names}}\t{{.Status}}'
curl -sf http://localhost:8000/health && echo " OCR ok"
curl -sf http://localhost:8001/health && echo " EMBED ok"
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

Expected: cả hai container `Up`, cả hai `/health` trả 200.

Nếu service embedding không khởi động được vì hết VRAM, **đừng hạ `--gpu-memory-utilization` của OCR** (dưới 0.75 là crash-loop, đã đo ở Task 1). Thay vào đó cho embedding chạy CPU — ở quy mô vài trăm văn bản là chấp nhận được: bỏ khối `deploy.resources` khỏi service `embed` và thêm `--device=cpu`. Ghi lựa chọn thực tế vào `spike-findings.md` để Task 14 biết ngân sách thời gian embed khác đi.

- [ ] **Step 7: Commit**

```bash
git add Dockerfile docker-compose.dev.yml docs/superpowers/plans/2026-08-01-spike-findings.md
git commit -m "build(search): add pgvector, poppler-utils and embedding service to dev stack"
```

---

## Task 3: `aidt_search_engine` — khung thư viện, kiểu dữ liệu, tiện ích text

**Files:**
- Create: `custom-addons/aidt_search_engine/__init__.py`
- Create: `custom-addons/aidt_search_engine/_compat.py`
- Create: `custom-addons/aidt_search_engine/types.py`
- Create: `custom-addons/aidt_search_engine/text.py`
- Create: `custom-addons/aidt_search_engine/tests/__init__.py`
- Test: `custom-addons/aidt_search_engine/tests/test_text.py`

**Interfaces:**
- Produces:
  - `types.Block(text, zone=None, zone_confidence=None, page=None, bbox=None, confidence=None)`
  - `types.Chunk(seq, text, embed_text, zone, zone_confidence, heading_path, page, bbox, token_count)`
  - `types.DocMeta(doc_type_label=None, reference=None, title=None)`
  - `types.QueryFilter(field, op, value, label, span)`
  - `types.ParsedQuery(raw, semantic, reference, filters)`
  - `types.Candidate(chunk_id, document_id, score=0.0)`
  - `text.strip_accents(s) -> str`
  - `text.estimate_tokens(s) -> int`
  - `text.normalize_ws(s) -> str`
  - `_compat.fe_parser`, `_compat.fe_zones`, `_compat.fe_types` (module `aidt_format_engine`)

- [ ] **Step 1: Viết test thất bại cho `text.py`**

Tạo `custom-addons/aidt_search_engine/tests/test_text.py`:

```python
import unittest

from aidt_search_engine.text import estimate_tokens, normalize_ws, strip_accents


class TestStripAccents(unittest.TestCase):
    def test_bo_dau_tieng_viet(self):
        self.assertEqual(strip_accents("hỗ trợ hộ nghèo"), "ho tro ho ngheo")

    def test_chu_d_gach_ngang(self):
        # NFD không phân rã 'đ' — phải xử lý riêng, nếu không kênh
        # không dấu sẽ lệch với unaccent() phía Postgres.
        self.assertEqual(strip_accents("Đảng đoàn"), "Dang doan")

    def test_giu_nguyen_chu_khong_dau(self):
        self.assertEqual(strip_accents("145/KH-UBND"), "145/KH-UBND")

    def test_chuoi_rong(self):
        self.assertEqual(strip_accents(""), "")


class TestEstimateTokens(unittest.TestCase):
    def test_uoc_luong_theo_do_dai(self):
        self.assertEqual(estimate_tokens("abcdef"), 2)

    def test_chuoi_rong_van_tra_it_nhat_1(self):
        self.assertEqual(estimate_tokens(""), 1)


class TestNormalizeWs(unittest.TestCase):
    def test_gop_khoang_trang(self):
        self.assertEqual(normalize_ws("  hỗ   trợ \n\n hộ nghèo "), "hỗ trợ hộ nghèo")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_text.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine'`

- [ ] **Step 3: Tạo khung package và `text.py`**

`custom-addons/aidt_search_engine/__init__.py` — tệp rỗng.
`custom-addons/aidt_search_engine/tests/__init__.py` — tệp rỗng.

`custom-addons/aidt_search_engine/text.py`:

```python
"""Tiện ích xử lý chuỗi dùng chung, không phụ thuộc Odoo."""

import re
import unicodedata

# Ước lượng thô: tiếng Việt khoảng 3 ký tự một token với tokenizer XLM-R.
# Chỉ dùng để quyết định chỗ cắt chunk (ngưỡng 400), cách xa giới hạn 8192
# của model nên sai số không gây tràn — không đáng gọi tokenizer thật.
CHARS_PER_TOKEN = 3

_WS = re.compile(r"\s+")


def strip_accents(s):
    """Bỏ dấu tiếng Việt.

    Phải khớp hành vi unaccent() của Postgres, vì kênh tìm kiếm không dấu
    so khớp chuỗi sinh ở Python với cột tsvector sinh ở SQL. NFD không phân
    rã 'đ'/'Đ' nên hai ký tự này xử lý riêng.
    """
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def estimate_tokens(s):
    """Số token ước lượng, luôn ≥ 1 để không có chunk 'không tốn gì'."""
    return max(1, len(s or "") // CHARS_PER_TOKEN)


def normalize_ws(s):
    """Gộp mọi chuỗi khoảng trắng thành một dấu cách, cắt hai đầu."""
    return _WS.sub(" ", s or "").strip()
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_text.py -q`
Expected: PASS, 7 passed

- [ ] **Step 5: Viết `types.py`**

```python
"""Kiểu dữ liệu dùng chung giữa các tầng của đường ống tìm kiếm."""

from dataclasses import dataclass, field


@dataclass
class Block:
    """Một khối nội dung đã trích xuất, chung cho cả nhánh DOCX lẫn OCR."""
    text: str
    zone: str | None = None
    zone_confidence: str | None = None      # 'style' | 'heuristic'
    page: int | None = None
    bbox: tuple | None = None               # (x0, y0, x1, y1)
    confidence: float | None = None         # chỉ nhánh OCR


@dataclass
class DocMeta:
    """Metadata cấp văn bản, dùng dựng contextual header."""
    doc_type_label: str | None = None       # 'Kế hoạch'
    reference: str | None = None            # '145/KH-UBND'
    title: str | None = None                # trích yếu


@dataclass
class Chunk:
    seq: int
    text: str
    embed_text: str
    heading_path: str = ""
    zone: str | None = None
    zone_confidence: str | None = None
    page: int | None = None
    bbox: tuple | None = None
    token_count: int = 0


@dataclass
class QueryFilter:
    """Một điều kiện lọc cứng bóc ra khỏi câu truy vấn."""
    field: str                              # 'date' | 'department_id' | 'doc_type' | 'do_khan'
    op: str                                 # 'between' | '='
    value: object
    label: str                              # chữ hiển thị trên chip "Đã hiểu"
    span: tuple                             # (start, end) trong chuỗi raw


@dataclass
class ParsedQuery:
    raw: str
    semantic: str
    reference: str | None = None
    filters: list = field(default_factory=list)


@dataclass
class Candidate:
    chunk_id: int
    document_id: int
    score: float = 0.0
```

- [ ] **Step 6: Viết `_compat.py`**

```python
"""Cầu import tới aidt_format_engine.

Cùng một thư viện có hai đường import tuỳ môi trường: lúc Odoo chạy thì nó
nằm dưới namespace `odoo.addons`; lúc chạy pytest thì `custom-addons` nằm
trên sys.path nên import thẳng. Đây là module DUY NHẤT trong
aidt_search_engine được phép nhắc tới `odoo`.
"""

try:                                        # trong Odoo
    from odoo.addons.aidt_format_engine import parser as fe_parser
    from odoo.addons.aidt_format_engine import types as fe_types
    from odoo.addons.aidt_format_engine import zones as fe_zones
except ImportError:                         # pytest ngoài Odoo
    from aidt_format_engine import parser as fe_parser
    from aidt_format_engine import types as fe_types
    from aidt_format_engine import zones as fe_zones

__all__ = ["fe_parser", "fe_types", "fe_zones"]
```

- [ ] **Step 7: Viết test cho `_compat` và `types`**

Tạo `custom-addons/aidt_search_engine/tests/test_compat.py`:

```python
import unittest

from aidt_search_engine._compat import fe_parser, fe_types, fe_zones
from aidt_search_engine.types import Block, Candidate, Chunk, DocMeta, ParsedQuery


class TestCompat(unittest.TestCase):
    def test_import_duoc_format_engine(self):
        self.assertTrue(hasattr(fe_parser, "parse_docx"))
        self.assertTrue(hasattr(fe_zones, "detect_zones"))
        self.assertTrue(hasattr(fe_types, "Para"))

    def test_zones_co_du_12_vung(self):
        self.assertEqual(len(fe_zones.ZONES), 12)
        self.assertIn("trich_yeu", fe_zones.ZONES)
        self.assertIn("noi_nhan", fe_zones.ZONES)


class TestTypes(unittest.TestCase):
    def test_block_mac_dinh(self):
        b = Block(text="xin chào")
        self.assertIsNone(b.zone)
        self.assertIsNone(b.bbox)

    def test_chunk_va_docmeta_khoi_tao_duoc(self):
        c = Chunk(seq=0, text="a", embed_text="b")
        self.assertEqual(c.heading_path, "")
        self.assertEqual(DocMeta().reference, None)

    def test_parsedquery_filters_khong_dung_chung(self):
        a, b = ParsedQuery(raw="x", semantic="x"), ParsedQuery(raw="y", semantic="y")
        a.filters.append("z")
        self.assertEqual(b.filters, [])

    def test_candidate_score_mac_dinh(self):
        self.assertEqual(Candidate(chunk_id=1, document_id=2).score, 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 8: Chạy toàn bộ test của thư viện**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests -q`
Expected: PASS, 13 passed

- [ ] **Step 9: Commit**

```bash
git add custom-addons/aidt_search_engine
git commit -m "feat(search): add aidt_search_engine skeleton with types and text helpers"
```

---

## Task 4: Khe cắm tách từ (`tokenize.py`)

**Files:**
- Create: `custom-addons/aidt_search_engine/tokenize.py`
- Test: `custom-addons/aidt_search_engine/tests/test_tokenize.py`

**Interfaces:**
- Consumes: không
- Produces: `tokenize(text, mode="syllable", segmenter=None) -> str`; hằng `MODE_SYLLABLE = "syllable"`, `MODE_WORD = "word"`

- [ ] **Step 1: Viết test thất bại**

```python
import unittest

from aidt_search_engine.tokenize import MODE_SYLLABLE, MODE_WORD, tokenize


def fake_segmenter(text):
    """Giả lập underthesea/pyvi: nối âm tiết cùng từ bằng '_'."""
    return text.replace("hộ nghèo", "hộ_nghèo").replace("an toàn", "an_toàn")


class TestTokenize(unittest.TestCase):
    def test_syllable_tra_nguyen_van(self):
        self.assertEqual(tokenize("hỗ trợ hộ nghèo", MODE_SYLLABLE), "hỗ trợ hộ nghèo")

    def test_word_dung_segmenter_duoc_truyen_vao(self):
        self.assertEqual(
            tokenize("hỗ trợ hộ nghèo", MODE_WORD, segmenter=fake_segmenter),
            "hỗ trợ hộ_nghèo",
        )

    def test_word_lui_ve_syllable_khi_khong_co_thu_vien(self):
        # segmenter=False mô phỏng "không cài underthesea lẫn pyvi".
        # Phải lùi êm chứ không được ném lỗi: v1 mặc định chạy không có
        # thư viện tách từ nào.
        self.assertEqual(
            tokenize("hỗ trợ hộ nghèo", MODE_WORD, segmenter=False),
            "hỗ trợ hộ nghèo",
        )

    def test_mode_la_gi_khac_thi_coi_nhu_syllable(self):
        self.assertEqual(tokenize("abc", "linh tinh"), "abc")

    def test_chuoi_rong(self):
        self.assertEqual(tokenize("", MODE_WORD, segmenter=fake_segmenter), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_tokenize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.tokenize'`

- [ ] **Step 3: Viết `tokenize.py`**

```python
"""Khe cắm tách từ tiếng Việt.

v1 chạy ở chế độ 'syllable' (trả nguyên văn) — kênh ts_seg tắt. Bật lên
'word' khi bộ eval của dự án con D cho thấy độ chính xác trên truy vấn cụm
nhiều âm tiết thấp hơn ngưỡng. Xem §5.1 và §1.3 của spec.

Thư viện tách từ được import MỀM: không cài thì lùi về syllable chứ không
ném lỗi, vì môi trường mặc định không có chúng.
"""

MODE_SYLLABLE = "syllable"
MODE_WORD = "word"

_CACHED = None                              # None = chưa dò, False = không có


def _load_segmenter():
    """Dò underthesea trước (chính xác hơn), rồi pyvi (nhẹ hơn, không tải model)."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    try:
        from underthesea import word_tokenize

        _CACHED = lambda t: word_tokenize(t, format="text")  # noqa: E731
        return _CACHED
    except ImportError:
        pass
    try:
        from pyvi import ViTokenizer

        _CACHED = ViTokenizer.tokenize
        return _CACHED
    except ImportError:
        _CACHED = False
    return _CACHED


def tokenize(text, mode=MODE_SYLLABLE, segmenter=None):
    """Chuẩn bị chuỗi cho to_tsvector.

    mode='syllable': trả nguyên văn — Postgres tự tách theo khoảng trắng.
    mode='word': nối âm tiết cùng từ bằng '_' để mỗi từ thành một token.

    `segmenter` cho phép test tiêm hàm giả; truyền False để mô phỏng môi
    trường không có thư viện nào.
    """
    if not text or mode != MODE_WORD:
        return text or ""
    seg = _load_segmenter() if segmenter is None else segmenter
    if not seg:
        return text
    return seg(text)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_tokenize.py -q`
Expected: PASS, 5 passed

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_search_engine/tokenize.py custom-addons/aidt_search_engine/tests/test_tokenize.py
git commit -m "feat(search): add Vietnamese word-segmentation seam, off by default"
```

---

## Task 5: Contextual chunk header (`header.py`)

Đây là kỹ thuật rẻ nhất và hiệu quả nhất trong cả thiết kế: nối tiêu đề văn bản và đường dẫn mục vào đầu mỗi chunk **trước khi embed**. Chunk lẻ mất ngữ cảnh là nguyên nhân thất bại phổ biến nhất của RAG doanh nghiệp.

**Files:**
- Create: `custom-addons/aidt_search_engine/header.py`
- Test: `custom-addons/aidt_search_engine/tests/test_header.py`

**Interfaces:**
- Consumes: `types.DocMeta`
- Produces: `build_header(meta, heading_path) -> str`; `build_embed_text(meta, heading_path, text) -> str`; hằng `SEP = "\n---\n"`

- [ ] **Step 1: Viết test thất bại**

```python
import unittest

from aidt_search_engine.header import build_embed_text, build_header
from aidt_search_engine.types import DocMeta

FULL = DocMeta(
    doc_type_label="Kế hoạch",
    reference="145/KH-UBND",
    title="Kế hoạch bảo đảm an toàn thông tin năm 2026",
)


class TestBuildHeader(unittest.TestCase):
    def test_day_du_hai_dong(self):
        self.assertEqual(
            build_header(FULL, "Phần II › Mục 3"),
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026\n"
            "Phần II › Mục 3",
        )

    def test_khong_co_duong_dan_muc_thi_chi_mot_dong(self):
        self.assertEqual(
            build_header(FULL, ""),
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026",
        )

    def test_thieu_so_ky_hieu(self):
        meta = DocMeta(doc_type_label="Công văn", title="Về việc phối hợp")
        self.assertEqual(build_header(meta, ""), "Công văn — Về việc phối hợp")

    def test_chi_co_trich_yeu(self):
        self.assertEqual(build_header(DocMeta(title="Về việc phối hợp"), ""),
                         "Về việc phối hợp")

    def test_metadata_rong_tra_chuoi_rong(self):
        self.assertEqual(build_header(DocMeta(), ""), "")


class TestBuildEmbedText(unittest.TestCase):
    def test_ghep_header_va_noi_dung(self):
        out = build_embed_text(FULL, "Điều 7", "Các sở, ban, ngành có trách nhiệm...")
        self.assertEqual(
            out,
            "Kế hoạch 145/KH-UBND — Kế hoạch bảo đảm an toàn thông tin năm 2026\n"
            "Điều 7\n---\nCác sở, ban, ngành có trách nhiệm...",
        )

    def test_khong_co_header_thi_khong_co_dau_phan_cach(self):
        # Không được để chunk mở đầu bằng '---' trơ trọi: nó sẽ được embed
        # như một token vô nghĩa ở vị trí quan trọng nhất của chuỗi.
        self.assertEqual(build_embed_text(DocMeta(), "", "nội dung"), "nội dung")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_header.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.header'`

- [ ] **Step 3: Viết `header.py`**

```python
"""Contextual chunk header.

Nối tiêu đề văn bản và đường dẫn mục vào đầu mỗi chunk trước khi embed, để
một đoạn tách rời vẫn mang đủ ngữ cảnh biết nó thuộc văn bản nào, mục nào.
"""

SEP = "\n---\n"


def build_header(meta, heading_path):
    """Dựng phần header hai dòng.

    Dòng 1: '{loại} {số ký hiệu} — {trích yếu}', bỏ qua phần nào thiếu.
    Dòng 2: đường dẫn mục ('Phần II › Mục 3'), bỏ hẳn nếu rỗng.
    """
    left = " ".join(p for p in (meta.doc_type_label, meta.reference) if p)
    if meta.title:
        line1 = f"{left} — {meta.title}" if left else meta.title
    else:
        line1 = left
    return "\n".join(line for line in (line1, heading_path) if line)


def build_embed_text(meta, heading_path, text):
    """Chuỗi thực sự đem đi embed. Lưu nguyên vào cột embed_text để về sau
    tái lập được: khi kết quả sai, câu hỏi đầu tiên luôn là 'nó đã embed gì'."""
    header = build_header(meta, heading_path)
    return f"{header}{SEP}{text}" if header else text
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_header.py -q`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_search_engine/header.py custom-addons/aidt_search_engine/tests/test_header.py
git commit -m "feat(search): add contextual chunk header builder"
```

---

## Task 6: Chunker (`chunker.py`)

Trái tim của tầng 4. **Cấu trúc trước, kích thước sau.**

Ba bậc ranh giới — đây là chỗ tinh chỉnh so với spec §4.6, đã cập nhật lại spec cho khớp:

| Bậc | Gồm | Hành vi |
|---|---|---|
| **Cứng** | `zone` đổi; `Phần/Chương/Mục/Điều` | Luôn cắt. `Phần/Chương/Mục/Điều` còn nối vào `heading_path` |
| **Mềm** | `^\d+\.`, `^[a-zđ])` | Chỉ cắt khi chunk đã chạm ngưỡng. Coi là cứng thì một danh sách 20 gạch đầu dòng thành 20 chunk tí hon, làm loãng chỉ mục |
| **Cuối** | Ranh giới câu | Dùng khi một khối đơn lẻ dài quá ngưỡng |

**Files:**
- Create: `custom-addons/aidt_search_engine/chunker.py`
- Test: `custom-addons/aidt_search_engine/tests/test_chunker.py`

**Interfaces:**
- Consumes: `types.Block`, `types.Chunk`, `types.DocMeta`, `header.build_embed_text`, `text.estimate_tokens`
- Produces:
  - `detect_heading(text) -> tuple[int, str] | None`
  - `is_soft_boundary(text) -> bool`
  - `split_long_text(text, target_tokens, overlap_sentences=1) -> list[str]`
  - `chunk_blocks(blocks, meta, target_tokens=400) -> list[Chunk]`
  - hằng `TARGET_TOKENS = 400`, `STANDALONE_ZONES = ("so_ky_hieu", "trich_yeu", "noi_nhan", "chu_ky")`

- [ ] **Step 1: Viết test thất bại cho `detect_heading` và `split_long_text`**

```python
import unittest

from aidt_search_engine.chunker import (
    STANDALONE_ZONES,
    chunk_blocks,
    detect_heading,
    is_soft_boundary,
    split_long_text,
)
from aidt_search_engine.types import Block, DocMeta

META = DocMeta(doc_type_label="Kế hoạch", reference="145/KH-UBND", title="An toàn thông tin")


class TestDetectHeading(unittest.TestCase):
    def test_phan_la_bac_1(self):
        self.assertEqual(detect_heading("PHẦN II. MỤC TIÊU"), (1, "PHẦN II"))

    def test_chuong_la_bac_2(self):
        self.assertEqual(detect_heading("Chương IV"), (2, "Chương IV"))

    def test_muc_la_bac_3(self):
        self.assertEqual(detect_heading("Mục 3. Tổ chức thực hiện"), (3, "Mục 3"))

    def test_dieu_la_bac_4(self):
        self.assertEqual(detect_heading("Điều 7. Trách nhiệm"), (4, "Điều 7"))

    def test_doan_thuong_khong_phai_tieu_de(self):
        self.assertIsNone(detect_heading("Các sở, ban, ngành có trách nhiệm"))

    def test_khong_bat_nham_giua_cau(self):
        # 'Điều' xuất hiện giữa câu không phải tiêu đề.
        self.assertIsNone(detect_heading("Căn cứ Điều 7 của Luật nêu trên"))


class TestIsSoftBoundary(unittest.TestCase):
    def test_so_thu_tu(self):
        self.assertTrue(is_soft_boundary("1. Mục tiêu chung"))

    def test_chu_cai_ngoac(self):
        self.assertTrue(is_soft_boundary("a) Bố trí kinh phí"))

    def test_doan_thuong(self):
        self.assertFalse(is_soft_boundary("Các sở, ban, ngành"))


class TestSplitLongText(unittest.TestCase):
    def test_ngan_hon_nguong_thi_khong_cat(self):
        self.assertEqual(split_long_text("Một câu ngắn.", 400), ["Một câu ngắn."])

    def test_dai_hon_nguong_thi_cat_theo_cau(self):
        text = " ".join(f"Câu số {i} dài vừa đủ để cộng dồn." for i in range(60))
        pieces = split_long_text(text, 50)
        self.assertGreater(len(pieces), 1)
        # Không mảnh nào được vượt xa ngưỡng.
        for p in pieces:
            self.assertLess(len(p) // 3, 50 * 2)

    def test_mot_cau_dai_hon_nguong_van_thanh_mot_manh(self):
        # Không được rơi vào vòng lặp vô hạn hay cắt giữa từ.
        long_sentence = "x" * 5000
        self.assertEqual(split_long_text(long_sentence, 50), [long_sentence])

    def test_chuoi_rong(self):
        self.assertEqual(split_long_text("", 400), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_chunker.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.chunker'`

- [ ] **Step 3: Viết `chunker.py`**

```python
"""Chunking: cấu trúc trước, kích thước sau.

Ba bậc ranh giới:
  cứng  — zone đổi, hoặc gặp Phần/Chương/Mục/Điều. Luôn cắt.
  mềm   — '1.', 'a)'. Chỉ cắt khi đã chạm ngưỡng, nếu không một danh sách
          20 gạch đầu dòng sẽ thành 20 chunk tí hon làm loãng chỉ mục.
  cuối  — ranh giới câu, dùng khi một khối đơn lẻ dài quá ngưỡng.
"""

import re

from .header import build_embed_text
from .text import estimate_tokens
from .types import Chunk

TARGET_TOKENS = 400

# Bốn vùng thể thức này luôn đứng riêng một chunk: đây là thứ văn thư tra
# cứu trực tiếp ('ai ký?', 'gửi cho ai?'), nhấn chìm chúng vào một chunk
# nội dung 400 token là ném đi tín hiệu mạnh nhất.
STANDALONE_ZONES = ("so_ky_hieu", "trich_yeu", "noi_nhan", "chu_ky")

# \A neo đầu chuỗi — 'Căn cứ Điều 7' giữa câu không được tính là tiêu đề.
_HEADINGS = (
    (1, re.compile(r"\A\s*(PHẦN|Phần)\s+([IVXLC]+)\b")),
    (2, re.compile(r"\A\s*(CHƯƠNG|Chương)\s+([IVXLC]+)\b")),
    (3, re.compile(r"\A\s*(MỤC|Mục)\s+(\d+)\b")),
    (4, re.compile(r"\A\s*(Điều)\s+(\d+)\b")),
)

_SOFT = re.compile(r"\A\s*(?:\d+\.|[a-zđ]\))\s")

_SENT_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n+")


def detect_heading(text):
    """(bậc, nhãn) nếu đoạn mở đầu một mục cấu trúc, ngược lại None."""
    for level, pattern in _HEADINGS:
        m = pattern.match(text or "")
        if m:
            return level, f"{m.group(1)} {m.group(2)}"
    return None


def is_soft_boundary(text):
    """Đoạn mở đầu bằng '1.' hoặc 'a)' — chỗ ưu tiên cắt khi đã đủ dài."""
    return bool(_SOFT.match(text or ""))


def split_long_text(text, target_tokens, overlap_sentences=1):
    """Cắt một khối dài theo ranh giới câu, có chồng lấn."""
    if not text or not text.strip():
        return []
    if estimate_tokens(text) <= target_tokens:
        return [text]
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]
    if len(sentences) <= 1:
        return [text]                       # một câu dài hơn ngưỡng: để nguyên
    pieces, cur = [], []
    for s in sentences:
        cur.append(s)
        if estimate_tokens(" ".join(cur)) >= target_tokens:
            pieces.append(" ".join(cur))
            cur = cur[-overlap_sentences:] if overlap_sentences else []
    tail = " ".join(cur)
    if tail and (not pieces or tail != pieces[-1]):
        pieces.append(tail)
    return pieces


def chunk_blocks(blocks, meta, target_tokens=TARGET_TOKENS):
    """list[Block] -> list[Chunk], gán heading_path và embed_text."""
    out, stack, buf = [], {}, []

    def heading_path():
        return " › ".join(stack[k] for k in sorted(stack))

    def flush():
        nonlocal buf
        if not buf:
            return
        joined = "\n".join(b.text for b in buf).strip()
        if not joined:
            buf = []
            return
        first, path = buf[0], heading_path()
        for piece in split_long_text(joined, target_tokens):
            out.append(Chunk(
                seq=len(out),
                text=piece,
                embed_text=build_embed_text(meta, path, piece),
                heading_path=path,
                zone=first.zone,
                zone_confidence=first.zone_confidence,
                page=first.page,
                bbox=first.bbox,
                token_count=estimate_tokens(piece),
            ))
        buf = []

    for b in blocks:
        if not (b.text or "").strip():
            continue
        heading = detect_heading(b.text)
        zone_changed = bool(buf) and buf[-1].zone != b.zone
        standalone = b.zone in STANDALONE_ZONES or (bool(buf) and buf[0].zone in STANDALONE_ZONES)
        if heading or zone_changed or standalone:
            flush()
        if heading:
            level, label = heading
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = label
        buf.append(b)
        if estimate_tokens("\n".join(x.text for x in buf)) >= target_tokens:
            tail = buf[-1] if len(buf) > 1 and not is_soft_boundary(buf[-1].text) else None
            flush()
            if tail is not None:
                buf = [tail]                # chồng lấn một đoạn

    flush()
    return out
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_chunker.py -q`
Expected: PASS, 13 passed

- [ ] **Step 5: Thêm test cho `chunk_blocks` — ca biên là chỗ đáng tiền**

Nối vào cuối `test_chunker.py`:

```python
class TestChunkBlocks(unittest.TestCase):
    def test_tai_lieu_rong(self):
        self.assertEqual(chunk_blocks([], META), [])

    def test_bo_qua_doan_toan_khoang_trang(self):
        self.assertEqual(chunk_blocks([Block(text="   "), Block(text="\n")], META), [])

    def test_doi_zone_thi_cat(self):
        blocks = [
            Block(text="Về việc phối hợp công tác", zone="trich_yeu"),
            Block(text="Kính gửi các đơn vị.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].zone, "trich_yeu")
        self.assertEqual(chunks[1].zone, "noi_dung")

    def test_bon_vung_dac_biet_luon_dung_rieng(self):
        for zone in STANDALONE_ZONES:
            blocks = [
                Block(text="Đoạn nội dung một.", zone="noi_dung"),
                Block(text="Giá trị vùng đặc biệt.", zone=zone),
                Block(text="Đoạn nội dung hai.", zone="noi_dung"),
            ]
            chunks = chunk_blocks(blocks, META)
            self.assertEqual(len(chunks), 3, f"vùng {zone} bị gộp")
            self.assertEqual(chunks[1].zone, zone)

    def test_heading_path_long_nhau_dung_thu_tu(self):
        blocks = [
            Block(text="PHẦN II. MỤC TIÊU", zone="noi_dung"),
            Block(text="Mục 3. Tổ chức thực hiện", zone="noi_dung"),
            Block(text="Các sở, ban, ngành có trách nhiệm.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        self.assertEqual(chunks[-1].heading_path, "PHẦN II › Mục 3")

    def test_heading_bac_nong_hon_cat_nhanh_sau(self):
        blocks = [
            Block(text="PHẦN II", zone="noi_dung"),
            Block(text="Mục 3", zone="noi_dung"),
            Block(text="PHẦN III", zone="noi_dung"),
            Block(text="Nội dung phần ba.", zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META)
        # 'Mục 3' của PHẦN II không được dính sang PHẦN III.
        self.assertEqual(chunks[-1].heading_path, "PHẦN III")

    def test_dieu_dai_bi_cat_thanh_nhieu_chunk(self):
        long_text = " ".join(f"Nội dung câu thứ {i} của điều này." for i in range(200))
        blocks = [
            Block(text="Điều 7. Trách nhiệm", zone="noi_dung"),
            Block(text=long_text, zone="noi_dung"),
        ]
        chunks = chunk_blocks(blocks, META, target_tokens=100)
        self.assertGreater(len(chunks), 1)
        # Mọi mảnh đều giữ nguyên heading_path của Điều 7.
        for c in chunks:
            self.assertEqual(c.heading_path, "Điều 7")

    def test_dieu_ngan_duoc_gop(self):
        blocks = [
            Block(text="Điều 1. Phạm vi", zone="noi_dung"),
            Block(text="Quy định này áp dụng cho toàn tỉnh.", zone="noi_dung"),
        ]
        self.assertEqual(len(chunk_blocks(blocks, META)), 1)

    def test_danh_sach_gach_dau_dong_khong_bi_bam_vun(self):
        # Ranh giới mềm: 6 gạch đầu dòng ngắn phải nằm chung một chunk.
        blocks = [Block(text=f"{i}. Nhiệm vụ ngắn thứ {i}.", zone="noi_dung")
                  for i in range(1, 7)]
        self.assertEqual(len(chunk_blocks(blocks, META)), 1)

    def test_seq_lien_tuc_tu_khong(self):
        blocks = [Block(text=f"Đoạn {i} nội dung.", zone="noi_dung") for i in range(5)]
        chunks = chunk_blocks(blocks, META, target_tokens=5)
        self.assertEqual([c.seq for c in chunks], list(range(len(chunks))))

    def test_embed_text_co_header_con_text_thi_khong(self):
        blocks = [Block(text="Điều 7. Trách nhiệm", zone="noi_dung")]
        c = chunk_blocks(blocks, META)[0]
        self.assertIn("145/KH-UBND", c.embed_text)
        self.assertNotIn("145/KH-UBND", c.text)

    def test_giu_page_va_bbox_cua_khoi_dau(self):
        blocks = [Block(text="Đoạn có toạ độ.", zone="noi_dung", page=3, bbox=(1, 2, 3, 4))]
        c = chunk_blocks(blocks, META)[0]
        self.assertEqual((c.page, c.bbox), (3, (1, 2, 3, 4)))
```

- [ ] **Step 6: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_chunker.py -q`
Expected: PASS, 25 passed

Nếu `test_danh_sach_gach_dau_dong_khong_bi_bam_vun` fail thì logic ranh giới mềm đang bị coi là cứng — sửa `chunk_blocks`, **không** sửa test.

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_search_engine/chunker.py custom-addons/aidt_search_engine/tests/test_chunker.py
git commit -m "feat(search): add structure-aware chunker with three-tier boundaries"
```

---

## Task 7: Phân tích ý định truy vấn (`intent.py`)

Tra cứu số hiệu → SQL. Lọc thời gian/đơn vị → metadata. Phần còn lại → ngữ nghĩa. Trộn hết vào một đường semantic là sai lầm kinh điển.

Thư viện **không được biết** selection của Odoo, nên danh mục loại văn bản / đơn vị / độ khẩn được **truyền vào**.

**Files:**
- Create: `custom-addons/aidt_search_engine/intent.py`
- Test: `custom-addons/aidt_search_engine/tests/test_intent.py`

**Interfaces:**
- Consumes: `types.QueryFilter`, `types.ParsedQuery`, `text.strip_accents`, `text.normalize_ws`
- Produces: `parse_query(raw, doc_types=None, departments=None, urgencies=None) -> ParsedQuery`
  - `doc_types`: `list[tuple[str, str]]` — `[("cong_van", "Công văn"), ...]`
  - `departments`: `list[tuple[int, str]]` — `[(7, "Sở Tài chính"), ...]`
  - `urgencies`: `list[tuple[str, str]]` — `[("hoa_toc", "Hỏa tốc"), ...]`
  - hằng `REFERENCE_RE`

- [ ] **Step 1: Viết test thất bại**

```python
import datetime as dt
import unittest

from aidt_search_engine.intent import parse_query

DOC_TYPES = [("cong_van", "Công văn"), ("ke_hoach", "Kế hoạch"),
             ("quyet_dinh", "Quyết định"), ("bao_cao", "Báo cáo")]
DEPARTMENTS = [(7, "Sở Tài chính"), (9, "Sở Thông tin và Truyền thông"),
               (3, "Văn phòng")]
URGENCIES = [("hoa_toc", "Hỏa tốc"), ("thuong_khan", "Thượng khẩn"),
             ("khan", "Khẩn")]


def parse(raw):
    return parse_query(raw, DOC_TYPES, DEPARTMENTS, URGENCIES)


class TestReference(unittest.TestCase):
    def test_bat_so_hieu_day_du(self):
        self.assertEqual(parse("145/KH-UBND").reference, "145/KH-UBND")

    def test_bat_so_hieu_trong_cau(self):
        self.assertEqual(parse("cho tôi xem Số 185/CV-STTTT").reference, "185/CV-STTTT")

    def test_bat_so_hieu_nhieu_doan(self):
        self.assertEqual(parse("nghị quyết 12/NQ-TW-BCT").reference, "12/NQ-TW-BCT")

    def test_khong_co_so_hieu(self):
        self.assertIsNone(parse("các văn bản về hỗ trợ hộ nghèo").reference)

    def test_khong_bat_nham_ngay_thang(self):
        self.assertIsNone(parse("văn bản ngày 25/7/2026").reference)


class TestDateFilter(unittest.TestCase):
    def _date_filter(self, raw):
        return next((f for f in parse(raw).filters if f.field == "date"), None)

    def test_nam(self):
        f = self._date_filter("văn bản về hộ nghèo năm 2025")
        self.assertEqual(f.value, (dt.date(2025, 1, 1), dt.date(2025, 12, 31)))
        self.assertEqual(f.label, "Năm 2025")

    def test_quy(self):
        f = self._date_filter("báo cáo quý II năm 2026")
        self.assertEqual(f.value, (dt.date(2026, 4, 1), dt.date(2026, 6, 30)))

    def test_quy_cach_xa_nam_giu_nguyen_van_ban_o_giua(self):
        # 'quý II' và 'năm 2026' không liền nhau — nội dung ngữ nghĩa nằm
        # giữa hai mốc này không được bị bóc theo (không bắc cầu span).
        q = parse("kế hoạch quý II về hỗ trợ hộ nghèo năm 2026")
        f = next(f for f in q.filters if f.field == "date")
        self.assertEqual(f.value, (dt.date(2026, 4, 1), dt.date(2026, 6, 30)))
        self.assertIn("hỗ trợ hộ nghèo", q.semantic)
        self.assertNotIn("2026", q.semantic)

    def test_thang_co_nam(self):
        f = self._date_filter("công văn tháng 3/2026")
        self.assertEqual(f.value, (dt.date(2026, 3, 1), dt.date(2026, 3, 31)))

    def test_thang_12_tinh_dung_ngay_cuoi(self):
        f = self._date_filter("báo cáo tháng 12/2025")
        self.assertEqual(f.value, (dt.date(2025, 12, 1), dt.date(2025, 12, 31)))

    def test_khong_co_moc_thoi_gian(self):
        self.assertIsNone(self._date_filter("hỗ trợ hộ nghèo"))


class TestOtherFilters(unittest.TestCase):
    def _field(self, raw, field):
        return next((f for f in parse(raw).filters if f.field == field), None)

    def test_loai_van_ban(self):
        self.assertEqual(self._field("kế hoạch về an toàn thông tin", "doc_type").value,
                         "ke_hoach")

    def test_don_vi_khop_ten_dai_nhat(self):
        # 'Sở Thông tin và Truyền thông' phải thắng, không được khớp 'Sở Tài chính'
        # hay dừng ở một tiền tố ngắn hơn.
        f = self._field("công văn của Sở Thông tin và Truyền thông", "department_id")
        self.assertEqual(f.value, 9)

    def test_don_vi_khop_khong_dau(self):
        self.assertEqual(self._field("van ban cua So Tai chinh", "department_id").value, 7)

    def test_do_khan_uu_tien_cum_dai(self):
        self.assertEqual(self._field("văn bản thượng khẩn", "do_khan").value, "thuong_khan")

    def test_do_khan_don(self):
        self.assertEqual(self._field("công văn khẩn", "do_khan").value, "khan")

    def test_don_vi_giua_quy_va_nam_khong_cat_giua_tu(self):
        # Span 'quý II' và span 'năm 2026' rời nhau, nhưng span đơn vị nằm
        # LỒNG GIỮA hai mốc đó — vòng lặp xoá text phải gộp span chồng lấn
        # trước khi xoá, nếu không sẽ lệch offset và cắt nham nhở giữa từ.
        q = parse("báo cáo quý II của Sở Tài chính năm 2026")
        self.assertEqual(self._field("báo cáo quý II của Sở Tài chính năm 2026",
                                      "department_id").value, 7)
        self.assertEqual(q.semantic, "của")

    def test_khan_cap_khong_bi_hieu_nham_la_nhan_do_khan(self):
        # 'khẩn cấp' là tính từ thường ('urgent/emergency'), không phải nhãn
        # độ khẩn 'Khẩn' — dù khớp đúng ranh giới từ, đây vẫn là khớp sai nghĩa.
        q = parse("công văn khẩn cấp về phòng chống bão")
        self.assertIsNone(self._field("công văn khẩn cấp về phòng chống bão", "do_khan"))
        self.assertIn("khẩn cấp", q.semantic)
        self.assertIn("phòng chống bão", q.semantic)


class TestSemanticRemainder(unittest.TestCase):
    def test_boc_filter_ra_khoi_chuoi_ngu_nghia(self):
        q = parse("các văn bản về hỗ trợ hộ nghèo năm 2025")
        self.assertNotIn("2025", q.semantic)
        self.assertIn("hỗ trợ hộ nghèo", q.semantic)

    def test_khong_boc_thi_giu_nguyen(self):
        q = parse("hỗ trợ hộ nghèo")
        self.assertEqual(q.semantic, "hỗ trợ hộ nghèo")
        self.assertEqual(q.filters, [])

    def test_raw_luon_duoc_giu(self):
        raw = "báo cáo quý II năm 2026 của Sở Tài chính"
        self.assertEqual(parse(raw).raw, raw)

    def test_truy_van_chi_co_so_hieu_thi_semantic_rong(self):
        self.assertEqual(parse("145/KH-UBND").semantic, "")

    def test_chuoi_rong(self):
        q = parse("")
        self.assertEqual((q.semantic, q.reference, q.filters), ("", None, []))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_intent.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.intent'`

- [ ] **Step 3: Viết `intent.py`**

```python
"""Định tuyến ý định truy vấn.

Bóc số hiệu và các filter cứng (thời gian, đơn vị, loại, độ khẩn) ra khỏi
câu hỏi; phần còn lại mới đem đi tìm ngữ nghĩa. 'Các văn bản về hỗ trợ hộ
nghèo năm 2025' phải thành filter date=2025 CỘNG truy vấn 'hỗ trợ hộ nghèo'
— ném cả câu vào embedding thì 'năm 2025' trở thành nhiễu ngữ nghĩa.

Danh mục (loại văn bản, đơn vị, độ khẩn) được truyền vào chứ không hardcode:
thư viện này không được biết gì về selection của Odoo.
"""

import calendar
import datetime as dt
import re

from .text import normalize_ws, strip_accents
from .types import ParsedQuery, QueryFilter

# Số hiệu: '145/KH-UBND', '12/NQ-TW-BCT'. Phần sau '/' phải là chữ IN HOA
# nên '25/7/2026' không lọt.
REFERENCE_RE = re.compile(r"\b(\d+\s*/\s*[A-ZĐ]{2,}(?:[-–][A-ZĐ]+)*)\b")

_YEAR_RE = re.compile(r"\bnăm\s+(\d{4})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bquý\s+(I{1,3}V?|IV)\b(?:\s*(?:năm|/)?\s*(\d{4}))?", re.IGNORECASE)
_MONTH_RE = re.compile(r"\btháng\s+(\d{1,2})\s*[/-]\s*(\d{4})\b", re.IGNORECASE)

_QUARTER_MONTHS = {"I": (1, 3), "II": (4, 6), "III": (7, 9), "IV": (10, 12)}


def _month_range(year, first_month, last_month):
    last_day = calendar.monthrange(year, last_month)[1]
    return dt.date(year, first_month, 1), dt.date(year, last_month, last_day)


# Nhãn danh mục "nuốt nhầm" vào một từ/cụm từ tiếng Việt thông thường khác
# nghĩa — vd. nhãn độ khẩn 'Khẩn' khớp đúng ranh giới từ bên trong 'khẩn cấp'
# (tính từ thường, không phải nhãn "Khẩn"). Ranh giới từ không phân biệt được
# vì cả hai đều có khoảng trắng ngăn cách; đây là danh sách chắp vá (ad-hoc)
# các âm tiết nối tiếp biết trước sẽ đổi nghĩa, không phải quy tắc ngôn ngữ
# tổng quát. Khoá là nhãn đã bỏ dấu + thường hoá.
_FALSE_FRIEND_CONTINUATIONS = {
    "khan": {"cap"},  # 'khẩn cấp' — tính từ, không phải nhãn độ khẩn
}


def _next_token(haystack_folded, pos):
    """Âm tiết liền sau vị trí `pos` (đã bỏ dấu + thường hoá), dùng để phát
    hiện các cụm bị nuốt nhầm kiểu 'khẩn cấp'."""
    m = re.match(r"\s*([a-z0-9]+)", haystack_folded[pos:])
    return m.group(1) if m else ""


def _find_ci(haystack_folded, needle):
    """Vị trí của `needle` trong chuỗi đã bỏ dấu + thường hoá, khớp trên
    ranh giới từ (không khớp vào giữa một từ khác); -1 nếu không có khớp
    hợp lệ.

    Khớp đúng ranh giới từ vẫn có thể sai nghĩa — xem `_FALSE_FRIEND_CONTINUATIONS`.
    """
    needle_folded = strip_accents(needle).lower()
    poison = _FALSE_FRIEND_CONTINUATIONS.get(needle_folded, ())
    pattern = re.compile(r"(?<![a-z0-9])" + re.escape(needle_folded) + r"(?![a-z0-9])")
    for m in pattern.finditer(haystack_folded):
        if _next_token(haystack_folded, m.end()) in poison:
            continue
        return m.start()
    return -1


def _extract_date(raw, spans):
    m = _MONTH_RE.search(raw)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            spans.append(m.span())
            return QueryFilter("date", "between", _month_range(year, month, month),
                               f"Tháng {month}/{year}", m.span())
    m = _QUARTER_RE.search(raw)
    if m:
        roman = m.group(1).upper()
        if roman in _QUARTER_MONTHS:
            own_year = m.group(2)
            quarter_span = m.span()
            year_span = None
            if own_year:
                year = int(own_year)
            else:
                year_m = _YEAR_RE.search(raw)
                year = int(year_m.group(1)) if year_m else None
                year_span = year_m.span() if year_m else None
            if year:
                first, last = _QUARTER_MONTHS[roman]
                # Quý và năm được bóc thành hai span RỜI NHAU thay vì một span
                # bắc cầu — nếu không, mọi nội dung ngữ nghĩa nằm giữa hai mốc
                # này (vd. tên đơn vị, mô tả) sẽ bị xoá theo.
                spans.append(quarter_span)
                if year_span:
                    spans.append(year_span)
                overall_span = (quarter_span[0],
                                 year_span[1] if year_span else quarter_span[1])
                return QueryFilter("date", "between", _month_range(year, first, last),
                                   f"Quý {roman}/{year}", overall_span)
    m = _YEAR_RE.search(raw)
    if m:
        year = int(m.group(1))
        spans.append(m.span())
        return QueryFilter("date", "between",
                           (dt.date(year, 1, 1), dt.date(year, 12, 31)),
                           f"Năm {year}", m.span())
    return None


def _extract_by_catalog(raw, folded, catalog, field, spans):
    """Khớp nhãn dài nhất trước — 'Thượng khẩn' phải thắng 'Khẩn', và
    'Sở Thông tin và Truyền thông' không được dừng ở một tiền tố ngắn hơn."""
    best = None
    for key, label in sorted(catalog or [], key=lambda kv: -len(kv[1])):
        pos = _find_ci(folded, label)
        if pos >= 0:
            best = QueryFilter(field, "=", key, label, (pos, pos + len(label)))
            break
    if best:
        spans.append(best.span)
    return best


def _merge_spans(spans):
    """Gộp các khoảng chồng lấn/liền kề thành các khoảng rời nhau.

    Các extractor có thể sinh ra span lồng nhau hoặc đè lên nhau (vd. span
    ngày tháng và span đơn vị nằm giữa nó). Vòng lặp xoá text ở `parse_query`
    chỉ đúng khi các span rời nhau — gộp trước để không lệch offset và cắt
    nhầm giữa từ, bất kể extractor phía trên có tự đảm bảo rời nhau hay không.
    """
    if not spans:
        return []
    ordered = sorted(tuple(s) for s in spans)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [tuple(s) for s in merged]


def parse_query(raw, doc_types=None, departments=None, urgencies=None):
    raw = raw or ""
    if not raw.strip():
        return ParsedQuery(raw=raw, semantic="", reference=None, filters=[])

    folded = strip_accents(raw).lower()
    spans, filters = [], []

    ref_match = REFERENCE_RE.search(raw)
    reference = None
    if ref_match:
        reference = normalize_ws(ref_match.group(1)).replace(" ", "")
        spans.append(ref_match.span())

    for extracted in (
        _extract_date(raw, spans),
        _extract_by_catalog(raw, folded, doc_types, "doc_type", spans),
        _extract_by_catalog(raw, folded, departments, "department_id", spans),
        _extract_by_catalog(raw, folded, urgencies, "do_khan", spans),
    ):
        if extracted:
            filters.append(extracted)

    remainder = raw
    for start, end in sorted(_merge_spans(spans), key=lambda s: -s[0]):
        remainder = remainder[:start] + " " + remainder[end:]

    return ParsedQuery(raw=raw, semantic=normalize_ws(remainder),
                       reference=reference, filters=filters)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_intent.py -q`
Expected: PASS, 23 passed

`test_boc_filter_ra_khoi_chuoi_ngu_nghia` còn kiểm cả việc chuỗi ngữ nghĩa **giữ được** "hỗ trợ hộ nghèo" — bóc quá tay cũng là lỗi, không chỉ bóc thiếu.

- [ ] **Step 5: Chạy toàn bộ test thư viện**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests -q`
Expected: PASS, 73 passed

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_search_engine/intent.py custom-addons/aidt_search_engine/tests/test_intent.py
git commit -m "feat(search): add query intent parser for reference and hard filters"
```

---

## Task 8: Hợp nhất RRF và khe cắm reranker

**Files:**
- Create: `custom-addons/aidt_search_engine/fusion.py`
- Create: `custom-addons/aidt_search_engine/rerank.py`
- Test: `custom-addons/aidt_search_engine/tests/test_fusion.py`

**Interfaces:**
- Produces: `reciprocal_rank_fusion(channels, k=60) -> list[tuple[object, float]]`; `rerank(query, candidates) -> list`; hằng `RRF_K = 60`

- [ ] **Step 1: Viết test thất bại**

```python
import unittest

from aidt_search_engine.fusion import RRF_K, reciprocal_rank_fusion
from aidt_search_engine.rerank import rerank


class TestRRF(unittest.TestCase):
    def test_khong_co_kenh_nao(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    def test_kenh_rong_khong_lam_do(self):
        self.assertEqual(reciprocal_rank_fusion([[], []]), [])

    def test_mot_kenh_giu_nguyen_thu_tu(self):
        out = reciprocal_rank_fusion([["a", "b", "c"]])
        self.assertEqual([i for i, _ in out], ["a", "b", "c"])

    def test_item_xuat_hien_nhieu_kenh_duoc_cong_diem(self):
        out = dict(reciprocal_rank_fusion([["a", "b"], ["a", "c"]]))
        self.assertAlmostEqual(out["a"], 2 / (RRF_K + 1))
        self.assertAlmostEqual(out["b"], 1 / (RRF_K + 2))

    def test_dong_thuan_thang_hang_cao_don_le(self):
        # 'b' đứng nhất ở một kênh, 'a' đứng nhì ở cả ba kênh -> 'a' thắng.
        out = reciprocal_rank_fusion([["b", "a"], ["c", "a"], ["d", "a"]])
        self.assertEqual(out[0][0], "a")

    def test_them_kenh_rac_khong_truat_ngoi_item_dong_thuan(self):
        # Tính chất quan trọng nhất: RRF phải chịu được một kênh kém.
        # Đây là cái cho phép bật/tắt kênh ts_seg và giảm cấp mềm mà an toàn.
        clean = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
        self.assertEqual(reciprocal_rank_fusion(clean)[0][0], "a")
        noisy = clean + [["z", "y", "x"]]
        self.assertEqual(reciprocal_rank_fusion(noisy)[0][0], "a")

    def test_ket_qua_on_dinh_khi_diem_bang_nhau(self):
        # Điểm bằng nhau phải phá hoà tất định, nếu không thứ tự kết quả
        # nhảy giữa hai lần chạy giống hệt.
        a = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
        b = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
        self.assertEqual(a, b)

    def test_k_lon_lam_phang_chenh_lech(self):
        gap_small_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
        gap_large_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
        self.assertGreater(gap_small_k["a"] - gap_small_k["b"],
                           gap_large_k["a"] - gap_large_k["b"])


class TestRerankSeam(unittest.TestCase):
    def test_v1_tra_nguyen_danh_sach(self):
        items = [("a", 0.9), ("b", 0.5)]
        self.assertEqual(rerank("truy vấn bất kỳ", items), items)

    def test_danh_sach_rong(self):
        self.assertEqual(rerank("q", []), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_fusion.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.fusion'`

- [ ] **Step 3: Viết `fusion.py` và `rerank.py`**

`fusion.py`:

```python
"""Reciprocal Rank Fusion.

Hợp nhất N danh sách đã xếp hạng mà không cần chuẩn hoá thang điểm giữa
chúng — cosine và ts_rank_cd không cùng đơn vị, so trực tiếp là vô nghĩa.
RRF chỉ nhìn THỨ HẠNG nên tránh được hẳn vấn đề đó, và không có tham số
nào phải tinh chỉnh ngoài k.

Nhận số kênh bất kỳ: thêm/bớt kênh (ts_seg bật lên, kênh vector chết) không
phải sửa hàm này.
"""

RRF_K = 60


def reciprocal_rank_fusion(channels, k=RRF_K):
    """channels: list các danh sách id đã xếp hạng (tốt nhất đứng đầu).

    Trả list[(id, score)] giảm dần theo điểm. Điểm bằng nhau phá hoà theo
    repr(id) để kết quả tất định giữa các lần chạy.
    """
    scores = {}
    for ranked in channels or []:
        for rank, item in enumerate(ranked or [], start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], repr(kv[0])))
```

`rerank.py`:

```python
"""Khe cắm reranker — chưa bật ở v1.

Cross-encoder chỉ tỏa sáng khi tập ứng viên lớn và nhiễu. Ở quy mô vài trăm
văn bản, RRF cộng contextual header đã gần chạm trần, trong khi model tốn
thêm ~1.2GB VRAM và ~300ms mỗi truy vấn.

Điều kiện bật: bộ eval của dự án con D cho thấy nDCG@10 của RRF thuần thấp
hơn ngưỡng. Khi đó chỉ thay thân hàm — chỗ gọi không đổi.
"""


def rerank(query, candidates):
    """v1: giữ nguyên thứ tự RRF."""
    return candidates
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_fusion.py -q`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_search_engine/fusion.py custom-addons/aidt_search_engine/rerank.py custom-addons/aidt_search_engine/tests/test_fusion.py
git commit -m "feat(search): add RRF fusion and reranker seam"
```

---

## Task 9: Bộ nhận vùng cho nhánh OCR (`extract/zone_adapter.py`)

**Đọc `docs/superpowers/plans/2026-08-01-spike-findings.md` trước khi bắt đầu.** Task 1 đã quyết cách làm; ba kết cục dẫn tới ba cách viết khác nhau. Dưới đây là đường đi cho kết cục "tái sử dụng được" — nếu findings nói khác, làm theo findings và **vẫn không sửa `aidt_format_engine`**.

**Files:**
- Create: `custom-addons/aidt_search_engine/extract/__init__.py`
- Create: `custom-addons/aidt_search_engine/extract/zone_adapter.py`
- Test: `custom-addons/aidt_search_engine/tests/test_zone_adapter.py`

**Interfaces:**
- Consumes: `_compat.fe_types`, `_compat.fe_zones`, `types.Block`
- Produces: `assign_zones(blocks, page_width) -> list[Block]` — trả **danh sách mới**, gán `zone` và `zone_confidence='heuristic'`; `align_from_bbox(bbox, page_width) -> str`

- [ ] **Step 1: Viết test thất bại**

```python
import unittest

from aidt_search_engine.extract.zone_adapter import align_from_bbox, assign_zones
from aidt_search_engine.types import Block

W = 1000.0


class TestAlignFromBbox(unittest.TestCase):
    def test_giua_trang(self):
        self.assertEqual(align_from_bbox((300, 0, 700, 20), W), "center")

    def test_sat_trai(self):
        self.assertEqual(align_from_bbox((20, 0, 300, 20), W), "left")

    def test_sat_phai(self):
        self.assertEqual(align_from_bbox((700, 0, 980, 20), W), "right")

    def test_trai_dai_het_dong_la_justify(self):
        self.assertEqual(align_from_bbox((20, 0, 980, 20), W), "justify")

    def test_khong_co_bbox(self):
        self.assertIsNone(align_from_bbox(None, W))

    def test_khong_biet_chieu_rong(self):
        self.assertIsNone(align_from_bbox((300, 0, 700, 20), 0))


class TestAssignZones(unittest.TestCase):
    def _ocr_page(self):
        return [
            Block(text="ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG", bbox=(300, 60, 700, 85), page=1),
            Block(text="CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", bbox=(300, 95, 760, 120), page=1),
            Block(text="Độc lập - Tự do - Hạnh phúc", bbox=(360, 125, 700, 145), page=1),
            Block(text="Số: 145/KH-UBND", bbox=(60, 160, 300, 180), page=1),
            Block(text="Bình Dương, ngày 25 tháng 7 năm 2026", bbox=(560, 160, 950, 180), page=1),
            Block(text="KẾ HOẠCH", bbox=(430, 210, 570, 235), page=1),
            Block(text="Căn cứ Luật An toàn thông tin mạng năm 2015;", bbox=(60, 280, 940, 300), page=1),
            Block(text="Nơi nhận:", bbox=(60, 700, 200, 720), page=1),
            Block(text="Nguyễn Văn A", bbox=(700, 800, 940, 820), page=1),
        ]

    def test_khong_nem_loi_khi_thieu_thuoc_tinh_docx(self):
        # Đây là R1: detect_zones vốn viết cho Para có fmt đầy đủ.
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(len(blocks), 9)

    def test_gan_zone_cho_moi_khoi(self):
        for b in assign_zones(self._ocr_page(), W):
            self.assertIsNotNone(b.zone)

    def test_nhan_dien_so_ky_hieu(self):
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(blocks[3].zone, "so_ky_hieu")

    def test_nhan_dien_noi_nhan(self):
        blocks = assign_zones(self._ocr_page(), W)
        self.assertEqual(blocks[7].zone, "noi_nhan")

    def test_do_tin_cay_luon_la_heuristic(self):
        # Nhánh OCR không có style đặt tên nên không bao giờ đạt 'style'.
        for b in assign_zones(self._ocr_page(), W):
            self.assertEqual(b.zone_confidence, "heuristic")

    def test_khong_sua_danh_sach_goc(self):
        original = self._ocr_page()
        assign_zones(original, W)
        self.assertTrue(all(b.zone is None for b in original))

    def test_danh_sach_rong(self):
        self.assertEqual(assign_zones([], W), [])

    def test_giu_nguyen_page_va_bbox(self):
        out = assign_zones(self._ocr_page(), W)
        self.assertEqual(out[3].page, 1)
        self.assertEqual(out[3].bbox, (60, 160, 300, 180))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_zone_adapter.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.extract'`

- [ ] **Step 3: Viết `extract/__init__.py` (rỗng) và `extract/zone_adapter.py`**

```python
"""Gán vùng thể thức cho khối OCR bằng chính bộ nhận vùng của aidt_format_engine.

Heuristic của zones.py là regex + vị trí ('Số: 145/KH-UBND', 'Nơi nhận:',
kiểm tra in hoa) — chạy trên text thuần được, không cần biết text đến từ
DOCX hay từ ảnh scan. Ta dựng Para giả từ Block, suy align từ tâm bbox, rồi
gọi detect_zones. Một bộ luật, hai nguồn đầu vào.

Nhánh OCR không có style đặt tên nên luôn dừng ở zone_confidence='heuristic';
nhánh DOCX vẫn đạt 'style' và chính xác 100% khi văn bản soạn từ template.
"""

import dataclasses

from .._compat import fe_types, fe_zones

# Ngưỡng theo tỷ lệ chiều rộng trang, không theo pixel tuyệt đối: ảnh scan
# 150dpi và 300dpi phải cho cùng kết quả.
_EDGE = 0.12          # coi là sát mép khi cách mép dưới 12% chiều rộng
_CENTER_TOL = 0.06    # lệch tâm dưới 6% thì coi là căn giữa
_FULL_WIDTH = 0.80    # phủ trên 80% chiều rộng thì coi là justify


def align_from_bbox(bbox, page_width):
    """left | center | right | justify, suy từ vị trí ngang của khối."""
    if not bbox or not page_width:
        return None
    x0, _, x1, _ = bbox
    left_gap, right_gap = x0 / page_width, (page_width - x1) / page_width
    if (x1 - x0) / page_width >= _FULL_WIDTH:
        return "justify"
    if abs(left_gap - right_gap) <= _CENTER_TOL:
        return "center"
    if right_gap <= _EDGE < left_gap:
        return "right"
    return "left"


def assign_zones(blocks, page_width):
    """Trả danh sách Block MỚI đã gán zone. Không đụng vào danh sách gốc."""
    if not blocks:
        return []
    paras = [
        fe_types.Para(
            index=i,
            text=b.text,
            style_name=None,
            fmt=fe_types.EffFormat(align=align_from_bbox(b.bbox, page_width)),
        )
        for i, b in enumerate(blocks)
    ]
    doc = fe_types.IntermediateDoc(
        pages=fe_types.PageSetup(width_mm=210.0, height_mm=297.0, margin_mm={}),
        paras=paras,
    )
    fe_zones.detect_zones(doc)
    return [
        dataclasses.replace(b, zone=p.zone or "noi_dung", zone_confidence="heuristic")
        for b, p in zip(blocks, doc.paras)
    ]
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_zone_adapter.py -q`
Expected: PASS, 14 passed

Nếu `detect_zones` ném lỗi vì `fmt` thiếu thuộc tính (kết cục 3 của Task 1), **không sửa `aidt_format_engine`**: điền thêm trường vào `EffFormat` khi dựng (`bold=None, size_pt=None, ...`) cho đủ, hoặc theo đúng quyết định đã ghi trong findings.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_search_engine/extract custom-addons/aidt_search_engine/tests/test_zone_adapter.py
git commit -m "feat(search): reuse format engine zone detection for OCR blocks"
```

---

## Task 10: Trích xuất DOCX và PDF (`extract/docx.py`, `extract/pdf.py`)

**Files:**
- Create: `custom-addons/aidt_search_engine/extract/docx.py`
- Create: `custom-addons/aidt_search_engine/extract/pdf.py`
- Test: `custom-addons/aidt_search_engine/tests/test_extract_docx.py`
- Test: `custom-addons/aidt_search_engine/tests/test_extract_pdf.py`

**Interfaces:**
- Consumes: `_compat.fe_parser`, `_compat.fe_zones`, `types.Block`
- Produces:
  - `docx.extract_docx(blob) -> list[Block]` — ném `UnreadableDocx` khi tệp hỏng
  - `pdf.page_count(path) -> int`
  - `pdf.page_text(path, page) -> str`
  - `pdf.render_page_png(path, page, dpi=150) -> bytes`
  - `pdf.PdfToolError` — lỗi khi poppler không chạy được
  - hằng `pdf.DEFAULT_DPI = 150`

- [ ] **Step 1: Viết test thất bại cho nhánh DOCX**

```python
import io
import unittest

import docx

from aidt_search_engine.extract.docx import extract_docx


def _build(lines):
    d = docx.Document()
    for text in lines:
        d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class TestExtractDocx(unittest.TestCase):
    def test_tra_ve_block_cho_moi_doan_co_chu(self):
        blob = _build(["ĐẢNG CỘNG SẢN VIỆT NAM", "Số: 145-KH/TU", "Nội dung."])
        blocks = extract_docx(blob)
        self.assertEqual([b.text for b in blocks],
                         ["ĐẢNG CỘNG SẢN VIỆT NAM", "Số: 145-KH/TU", "Nội dung."])

    def test_bo_qua_doan_rong(self):
        self.assertEqual(len(extract_docx(_build(["Có chữ.", "", "   "]))), 1)

    def test_co_gan_zone(self):
        blocks = extract_docx(_build(["Số: 145-KH/TU", "Nơi nhận:"]))
        self.assertTrue(all(b.zone for b in blocks))

    def test_docx_khong_co_bbox_va_page(self):
        # DOCX không có toạ độ; highlight cho nhánh này dựa vào ts_headline.
        for b in extract_docx(_build(["Nội dung."])):
            self.assertIsNone(b.bbox)
            self.assertIsNone(b.page)

    def test_tep_hong_nem_loi(self):
        from aidt_search_engine.extract.docx import UnreadableDocx
        with self.assertRaises(UnreadableDocx):
            extract_docx(b"khong phai docx")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_docx.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.extract.docx'`

- [ ] **Step 3: Viết `extract/docx.py`**

```python
"""Nhánh DOCX: dùng thẳng parser + zone detector của aidt_format_engine.

Đây là lý do không cần `unstructured`: aidt_format_engine đã tách đúng 12
vùng thể thức văn bản Đảng / NĐ-30, chính xác hơn hẳn một parser tổng quát.
Văn bản soạn từ template hệ thống còn có style đặt tên nên đạt
zone_confidence='style' — chính xác 100%.
"""

from .._compat import fe_parser, fe_zones
from ..types import Block

UnreadableDocx = fe_parser.UnreadableDocx


def extract_docx(blob):
    """bytes DOCX -> list[Block]. Ném UnreadableDocx nếu tệp hỏng."""
    doc = fe_parser.parse_docx(blob)
    fe_zones.detect_zones(doc)
    return [
        Block(
            text=p.text,
            zone=p.zone or "noi_dung",
            zone_confidence=p.zone_confidence,
        )
        for p in doc.paras
        if (p.text or "").strip()
    ]
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_docx.py -q`
Expected: PASS, 5 passed

- [ ] **Step 5: Viết test thất bại cho nhánh PDF**

```python
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidt_search_engine.extract.pdf import (
    DEFAULT_DPI,
    PdfToolError,
    page_count,
    page_text,
    render_page_png,
)

HAS_POPPLER = all(shutil.which(t) for t in ("pdfinfo", "pdftotext", "pdftoppm"))


def _make_pdf(path, pages_text):
    """Dựng PDF nhiều trang bằng LibreOffice nếu có, không thì bỏ qua test."""
    src = path.with_suffix(".txt")
    src.write_text("\f".join(pages_text), encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(path.parent), str(src)],
        check=True, capture_output=True, timeout=120,
    )
    return src.with_suffix(".pdf")


@unittest.skipUnless(HAS_POPPLER, "cần poppler-utils")
@unittest.skipUnless(shutil.which("soffice"), "cần libreoffice để dựng PDF mẫu")
class TestPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = _make_pdf(Path(cls.tmp.name) / "mau.txt",
                            ["Trang một hỗ trợ hộ nghèo", "Trang hai an toàn thông tin"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_dem_so_trang(self):
        self.assertEqual(page_count(str(self.pdf)), 2)

    def test_doc_text_dung_trang(self):
        self.assertIn("hộ nghèo", page_text(str(self.pdf), 1))
        self.assertNotIn("hộ nghèo", page_text(str(self.pdf), 2))

    def test_render_ra_png(self):
        data = render_page_png(str(self.pdf), 1, dpi=DEFAULT_DPI)
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertGreater(len(data), 1000)


class TestPdfErrors(unittest.TestCase):
    def test_tep_khong_ton_tai_nem_pdftoolerror(self):
        with self.assertRaises(PdfToolError):
            page_count("/khong/co/tep.pdf")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_pdf.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.extract.pdf'`

- [ ] **Step 7: Viết `extract/pdf.py`**

```python
"""Nhánh PDF: bọc poppler-utils.

Dùng CLI thay vì thư viện Python có chủ ý. PyMuPDF là AGPL-3, không dùng
được cho module LGPL-3. Và ta đã cần pdftoppm để rasterize trang scan, nên
lấy luôn pdftotext/pdfinfo cùng gói là không tốn thêm dependency nào.
"""

import re
import subprocess

DEFAULT_DPI = 150
_TIMEOUT = 120
_PAGES_RE = re.compile(r"^Pages:\s+(\d+)", re.MULTILINE)


class PdfToolError(RuntimeError):
    """poppler không chạy được, hoặc tệp không đọc được."""


def _run(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True,
                              timeout=_TIMEOUT, **kwargs)
    except FileNotFoundError as exc:
        raise PdfToolError(f"thiếu poppler-utils: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfToolError(f"{args[0]} quá thời gian") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
        raise PdfToolError(f"{args[0]} lỗi: {detail}") from exc


def page_count(path):
    out = _run(["pdfinfo", path]).stdout.decode("utf-8", "replace")
    m = _PAGES_RE.search(out)
    if not m:
        raise PdfToolError("pdfinfo không trả về số trang")
    return int(m.group(1))


def page_text(path, page):
    """Text của một trang. -layout giữ cột và khoảng cách, giúp nhận vùng."""
    out = _run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), path, "-"])
    return out.stdout.decode("utf-8", "replace")


def render_page_png(path, page, dpi=DEFAULT_DPI):
    """Rasterize một trang thành PNG để đưa vào OCR."""
    out = _run(["pdftoppm", "-png", "-r", str(dpi),
                "-f", str(page), "-l", str(page), path])
    if not out.stdout.startswith(b"\x89PNG"):
        raise PdfToolError(f"pdftoppm không trả về PNG cho trang {page}")
    return out.stdout
```

- [ ] **Step 8: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_pdf.py -q`
Expected: PASS (hoặc SKIPPED nếu máy không có poppler/libreoffice — nhưng `test_tep_khong_ton_tai_nem_pdftoolerror` phải luôn chạy và xanh)

- [ ] **Step 9: Commit**

```bash
git add custom-addons/aidt_search_engine/extract custom-addons/aidt_search_engine/tests/test_extract_docx.py custom-addons/aidt_search_engine/tests/test_extract_pdf.py
git commit -m "feat(search): add DOCX and PDF content extractors"
```

---

## Task 11: Client OCR (`extract/ocr.py`)

**Files:**
- Create: `custom-addons/aidt_search_engine/extract/ocr.py`
- Test: `custom-addons/aidt_search_engine/tests/test_extract_ocr.py`

**Interfaces:**
- Consumes: `types.Block`
- Produces:
  - `parse_ocr_output(raw) -> list[Block]`
  - `ocr_image(png_bytes, base_url, model="baidu/Unlimited-OCR", window_size=1024, timeout=180, transport=None) -> list[Block]`
  - `OcrError`, `OcrEmptyOutput`
  - hằng `PROMPT = "<image>document parsing."`, `NGRAM_SIZE = 35`, `WINDOW_IMAGE = 128`, `WINDOW_PDF = 1024`

- [ ] **Step 1: Viết test thất bại**

```python
import json
import unittest

from aidt_search_engine.extract.ocr import (
    NGRAM_SIZE,
    PROMPT,
    OcrEmptyOutput,
    OcrError,
    ocr_image,
    parse_ocr_output,
)

SAMPLE = (
    "<|det|>title [324, 72, 744, 93]<|/det|>ỦY BAN NHÂN DÂN TỈNH BÌNH DƯƠNG\n"
    "<|det|>title [304, 105, 766, 126]<|/det|>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
    "<|det|>text [60, 160, 300, 180]<|/det|>Số: 145/KH-UBND\n"
)


class TestParseOcrOutput(unittest.TestCase):
    def test_tach_dung_so_khoi(self):
        self.assertEqual(len(parse_ocr_output(SAMPLE)), 3)

    def test_lay_dung_text(self):
        self.assertEqual(parse_ocr_output(SAMPLE)[2].text, "Số: 145/KH-UBND")

    def test_lay_dung_bbox(self):
        self.assertEqual(parse_ocr_output(SAMPLE)[2].bbox, (60.0, 160.0, 300.0, 180.0))

    def test_dong_khong_co_the_det_van_thanh_block(self):
        # Model đôi khi trả dòng trần; mất chữ còn tệ hơn mất toạ độ.
        blocks = parse_ocr_output("Một dòng không có thẻ\n" + SAMPLE)
        self.assertEqual(blocks[0].text, "Một dòng không có thẻ")
        self.assertIsNone(blocks[0].bbox)

    def test_bo_qua_dong_rong(self):
        self.assertEqual(len(parse_ocr_output("\n\n" + SAMPLE + "\n\n")), 3)

    def test_chuoi_rong_tra_danh_sach_rong(self):
        self.assertEqual(parse_ocr_output(""), [])


class FakeTransport:
    """Bắt lại request body để kiểm công thức gọi, trả nội dung dựng sẵn."""

    def __init__(self, content=SAMPLE, exc=None):
        self.content, self.exc, self.body = content, exc, None

    def __call__(self, url, body, timeout):
        if self.exc:
            raise self.exc
        self.body = body
        return {"choices": [{"message": {"content": self.content}}]}


class TestOcrImage(unittest.TestCase):
    def test_tra_ve_block(self):
        self.assertEqual(len(ocr_image(b"\x89PNG...", "http://x/v1",
                                       transport=FakeTransport())), 3)

    def test_prompt_phai_bat_dau_bang_the_image(self):
        # Thiếu '<image>' thì model trả rỗng — đây là lỗi cấu hình im lặng
        # đã gặp thật, phải khoá bằng test.
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        texts = [c for c in t.body["messages"][0]["content"] if c["type"] == "text"]
        self.assertEqual(texts[0]["text"], PROMPT)
        self.assertTrue(texts[0]["text"].startswith("<image>"))

    def test_skip_special_tokens_phai_la_false(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        self.assertIs(t.body["skip_special_tokens"], False)

    def test_vllm_xargs_dung_cong_thuc(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", window_size=1024, transport=t)
        self.assertEqual(t.body["vllm_xargs"],
                         {"ngram_size": NGRAM_SIZE, "window_size": 1024})

    def test_anh_duoc_gui_dang_data_uri(self):
        t = FakeTransport()
        ocr_image(b"png", "http://x/v1", transport=t)
        images = [c for c in t.body["messages"][0]["content"] if c["type"] == "image_url"]
        self.assertTrue(images[0]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_ket_qua_rong_nem_ocrempty(self):
        # Trang trắng và lỗi cấu hình trông giống hệt nhau ở đây; tầng trên
        # phân biệt bằng cách kiểm ảnh có phải trang trắng không.
        with self.assertRaises(OcrEmptyOutput):
            ocr_image(b"png", "http://x/v1", transport=FakeTransport(content="   "))

    def test_loi_mang_nem_ocrerror(self):
        with self.assertRaises(OcrError):
            ocr_image(b"png", "http://x/v1",
                      transport=FakeTransport(exc=TimeoutError("hết giờ")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_ocr.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aidt_search_engine.extract.ocr'`

- [ ] **Step 3: Viết `extract/ocr.py`**

```python
"""Client Unlimited-OCR.

Công thức gọi là BẮT BUỘC, sai một trong ba thì model trả chuỗi rỗng mà
không báo lỗi gì:
  1. prompt phải mở đầu bằng literal '<image>'
  2. skip_special_tokens phải là False
  3. vllm_xargs {ngram_size: 35, window_size: N}

Đã kiểm chứng thật: một trang A4 150dpi mất ~2.7s, trả text kèm bbox và
nhãn khối theo cú pháp <|det|>nhãn [x0, y0, x1, y1]<|/det|>nội dung.
"""

import base64
import json
import re
import urllib.error
import urllib.request

from ..types import Block

PROMPT = "<image>document parsing."
NGRAM_SIZE = 35
WINDOW_IMAGE = 128          # ảnh rời
WINDOW_PDF = 1024           # trang thuộc PDF nhiều trang
DEFAULT_MODEL = "baidu/Unlimited-OCR"

_DET_RE = re.compile(
    r"<\|det\|>\s*(?P<label>[^\[\]]*?)\s*\[\s*(?P<box>[-\d.,\s]+?)\s*\]\s*<\|/det\|>"
    r"(?P<text>.*)"
)


class OcrError(RuntimeError):
    """Không gọi được service, hoặc service trả lỗi."""


class OcrEmptyOutput(OcrError):
    """Service trả rỗng — hoặc trang trắng, hoặc sai công thức gọi."""


def _http_post(url, body, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise OcrError(f"gọi OCR thất bại: {exc}") from exc


def parse_ocr_output(raw):
    """Chuỗi model trả về -> list[Block]."""
    blocks = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _DET_RE.match(line)
        if not m:
            # Dòng trần không có thẻ det: vẫn giữ, mất chữ tệ hơn mất toạ độ.
            blocks.append(Block(text=line))
            continue
        text = m.group("text").strip()
        if not text:
            continue
        try:
            nums = [float(v) for v in m.group("box").split(",")]
            bbox = tuple(nums[:4]) if len(nums) >= 4 else None
        except ValueError:
            bbox = None
        blocks.append(Block(text=text, bbox=bbox))
    return blocks


def ocr_image(png_bytes, base_url, model=DEFAULT_MODEL, window_size=WINDOW_PDF,
              timeout=180, transport=None):
    """PNG bytes -> list[Block]. `transport` cho test tiêm hàm giả."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": PROMPT},
        ]}],
        "max_tokens": 4096,
        "skip_special_tokens": False,
        "vllm_xargs": {"ngram_size": NGRAM_SIZE, "window_size": window_size},
    }
    send = transport or _http_post
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        data = send(url, body, timeout)
    except OcrError:
        raise
    except Exception as exc:                # TimeoutError, socket.error, ...
        raise OcrError(f"gọi OCR thất bại: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OcrError(f"OCR trả về cấu trúc lạ: {data!r}") from exc

    if not (content or "").strip():
        raise OcrEmptyOutput(
            "OCR trả rỗng — kiểm tra prompt có mở đầu bằng '<image>', "
            "skip_special_tokens=False và vllm_xargs"
        )
    return parse_ocr_output(content)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests/test_extract_ocr.py -q`
Expected: PASS, 13 passed

- [ ] **Step 5: Chạy toàn bộ test thư viện — mốc hoàn thành `aidt_search_engine`**

Run: `cd custom-addons && python -m pytest aidt_search_engine/tests -q`
Expected: PASS, ~112 passed

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_search_engine/extract/ocr.py custom-addons/aidt_search_engine/tests/test_extract_ocr.py
git commit -m "feat(search): add Unlimited-OCR client with mandatory call recipe"
```

---

## Task 12: Addon Odoo — khung module và bảng `aidt.doc.chunk`

**Files:**
- Create: `custom-addons/aidt_search/__init__.py`, `__manifest__.py`
- Create: `custom-addons/aidt_search/models/__init__.py`
- Create: `custom-addons/aidt_search/models/doc_chunk.py`
- Create: `custom-addons/aidt_search/security/ir.model.access.csv`
- Create: `custom-addons/aidt_search/data/ir_config_parameter.xml`
- Create: `custom-addons/aidt_search/tests/__init__.py`, `tests/test_schema.py`

**Interfaces:**
- Consumes: `aidt_dms` (model `aidt.document`, `dms.file`), `aidt_org` (`ir.rule`)
- Produces: model `aidt.doc.chunk` với các cột SQL `embedding vector(1024)`, `ts`, `ts_noaccent`, `ts_seg`; hàm SQL `f_unaccent(text)`

- [ ] **Step 1: Viết test thất bại**

`custom-addons/aidt_search/tests/test_schema.py`:

```python
from odoo.tests.common import TransactionCase


class TestChunkSchema(TransactionCase):
    def _columns(self):
        self.env.cr.execute(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name = 'aidt_doc_chunk'"
        )
        return dict(self.env.cr.fetchall())

    def test_extension_da_cai(self):
        self.env.cr.execute("SELECT extname FROM pg_extension")
        names = {r[0] for r in self.env.cr.fetchall()}
        self.assertIn("vector", names)
        self.assertIn("unaccent", names)

    def test_cot_embedding_dung_kieu(self):
        self.assertEqual(self._columns().get("embedding"), "vector")

    def test_hai_cot_tsvector_ton_tai(self):
        cols = self._columns()
        self.assertEqual(cols.get("ts"), "tsvector")
        self.assertEqual(cols.get("ts_noaccent"), "tsvector")
        self.assertEqual(cols.get("ts_seg"), "tsvector")

    def test_ts_la_generated_column(self):
        # Generated column là điểm mấu chốt: không có đường nào cho code
        # quên cập nhật chỉ mục lexical.
        self.env.cr.execute(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name='aidt_doc_chunk' AND column_name='ts'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "ALWAYS")

    def test_f_unaccent_bo_dau_va_xu_ly_chu_d(self):
        # Phải khớp strip_accents() phía Python, nếu không kênh không dấu trượt.
        self.env.cr.execute("SELECT f_unaccent('Đảng hộ nghèo')")
        self.assertEqual(self.env.cr.fetchone()[0], "Dang ho ngheo")

    def test_chi_muc_hnsw_va_gin_ton_tai(self):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'aidt_doc_chunk'"
        )
        defs = " ".join(r[0] for r in self.env.cr.fetchall())
        self.assertIn("hnsw", defs)
        self.assertIn("gin", defs)

    def test_ts_tu_dong_cap_nhat_khi_ghi_text(self):
        doc = self.env["aidt.document"].create({
            "name": "Văn bản thử", "direction": "den", "secrecy": "thuong",
        })
        chunk = self.env["aidt.doc.chunk"].create({
            "document_id": doc.id, "seq": 0,
            "text": "hỗ trợ hộ nghèo", "embed_text": "hỗ trợ hộ nghèo",
        })
        self.env.cr.execute(
            "SELECT ts @@ to_tsquery('simple', 'nghèo'), "
            "       ts_noaccent @@ to_tsquery('simple', 'ngheo') "
            "FROM aidt_doc_chunk WHERE id = %s", (chunk.id,)
        )
        has_accent, no_accent = self.env.cr.fetchone()
        self.assertTrue(has_accent)
        self.assertTrue(no_accent)
```

- [ ] **Step 2: Viết `__manifest__.py` và `__init__.py`**

`custom-addons/aidt_search/__manifest__.py`:

```python
{
    'name': 'AIDT Tìm kiếm thông minh',
    'version': '1.0',
    'category': 'Document Management',
    'summary': 'Chỉ mục lai (vector + lexical) và tìm kiếm ngữ nghĩa trên kho văn bản '
               '(V-10 → V-14, S-11, N-12)',
    'depends': ['aidt_dms', 'aidt_org'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
    ],
    'license': 'LGPL-3',
    'application': False,
}
```

`custom-addons/aidt_search/__init__.py`:

```python
from . import models
```

`custom-addons/aidt_search/models/__init__.py`:

```python
from . import doc_chunk
```

`custom-addons/aidt_search/tests/__init__.py`:

```python
from . import test_schema
```

- [ ] **Step 3: Viết `models/doc_chunk.py`**

```python
from odoo import api, fields, models

# Số chiều của AITeamVN/Vietnamese_Embedding. Đổi model sang số chiều khác
# là một migration có chủ đích (ALTER COLUMN + nạp lại toàn bộ), không phải
# đổi một tham số cấu hình.
EMBED_DIM = 1024


class AidtDocChunk(models.Model):
    _name = 'aidt.doc.chunk'
    _description = 'Đoạn nội dung đã chỉ mục'
    _order = 'document_id, file_id, seq'

    document_id = fields.Many2one(
        'aidt.document', string='Văn bản', required=True,
        ondelete='cascade', index=True)
    file_id = fields.Many2one(
        'dms.file', string='Tệp', ondelete='cascade', index=True)

    seq = fields.Integer(string='Thứ tự', default=0)
    zone = fields.Char(string='Vùng thể thức', index=True)
    zone_confidence = fields.Selection(
        [('style', 'Theo style'), ('heuristic', 'Suy đoán')],
        string='Độ tin cậy vùng')
    heading_path = fields.Char(string='Đường dẫn mục')
    text = fields.Text(string='Nội dung', required=True)
    embed_text = fields.Text(
        string='Chuỗi đã embed',
        help='Chuỗi thực sự đem đi embed, gồm contextual header. Giữ lại để '
             'khi kết quả sai còn trả lời được câu hỏi "nó đã embed cái gì".')
    page = fields.Integer(string='Trang')
    bbox = fields.Char(string='Toạ độ')
    ocr_confidence = fields.Float(string='Độ tin cậy OCR')
    token_count = fields.Integer(string='Số token')

    def init(self):
        """Tạo extension, hàm f_unaccent, cột vector/tsvector và chỉ mục.

        Ba cột dưới đây không khai bằng fields.* được vì ORM của Odoo không
        có kiểu vector lẫn tsvector. Odoo không xoá cột nó không biết nên
        cách này an toàn qua các lần nâng cấp module.
        """
        cr = self.env.cr
        cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

        # unaccent() không IMMUTABLE nên không dùng thẳng trong generated
        # column được. Bọc lại là thủ thuật chuẩn của Postgres.
        cr.execute("""
            CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
              LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
              $$ SELECT public.unaccent('public.unaccent', $1) $$
        """)

        cr.execute(f"""
            ALTER TABLE aidt_doc_chunk
              ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIM}),
              ADD COLUMN IF NOT EXISTS ts tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED,
              ADD COLUMN IF NOT EXISTS ts_noaccent tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', f_unaccent(coalesce(text, '')))) STORED,
              ADD COLUMN IF NOT EXISTS ts_seg tsvector
        """)

        cr.execute("""
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_embedding_idx
              ON aidt_doc_chunk USING hnsw (embedding vector_cosine_ops);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_idx
              ON aidt_doc_chunk USING gin (ts);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_noaccent_idx
              ON aidt_doc_chunk USING gin (ts_noaccent);
            CREATE INDEX IF NOT EXISTS aidt_doc_chunk_ts_seg_idx
              ON aidt_doc_chunk USING gin (ts_seg);
        """)
```

- [ ] **Step 4: Viết quyền và tham số cấu hình**

`custom-addons/aidt_search/security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_aidt_doc_chunk_user,aidt.doc.chunk user,model_aidt_doc_chunk,aidt_org.group_chuyen_vien,1,0,0,0
access_aidt_doc_chunk_admin,aidt.doc.chunk admin,model_aidt_doc_chunk,aidt_org.group_aidt_admin,1,1,1,1
```

`custom-addons/aidt_search/data/ir_config_parameter.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- URL service là DỮ LIỆU, không phải code: đổi được từ UI, không
         deploy lại. Cùng triết lý với ruleset YAML của aidt_format. -->
    <data noupdate="1">
        <record id="param_ocr_url" model="ir.config_parameter">
            <field name="key">aidt_search.ocr_url</field>
            <field name="value">http://unlimited-ocr:8000/v1</field>
        </record>
        <record id="param_embed_url" model="ir.config_parameter">
            <field name="key">aidt_search.embed_url</field>
            <field name="value">http://aidt-embed:8001/v1</field>
        </record>
        <record id="param_embed_model" model="ir.config_parameter">
            <field name="key">aidt_search.embed_model</field>
            <field name="value">AITeamVN/Vietnamese_Embedding</field>
        </record>
        <record id="param_embed_dim" model="ir.config_parameter">
            <field name="key">aidt_search.embed_dim</field>
            <field name="value">1024</field>
        </record>
        <record id="param_tokenize_mode" model="ir.config_parameter">
            <field name="key">aidt_search.tokenize_mode</field>
            <field name="value">syllable</field>
        </record>
        <record id="param_scan_char_threshold" model="ir.config_parameter">
            <field name="key">aidt_search.scan_char_threshold</field>
            <field name="value">50</field>
        </record>
    </data>
</odoo>
```

- [ ] **Step 5: Cài module và chạy test**

> **Cập nhật môi trường (đã xác minh trực tiếp, thay cho ghi chú cũ ở Task 2).**
> `aidt_demo` **đã có đầy đủ schema Odoo** — 82 module đã cài, gồm cả
> `aidt_dms`, `aidt_org`, `dms`, `mail`, `hr`, `project`. Đây KHÔNG phải lần
> khởi tạo đầu tiên: `-i aidt_search` chỉ cài thêm một module vào database đã
> có sẵn, không kéo theo cả chuỗi phụ thuộc, và không mất vài phút. Extension
> `vector` (pgvector 0.8.6) và `unaccent` cũng đã có sẵn trên `aidt_demo`. Vẫn
> không có dữ liệu demo cho `aidt.doc.chunk` — Task 18 tự tạo văn bản của nó.

```bash
cd /home/aphuc/dev/aidt-odoo
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -i aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: `7 passed`, không có dòng `FAIL`/`ERROR` trong log.

Nếu `test_f_unaccent_bo_dau_va_xu_ly_chu_d` fail (ra `Đang ho ngheo`) thì R2 đã mở — theo đúng cách xử lý đã ghi ở Task 2 Step 4 và cập nhật `f_unaccent` dùng dictionary `vi`.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add aidt_search module with pgvector chunk schema"
```

---

## Task 13: Hàng đợi chỉ mục — `aidt.index.job`, chống trùng, cron

**Files:**
- Create: `custom-addons/aidt_search/models/index_job.py`
- Create: `custom-addons/aidt_search/models/dms_file.py`
- Create: `custom-addons/aidt_search/data/ir_cron.xml`
- Modify: `custom-addons/aidt_search/models/__init__.py`
- Modify: `custom-addons/aidt_search/__manifest__.py` (thêm `data/ir_cron.xml`, view job)
- Modify: `custom-addons/aidt_search/security/ir.model.access.csv`
- Create: `custom-addons/aidt_search/tests/test_index_job.py`
- Modify: `custom-addons/aidt_search/tests/__init__.py`

**Interfaces:**
- Consumes: `aidt.doc.chunk`, `dms.file`
- Produces:
  - `aidt.index.job` với `_enqueue_file(dms_file) -> record`, `_claim(limit) -> recordset`, `_cron_process(limit=5, budget_seconds=300)`, `action_retry()`
  - `_mark_transient(msg)`, `_mark_permanent(msg)`, `_mark_done(stage_ms)`
  - hằng `MAX_ATTEMPT = 3`, `RETRY_BACKOFF_MINUTES = (1, 4, 16)`

- [ ] **Step 1: Viết test thất bại**

`custom-addons/aidt_search/tests/test_index_job.py`:

```python
import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class IndexJobCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms.field.mixin bỏ qua template khi test_enable bật, trừ khi có
        # context này — thiếu nó thì thư mục không tự sinh và test fail
        # một cách khó hiểu (xem docs/dms-integration-guide.md).
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch thử nghiệm', 'direction': 'den',
            'secrecy': 'thuong', 'reference': '145/KH-UBND',
        })

    def _add_file(self, name='mau.docx', content=b'noi dung'):
        return self.env['dms.file'].sudo().create({
            'name': name,
            'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(content),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
        })


class TestEnqueue(IndexJobCase):
    def test_tao_file_thi_sinh_job_pending(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(len(job), 1)
        self.assertEqual(job.state, 'pending')

    def test_job_gan_dung_van_ban(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(job.document_id, self.doc)

    def test_co_content_hash(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        self.assertEqual(len(job.content_hash), 64)

    def test_file_ngoai_aidt_document_khong_sinh_job(self):
        storage = self.env['dms.storage'].sudo().search([], limit=1)
        other = self.env['dms.directory'].sudo().create({
            'name': 'Thư mục rời', 'storage_id': storage.id, 'is_root_directory': True,
        })
        f = self.env['dms.file'].sudo().create({
            'name': 'ngoai.docx', 'directory_id': other.id,
            'content': base64.b64encode(b'x'),
        })
        self.assertFalse(self.env['aidt.index.job'].search([('file_id', '=', f.id)]))

    def test_doi_reference_xep_lai_hang_chi_muc(self):
        f = self._add_file()
        Job = self.env['aidt.index.job']
        Job.search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.write({'reference': '999/KH-UBND'})
        # reference nằm trong contextual header nên đã được embed vào vector;
        # không nạp lại thì header lệch thực tế.
        self.assertTrue(Job.search([('file_id', '=', f.id), ('state', '=', 'pending')]))


class TestDedup(IndexJobCase):
    def test_cung_noi_dung_thi_chep_chunk_khong_goi_ocr(self):
        f1 = self._add_file('mot.docx', b'noi dung giong het')
        Job = self.env['aidt.index.job']
        job1 = Job.search([('file_id', '=', f1.id)])
        self.env['aidt.doc.chunk'].create({
            'document_id': self.doc.id, 'file_id': f1.id, 'seq': 0,
            'text': 'nội dung', 'embed_text': 'nội dung',
        })
        job1.write({'state': 'done'})

        f2 = self._add_file('hai.docx', b'noi dung giong het')
        job2 = Job.search([('file_id', '=', f2.id)])
        with patch.object(type(self.env['aidt.index.pipeline']), 'run') as run:
            job2._cron_process()
            run.assert_not_called()
        self.assertEqual(job2.state, 'done')
        self.assertEqual(
            self.env['aidt.doc.chunk'].search_count([('file_id', '=', f2.id)]), 1)


class TestErrorClassification(IndexJobCase):
    def test_loi_tam_thoi_giu_pending_va_tang_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_transient('service không phản hồi')
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempt, 1)
        self.assertTrue(job.next_retry_at)

    def test_loi_vinh_vien_failed_ngay_khong_tang_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_permanent('định dạng chưa hỗ trợ')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempt, 0)
        self.assertEqual(job.error_kind, 'permanent')

    def test_qua_tran_attempt_thi_thanh_failed(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        for _ in range(3):
            job._mark_transient('timeout')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempt, 3)

    def test_action_retry_dua_ve_pending_va_reset_attempt(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_permanent('hỏng')
        job.action_retry()
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempt, 0)
        self.assertFalse(job.error)


class TestClaim(IndexJobCase):
    def test_khong_nhan_job_chua_toi_han_retry(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job._mark_transient('timeout')
        self.assertNotIn(job, self.env['aidt.index.job']._claim(limit=10))

    def test_khong_nhan_job_da_done(self):
        f = self._add_file()
        job = self.env['aidt.index.job'].search([('file_id', '=', f.id)])
        job.write({'state': 'done'})
        self.assertNotIn(job, self.env['aidt.index.job']._claim(limit=10))
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: FAIL — `KeyError: 'aidt.index.job'`

- [ ] **Step 3: Viết `models/index_job.py`**

```python
import hashlib
import logging
import time

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

MAX_ATTEMPT = 3
# Lùi lịch theo cấp số nhân: service vừa chết thì thử lại ngay không ích gì.
RETRY_BACKOFF_MINUTES = (1, 4, 16)


class AidtIndexJob(models.Model):
    _name = 'aidt.index.job'
    _description = 'Việc chỉ mục tài liệu'
    _order = 'create_date desc, id desc'

    document_id = fields.Many2one(
        'aidt.document', string='Văn bản', required=True,
        ondelete='cascade', index=True)
    file_id = fields.Many2one(
        'dms.file', string='Tệp', ondelete='cascade', index=True)
    content_hash = fields.Char(string='Hash nội dung', size=64, index=True)

    state = fields.Selection(
        [('pending', 'Chờ xử lý'), ('extracting', 'Đang trích xuất'),
         ('chunking', 'Đang chia đoạn'), ('embedding', 'Đang tạo vector'),
         ('done', 'Xong'), ('failed', 'Lỗi')],
        string='Trạng thái', default='pending', required=True, index=True)
    error_kind = fields.Selection(
        [('transient', 'Tạm thời'), ('permanent', 'Vĩnh viễn')],
        string='Loại lỗi')
    attempt = fields.Integer(string='Số lần thử', default=0)
    next_retry_at = fields.Datetime(string='Thử lại lúc')
    error = fields.Text(string='Thông điệp lỗi')
    stage_ms = fields.Json(string='Thời gian từng chặng')

    # ------------------------------------------------------------------ #
    # Xếp hàng
    # ------------------------------------------------------------------ #
    @api.model
    def _enqueue_file(self, dms_file):
        """Tạo job cho một dms.file thuộc aidt.document. Trả về job hoặc None."""
        directory = dms_file.sudo().directory_id
        if directory.res_model != 'aidt.document' or not directory.res_id:
            return None
        content = dms_file.sudo().with_context(bin_size=False).content
        digest = hashlib.sha256(content or b'').hexdigest() if content else False
        return self.sudo().create({
            'document_id': directory.res_id,
            'file_id': dms_file.id,
            'content_hash': digest,
            'state': 'pending',
        })

    @api.model
    def _enqueue_document(self, documents):
        """Xếp lại hàng toàn bộ tệp của văn bản — dùng khi đổi reference/name/
        doc_type, vì ba trường đó nằm trong contextual header đã embed."""
        for doc in documents:
            for dms_file in doc.sudo().directory_id.file_ids:
                self._enqueue_file(dms_file)

    # ------------------------------------------------------------------ #
    # Trạng thái
    # ------------------------------------------------------------------ #
    def _mark_transient(self, message):
        """Lỗi tạm thời: giữ pending, lùi lịch. Quá trần mới thành failed."""
        for job in self:
            attempt = job.attempt + 1
            if attempt >= MAX_ATTEMPT:
                job.write({
                    'state': 'failed', 'error_kind': 'transient',
                    'attempt': attempt, 'error': message, 'next_retry_at': False,
                })
                continue
            delay = RETRY_BACKOFF_MINUTES[min(attempt - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
            job.write({
                'state': 'pending', 'error_kind': 'transient', 'attempt': attempt,
                'error': message,
                'next_retry_at': fields.Datetime.add(fields.Datetime.now(), minutes=delay),
            })

    def _mark_permanent(self, message):
        """Lỗi vĩnh viễn: failed ngay. Retry chỉ đốt GPU để nhận đúng lỗi đó."""
        self.write({
            'state': 'failed', 'error_kind': 'permanent',
            'error': message, 'next_retry_at': False,
        })

    def _mark_done(self, stage_ms=None):
        self.write({
            'state': 'done', 'error': False, 'error_kind': False,
            'next_retry_at': False, 'stage_ms': stage_ms or {},
        })

    def action_retry(self):
        self.write({
            'state': 'pending', 'attempt': 0, 'error': False,
            'error_kind': False, 'next_retry_at': False,
        })

    # ------------------------------------------------------------------ #
    # Worker
    # ------------------------------------------------------------------ #
    @api.model
    def _claim(self, limit=5):
        """Nhận việc bằng SKIP LOCKED — an toàn khi sau này chạy nhiều worker."""
        self.env.cr.execute("""
            SELECT id FROM aidt_index_job
             WHERE state = 'pending'
               AND (next_retry_at IS NULL OR next_retry_at <= now() AT TIME ZONE 'UTC')
             ORDER BY id
             LIMIT %s
               FOR UPDATE SKIP LOCKED
        """, (limit,))
        return self.browse([r[0] for r in self.env.cr.fetchall()])

    def _copy_chunks_from_twin(self):
        """Chép chunk từ job đã done có cùng content_hash. True nếu chép được.

        Trong ERP cùng một công văn bị đính kèm lại liên tục — đây là chỗ
        tiết kiệm nhiều nhất và gần như miễn phí.
        """
        self.ensure_one()
        if not self.content_hash:
            return False
        twin = self.sudo().search([
            ('content_hash', '=', self.content_hash),
            ('state', '=', 'done'), ('id', '!=', self.id),
        ], limit=1)
        if not twin or not twin.file_id:
            return False
        Chunk = self.env['aidt.doc.chunk'].sudo()
        source = Chunk.search([('file_id', '=', twin.file_id.id)])
        if not source:
            return False
        Chunk.search([('file_id', '=', self.file_id.id)]).unlink()
        for chunk in source:
            chunk.copy({'document_id': self.document_id.id, 'file_id': self.file_id.id})
        self.env.cr.execute("""
            UPDATE aidt_doc_chunk tgt
               SET embedding = src.embedding
              FROM aidt_doc_chunk src
             WHERE tgt.file_id = %s AND src.file_id = %s AND tgt.seq = src.seq
        """, (self.file_id.id, twin.file_id.id))
        return True

    @api.model
    def _cron_process(self, limit=5, budget_seconds=300):
        """Chạy mỗi phút. Commit sau MỖI job: một tệp hỏng không được kéo đổ
        những tệp tốt. Có ngân sách đồng hồ để không giữ cron quá lâu."""
        started = time.monotonic()
        for job in self._claim(limit=limit):
            if time.monotonic() - started > budget_seconds:
                break
            try:
                if job._copy_chunks_from_twin():
                    job._mark_done({'dedup': 0})
                else:
                    self.env['aidt.index.pipeline'].run(job)
            except Exception as exc:                    # noqa: BLE001
                _logger.exception("Chỉ mục thất bại cho job %s", job.id)
                job._mark_transient(str(exc))
            self.env.cr.commit()
        return True
```

- [ ] **Step 4: Viết `models/dms_file.py` và hook đổi `reference`**

`custom-addons/aidt_search/models/dms_file.py`:

```python
from odoo import api, models

# Ba trường này nằm trong contextual header nên đã được embed vào vector.
# Đổi mà không nạp lại thì header lệch thực tế.
HEADER_FIELDS = {'reference', 'name', 'doc_type'}


class DmsFile(models.Model):
    _inherit = 'dms.file'

    @api.model_create_multi
    def create(self, vals_list):
        files = super().create(vals_list)
        for dms_file in files:
            self.env['aidt.index.job']._enqueue_file(dms_file)
        return files

    def write(self, vals):
        res = super().write(vals)
        if 'content' in vals:
            for dms_file in self:
                self.env['aidt.index.job']._enqueue_file(dms_file)
        return res


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    def write(self, vals):
        res = super().write(vals)
        if HEADER_FIELDS & set(vals):
            self.env['aidt.index.job']._enqueue_document(self)
        return res
```

Cập nhật `models/__init__.py`:

```python
from . import doc_chunk
from . import index_job
from . import dms_file
```

- [ ] **Step 5: Viết cron và cập nhật manifest, quyền**

`custom-addons/aidt_search/data/ir_cron.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="cron_index_job" model="ir.cron">
            <field name="name">AIDT: xử lý hàng đợi chỉ mục</field>
            <field name="model_id" ref="model_aidt_index_job"/>
            <field name="state">code</field>
            <field name="code">model._cron_process()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">minutes</field>
            <field name="active" eval="True"/>
        </record>
    </data>
</odoo>
```

Thêm vào `__manifest__.py` mục `data`, ngay sau `ir_config_parameter.xml`:

```python
        'data/ir_cron.xml',
```

Thêm hai dòng vào `security/ir.model.access.csv`:

```csv
access_aidt_index_job_user,aidt.index.job user,model_aidt_index_job,aidt_org.group_chuyen_vien,1,0,0,0
access_aidt_index_job_admin,aidt.index.job admin,model_aidt_index_job,aidt_org.group_aidt_admin,1,1,1,1
```

Cập nhật `tests/__init__.py`:

```python
from . import test_schema
from . import test_index_job
```

- [ ] **Step 6: Chạy test, phải xanh**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: `19 passed`

`TestDedup` phụ thuộc `aidt.index.pipeline` chưa tồn tại — nó chỉ patch `run` nên model phải khai được. Nếu đỏ vì `KeyError: 'aidt.index.pipeline'`, tạo trước một `AbstractModel` rỗng trong `models/pipeline.py` với `def run(self, job): raise NotImplementedError`, Task 14 sẽ điền thân.

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add index job queue with dedup, error classing and cron"
```

---

## Task 14: Pipeline trích xuất → chunk → embed → ghi

**Files:**
- Create: `custom-addons/aidt_search/models/embed_client.py`
- Create: `custom-addons/aidt_search/models/pipeline.py`
- Modify: `custom-addons/aidt_search/models/__init__.py`
- Create: `custom-addons/aidt_search/tests/test_pipeline.py`
- Modify: `custom-addons/aidt_search/tests/__init__.py`

**Interfaces:**
- Consumes: `aidt_search_engine.{chunker, types}`, `aidt_search_engine.extract.{docx, pdf, ocr, zone_adapter}`, `aidt.index.job`, `aidt.doc.chunk`
- Produces:
  - `aidt.embed.client.embed(texts) -> list[list[float]]` — ném `EmbedDimensionError` khi số chiều lệch
  - `aidt.index.pipeline.run(job)` — chạy hết một job, tự `_mark_done` / `_mark_permanent`
  - `aidt.index.pipeline._extract(job, blob, filename) -> list[Block]`
  - `aidt.index.pipeline._doc_meta(document) -> DocMeta`

- [ ] **Step 1: Viết test thất bại**

`custom-addons/aidt_search/tests/test_pipeline.py`:

```python
import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.aidt_search_engine.types import Block

DIM = 1024


def fake_vectors(texts):
    return [[0.01] * DIM for _ in texts]


class PipelineCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch an toàn thông tin', 'direction': 'den',
            'secrecy': 'thuong', 'reference': '145/KH-UBND', 'doc_type': 'ke_hoach',
        })

    def _file(self, name, content=b'noi dung'):
        return self.env['dms.file'].sudo().create({
            'name': name, 'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(content),
            'res_model': 'aidt.document', 'res_id': self.doc.id,
        })

    def _job(self, dms_file):
        return self.env['aidt.index.job'].search([('file_id', '=', dms_file.id)], limit=1)


class TestDocMeta(PipelineCase):
    def test_lay_dung_ba_thanh_phan_header(self):
        meta = self.env['aidt.index.pipeline']._doc_meta(self.doc)
        self.assertEqual(meta.reference, '145/KH-UBND')
        self.assertEqual(meta.doc_type_label, 'Kế hoạch')
        self.assertEqual(meta.title, 'Kế hoạch an toàn thông tin')


class TestEmbedClient(PipelineCase):
    def test_kiem_so_chieu_va_nem_khi_lech(self):
        # Đổi model mà quên embed_dim phải nổ NGAY lúc chèn, tuyệt đối
        # không được ghi bừa vector sai chiều vào cột vector(1024).
        from odoo.addons.aidt_search.models.embed_client import EmbedDimensionError
        Client = self.env['aidt.embed.client']
        with patch.object(type(Client), '_post', return_value=[[0.0] * 768]):
            with self.assertRaises(EmbedDimensionError):
                Client.embed(['xin chào'])

    def test_danh_sach_rong_khong_goi_service(self):
        Client = self.env['aidt.embed.client']
        with patch.object(type(Client), '_post') as post:
            self.assertEqual(Client.embed([]), [])
            post.assert_not_called()


class TestPipelineRun(PipelineCase):
    def _run(self, dms_file, blocks):
        job = self._job(dms_file)
        Pipeline = type(self.env['aidt.index.pipeline'])
        with patch.object(Pipeline, '_extract', return_value=blocks), \
             patch.object(type(self.env['aidt.embed.client']), 'embed', side_effect=fake_vectors):
            self.env['aidt.index.pipeline'].run(job)
        return job

    def test_sinh_chunk_va_danh_dau_done(self):
        f = self._file('mau.docx')
        job = self._run(f, [Block(text='Các sở, ban, ngành có trách nhiệm.', zone='noi_dung')])
        self.assertEqual(job.state, 'done')
        self.assertEqual(self.env['aidt.doc.chunk'].search_count([('file_id', '=', f.id)]), 1)

    def test_embed_text_chua_contextual_header(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Nội dung điều khoản.', zone='noi_dung')])
        chunk = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)], limit=1)
        self.assertIn('145/KH-UBND', chunk.embed_text)
        self.assertNotIn('145/KH-UBND', chunk.text)

    def test_ghi_vector_vao_cot_embedding(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Nội dung.', zone='noi_dung')])
        chunk = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)], limit=1)
        self.env.cr.execute(
            "SELECT embedding IS NOT NULL FROM aidt_doc_chunk WHERE id = %s", (chunk.id,))
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_nap_lai_xoa_chunk_cu_truoc(self):
        f = self._file('mau.docx')
        self._run(f, [Block(text='Bản đầu tiên.', zone='noi_dung')])
        self._job(f).action_retry()
        self._run(f, [Block(text='Bản thứ hai.', zone='noi_dung')])
        chunks = self.env['aidt.doc.chunk'].search([('file_id', '=', f.id)])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks.text, 'Bản thứ hai.')

    def test_ghi_stage_ms(self):
        f = self._file('mau.docx')
        job = self._run(f, [Block(text='Nội dung.', zone='noi_dung')])
        self.assertIn('extract', job.stage_ms)
        self.assertIn('embed', job.stage_ms)

    def test_khong_trich_duoc_gi_thi_failed_vinh_vien(self):
        f = self._file('trong.docx')
        job = self._run(f, [])
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')


class TestExtractRouting(PipelineCase):
    def test_dinh_dang_khong_ho_tro_la_loi_vinh_vien(self):
        f = self._file('anh.tiff.xyz', b'\x00\x01rac')
        job = self._job(f)
        self.env['aidt.index.pipeline'].run(job)
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')

    def test_docx_hong_la_loi_vinh_vien(self):
        f = self._file('hong.docx', b'khong phai docx')
        job = self._job(f)
        self.env['aidt.index.pipeline'].run(job)
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error_kind, 'permanent')
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: FAIL — `KeyError: 'aidt.embed.client'`

- [ ] **Step 3: Viết `models/embed_client.py`**

```python
import json
import logging
import urllib.error
import urllib.request

from odoo import api, models

_logger = logging.getLogger(__name__)

BATCH_SIZE = 32
TIMEOUT = 120


class EmbedError(RuntimeError):
    """Không gọi được service embedding."""


class EmbedDimensionError(RuntimeError):
    """Vector trả về không đúng số chiều của cột."""


class AidtEmbedClient(models.AbstractModel):
    _name = 'aidt.embed.client'
    _description = 'Client dịch vụ embedding'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_search.{key}', default)

    @api.model
    def _post(self, texts):
        url = f"{self._config('embed_url', '').rstrip('/')}/embeddings"
        body = {'model': self._config('embed_model'), 'input': texts}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise EmbedError(f'gọi embedding thất bại: {exc}') from exc
        try:
            return [row['embedding'] for row in data['data']]
        except (KeyError, TypeError) as exc:
            raise EmbedError(f'embedding trả về cấu trúc lạ: {data!r}') from exc

    @api.model
    def embed(self, texts):
        """list[str] -> list[list[float]]. Ném EmbedDimensionError nếu lệch chiều.

        Kiểm số chiều là bắt buộc: cột là vector(1024) cố định, ghi bừa một
        vector 768 chiều sẽ hỏng chỉ mục theo cách rất khó truy.
        """
        if not texts:
            return []
        expected = int(self._config('embed_dim', 1024))
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = self._post(texts[start:start + BATCH_SIZE])
            for vec in batch:
                if len(vec) != expected:
                    raise EmbedDimensionError(
                        f'model trả vector {len(vec)} chiều nhưng cột là '
                        f'vector({expected}) — đổi model là một migration, '
                        f'không phải đổi một tham số')
            vectors.extend(batch)
        return vectors
```

- [ ] **Step 4: Viết `models/pipeline.py`**

```python
import base64
import logging
import os
import tempfile
import time

from odoo import api, models

from odoo.addons.aidt_search_engine.chunker import chunk_blocks
from odoo.addons.aidt_search_engine.extract import ocr as ocr_mod
from odoo.addons.aidt_search_engine.extract import pdf as pdf_mod
from odoo.addons.aidt_search_engine.extract.docx import UnreadableDocx, extract_docx
from odoo.addons.aidt_search_engine.extract.zone_adapter import assign_zones
from odoo.addons.aidt_search_engine.types import DocMeta

_logger = logging.getLogger(__name__)

# Magic bytes — không tin đuôi tệp.
_ZIP_MAGIC = b'PK\x03\x04'
_PDF_MAGIC = b'%PDF'
_IMAGE_MAGICS = (b'\x89PNG', b'\xff\xd8\xff', b'II*\x00', b'MM\x00*')

# Ảnh 150dpi khổ A4 rộng ~1240px. zone_adapter dùng tỷ lệ nên con số này
# chỉ cần đúng bậc độ lớn.
_PAGE_WIDTH_PX = 1240.0


class PermanentExtractError(Exception):
    """Tệp không bao giờ xử lý được — retry chỉ đốt GPU."""


class AidtIndexPipeline(models.AbstractModel):
    _name = 'aidt.index.pipeline'
    _description = 'Đường ống chỉ mục tài liệu'

    @api.model
    def _config(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'aidt_search.{key}', default)

    @api.model
    def _doc_meta(self, document):
        """DocMeta cho contextual header."""
        labels = dict(document._fields['doc_type'].selection)
        return DocMeta(
            doc_type_label=labels.get(document.doc_type),
            reference=document.reference or None,
            title=document.name or None,
        )

    # ------------------------------------------------------------------ #
    # Định tuyến trích xuất
    # ------------------------------------------------------------------ #
    @api.model
    def _extract(self, job, blob, filename):
        if blob.startswith(_ZIP_MAGIC):
            try:
                return extract_docx(blob)
            except UnreadableDocx as exc:
                raise PermanentExtractError(f'DOCX không đọc được: {exc}') from exc
        if blob.startswith(_PDF_MAGIC):
            return self._extract_pdf(blob)
        if any(blob.startswith(m) for m in _IMAGE_MAGICS):
            return self._ocr_png(blob, ocr_mod.WINDOW_IMAGE)
        raise PermanentExtractError(f'định dạng chưa hỗ trợ: {filename}')

    @api.model
    def _extract_pdf(self, blob):
        """Quyết định theo TỪNG TRANG: văn bản thật rất hay lai — vài trang
        soạn máy, vài trang scan chèn vào."""
        threshold = int(self._config('scan_char_threshold', 50))
        blocks = []
        fd, path = tempfile.mkstemp(suffix='.pdf')
        try:
            with os.fdopen(fd, 'wb') as fh:
                fh.write(blob)
            try:
                total = pdf_mod.page_count(path)
            except pdf_mod.PdfToolError as exc:
                raise PermanentExtractError(f'PDF không đọc được: {exc}') from exc
            for page in range(1, total + 1):
                text = pdf_mod.page_text(path, page)
                if len(text.strip()) >= threshold:
                    blocks.extend(self._blocks_from_text(text, page))
                else:
                    png = pdf_mod.render_page_png(path, page)
                    blocks.extend(self._ocr_png(png, ocr_mod.WINDOW_PDF, page=page))
        finally:
            if os.path.exists(path):
                os.unlink(path)
        return blocks

    @api.model
    def _blocks_from_text(self, text, page):
        from odoo.addons.aidt_search_engine.types import Block
        raw = [Block(text=line.strip(), page=page)
               for line in text.splitlines() if line.strip()]
        return assign_zones(raw, _PAGE_WIDTH_PX)

    @api.model
    def _ocr_png(self, png, window_size, page=None):
        base_url = self._config('ocr_url', '')
        blocks = ocr_mod.ocr_image(png, base_url, window_size=window_size)
        for block in blocks:
            block.page = page
        return assign_zones(blocks, _PAGE_WIDTH_PX)

    # ------------------------------------------------------------------ #
    # Chạy một job
    # ------------------------------------------------------------------ #
    @api.model
    def run(self, job):
        job.write({'state': 'extracting'})
        stage_ms, dms_file = {}, job.file_id.sudo()
        blob = base64.b64decode(dms_file.with_context(bin_size=False).content or b'')

        t0 = time.monotonic()
        try:
            blocks = self._extract(job, blob, dms_file.name or '')
        except PermanentExtractError as exc:
            job._mark_permanent(str(exc))
            return
        except ocr_mod.OcrEmptyOutput as exc:
            # Trang trắng và lỗi cấu hình trông giống nhau — nhưng ghi chunk
            # rỗng thì tài liệu "đã chỉ mục" mà tìm mãi không ra.
            job._mark_permanent(str(exc))
            return
        stage_ms['extract'] = int((time.monotonic() - t0) * 1000)

        if not blocks:
            job._mark_permanent('không trích xuất được nội dung nào')
            return

        job.write({'state': 'chunking'})
        t0 = time.monotonic()
        chunks = chunk_blocks(blocks, self._doc_meta(job.document_id))
        stage_ms['chunk'] = int((time.monotonic() - t0) * 1000)
        if not chunks:
            job._mark_permanent('nội dung trích được rỗng sau khi chia đoạn')
            return

        job.write({'state': 'embedding'})
        t0 = time.monotonic()
        vectors = self.env['aidt.embed.client'].embed([c.embed_text for c in chunks])
        stage_ms['embed'] = int((time.monotonic() - t0) * 1000)

        self._store(job, chunks, vectors)
        job._mark_done(stage_ms)

    @api.model
    def _store(self, job, chunks, vectors):
        """Xoá chunk cũ rồi chèn mới, trong cùng một transaction."""
        Chunk = self.env['aidt.doc.chunk'].sudo()
        Chunk.search([('file_id', '=', job.file_id.id)]).unlink()
        records = Chunk.create([{
            'document_id': job.document_id.id,
            'file_id': job.file_id.id,
            'seq': c.seq,
            'zone': c.zone,
            'zone_confidence': c.zone_confidence,
            'heading_path': c.heading_path,
            'text': c.text,
            'embed_text': c.embed_text,
            'page': c.page,
            'bbox': str(list(c.bbox)) if c.bbox else False,
            'token_count': c.token_count,
        } for c in chunks])
        for record, vector in zip(records, vectors):
            self.env.cr.execute(
                "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
                (str(vector), record.id))
```

Cập nhật `models/__init__.py`:

```python
from . import doc_chunk
from . import embed_client
from . import pipeline
from . import index_job
from . import dms_file
```

Cập nhật `tests/__init__.py`: thêm `from . import test_pipeline`.

- [ ] **Step 5: Chạy test, phải xanh**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: `31 passed`

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add extraction pipeline with per-page PDF routing"
```

---

## Task 15: Dịch vụ tìm kiếm — định tuyến ý định, ba kênh, RRF, ACL

**Test phân quyền viết TRƯỚC, trước cả khi có giao diện.** Sai ở đây là lỗi bảo mật, không phải lỗi tính năng.

**Files:**
- Create: `custom-addons/aidt_search/models/search_service.py`
- Modify: `custom-addons/aidt_search/models/__init__.py`
- Create: `custom-addons/aidt_search/tests/test_search_acl.py`
- Create: `custom-addons/aidt_search/tests/test_search_service.py`
- Modify: `custom-addons/aidt_search/tests/__init__.py`

**Interfaces:**
- Consumes: `aidt_search_engine.{intent, fusion, rerank, text, tokenize}`, `aidt.embed.client`, `aidt.doc.chunk`
- Produces:
  - `aidt.search.service.search(query, extra_domain=None, limit=20) -> dict` với khoá `documents`, `filters`, `reference`, `channels_used`, `degraded`, `facets`, `total`
  - `_allowed_document_query(domain) -> odoo.orm.Query`
  - `_channel_vector(...)`, `_channel_lexical(...)` trả `list[chunk_id]`

- [ ] **Step 1: Viết test phân quyền thất bại**

`custom-addons/aidt_search/tests/test_search_acl.py`:

```python
from unittest.mock import patch

from odoo.tests.common import TransactionCase

DIM = 1024


class TestSearchAcl(TransactionCase):
    """V-13 và O-03: kết quả phải lọc theo quyền TRƯỚC khi trả về.

    Lọc sau khi xếp hạng là lỗ hổng: top-50 có thể toàn văn bản mật user
    không được xem, lọc xong còn rỗng, trong khi kết quả hợp lệ nằm ở hạng 51.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'Phòng A'})
        cls.dept_b = Dept.create({'name': 'Phòng B'})

        cls.user_a = cls._make_user('canbo_a', cls.dept_a, 'thuong')
        cls.user_b = cls._make_user('canbo_b', cls.dept_b, 'thuong')
        cls.user_mat = cls._make_user('canbo_mat', cls.dept_b, 'tuyet_mat')

        cls.doc_public_a = cls._make_doc('Kế hoạch công khai phòng A', cls.dept_a, 'thuong')
        cls.doc_secret_b = cls._make_doc('Kế hoạch tuyệt mật phòng B', cls.dept_b, 'tuyet_mat')
        for doc in (cls.doc_public_a, cls.doc_secret_b):
            cls._make_chunk(doc, 'kế hoạch bảo đảm an toàn thông tin')

    @classmethod
    def _make_user(cls, login, department, clearance):
        employee = cls.env['hr.employee'].create({
            'name': login, 'department_id': department.id})
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'groups_id': [(4, cls.env.ref('aidt_org.group_chuyen_vien').id)],
        })
        employee.user_id = user
        user.write({'clearance': clearance})
        return user

    @classmethod
    def _make_doc(cls, name, department, secrecy):
        return cls.env['aidt.document'].create({
            'name': name, 'direction': 'den', 'secrecy': secrecy,
            'department_id': department.id, 'doc_type': 'ke_hoach',
        })

    @classmethod
    def _make_chunk(cls, doc, text):
        chunk = cls.env['aidt.doc.chunk'].create({
            'document_id': doc.id, 'seq': 0, 'text': text, 'embed_text': text,
        })
        cls.env.cr.execute(
            "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
            (str([0.01] * DIM), chunk.id))
        return chunk

    def _search_as(self, user, query='an toàn thông tin'):
        service = self.env['aidt.search.service'].with_user(user)
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return service.search(query)

    def test_khong_tra_van_ban_ngoai_don_vi(self):
        names = [d['name'] for d in self._search_as(self.user_a)['documents']]
        self.assertIn('Kế hoạch công khai phòng A', names)
        self.assertNotIn('Kế hoạch tuyệt mật phòng B', names)

    def test_khong_lo_ca_tieu_de_van_ban_vuot_do_mat(self):
        # user_b cùng phòng B nhưng clearance 'thường' -> không được thấy gì.
        result = self._search_as(self.user_b)
        for doc in result['documents']:
            self.assertNotIn('tuyệt mật', doc['name'].lower())

    def test_du_clearance_thi_thay(self):
        names = [d['name'] for d in self._search_as(self.user_mat)['documents']]
        self.assertIn('Kế hoạch tuyệt mật phòng B', names)

    def test_facet_khong_dem_van_ban_ngoai_quyen(self):
        # Con số trên facet cũng không được lộ sự tồn tại của văn bản mật.
        total_a = sum(c for _, c in self._search_as(self.user_a)['facets']['doc_type'])
        total_mat = sum(c for _, c in self._search_as(self.user_mat)['facets']['doc_type'])
        self.assertEqual(total_a, 1)
        self.assertEqual(total_mat, 2)

    def test_tong_so_ket_qua_cung_bi_loc(self):
        self.assertEqual(self._search_as(self.user_a)['total'], 1)
        self.assertEqual(self._search_as(self.user_mat)['total'], 2)

    def test_tra_cuu_so_hieu_cung_phai_loc_quyen(self):
        # Nhánh SQL đi đường riêng nên rất dễ quên áp ir.rule ở đây.
        self.doc_secret_b.write({'reference': '999/KH-UBND'})
        result = self._search_as(self.user_a, '999/KH-UBND')
        self.assertEqual(result['documents'], [])
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: FAIL — `KeyError: 'aidt.search.service'`

- [ ] **Step 3: Viết `models/search_service.py`**

```python
import logging

from odoo import api, fields, models

from odoo.addons.aidt_search_engine.fusion import reciprocal_rank_fusion
from odoo.addons.aidt_search_engine.intent import parse_query
from odoo.addons.aidt_search_engine.rerank import rerank
from odoo.addons.aidt_search_engine.text import strip_accents

_logger = logging.getLogger(__name__)

CHANNEL_TOP_K = 50
SNIPPETS_PER_DOC = 3


class AidtSearchService(models.AbstractModel):
    _name = 'aidt.search.service'
    _description = 'Dịch vụ tìm kiếm thông minh'

    # ------------------------------------------------------------------ #
    # ACL
    # ------------------------------------------------------------------ #
    @api.model
    def _allowed_document_query(self, domain):
        """Query các văn bản user hiện tại được đọc.

        _search() đã áp ir.rule của aidt_org (đơn vị + secrecy_level <=
        clearance_level), nên ta KHÔNG viết một dòng luật quyền nào. Trả về
        Query để nhúng làm subquery — lọc trong SQL, TRƯỚC khi xếp hạng.
        """
        return self.env['aidt.document']._search(domain or [])

    @api.model
    def _domain_from_filters(self, parsed):
        domain = []
        for f in parsed.filters:
            if f.field == 'date':
                start, end = f.value
                domain += [('date', '>=', start), ('date', '<=', end)]
            else:
                domain.append((f.field, '=', f.value))
        return domain

    # ------------------------------------------------------------------ #
    # Ba kênh truy hồi
    # ------------------------------------------------------------------ #
    @api.model
    def _channel_vector(self, vector, allowed_sql, params):
        self.env.cr.execute(f"""
            SELECT c.id FROM aidt_doc_chunk c
             WHERE c.document_id IN ({allowed_sql})
               AND c.embedding IS NOT NULL
             ORDER BY c.embedding <=> %s::vector
             LIMIT %s
        """, params + [str(vector), CHANNEL_TOP_K])
        return [r[0] for r in self.env.cr.fetchall()]

    @api.model
    def _channel_lexical(self, query_text, column, allowed_sql, params, unaccent=False):
        expr = 'f_unaccent(%s)' if unaccent else '%s'
        self.env.cr.execute(f"""
            SELECT c.id
              FROM aidt_doc_chunk c,
                   websearch_to_tsquery('simple', {expr}) AS q
             WHERE c.document_id IN ({allowed_sql})
               AND c.{column} @@ q
             ORDER BY ts_rank_cd(c.{column}, q) DESC, c.id
             LIMIT %s
        """, params + [query_text, CHANNEL_TOP_K])
        return [r[0] for r in self.env.cr.fetchall()]

    # ------------------------------------------------------------------ #
    # Truy vấn
    # ------------------------------------------------------------------ #
    @api.model
    def _catalogs(self):
        doc_type_field = self.env['aidt.document']._fields['doc_type']
        departments = self.env['hr.department'].search_read([], ['name'])
        urgency = self.env['aidt.document']._fields.get('do_khan')
        return (
            list(doc_type_field.selection),
            [(d['id'], d['name']) for d in departments],
            list(urgency.selection) if urgency else [],
        )

    @api.model
    def search(self, query, extra_domain=None, limit=20):
        doc_types, departments, urgencies = self._catalogs()
        parsed = parse_query(query, doc_types, departments, urgencies)

        domain = self._domain_from_filters(parsed) + list(extra_domain or [])
        if parsed.reference:
            domain += ['|', ('reference', '=', parsed.reference),
                       ('so_ky_hieu_gui', '=', parsed.reference)]

        allowed = self._allowed_document_query(domain)
        allowed_sql, params = allowed.subselect().code, list(allowed.subselect().params)

        # Nhánh 1: tra cứu số hiệu -> SQL thẳng, bỏ qua tầng ngữ nghĩa.
        if parsed.reference and not parsed.semantic:
            documents = self.env['aidt.document'].browse(
                [r[0] for r in self._rows(allowed_sql, params, limit)])
            return self._format(parsed, documents, {}, [], degraded=False)

        channels, used, degraded = [], [], False
        if parsed.semantic:
            try:
                vector = self.env['aidt.embed.client'].embed([parsed.semantic])[0]
                channels.append(self._channel_vector(vector, allowed_sql, params))
                used.append('vector')
            except Exception as exc:                    # noqa: BLE001
                # Giảm cấp mềm: một container chết không được làm chết cả
                # tính năng. RRF nhận số kênh bất kỳ nên chuyện này miễn phí.
                _logger.warning('Kênh vector không dùng được, chạy tiếp lexical: %s', exc)
                degraded = True
            channels.append(self._channel_lexical(parsed.semantic, 'ts', allowed_sql, params))
            used.append('lexical')
            channels.append(self._channel_lexical(
                strip_accents(parsed.semantic), 'ts_noaccent', allowed_sql, params,
                unaccent=True))
            used.append('lexical_noaccent')

        fused = rerank(parsed.semantic, reciprocal_rank_fusion(channels))
        chunk_ids = [cid for cid, _ in fused]
        return self._format_from_chunks(parsed, chunk_ids, allowed_sql, params,
                                        used, degraded, limit)

    @api.model
    def _rows(self, allowed_sql, params, limit):
        self.env.cr.execute(
            f"SELECT id FROM aidt_document WHERE id IN ({allowed_sql}) LIMIT %s",
            params + [limit])
        return self.env.cr.fetchall()
```

> Việc gom chunk về văn bản, dựng trích đoạn `ts_headline` và tính facet nằm ở Task 16 — `_format` và `_format_from_chunks` được viết ở đó. Ở task này tạm để hai hàm trả `{'documents': [], 'facets': {'doc_type': []}, 'total': 0}` để test ACL chạy được, rồi Task 16 điền thân thật.

- [ ] **Step 4: Chạy test phân quyền, phải xanh**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: 6 test của `TestSearchAcl` xanh

**Nếu bất kỳ test nào trong `TestSearchAcl` đỏ, DỪNG LẠI.** Đây là kiểm soát bảo mật, không phải tính năng — không được đi tiếp task sau với nó đỏ.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add search service with ACL-first retrieval and RRF"
```

---

## Task 16: Kết quả — gom về văn bản, trích đoạn highlight, facet, nhật ký

**Files:**
- Modify: `custom-addons/aidt_search/models/search_service.py` (điền thân `_format`, `_format_from_chunks`)
- Create: `custom-addons/aidt_search/models/search_log.py`
- Modify: `custom-addons/aidt_search/models/__init__.py`, `security/ir.model.access.csv`
- Create: `custom-addons/aidt_search/tests/test_search_service.py`
- Modify: `custom-addons/aidt_search/tests/__init__.py`

**Interfaces:**
- Produces:
  - `aidt.search.log` với `log_search(parsed, document_ids, channels, duration_ms) -> record`, `action_click(document_id)`
  - `search()` trả dict đầy đủ: `documents: [{id, name, reference, doc_type, secrecy, date, department, snippets: [{text, heading_path, page}]}]`, `facets: {doc_type: [(label, count)], department: [...], year: [...], secrecy: [...]}`, `total`, `filters: [{field, label}]`, `reference`, `channels_used`, `degraded`

- [ ] **Step 1: Viết test thất bại**

`custom-addons/aidt_search/tests/test_search_service.py`:

```python
from unittest.mock import patch

from odoo.tests.common import TransactionCase

DIM = 1024


class SearchServiceCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.dept = cls.env['hr.department'].create({'name': 'Sở Tài chính'})
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Kế hoạch hỗ trợ hộ nghèo', 'direction': 'den',
            'secrecy': 'thuong', 'doc_type': 'ke_hoach',
            'reference': '145/KH-UBND', 'department_id': cls.dept.id,
            'date': '2025-06-15',
        })
        for seq, text in enumerate([
            'Bố trí kinh phí hỗ trợ hộ nghèo trên địa bàn tỉnh.',
            'Tổ chức thực hiện và báo cáo kết quả định kỳ.',
        ]):
            chunk = cls.env['aidt.doc.chunk'].create({
                'document_id': cls.doc.id, 'seq': seq, 'text': text,
                'embed_text': text, 'heading_path': 'Phần II › Mục 3', 'page': 2,
            })
            cls.env.cr.execute(
                "UPDATE aidt_doc_chunk SET embedding = %s::vector WHERE id = %s",
                (str([0.01] * DIM), chunk.id))

    def _search(self, query):
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          return_value=[[0.01] * DIM]):
            return self.env['aidt.search.service'].search(query)


class TestResultShape(SearchServiceCase):
    def test_gom_chunk_ve_don_vi_van_ban(self):
        # Người dùng nghĩ theo văn bản, không nghĩ theo chunk.
        docs = self._search('hỗ trợ hộ nghèo')['documents']
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['id'], self.doc.id)

    def test_moi_van_ban_kem_trich_doan(self):
        docs = self._search('hỗ trợ hộ nghèo')['documents']
        self.assertTrue(docs[0]['snippets'])
        self.assertLessEqual(len(docs[0]['snippets']), 3)

    def test_trich_doan_co_highlight(self):
        snippets = self._search('hộ nghèo')['documents'][0]['snippets']
        self.assertTrue(any('<b>' in s['text'] for s in snippets))

    def test_trich_doan_giu_duong_dan_muc_va_trang(self):
        snippet = self._search('hỗ trợ hộ nghèo')['documents'][0]['snippets'][0]
        self.assertEqual(snippet['heading_path'], 'Phần II › Mục 3')
        self.assertEqual(snippet['page'], 2)

    def test_metadata_van_ban_day_du(self):
        doc = self._search('hỗ trợ hộ nghèo')['documents'][0]
        for key in ('name', 'reference', 'doc_type', 'secrecy', 'date', 'department'):
            self.assertIn(key, doc)


class TestChipDaHieu(SearchServiceCase):
    def test_boc_filter_nam_va_bao_ve_ui(self):
        result = self._search('kế hoạch hỗ trợ hộ nghèo năm 2025')
        labels = [f['label'] for f in result['filters']]
        self.assertIn('Năm 2025', labels)

    def test_loc_nam_sai_thi_khong_ra_ket_qua(self):
        self.assertEqual(self._search('hỗ trợ hộ nghèo năm 2019')['documents'], [])

    def test_khong_co_filter_thi_danh_sach_rong(self):
        self.assertEqual(self._search('hỗ trợ hộ nghèo')['filters'], [])


class TestFacets(SearchServiceCase):
    def test_dem_theo_loai_van_ban(self):
        facets = self._search('hỗ trợ hộ nghèo')['facets']
        self.assertIn(('Kế hoạch', 1), facets['doc_type'])

    def test_dem_theo_don_vi(self):
        facets = self._search('hỗ trợ hộ nghèo')['facets']
        self.assertIn(('Sở Tài chính', 1), facets['department'])

    def test_dem_theo_nam(self):
        self.assertIn((2025, 1), self._search('hỗ trợ hộ nghèo')['facets']['year'])


class TestReferenceLookup(SearchServiceCase):
    def test_so_hieu_di_nhanh_sql(self):
        result = self._search('145/KH-UBND')
        self.assertEqual(result['reference'], '145/KH-UBND')
        self.assertEqual([d['id'] for d in result['documents']], [self.doc.id])

    def test_so_hieu_khong_ton_tai(self):
        self.assertEqual(self._search('999/XX-YYY')['documents'], [])


class TestDegradedMode(SearchServiceCase):
    def test_embed_chet_van_tra_ket_qua_lexical(self):
        # Một container chết không được làm chết cả tính năng.
        with patch.object(type(self.env['aidt.embed.client']), 'embed',
                          side_effect=RuntimeError('service down')):
            result = self.env['aidt.search.service'].search('hỗ trợ hộ nghèo')
        self.assertTrue(result['degraded'])
        self.assertTrue(result['documents'])
        self.assertNotIn('vector', result['channels_used'])


class TestSearchLog(SearchServiceCase):
    def test_moi_truy_van_sinh_mot_ban_ghi(self):
        before = self.env['aidt.search.log'].search_count([])
        self._search('hỗ trợ hộ nghèo')
        self.assertEqual(self.env['aidt.search.log'].search_count([]), before + 1)

    def test_ghi_lai_truy_van_goc_va_nguoi_dung(self):
        self._search('hỗ trợ hộ nghèo năm 2025')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertEqual(log.query_raw, 'hỗ trợ hộ nghèo năm 2025')
        self.assertEqual(log.user_id, self.env.user)

    def test_ghi_lai_ket_qua_va_kenh(self):
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        self.assertIn(self.doc.id, log.result_document_ids.ids)
        self.assertIn('lexical', log.channels_used)

    def test_ghi_lai_luot_click(self):
        self._search('hỗ trợ hộ nghèo')
        log = self.env['aidt.search.log'].search([], order='id desc', limit=1)
        log.action_click(self.doc.id)
        self.assertEqual(log.clicked_document_id, self.doc)
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run lệnh test Odoo như các task trước.
Expected: FAIL — `KeyError: 'aidt.search.log'`

- [ ] **Step 3: Viết `models/search_log.py`**

```python
from odoo import fields, models


class AidtSearchLog(models.Model):
    """Một bảng, hai nghĩa vụ.

    1. Nhật ký truy cập N-08 — P0, yêu cầu tuân thủ bắt buộc trong DMS,
       không phải tính năng phụ.
    2. Dữ liệu nuôi bộ eval của dự án con D.

    Bộ eval và cảnh báo truy cập bất thường nằm ngoài phạm vi spec này,
    nhưng dữ liệu để làm chúng tích luỹ từ ngày đầu.
    """

    _name = 'aidt.search.log'
    _description = 'Nhật ký tìm kiếm'
    _order = 'create_date desc, id desc'

    user_id = fields.Many2one(
        'res.users', string='Người tìm', required=True, index=True,
        default=lambda self: self.env.user)
    query_raw = fields.Char(string='Truy vấn gốc', required=True)
    query_semantic = fields.Char(string='Phần ngữ nghĩa')
    filters_json = fields.Json(string='Filter đã bóc')
    channels_used = fields.Char(string='Kênh đã dùng')
    degraded = fields.Boolean(string='Chạy giảm cấp')
    result_document_ids = fields.Many2many('aidt.document', string='Kết quả')
    clicked_document_id = fields.Many2one('aidt.document', string='Đã mở')
    duration_ms = fields.Integer(string='Thời gian (ms)')

    def action_click(self, document_id):
        self.ensure_one()
        self.sudo().clicked_document_id = document_id
        return True
```

- [ ] **Step 4: Điền thân `_format_from_chunks` và `_format` trong `search_service.py`**

Thay hai hàm tạm bằng:

```python
    @api.model
    def _snippets(self, chunk_ids, query_text):
        """Trích đoạn highlight bằng ts_headline, giữ nguyên thứ hạng RRF."""
        if not chunk_ids or not query_text:
            rows = self.env['aidt.doc.chunk'].sudo().browse(chunk_ids)
            return {c.id: {'text': (c.text or '')[:300], 'heading_path': c.heading_path,
                           'page': c.page, 'document_id': c.document_id.id} for c in rows}
        self.env.cr.execute("""
            SELECT c.id, c.document_id, c.heading_path, c.page,
                   ts_headline('simple', c.text,
                               websearch_to_tsquery('simple', %s),
                               'StartSel=<b>,StopSel=</b>,MaxFragments=2,MaxWords=30,MinWords=10')
              FROM aidt_doc_chunk c WHERE c.id = ANY(%s)
        """, (query_text, list(chunk_ids)))
        return {
            row[0]: {'document_id': row[1], 'heading_path': row[2] or '',
                     'page': row[3], 'text': row[4] or ''}
            for row in self.env.cr.fetchall()
        }

    @api.model
    def _facets(self, documents):
        """Đếm trên tập ĐÃ lọc quyền — con số facet cũng không được lộ sự
        tồn tại của văn bản mật."""
        labels = dict(self.env['aidt.document']._fields['doc_type'].selection)
        secrecy_labels = dict(self.env['aidt.document']._fields['secrecy'].selection)
        by_type, by_dept, by_year, by_secrecy = {}, {}, {}, {}
        for doc in documents:
            by_type[labels.get(doc.doc_type, '—')] = by_type.get(labels.get(doc.doc_type, '—'), 0) + 1
            name = doc.department_id.name or '—'
            by_dept[name] = by_dept.get(name, 0) + 1
            if doc.date:
                by_year[doc.date.year] = by_year.get(doc.date.year, 0) + 1
            key = secrecy_labels.get(doc.secrecy, '—')
            by_secrecy[key] = by_secrecy.get(key, 0) + 1
        srt = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], str(kv[0])))  # noqa: E731
        return {'doc_type': srt(by_type), 'department': srt(by_dept),
                'year': srt(by_year), 'secrecy': srt(by_secrecy)}

    @api.model
    def _serialize(self, document, snippets):
        return {
            'id': document.id,
            'name': document.name,
            'reference': document.reference or '',
            'doc_type': dict(document._fields['doc_type'].selection).get(document.doc_type, ''),
            'secrecy': dict(document._fields['secrecy'].selection).get(document.secrecy, ''),
            'date': fields.Date.to_string(document.date) if document.date else '',
            'department': document.department_id.name or '',
            'snippets': snippets[:SNIPPETS_PER_DOC],
        }

    @api.model
    def _format(self, parsed, documents, snippet_map, channels, degraded, started=None):
        grouped = {}
        for chunk_id, payload in snippet_map.items():
            grouped.setdefault(payload['document_id'], []).append(payload)
        results = [self._serialize(d, grouped.get(d.id, [])) for d in documents]
        duration = int((time.monotonic() - started) * 1000) if started else 0
        self.env['aidt.search.log'].sudo().create({
            'user_id': self.env.user.id,
            'query_raw': parsed.raw,
            'query_semantic': parsed.semantic,
            'filters_json': [{'field': f.field, 'label': f.label} for f in parsed.filters],
            'channels_used': ','.join(channels),
            'degraded': degraded,
            'result_document_ids': [(6, 0, documents.ids)],
            'duration_ms': duration,
        })
        return {
            'documents': results,
            'facets': self._facets(documents),
            'total': len(documents),
            'filters': [{'field': f.field, 'label': f.label} for f in parsed.filters],
            'reference': parsed.reference,
            'channels_used': channels,
            'degraded': degraded,
        }

    @api.model
    def _format_from_chunks(self, parsed, chunk_ids, allowed_sql, params,
                            channels, degraded, limit, started=None):
        snippet_map = self._snippets(chunk_ids, parsed.semantic)
        ordered_doc_ids = []
        for chunk_id in chunk_ids:
            doc_id = snippet_map.get(chunk_id, {}).get('document_id')
            if doc_id and doc_id not in ordered_doc_ids:
                ordered_doc_ids.append(doc_id)
        documents = self.env['aidt.document'].browse(ordered_doc_ids[:limit])
        return self._format(parsed, documents, snippet_map, channels, degraded, started)
```

Thêm `import time` vào đầu `search_service.py`, và trong `search()` đặt `started = time.monotonic()` ở dòng đầu rồi truyền xuống cả hai nhánh.

Cập nhật `models/__init__.py` thêm `from . import search_log`, `security/ir.model.access.csv` thêm hai dòng cho `model_aidt_search_log` (chuyên viên `1,1,1,0`, admin `1,1,1,1`), và `tests/__init__.py` thêm `test_search_service`.

- [ ] **Step 5: Chạy test, phải xanh**

Expected: `54 passed` (gồm cả 6 test ACL của Task 15 vẫn xanh)

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add result grouping, highlighted snippets, facets and search log"
```

---

## Task 17: Giao diện OWL — client action "Tìm kiếm thông minh"

**Files:**
- Create: `custom-addons/aidt_search/static/src/search_view.js`
- Create: `custom-addons/aidt_search/static/src/search_view.xml`
- Create: `custom-addons/aidt_search/static/src/search_view.scss`
- Create: `custom-addons/aidt_search/views/search_actions.xml`
- Create: `custom-addons/aidt_search/views/index_job_views.xml`
- Create: `custom-addons/aidt_search/views/aidt_document_views.xml`
- Modify: `custom-addons/aidt_search/__manifest__.py` (thêm `assets`, `data`)
- Create: `custom-addons/aidt_search/models/aidt_document.py` (badge `index_state`, `chunk_count`, nút chỉ mục lại)
- Create: `custom-addons/aidt_search/tests/test_document_badges.py`

**Interfaces:**
- Consumes: `aidt.search.service.search()` qua ORM RPC
- Produces: client action tag `aidt_search.search_view`; `aidt.document.index_state`, `chunk_count`, `action_reindex()`

- [ ] **Step 1: Viết test thất bại cho badge trên form văn bản**

```python
import base64

from odoo.tests.common import TransactionCase


class TestDocumentBadges(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.doc = cls.env['aidt.document'].create({
            'name': 'Văn bản thử', 'direction': 'den', 'secrecy': 'thuong'})

    def _file(self):
        return self.env['dms.file'].sudo().create({
            'name': 'a.docx', 'directory_id': self.doc.directory_id.id,
            'content': base64.b64encode(b'x'),
            'res_model': 'aidt.document', 'res_id': self.doc.id})

    def test_chua_co_tep_thi_none(self):
        self.assertEqual(self.doc.index_state, 'none')

    def test_co_job_pending_thi_pending(self):
        self._file()
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'pending')

    def test_job_done_thi_indexed(self):
        f = self._file()
        self.env['aidt.index.job'].search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'indexed')

    def test_job_failed_thi_failed(self):
        f = self._file()
        self.env['aidt.index.job'].search([('file_id', '=', f.id)]).write({'state': 'failed'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.index_state, 'failed')

    def test_dem_chunk(self):
        f = self._file()
        self.env['aidt.doc.chunk'].create({
            'document_id': self.doc.id, 'file_id': f.id, 'seq': 0,
            'text': 'a', 'embed_text': 'a'})
        self.doc.invalidate_recordset()
        self.assertEqual(self.doc.chunk_count, 1)

    def test_action_reindex_xep_lai_hang(self):
        f = self._file()
        Job = self.env['aidt.index.job']
        Job.search([('file_id', '=', f.id)]).write({'state': 'done'})
        self.doc.action_reindex()
        self.assertTrue(Job.search([('file_id', '=', f.id), ('state', '=', 'pending')]))
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Expected: FAIL — `AttributeError: 'aidt.document' object has no attribute 'index_state'`

- [ ] **Step 3: Viết `models/aidt_document.py`**

```python
from odoo import api, fields, models

# Ưu tiên hiển thị: lỗi phải nổi lên trên mọi trạng thái khác.
_PRIORITY = ('failed', 'pending', 'indexed')


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    index_state = fields.Selection(
        [('none', 'Chưa nạp'), ('pending', 'Đang xử lý'),
         ('indexed', 'Đã chỉ mục'), ('failed', 'Lỗi chỉ mục')],
        string='Trạng thái chỉ mục', compute='_compute_index_state', store=True)
    chunk_count = fields.Integer(string='Số đoạn', compute='_compute_chunk_count')

    @api.depends('directory_id.file_ids')
    def _compute_index_state(self):
        Job = self.env['aidt.index.job'].sudo()
        for doc in self:
            states = set(Job.search([('document_id', '=', doc.id)]).mapped('state'))
            if not states:
                doc.index_state = 'none'
                continue
            if 'failed' in states:
                doc.index_state = 'failed'
            elif states - {'done'}:
                doc.index_state = 'pending'
            else:
                doc.index_state = 'indexed'

    def _compute_chunk_count(self):
        Chunk = self.env['aidt.doc.chunk'].sudo()
        for doc in self:
            doc.chunk_count = Chunk.search_count([('document_id', '=', doc.id)])

    def action_reindex(self):
        self.env['aidt.index.job']._enqueue_document(self)
        return True
```

`index_state` là `store=True` nhưng `_compute` phụ thuộc trạng thái job — thêm vào `index_job.py` một hook để job đổi trạng thái thì làm mới văn bản:

```python
    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self.mapped('document_id')._compute_index_state()
        return res
```

- [ ] **Step 4: Chạy test, phải xanh**

Expected: `60 passed`

- [ ] **Step 5: Viết client action OWL**

`static/src/search_view.js`:

```javascript
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

export class AidtSearchView extends Component {
    static template = "aidt_search.SearchView";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            query: "",
            loading: false,
            searched: false,
            result: { documents: [], facets: {}, filters: [], total: 0, degraded: false },
            activeFacets: {},
        });
    }

    get facetDomain() {
        // Facet là bộ lọc PHỤ trên tập đã lọc quyền — không bao giờ mở rộng
        // phạm vi, chỉ thu hẹp. Quyền vẫn do ir.rule quyết ở phía server.
        const domain = [];
        for (const [field, value] of Object.entries(this.state.activeFacets)) {
            if (value !== undefined && value !== null) {
                domain.push([field, "=", value]);
            }
        }
        return domain;
    }

    async search() {
        if (!this.state.query.trim()) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.result = await this.orm.call(
                "aidt.search.service", "search",
                [this.state.query, this.facetDomain],
            );
            this.state.searched = true;
        } finally {
            this.state.loading = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.search();
        }
    }

    removeFilter(field) {
        // Chip "Đã hiểu" xoá được: người dùng luôn thấy hệ thống đã diễn giải
        // câu hỏi thế nào và sửa được khi nó hiểu sai.
        this.state.result.filters = this.state.result.filters.filter(
            (f) => f.field !== field
        );
        this.state.activeFacets[field] = undefined;
        this.search();
    }

    toggleFacet(field, value) {
        this.state.activeFacets[field] =
            this.state.activeFacets[field] === value ? undefined : value;
        this.search();
    }

    openDocument(documentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "aidt.document",
            res_id: documentId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("aidt_search.search_view", AidtSearchView);
```

`static/src/search_view.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
<t t-name="aidt_search.SearchView">
    <div class="o_aidt_search p-3">
        <div class="d-flex gap-2 mb-2">
            <input type="text" class="form-control form-control-lg"
                   placeholder="Ví dụ: văn bản nào về hỗ trợ hộ nghèo năm 2025"
                   t-model="state.query" t-on-keydown="onKeydown"/>
            <button class="btn btn-primary px-4" t-on-click="search"
                    t-att-disabled="state.loading">Tìm</button>
        </div>

        <div t-if="state.result.filters.length" class="mb-2 small">
            <span class="text-muted me-2">Đã hiểu:</span>
            <span t-foreach="state.result.filters" t-as="f" t-key="f.field"
                  class="badge text-bg-light border me-1">
                <t t-esc="f.label"/>
                <span class="ms-1 o_aidt_chip_x" t-on-click="() => this.removeFilter(f.field)">×</span>
            </span>
        </div>

        <div t-if="state.result.degraded" class="alert alert-warning py-2 small">
            Tìm kiếm ngữ nghĩa tạm ngưng — đang hiển thị kết quả theo từ khoá.
        </div>

        <div class="row" t-if="state.searched">
            <div class="col-3">
                <t t-foreach="Object.keys(state.result.facets)" t-as="field" t-key="field">
                    <div t-if="state.result.facets[field].length" class="mb-3">
                        <div class="fw-bold small text-uppercase text-muted mb-1"
                             t-esc="field"/>
                        <div t-foreach="state.result.facets[field]" t-as="row" t-key="row[0]"
                             class="o_aidt_facet d-flex justify-content-between"
                             t-att-class="{ 'fw-bold': state.activeFacets[field] === row[0] }"
                             t-on-click="() => this.toggleFacet(field, row[0])">
                            <span t-esc="row[0]"/>
                            <span class="text-muted" t-esc="row[1]"/>
                        </div>
                    </div>
                </t>
            </div>

            <div class="col-9">
                <div t-if="!state.result.documents.length" class="text-muted">
                    Không có kết quả phù hợp.
                </div>
                <div t-foreach="state.result.documents" t-as="doc" t-key="doc.id"
                     class="mb-3 pb-3 border-bottom">
                    <div class="d-flex align-items-center gap-2">
                        <a href="#" t-on-click.prevent="() => this.openDocument(doc.id)"
                           class="fw-bold" t-esc="doc.reference ? doc.doc_type + ' ' + doc.reference : doc.name"/>
                        <span class="badge text-bg-secondary" t-esc="doc.secrecy"/>
                    </div>
                    <div class="small text-muted" t-esc="doc.name"/>
                    <div t-foreach="doc.snippets" t-as="s" t-key="s_index" class="mt-1 small">
                        <span class="text-muted" t-if="s.heading_path">
                            <t t-esc="s.heading_path"/>
                            <t t-if="s.page"> · trang <t t-esc="s.page"/></t> —
                        </span>
                        <span t-out="s.text"/>
                    </div>
                </div>
            </div>
        </div>
    </div>
</t>
</templates>
```

`static/src/search_view.scss`:

```scss
.o_aidt_search {
    .o_aidt_facet { cursor: pointer; padding: 2px 0; }
    .o_aidt_facet:hover { text-decoration: underline; }
    .o_aidt_chip_x { cursor: pointer; font-weight: bold; }
    b { background: rgba(255, 230, 0, .45); font-weight: 600; }
}
```

`views/search_actions.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_aidt_search" model="ir.actions.client">
        <field name="name">Tìm kiếm thông minh</field>
        <field name="tag">aidt_search.search_view</field>
    </record>

    <menuitem id="menu_aidt_search"
              name="Tìm kiếm thông minh"
              parent="aidt_vanban_den.menu_unified_document_root"
              action="action_aidt_search"
              sequence="5"/>

    <menuitem id="menu_aidt_index_job"
              name="Hàng đợi chỉ mục"
              parent="aidt_vanban_den.menu_unified_document_root"
              action="action_aidt_index_job"
              groups="aidt_org.group_aidt_admin"
              sequence="90"/>
</odoo>
```

> Kiểm tra `xml_id` của menu cha bằng `grep -rn 'menu_unified_document_root' custom-addons/aidt_vanban_den/views/` trước khi chạy. Không khớp thì dùng đúng id có thật, **không** tạo menu gốc mới.

`views/index_job_views.xml` — list + form cho `aidt.index.job` với filter theo `state`, nút `action_retry`, và cột `error`, `attempt`, `stage_ms`. `views/aidt_document_views.xml` — thêm badge `index_state`, `chunk_count` và nút `action_reindex` vào form văn bản bằng view inheritance trên `aidt_vanban_den.view_aidt_document_form` (xác minh id thật trước).

Thêm vào `__manifest__.py`:

```python
    'assets': {
        'web.assets_backend': [
            'aidt_search/static/src/search_view.js',
            'aidt_search/static/src/search_view.xml',
            'aidt_search/static/src/search_view.scss',
        ],
    },
```

và bổ sung ba tệp view vào `data`.

- [ ] **Step 6: Nâng cấp module và kiểm tra giao diện tải được**

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
docker compose -f docker-compose.dev.yml logs odoo --tail=50 | grep -iE "error|traceback" || echo "sạch"
```

Mở `http://localhost:8069` → app Văn bản → **Tìm kiếm thông minh**. Ô tìm kiếm phải hiện, không có lỗi trong console trình duyệt.

- [ ] **Step 7: Commit**

```bash
git add custom-addons/aidt_search
git commit -m "feat(search): add OWL search client action with facets and understood-chips"
```

---

## Task 18: Kiểm chứng đầu-cuối trên `aidt_demo` và dọn dẹp

**Files:**
- Create: `docs/superpowers/plans/2026-08-01-e2e-verification.md`
- Modify: `custom-addons/aidt_search/README.md`

**Interfaces:**
- Consumes: toàn bộ hệ thống đã dựng
- Produces: bằng chứng đầu-cuối cho 7 tiêu chí hoàn thành ở §11 của spec

- [ ] **Step 1: Chạy toàn bộ hai bộ test**

```bash
cd /home/chauanphu/projects/aidt-odoo/custom-addons && python -m pytest aidt_search_engine/tests -q
cd /home/chauanphu/projects/aidt-odoo && docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -u aidt_search --test-enable --test-tags /aidt_search --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

Expected: thư viện ~112 passed; Odoo ~60 passed. **Cả hai phải xanh trước khi đi tiếp.**

- [ ] **Step 2: Nạp tài liệu thật và xem chunk sinh ra**

Trong Odoo: tạo văn bản đến, số ký hiệu `145/KH-UBND`, loại Kế hoạch, đính kèm `docs/demo/01-dat-chuan.pdf`. Đợi cron (≤1 phút) hoặc chạy tay:

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo shell -d aidt_demo --addons-path=/opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons <<'PY'
env['aidt.index.job']._cron_process()
env.cr.commit()
for c in env['aidt.doc.chunk'].search([], limit=10):
    print(f"[{c.seq}] {c.zone:<16} {c.heading_path:<24} {c.text[:60]}")
PY
```

Kiểm: `so_ky_hieu` bắt được `145/KH-UBND`; `noi_nhan` và `chu_ky` mỗi cái một chunk riêng; `heading_path` hợp lý.

- [ ] **Step 3: Chạy 5 truy vấn kịch bản**

| # | Truy vấn | Kỳ vọng |
|---|---|---|
| 1 | `hỗ trợ hộ nghèo` | Ra văn bản, có trích đoạn highlight |
| 2 | `ho tro ho ngheo` | **Cùng kết quả với #1** — kênh không dấu chạy |
| 3 | `145/KH-UBND` | Đúng một văn bản, `reference` khác `null`, không qua kênh vector |
| 4 | `kế hoạch năm 2026` | Chip "Đã hiểu" hiện `Năm 2026` **và** `Kế hoạch` |
| 5 | `an toàn thông tin quý III năm 2026` | Chip hiện `Quý III/2026`, kết quả lọc đúng khoảng |

Ghi kết quả thật (kể cả cái sai) vào `e2e-verification.md`.

- [ ] **Step 4: Kiểm chứng giảm cấp mềm**

```bash
docker compose -f docker-compose.dev.yml stop aidt-embed
```

Tìm lại truy vấn #1: phải **vẫn ra kết quả**, có dải cảnh báo vàng "Tìm kiếm ngữ nghĩa tạm ngưng". Rồi `docker compose -f docker-compose.dev.yml start aidt-embed`.

- [ ] **Step 5: Kiểm chứng phân quyền bằng tay**

Đăng nhập bằng một user chuyên viên thuộc phòng khác, tìm cùng truy vấn → **không thấy văn bản mật, và số trên facet không đếm nó**. Đây là V-13; test tự động đã phủ nhưng vẫn phải nhìn tận mắt một lần.

- [ ] **Step 6: Dọn database theo quy ước CLAUDE.md**

```bash
docker compose -f docker-compose.dev.yml exec db psql -U odoo -d postgres -c "\l"
docker compose -f docker-compose.dev.yml exec odoo ls /var/lib/odoo/filestore/
```

Chỉ được còn `aidt_demo` (ngoài database hệ thống của Postgres). Có `aidt_test` hay bất kỳ DB scratch nào thì:

```bash
docker compose -f docker-compose.dev.yml exec db psql -U odoo -d postgres -c "DROP DATABASE aidt_test;"
docker compose -f docker-compose.dev.yml exec odoo rm -rf /var/lib/odoo/filestore/aidt_test
```

- [ ] **Step 7: Viết README module và commit**

`custom-addons/aidt_search/README.md`: mục đích module, sơ đồ đường ống, bảng tham số `ir.config_parameter`, cách chạy hai bộ test, cách xử lý job `failed`, và **liên kết tới spec**.

```bash
git add custom-addons/aidt_search/README.md docs/superpowers/plans/2026-08-01-e2e-verification.md
git commit -m "docs(search): add module README and end-to-end verification record"
```

---

## Self-Review

**1. Phủ spec** — đối chiếu từng mục:

| Spec | Task |
|---|---|
| §2.1 hai module | 3 (`aidt_search_engine`), 12 (`aidt_search`) |
| §2.2 hạ tầng | 2 |
| §3.1 `aidt.doc.chunk` | 12 |
| §3.2 `aidt.index.job` | 13 |
| §3.3 `index_state`, `chunk_count` | 17 |
| §3.4 `aidt.search.log` | 16 |
| §4.1 kích hoạt + hook `reference` | 13 |
| §4.2 worker, SKIP LOCKED, ngân sách | 13 |
| §4.3 chống trùng | 13 |
| §4.4 cây định tuyến | 14 |
| §4.5 cấu trúc trung gian + công thức OCR | 9, 11 |
| §4.6 chunking + header | 5, 6 |
| §4.7 ghi chỉ mục | 14 |
| §5.1 định tuyến ý định | 7, 15 |
| §5.2 RRF | 8 |
| §5.3 khe cắm reranker | 8 |
| §5.4 lọc quyền | 15 |
| §5.5 gom về văn bản | 16 |
| §5.6 giảm cấp mềm | 15, 16 |
| §5.7 giao diện | 17 |
| §6.1 hai loại lỗi | 13 |
| §6.2 ba bẫy im lặng | 11 (OCR rỗng), 14 (số chiều), 16 (kho rỗng vs không kết quả) |
| §6.3 vận hành | 17 |
| §7 R1/R2/R3 | 1, 2 |
| §8 kiểm thử ba tầng | rải khắp; tầng 3 ở 18 |
| §11 tiêu chí hoàn thành | 18 |

Không có mục nào của spec thiếu task.

**2. Quét placeholder** — không có "TBD"/"TODO"/"tương tự Task N". Hai chỗ cố ý viết mô tả thay vì code đầy đủ, và cả hai đều nêu rõ cách tự kiểm chứng: `views/index_job_views.xml` + `views/aidt_document_views.xml` (Task 17) phải `grep` xml_id thật của menu và form cha trước khi viết, vì đoán sai id thì module không cài được.

**3. Nhất quán kiểu** — `Block`/`Chunk`/`DocMeta` khai ở Task 3 dùng đúng tên ở Task 5, 6, 9, 10, 11, 14. `parse_query()` trả `ParsedQuery` với `.raw/.semantic/.reference/.filters` — dùng nhất quán ở Task 7, 15, 16. `_mark_transient`/`_mark_permanent`/`_mark_done` khai ở Task 13, gọi ở Task 14. `embed()` khai ở Task 14, gọi ở Task 15.

**Ba điểm lệch đã sửa trong lúc soát:**
- §4.6 của spec liệt kê `\d+.` và `[a-zđ])` là ranh giới **cứng**; làm vậy thì một danh sách 20 gạch đầu dòng thành 20 chunk tí hon. Kế hoạch dùng ba bậc (cứng / mềm / ranh giới câu) và **spec đã được cập nhật cho khớp**.
- `_format`/`_format_from_chunks` được gọi ở Task 15 nhưng viết thân ở Task 16 — đã ghi rõ ở Task 15 là để tạm trả dict rỗng, nếu không người thực thi Task 15 sẽ bí.
- `aidt.index.pipeline` bị `TestDedup` (Task 13) patch trước khi Task 14 viết nó — đã ghi cách tạo `AbstractModel` rỗng trước.

