/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { widgetRegistry } from "../services/widget_registry";
import { WidgetLibrarySidebar } from "../components/widget_library_sidebar";
import { DashboardFilterBar } from "../components/dashboard_filter_bar";

function ensureChartJSLoaded() {
    if (window.Chart) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        const existingScript = document.querySelector('script[src*="chart.js"]');
        if (existingScript) {
            existingScript.addEventListener('load', () => resolve());
            setTimeout(resolve, 1500);
            return;
        }
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/chart.js";
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
        setTimeout(resolve, 2000);
    });
}

function ensureGridStackLoaded() {
    if (window.GridStack) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        const existingScript = document.querySelector('script[src*="gridstack"]');
        if (existingScript) {
            existingScript.addEventListener('load', () => resolve());
            setTimeout(resolve, 1500);
            return;
        }

        if (!document.querySelector('link[href*="gridstack"]')) {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = "https://cdn.jsdelivr.net/npm/gridstack@10.3.1/dist/gridstack.min.css";
            document.head.appendChild(link);
        }

        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/gridstack@10.3.1/dist/gridstack-all.js";
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
        setTimeout(resolve, 2500);
    });
}

export class DashboardViewerAction extends Component {
    static template = "aidt_dashboard_builder.DashboardViewerAction";
    static components = { WidgetLibrarySidebar, DashboardFilterBar };

    setup() {
        this.action = useService("action");
        this.onDrilldown = this.onDrilldown.bind(this);
        this.onWindowResize = this.onWindowResize.bind(this);
        this.onDocumentClick = this.onDocumentClick.bind(this);
        this.onDatePillChange = this.onDatePillChange.bind(this);
        this.onAddPresetWidget = this.onAddPresetWidget.bind(this);
        this.toggleSidebar = this.toggleSidebar.bind(this);
        this.onExportExcel = this.onExportExcel.bind(this);
        this.resizeTimeout = null;
        this.gridStackInstance = null;
        this.viewGridStackInstance = null;

        this.state = useState({
            loading: true,
            dashboardId: this.props.action.params?.dashboard_id || 0,
            dashboardName: "Dashboard",
            availableDashboards: [],
            pages: [],
            filters: [],
            activePageId: 0,
            widgetData: {},
            filterValues: {},
            error: null,
            dropdownOpen: false,
            editMode: false,
            hasCustomLayout: false,
            savingLayout: false,
            editedWidgets: [],
            sidebarOpen: false,
            activeFilterPill: 'all',
            isMobile: window.innerWidth < 768,
            isTablet: window.innerWidth >= 768 && window.innerWidth < 992,
            windowWidth: window.innerWidth,
        });

        onWillStart(async () => {
            await ensureChartJSLoaded();
            await this.loadDashboardList();
            await this.loadDashboardData();
        });

        onMounted(() => {
            window.addEventListener('resize', this.onWindowResize);
            document.addEventListener('click', this.onDocumentClick);
        });

        onWillUnmount(() => {
            window.removeEventListener('resize', this.onWindowResize);
            document.removeEventListener('click', this.onDocumentClick);
            if (this.resizeTimeout) {
                clearTimeout(this.resizeTimeout);
            }
            if (this.viewGridStackInstance) {
                try { this.viewGridStackInstance.destroy(false); } catch (e) {}
            }
            if (this.gridStackInstance) {
                try { this.gridStackInstance.destroy(false); } catch (e) {}
            }
        });
    }

    onDocumentClick(ev) {
        if (this.state.dropdownOpen) {
            const dropdownEl = document.querySelector('.dashboard-dropdown');
            if (dropdownEl && !dropdownEl.contains(ev.target)) {
                this.state.dropdownOpen = false;
            }
        }
    }

    onWindowResize() {
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        this.resizeTimeout = setTimeout(async () => {
            const currentWidth = window.innerWidth;
            const wasMobile = this.state.isMobile;
            this.state.windowWidth = currentWidth;
            this.state.isMobile = currentWidth < 768;
            this.state.isTablet = currentWidth >= 768 && currentWidth < 992;

            if (wasMobile !== this.state.isMobile) {
                if (this.state.editMode) {
                    this.initGridStack();
                } else {
                    await this.renderViewGridStack();
                }
            }
        }, 200);
    }

