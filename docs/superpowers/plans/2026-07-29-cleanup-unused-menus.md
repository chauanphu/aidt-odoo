# Cleanup Unused Root Menus (To-Do, Project, Website) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deactivate redundant root menu items (`project_todo`, `project`, `website`) in AIDT Odoo system so only specialized Cấp ủy apps appear on the main menu.

**Architecture:** Create an XML menu cleanup file `custom-addons/aidt_base/views/aidt_menu_cleanup.xml` that overrides the `active` attribute to `False` for the 3 root menu items, register it in `custom-addons/aidt_base/__manifest__.py`, and update database `aidt`.

**Tech Stack:** Odoo 19 XML View Inherit / Data override, Python, PostgreSQL.

## Global Constraints

- Preserve all underlying backend models (`project.task`) and public website portal routes (`/dang-ky-lich-lam-viec`).
- Do not introduce breaking schema changes.
- Ensure test execution via `odoo-bin --test-enable`.

---

### Task 1: Create XML View `aidt_menu_cleanup.xml` & Update Manifest

**Files:**
- Create: `custom-addons/aidt_base/views/aidt_menu_cleanup.xml`
- Modify: `custom-addons/aidt_base/__manifest__.py`
- Test: `custom-addons/aidt_base/tests/test_menu_cleanup.py`

**Interfaces:**
- Consumes: Core Odoo menu IDs `project_todo.menu_todo_todos_general`, `project.menu_main_pm`, `website.menu_website_configuration`.
- Produces: Deactivated menu records in `ir.ui.menu`.

- [ ] **Step 1: Write test validating menu cleanup**

Create `custom-addons/aidt_base/tests/test_menu_cleanup.py`:
```python
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMenuCleanup(TransactionCase):

    def test_unused_menus_deactivated(self):
        """Verify that To-Do, Project, and Website root menus are deactivated."""
        todo_menu = self.env.ref('project_todo.menu_todo_todos_general', raise_if_not_found=False)
        if todo_menu:
            self.assertFalse(todo_menu.active, "To-Do root menu should be deactivated")

        project_menu = self.env.ref('project.menu_main_pm', raise_if_not_found=False)
        if project_menu:
            self.assertFalse(project_menu.active, "Project root menu should be deactivated")

        website_menu = self.env.ref('website.menu_website_configuration', raise_if_not_found=False)
        if website_menu:
            self.assertFalse(website_menu.active, "Website root menu should be deactivated")
```

- [ ] **Step 2: Create `custom-addons/aidt_base/views/aidt_menu_cleanup.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>
        <!-- Deactivate To-Do root menu -->
        <record id="project_todo.menu_todo_todos_general" model="ir.ui.menu">
            <field name="active" eval="False"/>
        </record>

        <!-- Deactivate Project root menu -->
        <record id="project.menu_main_pm" model="ir.ui.menu">
            <field name="active" eval="False"/>
        </record>

        <!-- Deactivate Website admin root menu -->
        <record id="website.menu_website_configuration" model="ir.ui.menu">
            <field name="active" eval="False"/>
        </record>
    </data>
</odoo>
```

- [ ] **Step 3: Register XML view & dependencies in `custom-addons/aidt_base/__manifest__.py`**

Ensure `views/aidt_menu_cleanup.xml` is included in `'data'` and `'depends'` contains `'project'`, `'website'`, `'project_todo'`.

- [ ] **Step 4: Execute module upgrade & test**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_base --test-enable --stop-after-init
```
Expected: PASS and output `TestMenuCleanup passed`.

- [ ] **Step 5: Commit changes**

```bash
git add custom-addons/aidt_base/views/aidt_menu_cleanup.xml custom-addons/aidt_base/__manifest__.py custom-addons/aidt_base/tests/test_menu_cleanup.py
git commit -m "feat(base): deactivate To-Do, Project, and Website root menus"
```
