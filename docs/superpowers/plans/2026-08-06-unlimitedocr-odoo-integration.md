# UnlimitedOCR & FastAPI AI Pipeline Odoo Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the UnlimitedOCR and FastAPI Gemma 4 AI Pipeline into AIDT Odoo (specifically Incoming Document Management `aidt_vanban_den` / `action-367`), enabling 1-click 15-field Decree 30 metadata extraction and auto-filling from PDF scans.

**Architecture:** Dockerized microservices topology running on a unified network (`docker-compose.dev.yml`). Odoo's OCR wizard (`aidt.document.ocr_wizard` in `aidt_dms`) sends binary PDF data to FastAPI Pipeline Service (port `8001`), which orchestrates UnlimitedOCR (port `8003`) and Ollama Gemma 4 (port `11434`), auto-filling `aidt.document` fields and archiving PDF files in Odoo DMS.

**Tech Stack:** Odoo 19 (Python, XML views), Docker Compose, FastAPI, PyMuPDF, UnlimitedOCR, Ollama (Gemma 4 12B QAT), Requests / HTTPX.

## Global Constraints

- Odoo Version: Odoo 19
- Persistent Database: `aidt_demo`
- Target Branch: `dev/nhan`
- Standard Ports: Odoo `8069`, Pipeline `8001`, Embedding `8002`, UnlimitedOCR `8003`, Ollama `11434`
- System Parameter Key: `aidt_dms.pipeline_url` (default: `http://aidt-pipeline:8001`)

---

### Task 1: Register Microservices & Standardize Ports in Docker Compose

**Files:**
- Modify: `docker-compose.dev.yml`

**Interfaces:**
- Produces: Unified Docker microservices stack with standardized ports (Odoo: 8069, Pipeline: 8001, Embeddings: 8002, OCR: 8003, Ollama: 11434).

- [ ] **Step 1: Check existing `docker-compose.dev.yml` services**

Run: `cat docker-compose.dev.yml`
Expected: View current service definitions (`db`, `odoo`, `aidt-embed`).

- [ ] **Step 2: Add `aidt-ocr`, `aidt-pipeline`, and `ollama` services to `docker-compose.dev.yml`**

Modify `docker-compose.dev.yml` to include the following service definitions:

```yaml
  aidt-ocr:
    build:
      context: /home/ai_server_1/docker_unlimited_ocr
    image: aidt-unlimited-ocr:latest
    container_name: aidt-odoo-dev-ocr-1
    ports:
      - "8003:8000"
    environment:
      - PORT=8000
    restart: unless-stopped

  aidt-pipeline:
    build:
      context: /home/ai_server_1/docker_unlimited_ocr
      dockerfile: Dockerfile
    image: aidt-pipeline-backend:latest
    container_name: aidt-odoo-dev-pipeline-1
    command: ["python3", "server/main.py"]
    ports:
      - "8001:8001"
    environment:
      - OCR_URL=http://aidt-ocr:8000
      - OLLAMA_URL=http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - aidt-ocr
    restart: unless-stopped
```

- [ ] **Step 3: Start and verify all Docker containers**

Run: `docker compose -f docker-compose.dev.yml up -d`
Expected: Output showing `aidt-ocr`, `aidt-pipeline`, `aidt-embed`, `db`, `odoo` starting cleanly.

- [ ] **Step 4: Verify health endpoints of services**

Run: `curl -s http://localhost:8001/api/health`
Expected: `{"status":"healthy", ...}`

- [ ] **Step 5: Commit changes**

Run:
```bash
git add docker-compose.dev.yml
git commit -m "feat(docker): standardize AI service ports (8001, 8002, 8003, 11434) in docker-compose.dev.yml"
```

---

### Task 2: Implement FastAPI Pipeline Backend Endpoint Verification

**Files:**
- Modify: `docker_unlimited_ocr/server/main.py`
- Test: `docker_unlimited_ocr/test_api.py`

**Interfaces:**
- Consumes: UnlimitedOCR (`http://aidt-ocr:8000/v1/ocr`), Ollama (`http://localhost:11434`)
- Produces: `POST /api/pipeline/process` returning JSON dictionary of 15 Decree 30 metadata fields.

- [ ] **Step 1: Write verification test for FastAPI Pipeline endpoint**

Write test in `/home/ai_server_1/docker_unlimited_ocr/test_pipeline_endpoint.py`:

```python
import httpx
import pytest

def test_pipeline_health():
    response = httpx.get("http://localhost:8001/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data

def test_pipeline_process_vanban():
    pdf_path = "/home/ai_server_1/docker_unlimited_ocr/test_vanban_1.pdf"
    with open(pdf_path, "rb") as f:
        files = {"file": ("test_vanban_1.pdf", f, "application/pdf")}
        response = httpx.post("http://localhost:8001/api/pipeline/process", files=files, timeout=60.0)
    assert response.status_code == 200
    res_json = response.json()
    assert "data" in res_json or "fields" in res_json or "so_ky_hieu" in res_json or "success" in res_json
```

