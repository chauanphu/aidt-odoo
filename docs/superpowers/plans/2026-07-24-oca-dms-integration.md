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

