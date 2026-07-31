# Automatic Document Format Check on File Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically run format check on `.docx` attachments uploaded to incoming/outgoing `aidt.document` records, updating `format_ok` and `format_note` fields in real-time.

**Architecture:** Mapped via `ir.attachment` model override (`create` and `write`), triggering `_auto_check_format()` on target `aidt.document` records. Also syncs wizard results when manually executed.

**Tech Stack:** Python (Odoo 17 ORM), XML views, python-docx parser via `aidt_format_engine`.

## Global Constraints
- Target Odoo 17 ORM APIs (`api.model_create_multi`, `api.model`).
- Preserve existing wizard functionality (`aidt.format.check.wizard`).
- All code changes must pass tests via `odoo-bin` test runner or python unit tests.

---

### Task 1: Add `_auto_check_format()` method to `aidt.document` & Update Wizard Sync

**Files:**
- Modify: `custom-addons/aidt_format/models/aidt_document.py`
- Modify: `custom-addons/aidt_format/models/format_check_wizard.py`
- Test: `custom-addons/aidt_format/tests/test_auto_format_check.py`

**Interfaces:**
- Produces: `aidt.document._auto_check_format()` method that updates `format_ok` (Boolean) and `format_note` (Text).

- [ ] **Step 1: Write tests for `_auto_check_format()`**

Create `custom-addons/aidt_format/tests/test_auto_format_check.py`:
```python
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import base64

class TestAutoFormatCheck(TransactionCase):
    def setUp(self):
        super().setUp()
        self.doc = self.env['aidt.document'].create({
            'name': 'Văn bản test thể thức',
            'direction': 'den',
        })
        self.ruleset = self.env['aidt.format.ruleset'].create({
            'name': 'Bộ luật Test',
            'code': 'TEST-01',
            'active': True,
        })

    def test_auto_check_format_without_docx(self):
        self.doc._auto_check_format()
        self.assertFalse(self.doc.format_ok)
        self.assertIn("Chưa có tệp", self.doc.format_note or "")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest discover -s custom-addons/aidt_format/tests` or odoo test command.
Expected: Attribute/Assertion Failure because `_auto_check_format` is not implemented or fails.

- [ ] **Step 3: Implement `_auto_check_format()` on `aidt.document`**

In `custom-addons/aidt_format/models/aidt_document.py`:
```python
from odoo import models, fields, _
import base64

class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    format_ok = fields.Boolean(string='Thể thức đạt', default=False, readonly=True)
    format_note = fields.Text(string='Ghi chú thể thức', readonly=True)

    def _auto_check_format(self):
        for rec in self:
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id),
                '|',
                ('name', '=like', '%.docx'),
                ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ], order='id desc', limit=1)

            if not attachment:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Chưa có tệp đính kèm .docx để kiểm tra thể thức.")
                })
                continue

            ruleset = self.env['aidt.format.ruleset'].search([('active', '=', True)], limit=1)
            if not ruleset:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Chưa có bộ quy tắc thể thức nào đang kích hoạt.")
                })
                continue

            try:
                content = base64.b64decode(attachment.datas or b'')
                findings = self.env['aidt.format.checker'].check(content, ruleset)
                errors = [f for f in findings if f.get('severity') == 'error']
                warnings = [f for f in findings if f.get('severity') == 'warning']

                is_ok = len(errors) == 0
                summary_lines = []
                if is_ok:
                    summary_lines.append(_("Đạt thể thức (%d lỗi chặn, %d cảnh báo)") % (len(errors), len(warnings)))
                else:
                    summary_lines.append(_("Không đạt thể thức (%d lỗi chặn, %d cảnh báo):") % (len(errors), len(warnings)))

                for idx, item in enumerate(errors + warnings, 1):
                    sev = _("[LỖI CHẶN]") if item.get('severity') == 'error' else _("[CẢNH BÁO]")
                    loc = f" (Vị trí: {item.get('location')})" if item.get('location') else ""
                    sug = f" -> Gợi ý: {item.get('suggestion')}" if item.get('suggestion') else ""
                    summary_lines.append(f"{idx}. {sev} {item.get('rule_id') or ''}{loc}{sug}")

                rec.sudo().write({
                    'format_ok': is_ok,
                    'format_note': "\n".join(summary_lines)
                })
            except Exception as e:
                rec.sudo().write({
                    'format_ok': False,
                    'format_note': _("Lỗi khi kiểm tra thể thức tệp: %s") % str(e)
                })
```

- [ ] **Step 4: Update Wizard `action_kiem_tra()` in `custom-addons/aidt_format/models/format_check_wizard.py`**

```python
        self.da_kiem = True
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'aidt.document' and active_id:
            doc = self.env['aidt.document'].browse(active_id)
            if doc.exists():
                doc._auto_check_format()
```

