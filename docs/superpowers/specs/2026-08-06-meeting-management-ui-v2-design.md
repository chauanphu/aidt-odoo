# Meeting Management UI V2 Design Spec

## 1. Overview
The current UI for the Meeting Management module (`aidt.meeting.recording`) is constrained by Odoo's default `<sheet>` container, making the tables hard to read and the layout cramped. This spec defines a complete "Premium" refactor using modern web aesthetics (Glassmorphism, soft shadows) and an immersive full-width layout.

## 2. Architecture & Layout
- **Full-Width Container**: Replace Odoo's standard `<sheet>` with a custom `<div class="premium-dashboard-container">`. This overrides Odoo's default `max-width`, allowing the interface to span the full screen.
- **Top KPI Row**: 3 Metric Cards (Started At, Secrecy, Started By) distributed evenly across the top.
- **Main Content Split**: A 50/50 vertical split (`col-md-6` instead of the previous `col-md-8` and `col-md-4`).
  - **Left Column**: Event details, overview, and the full transcript notebook.
  - **Right Column**: Action Items (Công việc) and Decisions (Quyết định) tables. Given the 50% width on a full screen, these tables will be significantly larger and easier to read.

## 3. Premium Aesthetics (Glassmorphism)
- **Cards**: Remove the flat background and colored top-borders (`border-top`). Instead, apply a glassmorphism effect:
  - `background: rgba(255, 255, 255, 0.6);`
  - `backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);`
  - `border: 1px solid rgba(255, 255, 255, 0.4);`
  - `border-radius: 20px;`
- **Shadows**: Implement deep, soft shadows for depth: `box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.08);`.
- **Typography**: Utilize the `Inter` font for all dashboard text. Metric titles will use `font-weight: 600` with subtle letter-spacing.

## 4. Interactions & Micro-Animations
- **Hover States**: 
  - Cards will subtly scale up (`transform: translateY(-2px)`) and intensify their shadow on hover.
  - Table rows inside "Action Items" and "Decisions" will have a soft highlight effect (`background-color: rgba(99, 102, 241, 0.05)`) when hovered.
- **Transitions**: All interactive state changes must be smoothed with `transition: all 0.25s ease-in-out;`.

## 5. Implementation Notes
- **Odoo Form View constraints**: Odoo handles `readonly` fields inside `<form>` elements. We must ensure the DOM structure inside our custom `premium-dashboard-container` still properly renders Odoo's `<field>` widgets.
- **CSS Scope**: All new styles will be scoped within `.premium-dashboard-container` to avoid leaking into other Odoo views.
