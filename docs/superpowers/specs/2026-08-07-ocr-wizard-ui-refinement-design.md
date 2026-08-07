# Design Spec: OCR Wizard UI Refinement & Formatting

**Date:** 2026-08-07  
**Status:** Approved by User  

---

## 1. Overview & Objective
Refine the Odoo OCR Preview Wizard frontend UI (`aidt_document_ocr_wizard_views.xml`) and backend date formatters (`pipeline.py`) to deliver a modern, premium user experience.

---

## 2. Key Design Enhancements

### 2.1 Gemini Star SVG Badge ("Gợi ý AI")
- Replace standard text badges with the four-point Gemini Sparkle Star SVG icon (`<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">`).
- Keep badge hidden when fields are empty or unassigned.

### 2.2 Strict Vietnamese Date Normalization (`DD/MM/YYYY`)
- Replace any English short-month dates (e.g. `Aug 7`, `Aug 07`, `7 Aug`) with standard Vietnamese numeric date strings (e.g. `07/08/2026`).
- Ensure all backend pipeline output and Odoo wizard date fields enforce `DD/MM/YYYY` formatting.

### 2.3 Minimalist SVG Icons for AI Reasoning Log
- Replace raw unicode emojis (`📌` pin, `🧠` brain) in `ly_do_phan_cong` / `extracted_reasoning` with SVG vector icons:
  - **Pin Icon**: Vector Bookmark / Pin SVG icon.
  - **AI Mind Icon**: Vector Gemini Sparkle Lightbulb SVG icon.

---

## 3. Files Impacted
1. `/home/ai_server_1/aidt-odoo/custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard_views.xml`
2. `/home/ai_server_1/docker_unlimited_ocr/server/pipeline.py`
3. `/home/ai_server_1/aidt-odoo/custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`

---

## 4. Verification Plan
- Run automated python tests to verify `format_to_vn_date('Aug 7')` outputs `'07/08/2026'`.
- Restart Odoo container and upgrade `aidt_dms` module to verify rendered SVG badges in the form dialog.