- [ ] **Step 5: Run tests and verify pass**

Run tests to ensure `_auto_check_format()` runs smoothly.

- [ ] **Step 6: Commit**

```bash
git add custom-addons/aidt_format/models/aidt_document.py custom-addons/aidt_format/models/format_check_wizard.py custom-addons/aidt_format/tests/test_auto_format_check.py
git commit -m "feat(format): add _auto_check_format method to aidt.document model and sync wizard output"
```

---

### Task 2: Implement `ir.attachment` Upload Listener for Auto Execution

**Files:**
- Create: `custom-addons/aidt_format/models/ir_attachment.py`
- Modify: `custom-addons/aidt_format/models/__init__.py`
- Modify: `custom-addons/aidt_format/tests/test_auto_format_check.py`

**Interfaces:**
- Consumes: `aidt.document._auto_check_format()`
- Produces: `ir.attachment` `create` and `write` overrides triggering `_auto_check_format()` when a `.docx` file is attached to `aidt.document`.

- [ ] **Step 1: Write test for attachment creation/write auto trigger**

In `test_auto_format_check.py`:
```python
    def test_auto_check_triggered_on_attachment_create(self):
        # Attach dummy docx attachment to document
        attachment = self.env['ir.attachment'].create({
            'name': 'test_file.docx',
            'datas': base64.b64encode(b'PK...'),
            'res_model': 'aidt.document',
            'res_id': self.doc.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        self.assertTrue(bool(self.doc.format_note))
```

- [ ] **Step 2: Create `custom-addons/aidt_format/models/ir_attachment.py`**

```python
from odoo import models, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        doc_ids = set()
        for rec in records:
            if rec.res_model == 'aidt.document' and rec.res_id and (
                (rec.name and rec.name.lower().endswith('.docx')) or
                rec.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ):
                doc_ids.add(rec.res_id)
        if doc_ids:
            self.env['aidt.document'].browse(list(doc_ids))._auto_check_format()
        return records

    def write(self, vals):
        res = super().write(vals)
        doc_ids = set()
        for rec in self:
            if rec.res_model == 'aidt.document' and rec.res_id and (
                (rec.name and rec.name.lower().endswith('.docx')) or
                rec.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ):
                doc_ids.add(rec.res_id)
        if doc_ids:
            self.env['aidt.document'].browse(list(doc_ids))._auto_check_format()
        return res
```

- [ ] **Step 3: Register `ir_attachment.py` in `models/__init__.py`**

In `custom-addons/aidt_format/models/__init__.py`:
Add `from . import ir_attachment`.

- [ ] **Step 4: Run tests and verify pass**

Run unit tests to ensure `ir.attachment` creation automatically updates `aidt.document.format_ok` and `format_note`.

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_format/models/ir_attachment.py custom-addons/aidt_format/models/__init__.py custom-addons/aidt_format/tests/test_auto_format_check.py
git commit -m "feat(format): trigger auto format check on ir.attachment create/write for docx files"
```

---

### Task 3: UI Integration and Form View Displays for Incoming/Outgoing Documents

**Files:**
- Modify: `custom-addons/aidt_format/views/format_document_views.xml`
- Modify: `custom-addons/aidt_vanban_di/views/vanban_di_views.xml`

- [ ] **Step 1: Update `format_document_views.xml` to include `format_ok` and `format_note` fields on Document form view**

```xml
<record id="view_aidt_document_form_inherit_format" model="ir.ui.view">
    <field name="name">aidt.document.form.inherit.format</field>
    <field name="model">aidt.document</field>
    <field name="inherit_id" ref="aidt_org.view_aidt_document_form"/>
    <field name="arch" type="xml">
        <xpath expr="//header" position="inside">
            <button name="action_check_format" string="Kiểm tra thể thức" type="object" class="btn-secondary" icon="fa-check-square-o"/>
        </xpath>
        <xpath expr="//sheet" position="before">
            <div class="alert alert-success mb-0" role="alert" attrs="{'invisible': [('format_ok', '=', False)]}">
                <strong>Thể thức văn bản:</strong> Đạt chuẩn. <field name="format_note" class="d-inline"/>
            </div>
            <div class="alert alert-warning mb-0" role="alert" attrs="{'invisible': ['|', ('format_ok', '=', True), ('format_note', '=', False)]}">
                <strong>Thể thức văn bản:</strong> <field name="format_note" class="d-inline"/>
            </div>
        </xpath>
    </field>
</record>
```

- [ ] **Step 2: Verify views load and render properly without XML errors**

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_format/views/format_document_views.xml custom-addons/aidt_vanban_di/views/vanban_di_views.xml
git commit -m "feat(format): integrate format_ok badge and format_note alerts into document form views"
```
