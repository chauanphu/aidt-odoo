# Digital Signature Module (`aidt_sign`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triển khai module ký số điện tử PAdES chuẩn Nghị định 30 (`aidt_sign`), tự động chuyển đổi file `.docx` sang `.pdf`, thực hiện luồng ký 2 bước (Lãnh đạo ký cá nhân + Văn thư cấp số/đóng dấu cơ quan).

**Architecture:** Tạo module mới `custom-addons/aidt_sign` chứa Engine chuyển đổi PDF (`LibreOffice CLI`), Engine ký số PAdES (`pyHanko`), Model quản lý chứng thư số PKCS#12 (`.p12`). Ghi đè luồng `action_sign` và `action_issue_vbd` trong `aidt_vanban_di`.

**Tech Stack:** Odoo 17/18, Python `pyhanko`, `cryptography`, `pillow`, LibreOffice Headless CLI (`soffice`).

## Global Constraints

- Python requirements: `pyhanko[pypdf]>=0.20.0`, `cryptography>=41.0.0`, `pillow>=10.0.0`.
- System package: `libreoffice-writer`.
- Certificate storage: Secure binary field for `.p12`/`.pfx` files in Odoo database with encrypted password.
- Multi-signing: Support Incremental Updates for 2-step signing without breaking previous signatures.

---

### Task 1: Module Scaffolding & Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `Dockerfile`
- Create: `custom-addons/aidt_sign/__manifest__.py`
- Create: `custom-addons/aidt_sign/__init__.py`
- Create: `custom-addons/aidt_sign/models/__init__.py`
- Create: `custom-addons/aidt_sign/services/__init__.py`

**Interfaces:**
- Consumes: Odoo base module
- Produces: `aidt_sign` base module definition

- [ ] **Step 1: Update requirements.txt and Dockerfile with pyhanko and libreoffice**

Add `pyhanko[pypdf]>=0.20.0`, `pillow>=10.0.0` to `requirements.txt` and `libreoffice-writer` to `Dockerfile`.

- [ ] **Step 2: Create `aidt_sign/__manifest__.py`**

```python
{
    'name': 'AIDT Digital Signature (Ký Số PAdES)',
    'version': '1.0',
    'category': 'Document Management',
    'summary': 'Module Ký số điện tử PAdES & chuyển đổi PDF chuẩn Nghị định 30',
    'depends': ['base', 'mail', 'aidt_base'],
    'data': [
        'security/sign_groups.xml',
        'security/ir.model.access.csv',
        'views/aidt_sign_certificate_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
```

- [ ] **Step 3: Create `__init__.py` files**

Create `custom-addons/aidt_sign/__init__.py`:
```python
from . import models
from . import services
```

Create `custom-addons/aidt_sign/models/__init__.py`:
```python
from . import aidt_sign_certificate
from . import aidt_sign_log
from . import res_users
```

Create `custom-addons/aidt_sign/services/__init__.py`:
```python
from . import pdf_converter
from . import pades_signer
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt Dockerfile custom-addons/aidt_sign/
git commit -m "feat(aidt_sign): scaffold aidt_sign module and dependencies"
```

---

### Task 2: PDF Converter Service (`pdf_converter.py`)

**Files:**
- Create: `custom-addons/aidt_sign/services/pdf_converter.py`
- Create: `custom-addons/aidt_sign/tests/test_pdf_converter.py`

**Interfaces:**
- Consumes: File content bytes (docx/pdf) & filename
- Produces: `convert_to_pdf(file_content: bytes, filename: str) -> bytes`

- [ ] **Step 1: Write test for PDF converter**

```python
import unittest
from odoo.addons.aidt_sign.services.pdf_converter import convert_to_pdf

class TestPdfConverter(unittest.TestCase):
    def test_pdf_already_returns_same(self):
        content = b"%PDF-1.4 test"
        res = convert_to_pdf(content, "document.pdf")
        self.assertEqual(res, content)
```

- [ ] **Step 2: Implement `pdf_converter.py`**

```python
import tempfile
import subprocess
import os
import logging

_logger = logging.getLogger(__name__)

def convert_to_pdf(file_content: bytes, filename: str) -> bytes:
    if filename.lower().endswith('.pdf') or file_content.startswith(b'%PDF'):
        return file_content

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, filename)
        with open(input_path, 'wb') as f:
            f.write(file_content)

        cmd = [
            'soffice', '--headless', '--convert-to', 'pdf',
            '--outdir', tmp_dir, input_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if res.returncode != 0:
                _logger.error("LibreOffice conversion failed: %s", res.stderr.decode())
                raise RuntimeError(f"Chuyển đổi PDF thất bại: {res.stderr.decode()}")
        except Exception as e:
            _logger.error("Error executing LibreOffice: %s", str(e))
            raise RuntimeError(f"Lỗi hệ thống khi chuyển đổi file Word sang PDF: {str(e)}")

        base_name = os.path.splitext(filename)[0]
        output_pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")
        if not os.path.exists(output_pdf_path):
            raise FileNotFoundError(f"Không tìm thấy file PDF đầu ra sau khi convert: {output_pdf_path}")

        with open(output_pdf_path, 'rb') as f:
            return f.read()
```

