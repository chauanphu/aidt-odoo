/** @odoo-module **/

import { Component } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

export class KpiWidget extends Component {
    static template = "aidt_dashboard_builder.KpiWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    onClick() {
        if (this.props.onDrilldown && this.props.widget.drilldown_action_id) {
            this.props.onDrilldown(this.props.widget);
        }
    }
}

widgetRegistry.add("kpi", {
    component: KpiWidget,
    name: "Thẻ KPI",
});
