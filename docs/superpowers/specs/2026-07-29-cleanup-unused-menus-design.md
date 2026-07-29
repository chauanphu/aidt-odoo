# Design Specification: Cleanup Unused Root Menus (To-Do, Project, Website)

## 1. Overview
In the AIDT Odoo system tailored for Cấp ủy (Party Executive Committee) operations, several standard Odoo core modules (`project`, `website`, `project_todo`) install default root menu items in the main App Switcher. 

To maintain a clean, specialized UI focused exclusively on Cấp ủy administrative workflows (Văn bản đến, Văn bản đi, Nhiệm vụ, Lịch họp, Tổ chức, Bảng điều khiển), this design details how to deactivate redundant root menu items while preserving all underlying backend functionality (e.g., `project.task` integration for meeting follow-up tasks and public website portal routes for citizen appointments).

---

## 2. Scope & Target Menus

### 2.1. Menu Deactivations

| Menu ID | Module | Display Name | Target State | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `project_todo.menu_todo_todos_general` | `project_todo` | Việc cần làm | Deactivated (`active="0"`) | Redundant with AIDT Cấp ủy task system (`aidt_task`). |
| `project.menu_main_pm` | `project` | Dự án | Deactivated (`active="0"`) | Project management root menu is not relevant for Cấp ủy staff. Backend models (`project.task`) remain active. |
| `website.menu_website_configuration` | `website` | Trang web | Deactivated (`active="0"`) | Website CMS builder menu is unnecessary for operational staff. Public citizen portal routes remain fully functional. |

---

## 3. Technical Implementation

### 3.1. File Location & Module Structure
A new view definition file will be created in `custom-addons/aidt_base`:
- File path: `custom-addons/aidt_base/views/aidt_menu_cleanup.xml`
- Manifest update: Register `views/aidt_menu_cleanup.xml` in `custom-addons/aidt_base/__manifest__.py` under the `'data'` key.
- Manifest dependencies: Ensure `custom-addons/aidt_base/__manifest__.py` depends on `['base', 'project', 'website']` (and optional `project_todo` if installed).

### 3.2. XML View Definition Structure

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

---

## 4. Verification & Testing Criteria

1. **Menu Visibility Verification**:
   - Log in as `admin` or any demo user.
   - Verify that "Việc cần làm", "Dự án", and "Trang web" are no longer visible in the main App Switcher / top navigation bar.
2. **Backend Functionality Verification**:
   - Verify that creating a follow-up task from a calendar event (`calendar.event` -> `action_create_followup_task()`) creates a valid `project.task` record without error.
   - Verify that public citizen appointment booking route `/dang-ky-lich-lam-viec` remains accessible and functional on the website portal.
3. **Database Reset Verification**:
   - Run module upgrade or re-initialization to ensure menus remain deactivated by default across clean database builds.
