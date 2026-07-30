# Design Spec: Role-Based Access Control & Form Readonly Protection

## Overview
This document specifies the design for **Role-Based Access Control (RBAC)** and **Form Readonly Protection** for Document Management (`aidt.document`) across `custom-addons/aidt_vanban_den` and `custom-addons/aidt_vanban_di` in Odoo 19.

The goal is to enforce strict role-based button visibility and form field editability so that each user role (*Chuyên viên*, *Trưởng phòng*, *Văn thư*, *Chánh Văn phòng*, *Phó Bí thư*, *Bí thư*) can only see and execute actions appropriate to their position, and document fields are locked against unauthorized editing once submitted.

## Key Requirements & Security Mapping

### 1. Security Groups Reference (`addons/aidt_org/security/aidt_org_groups.xml`)
- `aidt_org.group_chuyen_vien` (Chuyên viên)
- `aidt_org.group_truong_phong` (Trưởng phòng)
- `aidt_org.group_van_thu` (Văn thư)
- `aidt_org.group_chanh_vp` (Chánh Văn phòng / Trưởng đơn vị)
- `aidt_org.group_pho_bi_thu` (Phó Bí thư)
- `aidt_org.group_bi_thu` (Bí thư)
- `aidt_org.group_aidt_admin` (Quản trị hệ thống)

### 2. Header Buttons Control (`vanban_den_views.xml` & `vanban_di_views.xml`)
- **Incoming Documents (`aidt_vanban_den`)**:
  - `action_register` ([Cấp số đến]): `groups="aidt_org.group_van_thu,aidt_org.group_aidt_admin"`
  - `action_submit_leader` ([Trình lãnh đạo]): `groups="aidt_org.group_van_thu,aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
  - `action_but_phe` ([Bút phê + Giao việc]): `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
  - `action_complete` ([Duyệt hoàn thành]): `groups="aidt_org.group_chanh_vp,aidt_org.group_bi_thu,aidt_org.group_aidt_admin"`

- **Outgoing Documents (`aidt_vanban_di`)**:
  - `action_submit_tp` ([Trình Trưởng phòng]): `groups="aidt_org.group_chuyen_vien,aidt_org.group_aidt_admin"`
  - `action_approve_tp` ([TP Duyệt]): `groups="aidt_org.group_truong_phong,aidt_org.group_aidt_admin"`
  - `action_reject_tp` ([TP Trả về]): `groups="aidt_org.group_truong_phong,aidt_org.group_aidt_admin"`
  - `action_approve_cvp` ([CVP Duyệt]): `groups="aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
  - `action_reject_cvp` ([CVP Trả về]): `groups="aidt_org.group_chanh_vp,aidt_org.group_aidt_admin"`
  - `action_approve_lanh_dao` ([Lãnh đạo Duyệt]): `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_aidt_admin"`
  - `action_reject_lanh_dao` ([Lãnh đạo Trả về]): `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_aidt_admin"`
  - `action_sign` ([Ký số]): `groups="aidt_org.group_bi_thu,aidt_org.group_pho_bi_thu,aidt_org.group_aidt_admin"`
  - `action_issue_vbd` ([Cấp số & Ban hành]): `groups="aidt_org.group_van_thu,aidt_org.group_aidt_admin"`

### 3. Model Action Level Role Checks (Python Layer)
In Python action methods (`action_but_phe`, `action_sign`, `action_register`, `action_issue_vbd`, etc.):
- Raise `UserError` if the current user does not belong to the allowed security group.
- Ensures backend security even if an API or custom script attempts to invoke the method directly.

### 4. Form Field Readonly Protection
- General document fields (`name`, `secrecy`, `doc_type`, `co_quan_gui`, `so_ky_hieu_gui`, `nguoi_soan_id`, `template_id`) get `readonly="state not in ('draft', 'tiep_nhan')"`.
- Bút phê fields (`lanh_dao_but_phe_id`, `don_vi_chu_tri_id`, `don_vi_phoi_hop_ids`, `y_kien_but_phe`, `han_xu_ly`) get `readonly="state != 'trinh_lanh_dao'"`.

## Verification & Testing
- Unit test `test_document_role_permissions.py` in `custom-addons/aidt_vanban_den/tests/`:
  - Validates that a user with only `group_chuyen_vien` cannot invoke `action_but_phe` or `action_sign`.
  - Validates that a user with `group_bi_thu` can successfully execute `action_but_phe` and `action_sign`.
  - Validates that a user with `group_van_thu` can execute `action_register` and `action_issue_vbd`.