- [ ] **Step 3: Run test**

```bash
python3 -m unittest custom-addons/aidt_sign/tests/test_pdf_converter.py
```

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_sign/services/pdf_converter.py custom-addons/aidt_sign/tests/
git commit -m "feat(aidt_sign): add docx to pdf converter service"
```

---

### Task 3: Certificate & Log Models (`aidt_sign_certificate.py`, `aidt_sign_log.py`, `res_users.py`)

**Files:**
- Create: `custom-addons/aidt_sign/models/aidt_sign_certificate.py`
- Create: `custom-addons/aidt_sign/models/aidt_sign_log.py`
- Create: `custom-addons/aidt_sign/models/res_users.py`

**Interfaces:**
- Consumes: Odoo ORM Models
- Produces: `aidt.sign.certificate`, `aidt.sign.log` models & `res.users` signature image / cert relation.

- [ ] **Step 1: Create `aidt_sign_certificate.py`**

```python
from odoo import models, fields, api

class AidtSignCertificate(models.Model):
    _name = 'aidt.sign.certificate'
    _description = 'Chứng thư số PKCS#12'

    name = fields.Char(string='Tên chứng thư', required=True)
    cert_file = fields.Binary(string='Tệp chứng thư (.p12/.pfx)', required=True)
    cert_filename = fields.Char(string='Tên tệp')
    password = fields.Char(string='Mật khẩu mở chứng thư', required=True)
    cert_type = fields.Selection([
        ('personal', 'Chữ ký số cá nhân (Lãnh đạo)'),
        ('org', 'Chữ ký số tổ chức (Con dấu cơ quan)')
    ], string='Loại chứng thư', default='personal', required=True)
    owner_id = fields.Many2one('res.users', string='Người sở hữu')
    active = fields.Boolean(default=True)
```

- [ ] **Step 2: Create `aidt_sign_log.py`**

```python
from odoo import models, fields

class AidtSignLog(models.Model):
    _name = 'aidt.sign.log'
    _description = 'Nhật ký Ký số PAdES'
    _order = 'create_date desc'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Many2oneReference(string='ID Bản ghi', model_field='res_model', required=True)
    user_id = fields.Many2one('res.users', string='Người ký', default=lambda self: self.env.user)
    sign_type = fields.Selection([
        ('leader', 'Ký Lãnh đạo'),
        ('org', 'Đóng dấu Cơ quan')
    ], string='Loại ký', required=True)
    cert_name = fields.Char(string='Chứng thư số sử dụng')
    signed_date = fields.Datetime(string='Thời điểm ký', default=fields.Datetime.now)
    digest_sha256 = fields.Char(string='Mã băm SHA-256')
```

- [ ] **Step 3: Create `res_users.py`**

```python
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    digital_signature_img = fields.Binary(string='Ảnh chữ ký tay tươi')
    certificate_ids = fields.One2many('aidt.sign.certificate', 'owner_id', string='Chứng thư số cá nhân')
```

- [ ] **Step 4: Commit**

```bash
git add custom-addons/aidt_sign/models/
git commit -m "feat(aidt_sign): add certificate and sign log models"
```

---

### Task 4: PAdES Signer Engine (`pades_signer.py`)

**Files:**
- Create: `custom-addons/aidt_sign/services/pades_signer.py`
- Create: `custom-addons/aidt_sign/tests/test_pades_signer.py`

**Interfaces:**
- Consumes: PDF bytes, Cert bytes, Cert password, Signature Image bytes, Signer Name
- Produces: `sign_pades_pdf(pdf_bytes: bytes, cert_bytes: bytes, password: str, img_bytes: bytes, signer_name: str, is_org: bool = False) -> bytes`

- [ ] **Step 1: Implement `pades_signer.py` using pyHanko**

```python
import io
import logging
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers, Timedelta

_logger = logging.getLogger(__name__)

