# Full-Screen 50/50 Split View Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the login page into a true full-screen 50/50 split-view layout spanning 100% viewport width and height without floating card containers or outer background gaps.

**Architecture:** Update QWeb XML template `custom-addons/aidt_base/views/aidt_login_templates.xml` to replace the outer card container with a full-height container (`container-fluid min-vh-100 p-0 m-0 overflow-hidden`), with 50% left crimson branding panel and 50% right white centered login form panel.

**Tech Stack:** Odoo 19 QWeb XML, Bootstrap 5, Python unit tests.

## Global Constraints
- Target module: `custom-addons/aidt_base`.
- Full-screen layout: 0 outer margins, 0 card borders, 100vh height.
- Left column: Traditional Party Red (`#7A0C0D` ➔ `#4A0809` gradient with `#D4AF37` gold accents).
- Right column: Clean white background with centered login form.

---

### Task 1: Update Login QWeb Template to Full-Screen 50/50 Layout

**Files:**
- Modify: `custom-addons/aidt_base/views/aidt_login_templates.xml`

**Interfaces:**
- Consumes: Odoo `web.login_layout`
- Produces: Full-screen 50/50 split view login page

- [ ] **Step 1: Update `aidt_login_templates.xml` with full-screen split layout**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Deactivate website.login_layout view if website module is installed -->
    <record id="website.login_layout" model="ir.ui.view">
        <field name="active" eval="False"/>
    </record>

    <!-- Override web.login_layout with Full-Screen 50/50 Red Login Layout -->
    <template id="aidt_login_layout_override" inherit_id="web.login_layout" priority="99" name="AIDT Full-Screen 2-Column Red Login Layout">
        <xpath expr="//div[hasclass('container')]" position="replace">
            <div class="container-fluid min-vh-100 p-0 m-0 overflow-hidden bg-white aidt-login-split-view">
                <div class="row g-0 min-vh-100">
                    <!-- Left Column: Branding Panel (Traditional Party Red 50%) -->
                    <div class="col-12 col-md-6 p-4 p-lg-5 text-white d-flex flex-column justify-content-between min-vh-100"
                         style="background: linear-gradient(145deg, #7A0C0D 0%, #4A0809 100%); border-right: 2px solid #D4AF37;">
                        <div class="my-auto">
                            <div class="mb-4 d-flex align-items-center gap-3">
                                <div class="rounded-circle d-flex align-items-center justify-content-center shadow"
                                     style="width: 60px; height: 60px; background: #D4AF37; color: #7A0C0D;">
                                    <i class="fa fa-star fa-2x" aria-hidden="true"/>
                                </div>
                                <div>
                                    <h4 class="mb-0 text-warning fw-bold text-uppercase" style="letter-spacing: 1px;">Văn phòng Cấp ủy</h4>
                                    <small class="text-white-50">Hệ thống Hành chính Điện tử</small>
                                </div>
                            </div>
                            <h2 class="fw-bold text-white mb-3 display-6">HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY</h2>
                            <p class="text-white-50 lead fs-6 mb-4">Giải pháp quản lý văn bản, bút phê, theo dõi nhiệm vụ và lịch công tác tập trung.</p>
                            
                            <div class="d-flex flex-column gap-3 mb-4">
                                <div class="d-flex align-items-start gap-2 fs-6">
                                    <i class="fa fa-check-circle text-warning mt-1"/>
                                    <span>Quản lý Văn bản đến &amp; Bút phê giao việc tức thì</span>
                                </div>
                                <div class="d-flex align-items-start gap-2 fs-6">
                                    <i class="fa fa-check-circle text-warning mt-1"/>
                                    <span>Theo dõi Nhiệm vụ toàn đơn vị 4 cấp trạng thái</span>
                                </div>
                                <div class="d-flex align-items-start gap-2 fs-6">
                                    <i class="fa fa-check-circle text-warning mt-1"/>
                                    <span>Lịch công tác tuần &amp; Đăng ký hẹn làm việc công dân</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="pt-3 border-top border-white-10 text-white-50 small mt-auto">
                            <i class="fa fa-shield me-1 text-warning"/> Bảo mật • Thông suốt • Hiệu quả
                        </div>
                    </div>
                    
                    <!-- Right Column: Odoo Login Form Panel (50%) -->
                    <div class="col-12 col-md-6 p-4 p-lg-5 bg-white d-flex flex-column justify-content-center min-vh-100">
                        <div class="w-100 mx-auto" style="max-width: 420px;">
                            <div class="text-center mb-4">
                                <img t-attf-src="/web/binary/company_logo{{ '?dbname='+db if db else '' }}" alt="Logo" style="max-height:90px; max-width: 100%; width:auto"/>
                                <h4 class="fw-bold text-dark mt-3 mb-1">Đăng nhập Hệ thống</h4>
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

- [ ] **Step 2: Commit**

```bash
git add custom-addons/aidt_base/views/aidt_login_templates.xml
git commit -m "feat(base): update login template to full-screen 50/50 split view"
```

---

### Task 2: Upgrade Module & Verify Full-Screen Layout

**Files:**
- Test: `custom-addons/aidt_base/tests/test_login_layout.py`

- [ ] **Step 1: Upgrade `aidt_base` and run unit test in Docker container**

Run:
```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin -c /etc/odoo/odoo.conf -d aidt -u aidt_base --test-enable --test-tags=TestLoginLayout --stop-after-init --http-port=8079 && docker restart aidt-odoo-dev-odoo-1
```
Expected: PASS (0 failed, 0 errors)

- [ ] **Step 2: Commit**

```bash
git add custom-addons/aidt_base/tests/test_login_layout.py
git commit -m "test(base): verify full-screen 50/50 split view login page"
```
