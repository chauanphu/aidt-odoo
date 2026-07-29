# Merge Incoming & Outgoing Document Apps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge separate "Văn bản đến" and "Văn bản đi" top-level menus into a single unified top-level application: **"Văn bản"** (`menu_aidt_document_unified_root`).

**Architecture:** Define unified root menu and re-parent sub-menus for incoming documents, outgoing documents, registers, and format checking in `custom-addons/aidt_vanban_den/views/unified_document_menus.xml`, update manifest files, and write unit tests.

**Tech Stack:** Odoo 19 XML UI Views, Python, PostgreSQL.

## Global Constraints

- Preserve all existing records, actions, workflows, and database models (`aidt.document`).
- Do not introduce breaking schema changes.
- Ensure test execution via `odoo-bin --test-enable`.

---

### Task 1: Create Unified Document Menu XML & Test

**Files:**
- Create: `custom-addons/aidt_vanban_den/views/unified_document_menus.xml`
- Modify: `custom-addons/aidt_vanban_den/__manifest__.py`
- Modify: `custom-addons/aidt_vanban_di/__manifest__.py`
- Create Test: `custom-addons/aidt_vanban_den/tests/test_unified_document_menu.py`

**Interfaces:**
- Consumes: Models `aidt.document`, actions from `aidt_vanban_den` and `aidt_vanban_di`.
- Produces: Root menu `menu_aidt_document_unified_root` with unified sub-menus.

- [ ] **Step 1: Write test for unified document menu structure**

Create `custom-addons/aidt_vanban_den/tests/test_unified_document_menu.py`:
```python
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUnifiedDocumentMenu(TransactionCase):

    def test_unified_document_root_menu_exists_and_active(self):
        """Verify unified document root menu exists and is active."""
        root_menu = self.env.ref('aidt_vanban_den.menu_aidt_document_unified_root', raise_if_not_found=False)
        self.assertTrue(root_menu, "Unified document root menu should exist")
        self.assertTrue(root_menu.active, "Unified document root menu should be active")

    def test_legacy_standalone_menus_deactivated(self):
        """Verify legacy standalone root menus are deactivated."""
        den_root = self.env.ref('aidt_vanban_den.menu_vanban_den_root', raise_if_not_found=False)
        if den_root:
            self.assertFalse(den_root.active, "Legacy incoming doc root menu should be inactive")

        di_root = self.env.ref('aidt_vanban_di.menu_vanban_di_root', raise_if_not_found=False)
        if di_root:
            self.assertFalse(di_root.active, "Legacy outgoing doc root menu should be inactive")
```

- [ ] **Step 2: Create `custom-addons/aidt_vanban_den/views/unified_document_menus.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>
        <!-- Menu Gốc Duy Nhất: Văn bản -->
        <menuitem id="menu_aidt_document_unified_root"
                  name="Văn bản"
                  web_icon="aidt_vanban_den,static/description/icon.png"
                  groups="base.group_user"
                  sequence="10"
                  active="1"/>

        <!-- Nhóm 1: Văn bản đến -->
        <menuitem id="menu_vanban_den_section"
                  name="Văn bản đến"
                  parent="menu_aidt_document_unified_root"
                  sequence="10"/>

        <menuitem id="menu_vanban_den_sub_all"
                  name="Tất cả Văn bản đến"
                  parent="menu_vanban_den_section"
                  action="action_vanban_den"
                  sequence="10"/>

        <menuitem id="menu_vanban_den_sub_trinh_lanh_dao"
                  name="Trình Lãnh đạo bút phê"
                  parent="menu_vanban_den_section"
                  action="action_vanban_den_trinh_lanh_dao"
                  sequence="20"/>

        <menuitem id="menu_vanban_den_sub_overdue"
                  name="Văn bản quá hạn"
                  parent="menu_vanban_den_section"
                  action="action_vanban_den_overdue"
                  sequence="30"/>

        <!-- Nhóm 2: Văn bản đi -->
        <menuitem id="menu_vanban_di_section"
                  name="Văn bản đi"
                  parent="menu_aidt_document_unified_root"
                  sequence="20"/>

        <menuitem id="menu_vanban_di_sub_all"
                  name="Tất cả Văn bản đi"
                  parent="menu_vanban_di_section"
                  action="aidt_vanban_di.action_vanban_di"
                  sequence="10"/>

        <menuitem id="menu_vanban_di_sub_draft"
                  name="Dự thảo của tôi"
                  parent="menu_vanban_di_section"
                  action="aidt_vanban_di.action_vanban_di_draft"
                  sequence="20"/>

        <menuitem id="menu_vanban_di_sub_trinh_ky"
                  name="Chờ duyệt / Chờ ký"
                  parent="menu_vanban_di_section"
                  action="aidt_vanban_di.action_vanban_di_trinh_ky"
                  sequence="30"/>

        <menuitem id="menu_vanban_di_sub_da_ban_hanh"
                  name="Đã ban hành"
                  parent="menu_vanban_di_section"
                  action="aidt_vanban_di.action_vanban_di_da_ban_hanh"
                  sequence="40"/>

        <!-- Nhóm 3: Sổ Văn bản -->
        <menuitem id="menu_so_vanban_section"
                  name="Sổ Văn bản"
                  parent="menu_aidt_document_unified_root"
                  sequence="30"/>

        <menuitem id="menu_so_vanban_den"
                  name="Sổ Văn bản đến"
                  parent="menu_so_vanban_section"
                  action="action_report_so_vanban_den"
                  sequence="10"/>

        <menuitem id="menu_so_vanban_di"
                  name="Sổ Văn bản đi"
                  parent="menu_so_vanban_section"
                  action="aidt_vanban_di.action_report_so_vanban_di"
                  sequence="20"/>

        <!-- Ẩn các menu root cũ -->
        <record id="menu_vanban_den_root" model="ir.ui.menu">
            <field name="active" eval="False"/>
        </record>

        <record id="aidt_vanban_di.menu_vanban_di_root" model="ir.ui.menu">
            <field name="active" eval="False"/>
        </record>
    </data>
</odoo>
```

- [ ] **Step 3: Update `custom-addons/aidt_vanban_den/__manifest__.py` & `aidt_vanban_di/__manifest__.py`**

Add `'aidt_vanban_di'` to depends of `aidt_vanban_den` and register `'views/unified_document_menus.xml'` in `'data'`.

- [ ] **Step 4: Execute module upgrade, run tests & update database**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_vanban_den,aidt_vanban_di --test-enable --stop-after-init
```

Update PostgreSQL:
```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt -c "
UPDATE ir_ui_menu SET active = false WHERE id IN (SELECT res_id FROM ir_model_data WHERE name IN ('menu_vanban_den_root', 'menu_vanban_di_root'));
UPDATE ir_ui_menu SET active = true WHERE id IN (SELECT res_id FROM ir_model_data WHERE name = 'menu_aidt_document_unified_root');
"
```

Restart container:
```bash
docker restart aidt-odoo-dev-odoo-1
```

- [ ] **Step 5: Commit changes**

```bash
git add custom-addons/aidt_vanban_den/views/unified_document_menus.xml custom-addons/aidt_vanban_den/__manifest__.py custom-addons/aidt_vanban_di/__manifest__.py custom-addons/aidt_vanban_den/tests/test_unified_document_menu.py
git commit -m "feat(vanban): merge incoming and outgoing document apps into unified Van ban application"
```
