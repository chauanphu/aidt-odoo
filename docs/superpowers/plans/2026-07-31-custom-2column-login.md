# Custom 2-Column Traditional Red Login View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a custom 2-column traditional red split-view login page for AIDT in `custom-addons/aidt_base` while preserving 100% of Odoo's login form logic.

**Architecture:** Inherit `web.login_layout` in XML template `aidt_login_templates.xml`, replacing the default single centered card with a Bootstrap-based 2-column flex card container (Left: Deep Maroon Red branding, Right: Odoo login form).

**Tech Stack:** Odoo 19 QWeb XML, Bootstrap 5, Python unit tests.

## Global Constraints
- Target module: `custom-addons/aidt_base`.
- Preserves all Odoo form input names (`login`, `password`, `db`, `csrf_token`, `type`, `redirect`) and form action `/web/login`.
- Left column theme: Traditional Party Red (`#7A0C0D` / `#4A0809` gradient with gold accents `#D4AF37`).

---

### Task 1: Create Custom 2-Column Login XML Template & Update Manifest

**Files:**
- Create: `custom-addons/aidt_base/views/aidt_login_templates.xml`
- Modify: `custom-addons/aidt_base/__manifest__.py`

**Interfaces:**
- Consumes: Odoo `web.login_layout`
- Produces: `web.login_layout` QWeb view override with `aidt-login-split-view` layout

- [ ] **Step 1: Create QWeb template override `aidt_login_templates.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="aidt_login_layout_override" inherit_id="web.login_layout" name="AIDT 2-Column Red Login Layout">
        <xpath expr="//div[hasclass('container')]" position="replace">
            <div class="container-fluid min-vh-100 p-0 d-flex align-items-center justify-content-center bg-light aidt-login-split-view" style="background: #1a1a1a;">
                <div class="card border-0 rounded-4 overflow-hidden shadow-lg w-100 my-4 mx-3" style="max-width: 960px;">
                    <div class="row g-0">
                        <!-- Left Column: Branding Panel (Traditional Party Red) -->
                        <div class="col-12 col-md-6 p-4 p-lg-5 text-white d-flex flex-column justify-content-between"
                             style="background: linear-gradient(145deg, #7A0C0D 0%, #4A0809 100%); border-right: 2px solid #D4AF37;">
                            <div>
                                <div class="mb-4 d-flex align-items-center gap-3">
                                    <div class="rounded-circle d-flex align-items-center justify-content-center shadow"
                                         style="width: 54px; height: 54px; background: #D4AF37; color: #7A0C0D;">
                                        <i class="fa fa-star fa-2x" aria-hidden="true"/>
                                    </div>
                                    <div>
                                        <h5 class="mb-0 text-warning fw-bold text-uppercase" style="letter-spacing: 1px;">Văn phòng Cấp ủy</h5>
                                        <small class="text-white-50">Hệ thống Hành chính Điện tử</small>
                                    </div>
                                </div>
                                <h3 class="fw-bold text-white mb-3">HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY</h3>
                                <p class="text-white-50 small mb-4">Giải pháp quản lý văn bản, bút phê, theo dõi nhiệm vụ và lịch công tác tập trung.</p>
                                
                                <div class="d-flex flex-column gap-3 mb-4">
                                    <div class="d-flex align-items-start gap-2">
                                        <i class="fa fa-check-circle text-warning mt-1"/>
                                        <span class="small">Quản lý Văn bản đến &amp; Bút phê giao việc tức thì</span>
                                    </div>
                                    <div class="d-flex align-items-start gap-2">
                                        <i class="fa fa-check-circle text-warning mt-1"/>
                                        <span class="small">Theo dõi Nhiệm vụ toàn đơn vị 4 cấp trạng thái</span>
                                    </div>
                                    <div class="d-flex align-items-start gap-2">
                                        <i class="fa fa-check-circle text-warning mt-1"/>
                                        <span class="small">Lịch công tác tuần &amp; Đăng ký hẹn làm việc công dân</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="pt-3 border-top border-white-10 text-white-50 small">
                                <i class="fa fa-shield me-1 text-warning"/> Bảo mật • Thông suốt • Hiệu quả
                            </div>
                        </div>
                        
                        <!-- Right Column: Odoo Login Form -->
                        <div class="col-12 col-md-6 p-4 p-lg-5 bg-white d-flex flex-column justify-content-center">
                            <div class="text-center mb-4">
                                <img t-attf-src="/web/binary/company_logo{{ '?dbname='+db if db else '' }}" alt="Logo" style="max-height:80px; max-width: 100%; width:auto"/>
                                <h5 class="fw-bold text-dark mt-3 mb-1">Đăng nhập Hệ thống</h5>
                                <p class="text-muted small">Vui lòng nhập tài khoản và mật khẩu để tiếp tục</p>
                            </div>
                            
                            <t t-out="0"/>
                            
                            <div class="text-center small mt-4 pt-3 border-top" t-if="not disable_footer">
                                <t t-if="not disable_database_manager">
                                    <a class="border-end pe-2 me-1 text-decoration-none" href="/web/database/manager">Quản lý Database</a>
                                </t>
                                <span class="text-muted">Hệ thống AIDT Cấp ủy</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </xpath>
    </template>
</odoo>
```

- [ ] **Step 2: Update `custom-addons/aidt_base/__manifest__.py`**

Add `'views/aidt_login_templates.xml'` to the `'data'` list.

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_base/views/aidt_login_templates.xml custom-addons/aidt_base/__manifest__.py
git commit -m "feat(base): add custom 2-column traditional red login template"
```

---

### Task 2: Create Automated Unit Test & Upgrade Module

**Files:**
- Create: `custom-addons/aidt_base/tests/test_login_layout.py`

- [ ] **Step 1: Write unit test `test_login_layout.py`**

```python
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLoginLayout(HttpCase):

    def test_01_custom_login_page_renders_2column(self):
        """Verify that opening /web/login renders the 2-column layout with system title."""
        res = self.url_open('/web/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn('aidt-login-split-view', res.text)
        self.assertIn('HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY', res.text)
```

- [ ] **Step 2: Run module upgrade and unit test in Docker container**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_base --test-enable --test-tags=TestLoginLayout --stop-after-init --http-port=8079 && docker restart aidt-odoo-dev-odoo-1
```
Expected: PASS (0 failed, 0 errors)

- [ ] **Step 3: Commit**

```bash
git add custom-addons/aidt_base/tests/test_login_layout.py
git commit -m "test(base): add unit test for 2-column red login page layout"
```
