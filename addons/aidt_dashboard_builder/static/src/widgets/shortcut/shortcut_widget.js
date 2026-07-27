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
}

widgetRegistry.add("shortcut", { component: ShortcutWidget, name: "Phím tắt" });
