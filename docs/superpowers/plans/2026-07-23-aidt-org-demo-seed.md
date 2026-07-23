# AIDT Org Demo Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hai module Odoo (`aidt_org` core + `aidt_org_demo` seed) chứng minh N-02 (cây tổ chức), N-03 (RBAC), N-05 (phân quyền phạm vi) theo spec `docs/superpowers/specs/2026-07-23-aidt-org-demo-seed-design.md`.

**Architecture:** `aidt_org` chứa model `aidt.document` + `hr.department.unit_type`, 6 groups kế thừa chuỗi, 2 ir.rule phạm vi (`child_of` theo đơn vị + chia sẻ đích danh). `aidt_org_demo` chỉ chứa data XML `noupdate="1"` (14 phòng ban, 20 cán bộ/users, 15 văn bản), gỡ được độc lập.

**Tech Stack:** Odoo 19 (repo này), PostgreSQL 16 qua `docker-compose.dev.yml`, XML data + Python model, test `odoo.tests.TransactionCase`.

## Global Constraints

- Odoo 19 API: field users↔groups là `group_ids` (KHÔNG phải `groups_id`); list view dùng `<list>` (KHÔNG phải `<tree>`); chatter trong form dùng `<chatter/>`.
- Manifest: `'license': 'LGPL-3'`; không sửa bất kỳ module core nào (`odoo/`, `addons/hr`...).
- Nhãn hiển thị tiếng Việt có dấu; xml id/login không dấu.
- Mọi file data seed trong `aidt_org_demo` bọc `<data noupdate="1">`.
- Lệnh Odoo trong container theo mẫu đã có trong `docker-compose.dev.yml`: `docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf ...`
- DB dev: `aidt_demo` (demo tay), `aidt_test` (chạy test). Odoo 19 CLI mặc định KHÔNG cài demo data (`--with-demo` default False) — không cần thêm flag.
- Commit message theo style repo: `[ADD] aidt_org: ...`, kèm trailer Co-Authored-By như quy định session.

**Điều kiện trước khi bắt đầu:** `docker compose -f docker-compose.dev.yml up -d db` (chỉ cần DB; các lệnh odoo dùng `run --rm`).

---

### Task 1: Module `aidt_org` — skeleton, models, groups, ACL

**Files:**
- Create: `addons/aidt_org/__init__.py`
- Create: `addons/aidt_org/__manifest__.py`
- Create: `addons/aidt_org/models/__init__.py`
- Create: `addons/aidt_org/models/hr_department.py`
- Create: `addons/aidt_org/models/aidt_document.py`
- Create: `addons/aidt_org/security/aidt_org_groups.xml`
- Create: `addons/aidt_org/security/ir.model.access.csv`

**Interfaces:**
- Produces: model `aidt.document` (fields: `name`, `reference`, `department_id`, `shared_user_ids`, `doc_type`, `date`, `state`); field `hr.department.unit_type`; xml ids `aidt_org.group_chuyen_vien`, `group_van_thu`, `group_chanh_vp`, `group_pho_bi_thu`, `group_bi_thu`, `group_aidt_admin` — Task 2/4/5 dùng đúng các tên này.

- [ ] **Step 1: Tạo `addons/aidt_org/__init__.py`**

```python
from . import models
```

- [ ] **Step 2: Tạo `addons/aidt_org/__manifest__.py`** (chưa khai báo rules/views — thêm ở Task 2/3)

```python
{
    'name': 'AIDT Tổ chức & Văn bản',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Cây tổ chức, RBAC vai trò, phân quyền phạm vi văn bản (N-02/N-03/N-05)',
    'depends': ['hr', 'mail'],
    'data': [
        'security/aidt_org_groups.xml',
        'security/ir.model.access.csv',
    ],
    'license': 'LGPL-3',
}
```

- [ ] **Step 3: Tạo `addons/aidt_org/models/__init__.py`**

```python
from . import hr_department
from . import aidt_document
```

- [ ] **Step 4: Tạo `addons/aidt_org/models/hr_department.py`**

```python
from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    unit_type = fields.Selection(
        [('cap_uy', 'Cấp ủy'), ('ban', 'Ban'), ('phong', 'Phòng')],
        string='Loại đơn vị',
    )
```

- [ ] **Step 5: Tạo `addons/aidt_org/models/aidt_document.py`**

```python
from odoo import fields, models


class AidtDocument(models.Model):
    _name = 'aidt.document'
    _description = 'Văn bản'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Trích yếu', required=True, tracking=True)
    reference = fields.Char(string='Số/Ký hiệu')
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị', required=True, index=True)
    shared_user_ids = fields.Many2many('res.users', string='Chia sẻ với')
    doc_type = fields.Selection(
        [('cong_van', 'Công văn'), ('bao_cao', 'Báo cáo'),
         ('ke_hoach', 'Kế hoạch'), ('quyet_dinh', 'Quyết định')],
        string='Loại văn bản', default='cong_van')
    date = fields.Date(string='Ngày ban hành')
    state = fields.Selection(
        [('draft', 'Dự thảo'), ('issued', 'Đã ban hành'), ('archived', 'Lưu trữ')],
        string='Trạng thái', default='draft', tracking=True)
```

