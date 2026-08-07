# OCR Wizard UI Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Odoo OCR Preview Wizard UI with Gemini Sparkle SVG star badges, Vietnamese date formatting (`07/08/2026`), and clean SVG icons for AI reasoning evidence.

**Architecture:** Update XML view templates (`aidt_document_ocr_wizard_views.xml`), Python date formatters (`pipeline.py`), and Odoo wizard python model (`aidt_document_ocr_wizard.py`).

**Tech Stack:** Odoo 16, Python 3, QWeb / XML Views, SVG icons.

## Global Constraints
- Enforce strict `DD/MM/YYYY` date format for all date outputs.
- Replace all text badges with Gemini Sparkle Star SVG badges.
- Replace raw unicode emojis with clean vector SVG icons.

---

### Task 1: Update Date Formatting Engine (`pipeline.py` & `aidt_document_ocr_wizard.py`)

**Files:**
- Modify: `/home/ai_server_1/docker_unlimited_ocr/server/pipeline.py`
- Modify: `/home/ai_server_1/aidt-odoo/custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard.py`

**Interfaces:**
- Consumes: Raw date strings (e.g. `Aug 7`, `Aug 07`, `7 Aug 2026`, `2026-08-07`)
- Produces: Vietnamese formatted date strings (`07/08/2026`)

- [ ] **Step 1: Enhance `format_to_vn_date()` in `pipeline.py`**

Update `format_to_vn_date` to convert English short-month names (`Jan` to `Dec`) into numeric months.

- [ ] **Step 2: Verify `format_to_vn_date` with Python script**

Run: `python3 -c "from server.pipeline import format_to_vn_date; assert format_to_vn_date('Aug 7') == '07/08/2026'; print('OK')"`

- [ ] **Step 3: Update `_parse_date` in `aidt_document_ocr_wizard.py`**

Ensure `_parse_date` correctly converts English short months (`Aug 7`, `7 Aug`) to Odoo `YYYY-MM-DD` date objects.

- [ ] **Step 4: Commit changes**

```bash
git add /home/ai_server_1/docker_unlimited_ocr/server/pipeline.py
git commit -m "fix(pipeline): enforce DD/MM/YYYY date formatting for English short month strings"
```

---

### Task 2: Update Odoo Wizard Form View with Gemini Star & SVG Icons

**Files:**
- Modify: `/home/ai_server_1/aidt-odoo/custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard_views.xml`

**Interfaces:**
- Consumes: Odoo Form View XML layout
- Produces: Enhanced UI elements with Gemini Sparkle SVG star badges and SVG reasoning icons

- [ ] **Step 1: Replace pill badges with Gemini Sparkle SVG Star Badges**

Replace `<span class="badge ...">Gợi ý AI</span>` with inline SVG Gemini 4-point star badge.

- [ ] **Step 2: Replace raw unicode emojis in Trích dẫn section with SVG icons**

Replace `📌` and `🧠` with clean inline SVG bookmark pin icon and SVG lightbulb / Gemini sparkle icon.

- [ ] **Step 3: Upgrade `aidt_dms` module and restart Odoo container**

Run: `docker exec aidt-odoo-dev-odoo-1 python3 -c "import odoo; ... env['ir.module.module'].search([('name', '=', 'aidt_dms')]).button_immediate_upgrade(); cr.commit()"`  
Run: `docker restart aidt-odoo-dev-odoo-1`

- [ ] **Step 4: Commit XML view changes**

```bash
git add custom-addons/aidt_dms/wizards/aidt_document_ocr_wizard_views.xml
git commit -m "style(wizard): render Gemini Sparkle SVG badges and clean SVG reasoning icons"
```