    get currentDashboardName() {
        const found = (this.state.availableDashboards || []).find(d => d.id === this.state.dashboardId);
        return found ? found.name : (this.state.dashboardName || "Chọn Dashboard");
    }

    toggleDropdown(ev) {
        if (ev) ev.stopPropagation();
        this.state.dropdownOpen = !this.state.dropdownOpen;
    }

    async selectDashboard(id) {
        this.state.dropdownOpen = false;
        const selectedId = Number(id);
        if (selectedId && selectedId !== this.state.dashboardId) {
            this.state.dashboardId = selectedId;
            this.state.activePageId = 0;
            this.state.editMode = false;
            await this.loadDashboardData(true);
        }
    }

    async loadDashboardList() {
        try {
            const res = await rpc("/dashboard/api/list", {});
            if (res && res.status === "success") {
                this.state.availableDashboards = res.dashboards || [];
            }
        } catch (err) {
            console.error("Lỗi khi tải danh sách Dashboard:", err);
        }
    }

    get isAccessDenied() {
        if (this.state.error && (
            this.state.error.includes("Access Denied") ||
            this.state.error.includes("not allowed") ||
            this.state.error.includes("quyền") ||
            this.state.error.includes("Quyền")
        )) {
            return true;
        }
        if (!this.state.loading && (!this.state.availableDashboards || this.state.availableDashboards.length === 0)) {
            return true;
        }
        return false;
    }

    async loadDashboardData(forceRefresh = false) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const res = await rpc("/dashboard/api/data", {
                dashboard_id: Number(this.state.dashboardId),
                filter_values: this.state.filterValues,
                force_refresh: forceRefresh,
            });

