# Meeting Management UI Design Spec
Date: 2026-08-06

## 1. Overview
The goal of this design is to upgrade the standard Odoo Form View of the `aidt.meeting.recording` model to adhere to the **AIDT Enterprise Design System (Academic Premium & SaaS Clean UI)**. The new UI will transform the basic form into a multi-dimensional Dashboard layout.

## 2. Architecture & Approach
We will use **CSS Injection + XML Layout Rework (Approach 1)**.
- Modifying the existing Odoo XML Form View (`views/meeting_recording_views.xml`).
- Creating a new SCSS file (`static/src/scss/meeting_dashboard.scss`) loaded into `web.assets_backend`.
- This approach avoids the complexity of building a fully custom OWL component from scratch, while achieving 90%+ visual parity with the design system.

## 3. Layout Structure
The Form View `<sheet>` will be converted into a dashboard layout using Bootstrap grid classes (`<div class="row">`, `col-md-X`):

1. **Top Row (KPIs):**
   - **Duration / Time:** `theme-primary`, icon: `fa-clock-o`
   - **Secrecy Level:** `theme-danger`, icon: `fa-lock` (only if secret)
   - **AI Status:** `theme-success` or `theme-warning`, icon: `fa-robot`
2. **Main Content Column (Left, 65% width):**
   - Glassmorphism Card (`o_dashboard_card theme-primary`)
   - Contains: Overview, Transcript (Bản bóc băng), Key points, Risks.
3. **Action & Decisions Column (Right, 35% width):**
   - Glassmorphism Card (`o_dashboard_card table-card theme-warning`)
   - Contains: Action Items (Công việc), Decisions (Quyết định) in list format.

## 4. UI/UX Elements & Styling
Following `docs/DESIGN.md`:
- **Classes:** `o_dashboard_viewer_container`, `o_dashboard_card`, `kpi-card`, `widget-icon-roundel`.
- **Micro-animations:** Hover float (`translateY(-2px)`) with shadow transitions.
- **Typography:**
  - Standard text: `Inter`.
  - Numeric/KPIs: `JetBrains Mono`.
- **Colors:**
  - Primary Backgrounds: Slate scale (`#F8FAFC`, `#E2E8F0`).
  - Accents: `theme-primary` (Blue), `theme-warning` (Amber/Orange).

## 5. Scope & Constraints
- Modifies ONLY the Form View of `aidt.meeting.recording`.
- Retains all existing fields, buttons (Dừng ghi âm, Tổng hợp AI), and state mechanics.
- No changes to the backend AI models (Whisper/Gemma) or recording mechanism.
