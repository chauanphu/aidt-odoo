# Design Spec: Custom 2-Column Traditional Red Login View (`aidt_base`)

## Overview
This design spec outlines the custom 2-column split-view login page for the AIDT application in `custom-addons/aidt_base`. The custom login page replaces the standard centered Odoo card layout while retaining 100% of the underlying Odoo authentication logic, CSRF tokens, fields, error messages, and actions.

## 1. Aesthetic Theme & Palette
- **Primary Theme**: Traditional Party & Executive Red (*Tone Đỏ Truyền thống Cấp ủy*)
- **Background Gradient (Left Column)**: `#7A0C0D` ➔ `#4A0809` (Rich Deep Crimson Red)
- **Accent Color**: Gold / Brass (`#D4AF37`) for emblem borders, badges, and highlights
- **Right Column Background**: `#F8F9FA` (Soft Light Gray) with pure white login card container

## 2. Layout Structure (2-Column Split View)
- **Container**: Full-height viewport wrapper (`min-vh-100 d-flex align-items-center justify-content-center py-4 py-md-0`)
- **Main Card Box**: 2-column Bootstrap grid container (`row g-0 rounded-4 overflow-hidden shadow-lg w-100 mx-3`) with max-width `1000px`.

### Left Column: Branding & Intro Panel (`col-12 col-md-6 p-4 p-lg-5 text-white`)
- **Header**:
  - Party Emblem / Logo Badge with gold border ring.
  - Heading 1 (`h2 text-warning fw-bold mb-2`): **HỆ THỐNG VĂN PHÒNG ĐIỆN TỬ CẤP ỦY**
  - Subtitle (`p text-white-50 small mb-4`): *Đơn vị Cấp ủy & Hành chính Công*
- **Feature Highlights List**:
  1. 📄 **Quản lý Văn bản Đến & Văn bản Đi**: Luồng bút phê, cấp số và ban hành văn bản tức thì.
  2. 🎯 **Theo dõi Nhiệm vụ & Tiến độ**: Theo dõi 4 trạng thái nhiệm vụ toàn đơn vị.
  3. 📅 **Lịch công tác Tuần & Lịch hẹn**: Lịch làm việc Thường trực và đăng ký hẹn làm việc công dân.
- **Footer Note**: *Bảo mật - Thông suốt - Hiệu quả*.

### Right Column: Odoo Login Form Container (`col-12 col-md-6 p-4 p-lg-5 bg-white border-start`)
- Wraps the existing Odoo `web.login` form:
  - Form action `/web/login`
  - Hidden inputs (`csrf_token`, `type`, `redirect`)
  - Email / Username field (`login`)
  - Password field (`password`) with CapsLock warning and toggle show password
  - Error and success alerts (`error`, `message`)
  - Submit button (**Đăng nhập**)
  - Footer links (Database manager link if enabled)

## 3. Technical Implementation Details
- **Target File**: `custom-addons/aidt_base/views/aidt_login_templates.xml`
- **Inheritance Target**: `web.login_layout` template
- **Manifest Integration**: Add `views/aidt_login_templates.xml` to `custom-addons/aidt_base/__manifest__.py` under `data`.
- **Backward Compatibility**: Fully preserves all form IDs, input names, CSRF validation, and RPC error handling.

## 4. Verification Plan
1. Upgrade `aidt_base` module via Docker command.
2. Open browser at `http://localhost:8069/web/login`.
3. Verify 2-column responsive layout (Left column red branding, Right column login form).
4. Perform successful login with `cv.tonghop1` / `demo2026`.
5. Verify incorrect credentials raise standard red alert error.