- [ ] **Step 6: Tạo `addons/aidt_org/security/aidt_org_groups.xml`** (pattern theo `addons/hr/security/hr_security.xml`)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="res_groups_privilege_aidt_document" model="res.groups.privilege">
        <field name="name">Quản lý văn bản</field>
        <field name="sequence">30</field>
        <field name="category_id" ref="base.module_category_human_resources"/>
    </record>

    <record id="group_chuyen_vien" model="res.groups">
        <field name="name">Chuyên viên</field>
        <field name="sequence">10</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
        <field name="comment">Đọc và soạn dự thảo văn bản trong phạm vi đơn vị mình.</field>
    </record>

    <record id="group_van_thu" model="res.groups">
        <field name="name">Văn thư</field>
        <field name="sequence">20</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('group_chuyen_vien'))]"/>
        <field name="comment">Đăng ký, cấp số văn bản của đơn vị.</field>
    </record>

    <record id="group_chanh_vp" model="res.groups">
        <field name="name">Chánh Văn phòng / Trưởng đơn vị</field>
        <field name="sequence">30</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('group_van_thu'))]"/>
        <field name="comment">Duyệt và ban hành văn bản trong nhánh đơn vị mình phụ trách.</field>
    </record>

    <record id="group_pho_bi_thu" model="res.groups">
        <field name="name">Phó Bí thư</field>
        <field name="sequence">40</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('group_chanh_vp'))]"/>
    </record>

    <record id="group_bi_thu" model="res.groups">
        <field name="name">Bí thư</field>
        <field name="sequence">50</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('group_pho_bi_thu'))]"/>
    </record>

    <record id="group_aidt_admin" model="res.groups">
        <field name="name">Quản trị hệ thống văn bản</field>
        <field name="sequence">60</field>
        <field name="privilege_id" ref="res_groups_privilege_aidt_document"/>
        <field name="implied_ids" eval="[(4, ref('group_bi_thu'))]"/>
        <field name="user_ids" eval="[(4, ref('base.user_admin'))]"/>
        <field name="comment">Toàn quyền, không giới hạn phạm vi đơn vị.</field>
    </record>

</odoo>
```

- [ ] **Step 7: Tạo `addons/aidt_org/security/ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_aidt_document_chuyen_vien,aidt.document chuyen vien,model_aidt_document,group_chuyen_vien,1,1,1,0
access_aidt_document_admin,aidt.document admin,model_aidt_document,group_aidt_admin,1,1,1,1
```

- [ ] **Step 8: Cài module trên DB test để xác nhận installable**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -i aidt_org --stop-after-init
```
Expected: exit 0, log có `Module aidt_org loaded` (hoặc `loading aidt_org`), KHÔNG có dòng `ERROR`/`CRITICAL`.

- [ ] **Step 9: Commit**

```bash
git add addons/aidt_org
git commit -m "[ADD] aidt_org: document model, unit_type, role groups and ACL"
```

---

### Task 2: TDD record rules — test phạm vi trước, rule sau

**Files:**
- Create: `addons/aidt_org/tests/__init__.py`
- Create: `addons/aidt_org/tests/test_document_scope.py`
- Create: `addons/aidt_org/security/aidt_org_rules.xml`
- Modify: `addons/aidt_org/__manifest__.py` (thêm 1 dòng data)

**Interfaces:**
- Consumes: model `aidt.document`, groups `aidt_org.group_*` (Task 1).
- Produces: xml ids `aidt_org.rule_aidt_document_scope`, `aidt_org.rule_aidt_document_admin`.

- [ ] **Step 1: Tạo `addons/aidt_org/tests/__init__.py`**

```python
from . import test_document_scope
```

- [ ] **Step 2: Tạo `addons/aidt_org/tests/test_document_scope.py`** — fixture tự chứa, không phụ thuộc `aidt_org_demo`

```python
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestDocumentScope(TransactionCase):
    """Kịch bản O-03: đóng vai từng vai trò, xác nhận phạm vi N-05."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Department = cls.env['hr.department']
        cls.dept_root = Department.create({'name': 'Tỉnh ủy Test', 'unit_type': 'cap_uy'})
        cls.dept_vp = Department.create(
            {'name': 'Văn phòng', 'unit_type': 'ban', 'parent_id': cls.dept_root.id})
        cls.dept_th = Department.create(
            {'name': 'Phòng Tổng hợp', 'unit_type': 'phong', 'parent_id': cls.dept_vp.id})
        cls.dept_tc = Department.create(
            {'name': 'Ban Tổ chức', 'unit_type': 'ban', 'parent_id': cls.dept_root.id})

        group_cv = cls.env.ref('aidt_org.group_chuyen_vien')
        group_cvp = cls.env.ref('aidt_org.group_chanh_vp')
        group_bt = cls.env.ref('aidt_org.group_bi_thu')

        cls.user_cv = cls._make_user('test_cv', group_cv, cls.dept_th)
        cls.user_cvp = cls._make_user('test_cvp', group_cvp, cls.dept_vp)
        cls.user_bt = cls._make_user('test_bt', group_bt, cls.dept_root)
        cls.user_tc = cls._make_user('test_tc', group_cv, cls.dept_tc)

        Doc = cls.env['aidt.document']
        cls.doc_th = Doc.create({'name': 'VB Tổng hợp', 'department_id': cls.dept_th.id})
        cls.doc_vp = Doc.create({'name': 'VB Văn phòng', 'department_id': cls.dept_vp.id})
        cls.doc_tc = Doc.create({'name': 'VB Ban TC', 'department_id': cls.dept_tc.id})
        cls.doc_shared = Doc.create({
            'name': 'VB chia sẻ chéo', 'department_id': cls.dept_tc.id,
            'shared_user_ids': [(4, cls.user_cv.id)],
        })

    @classmethod
    def _make_user(cls, login, group, department):
        user = cls.env['res.users'].create({
            'name': login,
            'login': login,
            'group_ids': [(4, group.id)],
        })
        cls.env['hr.employee'].create({
            'name': login,
            'user_id': user.id,
            'department_id': department.id,
        })
        return user

    def test_cv_sees_own_department_and_shared_only(self):
        """CV Phòng Tổng hợp: chỉ VB phòng mình + VB được chia sẻ."""
        docs = self.env['aidt.document'].with_user(self.user_cv).search([])
        self.assertEqual(set(docs.ids), {self.doc_th.id, self.doc_shared.id})

    def test_chanh_vp_sees_whole_branch(self):
        """Chánh VP: toàn nhánh Văn phòng (child_of), không thấy Ban TC."""
        docs = self.env['aidt.document'].with_user(self.user_cvp).search([])
        self.assertEqual(set(docs.ids), {self.doc_th.id, self.doc_vp.id})

    def test_bi_thu_sees_all(self):
        """Bí thư ở root: thấy toàn bộ."""
        docs = self.env['aidt.document'].with_user(self.user_bt).search([])
        self.assertEqual(set(docs.ids), {
            self.doc_th.id, self.doc_vp.id, self.doc_tc.id, self.doc_shared.id})

    def test_create_outside_scope_raises(self):
        """CV Ban TC tạo VB gán cho Phòng Tổng hợp → AccessError."""
        with self.assertRaises(AccessError):
            self.env['aidt.document'].with_user(self.user_tc).create({
                'name': 'VB lấn sân', 'department_id': self.dept_th.id,
            })
```

