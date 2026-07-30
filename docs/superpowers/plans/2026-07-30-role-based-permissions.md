# Role-Based Access Control & Form Readonly Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement strict role-based button visibility (`groups="..."`), Python-layer role checks, form field readonly protection against unauthorized editing, and automated unit tests across `aidt_vanban_den` and `aidt_vanban_di`.

**Tech Stack:** Odoo 19 (Python 3.12, XML views, security groups).

## Global Constraints
- Location: `custom-addons/aidt_vanban_den`, `custom-addons/aidt_vanban_di`
- Security Groups defined in: `addons/aidt_org/security/aidt_org_groups.xml`
- Run test command: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_vanban_den,aidt_vanban_di --test-enable --stop-after-init`

---

### Task 1: Python-layer Role Validation & Unit Tests

**Files:**
- Modify: `custom-addons/aidt_vanban_den/models/aidt_document.py`
- Modify: `custom-addons/aidt_vanban_di/models/aidt_document.py`
- Create: `custom-addons/aidt_vanban_den/tests/test_document_role_permissions.py`

**Steps:**
- [ ] **Step 1: Write unit tests**

Create `custom-addons/aidt_vanban_den/tests/test_document_role_permissions.py`:
```python
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestDocumentRolePermissions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group_chuyen_vien = self.env.ref('aidt_org.group_chuyen_vien')
        self.group_van_thu = self.env.ref('aidt_org.group_van_thu')
        self.group_bi_thu = self.env.ref('aidt_org.group_bi_thu')

        self.user_chuyen_vien = self.env['res.users'].create({
            'name': 'Test Chuyen Vien',
            'login': 'test_cv_user',
            'email': 'cv@test.com',
            'groups_id': [(6, 0, [self.group_chuyen_vien.id])],
        })
        self.user_bi_thu = self.env['res.users'].create({
            'name': 'Test Bi Thu',
            'login': 'test_bt_user',
            'email': 'bt@test.com',
            'groups_id': [(6, 0, [self.group_bi_thu.id])],
        })

    def test_chuyen_vien_cannot_but_phe(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Den',
            'direction': 'den',
            'state': 'trinh_lanh_dao',
            'file_count': 1,
        })
        dept = self.env['hr.department'].create({'name': 'Phong Test'})
        doc.don_vi_chu_tri_id = dept.id

        with self.assertRaises(UserError):
            doc.with_user(self.user_chuyen_vien).action_but_phe()

    def test_bi_thu_can_but_phe(self):
        doc = self.env['aidt.document'].create({
            'name': 'Test Document Den 2',
            'direction': 'den',
            'state': 'trinh_lanh_dao',
            'file_count': 1,
        })
        dept = self.env['hr.department'].create({'name': 'Phong Test 2'})
        doc.don_vi_chu_tri_id = dept.id

        doc.with_user(self.user_bi_thu).action_but_phe()
        self.assertEqual(doc.state, 'dang_xu_ly')
```

- [ ] **Step 2: Add Python role checks in `custom-addons/aidt_vanban_den/models/aidt_document.py` & `custom-addons/aidt_vanban_di/models/aidt_document.py`**

In `aidt_vanban_den/models/aidt_document.py`:
- In `action_register()`: ensure user has `aidt_org.group_van_thu` or `aidt_org.group_aidt_admin`.
- In `action_submit_leader()`: ensure user has `aidt_org.group_van_thu`, `aidt_org.group_chanh_vp` or `aidt_org.group_aidt_admin`.
- In `action_but_phe()`: ensure user has `aidt_org.group_bi_thu`, `aidt_org.group_pho_bi_thu`, `aidt_org.group_chanh_vp` or `aidt_org.group_aidt_admin`.

In `aidt_vanban_di/models/aidt_document.py`:
- In `action_approve_tp()`: ensure user has `aidt_org.group_truong_phong` or `aidt_org.group_aidt_admin`.
- In `action_approve_cvp()`: ensure user has `aidt_org.group_chanh_vp` or `aidt_org.group_aidt_admin`.
- In `action_approve_lanh_dao()` / `action_sign()`: ensure user has `aidt_org.group_bi_thu`, `aidt_org.group_pho_bi_thu` or `aidt_org.group_aidt_admin`.
- In `action_issue_vbd()`: ensure user has `aidt_org.group_van_thu` or `aidt_org.group_aidt_admin`.

- [ ] **Step 3: Run tests & commit**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_vanban_den,aidt_vanban_di --test-enable --stop-after-init`
Commit with message `feat(security): enforce python-layer role checks for document workflow actions`.

---

### Task 2: XML Form View Groups & Readonly Protections

**Files:**
- Modify: `custom-addons/aidt_vanban_den/views/vanban_den_views.xml`
- Modify: `custom-addons/aidt_vanban_di/views/vanban_di_views.xml`

**Steps:**
- [ ] **Step 1: Update XML buttons with `groups="..."` attributes**

In `vanban_den_views.xml`:
- `action_register`: `groups="aidt_org.group_van_thu,aidt_org.group_aidt_admin"`
- `action_submit_leader`: `groups="aidt_org.group_van_thu,aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
- `action_but_phe`: `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
- `action_complete`: `groups="aidt_org.group_chanh_vp,aidt_org.group_bi_thu,aidt_org.group_aidt_admin"`

In `vanban_di_views.xml`:
- `action_submit_tp`: `groups="aidt_org.group_chuyen_vien,aidt_org.group_aidt_admin"`
- `action_approve_tp` / `action_reject_tp`: `groups="aidt_org.group_truong_phong,aidt_org.group_aidt_admin"`
- `action_approve_cvp` / `action_reject_cvp`: `groups="aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
- `action_approve_lanh_dao` / `action_reject_lanh_dao`: `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_aidt_admin"`
- `action_sign`: `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_aidt_admin"`
- `action_issue_vbd`: `groups="aidt_org.group_van_thu,aidt_org.group_aidt_admin"`

- [ ] **Step 2: Add `readonly` expressions on form fields**

In `vanban_den_views.xml` and `vanban_di_views.xml`:
- Primary header fields (`so_den`, `co_quan_gui`, `so_ky_hieu_gui`, `ngay_den`, `do_khan`, `secrecy`, `doc_type`): add `readonly="state not in ('draft', 'tiep_nhan')"`.
- Bút phê fields (`lanh_dao_but_phe_id`, `don_vi_chu_tri_id`, `don_vi_phoi_hop_ids`, `y_kien_but_phe`, `han_xu_ly`): add `readonly="state != 'trinh_lanh_dao'"`.

- [ ] **Step 3: Upgrade module & run tests**

Run: `docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_vanban_den,aidt_vanban_di --test-enable --stop-after-init`

- [ ] **Step 4: Commit changes**

```bash
git add custom-addons/aidt_vanban_den/views/vanban_den_views.xml custom-addons/aidt_vanban_di/views/vanban_di_views.xml
git commit -m "feat(security): enforce role-based button visibility and form field readonly protection"
```