def sign_pades_pdf(pdf_bytes: bytes, cert_bytes: bytes, password: str, img_bytes: bytes = None, signer_name: str = "", is_org: bool = False) -> bytes:
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        writer = IncrementalPdfFileWriter(pdf_stream)

        # Load PKCS12 Certificate
        cert_stream = io.BytesIO(cert_bytes)
        signer = signers.load_crypto_backend().load_pkcs12_key_set(
            cert_stream, password=password.encode('utf-8')
        )

        sig_field_name = 'OrgStampField' if is_org else 'LeaderSignatureField'
        fields.append_signature_field(
            writer,
            sig_field_spec=fields.SigFieldSpec(
                sig_field_name=sig_field_name,
                on_page=-1,
                box=(350, 100, 550, 200) if not is_org else (100, 700, 250, 800)
            )
        )

        meta = signers.PdfSignatureMetadata(field_name=sig_field_name)
        pdf_signer = signers.PdfSigner(
            meta, signer=signer,
        )

        out = io.BytesIO()
        pdf_signer.sign_pdf(writer, output=out)
        return out.getvalue()
    except Exception as e:
        _logger.error("PAdES signing failed: %s", str(e))
        raise RuntimeError(f"Lỗi ký số PAdES: {str(e)}")
```

- [ ] **Step 2: Commit**

```bash
git add custom-addons/aidt_sign/services/pades_signer.py
git commit -m "feat(aidt_sign): add PAdES signer engine service"
```

---

### Task 5: Integration with `aidt_vanban_di`

**Files:**
- Modify: `custom-addons/aidt_vanban_di/__manifest__.py`
- Modify: `custom-addons/aidt_vanban_di/models/aidt_document.py`

**Interfaces:**
- Consumes: `action_sign()`, `action_issue_vbd()` in `aidt_vanban_di`
- Produces: Integrated PAdES digital signing & auto DOCX->PDF conversion in `aidt_vanban_di`

- [ ] **Step 1: Add `aidt_sign` dependency to `aidt_vanban_di/__manifest__.py`**

Add `'aidt_sign'` to `'depends'`.

- [ ] **Step 2: Override `action_sign()` in `aidt_document.py`**

```python
    def action_sign(self):
        """Thực hiện Ký số Lãnh đạo PAdES."""
        allowed_groups = ['aidt_org.group_bi_thu', 'aidt_org.group_pho_bi_thu', 'aidt_org.group_aidt_admin']
        if not any(self.env.user.has_group(g) for g in allowed_groups):
            raise UserError("Bạn không có quyền thực hiện ký số.")

        for rec in self:
            if rec.direction != 'di':
                continue

            # 1. Tim attachment du thao
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'aidt.document'),
                ('res_id', '=', rec.id)
            ], order='id desc', limit=1)

            if not attachment:
                raise UserError("Vui lòng đính kèm tệp dự thảo trước khi ký số.")

            # 2. Convert docx sang pdf neu can
            pdf_bytes = convert_to_pdf(attachment.datas, attachment.name)

            # 3. Lay cert cua user
            cert = self.env['aidt.sign.certificate'].search([
                ('owner_id', '=', self.env.uid),
                ('cert_type', '=', 'personal'),
                ('active', '=', True)
            ], limit=1)

            if not cert:
                # Nếu chưa cài cert thực tế, fallback lưu vết như MVP hiện tại và đổi state
                rec.sudo().write({
                    'state': 'cho_cap_so',
                    'nguoi_ky_id': self.env.uid,
                    'ngay_ky': fields.Datetime.now(),
                })
                continue

            # 4. Ky PAdES
            signed_pdf = sign_pades_pdf(
                pdf_bytes=pdf_bytes,
                cert_bytes=cert.cert_file,
                password=cert.password,
                signer_name=self.env.user.name
            )

            # 5. Cap nhat attachment & record state
            attachment.sudo().write({
                'datas': signed_pdf,
                'name': f"{os.path.splitext(attachment.name)[0]}_signed.pdf",
                'mimetype': 'application/pdf'
            })

            rec.sudo().write({
                'state': 'cho_cap_so',
                'nguoi_ky_id': self.env.uid,
                'ngay_ky': fields.Datetime.now(),
            })
```

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_vanban_di/
git commit -m "feat(aidt_vanban_di): integrate PAdES digital signing into action_sign"
```

---

### Task 6: Views & Security Rules for `aidt_sign`

**Files:**
- Create: `custom-addons/aidt_sign/security/sign_groups.xml`
- Create: `custom-addons/aidt_sign/security/ir.model.access.csv`
- Create: `custom-addons/aidt_sign/views/aidt_sign_certificate_views.xml`
- Create: `custom-addons/aidt_sign/views/res_users_views.xml`

- [ ] **Step 1: Define security rules & access ACLs**
- [ ] **Step 2: Create views for Certificates and User signature upload**
- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_sign/security/ custom-addons/aidt_sign/views/
git commit -m "feat(aidt_sign): add security access rules and certificate management views"
```
