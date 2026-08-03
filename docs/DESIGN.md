# AIDT Enterprise Design System (Academic Premium & SaaS Clean UI)

> **Specification & Guidelines cho tất cả Addons thuộc hệ thống AIDT Odoo**  
> *Được trích xuất và chuẩn hóa từ Addon mẫu: `aidt_dashboard_builder`*

---

## 📌 1. Triết lý Thiết kế (Design Philosophy)

Hệ thống giao diện AIDT được xây dựng dựa trên sự kết hợp giữa **Academic Premium (Chuẩn mực Học thuật & Cơ quan Nhà nước)** và **SaaS Clean UI (Hiện đại, Tối giản, Trực quan)**:

1. **Trực quan & Đẳng cấp**: Sử dụng bảng màu phối hợp hài hòa (Slate Grays kết hợp với các Accent Color nhẹ nhàng), tránh sử dụng màu sắc nguyên bản thô ráp (như pure red, green, blue).
2. **Typography Rõ ràng**: Số liệu thống kê, KPI và mã định danh bắt buộc dùng font **Monospace** (`JetBrains Mono`). Chữ giao diện dùng font **Inter** hiện đại.
3. **Phân cấp Thẻ (Card Elevation)**: Thẻ nội dung có viền mỏng `#E2E8F0`, góc bo tròn lớn (`14px` – `22px`), hiệu ứng đổ bóng siêu nhẹ (`shadow-xs` / `shadow-sm`) và hiệu ứng float khi hover (`translateY(-2px)`).
4. **Viền Tròn & Icon Roundel**: Mọi icon đại diện loại dữ liệu đều được bọc trong một huy hiệu hình vuông bo tròn (**Widget Icon Roundel** `38px x 38px`) với nền nhạt matching màu chủ đề.

---

## 🎨 2. Design Tokens & Bảng màu (Color Palette)

### 2.1 Bảng màu Chủ đạo (Brand & System Colors)

```css
:root {
    /* Brand & Accent Colors */
    --dash-hutech-blue: #005b9a;        /* Xanh HUTECH / Xanh Văn phòng Tỉnh ủy */
    --dash-saas-blue: #2563EB;          /* Xanh SaaS hiện đại */
    --dash-purple: #714B67;             /* Tím Odoo Enterprise / Filter Accent */
    --dash-purple-hover: #5d3d54;
    --dash-purple-light: rgba(113, 75, 103, 0.08);
    --dash-purple-glow: rgba(113, 75, 103, 0.25);
    --dash-teal: #00A09D;               /* Xanh Ngọc Bảo */

    /* Slate System Scale (Nền & Chữ) */
    --dash-slate-50: #F8FAFC;          /* Canvas Background */
    --dash-slate-100: #F1F5F9;         /* Table Header / Badge Bg */
    --dash-slate-200: #E2E8F0;         /* Card Border Default */
    --dash-slate-300: #CBD5E1;         /* Hover Border */
    --dash-slate-400: #94A3B8;         /* Subtitle / Icon Muted */
    --dash-slate-500: #64748B;         /* Secondary Text */
    --dash-slate-600: #475569;         /* Table Header Text */
    --dash-slate-700: #334155;         /* Card Title Text */
    --dash-slate-800: #1E293B;         /* Heading Dark Text */
    --dash-slate-900: #0F172A;         /* Primary Dark Text */

    /* Canvas & Cards */
    --dash-bg-light: #F8FAFC;
    --dash-card-bg: #FFFFFF;
    --dash-border: #E2E8F0;

    /* Border Radius Scale */
    --dash-radius-sm: 10px;
    --dash-radius-md: 14px;            /* Nút bấm, Filter Chip, Icon Roundel */
    --dash-radius-lg: 18px;            /* Sub-container */
    --dash-radius-xl: 22px;            /* Dashboard KPI & Chart Card */
    --dash-radius-2xl: 28px;           /* Modal / Large Banner */

    /* Glassmorphism */
    --dash-glass-bg: rgba(255, 255, 255, 0.85);
    --dash-glass-blur: 16px;
}
```

---

### 2.2 Quy chuẩn Phối màu theo Chủ đề (Color Theme Mapping)

