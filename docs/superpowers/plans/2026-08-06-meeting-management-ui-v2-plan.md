# Meeting Management UI V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Odoo Form View of `aidt.meeting.recording` to a premium full-width glassmorphism layout with a 50/50 split for larger tables.

**Architecture:** Modify the existing SCSS and XML form view definitions. Replace the Odoo `<sheet>` container with a custom `<div class="premium-dashboard-container">`. Implement CSS Grid/Flexbox for layout and apply modern aesthetics.

**Tech Stack:** Odoo 19.0, XML (Views), SCSS (Styling).

## Global Constraints
- **Scope:** Modify ONLY the Form View of `aidt.meeting.recording` and its SCSS assets.
- **Functionality:** Retain all existing fields, buttons, and state mechanics. Do not alter Odoo field types.
- **Testing:** Due to missing `pytest` and Odoo test runner dependencies, tests should be standalone Python validation scripts checking the presence of CSS/XML tokens.

---

### Task 1: Premium Dashboard SCSS Updates

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss`
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`

**Interfaces:**
- Produces: CSS classes `.premium-dashboard-container`, `.premium-card`, and hover state utilities that Task 2 will apply.

- [ ] **Step 1: Write the failing test**

Modify `test_ui_assets.py` to check for the new `premium-dashboard-container` and `premium-card` classes.

```python
import os

def test_scss_contains_premium_tokens():
    scss_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'scss', 'meeting_dashboard.scss')
    with open(scss_path, 'r') as f:
        content = f.read()
    
    assert '.premium-dashboard-container' in content, "Missing .premium-dashboard-container class"
    assert '.premium-card' in content, "Missing .premium-card class"
    assert 'backdrop-filter: blur' in content, "Missing glassmorphism blur"
    assert 'box-shadow' in content, "Missing soft shadow"

if __name__ == '__main__':
    test_scss_contains_premium_tokens()
    print("SCSS premium tokens test passed!")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`
Expected: FAIL with "Missing .premium-dashboard-container class"

- [ ] **Step 3: Write minimal implementation**

Append to `custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss`:

```scss
/* V2 Premium Dashboard Styles */
.premium-dashboard-container {
    width: 100%;
    padding: 20px;
    font-family: 'Inter', sans-serif;
    background-color: transparent; /* Allow Odoo background to show, or set a subtle tint */
}

.premium-card {
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.4);
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.08);
    transition: all 0.25s ease-in-out;
}

.premium-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 15px 45px -10px rgba(0, 0, 0, 0.12);
}

.premium-table-row:hover {
    background-color: rgba(99, 102, 241, 0.05);
}

/* Override KPI specific styles */
.kpi-title-premium {
    font-weight: 600;
    letter-spacing: 0.5px;
    color: #4b5563; /* Subtle dark gray */
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py
git commit -m "style: add premium dashboard SCSS tokens"
```

---

### Task 2: Refactor XML Form View to 50/50 Split

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`
- Modify: `custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`

**Interfaces:**
- Consumes: The `premium-card` and `premium-dashboard-container` CSS classes defined in Task 1.

- [ ] **Step 1: Write the failing test**

Modify `test_ui_views.py` to check for the new `premium-dashboard-container` and `col-md-6` grid sizes instead of `col-md-8`.

```python
import os
import xml.etree.ElementTree as ET

def test_xml_premium_layout():
    xml_path = os.path.join(os.path.dirname(__file__), '..', 'views', 'meeting_recording_views.xml')
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Check for the premium container
    container = root.find(".//div[@class='premium-dashboard-container']")
    assert container is not None, "Missing <div class='premium-dashboard-container'>"
    
    # Check for the 50/50 layout (at least two col-md-6)
    col_6_elements = root.findall(".//div[@class='col-md-6']")
    assert len(col_6_elements) >= 2, "Main layout must use col-md-6 for a 50/50 split"