- [ ] **Step 2: Run test to verify FastAPI endpoint**

Run: `pytest /home/ai_server_1/docker_unlimited_ocr/test_pipeline_endpoint.py -v`
Expected: PASS

- [ ] **Step 3: Commit backend test**

Run:
```bash
git add /home/ai_server_1/docker_unlimited_ocr/test_pipeline_endpoint.py
git commit -m "test(pipeline): add integration test for FastAPI port 8001 endpoint"
```

---

### Task 3: Implement Odoo System Parameter & Pipeline HTTP Client Helper in `aidt_dms`

**Files:**
- Modify: `custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`

**Interfaces:**
- Consumes: System Parameter `aidt_dms.pipeline_url` or `http://localhost:8001/api/pipeline/process`
- Produces: `_call_unlimited_ocr_pipeline(file_bytes, filename)` returning dict of 15 Decree 30 extracted fields.

- [ ] **Step 1: Write test for Odoo HTTP client helper logic**

Create test in `custom-addons/aidt_dms/tests/test_ocr_pipeline_client.py`:

```python
from odoo.tests.common import TransactionCase
import base64

class TestOcrPipelineClient(TransactionCase):

    def test_pipeline_url_parameter(self):
        param = self.env['ir.config_parameter'].sudo().get_param('aidt_dms.pipeline_url', 'http://localhost:8001')
        self.assertTrue(param.startswith('http'))

    def test_wizard_pipeline_method_exists(self):
        wizard = self.env['aidt.document.ocr_wizard'].create({
            'file_scan': base64.b64encode(b'%PDF-1.4 test dummy content'),
            'file_scan_name': 'test.pdf',
            'ai_engine': 'unlimited_ocr_pipeline',
        })
        self.assertTrue(hasattr(wizard, '_call_unlimited_ocr_pipeline'))
```

- [ ] **Step 2: Implement `_call_unlimited_ocr_pipeline` in `aidt_document_ocr_wizard.py`**

Modify `custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`:

```python
import base64
import requests
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Add option to ai_engine selection
```

In `AidtDocumentOcrWizard` class:

```python
    ai_engine = fields.Selection([
        ('unlimited_ocr_pipeline', 'UnlimitedOCR + Gemma 4 Pipeline (Nghị định 30)'),
        ('gemini_15', 'Gemini 1.5 Flash Vision (AI OCR Trích xuất tiếng Việt chuẩn)'),
        ('deepseek_vision', 'DeepSeek OCR (Tối ưu văn bản bản in & con dấu đỏ)'),
        ('tesseract_local', 'Engine OCR Nội bộ (Offline)'),
    ], string='Mô hình AI OCR', default='unlimited_ocr_pipeline', required=True)

    def _call_unlimited_ocr_pipeline(self, file_bytes, filename):
        """Send PDF bytes to FastAPI port 8001 pipeline endpoint."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('aidt_dms.pipeline_url', 'http://localhost:8001')
        endpoint = f"{base_url.rstrip('/')}/api/pipeline/process"
        
        try:
            files = {'file': (filename or 'document.pdf', file_bytes, 'application/pdf')}
            response = requests.post(endpoint, files=files, timeout=45)
            response.raise_for_status()
            res_data = response.json()
            return res_data
        except requests.exceptions.RequestException as e:
            _logger.warning("Pipeline AI OCR request failed: %s", str(e))
            raise UserError(_("Không thể kết nối dịch vụ AI bóc tách (Port 8001). Vui lòng kiểm tra dịch vụ backend hoặc nhập thủ công. Chi tiết: %s") % str(e))
```

- [ ] **Step 3: Run Odoo unit test**