Mỗi chỉ số KPI hoặc Widget bắt buộc gắn liền với một **Theme Color** duy nhất để tạo sự phân biệt thị giác:

| Theme Name | Icon Roundel Bg | Icon & Border Color | Value Text Color | Trường hợp sử dụng tiêu biểu |
| :--- | :--- | :--- | :--- | :--- |
| `theme-primary` | `#E6F0F7` | `#005B9A` / `#CBE0F0` | `#005B9A` | Tổng số Văn bản đến, Lịch tuần |
| `theme-success` | `#ECFDF5` | `#10B981` / `#A7F3D0` | `#059669` | Văn bản đã ban hành, Hoàn thành |
| `theme-warning` | `#FFFBEB` | `#F59E0B` / `#FDE68A` | `#D97706` | Chờ bút phê, Chờ xử lý |
| `theme-danger` | `#FFF1F2` | `#F43F5E` / `#FECDD3` | `#E11D48` | Văn bản Mật/Tối mật, Khẩn cấp |
| `theme-info` | `#F0F9FF` | `#0284C7` / `#BAE6FD` | `#0284C7` | Nhiệm vụ đang thực hiện |
| `theme-teal` | `#ECFEFF` | `#06B6D4` / `#A5F3FC` | `#0891B2` | Phân tích Thống kê, Báo cáo |
| `theme-rose` | `#FDF2F8` | `#EC4899` / `#FBCFE8` | `#DB2777` | Đơn thư Tiếp dân, Kiến nghị |
| `theme-dark` | `#F1F5F9` | `#334155` / `#CBD5E1` | `#1E293B` | Lưu trữ lịch sử, Cấu hình |

---

## 🔤 3. Quy chuẩn Font chữ (Typography System)

1. **Font Chữ Giao diện Chi tiết**:
   - Bắt buộc khai báo: `'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
2. **Font Chữ Số liệu & KPI Monospace**:
   - Bắt buộc khai báo: `'JetBrains Mono', 'Roboto Mono', 'SFMono-Regular', Consolas, monospace`
3. **Phân cấp Font**:
   - **Tên Dashboard / Tiêu đề lớn**: `font-size: 1.1rem`, `font-weight: 700`, `color: #0F172A`.
   - **Tiêu đề KPI Card (`.kpi-title`)**: `font-size: 0.825rem` (`13px`), `font-weight: 700`, `text-transform: uppercase`, `letter-spacing: 0.04em`, `color: #334155`.
   - **Con số KPI (`.kpi-value`)**: `font-size: 2.2rem`, `font-weight: 900`, `font-family: JetBrains Mono`, `line-height: 1.1`.
   - **Header Bảng (`th`)**: `font-size: 11px`, `font-weight: 700`, `text-transform: uppercase`, `letter-spacing: 0.05em`, `color: #475569`, `background: #F1F5F9`.
   - **Dòng Bảng (`td`)**: `font-size: 0.85rem`, `font-weight: 600`, `color: #0F172A`.

---

## 🧩 4. Quy chuẩn Component UI Chuẩn (UI Components)

### 4.1 Thẻ KPI (KPI Metric Card)

