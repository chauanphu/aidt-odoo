# Design Specification: Integrate Format Check into Document Management & Hide Standalone Root Menu

## 1. Overview
Currently, the `aidt_format` module provides an automated document format checker (validating `.docx` styling, margins, fonts, and headers against Party & State formatting guidelines like Quy định 66-QĐ/TW). However, it currently renders as an independent top-level application ("Thể thức văn bản") on the main Odoo App Switcher menu.

This design details how to:
1. Deactivate the standalone root menu item (`menu_aidt_format_root`).
2. Add an `action_check_format()` button on the `aidt.document` form view header (Văn bản đến, Văn bản đi, Dự thảo) to automatically open the format checking wizard for attached `.docx` files.
3. Add a dedicated sub-menu under the Document application menu ("Công cụ" -> "Kiểm tra thể thức") so clerks can also check arbitrary `.docx` files.

---

## 2. Technical Architecture & Modifications

### 2.1. Deactivating Standalone Root Menu
In `custom-addons/aidt_format/views/format_ruleset_views.xml`:
- Set `active="0"` on `<menuitem id="menu_aidt_format_root">`.

### 2.2. Model Extension (`aidt.document`)
In `custom-addons/aidt_format/models/aidt_document.py` (extending `aidt.document`):
- Implement `action_check_format(self)`:
  - Finds the primary `.docx` file attached to `self` (via `ir.attachment` or `dms.file`).
  - Opens `aidt.format.check.wizard` in a modal dialog with `docx_file` and `filename` pre-populated from the document attachment.
  - If no `.docx` file is attached, raises a user-friendly `UserError` prompting the user to attach a `.docx` file first.

### 2.3. View Extension & Integration
In `custom-addons/aidt_format/views/format_document_views.xml`:
- Inherit `aidt_org.view_aidt_document_form` (or form view for `aidt.document`).
- Add button in the `<header>` section:
  ```xml
  <button name="action_check_format" 
          string="Kiểm tra thể thức" 
          type="object" 
          class="btn-secondary" 
          icon="fa-check-square-o"/>
  ```
- Add child menu item under `aidt_org` Document application:
  ```xml
  <menuitem id="menu_aidt_format_check_document"
            name="Kiểm tra thể thức"
            parent="aidt_org.menu_aidt_document_root"
            action="format_check_wizard_action"
            sequence="50"/>
  ```

---

## 3. Verification & Testing Criteria

1. **Menu Verification**:
   - Verify standalone "Thể thức văn bản" root menu is hidden from main App Switcher.
   - Verify "Kiểm tra thể thức" appears under Document application sub-menu.
2. **Button & Wizard Verification**:
   - Verify clicking "Kiểm tra thể thức" on a document record opens the format check wizard modal.
   - Verify format check wizard runs successfully and reports errors/warnings for sample `.docx` files.
3. **Automated Test Suite**:
   - Write unit tests in `custom-addons/aidt_format/tests/test_document_format_integration.py` verifying button execution and menu deactivation.