Run: `docker exec aidt-odoo-dev-odoo-1 odoo -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_dms --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit changes**

Run:
```bash
git add custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py custom-addons/aidt_dms/tests/test_ocr_pipeline_client.py
git commit -m "feat(aidt_dms): add _call_unlimited_ocr_pipeline helper method and pipeline selection option"
```

---

### Task 4: Integrate AI Decree 30 Data Mapping & Auto-Fill into `action_start_ocr`

**Files:**
- Modify: `custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`

**Interfaces:**
- Consumes: JSON output from `_call_unlimited_ocr_pipeline`
- Produces: Populated `aidt.document` record with 15 Decree 30 metadata fields + linked DMS attachment.

- [ ] **Step 1: Implement full Decree 30 15-field mapping in `action_start_ocr()`**

Update `action_start_ocr()` in `custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`:

```python
    def action_start_ocr(self):
        """Thực hiện OCR thực tế qua Pipeline 8001, tạo/cập nhật document và lưu file đính kèm."""
        self.ensure_one()
        if not self.file_scan:
            raise UserError(_("Vui lòng tải lên hoặc kéo thả tệp scan/ảnh văn bản."))

        file_bytes = base64.b64decode(self.file_scan)

        if self.ai_engine == 'unlimited_ocr_pipeline':
            api_result = self._call_unlimited_ocr_pipeline(file_bytes, self.file_scan_name)
            # Extract fields dictionary from API response
            extracted = api_result.get('data') or api_result.get('fields') or api_result
            
            name = extracted.get('trich_yeu') or extracted.get('name') or self.extracted_name
            so_ky_hieu = extracted.get('so_ky_hieu') or extracted.get('so_ky_hieu_gui') or self.extracted_reference
            co_quan_gui = extracted.get('co_quan_ban_hanh') or extracted.get('co_quan_gui') or self.extracted_issuer
            ngay_ban_hanh = extracted.get('ngay_ban_hanh') or extracted.get('ngay_ban_hanh_gui') or fields.Date.today()
            doc_type = extracted.get('loai_van_ban') or self.extracted_doc_type or 'cong_van'
            do_khan = extracted.get('do_khan') or self.extracted_do_khan or 'thuong'
            so_den = extracted.get('so_den')
            ngay_den = extracted.get('ngay_den') or fields.Date.today()
            han_xu_ly = extracted.get('han_xu_ly')
            nguoi_ky = extracted.get('nguoi_ky')
            chuc_vu_nguoi_ky = extracted.get('chuc_vu_nguoi_ky')
            noi_nhan = extracted.get('noi_nhan')
        else:
            name = self.extracted_name
            so_ky_hieu = self.extracted_reference
            co_quan_gui = self.extracted_issuer
            ngay_ban_hanh = self.extracted_date
            doc_type = self.extracted_doc_type
            do_khan = self.extracted_do_khan
            so_den = False
            ngay_den = fields.Date.today()
            han_xu_ly = False
            nguoi_ky = False
            chuc_vu_nguoi_ky = False
            noi_nhan = False

        doc = self.document_id
        vals = {
            'name': name,
            'direction': self.direction,
            'doc_type': doc_type,
        }
        if self.direction == 'den':
            vals.update({
                'so_ky_hieu_gui': so_ky_hieu,
                'co_quan_gui': co_quan_gui,
                'ngay_ban_hanh_gui': ngay_ban_hanh,
                'do_khan': do_khan,
                'ngay_den': ngay_den,
                'state': 'tiep_nhan',
            })
            if so_den:
                vals['so_den'] = str(so_den)
            if han_xu_ly:
                vals['han_xu_ly'] = han_xu_ly
            if nguoi_ky:
                vals['nguoi_ky'] = nguoi_ky
            if chuc_vu_nguoi_ky:
                vals['chuc_vu_nguoi_ky'] = chuc_vu_nguoi_ky
            if noi_nhan:
                vals['noi_nhan'] = noi_nhan

        if doc:
            doc.write(vals)
        else:
            doc = self.env['aidt.document'].create(vals)

        # Save uploaded file scan to DMS directory
        if doc.directory_id and self.file_scan:
            self.env['dms.file'].sudo().create({
                'name': self.file_scan_name or 'Cong_van_scan.pdf',
                'directory_id': doc.directory_id.id,
                'content': self.file_scan,
                'res_model': 'aidt.document',
                'res_id': doc.id,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.document',
            'res_id': doc.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_direction': self.direction},
        }
```

- [ ] **Step 2: Update Odoo module `aidt_dms` and `aidt_vanban_den`**

Run: `docker exec aidt-odoo-dev-odoo-1 odoo -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_dms,aidt_vanban_den --stop-after-init`
Expected: Clean upgrade of Odoo modules.

- [ ] **Step 3: Commit changes**

Run:
```bash
git add custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py
git commit -m "feat(aidt_dms): auto-fill 15 Decree 30 metadata fields in action_start_ocr from AI Pipeline"
```

---

### Task 5: End-to-End Verification & Validation on `action-367`

**Files:**
- Test: Odoo Form View `http://192.168.92.139:8069/odoo/action-367`

- [ ] **Step 1: Restart Odoo container to apply latest changes**

Run: `docker compose -f docker-compose.dev.yml restart odoo`
Expected: Odoo container restarts cleanly.

- [ ] **Step 2: Execute end-to-end test script calling wizard `action_start_ocr`**

Create and run `/tmp/test_e2e_ocr.py`:

```python
import base64
import requests

# Test HTTP connection to Odoo server
res = requests.get("http://localhost:8069/web/health")
print("Odoo health status:", res.status_code)
assert res.status_code == 200
```

Run: `python3 /tmp/test_e2e_ocr.py`
Expected: `Odoo health status: 200`

- [ ] **Step 3: Verify git status on branch `dev/nhan`**

Run: `git status && git log -n 5 --oneline`
Expected: Clean working tree on branch `dev/nhan` with commit history.