if __name__ == '__main__':
    test_xml_premium_layout()
    print("XML premium layout test passed!")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`
Expected: FAIL with "Missing <div class='premium-dashboard-container'>"

- [ ] **Step 3: Write minimal implementation**

Edit `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`:
1. Change `<sheet class="o_dashboard_viewer_container">` to `<div class="premium-dashboard-container">`. (Make sure to change the closing `</sheet>` to `</div>`).
2. Update the KPI cards: change `class="o_dashboard_card kpi-card theme-primary dash-animate-in"` to `class="premium-card dash-animate-in"`. Apply this to all three KPI cards. Also update `kpi-title` to `kpi-title-premium`.
3. Change the main layout split: find `<div class="col-md-8">` and change it to `<div class="col-md-6">`. Find the adjacent `<div class="col-md-4">` containing the tables and change it to `<div class="col-md-6">`.
4. Update the inner cards to use `class="premium-card"`.

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_meeting_recording_form" model="ir.ui.view">
        <field name="name">aidt.meeting.recording.form</field>
        <field name="model">aidt.meeting.recording</field>
        <field name="arch" type="xml">
            <form string="Bản ghi cuộc họp">
                <header>
                    <button name="action_stop" type="object" string="Dừng ghi âm"
                            invisible="state != 'recording'"/>
                    <button name="action_retry_summary" type="object"
                            string="Tổng hợp AI"
                            invisible="0"/>
                    <button name="action_retranscribe" type="object"
                            string="Bóc băng lại"
                            confirm="Chạy lại bóc băng trên audio còn lưu bằng cấu hình hiện tại. Bản bóc băng và tóm tắt mới sẽ được đăng thêm một lần nữa vào cuộc trò chuyện."
                            invisible="state != 'done'"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <div class="premium-dashboard-container">
                    <div class="row mb-4">
                        <div class="col-md-4">
                            <div class="premium-card dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title-premium">BẮT ĐẦU</span>
                                    <div class="widget-icon-roundel theme-primary">
                                        <i class="fa fa-clock-o"></i>
                                    </div>
                                </div>
                                <div class="mt-3">
                                    <field name="started_at" readonly="1" class="kpi-value"/>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="premium-card dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title-premium">ĐỘ MẬT</span>
                                    <div class="widget-icon-roundel theme-danger">
                                        <i class="fa fa-lock"></i>
                                    </div>
                                </div>
                                <div class="mt-3">
                                    <field name="secrecy_at_start" readonly="1" class="kpi-value"/>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="premium-card dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title-premium">NGƯỜI TẠO</span>
                                    <div class="widget-icon-roundel theme-success">
                                        <i class="fa fa-user"></i>
                                    </div>
                                </div>
                                <div class="mt-3">
                                    <field name="started_by_id" readonly="1" class="kpi-value"/>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <field name="summary_error" readonly="1" invisible="not summary_error"/>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="premium-card mb-3">
                                <group>
                                    <field name="event_id"/>
                                    <field name="channel_id"/>
                                    <field name="ended_at"/>
                                    <field name="declined_partner_ids" widget="many2many_tags"/>
                                </group>
                                <notebook>
                                    <page string="Tổng quan" name="overview_page">
                                        <group>
                                            <field name="title"/>
                                            <field name="overview"/>
                                            <field name="meeting_minutes"/>
                                            <field name="key_points"/>
                                            <field name="risks"/>
                                        </group>
                                    </page>
                                    <page string="Bản bóc băng" name="transcript_page">
                                        <field name="transcript_text"/>
                                    </page>
                                </notebook>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="premium-card mb-3">
                                <h6 class="table-title mb-3"><i class="fa fa-tasks me-2"></i>Công việc</h6>
                                <field name="action_item_ids">
                                    <list editable="bottom" class="premium-table-row">
                                        <field name="task"/>
                                        <field name="owner"/>
                                        <field name="deadline"/>
                                        <field name="priority"/>
                                        <field name="timestamp"/>
                                    </list>
                                </field>
                            </div>
                            <div class="premium-card">
                                <h6 class="table-title mb-3"><i class="fa fa-gavel me-2"></i>Quyết định</h6>
                                <field name="decision_ids">
                                    <list editable="bottom" class="premium-table-row">
                                        <field name="content"/>
                                        <field name="timestamp"/>
                                    </list>
                                </field>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </field>
    </record>

    <record id="view_meeting_recording_list" model="ir.ui.view">
        <field name="name">aidt.meeting.recording.list</field>
        <field name="model">aidt.meeting.recording</field>
        <field name="arch" type="xml">
            <list string="Bản ghi cuộc họp">
                <field name="channel_id"/>
                <field name="event_id"/>
                <field name="started_at"/>
                <field name="ended_at"/>
                <field name="secrecy_at_start"/>
                <field name="state"/>
            </list>
        </field>
    </record>

    <record id="action_meeting_recording" model="ir.actions.act_window">
        <field name="name">Bản ghi cuộc họp</field>
        <field name="res_model">aidt.meeting.recording</field>
        <field name="view_mode">list,form</field>
    </record>

    <!-- Root menu -->
    <menuitem id="menu_meeting_root" 
              name="Quản lý Cuộc họp" 
              sequence="50" 
              web_icon="aidt_meeting_minutes,static/description/icon.png"/>

    <menuitem id="menu_meeting_recording"
              name="Bản ghi cuộc họp"
              parent="menu_meeting_root"
              action="action_meeting_recording"
              groups="aidt_meeting_minutes.group_meeting_minutes_manager"
              sequence="10"/>
</odoo>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml custom-addons/aidt_meeting_minutes/tests/test_ui_views.py
git commit -m "feat(aidt_meeting_minutes): refactor form view to premium 50/50 dashboard layout"
```