- [ ] **Step 3: Chạy test — xác nhận FAIL (chưa có rule, ai cũng thấy hết)**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -u aidt_org --test-tags /aidt_org --stop-after-init
```
Expected: exit ≠ 0; log có `FAIL: TestDocumentScope.test_cv_sees_own_department_and_shared_only` và `test_chanh_vp_sees_whole_branch`, `test_create_outside_scope_raises` (CV đang thấy cả 4 VB vì chưa có ir.rule). `test_bi_thu_sees_all` PASS là bình thường.

- [ ] **Step 4: Tạo `addons/aidt_org/security/aidt_org_rules.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <record id="rule_aidt_document_scope" model="ir.rule">
        <field name="name">Văn bản: phạm vi đơn vị mình + được chia sẻ</field>
        <field name="model_id" ref="model_aidt_document"/>
        <field name="groups" eval="[(4, ref('group_chuyen_vien'))]"/>
        <field name="domain_force">['|', ('department_id', 'child_of', user.employee_id.department_id.ids), ('shared_user_ids', 'in', [user.id])]</field>
    </record>

    <record id="rule_aidt_document_admin" model="ir.rule">
        <field name="name">Văn bản: quản trị toàn quyền</field>
        <field name="model_id" ref="model_aidt_document"/>
        <field name="groups" eval="[(4, ref('group_aidt_admin'))]"/>
        <field name="domain_force">[(1, '=', 1)]</field>
    </record>

</data>
</odoo>
```

- [ ] **Step 5: Thêm rules vào `addons/aidt_org/__manifest__.py`** — sửa key `data` thành:

```python
    'data': [
        'security/aidt_org_groups.xml',
        'security/ir.model.access.csv',
        'security/aidt_org_rules.xml',
    ],
```

- [ ] **Step 6: Chạy lại test — xác nhận PASS cả 4**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -u aidt_org --test-tags /aidt_org --stop-after-init
```
Expected: exit 0, log có `4 tests` / `0 failed, 0 error(s)`.

- [ ] **Step 7: Commit**

```bash
git add addons/aidt_org
git commit -m "[ADD] aidt_org: scope record rules with O-03 role-play tests"
```

---

### Task 3: Views & menu

**Files:**
- Create: `addons/aidt_org/views/aidt_document_views.xml`
- Create: `addons/aidt_org/views/hr_department_views.xml`
- Modify: `addons/aidt_org/__manifest__.py`

**Interfaces:**
- Consumes: model `aidt.document` (Task 1).
- Produces: menu root `aidt_org.menu_aidt_root` ("Văn bản") — dùng trong demo tay Task 6.

- [ ] **Step 1: Tạo `addons/aidt_org/views/aidt_document_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="aidt_document_view_list" model="ir.ui.view">
        <field name="name">aidt.document.list</field>
        <field name="model">aidt.document</field>
        <field name="arch" type="xml">
            <list>
                <field name="reference"/>
                <field name="name"/>
                <field name="doc_type"/>
                <field name="department_id"/>
                <field name="date"/>
                <field name="state"/>
            </list>
        </field>
    </record>

    <record id="aidt_document_view_form" model="ir.ui.view">
        <field name="name">aidt.document.form</field>
        <field name="model">aidt.document</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="reference"/>
                            <field name="doc_type"/>
                            <field name="state"/>
                        </group>
                        <group>
                            <field name="department_id"/>
                            <field name="date"/>
                            <field name="shared_user_ids" widget="many2many_tags"/>
                        </group>
                    </group>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>

    <record id="aidt_document_action" model="ir.actions.act_window">
        <field name="name">Văn bản</field>
        <field name="res_model">aidt.document</field>
        <field name="view_mode">list,form</field>
    </record>

    <menuitem id="menu_aidt_root" name="Văn bản" sequence="5"/>
    <menuitem id="menu_aidt_document" parent="menu_aidt_root"
              action="aidt_document_action" sequence="10"/>

</odoo>
```