![KPI Card Layout Pattern](https://img.shields.io/badge/Pattern-KPI_Card-005b9a)

```html
<div class="o_dashboard_card kpi-card theme-primary dash-animate-in">
    <div class="kpi-header d-flex align-items-center justify-content-between">
        <span class="kpi-title">TỔNG VĂN BẢN ĐẾN</span>
        <div class="widget-icon-roundel">
            <i class="fa fa-inbox"></i>
        </div>
    </div>
    <div class="d-flex align-items-end justify-content-between mt-3">
        <div class="kpi-value">22</div>
        <button class="btn btn-sm btn-outline-secondary rounded-pill px-3 fs-7">
            <i class="fa fa-external-link me-1"></i>Xem
        </button>
    </div>
</div>
```

---

### 4.2 Thanh Bộ Lọc Thời Gian (Filter Bar & Pills)

Thanh lọc thời gian dạng Pill bo tròn 20px đặt ngay bên dưới Header Dashboard:

```html
<div class="o_dashboard_filter_bar d-flex align-items-center gap-2 p-3 bg-white border-bottom">
    <span class="fw-bold text-slate-700 fs-7 me-2"><i class="fa fa-calendar me-1"></i>Thời gian:</span>
    <button class="btn btn-sm dash-pill-active rounded-pill px-3">Tất cả</button>
    <button class="btn btn-sm dash-pill-inactive rounded-pill px-3">Hôm nay</button>
    <button class="btn btn-sm dash-pill-inactive rounded-pill px-3">Tuần này</button>
    <button class="btn btn-sm dash-pill-inactive rounded-pill px-3">Tháng này</button>
    <button class="btn btn-sm dash-pill-inactive rounded-pill px-3">Quý này</button>
    <button class="btn btn-sm dash-pill-inactive rounded-pill px-3">Năm nay</button>
</div>
```

---

### 4.3 Bảng Dữ liệu Đơn giản (Clean Data Table Card)

Bảng hiển thị thông tin danh sách mới nhất (Văn bản mới, Lịch sắp tới, Task chờ xử lý):

```html
<div class="o_dashboard_card table-card">
    <div class="d-flex align-items-center justify-content-between mb-3">
        <div class="d-flex align-items-center gap-2">
            <div class="widget-icon-roundel theme-info">
                <i class="fa fa-table"></i>
            </div>
            <h6 class="table-title mb-0">Danh sách Văn bản Mới nhất</h6>
        </div>
        <a href="#" class="btn btn-sm btn-link text-decoration-none fw-bold fs-7">Xem tất cả &rarr;</a>
    </div>
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead>
                <tr>
                    <th>TRÍCH YẾU</th>
                    <th>SỐ/KÝ HIỆU</th>
                    <th>LOẠI VĂN BẢN</th>
                    <th>TRẠNG THÁI</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="fw-bold">Công văn hướng dẫn lập hồ sơ lưu trữ...</td>
                    <td>12/HD-VP</td>
                    <td><span class="badge bg-light text-dark border">cong_van</span></td>
                    <td><span class="badge bg-success-subtle text-success border border-success-subtle">Đã ban hành</span></td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
```

---

## ⚡ 5. Hiệu ứng Chuyển động (Animations & Micro-interactions)

Mọi giao diện thuộc hệ thống AIDT phải tuân thủ hiệu ứng động mượt mà (Natural Motion):

1. **Hiệu ứng vào trang (Entrance Animation)**:
   - Các card xuất hiện dùng `@keyframes dashFadeInUp` (`translateY(18px)` -> `translateY(0)`).
   - Stagger delay cho từng cột: `animation-delay: 0.03s * n`.
2. **Hiệu ứng Hover Card**:
   - `transition: border-color 0.2s ease, box-shadow 0.2s ease;`
   - Đổi màu border từ `#E2E8F0` sang `#CBD5E1`.
   - Đổ bóng nhẹ `0 4px 12px rgba(15, 23, 42, 0.06)`.
3. **Nút bấm Refresh / Reload**:
   - Icon xoay tròn linh hoạt `@keyframes dashSpinRefresh` khi dữ liệu đang tải.

---

## 🛠 6. Hướng dẫn Tích hợp vào Addon Mới (`aidt_*`)

Để một Addon mới (như `aidt_calendar`, `aidt_vanban_den`, `aidt_task`, `aidt_dms`) đồng bộ 100% giao diện với `aidt_dashboard_builder`:

1. **Import file SCSS**: Trong asset bundle `web.assets_backend` của addon mới, import hoặc bao bọc các class CSS theo các biến `--dash-*`.
2. **Sử dụng đúng CSS Class Structure**:
   - Container ngoài cùng: `.o_dashboard_viewer_container`
   - Header bar: `.o_dashboard_header`
   - Card chính: `.o_dashboard_card` + Theme Class (`theme-primary`, `theme-success`, ...)
   - Icon badge: `.widget-icon-roundel`
   - Monospace text: `.kpi-value`
3. **Thân thiện với Mobile**: Đảm bảo sử dụng `clamp()` cho font-size và padding để tự động co giãn đẹp mắt trên tablet và mobile.

---
*Hệ thống Thiết kế chuẩn AIDT Odoo Enterprise 19.0 — Ban Cơ yếu & Văn phòng Tỉnh ủy*
