# Design Spec: Full-Screen 50/50 Split View Login Page (`aidt_base`)

## Overview
This design spec defines a true full-screen 50/50 split-view login page for AIDT in `custom-addons/aidt_base`. It eliminates floating card boxes, outer margins, rounded borders, and background shadows, spanning 100% viewport width (`100vw`) and 100% viewport height (`100vh`).

## 1. Aesthetic Theme & Full-Screen Layout
- **Layout**: 100% Viewport Height & Width (`min-vh-100 w-100 m-0 p-0 overflow-hidden`) split into two equal 50% columns on medium+ screens (`col-12 col-md-6`).
- **No Card Enclosure**: Removes floating card containers, outer margins, borders, and shadows.

### Left 50% Column: Traditional Party Red Branding Panel (`col-12 col-md-6 min-vh-100`)
- **Background**: Solid Gradient `#7A0C0D` ➔ `#4A0809` (Traditional Party Red) covering 100% height and 50% screen width.
- **Divider**: Subtle vertical gold border (`border-end: 2px solid #D4AF37`).
- **Content**:
  - Gold star emblem badge (`#D4AF37`).
  - Title: **HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY**
  - Subtitle: *Văn phòng Cấp ủy - Hệ thống Hành chính Điện tử*
  - 3 Feature bullet cards with gold check icons.
  - Bottom security note: *Bảo mật • Thông suốt • Hiệu quả*.

### Right 50% Column: Full-Height Clean Login Panel (`col-12 col-md-6 min-vh-100 bg-white`)
- **Background**: Pure White (`#FFFFFF`).
- **Content**: Centered Odoo Login Form inside a responsive flex container (`d-flex align-items-center justify-content-center h-100 p-4 p-lg-5`).
- **Preserved Odoo Features**:
  - Company logo image `/web/binary/company_logo`
  - All form fields (`login`, `password`, `csrf_token`, `redirect`, `type`)
  - Error and status alerts (`error`, `message`)
  - Submit button (**Đăng nhập**)
  - Database Manager link

## 2. Technical Implementation Details
- **Target File**: `custom-addons/aidt_base/views/aidt_login_templates.xml`
- **Inheritance**: `web.login_layout` (`priority="99"`) with `website.login_layout` deactivation (`active="False"`).
- **CSS Utility Classes**: Pure Bootstrap 5 classes (`min-vh-100`, `row g-0`, `col-md-6`) for seamless responsiveness across desktop, tablet, and mobile screens.

## 3. Verification Plan
1. Upgrade `aidt_base` module via Docker command.
2. Open browser in incognito mode at `http://localhost:8069/web/login`.
3. Verify full-screen 50/50 split layout (Left 50% red branding, Right 50% white login form, no card borders or outer background gaps).
4. Perform test login with `cv.tonghop1` / `demo2026`.
