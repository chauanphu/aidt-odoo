# Design Specification: Merge Incoming & Outgoing Document Apps into Unified "Văn bản" Application

## 1. Overview
Currently, the AIDT Odoo system exposes two separate top-level applications on the main App Switcher:
- **"Văn bản đến"** (`aidt_vanban_den`, `sequence: 1`)
- **"Văn bản đi"** (`aidt_vanban_di`, `sequence: 2`)

However, both modules share the same underlying database table and model: `aidt.document` (differentiated by `direction = 'den'` vs `direction = 'di'`).

This design unifies both applications into a single, cohesive top-level application: **"Văn bản"** (`menu_aidt_document_unified_root`). This streamlines the App Switcher UI, groups all incoming/outgoing documents, registers, and format checking under a single sidebar menu structure, while keeping all data models and business workflows intact.

---

## 2. Target Menu Structure

### 2.1. Unified Root Menu
- **Root Menu ID**: `aidt_org.menu_aidt_document_root` (or `aidt_vanban_den.menu_aidt_document_unified_root`)
- **Name**: `Văn bản`
- **Icon**: `aidt_vanban_den,static/description/icon.png`
- **Sequence**: `10`
- **Deactivated Standalone Menus**:
  - `aidt_vanban_den.menu_vanban_den_root` -> Deactivated (`active="0"`).
  - `aidt_vanban_di.menu_vanban_di_root` -> Deactivated (`active="0"`).

### 2.2. Sub-Menu Hierarchy under "Văn bản" App

```text
📁 Menu "Văn bản" (Root)
├── 📥 Văn bản đến
│   ├── Tất cả Văn bản đến (direction='den')
│   ├── Trình Lãnh đạo bút phê (direction='den', state='trinh_lanh_dao')
│   └── Văn bản quá hạn (direction='den', is_overdue=True)
├── 📤 Văn bản đi
│   ├── Tất me Văn bản đi (direction='di')
│   ├── Dự thảo của tôi (direction='di', state='draft', create_uid=user.id)
│   ├── Chờ duyệt / Chờ ký (direction='di', state in ['trinh_duyet','cho_duyet_tp','cho_duyet_cvp','cho_duyet_lanh_dao','cho_ky'])
│   └── Đã ban hành (direction='di', state='da_ban_hanh')
├── 📖 Sổ Văn bản
│   ├── Sổ Văn bản đến (Action report_so_vanban_den)
│   └── Sổ Văn bản đi (Action report_so_vanban_di)
└── 🛠️ Công cụ & Thể thức
    └── Kiểm tra thể thức (.docx) (Action format_check_wizard_action)
```

---

## 3. Technical Implementation

### 3.1. Unified Menu XML Definition
In `custom-addons/aidt_vanban_den/views/unified_document_menus.xml`:
1. Define the unified root menu:
   ```xml
   <menuitem id="menu_aidt_document_unified_root"
             name="Văn bản"
             web_icon="aidt_vanban_den,static/description/icon.png"
             groups="base.group_user"
             sequence="10"
             active="1"/>
   ```
2. Re-parent incoming document menus (`menu_vanban_den_main`, `menu_vanban_den_trinh_lanh_dao`, etc.) under `menu_aidt_document_unified_root`.
3. Re-parent outgoing document menus (`menu_vanban_di_main`, `menu_vanban_di_draft`, `menu_vanban_di_trinh_ky`, `menu_vanban_di_da_ban_hanh`) under `menu_aidt_document_unified_root`.
4. Re-parent register reports (`report_so_vanban_den`, `report_so_vanban_di`) under `Sổ Văn bản` section.
5. Deactivate legacy standalone top-level menus in PostgreSQL database `aidt`.

---

## 4. Verification & Testing Criteria

1. **App Switcher Menu Verification**:
   - Verify only one "Văn bản" app icon appears on the main App Switcher.
   - Verify clicking "Văn bản" opens the unified document navigation sidebar with "Văn bản đến", "Văn bản đi", "Sổ Văn bản", and "Kiểm tra thể thức".
2. **Functional Integrity**:
   - Verify filtering for incoming documents (`direction='den'`) works properly.
   - Verify filtering for outgoing documents (`direction='di'`) works properly.
   - Verify creating new incoming/outgoing documents functions seamlessly without schema errors.
3. **Automated Test Suite**:
   - Write unit test in `custom-addons/aidt_vanban_den/tests/test_unified_document_menu.py` asserting unified root menu existence and sub-menu organization.