- [ ] **Step 2: Tạo `addons/aidt_org/views/hr_department_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_department_form_inherit_aidt" model="ir.ui.view">
        <field name="name">hr.department.form.aidt</field>
        <field name="model">hr.department</field>
        <field name="inherit_id" ref="hr.view_department_form"/>
        <field name="arch" type="xml">
            <field name="parent_id" position="after">
                <field name="unit_type"/>
            </field>
        </field>
    </record>

</odoo>
```

Lưu ý: nếu upgrade báo lỗi không tìm thấy `parent_id` trong `hr.view_department_form`, mở `addons/hr/views/hr_department_views.xml` tìm field có thật trong form (vd `manager_id`) và đổi anchor `position="after"` sang field đó — chỉ đổi anchor, không đổi nội dung thêm vào.

- [ ] **Step 3: Thêm views vào `addons/aidt_org/__manifest__.py`** — key `data` thành:

```python
    'data': [
        'security/aidt_org_groups.xml',
        'security/ir.model.access.csv',
        'security/aidt_org_rules.xml',
        'views/aidt_document_views.xml',
        'views/hr_department_views.xml',
    ],
```

- [ ] **Step 4: Upgrade để xác nhận views hợp lệ**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -u aidt_org --stop-after-init
```
Expected: exit 0, không có `ERROR` (view validation chạy lúc upgrade).

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_org
git commit -m "[ADD] aidt_org: document views, menu and department unit_type field"
```

---

### Task 4: Module `aidt_org_demo` — cây đơn vị + cán bộ + users

**Files:**
- Create: `addons/aidt_org_demo/__init__.py` (rỗng)
- Create: `addons/aidt_org_demo/__manifest__.py`
- Create: `addons/aidt_org_demo/data/org_departments.xml`
- Create: `addons/aidt_org_demo/data/org_employees_users.xml`

**Interfaces:**
- Consumes: `hr.department.unit_type`, groups `aidt_org.group_*`.
- Produces: xml ids `aidt_org_demo.dept_*` (14 phòng ban), `aidt_org_demo.user_*` / `employee_*` (20 cán bộ) — Task 5 tham chiếu.

- [ ] **Step 1: Tạo `addons/aidt_org_demo/__init__.py`** — file rỗng.

- [ ] **Step 2: Tạo `addons/aidt_org_demo/__manifest__.py`**

```python
{
    'name': 'AIDT Tổ chức & Văn bản — Dữ liệu demo',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Seed demo: cây Tỉnh ủy 3 cấp, 20 cán bộ, văn bản mẫu',
    'depends': ['aidt_org'],
    'data': [
        'data/org_departments.xml',
        'data/org_employees_users.xml',
        'data/org_documents.xml',
    ],
    'license': 'LGPL-3',
}
```

(File `data/org_documents.xml` tạo ở Task 5 — trong Task 4, tạm để `data` chỉ gồm 2 dòng đầu, thêm dòng thứ 3 ở Task 5.)

- [ ] **Step 3: Tạo `addons/aidt_org_demo/data/org_departments.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <record id="dept_tinh_uy" model="hr.department">
        <field name="name">Tỉnh ủy Demo</field>
        <field name="unit_type">cap_uy</field>
    </record>

    <!-- Văn phòng Tỉnh ủy -->
    <record id="dept_vptu" model="hr.department">
        <field name="name">Văn phòng Tỉnh ủy</field>
        <field name="unit_type">ban</field>
        <field name="parent_id" ref="dept_tinh_uy"/>
    </record>
    <record id="dept_tonghop" model="hr.department">
        <field name="name">Phòng Tổng hợp</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_vptu"/>
    </record>
    <record id="dept_hclt" model="hr.department">
        <field name="name">Phòng Hành chính – Lưu trữ</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_vptu"/>
    </record>
    <record id="dept_quantri" model="hr.department">
        <field name="name">Phòng Quản trị</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_vptu"/>
    </record>

    <!-- Ban Tổ chức -->
    <record id="dept_btc" model="hr.department">
        <field name="name">Ban Tổ chức Tỉnh ủy</field>
        <field name="unit_type">ban</field>
        <field name="parent_id" ref="dept_tinh_uy"/>
    </record>
    <record id="dept_tccb" model="hr.department">
        <field name="name">Phòng Tổ chức – Cán bộ</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_btc"/>
    </record>
    <record id="dept_csd" model="hr.department">
        <field name="name">Phòng Cơ sở đảng – Đảng viên</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_btc"/>
    </record>

    <!-- Ban Tuyên giáo -->
    <record id="dept_btg" model="hr.department">
        <field name="name">Ban Tuyên giáo Tỉnh ủy</field>
        <field name="unit_type">ban</field>
        <field name="parent_id" ref="dept_tinh_uy"/>
    </record>
    <record id="dept_tuyentruyen" model="hr.department">
        <field name="name">Phòng Tuyên truyền</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_btg"/>
    </record>
    <record id="dept_lyluan" model="hr.department">
        <field name="name">Phòng Lý luận chính trị</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_btg"/>
    </record>

    <!-- Ủy ban Kiểm tra -->
    <record id="dept_ubkt" model="hr.department">
        <field name="name">Ủy ban Kiểm tra Tỉnh ủy</field>
        <field name="unit_type">ban</field>
        <field name="parent_id" ref="dept_tinh_uy"/>
    </record>
    <record id="dept_nv1" model="hr.department">
        <field name="name">Phòng Nghiệp vụ 1</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_ubkt"/>
    </record>
    <record id="dept_nv2" model="hr.department">
        <field name="name">Phòng Nghiệp vụ 2</field>
        <field name="unit_type">phong</field>
        <field name="parent_id" ref="dept_ubkt"/>
    </record>

</data>
</odoo>
```

