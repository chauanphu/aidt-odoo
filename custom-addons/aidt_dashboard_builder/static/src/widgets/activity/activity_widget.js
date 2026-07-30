/** @odoo-module **/

import { Component } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

export class ActivityWidget extends Component {
    static template = "aidt_dashboard_builder.ActivityWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };
}

widgetRegistry.add("activity", { component: ActivityWidget, name: "Hoạt động gần đây" });
