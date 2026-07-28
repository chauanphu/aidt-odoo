# AIDT Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `aidt_calendar` custom Odoo module for Party/Government office meeting scheduling, room booking conflict prevention, document/DMS linking, 4-level secrecy enforcement (N-04/N-05), follow-up task generation, and public portal appointment booking.

**Architecture:** Custom module `custom-addons/aidt_calendar` inheriting `calendar.event`, `resource.resource`, `project.task`, and `aidt.document`. Uses Odoo ORM constraints for room booking conflict validation and Record Rules for 4-level secrecy control.

**Tech Stack:** Odoo 19 Community ORM (Python 3.12), PostgreSQL 16, XML Views, QWeb, Unit Test Framework (`TransactionCase`).

## Global Constraints

- Module location: `custom-addons/aidt_calendar`.
- Secrecy levels: 4 levels (`thuong`: 0, `mat`: 1, `toi_mat`: 2, `tuyet_mat`: 3).
- Test execution: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo --test-enable -i aidt_calendar --stop-after-init`.

---

### Task 1: Module Scaffolding & Manifest

**Files:**
- Create: `custom-addons/aidt_calendar/__init__.py`
- Create: `custom-addons/aidt_calendar/__manifest__.py`
- Create: `custom-addons/aidt_calendar/models/__init__.py`
- Create: `custom-addons/aidt_calendar/tests/__init__.py`
- Create: `custom-addons/aidt_calendar/tests/test_scaffold.py`

**Interfaces:**
- Consumes: Odoo base modules `calendar`, `resource`, `project`, `aidt_org`, `aidt_dms`.
- Produces: `aidt_calendar` module definition.

- [ ] **Step 1: Write failing test for module manifest**

```python
# custom-addons/aidt_calendar/tests/test_scaffold.py
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestCalendarScaffold(TransactionCase):
    def test_module_installed(self):
        module = self.env['ir.module.module'].search([('name', '=', 'aidt_calendar')])
        self.assertTrue(module, "Module aidt_calendar must exist")
        self.assertEqual(module.state, 'installed', "Module aidt_calendar must be installed")