- [ ] **Step 4: Tạo `addons/aidt_org_demo/data/org_employees_users.xml`**

Pattern mỗi cán bộ = 1 `res.users` + 1 `hr.employee` (link qua `user_id`, manager chain qua `parent_id`). Mật khẩu chung `demo2026`. File đầy đủ 20 cặp — dưới đây là toàn bộ nội dung:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <!-- ===== Tỉnh ủy ===== -->
    <record id="user_bithu" model="res.users">
        <field name="name">Nguyễn Văn An</field>
        <field name="login">bithu</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_bi_thu'))]"/>
    </record>
    <record id="employee_bithu" model="hr.employee">
        <field name="name">Nguyễn Văn An</field>
        <field name="job_title">Bí thư</field>
        <field name="department_id" ref="dept_tinh_uy"/>
        <field name="user_id" ref="user_bithu"/>
    </record>

    <record id="user_photbt" model="res.users">
        <field name="name">Trần Thị Bình</field>
        <field name="login">photbt</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_pho_bi_thu'))]"/>
    </record>
    <record id="employee_photbt" model="hr.employee">
        <field name="name">Trần Thị Bình</field>
        <field name="job_title">Phó Bí thư Thường trực</field>
        <field name="department_id" ref="dept_tinh_uy"/>
        <field name="user_id" ref="user_photbt"/>
        <field name="parent_id" ref="employee_bithu"/>
    </record>

    <!-- ===== Văn phòng Tỉnh ủy ===== -->
    <record id="user_chanhvp" model="res.users">
        <field name="name">Lê Minh Châu</field>
        <field name="login">chanhvp</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_chanhvp" model="hr.employee">
        <field name="name">Lê Minh Châu</field>
        <field name="job_title">Chánh Văn phòng</field>
        <field name="department_id" ref="dept_vptu"/>
        <field name="user_id" ref="user_chanhvp"/>
        <field name="parent_id" ref="employee_bithu"/>
    </record>

    <record id="user_phochanhvp" model="res.users">
        <field name="name">Phạm Quốc Dũng</field>
        <field name="login">phochanhvp</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_phochanhvp" model="hr.employee">
        <field name="name">Phạm Quốc Dũng</field>
        <field name="job_title">Phó Chánh Văn phòng</field>
        <field name="department_id" ref="dept_vptu"/>
        <field name="user_id" ref="user_phochanhvp"/>
        <field name="parent_id" ref="employee_chanhvp"/>
    </record>

    <record id="user_tp_tonghop" model="res.users">
        <field name="name">Hoàng Thu Em</field>
        <field name="login">tp.tonghop</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_tp_tonghop" model="hr.employee">
        <field name="name">Hoàng Thu Em</field>
        <field name="job_title">Trưởng phòng Tổng hợp</field>
        <field name="department_id" ref="dept_tonghop"/>
        <field name="user_id" ref="user_tp_tonghop"/>
        <field name="parent_id" ref="employee_chanhvp"/>
    </record>

    <record id="user_cv_tonghop1" model="res.users">
        <field name="name">Vũ Văn Phú</field>
        <field name="login">cv.tonghop1</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_tonghop1" model="hr.employee">
        <field name="name">Vũ Văn Phú</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_tonghop"/>
        <field name="user_id" ref="user_cv_tonghop1"/>
        <field name="parent_id" ref="employee_tp_tonghop"/>
    </record>

    <record id="user_cv_tonghop2" model="res.users">
        <field name="name">Đỗ Thị Giang</field>
        <field name="login">cv.tonghop2</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_tonghop2" model="hr.employee">
        <field name="name">Đỗ Thị Giang</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_tonghop"/>
        <field name="user_id" ref="user_cv_tonghop2"/>
        <field name="parent_id" ref="employee_tp_tonghop"/>
    </record>

    <record id="user_tp_hanhchinh" model="res.users">
        <field name="name">Ngô Đức Inh</field>
        <field name="login">tp.hanhchinh</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_tp_hanhchinh" model="hr.employee">
        <field name="name">Ngô Đức Inh</field>
        <field name="job_title">Trưởng phòng Hành chính – Lưu trữ</field>
        <field name="department_id" ref="dept_hclt"/>
        <field name="user_id" ref="user_tp_hanhchinh"/>
        <field name="parent_id" ref="employee_chanhvp"/>
    </record>

    <record id="user_vanthu" model="res.users">
        <field name="name">Bùi Thị Hoa</field>
        <field name="login">vanthu</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_van_thu'))]"/>
    </record>
    <record id="employee_vanthu" model="hr.employee">
        <field name="name">Bùi Thị Hoa</field>
        <field name="job_title">Văn thư</field>
        <field name="department_id" ref="dept_hclt"/>
        <field name="user_id" ref="user_vanthu"/>
        <field name="parent_id" ref="employee_tp_hanhchinh"/>
    </record>

    <record id="user_tp_quantri" model="res.users">
        <field name="name">Đặng Văn Khang</field>
        <field name="login">tp.quantri</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_tp_quantri" model="hr.employee">
        <field name="name">Đặng Văn Khang</field>
        <field name="job_title">Trưởng phòng Quản trị</field>
        <field name="department_id" ref="dept_quantri"/>
        <field name="user_id" ref="user_tp_quantri"/>
        <field name="parent_id" ref="employee_chanhvp"/>
    </record>

    <!-- ===== Ban Tổ chức ===== -->
    <record id="user_truongban_tc" model="res.users">
        <field name="name">Cao Thị Lan</field>
        <field name="login">truongban.tc</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_truongban_tc" model="hr.employee">
        <field name="name">Cao Thị Lan</field>
        <field name="job_title">Trưởng Ban Tổ chức</field>
        <field name="department_id" ref="dept_btc"/>
        <field name="user_id" ref="user_truongban_tc"/>
        <field name="parent_id" ref="employee_bithu"/>
    </record>

    <record id="user_tp_tccb" model="res.users">
        <field name="name">Lý Văn Minh</field>
        <field name="login">tp.tccb</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_tp_tccb" model="hr.employee">
        <field name="name">Lý Văn Minh</field>
        <field name="job_title">Trưởng phòng Tổ chức – Cán bộ</field>
        <field name="department_id" ref="dept_tccb"/>
        <field name="user_id" ref="user_tp_tccb"/>
        <field name="parent_id" ref="employee_truongban_tc"/>
    </record>

    <record id="user_cv_tccb" model="res.users">
        <field name="name">Phan Thị Nga</field>
        <field name="login">cv.tccb</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_tccb" model="hr.employee">
        <field name="name">Phan Thị Nga</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_tccb"/>
        <field name="user_id" ref="user_cv_tccb"/>
        <field name="parent_id" ref="employee_tp_tccb"/>
    </record>

    <record id="user_cv_csd" model="res.users">
        <field name="name">Trịnh Văn Oanh</field>
        <field name="login">cv.csd</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_csd" model="hr.employee">
        <field name="name">Trịnh Văn Oanh</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_csd"/>
        <field name="user_id" ref="user_cv_csd"/>
        <field name="parent_id" ref="employee_truongban_tc"/>
    </record>

    <!-- ===== Ban Tuyên giáo ===== -->
    <record id="user_truongban_tg" model="res.users">
        <field name="name">Mai Quốc Phong</field>
        <field name="login">truongban.tg</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_truongban_tg" model="hr.employee">
        <field name="name">Mai Quốc Phong</field>
        <field name="job_title">Trưởng Ban Tuyên giáo</field>
        <field name="department_id" ref="dept_btg"/>
        <field name="user_id" ref="user_truongban_tg"/>
        <field name="parent_id" ref="employee_bithu"/>
    </record>

    <record id="user_cv_tuyentruyen" model="res.users">
        <field name="name">Chu Thị Quỳnh</field>
        <field name="login">cv.tuyentruyen</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_tuyentruyen" model="hr.employee">
        <field name="name">Chu Thị Quỳnh</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_tuyentruyen"/>
        <field name="user_id" ref="user_cv_tuyentruyen"/>
        <field name="parent_id" ref="employee_truongban_tg"/>
    </record>

    <record id="user_cv_lyluan" model="res.users">
        <field name="name">Tạ Văn Sơn</field>
        <field name="login">cv.lyluan</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_lyluan" model="hr.employee">
        <field name="name">Tạ Văn Sơn</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_lyluan"/>
        <field name="user_id" ref="user_cv_lyluan"/>
        <field name="parent_id" ref="employee_truongban_tg"/>
    </record>

    <!-- ===== Ủy ban Kiểm tra ===== -->
    <record id="user_chunhiem_ubkt" model="res.users">
        <field name="name">Dương Thị Tâm</field>
        <field name="login">chunhiem.ubkt</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chanh_vp'))]"/>
    </record>
    <record id="employee_chunhiem_ubkt" model="hr.employee">
        <field name="name">Dương Thị Tâm</field>
        <field name="job_title">Chủ nhiệm Ủy ban Kiểm tra</field>
        <field name="department_id" ref="dept_ubkt"/>
        <field name="user_id" ref="user_chunhiem_ubkt"/>
        <field name="parent_id" ref="employee_bithu"/>
    </record>

    <record id="user_cv_nv1" model="res.users">
        <field name="name">Hồ Văn Út</field>
        <field name="login">cv.nv1</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_nv1" model="hr.employee">
        <field name="name">Hồ Văn Út</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_nv1"/>
        <field name="user_id" ref="user_cv_nv1"/>
        <field name="parent_id" ref="employee_chunhiem_ubkt"/>
    </record>

    <record id="user_cv_nv2" model="res.users">
        <field name="name">Lưu Thị Vân</field>
        <field name="login">cv.nv2</field>
        <field name="password">demo2026</field>
        <field name="group_ids" eval="[(4, ref('aidt_org.group_chuyen_vien'))]"/>
    </record>
    <record id="employee_cv_nv2" model="hr.employee">
        <field name="name">Lưu Thị Vân</field>
        <field name="job_title">Chuyên viên</field>
        <field name="department_id" ref="dept_nv2"/>
        <field name="user_id" ref="user_cv_nv2"/>
        <field name="parent_id" ref="employee_chunhiem_ubkt"/>
    </record>

