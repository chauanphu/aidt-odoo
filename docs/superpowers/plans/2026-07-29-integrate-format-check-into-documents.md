# Integrate Format Check into Document Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deactivate standalone "Thể thức văn bản" root menu, add `action_check_format()` button to `aidt.document` form view header, and integrate Format Check sub-menu into Document application.

**Architecture:** Extend `aidt.document` in `aidt_format`, add form button and menu override in `custom-addons/aidt_format/views/`, write tests, and update database.

**Tech Stack:** Odoo 19, Python, XML, PostgreSQL.

## Global Constraints

- Preserve all existing format checking algorithms and YAML rulesets (`aidt.format.ruleset`).
- Do not introduce breaking schema changes.
- Ensure test execution via `odoo-bin --test-enable`.

---

### Task 1: Extend `aidt.document` Model with `action_check_format()`

**Files:**
- Create: `custom-addons/aidt_format/models/aidt_document.py`
- Modify: `custom-addons/aidt_format/models/__init__.py`
- Test: `custom-addons/aidt_format/tests/test_document_format_integration.py`

**Interfaces:**
- Consumes: Model `aidt.document` from `aidt_org`, Wizard `aidt.format.check.wizard`.
- Produces: Method `action_check_format(self)` returning action dict to launch format check wizard.

- [ ] **Step 1: Write failing test for `action_check_format()`**

Create `custom-addons/aidt_format/tests/test_document_format_integration.py`:
```python
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
import base64


@tagged('post_install', '-at_install')
class TestDocumentFormatIntegration(TransactionCase):

    def setUp(self):
        super().setUp()
        self.doc = self.env['aidt.document'].create({
            'name': 'Văn bản test thể thức',
            'reference': '123/QD-TU',
        })

    def test_action_check_format_without_attachment_raises_error(self):
        """Verify calling action_check_format without docx attachment raises UserError."""
        with self.assertRaises(UserError):
            self.doc.action_check_format()

    def test_action_check_format_with_attachment_returns_action(self):
        """Verify calling action_check_format with docx attachment returns wizard action."""
        self.env['ir.attachment'].create({
            'name': 'test_doc.docx',
            'datas': base64.b64encode(b"dummy docx content"),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        action = self.doc.action_check_format()
        self.assertEqual(action['res_model'], 'aidt.format.check.wizard')
        self.assertEqual(action['target'], 'new')
```

- [ ] **Step 2: Create `custom-addons/aidt_format/models/aidt_document.py`**

```python
from odoo import models, fields, _
from odoo.exceptions import UserError


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    def action_check_format(self):
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'aidt.document'),
            ('res_id', '=', self.id),
            '|',
            ('name', '=like', '%.docx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        ], limit=1)

        if not attachment:
            raise UserError(_("Vui lòng đính kèm tệp văn bản định dạng .docx trước khi kiểm tra thể thức."))

        ruleset = self.env['aidt.format.ruleset'].search([('active', '=', True)], limit=1)

        wizard = self.env['aidt.format.check.wizard'].create({
            'docx_file': attachment.datas,
            'filename': attachment.name,
            'ruleset_id': ruleset.id if ruleset else False,
        })

        return {
            'name': _("Kiểm tra thể thức văn bản"),
            'type': 'ir.actions.act_window',
            'res_model': 'aidt.format.check.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
```

- [ ] **Step 3: Register model and import in `custom-addons/aidt_format/models/__init__.py`**

Ensure `from . import aidt_document` is added to `custom-addons/aidt_format/models/__init__.py`.

- [ ] **Step 4: Run unit tests**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_format --test-enable --stop-after-init
```
Expected: PASS with 0 failures.

- [ ] **Step 5: Commit Task 1 changes**

```bash
git add custom-addons/aidt_format/models/aidt_document.py custom-addons/aidt_format/models/__init__.py custom-addons/aidt_format/tests/test_document_format_integration.py
git commit -m "feat(format): add action_check_format method to aidt.document model"
```

---

### Task 2: Update Views, Hide Standalone Root Menu & Integrate Sub-Menu

**Files:**
- Modify: `custom-addons/aidt_format/views/format_ruleset_views.xml`
- Create: `custom-addons/aidt_format/views/format_document_views.xml`
- Modify: `custom-addons/aidt_format/__manifest__.py`
- Test: `custom-addons/aidt_format/tests/test_document_format_integration.py`

- [ ] **Step 1: Deactivate `menu_aidt_format_root` in `format_ruleset_views.xml`**

Set `active="0"` on `menu_aidt_format_root`:
```xml
    <menuitem id="menu_aidt_format_root"
              name="Thể thức văn bản"
              sequence="6"
              active="0"/>
```

- [ ] **Step 2: Create `custom-addons/aidt_format/views/format_document_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Thêm nút Kiểm tra thể thức vào Form Văn bản -->
    <record id="view_aidt_document_form_inherit_format" model="ir.ui.view">
        <field name="name">aidt.document.form.inherit.format</field>
        <field name="model">aidt.document</field>
        <field name="inherit_id" ref="aidt_org.view_aidt_document_form"/>
        <field name="arch" type="xml">
            <xpath expr="//header" position="inside">
                <button name="action_check_format"
                        string="Kiểm tra thể thức"
                        type="object"
                        class="btn-secondary"
                        icon="fa-check-square-o"/>
            </xpath>
        </field>
    </record>

    <!-- Thêm Menu Kiểm tra thể thức vào App Văn bản -->
    <menuitem id="menu_aidt_format_check_document"
              name="Kiểm tra thể thức"
              parent="aidt_org.menu_aidt_document_root"
              action="format_check_wizard_action"
              groups="base.group_user"
              sequence="50"/>
</odoo>
```

- [ ] **Step 3: Update `custom-addons/aidt_format/__manifest__.py`**

Add `'aidt_org'` to `'depends'` and `'views/format_document_views.xml'` to `'data'`.

- [ ] **Step 4: Run full test suite & upgrade database**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_format --test-enable --stop-after-init
```

Update PostgreSQL:
```bash
docker exec aidt-odoo-dev-db-1 psql -U odoo -d aidt -c "UPDATE ir_ui_menu SET active = false WHERE id IN (SELECT res_id FROM ir_model_data WHERE name = 'menu_aidt_format_root');"
```

Restart container:
```bash
docker restart aidt-odoo-dev-odoo-1
```

- [ ] **Step 5: Commit Task 2 changes**

```bash
git add custom-addons/aidt_format/views/format_ruleset_views.xml custom-addons/aidt_format/views/format_document_views.xml custom-addons/aidt_format/__manifest__.py
git commit -m "feat(format): hide standalone root menu and add format check button to document views"
```
