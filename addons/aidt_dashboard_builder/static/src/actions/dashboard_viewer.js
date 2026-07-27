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

export class DashboardViewerAction extends Component {
    static template = "aidt_dashboard_builder.DashboardViewerAction";

    setup() {
        this.action = useService("action");
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
        });

        onWillStart(async () => {
            await ensureChartJSLoaded();
            await this.loadDashboardList();
            await this.loadDashboardData();
        });
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
                this.state.pages = res.pages || [];
                this.state.filters = res.filters || [];
                if (this.state.pages.length > 0 && !this.state.activePageId) {
                    this.state.activePageId = this.state.pages[0].id;
                }
                this.state.widgetData = res.data || {};
            } else {
                this.state.error = (res && res.message) ? res.message : "Lỗi tải dữ liệu Dashboard";
            }
        } catch (err) {
            this.state.error = err.message || "Lỗi kết nối Server";
        } finally {
            this.state.loading = false;
        }
    }

    async onDashboardSelect(ev) {
        const selectedId = Number(ev.target.value);
        if (selectedId && selectedId !== this.state.dashboardId) {
            this.state.dashboardId = selectedId;
            this.state.activePageId = 0;
            await this.loadDashboardData(true);
        }
    }

    onPageSelect(pageId) {
        this.state.activePageId = pageId;
    }

    isWidgetVisible(wData) {
        if (!this.state.pages || this.state.pages.length === 0) {
            return true;
        }
        if (!wData.page_id) {
            return true;
        }
        return wData.page_id === this.state.activePageId;
    }

    get kpiWidgets() {
        return Object.keys(this.state.widgetData)
            .map(id => ({ id, data: this.state.widgetData[id] }))
            .filter(w => (w.data.type === 'kpi' || w.data.widget_type === 'kpi') && this.isWidgetVisible(w.data));
    }

    get contentWidgets() {
        return Object.keys(this.state.widgetData)
            .map(id => ({ id, data: this.state.widgetData[id] }))
            .filter(w => (w.data.type !== 'kpi' && w.data.widget_type !== 'kpi') && this.isWidgetVisible(w.data));
    }

    getContentColClass(widgetType) {
        if (widgetType === 'table') {
            return 'col-12 col-xl-8';
        } else if (widgetType && widgetType.includes('chart')) {
            return 'col-12 col-lg-6';
        } else {
            return 'col-12 col-md-6 col-lg-4';
        }
    }

    getWidgetComponent(widgetType) {
        const reg = widgetRegistry.get(widgetType, null);
        return reg ? reg.component : null;
    }

    async onDrilldown(widget, widgetData = null) {
        const actionId = widget.drilldown_action_id || (widgetData && widgetData.drilldown_action_id);
        const modelName = widgetData && widgetData.model_name;

        if (actionId) {
            await this.action.doAction(actionId);
        } else if (modelName) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: widget.name || "Chi tiết dữ liệu",
                res_model: modelName,
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