</data>
</odoo>
```

- [ ] **Step 5: Cài `aidt_org_demo` (manifest tạm chưa có org_documents.xml)**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -i aidt_org_demo --stop-after-init
```
Expected: exit 0, không `ERROR`.

- [ ] **Step 6: Xác nhận số liệu bằng odoo shell**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d aidt_test --no-http <<'EOF'
root = env.ref('aidt_org_demo.dept_tinh_uy')
depts = env['hr.department'].search([('id', 'child_of', root.id)])
print('DEPTS:', len(depts))
print('EMPLOYEES:', env['hr.employee'].search_count([('department_id', 'child_of', root.id)]))
print('SAMPLE:', env.ref('aidt_org_demo.dept_tonghop').complete_name)
EOF
```
Expected output chứa: `DEPTS: 14`, `EMPLOYEES: 20`, `SAMPLE: Tỉnh ủy Demo / Văn phòng Tỉnh ủy / Phòng Tổng hợp`.

- [ ] **Step 7: Commit**

```bash
git add addons/aidt_org_demo
git commit -m "[ADD] aidt_org_demo: seed 3-level org tree with 20 staff users"
```

---

### Task 5: Văn bản mẫu (15 bản ghi, 2 chia sẻ chéo)

**Files:**
- Create: `addons/aidt_org_demo/data/org_documents.xml`
- Modify: `addons/aidt_org_demo/__manifest__.py` (thêm dòng `'data/org_documents.xml'`)

**Interfaces:**
- Consumes: `aidt_org_demo.dept_*`, `aidt_org_demo.user_cv_tonghop1`, `aidt_org_demo.user_chanhvp` (Task 4); model `aidt.document` (Task 1).

- [ ] **Step 1: Tạo `addons/aidt_org_demo/data/org_documents.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <!-- Tỉnh ủy: 2 -->
    <record id="doc_tu_01" model="aidt.document">
        <field name="name">Nghị quyết về chuyển đổi số trong công tác văn phòng</field>
        <field name="reference">01-NQ/TU</field>
        <field name="doc_type">quyet_dinh</field>
        <field name="department_id" ref="dept_tinh_uy"/>
        <field name="date">2026-01-15</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_tu_02" model="aidt.document">
        <field name="name">Kết luận hội nghị Ban Thường vụ quý I</field>
        <field name="reference">02-KL/TU</field>
        <field name="doc_type">bao_cao</field>
        <field name="department_id" ref="dept_tinh_uy"/>
        <field name="date">2026-03-30</field>
        <field name="state">issued</field>
    </record>

    <!-- Nhánh Văn phòng: 4 -->
    <record id="doc_vp_01" model="aidt.document">
        <field name="name">Công văn đôn đốc báo cáo tháng của các đơn vị</field>
        <field name="reference">15-CV/VPTU</field>
        <field name="doc_type">cong_van</field>
        <field name="department_id" ref="dept_vptu"/>
        <field name="date">2026-04-05</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_th_01" model="aidt.document">
        <field name="name">Báo cáo tổng hợp tình hình kinh tế – xã hội quý I</field>
        <field name="reference">08-BC/VPTU</field>
        <field name="doc_type">bao_cao</field>
        <field name="department_id" ref="dept_tonghop"/>
        <field name="date">2026-04-10</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_th_02" model="aidt.document">
        <field name="name">Dự thảo kế hoạch công tác tháng 5</field>
        <field name="reference">09-KH/VPTU</field>
        <field name="doc_type">ke_hoach</field>
        <field name="department_id" ref="dept_tonghop"/>
        <field name="date">2026-04-25</field>
        <field name="state">draft</field>
    </record>
    <record id="doc_hclt_01" model="aidt.document">
        <field name="name">Công văn hướng dẫn lập hồ sơ lưu trữ điện tử</field>
        <field name="reference">21-CV/VPTU</field>
        <field name="doc_type">cong_van</field>
        <field name="department_id" ref="dept_hclt"/>
        <field name="date">2026-05-02</field>
        <field name="state">issued</field>
    </record>

    <!-- Ban Tổ chức: 3 (1 chia sẻ cho cv.tonghop1) -->
    <record id="doc_btc_01" model="aidt.document">
        <field name="name">Kế hoạch luân chuyển cán bộ năm 2026</field>
        <field name="reference">05-KH/BTCTU</field>
        <field name="doc_type">ke_hoach</field>
        <field name="department_id" ref="dept_btc"/>
        <field name="date">2026-02-20</field>
        <field name="state">issued</field>
        <field name="shared_user_ids" eval="[(4, ref('user_cv_tonghop1'))]"/>
    </record>
    <record id="doc_tccb_01" model="aidt.document">
        <field name="name">Báo cáo rà soát quy hoạch cán bộ giai đoạn 2026–2031</field>
        <field name="reference">11-BC/BTCTU</field>
        <field name="doc_type">bao_cao</field>
        <field name="department_id" ref="dept_tccb"/>
        <field name="date">2026-03-12</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_csd_01" model="aidt.document">
        <field name="name">Công văn hướng dẫn đại hội chi bộ trực thuộc</field>
        <field name="reference">14-CV/BTCTU</field>
        <field name="doc_type">cong_van</field>
        <field name="department_id" ref="dept_csd"/>
        <field name="date">2026-04-01</field>
        <field name="state">issued</field>
    </record>

    <!-- Ban Tuyên giáo: 3 -->
    <record id="doc_btg_01" model="aidt.document">
        <field name="name">Kế hoạch tuyên truyền kỷ niệm các ngày lễ lớn</field>
        <field name="reference">07-KH/BTGTU</field>
        <field name="doc_type">ke_hoach</field>
        <field name="department_id" ref="dept_btg"/>
        <field name="date">2026-01-25</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_tt_01" model="aidt.document">
        <field name="name">Công văn định hướng tuyên truyền tháng 4</field>
        <field name="reference">18-CV/BTGTU</field>
        <field name="doc_type">cong_van</field>
        <field name="department_id" ref="dept_tuyentruyen"/>
        <field name="date">2026-04-02</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_llct_01" model="aidt.document">
        <field name="name">Báo cáo kết quả bồi dưỡng lý luận chính trị quý I</field>
        <field name="reference">12-BC/BTGTU</field>
        <field name="doc_type">bao_cao</field>
        <field name="department_id" ref="dept_lyluan"/>
        <field name="date">2026-04-08</field>
        <field name="state">draft</field>
    </record>

    <!-- Ủy ban Kiểm tra: 3 (1 chia sẻ cho chanhvp) -->
    <record id="doc_ubkt_01" model="aidt.document">
        <field name="name">Báo cáo kết quả kiểm tra dấu hiệu vi phạm quý I</field>
        <field name="reference">04-BC/UBKTTU</field>
        <field name="doc_type">bao_cao</field>
        <field name="department_id" ref="dept_ubkt"/>
        <field name="date">2026-03-28</field>
        <field name="state">issued</field>
        <field name="shared_user_ids" eval="[(4, ref('user_chanhvp'))]"/>
    </record>
    <record id="doc_nv1_01" model="aidt.document">
        <field name="name">Kế hoạch kiểm tra tổ chức đảng cấp dưới năm 2026</field>
        <field name="reference">06-KH/UBKTTU</field>
        <field name="doc_type">ke_hoach</field>
        <field name="department_id" ref="dept_nv1"/>
        <field name="date">2026-02-10</field>
        <field name="state">issued</field>
    </record>
    <record id="doc_nv2_01" model="aidt.document">
        <field name="name">Công văn yêu cầu cung cấp hồ sơ phục vụ giám sát</field>
        <field name="reference">19-CV/UBKTTU</field>
        <field name="doc_type">cong_van</field>
        <field name="department_id" ref="dept_nv2"/>
        <field name="date">2026-04-15</field>
        <field name="state">issued</field>
    </record>