```

- [ ] **Step 2: Create manifest and init files**

```python
# custom-addons/aidt_calendar/__manifest__.py
{
    'name': 'AIDT Calendar - Lịch họp & Công tác Cấp ủy',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Quản lý lịch họp, phòng họp, liên kết văn bản và bóc tách nhiệm vụ',
    'depends': ['calendar', 'resource', 'project', 'aidt_org', 'aidt_dms'],
    'data': [
        'security/ir.model.access.csv',
        'security/aidt_calendar_rules.xml',
        'views/calendar_event_views.xml',
        'views/appointment_registration_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
```

```python
# custom-addons/aidt_calendar/__init__.py
from . import models

# custom-addons/aidt_calendar/models/__init__.py
# Empty placeholder for models
```

- [ ] **Step 3: Run test to verify module installation**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_calendar
git commit -m "feat(calendar): scaffold aidt_calendar module manifest and tests"
```

---

### Task 2: Model Extension `calendar.event` & Room Booking Constraint

**Files:**
- Create: `custom-addons/aidt_calendar/models/calendar_event.py`
- Modify: `custom-addons/aidt_calendar/models/__init__.py`
- Test: `custom-addons/aidt_calendar/tests/test_calendar_event.py`

**Interfaces:**
- Consumes: `calendar.event`, `aidt.document`, `resource.resource`.
- Produces: Extended `calendar.event` with fields `secrecy`, `secrecy_level`, `room_id`, `document_id`, `is_weekly_schedule` and room conflict constraint.

- [ ] **Step 1: Write failing test for room booking conflict**

```python
# custom-addons/aidt_calendar/tests/test_calendar_event.py
from fields import datetime
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged('post_install', '-at_install')
class TestCalendarEvent(TransactionCase):
    def setUp(self):
        super().setUp()
        self.room = self.env['resource.resource'].create({'name': 'Phòng họp A'})

    def test_room_booking_conflict(self):
        now = datetime.now()
        start1 = now
        stop1 = now.replace(hour=now.hour + 1)
        self.env['calendar.event'].create({
            'name': 'Cuộc họp 1',
            'start': start1,
            'stop': stop1,
            'room_id': self.room.id,
        })
        with self.assertRaises(ValidationError):
            self.env['calendar.event'].create({
                'name': 'Cuộc họp 2 trùng giờ',
                'start': start1,
                'stop': stop1,
                'room_id': self.room.id,
            })
```

- [ ] **Step 2: Implement model fields and constrains**

```python
# custom-addons/aidt_calendar/models/calendar_event.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_SECRECY_LEVEL = {'thuong': 0, 'mat': 1, 'toi_mat': 2, 'tuyet_mat': 3}

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    secrecy = fields.Selection([
        ('thuong', 'Thường'),
        ('mat', 'Mật'),
        ('toi_mat', 'Tối mật'),
        ('tuyet_mat', 'Tuyệt mật'),
    ], string='Độ mật', default='thuong', required=True, tracking=True)
    secrecy_level = fields.Integer(
        string='Mức mật', compute='_compute_secrecy_level', store=True, index=True
    )
    document_id = fields.Many2one('aidt.document', string='Văn bản liên quan')
    room_id = fields.Many2one('resource.resource', string='Phòng họp')
    department_id = fields.Many2one('hr.department', string='Đơn vị chủ trì')
    is_weekly_schedule = fields.Boolean('Lịch công tác tuần', default=False)
    appointment_type = fields.Selection([
        ('internal', 'Nội bộ'),
        ('leadership', 'Lịch Cấp ủy'),
        ('citizen', 'Tiếp công dân'),
    ], string='Loại lịch', default='internal')

    @api.depends('secrecy')
    def _compute_secrecy_level(self):
        for event in self:
            event.secrecy_level = _SECRECY_LEVEL.get(event.secrecy, 0)

    @api.constrains('room_id', 'start', 'stop')
    def _check_room_booking_conflict(self):
        for event in self:
            if not event.room_id or not event.start or not event.stop:
                continue
            conflicts = self.search([
                ('id', '!=', event.id),
                ('room_id', '=', event.room_id.id),
                ('start', '<', event.stop),
                ('stop', '>', event.start),
            ])
            if conflicts:
                raise ValidationError(
                    f"Phòng họp '{event.room_id.name}' đã được đăng ký cho cuộc họp khác trong khoảng thời gian này!"
                )
```

- [ ] **Step 3: Run test to verify constraint passes**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_calendar/models/calendar_event.py custom-addons/aidt_calendar/tests/test_calendar_event.py
git commit -m "feat(calendar): add secrecy level and room booking constraint"
```

---

### Task 3: Security & 4-Level Secrecy Record Rules (N-04/N-05)

**Files:**
- Create: `custom-addons/aidt_calendar/security/ir.model.access.csv`
- Create: `custom-addons/aidt_calendar/security/aidt_calendar_rules.xml`
- Test: `custom-addons/aidt_calendar/tests/test_calendar_security.py`

**Interfaces:**
- Consumes: `calendar.event`, `res.users.clearance_level`.
- Produces: Record rules enforcing `secrecy_level <= user.clearance_level`.

- [ ] **Step 1: Write failing test for secrecy access control**

```python
# custom-addons/aidt_calendar/tests/test_calendar_security.py
from fields import datetime
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestCalendarSecurity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user_low = self.env['res.users'].create({
            'name': 'User Low Clearance',
            'login': 'user_low_cal',
            'email': 'low@test.com',
            'clearance_level': 0,
        })
        self.event_secret = self.env['calendar.event'].create({
            'name': 'Cuộc họp Tuyệt mật',
            'start': datetime.now(),
            'stop': datetime.now(),
            'secrecy': 'tuyet_mat',
        })

    def test_user_cannot_read_secret_meeting(self):
        events = self.env['calendar.event'].with_user(self.user_low).search([
            ('id', '=', self.event_secret.id)
        ])
        self.assertFalse(events, "User with clearance level 0 must not see secret meeting")
```

- [ ] **Step 2: Create Record Rules XML**

```xml
<!-- custom-addons/aidt_calendar/security/aidt_calendar_rules.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="calendar_event_rule_secrecy" model="ir.rule">
        <field name="name">Calendar Event Secrecy Access Rule</field>
        <field name="model_id" ref="calendar.model_calendar_event"/>
        <field name="domain_force">
            [('secrecy_level', '&lt;=', user.clearance_level)]
        </field>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="True"/>
    </record>
</odoo>
```

- [ ] **Step 3: Run security tests**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_calendar/security/ custom-addons/aidt_calendar/tests/test_calendar_security.py
git commit -m "security(calendar): enforce 4-level secrecy record rules for calendar events"
```

---

### Task 4: Follow-up Task Generation Integration (`project.task`)

**Files:**
- Create: `custom-addons/aidt_calendar/models/project_task.py`
- Modify: `custom-addons/aidt_calendar/models/calendar_event.py`
- Test: `custom-addons/aidt_calendar/tests/test_meeting_task.py`

**Interfaces:**
- Consumes: `calendar.event`, `project.task`.
- Produces: Action `action_create_followup_task` on `calendar.event` linking to `project.task`.

- [ ] **Step 1: Write failing test for task creation from meeting**

```python
# custom-addons/aidt_calendar/tests/test_meeting_task.py
from fields import datetime
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestMeetingTask(TransactionCase):
    def test_create_task_from_meeting(self):
        event = self.env['calendar.event'].create({
            'name': 'Họp chỉ đạo Kế hoạch 2026',
            'start': datetime.now(),
            'stop': datetime.now(),
        })
        action = event.action_create_followup_task()
        self.assertEqual(action['res_model'], 'project.task')
        self.assertEqual(action['context']['default_meeting_id'], event.id)
```

- [ ] **Step 2: Implement project.task inheritance and meeting action**

```python
# custom-addons/aidt_calendar/models/project_task.py
from odoo import fields, models

class ProjectTask(models.Model):
    _inherit = 'project.task'

    meeting_id = fields.Many2one('calendar.event', string='Từ cuộc họp')
```

Add method to `calendar_event.py`:
```python
def action_create_followup_task(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': f'Nhiệm vụ từ cuộc họp: {self.name}',
        'res_model': 'project.task',
        'view_mode': 'form',
        'target': 'current',
        'context': {
            'default_name': f'Thực hiện kết luận cuộc họp: {self.name}',
            'default_meeting_id': self.id,
            'default_department_id': self.department_id.id if self.department_id else False,
        }
    }
```

- [ ] **Step 3: Run test**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_calendar/models/project_task.py custom-addons/aidt_calendar/tests/test_meeting_task.py
git commit -m "feat(calendar): implement follow-up task generation from meeting"
```

---

### Task 5: Views, Form Extensions & Weekly Schedule Menu

**Files:**
- Create: `custom-addons/aidt_calendar/views/calendar_event_views.xml`
- Test: `custom-addons/aidt_calendar/tests/test_calendar_views.py`

**Interfaces:**
- Consumes: `calendar.view_calendar_event_form`.
- Produces: Extended form view with secrecy, document link, room selection, task action button, and weekly schedule menu.

- [ ] **Step 1: Write test verifying view loading**

```python
# custom-addons/aidt_calendar/tests/test_calendar_views.py
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestCalendarViews(TransactionCase):
    def test_calendar_views_exist(self):
        view = self.env.ref('aidt_calendar.calendar_event_view_form_inherit')
        self.assertTrue(view, "Inherited form view must exist")
```

- [ ] **Step 2: Create Views XML**

```xml
<!-- custom-addons/aidt_calendar/views/calendar_event_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="calendar_event_view_form_inherit" model="ir.ui.view">
        <field name="name">calendar.event.form.aidt</field>
        <field name="model">calendar.event</field>
        <field name="inherit_id" ref="calendar.view_calendar_event_form"/>
        <field name="arch" type="xml">
            <xpath expr="//header" position="inside">
                <button name="action_create_followup_task" string="Tạo nhiệm vụ chỉ đạo" type="object" class="btn-primary"/>
            </xpath>
            <xpath expr="//field[@name='categ_ids']" position="after">
                <field name="secrecy"/>
                <field name="document_id"/>
                <field name="room_id"/>
                <field name="department_id"/>
                <field name="is_weekly_schedule"/>
                <field name="appointment_type"/>
            </xpath>
        </field>
    </record>

    <record id="action_weekly_schedule" model="ir.actions.act_window">
        <field name="name">Lịch công tác tuần</field>
        <field name="res_model">calendar.event</field>
        <field name="view_mode">list,calendar,form</field>
        <field name="domain">[('is_weekly_schedule', '=', True)]</field>
    </record>

    <menuitem id="menu_weekly_schedule" parent="calendar.mail_menu_calendar" name="Lịch công tác tuần" action="action_weekly_schedule" sequence="5"/>
</odoo>
```

- [ ] **Step 3: Run test**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_calendar/views/calendar_event_views.xml custom-addons/aidt_calendar/tests/test_calendar_views.py
git commit -m "feat(calendar): add form view extensions and weekly schedule menu"
```

---

### Task 6: Public Portal Appointment Booking

**Files:**
- Create: `custom-addons/aidt_calendar/models/appointment_registration.py`
- Create: `custom-addons/aidt_calendar/controllers/main.py`
- Create: `custom-addons/aidt_calendar/views/appointment_registration_views.xml`
- Test: `custom-addons/aidt_calendar/tests/test_portal_appointment.py`

**Interfaces:**
- Consumes: Odoo `http.Controller`, `calendar.event`.
- Produces: Public portal registration form and backend approval flow.

- [ ] **Step 1: Write failing test for portal appointment approval**

```python
# custom-addons/aidt_calendar/tests/test_portal_appointment.py
from fields import datetime
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestPortalAppointment(TransactionCase):
    def test_approve_appointment_registration(self):
        reg = self.env['aidt.appointment.registration'].create({
            'name': 'Nguyễn Văn A',
            'phone': '0912345678',
            'content': 'Xin tiếp làm việc về đơn thư đất đai',
            'preferred_date': datetime.now(),
        })
        reg.action_approve()
        self.assertEqual(reg.state, 'approved')
        self.assertTrue(reg.event_id, "Event must be created on approval")
```

- [ ] **Step 2: Implement registration model and controller**

```python
# custom-addons/aidt_calendar/models/appointment_registration.py
from odoo import fields, models

class AppointmentRegistration(models.Model):
    _name = 'aidt.appointment.registration'
    _description = 'Đăng ký tiếp dân / làm việc'
    _inherit = ['mail.thread']

    name = fields.Char('Họ và tên', required=True)
    identity_card = fields.Char('Số CCCD / MST')
    phone = fields.Char('Số điện thoại', required=True)
    email = fields.Char('Email')
    organization = fields.Char('Cơ quan / Đơn vị')
    content = fields.Text('Nội dung làm việc', required=True)
    preferred_date = fields.Datetime('Thời gian đề xuất', required=True)
    state = fields.Selection([
        ('draft', 'Mới tiếp nhận'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái', default='draft', tracking=True)
    event_id = fields.Many2one('calendar.event', string='Cuộc họp tạo ra')

    def action_approve(self):
        for reg in self:
            event = self.env['calendar.event'].create({
                'name': f'Tiếp dân: {reg.name} - {reg.content[:50]}',
                'start': reg.preferred_date,
                'stop': reg.preferred_date,
                'appointment_type': 'citizen',
                'description': f'Người đăng ký: {reg.name}\nSĐT: {reg.phone}\nNội dung: {reg.content}',
            })
            reg.write({'state': 'approved', 'event_id': event.id})
```

- [ ] **Step 3: Create Controller & Views**

```python
# custom-addons/aidt_calendar/controllers/main.py
from odoo import http
from odoo.http import request

class AppointmentController(http.Controller):
    @http.route('/dang-ky-lich-lam-viec', type='http', auth='public', website=True, sitemap=True)
    def appointment_form(self, **kw):
        return request.render('aidt_calendar.appointment_page', {})
```

- [ ] **Step 4: Run test**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_calendar --test-enable --stop-after-init`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom-addons/aidt_calendar
git commit -m "feat(calendar): implement public portal appointment registration and approval flow"
```