            if (res && res.status === "success") {
                this.state.dashboardId = res.dashboard_id || this.state.dashboardId;
                this.state.dashboardName = res.dashboard_name || "Dashboard";
                this.state.hasCustomLayout = res.has_custom_layout || false;
                this.state.pages = res.pages || [];
                this.state.filters = res.filters || [];
                if (this.state.pages.length > 0 && !this.state.activePageId) {
                    this.state.activePageId = this.state.pages[0].id;
                }
                this.state.widgetData = res.data || {};
                const now = new Date();
                this.state.lastUpdated = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

                await this.renderViewGridStack();
            } else if (res && res.status === "access_denied") {
                this.state.error = res.message || "Tài khoản của bạn chưa được phân quyền xem Dashboard này.";
            } else {
                this.state.error = (res && res.message) ? res.message : "Tài khoản của bạn chưa được phân quyền xem Dashboard này.";
            }
        } catch (err) {
            this.state.error = err.message || "Tài khoản của bạn chưa được phân quyền xem Dashboard này.";
        } finally {
            this.state.loading = false;
        }
    }

    async renderViewGridStack() {
        if (this.state.editMode) return;
        await ensureGridStackLoaded();
        setTimeout(() => {
            const gridEl = document.querySelector('.grid-stack-view-canvas');
            if (!gridEl || !window.GridStack) return;

            if (this.viewGridStackInstance) {
                try { this.viewGridStackInstance.destroy(false); } catch (e) {}
            }

            const isMobile = window.innerWidth < 768;
            this.viewGridStackInstance = window.GridStack.init({
                staticGrid: true,
                float: true,
                cellHeight: isMobile ? 105 : 115,
                column: 12,
                margin: 0,
                animate: true,
                disableOneColumnMode: !isMobile
            }, gridEl);

            // Stagger entrance animation for grid items
            const items = gridEl.querySelectorAll('.grid-stack-item');
            items.forEach((el, idx) => {
                el.style.animationDelay = `${idx * 0.06}s`;
                el.classList.add('dash-animate-in');
            });
        }, 150);
    }

    async onPageSelect(pageId) {
        this.state.activePageId = pageId;
        await this.renderViewGridStack();
    }

    getMinW(widgetType) {
        const type = (widgetType || '').toLowerCase();
        if (type === 'kpi' || type === 'shortcut') return 3;
        if (type === 'table') return 6;
        return 4;
    }

    getMinH(widgetType) {
        const type = (widgetType || '').toLowerCase();
        if (type === 'kpi' || type === 'shortcut') return 2;
        if (type === 'table') return 4;
        return 3;
    }

    isWidgetVisible(wData) {
        if (!this.state.pages || this.state.pages.length === 0) {
            return true;
        }
        if (!wData.page_id) {
            return this.state.pages.length > 0 ? (this.state.activePageId === this.state.pages[0].id) : true;
        }
        return wData.page_id === this.state.activePageId;
    }

    get allVisibleWidgets() {
        const rawWidgets = Object.keys(this.state.widgetData)
            .map((id) => {
                const wData = this.state.widgetData[id];
                return { id: Number(id), data: wData };
            })
            .filter((w) => this.isWidgetVisible(w.data))
            .sort((a, b) => {
                const seqA = a.data.sequence !== undefined ? Number(a.data.sequence) : a.id;
                const seqB = b.data.sequence !== undefined ? Number(b.data.sequence) : b.id;
                return seqA - seqB;
            });

        // 1. Process dimensions and raw position data
        const processed = rawWidgets.map((w, idx) => {
            const wData = w.data;
            const wType = wData.widget_type || wData.type;
            const minW = this.getMinW(wType);
            const minH = this.getMinH(wType);

            let pos = {};
            try {
                pos = typeof wData.position_json === 'string' ? JSON.parse(wData.position_json || '{}') : (wData.position_json || {});
            } catch (e) {}

            const hasPos = pos.x !== undefined && pos.y !== undefined && !isNaN(pos.x) && !isNaN(pos.y);
            const rawW = pos.w !== undefined ? Number(pos.w) : Number(wData.col_size || minW);
            const rawH = pos.h !== undefined ? Number(pos.h) : minH;
            const colW = Math.min(12, Math.max(minW, isNaN(rawW) ? minW : rawW));
            const colH = Math.max(minH, isNaN(rawH) ? minH : rawH);

            let x = hasPos ? Number(pos.x) : null;
            let y = hasPos ? Number(pos.y) : null;
            if (hasPos && x + colW > 12) {
                x = Math.max(0, 12 - colW);
            }

            return {
                id: w.id,
                data: wData,
                name: wData.name,
                widget_type: wType,
                color_theme: wData.color_theme || 'primary',
                custom_color: wData.custom_color || false,
                sequence: wData.sequence !== undefined ? Number(wData.sequence) : (idx + 1) * 10,
                col_size: String(colW),
                hasPos: hasPos,
                x: x,
                y: y,
                w: colW,
                h: colH,
                position_json: wData.position_json
            };
        });

        // 2. Build 2D Occupied Grid Matrix to prevent overlapping
        const occupied = {};
        const isOccupied = (x, y, w, h) => {
            for (let r = y; r < y + h; r++) {
                for (let c = x; c < x + w; c++) {
                    if (occupied[`${c},${r}`]) return true;
                }
            }
            return false;
        };
        const markOccupied = (x, y, w, h) => {
            for (let r = y; r < y + h; r++) {
                for (let c = x; c < x + w; c++) {
                    occupied[`${c},${r}`] = true;
                }
            }
        };

        // First pass: mark explicit positions
        processed.forEach((w) => {
            if (w.hasPos) {
                markOccupied(w.x, w.y, w.w, w.h);
            }
        });

        // Second pass: allocate non-overlapping slots for unpositioned widgets
        processed.forEach((w) => {
            if (!w.hasPos) {
                let foundX = 0;
                let foundY = 0;
                let placed = false;

                for (let searchY = 0; searchY < 200 && !placed; searchY++) {
                    for (let searchX = 0; searchX <= 12 - w.w; searchX++) {
                        if (!isOccupied(searchX, searchY, w.w, w.h)) {
                            foundX = searchX;
                            foundY = searchY;
                            placed = true;
                            break;
                        }
                    }
                }
                w.x = foundX;
                w.y = foundY;
                markOccupied(w.x, w.y, w.w, w.h);
            }
        });

        // 3. Compact row gaps: Tightly pack contiguous items on each row to remove accidental empty grid gaps
        const rows = {};
        processed.forEach(w => {
            if (!rows[w.y]) rows[w.y] = [];
            rows[w.y].push(w);
        });

        Object.keys(rows).forEach(rKey => {
            const rowWidgets = rows[rKey].sort((a, b) => a.x - b.x);
            let nextAvailableX = 0;
            rowWidgets.forEach(w => {
                if (w.x > nextAvailableX) {
                    w.x = nextAvailableX;
                }
                nextAvailableX = w.x + w.w;
            });
        });

        return processed;
    }

    autoCompactLayout() {
        if (this.gridStackInstance) {
            this.gridStackInstance.compact();
            this.extractCurrentGridNodes();
        }
    }

    async toggleEditMode() {
        if (this.viewGridStackInstance) {
            try { this.viewGridStackInstance.destroy(false); } catch (e) {}
            this.viewGridStackInstance = null;
        }

        this.state.editMode = !this.state.editMode;

        if (this.state.editMode) {
            this.state.editedWidgets = this.allVisibleWidgets.map((w) => ({
                id: w.id,
                name: w.name,
                widget_type: w.widget_type,
                color_theme: w.color_theme,
                custom_color: w.custom_color,
                sequence: w.sequence,
                col_size: String(w.w),
                x: w.x,
                y: w.y,
                w: w.w,
                h: w.h,
                position_json: JSON.stringify({ x: w.x, y: w.y, w: w.w, h: w.h }),
                data: w.data
            }));
            await ensureGridStackLoaded();
            setTimeout(() => this.initGridStack(), 200);
        } else {
            if (this.gridStackInstance) {
                try { this.gridStackInstance.destroy(false); } catch (e) {}
                this.gridStackInstance = null;
            }
            await this.renderViewGridStack();
        }
    }

    initGridStack() {
        if (!window.GridStack) return;
        const gridEl = document.querySelector('.grid-stack-canvas');
        if (!gridEl) return;

        if (this.gridStackInstance) {
            try { this.gridStackInstance.destroy(false); } catch (e) {}
        }

        const isMobile = window.innerWidth < 768;
        this.gridStackInstance = window.GridStack.init({
            float: true,
            cellHeight: isMobile ? 105 : 115,
            column: 12,
            margin: 0,
            animate: true,
            disableOneColumnMode: !isMobile,
            resizable: { handles: 'e, se, s, w' },
            draggable: { handle: '.widget-edit-toolbar' }
        }, gridEl);

        this.gridStackInstance.on('change', (event, items) => {
            if (!items || !Array.isArray(items)) return;
            items.forEach(item => {
                const wId = Number(item.id);
                const target = this.state.editedWidgets.find(w => w.id === wId);
                if (target) {
                    const minW = this.getMinW(target.widget_type);
                    const minH = this.getMinH(target.widget_type);
                    const finalW = Math.max(minW, item.w);
                    const finalH = Math.max(minH, item.h);
                    let finalX = item.x;
                    let finalY = item.y;

                    if (finalX + finalW > 12) {
                        finalX = Math.max(0, 12 - finalW);
                    }

                    if (item.w < minW || item.h < minH || item.x !== finalX) {
                        const el = item.el || document.querySelector(`.grid-stack-canvas .grid-stack-item[gs-id="${wId}"]`);
                        if (el && this.gridStackInstance) {
                            this.gridStackInstance.update(el, { x: finalX, y: finalY, w: finalW, h: finalH });
                        }
                    }

                    target.x = finalX;
                    target.y = finalY;
                    target.w = finalW;
                    target.h = finalH;
                    target.col_size = String(finalW);
                    target.sequence = finalY * 12 + finalX;
                    target.position_json = JSON.stringify({ x: finalX, y: finalY, w: finalW, h: finalH });
                }
            });
        });
    }

    extractCurrentGridNodes() {
        const itemEls = document.querySelectorAll('.grid-stack-canvas .grid-stack-item');
        itemEls.forEach(el => {
            const wId = Number(el.getAttribute('gs-id'));
            if (!wId) return;

            const x = Number(el.getAttribute('gs-x'));
            const y = Number(el.getAttribute('gs-y'));
            const w = Number(el.getAttribute('gs-w'));
            const h = Number(el.getAttribute('gs-h'));

            const target = this.state.editedWidgets.find(item => item.id === wId);
            if (target && !isNaN(x) && !isNaN(y) && !isNaN(w) && !isNaN(h)) {
                const minW = this.getMinW(target.widget_type);
                const minH = this.getMinH(target.widget_type);
                const finalW = Math.max(minW, w);
                const finalH = Math.max(minH, h);
                const finalX = (x + finalW > 12) ? Math.max(0, 12 - finalW) : x;

                target.x = finalX;
                target.y = y;
                target.w = finalW;
                target.h = finalH;
                target.col_size = String(finalW);
                target.sequence = y * 12 + finalX;
                target.position_json = JSON.stringify({ x: finalX, y, w: finalW, h: finalH });
            }
        });
    }

    async saveLayout(isGlobal = true) {
        this.extractCurrentGridNodes();

        const payload = this.state.editedWidgets.map((w, idx) => ({
            id: w.id,
            sequence: w.sequence !== undefined ? w.sequence : (idx + 1) * 10,
            col_size: String(w.col_size || w.w || '4'),
            position_json: w.position_json || JSON.stringify({ x: w.x || 0, y: w.y || 0, w: Number(w.w || 4), h: Number(w.h || 3) })
        }));

        payload.forEach(item => {
            if (this.state.widgetData[item.id]) {
                this.state.widgetData[item.id].sequence = item.sequence;
                this.state.widgetData[item.id].col_size = item.col_size;
                this.state.widgetData[item.id].position_json = item.position_json;
            }
        });

        if (this.gridStackInstance) {
            try { this.gridStackInstance.destroy(false); } catch (e) {}
            this.gridStackInstance = null;
        }

        this.state.savingLayout = true;
        try {
            const res = await rpc("/dashboard/api/layout/save", {
                dashboard_id: Number(this.state.dashboardId),
                widgets_layout: payload,
                is_global: isGlobal
            });

            if (res && res.status === "success") {
                this.state.editMode = false;
                await this.loadDashboardData(true);
            }
        } catch (err) {
            console.error("Lỗi khi lưu layout:", err);
        } finally {
            this.state.savingLayout = false;
        }
    }

    async resetLayout() {
        this.state.savingLayout = true;
        try {
            const res = await rpc("/dashboard/api/layout/reset", {
                dashboard_id: Number(this.state.dashboardId)
            });
            if (res && res.status === "success") {
                this.state.editMode = false;
                await this.loadDashboardData(true);
            }
        } catch (err) {
            console.error("Lỗi khi reset layout:", err);
        } finally {
            this.state.savingLayout = false;
        }
    }

    getColClass(colSize, defaultType) {
        const size = Number(colSize || 4);
        if (size <= 2) return 'col-12 col-sm-4 col-lg-2';
        if (size === 3) return 'col-12 col-sm-6 col-lg-3';
        if (size === 4) return 'col-12 col-sm-6 col-lg-4';
        if (size === 5) return 'col-12 col-md-6 col-lg-5';
        if (size === 6) return 'col-12 col-lg-6';
        if (size === 7) return 'col-12 col-lg-7';
        if (size === 8) return 'col-12 col-xl-8';
        if (size === 9) return 'col-12 col-xl-9';
        if (size === 10) return 'col-12 col-xl-10';
        if (size === 11) return 'col-12 col-xl-11';
        if (size >= 12) return 'col-12';
        return this.getContentColClass(defaultType);
    }

    getContentColClass(widgetType) {
        if (widgetType === 'table') {
            return 'col-12 col-xl-8';
        } else if (widgetType && widgetType.includes('chart')) {
            return 'col-12 col-lg-6';
        } else if (widgetType === 'shortcut') {
            return 'col-12 col-sm-6 col-md-4 col-lg-3';
        } else if (widgetType === 'activity') {
            return 'col-12 col-md-6 col-lg-4';
        } else {
            return 'col-12 col-md-6 col-lg-4';
        }
    }

    getWidgetComponent(widgetType) {
        const reg = widgetRegistry.get(widgetType, null);
        return reg ? reg.component : null;
    }

    async onDrilldown(widget, widgetData = null, resId = null, clickParams = null) {
        if (this.state.editMode) {
            return;
        }

        const data = widgetData || (widget ? this.state.widgetData[widget.id] : null) || {};
        const actionId = data.action_id || data.drilldown_action_id || (widget && widget.drilldown_action_id);
        const modelName = data.model_name || (widget && widget.model_name);

        let baseDomain = [];
        if (data.domain && Array.isArray(data.domain)) {
            baseDomain = [...data.domain];
        }

        if (clickParams && clickParams.group_domain) {
            baseDomain.push(clickParams.group_domain);
        }

        const widgetTitle = (widget && widget.name) || data.name || "Chi tiết dữ liệu";
        const viewTitle = (clickParams && clickParams.label) ? `${widgetTitle} (${clickParams.label})` : widgetTitle;

        if (resId && modelName) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Chi tiết bản ghi",
                res_model: modelName,
                res_id: Number(resId),
                views: [[false, "form"]],
                target: "current",
            });
        } else if (actionId) {
            const options = {};
            if (baseDomain.length > 0) {
                options.domain = baseDomain;
            }
            await this.action.doAction(actionId, options);
        } else if (modelName) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: viewTitle,
                res_model: modelName,
                domain: baseDomain,
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        }
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    async onAddPresetWidget(preset) {
        this.state.sidebarOpen = false;
        const context = {
            default_dashboard_id: Number(this.state.dashboardId),
            default_name: preset.name,
            default_widget_type: preset.type,
            default_col_size: String(preset.defaultW),
        };
        if (this.state.activePageId && Number(this.state.activePageId) > 0) {
            context.default_page_id = Number(this.state.activePageId);
        }

        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: `Thêm Widget Mới: ${preset.name}`,
                res_model: "dynamic.dashboard.widget",
                views: [[false, "form"]],
                target: "new",
                context: context,
            },
            {
                onClose: async () => {
                    await this.loadDashboardData(true);
                    if (this.state.editMode) {
                        this.state.editedWidgets = this.allVisibleWidgets.map((w) => ({
                            id: w.id,
                            name: w.name,
                            widget_type: w.widget_type,
                            color_theme: w.color_theme,
                            custom_color: w.custom_color,
                            sequence: w.sequence,
                            col_size: String(w.w),
                            x: w.x,
                            y: w.y,
                            w: w.w,
                            h: w.h,
                            position_json: JSON.stringify({ x: w.x, y: w.y, w: w.w, h: w.h }),
                            data: w.data
                        }));
                        if (this.gridStackInstance) {
                            try { this.gridStackInstance.destroy(false); } catch (e) {}
                            this.gridStackInstance = null;
                        }
                        setTimeout(() => this.initGridStack(), 150);
                    }
                },
            }
        );
    }

    async onDatePillChange(pillId) {
        this.state.activeFilterPill = pillId;
        this.state.filterValues = {
            ...this.state.filterValues,
            date_pill: pillId
        };
        await this.loadDashboardData(true);
    }

    async onGlobalFilterChange(filterName, value) {
        this.state.filterValues = {
            ...this.state.filterValues,
            [filterName]: value
        };
        await this.loadDashboardData(true);
    }

    async onExportExcel() {
        try {
            const res = await rpc("/dashboard/api/export/excel", {
                dashboard_id: Number(this.state.dashboardId),
                filter_values: this.state.filterValues,
            });

            if (res && res.status === "success" && res.file_base64) {
                const byteCharacters = atob(res.file_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = res.filename || "Dashboard_Report.xlsx";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        } catch (err) {
            console.error("Lỗi khi xuất Excel:", err);
        }
    }

    async onRefreshClick() {
        // Add spin animation to refresh buttons
        const refreshBtns = document.querySelectorAll('.btn-refresh');
        refreshBtns.forEach(btn => btn.classList.add('is-refreshing'));
        await this.loadDashboardData(true);
        refreshBtns.forEach(btn => btn.classList.remove('is-refreshing'));
    }
}

registry.category("actions").add("action_dashboard_viewer", DashboardViewerAction);