</data>
</odoo>
```

- [ ] **Step 2: Thêm `'data/org_documents.xml'` vào cuối list `data` trong `addons/aidt_org_demo/__manifest__.py`.**

- [ ] **Step 3: Upgrade demo module**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test -u aidt_org_demo --stop-after-init
```
Expected: exit 0, không `ERROR`.

- [ ] **Step 4: Kiểm chứng phạm vi trên dữ liệu demo bằng odoo shell**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d aidt_test --no-http <<'EOF'
Doc = env['aidt.document']
u = lambda xid: env.ref('aidt_org_demo.' + xid)
print('TOTAL:', Doc.sudo().search_count([]))
print('CV_TONGHOP1:', Doc.with_user(u('user_cv_tonghop1')).search_count([]))
print('CHANHVP:', Doc.with_user(u('user_chanhvp')).search_count([]))
print('BITHU:', Doc.with_user(u('user_bithu')).search_count([]))
print('CV_NV2:', Doc.with_user(u('user_cv_nv2')).search_count([]))
EOF
```
Expected:
- `TOTAL: 15`
- `CV_TONGHOP1: 3` (2 VB Phòng Tổng hợp + 1 VB Ban TC được chia sẻ)
- `CHANHVP: 5` (4 VB nhánh Văn phòng + 1 VB UBKT được chia sẻ)
- `BITHU: 15`
- `CV_NV2: 1` (chỉ VB Phòng Nghiệp vụ 2)

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_org_demo
git commit -m "[ADD] aidt_org_demo: seed 15 sample documents with cross-unit sharing"
```

