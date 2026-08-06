# Meeting Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the standard Odoo Form View of `aidt.meeting.recording` to a multi-dimensional Dashboard layout adhering to the AIDT Enterprise Design System.

**Architecture:** CSS Injection + XML Layout Rework. Add a custom SCSS file with design tokens and redesign the XML form view using Bootstrap grid and dashboard classes.

**Tech Stack:** Odoo XML, SCSS, Python unittest.

## Global Constraints

- Modify ONLY the Form View of `aidt.meeting.recording`.
- Retain all existing fields, buttons, and state mechanics.

---

### Task 1: Add SCSS Design Tokens

**Files:**
- Create: `custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss`
- Modify: `custom-addons/aidt_meeting_minutes/__manifest__.py`
- Create: `custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/__init__.py`

**Interfaces:**
- Consumes: `DESIGN.md` styling guidelines.
- Produces: CSS classes `.o_dashboard_viewer_container`, `.o_dashboard_card`, `.theme-primary`, `.kpi-card`, etc., loaded into `web.assets_backend`.

- [ ] **Step 1: Write the failing test**
Create `custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`:
```python
from odoo.tests.common import TransactionCase
import ast

class TestUIAssets(TransactionCase):
    def test_manifest_assets(self):
        """Ensure the new SCSS file is listed in the manifest"""
        with open('custom-addons/aidt_meeting_minutes/__manifest__.py', 'r') as f:
            manifest = ast.literal_eval(f.read())
        assets = manifest.get('assets', {}).get('web.assets_backend', [])
        self.assertIn('aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss', assets)
```
Add `from . import test_ui_assets` to `custom-addons/aidt_meeting_minutes/tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**
Run: `odoo --test-tags .test_manifest_assets -i aidt_meeting_minutes` (or run it via pytest if environment is set up: `pytest custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py`)
Expected: FAIL (AssertionError: SCSS file not in assets)

- [ ] **Step 3: Write minimal implementation**
Create `custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss`:
```scss
// Variables
$dash-slate-50: #F8FAFC;
$dash-slate-200: #E2E8F0;
$dash-slate-700: #334155;
$dash-primary: #005B9A;
$dash-warning: #F59E0B;
$dash-danger: #F43F5E;
$dash-success: #10B981;
$dash-info: #0284C7;

.o_dashboard_viewer_container {
    background-color: $dash-slate-50;
    padding: 16px;
    font-family: 'Inter', sans-serif;
}

.o_dashboard_card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(16px);
    border: 1px solid $dash-slate-200;
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 16px;

    &:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #CBD5E1;
    }
}

.kpi-card {
    border-radius: 14px;
    padding: 16px;
}

.theme-primary { border-top: 4px solid $dash-primary; }
.theme-warning { border-top: 4px solid $dash-warning; }
.theme-danger { border-top: 4px solid $dash-danger; }
.theme-success { border-top: 4px solid $dash-success; }
.theme-info { border-top: 4px solid $dash-info; }

.widget-icon-roundel {
    width: 38px;
    height: 38px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    
    &.theme-primary { background: #E6F0F7; color: $dash-primary; }
    &.theme-warning { background: #FFFBEB; color: $dash-warning; }
    &.theme-danger { background: #FFF1F2; color: $dash-danger; }
    &.theme-success { background: #ECFDF5; color: $dash-success; }
    &.theme-info { background: #F0F9FF; color: $dash-info; }
}

.kpi-title {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    color: $dash-slate-700;
}

.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 900;
}
```

Modify `custom-addons/aidt_meeting_minutes/__manifest__.py` to include `'aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss'` in `web.assets_backend`.

- [ ] **Step 4: Run test to verify it passes**
Run: `odoo --test-tags .test_manifest_assets -i aidt_meeting_minutes` or pytest equivalent.
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add custom-addons/aidt_meeting_minutes/tests/test_ui_assets.py custom-addons/aidt_meeting_minutes/tests/__init__.py custom-addons/aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss custom-addons/aidt_meeting_minutes/__manifest__.py
git commit -m "feat(aidt_meeting_minutes): add meeting dashboard SCSS tokens"
```

---

### Task 2: Refactor XML Form View

**Files:**
- Modify: `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`
- Create: `custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`
- Modify: `custom-addons/aidt_meeting_minutes/tests/__init__.py`

**Interfaces:**
- Consumes: SCSS classes defined in Task 1.

- [ ] **Step 1: Write the failing test**
Create `custom-addons/aidt_meeting_minutes/tests/test_ui_views.py`:
```python
from odoo.tests.common import TransactionCase

class TestUIViews(TransactionCase):
    def test_dashboard_classes_in_view(self):
        """Ensure dashboard classes are present in the form view"""
        view = self.env.ref('aidt_meeting_minutes.view_meeting_recording_form')
        arch = view.arch
        self.assertIn('o_dashboard_viewer_container', arch)
        self.assertIn('o_dashboard_card', arch)
```
Add `from . import test_ui_views` to `custom-addons/aidt_meeting_minutes/tests/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**
Run: `odoo --test-tags .test_dashboard_classes_in_view -i aidt_meeting_minutes`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Modify `custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml`:
Replace `<sheet>` content (except the header) with the dashboard grid layout.
```xml
                <sheet class="o_dashboard_viewer_container">
                    <div class="row mb-4">
                        <div class="col-md-4">
                            <div class="o_dashboard_card kpi-card theme-primary dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title">BẮT ĐẦU</span>
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
                            <div class="o_dashboard_card kpi-card theme-danger dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title">ĐỘ MẬT</span>
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
                            <div class="o_dashboard_card kpi-card theme-success dash-animate-in">
                                <div class="kpi-header d-flex align-items-center justify-content-between">
                                    <span class="kpi-title">NGƯỜI TẠO</span>
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
                        <div class="col-md-8">
                            <div class="o_dashboard_card theme-primary">
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
                        <div class="col-md-4">
                            <div class="o_dashboard_card table-card theme-warning mb-3">
                                <h6 class="table-title mb-3"><i class="fa fa-tasks me-2"></i>Công việc</h6>
                                <field name="action_item_ids">
                                    <list editable="bottom">
                                        <field name="task"/>
                                        <field name="owner"/>
                                        <field name="deadline"/>
                                        <field name="priority"/>
                                        <field name="timestamp"/>
                                    </list>
                                </field>
                            </div>
                            <div class="o_dashboard_card table-card theme-info">
                                <h6 class="table-title mb-3"><i class="fa fa-gavel me-2"></i>Quyết định</h6>
                                <field name="decision_ids">
                                    <list editable="bottom">
                                        <field name="content"/>
                                        <field name="timestamp"/>
                                    </list>
                                </field>
                            </div>
                        </div>
                    </div>
                </sheet>
```

- [ ] **Step 4: Run test to verify it passes**
Run: `odoo --test-tags .test_dashboard_classes_in_view -i aidt_meeting_minutes`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add custom-addons/aidt_meeting_minutes/tests/test_ui_views.py custom-addons/aidt_meeting_minutes/tests/__init__.py custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml
git commit -m "feat(aidt_meeting_minutes): apply dashboard layout to meeting form view"
```
