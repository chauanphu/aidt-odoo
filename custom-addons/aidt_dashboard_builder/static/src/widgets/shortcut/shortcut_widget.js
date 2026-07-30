/** @odoo-module **/

import { Component } from "@odoo/owl";
import { widgetRegistry } from "../../services/widget_registry";

export class ShortcutWidget extends Component {
    static template = "aidt_dashboard_builder.ShortcutWidget";
    static props = {
        widget: Object,
        data: Object,
        onDrilldown: { type: Function, optional: true },
    };

    onClick() {
        if (this.props.onDrilldown) {
            this.props.onDrilldown(this.props.widget, this.props.data);
        }
    }
}

widgetRegistry.add("shortcut", { component: ShortcutWidget, name: "Phím tắt" });