---

### Task 6: Demo end-to-end & nghiệm thu

**Files:** không tạo file mới — dựng môi trường demo và chạy checklist.

**Interfaces:**
- Consumes: toàn bộ Task 1–5.

- [ ] **Step 1: Chạy full test suite lần cuối trên DB sạch**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_test_final -i aidt_org,aidt_org_demo --test-tags /aidt_org --stop-after-init
```
Expected: exit 0, `0 failed, 0 error(s)`.

- [ ] **Step 2: Dựng DB demo và khởi động server**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt_demo -i aidt_org,aidt_org_demo --stop-after-init
docker compose -f docker-compose.dev.yml up -d
```
Expected: http://localhost:8069 hiển thị màn hình đăng nhập, DB `aidt_demo`.

- [ ] **Step 3: Checklist demo tay (kịch bản O-03 trong spec)** — báo người dùng thực hiện, mật khẩu chung `demo2026`:

1. Login `cv.tonghop1` → menu **Văn bản**: thấy đúng 3 VB; tìm "kiểm tra" không ra VB nào của UBKT.
2. Login `chanhvp` → thấy 5 VB (4 nhánh VP + 1 được chia sẻ từ UBKT).
3. Login `bithu` → thấy 15 VB.
4. Login `vanthu` → tạo VB mới, chọn đơn vị "Ban Tổ chức Tỉnh ủy" → lưu bị chặn AccessError; đổi về "Phòng Hành chính – Lưu trữ" → lưu thành công.
5. Login `admin` → **Nhân sự → Phòng ban**: cây 14 đơn vị 3 cấp, cột Loại đơn vị; **Settings → Users**: privilege "Quản lý văn bản" với 6 vai trò.

- [ ] **Step 4: Cập nhật knowledge graph (quy định CLAUDE.md)**

Run: `graphify update .`
Expected: graph cập nhật thêm nodes của 2 module mới, không lỗi.

- [ ] **Step 5: Commit cuối (nếu có thay đổi graph/docs)**

```bash
git add -A graphify-out docs
git commit -m "[IMP] aidt_org: refresh knowledge graph after demo modules"
```
(Bỏ qua nếu `graphify-out/` nằm trong `.gitignore` và không có gì để commit.)
