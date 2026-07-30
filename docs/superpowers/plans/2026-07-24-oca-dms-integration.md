# OCA DMS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `aidt.document` a centralized file store backed by vendored OCA/dms, with file access riding the existing `aidt_org` ir.rules, a 4-level secrecy control (N-04), and in-browser preview of PDF/office files (V-04).

**Architecture:** Vendor three unmodified OCA/dms modules; put every adaptation in a new `aidt_dms` bridge that auto-creates one `dms.directory` per document under an `attachment`+inherit storage, so `dms.security.mixin` delegates file access to `aidt.document._filtered_access`. Secrecy lives in `aidt_org` as a global ir.rule + integer clearance on `res.users`. Office preview comes from `dms_libreoffice_preview` + `libreoffice-writer` in the runtime image, surfaced through the ORM-filtered DMS Files list view.

**Tech Stack:** Odoo 19, Python 3.12, PostgreSQL 16, Docker; OCA/dms (vendored @ pinned SHAs), LibreOffice (headless).

## Global Constraints

- **Never edit vendored directories** (`addons/dms/`, `addons/dms_preview_pane/`, `addons/dms_libreoffice_preview/`). All adaptation lives in `aidt_dms` or `aidt_org`.
- **Pinned vendor SHAs:** `dms` = `171bd86a1b59c846fc41eb47d2bcdbe739363111`; `dms_preview_pane` = `a0da22680638138e0d8364d70e315b480f40be48`; `dms_libreoffice_preview` = `faf9c3eccd6e7afb303cc02ff66a591faceb9bf0`. Source: forks of OCA/dms PRs #475/#483/#484.
- **Storage regime = inheritance only:** exactly one `dms.storage` with `save_type='attachment'` and `inherit_access_from_parent_record=True`. No access-group storages.
- **Secrecy rule must be GLOBAL** (an `ir.rule` with no `groups` field) so it ANDs with the department rules instead of ORing (widening) them.
- **Secrecy levels:** `thuong`=0, `mat`=1, `toi_mat`=2, `tuyet_mat`=3. `res.users.clearance_level` default 0, must NOT be self-writeable.
- **Directory names:** strip `/` (and NUL) from `reference` before naming a directory — `dms`'s `check_name` rejects `/` because it validates by touching a file on disk.
- UI strings in Vietnamese, matching existing `aidt_org` style. License `LGPL-3`.

### Running tests

All tests run in the dev container against a throwaway database. From the repo root:

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i <MODULE> --test-enable --stop-after-init --log-level=test --no-http
```

- First run of a module uses `-i <MODULE>`; to re-run after editing an already-installed module in the same DB use `-u <MODULE>`. When in doubt, use a fresh `-d` name.
- Expected success signature in the log tail: `odoo.tests.result: ... 0 failed, 0 error(s)`.
- `db` service credentials are `odoo`/`odoo` (from `docker-compose.dev.yml`), already wired via env — no `--db_*` flags needed.

After finishing all tasks, run `graphify update .` to refresh the knowledge graph.

---

## File Structure

```
addons/
  dms/                         ← vendored (Task 1)
  dms_preview_pane/            ← vendored (Task 1)
  dms_libreoffice_preview/     ← vendored (Task 1)
  VENDORED.md                  ← provenance (Task 1)

  aidt_org/                    ← existing; extended for N-04
    models/aidt_document.py    ← + secrecy, secrecy_level (Task 2)
    models/res_users.py        ← NEW: clearance_level (Task 2)
    models/__init__.py         ← + res_users import (Task 2)
    security/aidt_org_rules.xml← + global secrecy rule (Task 2)
    data/aidt_clearance.xml    ← NEW: admin clearance=3 (Task 2)
    views/aidt_document_views.xml ← + secrecy field (Task 2)
    views/res_users_views.xml  ← NEW: clearance field on user form (Task 2)
    tests/test_secrecy.py      ← NEW (Task 2)
    __manifest__.py            ← + new data/views/depends (Task 2)

  aidt_dms/                    ← NEW bridge module
    __manifest__.py            ← (Task 3)
    __init__.py                ← (Task 3)
    models/__init__.py         ← (Task 4)
    models/aidt_document.py    ← create/write/unlink + directory_id/file_ids (Task 4,5)
    data/dms_storage.xml       ← storage + root directory (Task 3)
    security/aidt_dms_groups.xml ← imply dms.group_dms_user (Task 3)
    views/aidt_document_views.xml ← file_ids + open button (Task 5,8)
    views/aidt_dms_menus.xml   ← DMS Files menu/action (Task 8)
    tests/__init__.py          ← (Task 4)
    tests/test_directory_sync.py ← (Task 4,5)
    tests/test_dms_security.py ← (Task 6)

  aidt_org_demo/
    data/org_files.xml         ← NEW: seed demo files (Task 9)
    __manifest__.py            ← + org_files.xml (Task 9)

Dockerfile                     ← + libreoffice-writer (Task 7)
```

---

## Task 1: Vendor the three OCA/dms modules

**Files:**
- Create: `addons/dms/` (whole tree @ `171bd86`)
- Create: `addons/dms_preview_pane/` (whole tree @ `a0da226`)
- Create: `addons/dms_libreoffice_preview/` (whole tree @ `faf9c3e`)
- Create: `addons/VENDORED.md`

**Interfaces:**
- Produces: models `dms.storage`, `dms.directory`, `dms.file`, `dms.access.group`; groups `dms.group_dms_user`, `dms.group_dms_manager`; JS registry category `dms.preview_handlers` (from `dms_preview_pane`).

- [ ] **Step 1: Fetch each pinned module into addons/**

```bash
cd "$(git rev-parse --show-toplevel)"
tmp="$(mktemp -d)"
git clone --no-checkout https://github.com/ledoent/dms "$tmp/dms"
git -C "$tmp/dms" archive 171bd86a1b59c846fc41eb47d2bcdbe739363111 dms | tar -x -C addons/
git -C "$tmp/dms" archive a0da22680638138e0d8364d70e315b480f40be48 dms_preview_pane | tar -x -C addons/
git -C "$tmp/dms" archive faf9c3eccd6e7afb303cc02ff66a591faceb9bf0 dms_libreoffice_preview | tar -x -C addons/
rm -rf "$tmp"
ls addons/dms/__manifest__.py addons/dms_preview_pane/__manifest__.py addons/dms_libreoffice_preview/__manifest__.py
```

Expected: all three `__manifest__.py` paths listed (no error).

- [ ] **Step 2: Write provenance file**

Create `addons/VENDORED.md`:

```markdown
# Vendored third-party addons

These directories are copied verbatim from upstream at a pinned commit.
**Do not edit them** — all local adaptation lives in `aidt_dms` / `aidt_org`.
To refresh, re-run the fetch commands below with the new SHA and update this table.

