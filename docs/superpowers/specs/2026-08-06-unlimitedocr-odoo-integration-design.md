# Design Spec: Integration of UnlimitedOCR & FastAPI AI Pipeline into AIDT Odoo (Văn bản đến / action-367)

**Date**: 2026-08-06  
**Target Branch**: `dev/nhan`  
**Repository**: `aidt-odoo` (`https://github.com/chauanphu/aidt-odoo`)  
**Status**: Approved by User  

---

## 🎯 Executive Summary

Targeting Odoo 19 `aidt_vanban_den` (Incoming Document Management, viewable at `http://192.168.92.139:8069/odoo/action-367`), this project integrates a multi-container multimodal AI extraction microservice into the Odoo ecosystem. 

When users click **"Trích xuất AI (OCR)"** on the Incoming Document form or wizard, the system passes uploaded PDF files to the FastAPI AI Pipeline (`http://aidt-pipeline:8001/api/pipeline/process`). The pipeline utilizes UnlimitedOCR and Ollama (Gemma 4 12B QAT) to extract 15 administrative metadata fields adhering to Vietnam **Decree 30/2020/NĐ-CP**, automatically populating the `aidt.document` record fields and attaching the original file to Odoo DMS.

---

## 🏛️ Architecture & Microservices Topology

### 1. Docker Compose Services & Port Matrix

All AI microservices and Odoo operate under a unified Docker network (`aidt-odoo-dev-network`) defined in `docker-compose.dev.yml`:

| Service Name | Container Name | Host:Container Port | Description & Engine |
| :--- | :--- | :--- | :--- |
| **`odoo`** | `aidt-odoo-dev-odoo-1` | `8069:8069` | Core Odoo 19 ERP Server |
| **`db`** | `aidt-odoo-dev-db-1` | `5432:5432` | PostgreSQL 16 + pgvector 0.8.6 |
| **`aidt-pipeline`** | `aidt-odoo-dev-pipeline-1` | `8001:8001` | FastAPI Orchestration Service (15-field Decree 30 parser) |
| **`aidt-embed`** | `aidt-odoo-dev-embed-1` | `8002:8001` | vLLM Vietnamese Embedding Server (`AITeamVN/Vietnamese_Embedding`) |
| **`aidt-ocr`** | `aidt-odoo-dev-ocr-1` | `8003:8000` | UnlimitedOCR Raw Engine (*Standardized from 3000 -> 8003*) |
| **`ollama`** | `aidt-odoo-dev-ollama-1` | `11434:11434` | Ollama LLM Engine (`gemma-4-12b-it-qat-q4_0:latest`) |

### 2. Network Communication & Dynamic Configuration
- Inter-container calls communicate over internal Docker DNS (`http://aidt-pipeline:8001`).
- Odoo stores the pipeline API URL in System Parameters (`ir.config_parameter` key `aidt_dms.pipeline_url`, default `http://aidt-pipeline:8001`).

---

## 🧩 Odoo Integration & Data Mapping (`aidt_dms` & `aidt_vanban_den`)

### 1. Wizard Enhancement (`aidt.document.ocr_wizard`)
- **Module Path**: `custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`
- **Field Addition**: Option `('unlimited_ocr_pipeline', 'UnlimitedOCR + Gemma 4 Pipeline (Nghị định 30)')` added to `ai_engine` field, set as `default='unlimited_ocr_pipeline'`.
- **Workflow**:
  1. User clicks **"Trích xuất AI (OCR)"** on `action-367` form.
  2. Uploads/selects PDF file scan in wizard.
  3. Clicking **"Thực hiện OCR"** triggers `action_start_ocr()`:
     - Encodes uploaded file into bytes and POSTs to `/api/pipeline/process`.
     - Receives structured JSON response with 15 Decree 30 fields.
     - Auto-populates `aidt.document` record fields and creates a linked `dms.file` attachment.

### 2. Decree 30 Field Mapping Specification

| AI Pipeline JSON Key | Target Field in `aidt.document` | Data Type | Field Label |
| :--- | :--- | :--- | :--- |
| `so_den` | `so_den` | Char / Integer | Số đến trong sổ |
| `ngay_den` | `ngay_den` | Date (`YYYY-MM-DD`) | Ngày đến nhận văn bản |
| `so_ky_hieu` | `so_ky_hieu_gui` | Char | Số / Ký hiệu gốc (e.g. `185/CV-STTTT`) |
| `ngay_ban_hanh` | `ngay_ban_hanh_gui` | Date (`YYYY-MM-DD`) | Ngày ký / ban hành gốc |
| `co_quan_ban_hanh` | `co_quan_gui` | Char | Cơ quan ban hành gốc |
| `trich_yeu` | `name` | Text | Trích yếu nội dung văn bản |
| `loai_van_ban` | `doc_type` | Selection | Loại văn bản (Công văn, Quyết định, Kế hoạch...) |
| `do_khan` | `do_khan` | Selection | Thường, Khẩn, Thượng khẩn, Hỏa tốc |
| `do_mat` | `do_mat` | Selection | Thường, Mật, Tối mật, Tuyệt mật |
| `han_xu_ly` | `han_xu_ly` | Date (`YYYY-MM-DD`) | Hạn xử lý văn bản |
| `nguoi_ky` | `nguoi_ky` | Char | Họ tên người ký |
| `chuc_vu_nguoi_ky` | `chuc_vu_nguoi_ky` | Char | Chức vụ người ký ban hành |
| `noi_nhan` | `noi_nhan` | Text | Nơi nhận / Đơn vị phối hợp |
| `so_trang` | `so_trang` | Integer | Tổng số trang |
| `trang_thai` | `state` | Selection | Trạng thái tiếp nhận initial state (`tiep_nhan`) |

---

## 🛡️ Error Handling & Verification Plan

### 1. Robust Exception Handling
- **Timeout / Offline Protection**: HTTP request to 8001 handles timeout (30s max). If offline or failing, raises a clean user-facing Odoo Warning (`UserError`) asking the user to retry or input manually without crashing the Odoo session.
- **Unicode & Date Normalization**: Handles Vietnamese `Đ` character in reference codes (e.g., `1486/QĐ-TTg`) and formats local dates (`DD/MM/YYYY`) into standard ISO format (`YYYY-MM-DD`).

### 2. End-to-End Verification Steps
1. **Docker Health Check**: Run `docker compose -f docker-compose.dev.yml up -d` and verify services `odoo`, `db`, `aidt-pipeline`, `aidt-embed`, `aidt-ocr`, and `ollama` are healthy.
2. **Port 8003 & 8001 Health Verification**: Verify `http://localhost:8003/v1/ocr` and `http://localhost:8001/api/health` return online status for both OCR and Ollama.
3. **Odoo UI Action Test**: Navigate to `http://192.168.92.139:8069/odoo/action-367`, click "Trích xuất AI (OCR)", upload `test_vanban_1.pdf`, and verify all 15 metadata fields populate accurately into the document record.
