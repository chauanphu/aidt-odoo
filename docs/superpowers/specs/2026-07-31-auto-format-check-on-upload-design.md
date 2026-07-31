# Design Specification: Automatic Document Format Check on File Upload

## 1. Overview
Currently, document format checking against Party & State regulations (e.g. Quy định 66-QĐ/TW, Nghị định 30/2020/NĐ-CP) in `aidt_format` requires manual execution via a button click and wizard modal (`aidt.format.check.wizard`). Furthermore, the fields `format_ok` and `format_note` on `aidt.document` are static placeholders and do not automatically reflect format compliance upon file upload.

This design specifies the implementation of **automatic format checking upon `.docx` file upload** for both Incoming ("Văn bản đến") and Outgoing ("Văn bản đi") documents in `aidt.document`.

---

## 2. Architecture & Data Flow

```
[ User Uploads .docx File ]
         │
         ▼
[ ir.attachment.create() / write() ]
         │
         ├─► (res_model == 'aidt.document' & file is .docx?)
         │        │ YES
         │        ▼
         │   [ aidt.document._auto_check_format() ]
         │        │
         │        ├─► Search active aidt.format.ruleset
         │        ├─► Call aidt.format.checker.check(raw_docx_bytes)
         │        ▼
         │   [ Compute format_ok & format_note ]
         │        │
         │        ├─► format_ok = (error_count == 0)
         │        └─► format_note = Summary string of errors & warnings
         │        ▼
         └─► [ Update aidt.document fields ]
```

---

## 3. Detailed Component Specification

### 3.1. `ir.attachment` Model Extension (`custom-addons/aidt_format/models/ir_attachment.py`)
- Extend `ir.attachment` model:
  - Override `create(vals_list)`: After creating attachments, identify those linked to `res_model == 'aidt.document'` with `.docx` extension/mimetype. Trigger `_auto_check_format()` on the target `aidt.document` records.
  - Override `write(vals)`: If `datas`, `db_datas`, `raw`, or file attributes change for attachments linked to `aidt.document`, re-trigger `_auto_check_format()` on the target document.

### 3.2. `aidt.document` Model Extension (`custom-addons/aidt_format/models/aidt_document.py`)
- Ensure `format_ok` (`Boolean`) and `format_note` (`Text`) fields are defined in `aidt_format/models/aidt_document.py` (or inherited cleanly across `aidt_vanban_den` and `aidt_vanban_di`).
- Implement `_auto_check_format(self)`:
  - Searches for the latest attached `.docx` file for `self`.
  - If no `.docx` attachment exists, resets `format_ok = False` and `format_note = False`.
  - Reads binary bytes of the docx attachment and runs `self.env['aidt.format.checker'].check(content, ruleset)`.
  - Calculates:
    - `errors`: Findings with `severity == 'error'`
    - `warnings`: Findings with `severity == 'warning'`
    - `format_ok = (len(errors) == 0)`
    - `format_note`: Formatted summary, e.g.:
      `"Đạt thể thức (0 lỗi, 2 cảnh báo)"` or `"Không đạt thể thức (3 lỗi chặn, 1 cảnh báo): \n- [Thần chú] Cần 13pt, đang 14pt..."`
  - Updates `self.sudo().write({'format_ok': format_ok, 'format_note': format_note})`.

### 3.3. `aidt.format.check.wizard` Update (`custom-addons/aidt_format/models/format_check_wizard.py`)
- Update `action_kiem_tra()`:
  - If the wizard was launched from an `aidt.document` record (context `active_model == 'aidt.document'` and `active_id`), after running the check lines, also update the parent `aidt.document`'s `format_ok` and `format_note`.

### 3.4. View Integration
- **Văn bản đến (`custom-addons/aidt_vanban_den/views/vanban_den_views.xml` or `aidt_format/views/format_document_views.xml`)**:
  - Display `format_ok` badge/widget and `format_note` on the form view.
- **Văn bản đi (`custom-addons/aidt_vanban_di/views/vanban_di_views.xml`)**:
  - Ensure `format_ok` and `format_note` are displayed in the form header/notebook section cleanly with status indicators.

---

## 4. Verification & Testing Plan

### 4.1. Automated Unit Tests (`custom-addons/aidt_format/tests/test_auto_format_check.py`)
1. **Test Auto Check on Attachment Upload**:
   - Create an `aidt.document` record.
   - Upload a sample valid `.docx` `ir.attachment` linked to the record.
   - Verify `_auto_check_format()` triggers automatically, setting `format_ok = True` and updating `format_note`.
2. **Test Failure Handling on Non-compliant `.docx`**:
   - Upload a non-compliant `.docx` file (with wrong margins/fonts).
   - Verify `format_ok = False` and `format_note` lists specific error rules.
3. **Test Attachment Deletion/Replacement**:
   - Upload new attachment or delete attachment and verify status updates accordingly.
4. **Test Manual Wizard Synchronization**:
   - Execute wizard from document form and verify parent record `format_ok` and `format_note` sync with wizard output.

---

## 5. Security & Performance
- **Performance**: Executing docx zip extraction and XML inspection takes ~50ms per file, negligible impact on upload request latency.
- **Error Handling**: Wrapped in try-except block inside `_auto_check_format` so that if an invalid file format or corrupted docx is uploaded, it sets `format_ok = False` and logs a user-friendly message without breaking the attachment upload process.
