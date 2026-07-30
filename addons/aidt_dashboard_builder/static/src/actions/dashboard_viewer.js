/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { widgetRegistry } from "../services/widget_registry";

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

    setup() {
        this.action = useService("action");
        this.onDrilldown = this.onDrilldown.bind(this);
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
        });

        onWillStart(async () => {
            await ensureChartJSLoaded();
            await this.loadDashboardList();
            await this.loadDashboardData();
        });
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

            this.viewGridStackInstance = window.GridStack.init({
                staticGrid: true,
                float: true,
                cellHeight: 110,
                column: 12,
                margin: 10,
                animate: true,
                disableOneColumnMode: true
            }, gridEl);
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
        return Object.keys(this.state.widgetData)
            .map((id, idx) => {
                const wData = this.state.widgetData[id];
                const wType = wData.widget_type || wData.type;
                const minW = this.getMinW(wType);
                const minH = this.getMinH(wType);
                let pos = {};
                try {
                    pos = typeof wData.position_json === 'string' ? JSON.parse(wData.position_json || '{}') : (wData.position_json || {});
                } catch (e) {}
                const rawW = pos.w !== undefined ? Number(pos.w) : Number(wData.col_size || minW);
                const rawH = pos.h !== undefined ? Number(pos.h) : minH;
                const colW = Math.max(minW, isNaN(rawW) ? minW : rawW);
                const colH = Math.max(minH, isNaN(rawH) ? minH : rawH);

                const safeX = (pos.x !== undefined && !isNaN(pos.x)) ? Number(pos.x) : (idx % 3) * 4;
                const finalX = (safeX + colW > 12) ? Math.max(0, 12 - colW) : safeX;
                const finalY = (pos.y !== undefined && !isNaN(pos.y)) ? Number(pos.y) : Math.floor(idx / 3) * 3;

                return {
                    id: Number(id),
                    data: wData,
                    name: wData.name,
                    widget_type: wType,
                    color_theme: wData.color_theme || 'primary',
                    sequence: (wData.sequence !== undefined) ? Number(wData.sequence) : (idx + 1) * 10,
                    col_size: String(colW),
                    x: finalX,
                    y: finalY,
                    w: colW,
                    h: colH,
                    position_json: wData.position_json
                };
            })
            .filter(w => this.isWidgetVisible(w.data))
            .sort((a, b) => a.sequence - b.sequence);
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

        this.gridStackInstance = window.GridStack.init({
            float: true,
            cellHeight: 110,
            column: 12,
            margin: 10,
            animate: true,
            disableOneColumnMode: true,
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

    async onRefreshClick() {
        await this.loadDashboardData(true);
    }
}

registry.category("actions").add("action_dashboard_viewer", DashboardViewerAction);