| Module | Upstream | PR | Pinned SHA | Vendored on |
|---|---|---|---|---|
| `dms` | github.com/OCA/dms | [#475](https://github.com/OCA/dms/pull/475) | `171bd86a1b59c846fc41eb47d2bcdbe739363111` | 2026-07-24 |
| `dms_preview_pane` | github.com/OCA/dms | [#483](https://github.com/OCA/dms/pull/483) | `a0da22680638138e0d8364d70e315b480f40be48` | 2026-07-24 |
| `dms_libreoffice_preview` | github.com/OCA/dms | [#484](https://github.com/OCA/dms/pull/484) | `faf9c3eccd6e7afb303cc02ff66a591faceb9bf0` | 2026-07-24 |

## Refresh

    git clone --no-checkout https://github.com/ledoent/dms /tmp/dms
    git -C /tmp/dms archive <SHA> <module> | tar -x -C addons/

Once OCA/dms merges the 19.0 branch, switch the remote to `OCA/dms` and pin the
merge commit instead of the fork.
```

- [ ] **Step 3: Verify the core module installs**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i dms,dms_libreoffice_preview,dms_preview_pane --stop-after-init --log-level=info --no-http
```
Expected: log ends with `Modules loaded.` and no `CRITICAL`/`ERROR`. (This installs but runs no tests yet.)

- [ ] **Step 4: Commit**

```bash
git add addons/dms addons/dms_preview_pane addons/dms_libreoffice_preview addons/VENDORED.md
git commit -m "[ADD] vendor OCA/dms (dms, preview_pane, libreoffice_preview) @ pinned SHAs"
```

---

## Task 2: N-04 secrecy field, clearance, and global rule (aidt_org)

**Files:**
- Modify: `addons/aidt_org/models/aidt_document.py`
- Create: `addons/aidt_org/models/res_users.py`
- Modify: `addons/aidt_org/models/__init__.py`
- Modify: `addons/aidt_org/security/aidt_org_rules.xml`
- Create: `addons/aidt_org/data/aidt_clearance.xml`
- Modify: `addons/aidt_org/views/aidt_document_views.xml`
- Create: `addons/aidt_org/views/res_users_views.xml`
- Modify: `addons/aidt_org/__manifest__.py`
- Test: `addons/aidt_org/tests/test_secrecy.py`, `addons/aidt_org/tests/__init__.py`

**Interfaces:**
- Produces: `aidt.document.secrecy` (Selection), `aidt.document.secrecy_level` (Integer, stored+indexed, 0–3), `res.users.clearance_level` (Integer 0–3), global rule `aidt_org.rule_aidt_document_secrecy`.

- [ ] **Step 1: Write the failing test**

Create `addons/aidt_org/tests/test_secrecy.py`:

```python
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSecrecy(TransactionCase):
    """N-04: độ mật chặn ở tầng dữ liệu, AND với phạm vi đơn vị."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'Đơn vị A', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'Đơn vị B', 'unit_type': 'ban'})
        cls.group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        # CV đơn vị A, clearance 1 (đọc tới 'mat')
        cls.user_a = cls._make_user('sec_a', cls.dept_a, clearance=1)
        # CV đơn vị A, clearance 3 (đọc mọi mức) — dùng cho bẫy OR-nới-rộng
        cls.user_a3 = cls._make_user('sec_a3', cls.dept_a, clearance=3)

        Doc = cls.env['aidt.document']
        cls.doc_mat = Doc.create({
            'name': 'VB Mật A', 'department_id': cls.dept_a.id, 'secrecy': 'mat'})
        cls.doc_tuyetmat = Doc.create({
            'name': 'VB Tuyệt mật A', 'department_id': cls.dept_a.id,
            'secrecy': 'tuyet_mat'})
        cls.doc_b_thuong = Doc.create({
            'name': 'VB Thường B', 'department_id': cls.dept_b.id, 'secrecy': 'thuong'})

    @classmethod
    def _make_user(cls, login, dept, clearance):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, cls.group_cv.id)],
            'clearance_level': clearance,
        })
        cls.env['hr.employee'].create(
            {'name': login, 'user_id': user.id, 'department_id': dept.id})
        return user

    def test_level_mapping(self):
        self.assertEqual(self.doc_mat.secrecy_level, 1)
        self.assertEqual(self.doc_tuyetmat.secrecy_level, 3)

    def test_clearance_blocks_above_level(self):
        """clearance 1 đọc được Mật, KHÔNG đọc được Tuyệt mật."""
        Doc = self.env['aidt.document'].with_user(self.user_a)
        self.assertTrue(Doc.browse(self.doc_mat.id).name)
        with self.assertRaises(AccessError):
            self.assertTrue(Doc.browse(self.doc_tuyetmat.id).name)

    def test_search_hides_above_level(self):
        """VB vượt mức mật vắng mặt khỏi search (không lộ tiêu đề)."""
        ids = self.env['aidt.document'].with_user(self.user_a).search([]).ids
        self.assertIn(self.doc_mat.id, ids)
        self.assertNotIn(self.doc_tuyetmat.id, ids)

    def test_clearance_does_not_widen_department(self):
        """clearance 3 KHÔNG cho thấy VB đơn vị khác — regression OR-nới-rộng."""
        ids = self.env['aidt.document'].with_user(self.user_a3).search([]).ids
        self.assertNotIn(self.doc_b_thuong.id, ids)

    def test_clearance_not_self_writeable(self):
        """User không tự nâng clearance của mình."""
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(self.user_a).browse(
                self.user_a.id).write({'clearance_level': 3})
```

Create `addons/aidt_org/tests/__init__.py` if the new file isn't picked up (it already imports `test_document_scope`; add the new module):

```python
from . import test_document_scope
from . import test_secrecy
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i aidt_org --test-enable --stop-after-init --log-level=test --no-http
```
Expected: FAIL — `Invalid field 'clearance_level' on model 'res.users'` / `secrecy_level`.

- [ ] **Step 3: Add secrecy fields to aidt.document**

In `addons/aidt_org/models/aidt_document.py`, change the import line and add fields after `state`:

```python
from odoo import api, fields, models

_SECRECY_LEVEL = {'thuong': 0, 'mat': 1, 'toi_mat': 2, 'tuyet_mat': 3}


class AidtDocument(models.Model):
    # ... existing _name/_inherit/_order and existing fields unchanged ...

    secrecy = fields.Selection(
        [('thuong', 'Thường'), ('mat', 'Mật'),
         ('toi_mat', 'Tối mật'), ('tuyet_mat', 'Tuyệt mật')],
        string='Độ mật', required=True, default='thuong', tracking=True)
    secrecy_level = fields.Integer(
        string='Mức mật', compute='_compute_secrecy_level',
        store=True, index=True)

    @api.depends('secrecy')
    def _compute_secrecy_level(self):
        for doc in self:
            doc.secrecy_level = _SECRECY_LEVEL.get(doc.secrecy, 0)
```

(Keep every existing field; only add the two new fields, the constant, the `api` import, and the compute method.)

- [ ] **Step 4: Add clearance_level to res.users**

Create `addons/aidt_org/models/res_users.py`:

```python
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    clearance_level = fields.Integer(
        string='Mức mật được duyệt', default=0,
        help='0=Thường, 1=Mật, 2=Tối mật, 3=Tuyệt mật. '
             'Chỉ quản trị viên đặt được; người dùng không tự sửa.')
```

Add to `addons/aidt_org/models/__init__.py`:

```python
from . import res_users
```

(Append after the existing imports.)

- [ ] **Step 5: Add the GLOBAL secrecy rule**

In `addons/aidt_org/security/aidt_org_rules.xml`, add inside `<data noupdate="1">` (no `groups` field — this is deliberate; it makes the rule global and AND-composed):

```xml
    <record id="rule_aidt_document_secrecy" model="ir.rule">
        <field name="name">Văn bản: chặn theo độ mật (toàn cục)</field>
        <field name="model_id" ref="model_aidt_document"/>
        <field name="domain_force">[('secrecy_level', '&lt;=', user.clearance_level)]</field>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="True"/>
    </record>
```

- [ ] **Step 6: Give admin full clearance**

Create `addons/aidt_org/data/aidt_clearance.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">
    <record id="base.user_admin" model="res.users">
        <field name="clearance_level">3</field>
    </record>
</data>
</odoo>
```

- [ ] **Step 7: Add fields to the views**

In `addons/aidt_org/views/aidt_document_views.xml`, add `<field name="secrecy"/>` next to the existing `doc_type`/`state` fields in the form (place it in the same group as the other metadata fields).

Create `addons/aidt_org/views/res_users_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_users_form_clearance" model="ir.ui.view">
        <field name="name">res.users.form.clearance</field>
        <field name="model">res.users</field>
        <field name="inherit_id" ref="base.view_users_form"/>
        <field name="arch" type="xml">
            <field name="active" position="after">
                <field name="clearance_level"/>
            </field>
        </field>
    </record>
</odoo>
```

- [ ] **Step 8: Register data/views in the manifest**

In `addons/aidt_org/__manifest__.py`, add to the `data` list (after the existing security/views entries):

```python
        'data/aidt_clearance.xml',
        'views/res_users_views.xml',
```

- [ ] **Step 9: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i aidt_org --test-enable --stop-after-init --log-level=test --no-http
```
Expected: PASS — `0 failed, 0 error(s)`; `test_document_scope` still green.

- [ ] **Step 10: Commit**

```bash
git add addons/aidt_org
git commit -m "[IMP] aidt_org: N-04 độ mật + clearance + global secrecy rule"
```

---

## Task 3: Scaffold aidt_dms — storage, root directory, DMS group

**Files:**
- Create: `addons/aidt_dms/__manifest__.py`, `addons/aidt_dms/__init__.py`
- Create: `addons/aidt_dms/data/dms_storage.xml`
- Create: `addons/aidt_dms/security/aidt_dms_groups.xml`

**Interfaces:**
- Produces: `aidt_dms.storage_aidt` (dms.storage, attachment+inherit), `aidt_dms.directory_root_aidt` (root dms.directory, res_model=aidt.document), and `group_chuyen_vien` implying `dms.group_dms_user`.

- [ ] **Step 1: Write the manifest and package init**

Create `addons/aidt_dms/__manifest__.py`:

```python
{
    'name': 'AIDT Văn bản — Kho tài liệu (DMS)',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Cầu nối aidt.document ↔ OCA DMS: kho tệp tập trung, quyền kế thừa (N-10/N-05/V-04)',
    'depends': ['aidt_org', 'dms', 'dms_libreoffice_preview'],
    'data': [
        'security/aidt_dms_groups.xml',
        'data/dms_storage.xml',
        'views/aidt_document_views.xml',
        'views/aidt_dms_menus.xml',
    ],
    'license': 'LGPL-3',
}
```

(The two `views/*.xml` files are created in Tasks 5 and 8; create empty valid stubs now so the module installs — see Step 4.)

Create `addons/aidt_dms/__init__.py`:

```python
from . import models
```

- [ ] **Step 2: Storage + root directory data**

Create `addons/aidt_dms/data/dms_storage.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <record id="storage_aidt" model="dms.storage">
        <field name="name">Kho văn bản AIDT</field>
        <field name="save_type">attachment</field>
        <field name="inherit_access_from_parent_record" eval="True"/>
        <field name="model_ids" eval="[(4, ref('aidt_org.model_aidt_document'))]"/>
    </record>

    <record id="directory_root_aidt" model="dms.directory">
        <field name="name">Văn bản</field>
        <field name="is_root_directory" eval="True"/>
        <field name="storage_id" ref="storage_aidt"/>
        <field name="res_model">aidt.document</field>
    </record>

</data>
</odoo>
```

- [ ] **Step 3: Imply the DMS user group into the base role**

Create `addons/aidt_dms/security/aidt_dms_groups.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- Chuyên viên (vai trò gốc) cần quyền ACL đọc/ghi tệp DMS.
         Directory do aidt_dms tạo bằng sudo; người dùng chỉ thao tác tệp. -->
    <record id="aidt_org.group_chuyen_vien" model="res.groups">
        <field name="implied_ids" eval="[(4, ref('dms.group_dms_user'))]"/>
    </record>

</odoo>
```

- [ ] **Step 4: Create valid empty view stubs so the module installs**

Create `addons/aidt_dms/views/aidt_document_views.xml` and `addons/aidt_dms/views/aidt_dms_menus.xml`, each with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
</odoo>
```

Also create `addons/aidt_dms/models/__init__.py` with a single blank line (populated in Task 4) so `from . import models` succeeds:

```python
```

- [ ] **Step 5: Verify install and config**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i aidt_dms --stop-after-init --log-level=info --no-http
```
Expected: `Modules loaded.` with no ERROR. (Behavioural assertions come with Task 4's tests.)

- [ ] **Step 6: Commit**

```bash
git add addons/aidt_dms
git commit -m "[ADD] aidt_dms: DMS storage (attachment+inherit) + root directory + dms_user group"
```

---

## Task 4: Auto-create a directory per document, with safe naming

**Files:**
- Create: `addons/aidt_dms/models/aidt_document.py`
- Modify: `addons/aidt_dms/models/__init__.py`
- Create: `addons/aidt_dms/tests/__init__.py`, `addons/aidt_dms/tests/test_directory_sync.py`

**Interfaces:**
- Consumes: `aidt_dms.storage_aidt`, `aidt_dms.directory_root_aidt` (Task 3).
- Produces: `aidt.document.directory_id` (Many2one dms.directory, readonly), `aidt.document._dir_name()` → str with no `/`.

- [ ] **Step 1: Write the failing test**

Create `addons/aidt_dms/tests/test_directory_sync.py`:

```python
from odoo.tests.common import TransactionCase


class TestDirectorySync(TransactionCase):
    """Mỗi văn bản tự sinh 1 dms.directory link theo record."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env['hr.department'].create(
            {'name': 'ĐV Test DMS', 'unit_type': 'ban'})

    def _new_doc(self, **vals):
        base = {'name': 'VB test', 'department_id': self.dept.id}
        base.update(vals)
        return self.env['aidt.document'].create(base)

    def test_directory_created_and_linked(self):
        doc = self._new_doc()
        self.assertTrue(doc.directory_id)
        self.assertEqual(doc.directory_id.res_model, 'aidt.document')
        self.assertEqual(doc.directory_id.res_id, doc.id)
        root = self.env.ref('aidt_dms.directory_root_aidt')
        self.assertEqual(doc.directory_id.parent_id, root)

    def test_slash_in_reference_is_sanitized(self):
        """Số ký hiệu có '/' không được lọt vào tên directory (check_name)."""
        doc = self._new_doc(reference='01-NQ/TU')
        self.assertNotIn('/', doc.directory_id.name)
        self.assertIn('01-NQ-TU', doc.directory_id.name)
```

Create `addons/aidt_dms/tests/__init__.py`:

```python
from . import test_directory_sync
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: FAIL — `Invalid field 'directory_id'` / directory not created.

- [ ] **Step 3: Implement the create override + naming**

Create `addons/aidt_dms/models/aidt_document.py`:

```python
from odoo import api, fields, models


class AidtDocument(models.Model):
    _inherit = 'aidt.document'

    directory_id = fields.Many2one(
        'dms.directory', string='Thư mục lưu trữ',
        readonly=True, copy=False, ondelete='set null')

    def _dir_name(self):
        """Tên thư mục hợp lệ: bỏ '/' và NUL (check_name của DMS từ chối '/'),
        ưu tiên số ký hiệu, thêm id để duy nhất."""
        self.ensure_one()
        base = (self.reference or self.name or 'VB')
        base = base.replace('/', '-').replace('\x00', '').strip() or 'VB'
        return f"{base} [{self.id}]"

    @api.model_create_multi
    def create(self, vals_list):
        docs = super().create(vals_list)
        root = self.env.ref('aidt_dms.directory_root_aidt')
        Directory = self.env['dms.directory'].sudo()
        for doc in docs:
            directory = Directory.create({
                'name': doc._dir_name(),
                'parent_id': root.id,
                'res_model': 'aidt.document',
                'res_id': doc.id,
            })
            doc.directory_id = directory.id
        return docs
```

Set `addons/aidt_dms/models/__init__.py` to:

```python
from . import aidt_document
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: PASS — `0 failed, 0 error(s)`.

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_dms/models addons/aidt_dms/tests
git commit -m "[IMP] aidt_dms: auto-create linked dms.directory per document, sanitize name"
```

---

## Task 5: Expose files, sync renames, block unsafe delete

**Files:**
- Modify: `addons/aidt_dms/models/aidt_document.py`
- Modify: `addons/aidt_dms/views/aidt_document_views.xml`
- Modify: `addons/aidt_dms/tests/test_directory_sync.py`

**Interfaces:**
- Consumes: `directory_id`, `_dir_name()` (Task 4).
- Produces: `aidt.document.file_ids` (One2many related to `directory_id.file_ids`).

- [ ] **Step 1: Add failing tests for files, rename, delete**

Append to `addons/aidt_dms/tests/test_directory_sync.py` inside the class:

```python
    def _add_file(self, doc, name='tep.txt'):
        import base64
        return self.env['dms.file'].create({
            'name': name,
            'directory_id': doc.directory_id.id,
            'content': base64.b64encode(b'noi dung'),
        })

    def test_file_ids_related(self):
        doc = self._new_doc()
        f = self._add_file(doc)
        self.assertIn(f, doc.file_ids)

    def test_rename_syncs_directory(self):
        doc = self._new_doc(reference='10-BC/VP')
        doc.write({'reference': '11-BC/VP'})
        self.assertIn('11-BC-VP', doc.directory_id.name)

    def test_delete_blocked_when_files_exist(self):
        from odoo.exceptions import UserError
        doc = self._new_doc()
        self._add_file(doc)
        with self.assertRaises(UserError):
            doc.unlink()

    def test_delete_removes_empty_directory(self):
        doc = self._new_doc()
        directory = doc.directory_id
        doc.unlink()
        self.assertFalse(directory.exists())
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: FAIL — `Invalid field 'file_ids'` / no UserError on delete.

- [ ] **Step 3: Add file_ids, write-sync, unlink guard**

In `addons/aidt_dms/models/aidt_document.py`, change the import and add the field + two methods:

```python
from odoo import _, api, fields, models
from odoo.exceptions import UserError
```

Add the field after `directory_id`:

```python
    file_ids = fields.One2many(
        related='directory_id.file_ids', string='Tệp đính kèm', readonly=True)
```

Add these methods to the class:

```python
    def write(self, vals):
        res = super().write(vals)
        if {'reference', 'name'} & set(vals):
            for doc in self.filtered('directory_id'):
                doc.directory_id.sudo().name = doc._dir_name()
        return res

    def unlink(self):
        for doc in self.filtered('directory_id'):
            if doc.directory_id.sudo().file_ids:
                raise UserError(_(
                    "Không thể xóa văn bản '%s' vì còn tệp đính kèm. "
                    "Hãy chuyển sang trạng thái Lưu trữ.", doc.name))
        directories = self.directory_id
        res = super().unlink()
        directories.sudo().unlink()
        return res
```

- [ ] **Step 4: Show files on the document form**

Replace `addons/aidt_dms/views/aidt_document_views.xml` with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_aidt_document_form_dms" model="ir.ui.view">
        <field name="name">aidt.document.form.dms</field>
        <field name="model">aidt.document</field>
        <field name="inherit_id" ref="aidt_org.aidt_document_view_form"/>
        <field name="arch" type="xml">
            <sheet position="inside">
                <notebook>
                    <page string="Tệp đính kèm" name="files">
                        <field name="file_ids" readonly="1">
                            <list>
                                <field name="name"/>
                                <field name="mimetype"/>
                                <field name="human_size"/>
                            </list>
                        </field>
                    </page>
                </notebook>
            </sheet>
        </field>
    </record>
</odoo>
```

Note: the parent form's external id is `aidt_org.aidt_document_view_form` (verified). The form has a `<sheet>` but no existing `<notebook>` or button box, so both are added fresh here.

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: PASS — `0 failed, 0 error(s)`.

- [ ] **Step 6: Commit**

```bash
git add addons/aidt_dms
git commit -m "[IMP] aidt_dms: file_ids on form, rename sync, block delete with files"
```

---

## Task 6: Security integration tests (inheritance filters files)

**Files:**
- Create: `addons/aidt_dms/tests/test_dms_security.py`
- Modify: `addons/aidt_dms/tests/__init__.py`

**Interfaces:**
- Consumes: `aidt.document.secrecy` (Task 2), `directory_id`/`file_ids` (Tasks 4–5), storage inherit mode (Task 3).

- [ ] **Step 1: Write the security tests**

Create `addons/aidt_dms/tests/test_dms_security.py`:

```python
import base64

from odoo.tests.common import TransactionCase


class TestDmsSecurity(TransactionCase):
    """V-13/N-04: quyền tệp kế thừa từ văn bản, lọc ở tầng ORM."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'ĐV A sec', 'unit_type': 'ban'})
        cls.dept_b = Dept.create({'name': 'ĐV B sec', 'unit_type': 'ban'})
        cls.group_cv = cls.env.ref('aidt_org.group_chuyen_vien')

        # CV đơn vị A, clearance 0 (chỉ Thường)
        cls.user_a0 = cls._make_user('dsec_a0', cls.dept_a, 0)
        # CV đơn vị A, clearance 3 (mọi mức)
        cls.user_a3 = cls._make_user('dsec_a3', cls.dept_a, 3)
        # CV đơn vị B, clearance 3
        cls.user_b3 = cls._make_user('dsec_b3', cls.dept_b, 3)

        Doc = cls.env['aidt.document']
        cls.doc_secret = Doc.create({
            'name': 'VB Tuyệt mật A', 'department_id': cls.dept_a.id,
            'secrecy': 'tuyet_mat'})
        cls.file_secret = cls.env['dms.file'].create({
            'name': 'tuyet-mat.txt',
            'directory_id': cls.doc_secret.directory_id.id,
            'content': base64.b64encode(b'bi mat'),
        })

    @classmethod
    def _make_user(cls, login, dept, clearance):
        user = cls.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(4, cls.group_cv.id)],
            'clearance_level': clearance,
        })
        cls.env['hr.employee'].create(
            {'name': login, 'user_id': user.id, 'department_id': dept.id})
        return user

    def _visible_file_ids(self, user):
        return self.env['dms.file'].with_user(user).search([]).ids

    def test_low_clearance_cannot_see_file(self):
        """Đúng đơn vị nhưng thiếu clearance → tệp vắng mặt khỏi search."""
        self.assertNotIn(self.file_secret.id, self._visible_file_ids(self.user_a0))

    def test_cleared_same_unit_sees_file(self):
        self.assertIn(self.file_secret.id, self._visible_file_ids(self.user_a3))

    def test_other_unit_cannot_see_file(self):
        """Clearance đủ nhưng khác đơn vị → vẫn vô hình (AND phạm vi)."""
        self.assertNotIn(self.file_secret.id, self._visible_file_ids(self.user_b3))

    def test_share_does_not_bypass_clearance(self):
        """Chia sẻ VB Tối mật cho user clearance 0 → tệp vẫn vô hình."""
        doc = self.env['aidt.document'].create({
            'name': 'VB Tối mật chia sẻ', 'department_id': self.dept_b.id,
            'secrecy': 'toi_mat', 'shared_user_ids': [(4, self.user_a0.id)]})
        f = self.env['dms.file'].create({
            'name': 'toi-mat.txt', 'directory_id': doc.directory_id.id,
            'content': base64.b64encode(b'x')})
        self.assertNotIn(f.id, self._visible_file_ids(self.user_a0))
```

Update `addons/aidt_dms/tests/__init__.py`:

```python
from . import test_directory_sync
from . import test_dms_security
```

- [ ] **Step 2: Run and verify pass**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: PASS — `0 failed, 0 error(s)`. If `test_low_clearance_cannot_see_file` fails, the storage is not in inherit mode (recheck Task 3 `dms_storage.xml`).

- [ ] **Step 3: Commit**

```bash
git add addons/aidt_dms/tests
git commit -m "[ADD] aidt_dms: security tests — file access inherits document scope + secrecy"
```

---

## Task 7: Add LibreOffice to the runtime image (V-04 office preview)

**Files:**
- Modify: `Dockerfile:48-65`

**Interfaces:**
- Produces: `soffice` on `$PATH` in the runtime + dev images.

- [ ] **Step 1: Add libreoffice-writer to the runtime apt block**

In `Dockerfile`, inside the runtime `apt-get install` list (the block starting at line 48), add `libreoffice-writer` in alphabetical position (after `gettext-base`):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-noto-cjk \
        gettext-base \
        libreoffice-writer \
        libjpeg62-turbo \
        libldap-2.5-0 \
        libpq5 \
        libsasl2-2 \
        libxml2 \
        libxslt1.1 \
        nodejs \
        npm \
        postgresql-client \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*
```

Vietnamese diacritics in converted PDFs are covered by the existing `fonts-dejavu-core` + `fonts-liberation`; no extra font package is needed. The `dev` stage inherits this via `FROM runtime`.

- [ ] **Step 2: Rebuild and verify soffice is present**

Run:
```bash
docker compose -f docker-compose.dev.yml build odoo
docker compose -f docker-compose.dev.yml run --rm odoo bash -lc "soffice --version"
```
Expected: prints `LibreOffice <version>` (e.g. `LibreOffice 7.x`).

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "[IMP] docker: add libreoffice-writer for DMS office preview (V-04)"
```

---

## Task 8: DMS Files menu + open-in-view button

**Files:**
- Modify: `addons/aidt_dms/views/aidt_dms_menus.xml`
- Modify: `addons/aidt_dms/views/aidt_document_views.xml`

**Interfaces:**
- Consumes: `dms.file`, `directory_id` (Tasks 3–5).
- Produces: menu `aidt_dms.menu_aidt_files`, action `aidt_dms.action_aidt_files`.

This task is UI wiring; it is verified manually (renders + preview) rather than by unit test, since the preview is client-side OWL.

- [ ] **Step 1: Define the Files action and menu**

Replace `addons/aidt_dms/views/aidt_dms_menus.xml` with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_aidt_files" model="ir.actions.act_window">
        <field name="name">Tệp văn bản</field>
        <field name="res_model">dms.file</field>
        <field name="view_mode">list,kanban,form</field>
        <field name="domain">[('res_model', '=', 'aidt.document')]</field>
        <field name="context">{'searchpanel_default_directory_id': False}</field>
    </record>

    <menuitem id="menu_aidt_files_root" name="Kho văn bản" sequence="45"/>
    <menuitem id="menu_aidt_files" name="Tệp văn bản"
              parent="menu_aidt_files_root" action="action_aidt_files"
              sequence="10"/>
</odoo>
```

The `dms.file` list ships with the preview pane from `dms_preview_pane`; the ORM `_search` filter guarantees users see only permitted files. The `domain` scopes the menu to AIDT document files.

- [ ] **Step 2: Add an "open files" button to the document form**

In `addons/aidt_dms/views/aidt_document_views.xml`, add a button box before the `<notebook>` added in Task 5 (inside the same inherit `<sheet position="inside">`), opening the file view filtered to this document's directory:

```xml
                <div class="oe_button_box" name="button_box">
                    <button type="object" name="action_open_files"
                            class="oe_stat_button" icon="fa-folder-open">
                        <field name="file_count" widget="statinfo" string="Tệp"/>
                    </button>
                </div>
```

Then add the supporting field + method to `addons/aidt_dms/models/aidt_document.py`:

```python
    file_count = fields.Integer(
        string='Số tệp', compute='_compute_file_count')

    @api.depends('file_ids')
    def _compute_file_count(self):
        for doc in self:
            doc.file_count = len(doc.file_ids)

    def action_open_files(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dms.file',
            'name': 'Tệp: %s' % self.name,
            'view_mode': 'list,kanban,form',
            'domain': [('directory_id', '=', self.directory_id.id)],
            'context': {'default_directory_id': self.directory_id.id},
        }
```

- [ ] **Step 3: Verify install and render manually**

Run:
```bash
docker compose -f docker-compose.dev.yml up -d --build
```
Then in the browser (http://localhost:8069, install `aidt_dms` + `aidt_org_demo`):
1. Open **Kho văn bản → Tệp văn bản** — confirm the list renders and only permitted files show.
2. Open a document, click the **Tệp** stat button — confirm it opens the file list filtered to that document.
3. Upload a `.docx`, open it — confirm the LibreOffice preview renders a PDF with correct Vietnamese diacritics.

Expected: all three succeed; no JS console errors.

- [ ] **Step 4: Re-run the module tests (regression)**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -u aidt_dms --test-enable --stop-after-init --log-level=test --no-http
```
Expected: PASS — `0 failed, 0 error(s)`.

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_dms
git commit -m "[ADD] aidt_dms: DMS Files menu + open-files button on document form (V-04)"
```

---

## Task 9: Seed demo files

**Files:**
- Create: `addons/aidt_org_demo/data/org_files.xml`
- Modify: `addons/aidt_org_demo/__manifest__.py`

**Interfaces:**
- Consumes: existing demo documents in `aidt_org_demo/data/org_documents.xml`; `dms.file`, `directory_id` (Tasks 3–5).

- [ ] **Step 1: Identify two existing demo document xmlids**

Run:
```bash
grep -o 'record id="[^"]*" model="aidt.document"' addons/aidt_org_demo/data/org_documents.xml | head -2
```
Expected: two `record id="..."` lines. Use those two ids below (shown here as `doc_1` / `doc_2` — replace with the real ids).

- [ ] **Step 2: Add the seed file data**

Create `addons/aidt_org_demo/data/org_files.xml` (replace `aidt_org_demo.doc_1` / `doc_2` with the real ids from Step 1):

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
<data noupdate="1">

    <record id="file_demo_1" model="dms.file">
        <field name="name">cong-van-mau.txt</field>
        <field name="directory_id" ref="aidt_org_demo.doc_1"
               eval="obj().env.ref('aidt_org_demo.doc_1').directory_id.id"/>
        <field name="content" type="base64">Tê¬p ma^~u công v&#259;n.</field>
    </record>

    <record id="file_demo_2" model="dms.file">
        <field name="directory_id"
               eval="obj().env.ref('aidt_org_demo.doc_2').directory_id.id"/>
        <field name="name">bao-cao-mau.txt</field>
        <field name="content" type="base64">Tê¬p ma^~u báo cáo.</field>
    </record>

</data>
</odoo>
```

Note: `dms.file.directory_id` must be the document's auto-created directory. The `eval` reads it from the referenced document. If the `ref=` attribute form errors, keep only the `eval=` form (delete the `ref=` attribute on `file_demo_1`).

- [ ] **Step 3: Register in the demo manifest**

In `addons/aidt_org_demo/__manifest__.py`, add `'aidt_dms'` to `depends` and append to `data`:

```python
        'data/org_files.xml',
```

- [ ] **Step 4: Verify the demo loads**

Run:
```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d test_run -i aidt_org_demo,aidt_dms --stop-after-init --log-level=info --no-http
```
Expected: `Modules loaded.`; no ERROR; the two demo files exist under their documents' directories.

- [ ] **Step 5: Commit**

```bash
git add addons/aidt_org_demo
git commit -m "[ADD] aidt_org_demo: seed demo files into document directories"
```

- [ ] **Step 6: Refresh the knowledge graph**

Run:
```bash
graphify update .
git add graphify-out
git commit -m "chore(graphify): refresh graph after DMS integration"
```

---

## Self-Review Notes

- **Spec coverage:** N-10 store (Tasks 1,3,4) · N-05/V-13 inheritance (Tasks 3,6) · N-04 secrecy (Task 2, verified Task 6) · V-04 PDF (Task 1 core) + office (Tasks 7,8) · vendoring rule (Task 1 + Global Constraints). Deferred per spec §6: N-10 versioning, S-09 archive tree — no tasks, intentionally.
- **The OR-widening trap** (spec §4.2) is guarded by `test_clearance_does_not_widen_department` (Task 2) and `test_other_unit_cannot_see_file` (Task 6).
- **The check_name `/` gotcha** (spec §3.2) is guarded by `test_slash_in_reference_is_sanitized` (Task 4).
- **Type consistency:** `directory_id`, `file_ids`, `file_count`, `_dir_name()`, `secrecy_level`, `clearance_level` are defined once and referenced consistently across tasks.
```

# OCA DMS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa OCA DMS (`OCA/dms`) vào bản fork Odoo 19 này làm hệ quản lý tài liệu thay cho Odoo Enterprise `documents`, theo cấu trúc `extra-addons/` (code vendor) + `custom-addons/` (code của dự án).

**Architecture:** Ba lớp addon xếp chồng, không lớp nào sửa lớp dưới. `addons/` + `odoo/` là core Odoo, tuyệt đối không đụng. `extra-addons/<vendor-repo>/` chứa code bên thứ ba kéo về bằng `git subtree`, chỉ sửa khi không sửa thì không chạy được. `custom-addons/aidt_*/` chứa toàn bộ code của dự án, kế thừa (`_inherit`) và mở rộng module vendor thay vì sửa chúng. Mỗi lớp được thêm vào `addons_path` bằng một mục riêng.

**Tech Stack:** Odoo 19.0 (fork in-tree), Python 3.12, PostgreSQL 16, Docker Compose (`docker-compose.dev.yml`), OCA/dms branch 18.0.

## Global Constraints

- Odoo series của repo: **19.0** (`odoo/release.py` → `version_info = (19, 0, 0, FINAL, 0, '')`).
- Upstream pin: `https://github.com/OCA/dms`, branch `18.0`, commit **`6da958550a511dfa382c1f4208d6024adb4a5d95`** (2026-07-22).
- **Mọi manifest phải có `"version"` bắt đầu bằng `19.0.`**. `odoo/modules/module.py:465-467` gọi `check_version()`; nếu sai series, Odoo ghi log `WARNING ... has an incompatible version, setting installable=False` và module **biến mất khỏi danh sách cài được** — không phải lỗi crash, nên phải chủ động kiểm tra bằng log hoặc bảng `ir_module_module`.
- **Không sửa file nào trong `addons/` hoặc `odoo/`.** Mọi thay đổi hành vi làm bằng `_inherit`.
- Sửa file trong `extra-addons/` **chỉ khi module không chạy được nếu không sửa**. Mỗi lần sửa là một commit riêng, tiêu đề bắt đầu bằng `[MIG]`, và phải được ghi vào `extra-addons/README.md`.
- Module của dự án dùng tiền tố `aidt_`, license `LGPL-3`.
- Module bị loại khỏi phạm vi vendor: `dms_user_role` (cần `base_user_role` từ OCA/server-backend, không có trong repo) và `web_editor_media_dialog_dms` (cần `web_editor`, module này **không tồn tại trong Odoo 19**, đã bị thay bằng `html_editor`).
- `docker/odoo.conf` được `COPY` vào image lúc build (`Dockerfile:88`), **không** bind-mount. Mọi thay đổi file này bắt buộc chạy lại với `--build`.
- Mọi commit kết thúc bằng dòng trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## File Structure

| File | Trách nhiệm |
|---|---|
| `docker/odoo.conf` | Khai báo `addons_path` gồm 3 lớp addon |
| `custom-addons/aidt_base/` | Module nền của dự án; các module `aidt_*` khác depends vào nó |
| `extra-addons/README.md` | Sổ ghi vendor: nguồn, commit pin, module đã loại, danh sách patch |
| `extra-addons/dms/` | Subtree của OCA/dms@18.0 |
| `custom-addons/aidt_dms/models/sale_order.py` | Gắn `dms.field.mixin` vào `sale.order` |
| `custom-addons/aidt_dms/views/sale_order_views.xml` | Chèn tab Documents vào form Sale Order bằng view inheritance |
| `custom-addons/aidt_dms/tests/test_sale_order_dms.py` | Test tích hợp: tạo Sale Order → tự sinh thư mục DMS |
| `docs/dms-integration-guide.md` | Hướng dẫn cho dev: thêm DMS vào một model mới |

---

### Task 1: Cấu trúc addons 3 lớp + module nền `aidt_base`

Task này dựng `addons_path` và chứng minh nó hoạt động bằng một module thật cài được.

**Files:**
- Create: `custom-addons/aidt_base/__init__.py`
- Create: `custom-addons/aidt_base/__manifest__.py`
- Create: `custom-addons/.gitkeep`
- Modify: `docker/odoo.conf:6`

**Interfaces:**
- Consumes: không có (task đầu tiên)
- Produces: module `aidt_base` cài được, dùng làm `depends` cho mọi module `aidt_*` sau này. Thư mục `custom-addons/` đã nằm trong `addons_path`.

- [ ] **Step 1: Chạy thử để thấy nó thất bại**

```bash
cd /home/harryitc/my_project/aidt-odoo
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i aidt_base --stop-after-init
```

Expected: FAIL — Odoo thoát với lỗi `Some modules are not loaded, some dependencies or manifest may be missing: ['aidt_base']`.

Đây là trạng thái đúng để bắt đầu: module chưa tồn tại, thư mục chưa nằm trong `addons_path`.

- [ ] **Step 2: Sửa `addons_path`**

Trong `docker/odoo.conf`, thay dòng 6:

```
addons_path = /opt/odoo/addons
```

thành:

```
addons_path = /opt/odoo/addons,/opt/odoo/custom-addons
```

Chưa thêm `extra-addons/dms` ở bước này vì thư mục đó chưa tồn tại — Task 2 sẽ thêm.

- [ ] **Step 3: Tạo module `aidt_base`**

`custom-addons/.gitkeep` — file rỗng, để git theo dõi thư mục:

```bash
mkdir -p custom-addons/aidt_base
touch custom-addons/.gitkeep
```

`custom-addons/aidt_base/__manifest__.py`:

```python
{
    "name": "AIDT Base",
    "summary": "Nền chung cho các module tuỳ chỉnh của dự án AIDT",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "license": "LGPL-3",
    "author": "AIDT",
    "depends": ["base"],
    "data": [],
    "installable": True,
    "application": False,
}
```

`custom-addons/aidt_base/__init__.py` — file rỗng:

```python
```

- [ ] **Step 4: Build lại image**

`docker/odoo.conf` được COPY lúc build nên bắt buộc `--build`:

```bash
docker compose -f docker-compose.dev.yml build odoo
```

Expected: build thành công, exit code 0.

- [ ] **Step 5: Chạy lại lệnh cài và xác nhận thành công**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i aidt_base --stop-after-init
```

Expected: PASS — log chứa `odoo.modules.loading: Modules loaded.`, exit code 0, không có dòng `CRITICAL` hay `ERROR`.

- [ ] **Step 6: Kiểm chứng trong database**

```bash
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_test -c \
  "select name, state from ir_module_module where name = 'aidt_base';"
```

Expected: đúng 1 dòng, `aidt_base | installed`.

- [ ] **Step 7: Commit**

```bash
git add docker/odoo.conf custom-addons/
git commit -m "$(cat <<'EOF'
[ADD] custom-addons: three-layer addons path and aidt_base module

Adds custom-addons/ to addons_path and an empty base module that all
project-specific aidt_* modules will depend on.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Vendor OCA/dms bằng git subtree

**Files:**
- Create: `extra-addons/dms/` (subtree, ~20MB)
- Create: `extra-addons/README.md`
- Modify: `docker/odoo.conf:6`
- Delete: `extra-addons/dms/dms_user_role/`, `extra-addons/dms/web_editor_media_dialog_dms/`

**Interfaces:**
- Consumes: `addons_path` từ Task 1
- Produces: 5 thư mục module tại `extra-addons/dms/{dms,dms_field,dms_auto_classification,dms_field_auto_classification,hr_dms_field}`. Chúng **chưa cài được** — Task 3 và 4 xử lý. `extra-addons/dms` đã nằm trong `addons_path`.

**Về 3 module hoãn lại:** `dms_auto_classification`, `dms_field_auto_classification`, `hr_dms_field` được giữ nguyên ở version `18.0.*` và **cố ý không bump**. Chúng sẽ sinh log `WARNING ... incompatible version, setting installable=False` mỗi lần khởi động — đó là hành vi mong muốn: module nằm sẵn đó nhưng không cài được cho tới khi có người chủ động bump và kiểm thử. Đừng nhầm các cảnh báo này với lỗi.

- [ ] **Step 1: Đảm bảo working tree sạch**

`git subtree add` tạo một merge commit nên cần index sạch.

```bash
git status --short
```

Expected: không có dòng nào bắt đầu bằng `M `, ` M`, `A `, hay `D `. File `??` (untracked) không sao.

Nếu còn thay đổi chưa commit, commit hoặc stash trước khi đi tiếp.

- [ ] **Step 2: Kéo subtree về**

```bash
git subtree add --prefix extra-addons/dms \
  https://github.com/OCA/dms.git 18.0 --squash
```

Expected: output kết thúc bằng `Merge commit '<sha>'` hoặc `Added dir 'extra-addons/dms'`, exit code 0.

- [ ] **Step 3: Xác nhận đúng commit đã pin**

```bash
git log --oneline -1 --grep="git-subtree-split" --format="%b" | grep git-subtree-split
```

Expected: chứa `git-subtree-split: 6da958550a511dfa382c1f4208d6024adb4a5d95`

Nếu SHA khác, upstream đã có commit mới hơn kể từ lúc viết plan. Ghi lại SHA thực tế và dùng nó ở Step 5 thay cho SHA trong plan — đừng cố ép về SHA cũ.

- [ ] **Step 4: Xoá 2 module không dùng được**

```bash
git rm -r extra-addons/dms/dms_user_role
git rm -r extra-addons/dms/web_editor_media_dialog_dms
```

Expected: git báo đã xoá file, exit code 0.

- [ ] **Step 5: Viết sổ vendor**

`extra-addons/README.md`:

```markdown
# extra-addons — code của bên thứ ba

Thư mục này chỉ chứa những gì có thể tải lại được từ internet.
Nếu xoá cả thư mục rồi kéo lại mà mất mát thông tin, nghĩa là có thứ đã bị
đặt sai chỗ — nó phải nằm ở `custom-addons/`.

Mỗi repo vendor là một thư mục con và cần **một mục riêng trong
`addons_path`** (xem `docker/odoo.conf`), vì module nằm ở tầng con của nó.

## dms/

| | |
|---|---|
| Nguồn | https://github.com/OCA/dms |
| Branch | 18.0 |
| Commit pin | `6da958550a511dfa382c1f4208d6024adb4a5d95` (2026-07-22) |
| Cách kéo về | `git subtree add --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash` |
| Cách cập nhật | `git subtree pull --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash` |

### Module đã xoá khỏi bản vendor

| Module | Lý do |
|---|---|
| `dms_user_role` | Cần `base_user_role` (OCA/server-backend), chưa vendor repo đó |
| `web_editor_media_dialog_dms` | Cần `web_editor`, module này không còn trong Odoo 19 (đã thay bằng `html_editor`). Muốn dùng phải port thật, không phải bump version. |

### Patch đã áp lên code upstream

Mọi mục dưới đây là **thay đổi của chúng ta**, sẽ gây xung đột khi
`git subtree pull`. Khi OCA phát hành branch 19.0 chính thức, đối chiếu danh
sách này để bỏ những patch đã được upstream giải quyết.

| Commit | Nội dung |
|---|---|
| _(cập nhật ở Task 3 và Task 4)_ | |

## Nguyên tắc

- **Không sửa code ở đây để đổi hành vi.** Muốn đổi hành vi thì tạo/ sửa module
  `aidt_*` trong `custom-addons/` và dùng `_inherit`.
- Chỉ sửa khi module **không chạy được** nếu không sửa, hoặc vá bug gấp của upstream.
- Mỗi lần sửa: một commit riêng, tiêu đề bắt đầu `[MIG]` hoặc `[FIX]`, và thêm
  một dòng vào bảng "Patch đã áp" ở trên.
```

- [ ] **Step 6: Thêm `extra-addons/dms` vào addons_path**

Trong `docker/odoo.conf` dòng 6, thay:

```
addons_path = /opt/odoo/addons,/opt/odoo/custom-addons
```

thành:

```
addons_path = /opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons
```

- [ ] **Step 7: Build lại và xác nhận Odoo thấy đường dẫn mới nhưng module chưa cài được**

```bash
docker compose -f docker-compose.dev.yml build odoo
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i dms --stop-after-init 2>&1 | tee /tmp/dms-install-attempt.log
grep "module dms has an incompatible version" /tmp/dms-install-attempt.log
```

Expected: grep tìm thấy dòng dạng
`WARNING ... The module dms has an incompatible version, setting installable=False`

Đây chính là cơ chế ở `odoo/modules/module.py:465-467` — **đây là thất bại được dự đoán trước**, Task 3 sẽ xử lý. Nếu grep không tìm thấy gì, dừng lại: hoặc `addons_path` sai, hoặc thất bại vì lý do khác cần đọc log đầy đủ.

- [ ] **Step 8: Commit**

```bash
git add extra-addons/README.md docker/odoo.conf
git commit -m "$(cat <<'EOF'
[ADD] extra-addons: vendor OCA/dms 18.0 via git subtree

Pins OCA/dms at 6da9585 (18.0). Drops dms_user_role (needs base_user_role)
and web_editor_media_dialog_dms (needs web_editor, gone in Odoo 19).
Modules are not installable yet — manifest series bump follows.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Làm cho module `dms` cài được trên Odoo 19

Đây là task duy nhất có phần chưa biết trước. Chỉ **một** thay đổi là chắc chắn cần (bump version). Mọi thứ khác phải xuất phát từ traceback thật.

**Files:**
- Modify: `extra-addons/dms/dms/__manifest__.py` (dòng chứa `"version"`)
- Modify: `extra-addons/README.md` (bảng "Patch đã áp")
- Có thể modify thêm: file trong `extra-addons/dms/dms/` — chỉ khi có lỗi thật

**Interfaces:**
- Consumes: `extra-addons/dms/` và `addons_path` từ Task 2
- Produces: model `dms.storage`, `dms.directory`, `dms.file`, `dms.access.group`, `dms.category`, `dms.tag` và abstract model `dms.security.mixin` dùng được. Database `aidt_test` có `dms` ở trạng thái `installed`.

- [ ] **Step 1: Xác nhận thất bại hiện tại**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i dms --stop-after-init 2>&1 | grep "module dms has an incompatible version"
```

Expected: FAIL — in ra `The module dms has an incompatible version, setting installable=False`

- [ ] **Step 2: Bump version trong manifest**

Trong `extra-addons/dms/dms/__manifest__.py`, thay:

```python
    "version": "18.0.1.1.1",
```

thành:

```python
    "version": "19.0.1.1.1",
```

Giữ nguyên 3 số cuối. Chúng là version nội bộ của module, đổi chúng sẽ làm sai lệch cơ chế migration khi `git subtree pull` sau này.

- [ ] **Step 3: Chạy lại và đọc lỗi tiếp theo**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i dms --stop-after-init 2>&1 | tee /tmp/dms-install.log
echo "EXIT=$?"
grep -nE "CRITICAL|ERROR|Traceback" /tmp/dms-install.log
```

Có hai khả năng:

**a) Không có dòng ERROR/CRITICAL nào, exit code 0** → nhảy thẳng tới Step 5.

**b) Có lỗi** → sang Step 4.

- [ ] **Step 4: Vòng lặp sửa lỗi (chỉ chạy khi Step 3 báo lỗi)**

**REQUIRED SUB-SKILL:** dùng `superpowers:systematic-debugging` cho mỗi lỗi.

Quy tắc bắt buộc của vòng lặp này:

1. Sửa **một** lỗi mỗi lần, lỗi trên cùng trong log trước.
2. Mỗi thay đổi phải truy được về **một traceback cụ thể**. Không viết lại code theo linh cảm, không "sửa cho chắc".
3. Sau mỗi lần sửa, chạy lại lệnh ở Step 3.
4. Mỗi lỗi đã sửa = một commit riêng:

```bash
git add extra-addons/dms/dms/<file đã sửa>
git commit -m "$(cat <<'EOF'
[MIG] dms: <mô tả ngắn thay đổi> for Odoo 19

<Dán dòng lỗi gốc vào đây>

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

5. Thêm một dòng vào bảng "Patch đã áp" trong `extra-addons/README.md` cho mỗi commit.

**Ngưỡng dừng:** nếu vượt quá 10 lỗi riêng biệt, dừng lại và báo cho người dùng trước khi đi tiếp. Số lượng đó nghĩa là khoảng cách 18→19 lớn hơn dự đoán và quyết định phạm vi cần được xem lại.

**Bối cảnh có ích khi chẩn đoán** (đã khảo sát trước, các API sau **vẫn tồn tại** trong Odoo 19 nên không phải nguyên nhân): `@mail/core/common/attachment_model`, `@mail/core/common/link_preview`, `@web/core/file_viewer/file_viewer_hook`, kanban/list controller và renderer, `_sql_constraints` kiểu cũ. Trong code `dms@18.0` cũng không có `<tree>`, `name_get()`, `check_access_rights()` — tức là các nguồn gãy phổ biến nhất đều đã loại trừ.

- [ ] **Step 5: Kiểm chứng trạng thái cài đặt trong database**

```bash
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_test -c \
  "select name, state, latest_version from ir_module_module where name = 'dms';"
```

Expected: `dms | installed | 19.0.1.1.1`

- [ ] **Step 6: Kiểm chứng model đã được đăng ký**

```bash
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_test -tAc \
  "select model from ir_model where model like 'dms.%' order by model;"
```

Expected: danh sách chứa ít nhất `dms.access.group`, `dms.category`, `dms.directory`, `dms.file`, `dms.storage`, `dms.tag`.

- [ ] **Step 7: Chạy test của chính module dms**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d dms_selftest -i dms --test-enable --stop-after-init 2>&1 \
  | tee /tmp/dms-tests.log
grep -E "tests? (passed|failed)|FAIL:|ERROR:" /tmp/dms-tests.log
```

Expected: log chứa dòng dạng `X tests ... 0 failed, 0 error(s)`.

Nếu có test fail: sửa theo đúng vòng lặp ở Step 4. Test fail là bằng chứng cứng hơn log cài đặt — không được bỏ qua.

- [ ] **Step 8: Commit version bump (nếu chưa commit ở Step 4)**

```bash
git add extra-addons/dms/dms/__manifest__.py extra-addons/README.md
git commit -m "$(cat <<'EOF'
[MIG] dms: bump manifest to 19.0 series

Odoo rejects manifests from another series (odoo/modules/module.py:465),
setting installable=False. Internal version digits unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Làm cho module `dms_field` cài được

**Files:**
- Modify: `extra-addons/dms/dms_field/__manifest__.py` (dòng chứa `"version"`)
- Modify: `extra-addons/README.md` (bảng "Patch đã áp")
- Có thể modify thêm: file trong `extra-addons/dms/dms_field/` — chỉ khi có lỗi thật

**Interfaces:**
- Consumes: module `dms` đã cài được (Task 3)
- Produces:
  - Abstract model `dms.field.mixin` với field `dms_directory_ids` (One2many tới `dms.directory` qua `res_model`/`res_id`)
  - Model `dms.field.template` với các field: `name` (Char, required), `storage_id` (Many2one `dms.storage`, domain `save_type != 'attachment'`), `parent_directory_id` (Many2one `dms.directory`), `model_id` (Many2one `ir.model`), `group_ids` (Many2many `dms.access.group`), `user_field_id` (Many2one `ir.model.fields`), `directory_format_name` (Char, default `{{object.display_name}}`)
  - View type `dms_list` đăng ký trên `ir.ui.view` — dùng trong XML dưới dạng `<field name="dms_directory_ids" mode="dms_list"/>`

- [ ] **Step 1: Xác nhận thất bại hiện tại**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i dms_field --stop-after-init 2>&1 | grep "module dms_field has an incompatible version"
```

Expected: FAIL — `The module dms_field has an incompatible version, setting installable=False`

- [ ] **Step 2: Bump version**

Trong `extra-addons/dms/dms_field/__manifest__.py`, thay:

```python
    "version": "18.0.1.2.2",
```

thành:

```python
    "version": "19.0.1.2.2",
```

- [ ] **Step 3: Cài và đọc lỗi**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_test -i dms_field --stop-after-init 2>&1 | tee /tmp/dms-field-install.log
grep -nE "CRITICAL|ERROR|Traceback" /tmp/dms-field-install.log
```

Nếu có lỗi: dùng đúng vòng lặp ở Task 3 Step 4, đổi prefix commit thành `[MIG] dms_field:`.

**Điểm nghi ngờ số một nếu có lỗi:** `extra-addons/dms/dms_field/models/ir_ui_view.py` import `NameManager` từ `odoo.addons.base.models.ir_ui_view` và override `_postprocess_tag_dms_list()`. Đây là API nội bộ của tầng view, dễ đổi giữa các series nhất trong toàn bộ codebase DMS. Xác minh bằng:

```bash
grep -n "class NameManager\|def _postprocess_tag_field\|def _editable_node" odoo/addons/base/models/ir_ui_view.py
```

Nếu chữ ký hàm khác đi, chỉnh code trong `dms_field` cho khớp với chữ ký của Odoo 19 — đây đúng là trường hợp "không sửa thì không chạy", nên được phép sửa trong `extra-addons/`.

- [ ] **Step 4: Kiểm chứng trạng thái cài đặt**

```bash
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_test -c \
  "select name, state from ir_module_module where name in ('dms','dms_field') order by name;"
```

Expected: cả hai dòng đều `installed`.

- [ ] **Step 5: Kiểm chứng view type `dms_list` đã đăng ký**

```bash
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_test -tAc \
  "select count(*) from ir_ui_view where type = 'dms_list';"
```

Expected: số `>= 0` và **không có lỗi SQL**. Truy vấn chạy được nghĩa là giá trị `dms_list` đã được thêm hợp lệ vào cột selection.

- [ ] **Step 6: Chạy test của dms_field**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d dms_field_selftest -i dms_field --test-enable --stop-after-init 2>&1 \
  | tee /tmp/dms-field-tests.log
grep -E "tests? (passed|failed)|FAIL:|ERROR:" /tmp/dms-field-tests.log
```

Expected: `0 failed, 0 error(s)`.

- [ ] **Step 7: Commit**

```bash
git add extra-addons/dms/dms_field/__manifest__.py extra-addons/README.md
git commit -m "$(cat <<'EOF'
[MIG] dms_field: bump manifest to 19.0 series

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Module tích hợp `aidt_dms` — gắn DMS vào Sale Order

Đây là bản tham chiếu: chứng minh trọn vẹn mô hình "vendor + custom" và làm khuôn mẫu để gắn DMS vào bất kỳ model nào khác.

**Files:**
- Create: `custom-addons/aidt_dms/__init__.py`
- Create: `custom-addons/aidt_dms/__manifest__.py`
- Create: `custom-addons/aidt_dms/models/__init__.py`
- Create: `custom-addons/aidt_dms/models/sale_order.py`
- Create: `custom-addons/aidt_dms/views/sale_order_views.xml`
- Create: `custom-addons/aidt_dms/tests/__init__.py`
- Test: `custom-addons/aidt_dms/tests/test_sale_order_dms.py`

**Interfaces:**
- Consumes: `dms.field.mixin`, `dms.field.template`, `dms.storage`, `dms.access.group`, `dms.directory` (Task 3, 4); module `aidt_base` (Task 1)
- Produces: `sale.order` có field `dms_directory_ids`; form view của Sale Order có tab "Documents"; khuôn mẫu để nhân bản sang model khác

- [ ] **Step 1: Viết test cho hành vi mong muốn (chưa có code)**

`custom-addons/aidt_dms/tests/__init__.py`:

```python
from . import test_sale_order_dms
```

`custom-addons/aidt_dms/tests/test_sale_order_dms.py`:

```python
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.addons.base.tests.common import BaseCommon


class TestSaleOrderDms(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms.field.mixin.create() bỏ qua template khi chạy test, trừ khi
        # context test_dms_field được bật. Xem dms_field/models/dms_field_mixin.py.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.storage = cls.env["dms.storage"].create(
            {"name": "AIDT Test Storage", "save_type": "database"}
        )
        cls.access_group = cls.env["dms.access.group"].create(
            {
                "name": "AIDT Test Group",
                "perm_create": True,
                "perm_write": True,
                "perm_unlink": True,
                "explicit_user_ids": [(6, 0, [cls.env.user.id])],
            }
        )
        # install_mode làm dms.field.template tự tạo thư mục gốc của chính nó,
        # là thứ create_dms_directory() sao chép sang từng record.
        cls.template = (
            cls.env["dms.field.template"]
            .with_context(install_mode=True)
            .create(
                {
                    "name": "Sale Order",
                    "storage_id": cls.storage.id,
                    "model_id": cls.env["ir.model"]._get_id("sale.order"),
                    "group_ids": [(6, 0, cls.access_group.ids)],
                    "directory_format_name": "{{object.name}}",
                }
            )
        )
        cls.partner = cls.env["res.partner"].create({"name": "AIDT Test Customer"})

    def test_sale_order_has_dms_directory_field(self):
        self.assertIn("dms_directory_ids", self.env["sale.order"]._fields)

    def test_creating_sale_order_creates_dms_directory(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(len(order.dms_directory_ids), 1)
        directory = order.dms_directory_ids
        self.assertEqual(directory.name, order.name)
        self.assertEqual(directory.storage_id, self.storage)
        self.assertEqual(directory.res_model, "sale.order")
        self.assertEqual(directory.res_id, order.id)

    def test_deleting_sale_order_removes_dms_directory(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        directory = order.dms_directory_ids
        self.assertTrue(directory.exists())
        order.unlink()
        self.assertFalse(directory.exists())
```

- [ ] **Step 2: Tạo bộ khung module để test chạy được (và fail đúng lý do)**

`custom-addons/aidt_dms/__manifest__.py`:

```python
{
    "name": "AIDT — DMS Integration",
    "summary": "Gắn OCA DMS vào các model nghiệp vụ của AIDT",
    "version": "19.0.1.0.0",
    "category": "Document Management",
    "license": "LGPL-3",
    "author": "AIDT",
    "depends": ["aidt_base", "dms", "dms_field", "sale"],
    "data": [],
    "installable": True,
    "application": False,
}
```

`"data"` để rỗng ở bước này là cố ý: view chưa tồn tại, khai một file chưa có sẽ làm module không load được. Step 7 sẽ tạo view và khai nó cùng lúc.

`custom-addons/aidt_dms/__init__.py`:

```python
from . import models
```

`custom-addons/aidt_dms/models/__init__.py`:

```python
from . import sale_order
```

`custom-addons/aidt_dms/models/sale_order.py` — cố ý **chưa** thêm mixin, để test fail:

```python
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"
```

Chưa tạo file view nào ở bước này.

- [ ] **Step 3: Chạy test để xác nhận nó fail**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_dms_test -i aidt_dms --test-enable \
  --test-tags /aidt_dms --stop-after-init 2>&1 | tee /tmp/aidt-dms-test.log
grep -E "FAIL:|ERROR:" /tmp/aidt-dms-test.log
```

Expected: FAIL — `test_sale_order_has_dms_directory_field` báo `AssertionError: 'dms_directory_ids' not found in ...`, và hai test còn lại cũng fail.

- [ ] **Step 4: Thêm mixin — thay đổi tối thiểu để test pass**

Sửa `custom-addons/aidt_dms/models/sale_order.py` thành:

```python
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "dms.field.mixin"]
```

Lưu ý: khi thêm mixin phải khai lại cả `_name` lẫn danh sách `_inherit` gồm chính model đó. Đây là dạng bắt buộc của Odoo khi ghép một AbstractModel vào một model đã có. `hr_dms_field` và `dms_field/models/res_partner.py` của OCA làm y hệt.

- [ ] **Step 5: Chạy lại test và xác nhận pass**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_dms_test2 -i aidt_dms --test-enable \
  --test-tags /aidt_dms --stop-after-init 2>&1 | tee /tmp/aidt-dms-test2.log
grep -E "FAIL:|ERROR:|tests? .* failed" /tmp/aidt-dms-test2.log
```

Expected: PASS — `0 failed, 0 error(s)`, không có dòng `FAIL:`.

Dùng database mới (`aidt_dms_test2`) vì lần chạy trước đã tạo bảng theo phiên bản model cũ.

- [ ] **Step 6: Commit phần model**

```bash
git add custom-addons/aidt_dms/
git commit -m "$(cat <<'EOF'
[ADD] aidt_dms: attach dms.field.mixin to sale.order

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Thêm tab Documents vào form Sale Order**

Trong `custom-addons/aidt_dms/__manifest__.py`, thay `"data": [],` bằng:

```python
    "data": [
        "views/sale_order_views.xml",
    ],
```

Rồi tạo `custom-addons/aidt_dms/views/sale_order_views.xml`:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!-- License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). -->
<odoo>
    <record id="view_order_form_aidt_dms" model="ir.ui.view">
        <field name="name">sale.order.form.aidt.dms</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form" />
        <field name="arch" type="xml">
            <notebook position="inside">
                <page name="aidt_dms" string="Documents" invisible="not id">
                    <field name="dms_directory_ids" mode="dms_list" />
                </page>
            </notebook>
        </field>
    </record>
</odoo>
```

Ba điểm cần hiểu:
- `inherit_id` + `position` là **view inheritance** — file view gốc của module `sale` không bị đụng vào.
- `mode="dms_list"` là cách đúng để render cây DMS, khớp với view type mà `dms_field` đăng ký. Đây chính là khuôn mà OCA dùng trong `dms_field/demo/partner_dms.xml`.
- `invisible="not id"` ẩn tab khi bản ghi chưa được lưu, vì lúc đó chưa có `res_id` để gắn thư mục.

- [ ] **Step 8: Xác nhận view load được**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_dms_test2 -u aidt_dms --stop-after-init 2>&1 | tee /tmp/aidt-view.log
grep -nE "CRITICAL|ERROR|ParseError|Traceback" /tmp/aidt-view.log
```

Expected: grep không ra kết quả nào, exit code 0.

Lỗi view sai trong Odoo được phát hiện ngay lúc load, nên "không có lỗi" ở đây là bằng chứng thật, không phải suy đoán.

- [ ] **Step 9: Kiểm chứng view đã vào database**

```bash
docker compose -f docker-compose.dev.yml exec db \
  psql -U odoo -d aidt_dms_test2 -tAc \
  "select count(*) from ir_ui_view where name = 'sale.order.form.aidt.dms';"
```

Expected: `1`

- [ ] **Step 10: Commit**

```bash
git add custom-addons/aidt_dms/views/sale_order_views.xml custom-addons/aidt_dms/__manifest__.py
git commit -m "$(cat <<'EOF'
[ADD] aidt_dms: add Documents tab to sale order form

Uses view inheritance so sale's own view file stays untouched.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Kiểm chứng bằng UI thật + tài liệu hướng dẫn

Các task trước chứng minh code chạy. Task này chứng minh **người dùng thật bấm được**, và để lại hướng dẫn cho dev tiếp theo.

**Files:**
- Create: `docs/dms-integration-guide.md`
- Modify: `extra-addons/README.md` (hoàn tất bảng "Patch đã áp")

**Interfaces:**
- Consumes: toàn bộ Task 1–5
- Produces: không có interface code; đầu ra là bằng chứng vận hành và tài liệu

- [ ] **Step 1: Khởi động stack dev**

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
```

Expected: cả `db` và `odoo` đều `Up`, `db` ở trạng thái `healthy`.

Lưu ý: lần build đầu mất nhiều phút. Nếu chạy nền bị ngắt, chạy lại ở terminal trực tiếp.

- [ ] **Step 2: Tạo database demo và cài đủ module**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_demo -i aidt_dms --stop-after-init
```

Expected: exit code 0, log kết thúc bằng `Modules loaded.`

- [ ] **Step 3: Kiểm chứng bằng UI — luồng DMS cơ bản**

Mở http://localhost:8069, đăng nhập database `aidt_demo`, rồi làm theo đúng thứ tự và ghi lại kết quả từng bước:

1. Vào app **Documents** (DMS) từ menu chính → **menu phải hiện ra**
2. Settings → tạo một `Storage` mới, `Save Type = Database` → **lưu được, không lỗi**
3. Tạo một `Directory` gốc trong storage đó → **lưu được**
4. Upload một file PDF vào directory → **file hiện trong danh sách**
5. Bấm vào file → **preview hiện nội dung PDF**, không phải khung trắng

Bước 5 là quan trọng nhất: nó chạy qua tầng JS (`file_viewer_hook`) và tầng `Stream` trong `odoo/http.py`. Khung trắng nghĩa là lỗi, không phải "chưa load xong".

Nếu bước nào fail: quay lại vòng lặp sửa lỗi ở Task 3 Step 4, dùng console của trình duyệt và log container làm nguồn chẩn đoán.

- [ ] **Step 4: Kiểm chứng bằng UI — luồng tích hợp Sale Order**

1. Vào Settings → Technical → tìm menu **DMS Field Templates**, tạo một template:
   - Name: `Sale Order`
   - Storage: storage vừa tạo ở Step 3
   - Model: `Sales Order`
   - Directory format name: `{{object.name}}`
2. Vào app **Sales**, tạo một Sale Order mới với một khách hàng bất kỳ, **Lưu**
3. → Tab **Documents** xuất hiện trong form
4. Bấm vào tab → **hiện cây thư mục, có một thư mục tên đúng bằng số Sale Order** (ví dụ `S00001`)
5. Upload một file vào đó → **file lưu được và hiện ra**

Bước 4 là bằng chứng `dms.field.mixin.create()` đã chạy đúng trên môi trường thật (không phải test, nơi nó bị gate bởi context `test_dms_field`).

- [ ] **Step 5: Chạy lại toàn bộ test lần cuối**

```bash
docker compose -f docker-compose.dev.yml run --rm odoo \
  odoo -d aidt_full_test -i aidt_dms --test-enable --stop-after-init 2>&1 \
  | tee /tmp/aidt-full-test.log
grep -cE "FAIL:|ERROR:" /tmp/aidt-full-test.log
```

Expected: `0`

Lệnh này cài `aidt_dms` cùng toàn bộ dependency (`dms`, `dms_field`, `sale`, `aidt_base`) và chạy test của tất cả, tức là bắt được cả hồi quy do module của ta gây ra cho module vendor.

- [ ] **Step 6: Viết hướng dẫn cho dev**

`docs/dms-integration-guide.md`:

```markdown
# Gắn DMS vào một model — hướng dẫn

## Bối cảnh

Odoo Enterprise `documents` không có ở bản Community này. Ta dùng
[OCA/dms](https://github.com/OCA/dms), vendor tại `extra-addons/dms/`.
Mọi tuỳ chỉnh nằm ở `custom-addons/aidt_dms/` và **không bao giờ** sửa
code trong `extra-addons/` để đổi hành vi.

## Ba cách tích hợp — chọn cách rẻ nhất còn đủ dùng

### Cách 1 — Storage kiểu `attachment` (không viết code)

`dms.storage` có `save_type = "attachment"` cùng field `model_ids`
(Many2many tới `ir.model`). Chọn model nào ở đó thì **mọi `ir.attachment`
của record thuộc model đó tự hiện trong cây DMS**, không tạo bản sao dữ liệu.

Cấu hình hoàn toàn trong UI. Thử cách này trước.

Giới hạn: không có cây thư mục riêng cho từng record.

### Cách 2 — `dms.field.mixin` (một dòng Python + một khối XML)

Dùng khi mỗi record cần thư mục riêng. Đây là cách `aidt_dms` làm với
`sale.order` — copy nguyên mẫu đó.

**Python** — `custom-addons/aidt_dms/models/<model>.py`:

```python
from odoo import models


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "dms.field.mixin"]
```

Phải khai cả `_name` lẫn danh sách `_inherit` gồm chính model đó.

**XML** — thêm tab vào form, bằng view inheritance:

```xml
<record id="view_task_form_aidt_dms" model="ir.ui.view">
    <field name="model">project.task</field>
    <field name="inherit_id" ref="project.view_task_form2" />
    <field name="arch" type="xml">
        <notebook position="inside">
            <page name="aidt_dms" string="Documents" invisible="not id">
                <field name="dms_directory_ids" mode="dms_list" />
            </page>
        </notebook>
    </field>
</record>
```

`mode="dms_list"` là view type do `dms_field` đăng ký trên `ir.ui.view`.

**Cấu hình** — Settings → Technical → DMS Field Templates. Tạo template
trỏ tới model đó, chọn storage và `directory_format_name`. Đây là **dữ liệu,
không phải code**: người dùng nghiệp vụ tự đổi được, không cần deploy lại.

Đừng quên thêm module tương ứng vào `depends` của `aidt_dms`.

### Cách 3 — gọi thẳng model DMS

Chỉ dùng khi luồng nghiệp vụ đặc thù mà template không diễn tả được:

```python
directory = self.env["dms.directory"].create({
    "name": f"HĐ {self.name}",
    "storage_id": storage.id,
    "res_model": self._name,
    "res_id": self.id,
})
self.env["dms.file"].create({
    "name": "hop-dong.pdf",
    "directory_id": directory.id,
    "content": base64_data,
})
```

## Cấu trúc dữ liệu

```
dms.storage      save_type (database | file | attachment), model_ids, company_id
  └─ dms.directory   parent_id (cây lồng nhau), res_model + res_id (gắn record)
       └─ dms.file       content, category_id, tag_ids, mimetype
dms.access.group   phân quyền, gắn vào directory
dms.category / dms.tag   phân loại
```

## Hai cái bẫy đã gặp thật

**1. Template không chạy trong test.**
`dms.field.mixin.create()` bỏ qua template khi `config["test_enable"]` bật,
trừ khi context có `test_dms_field`. Trong test phải viết:

```python
cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
```

Không có dòng này thì thư mục không tự sinh và test fail một cách khó hiểu.

**2. Quyền truy cập.**
Mixin dùng `sudo()` trong `write()` và `unlink()` vì người dùng thường
không có quyền trên `dms.directory`. Nó còn override `web_save()` để né
lỗi access khi lưu form — chính OCA gọi đó là "hack" trong comment.
Khi bạn tự viết code đụng `dms.directory`, phải tính đến điều này.

## Cập nhật DMS từ upstream

```bash
git subtree pull --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash
```

Xung đột sẽ rơi đúng vào những chỗ ta đã patch — xem bảng "Patch đã áp"
trong `extra-addons/README.md`. `custom-addons/aidt_dms/` không bị ảnh hưởng.

Khi OCA phát hành branch 19.0 chính thức, đối chiếu bảng đó để bỏ những
patch đã được upstream giải quyết, rồi đổi branch nguồn thành `19.0`.
```

- [ ] **Step 7: Hoàn tất bảng patch trong `extra-addons/README.md`**

Điền vào bảng "Patch đã áp" mọi commit `[MIG]`/`[FIX]` đã tạo ở Task 3 và Task 4.

Lấy danh sách chính xác bằng:

```bash
git log --oneline --grep="^\[MIG\]\|^\[FIX\]" -- extra-addons/
```

Mỗi dòng output thành một hàng trong bảng, cột trái là SHA ngắn, cột phải là mô tả.

- [ ] **Step 8: Commit**

```bash
git add docs/dms-integration-guide.md extra-addons/README.md
git commit -m "$(cat <<'EOF'
[ADD] docs: DMS integration guide and vendor patch log

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Ghi chú về rủi ro

**Task 3 và Task 4 là hai task duy nhất có phần chưa xác định.** Khảo sát trước cho thấy khoảng cách 18→19 nhỏ (mọi API JS mà DMS dùng đều còn; không có `<tree>`, `name_get`, `check_access_rights`), nhưng chi phí thật chỉ lộ ra khi loader chạy. Điểm rủi ro tập trung nhất là `dms_field/models/ir_ui_view.py` vì nó override API nội bộ của tầng view.

**Nếu Task 3 vượt 10 lỗi riêng biệt:** dừng, báo người dùng. Khi đó nên cân nhắc thu hẹp còn mỗi module `dms` và bỏ `dms_field` khỏi đợt này.

**`web_editor_media_dialog_dms` cần công việc riêng** nếu sau này muốn chọn file DMS từ media dialog của trình soạn thảo — đó là port sang `html_editor`, không phải bump version.
